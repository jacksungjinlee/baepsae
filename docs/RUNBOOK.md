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
both separate from our pipeline); the last daily run and the last deploy succeeded (a daily run that held its publish on a backup
morning, dates going back or a lost stock is skipped, so the run before it counts; a same-day run that passed the gate and the
screen check but was not better counts as healthy: "Backup days: coverage floor and same-day updates"); the daily run is still
switched on;
the pages users get are the current build, the site's `data.json` is exactly the published copy, and the site does not
serve the `docs/` folder (two of its files must answer "not found").
A server error from GitHub Pages (HTTP 5xx) on a data file or page is asked again once, 20 seconds later, before it
counts (Jack, 2026-11-19): a second 5xx or any other failed answer is a problem as before, and once one retry has failed
the alarm is certain, so later 5xx answers in that check fail at once without waiting (the run cannot overrun its
30-minute limit and end with no alarm). A "not found"-type answer (4xx) is never asked again. Every line about it in the
run log starts "5xx 다시 물음", and the count ("· 5xx 다시 물음: N곳") ends the log and, when N > 0, the run's summary page.

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
    to `v2` in the cache key, in all seven places (`update-data.yml` twice, `ci.yml` four times, `deploy.yml` once; a
    small PR), so a fresh copy is downloaded. The tests accept any version number as long as every place uses the same
    one, so no test edit is needed. If the step "브라우저 · 한글 글꼴 준비" fails on the font line instead, the runner's
    font setup changed: fix `tests/fonts/install.sh` in a PR.
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
      the data, and guarantees a beta and volatility for none of the US ones one by one. Since 2026-11-13 the gate
      fails when fewer than 95% of all US stocks have a beta, or a volatility, and warns below 97% (rows "미국 beta 채움"
      and "미국 vol 채움", the Korean rule; their change rows mirror the Korean ones and never fail before the floor
      does). Below 97% the row's value names the first 10 blank stocks (so the 09:13 check sees them) and the
      log and step summary list them all ("미국 beta 빈 종목"). Read the names: if they are new listings (less than 250
      trading days of prices, so the pipeline leaves beta and volatility blank by design), tell Jack before the share
      reaches 95%; do not lower the floor. If they are long-listed names, suspect the pipeline, with one standing
      exception: ABVX has a beta but no volatility (its volatility is above the pipeline's 300% cap). A Yahoo outage
      drops tickers from the list rather than blanking them, so these rows don't see it; "미국 종목 수 변화" catches
      it only when more than 15% of US stocks go missing, and a smaller outage shows in no gate row. When a built-in stock is missing from
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
  fixed day (`tests/testclock.py`). So a pull request's code meets today's real data in the daily run above, in the
  deploy check below (since #115, every deploy that changes code runs the same three checks before publishing), or when
  the three commands are run by hand: `python tests/real_data_check.py --data DIR`, `python tests/smoke_launch.py --data DIR`
  and `python tests/smoke_app.py --data DIR`. To run them by hand (to look into a blocked deploy, or whenever `CLAUDE.md`
  asks for it before a merge): put a fresh copy of
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
- **The deploy check (since #115, Jack 2026-11-12).** Every deploy that changes code (a merge to `main`, or Actions →
  Deploy → Run workflow) runs the daily run's three checks before anything is uploaded: on the four data files it is
  about to publish, exactly as they are in the folder it uploads, with the code it has just built (steps "배포 전 화면
  검사 …" in Deploy, `tools/deploy_check.py`). The same `--data` rules as the daily run apply (`!! 확인 못 함` and
  `!! 알림` lines pass and are listed in the run's summary and as yellow warnings).
  - **The deploy after a daily publish** skips the checks only when both of these hold: every commit between the commit
    that daily run checked and the commit being deployed changed nothing but the four data files (a file renamed into
    one of them counts as code), and the four files it uploads are exactly the ones in the `data` commit that run made
    (by `baepsae-bot`, during that run). That run already checked those files with that code just before publishing.
    If either can't be shown, it runs the checks like a code deploy.
  - **All three pass:** it publishes as before. A code deploy takes about 3 to 4 minutes longer than before (the daily
    run's same check takes about 3 minutes, almost all of it `smoke_app`).
  - **One fails:** it finds the code the site serves now (the build mark `baepsae-build` in the live pages), fetches
    that commit into a separate scratch repository (never into the checkout), builds it in a separate folder without
    running any package install scripts, and the rebuilt pages must match the live ones byte for byte. Then it runs
    the failed checks again with that code on the same files. This takes up to about 3 more minutes (less when
    `smoke_app` passed), so about 7 minutes in all. Then it compares **line by line** (a "check" is one result line,
    about 162 of them across the three scripts):

    | New code | Live code, same files | Result |
    |---|---|---|
    | passes | (not run) | publish |
    | fails a line | passes that line, or passes the whole script | **blocked** |
    | fails some lines | fails every one of them too | **published, Jack told** |
    | stops before its result line | runs to its result line | **blocked** |
    | fails | can't be found, fetched, built or matched, or stops before its result line, or its lines can't be read | **blocked** (unknown) |

    The lines a block is about (the ones only the new code fails) come first in the red line and the summary.
    `smoke_launch` stopping on purpose because the data lacks a field 2.0 needs counts as one failing line on both
    sides, not as a stop, so a fix for that data can still go live.
    **Same code:** when every file except the four data files is the same in the live commit and the new one (a manual
    deploy, or a data deploy that had to run the checks), a difference can only be a flaky scene or the clock. The
    deploy then runs the blocked script once more with the new code: if it passes, it publishes; if it fails again, it
    publishes and tells Jack, saying exactly that ("같은 코드인데 두 번 실패", with the lines; not "the live code fails
    too"). It never blocks the same code against itself, so a flaky scene can't hold the morning data.
    Each script has its own 20-minute limit inside the step; one that hangs is stopped and counts as stopping before its
    result line.
    - **Blocked deploy:** the Deploy run ends red before anything is uploaded, so users keep the site exactly as it was.
      The run page shows a red line "배포 막음 · 배포 전 화면 검사" naming the script, both results and the lines only the
      new code fails (for example `smoke_app: 새 코드 141 / 145 통과 · 지금 사이트 코드 145 / 145 통과`), and its
      summary says "뱁새 배포 전 화면 검사 — 막음". Lines that the live code fails too are shown as yellow warnings
      "배포 · 지금 사이트 코드도 실패하는 줄" in the same run. The watchdog opens (or comments on) the 뱁새 데이터 경보
      issue about 10 minutes later, because the last deploy failed.
      **What to do after a merge:** `main` is now ahead of the site, and the next daily run checks its new data with
      `main`'s code, so it will probably hold that morning's publish too. If the failing line looks like a one-off (a
      single timing scene), start Actions → Deploy → Run workflow once; if it fails again, revert the merge at once (a
      revert PR, merged), then fix forward in a new PR.
      **What to do when the blocked deploy came after a daily publish** (the code changed during that run, or its files
      couldn't be matched, so the checks ran): that day's new data is on the `data` branch but not on the site, so users
      see yesterday's numbers with yesterday's date. Revert or fix forward fast, then start Actions → Deploy → Run
      workflow to put the data out.
      **The revert's own deploy can be blocked too** (the old code fails a line the code being reverted passes). Start
      Actions → Deploy → Run workflow once more; if it is blocked again, fix forward in a new PR instead of reverting
      further.
      Never skip or loosen a check to get a deploy out.
    - **"Live fails too":** the new code fails only lines the code the site serves now also fails on the same files.
      That is not the new code's doing (usually the data, the clock or the machine), so the deploy goes ahead (a fix for
      a data problem must be able to go live) and Jack is told: before the upload, the 뱁새 데이터 경보 issue gets the
      label `deploy-check` and a post whose first line is **[배포 화면 검사]**, saying the new code is being put up and
      listing each failing line once (a new issue if none is open). The run shows a yellow warning "배포 · 지금 사이트
      코드도 실패" and no red lines. If the upload then fails, the site stays as it was and the watchdog reports the
      failed deploy; the label stays right either way, because the live code fails those lines too.
      The watchdog does not close an issue that has the `deploy-check` label (it doesn't run these browser checks, so
      it can't say they are fixed). The label comes off by itself when a later deploy passes all three: a code deploy,
      or the deploy after the next daily publish (that run checked its files with the same code). The watchdog then
      closes the issue at its next check. If the issue can't be opened (GitHub trouble), nothing is uploaded: a deploy
      over a failing check always tells Jack. Start Actions → Deploy → Run workflow again later.
      This is also what happens when the data is so broken that neither code can load it (both fail the same lines):
      Jack's rule publishes and tells him. The gate (`validate_data.py --live`) still runs first and blocks data that
      fails it.
      **What to do:** as for any alert (paste the issue into a Claude Code session).
    - **Live code unknown:** blocked, with the reason after "지금 사이트의 코드를 알 수 없어요" (the live site was
      unreachable, a page had no build mark, the commit couldn't be fetched, the rebuild differed, or the live run
      stopped early). This is not the new code's fault and needs no revert: once the live site answers again, start
      Actions → Deploy → Run workflow. If it stays unknown, look at the reason in the run log.
    - **The check machinery itself is down** (for example the browser can't be downloaded or started): every script
      stops before its result line with both codes, so every code deploy is blocked, reverts included. Fix the
      machinery first (the cache key, `tests/fonts/install.sh`, a pinned version; see the screen check above), then
      start Actions → Deploy → Run workflow. Data deploys that can skip the checks are not affected.
  - Always start a new run with **Actions → Deploy → Run workflow**. "Re-run" on an old run uses that run's old
    workflow file, which may not have this check at all.
  - Both runs use this deploy's Python tools, browser and font; only the app code and the check scripts differ.
  - The deploy's checkout keeps no token in the working folder. Only the three steps that call the GitHub API (the gate,
    "필요한지", "결과") get the token; the three checks, their tools and the browser never see it. npm packages are
    installed without their install scripts, for the site build and the live rebuild alike (the built pages are the
    same byte for byte).
- **US companies whose financial statements are not in dollars (since #114).** The daily run marks them `fcur` (Yahoo's
  financialCurrency, 27 on 2026-11-12) and blanks their PER, PBR and dividend yield (a 0% stays only when Yahoo clearly
  shows no dividend in the last 12 months). When Yahoo answers with only part of a company's details (no currency, sector
  or description), the run keeps the last known values from the US info cache (only from the same company, or from an
  entry at most 14 days old) and **the next run asks again**: such an answer is never kept as fresh for 3 days. Five
  gate rows:
  - "미국 재무제표 통화가 달러가 아닌 회사: … 빈 칸" and "미국 PBR 0 근처라 비운 종목: …" fail if a blanked number is back:
    a pipeline bug, never the market. Fix the code; never loosen the row.
  - "미국 재무제표 통화를 모르는 회사 (경고만)" names companies whose currency Yahoo did not give (FISV on 11-12). They are
    not blanked; the next run asks Yahoo again. Look at their PBR on the site if the same name stays for days.
  - "미국 상세 정보가 일부만 온 종목 (예전 값으로 채움 · 경고만)" names the stocks whose details were filled from the cache
    today, with their share of all US stocks. The "미국 설명 채움" row cannot see a bad Yahoo day any more (the cache fills
    the gaps), so this row is where it shows. A few names: nothing to do, the next run asks again. Many (more than about
    10%, or the same names day after day): Yahoo is answering badly; tell Jack before the cached details grow old.
  - "어제 재무제표 통화가 있던 미국 종목이 오늘 통화 없음": **fails** only when such a company has no currency information
    today and its PER, PBR or yield is back. The run keeps the last known currency when Yahoo leaves it out, so a failure
    means something broke. What to check, in the run log: did the US info cache come back ("미국 상세 정보 보관본 N곳" near
    the usual ~770; "보관본 없음" means the cache was lost), and the lines "야후 응답에 재무제표 통화가 없어 예전 값을 그대로 씀"
    and "일부만 온 야후 응답 … 다음 실행에서 다시 물어봐요". If the cache was lost, Yahoo left the currency out on a day with
    nothing to fall back on: the next scheduled run asks again, and it usually publishes. If the cache is there and the
    row still fails, the merge is broken: fix the code in a PR. Never get around it with a bootstrap run (`--bootstrap`
    skips the comparison with yesterday and would publish the wrong numbers) or by loosening the row.
    It **warns** with "야후가 이제 달러 재무제표라고 함 — 숫자를 확인하세요" when Yahoo now says the company reports in dollars
    (numbers or not; the publish goes out): open the company on the site and compare its PBR and PER with the company's
    own report; if they look wrong, tell Jack. It also warns when a company has neither a currency nor numbers.
- The issue's first line says which case it is. If it says the files **on the site** failed the checks
  ("검사를 통과하지 못했어요"), users may be seeing wrong numbers: treat that one as urgent.
- An issue whose first line starts with **[시험]** is a test that Claude ran on purpose. The site is fine.
- An issue (or comment) whose first line starts with **[배포 화면 검사]** comes from a deploy: new code was put up although
  real-data check lines fail, because the code the site served before fails the same lines on the same files ("The
  deploy check" above). Users may see what the check caught: look at it soon.
- The same test also sends healthchecks.io one failure signal, so Jack gets a "down" email, then rechecks the real site
  and, if it is fine, sends the normal signal ("up" email, usually within a minute) and closes the [시험] issue. A "down"
  email with no "up" email after it means the recheck found a real problem.

## What to do

Open a new Claude Code Cloud session and paste (replace N with the issue number, which is also written in the issue):

> 뱁새 데이터 경보 이슈 #N 이 떴어. 로그를 보고 원인을 찾아서 CLAUDE.md 규칙대로 고치고 PR 열어줘.

Claude reads the run logs, fixes the cause by the CLAUDE.md rules (fix the data or the code, never loosen a check), and
tells you what happened in plain words.

## Checks on our own processing: drop or blank, then publish (Jack's standing rule, since #149)

Jack, 2026-11-19: "Standing rule for checks on our own processing: a single bad row is dropped or blanked with a loud warning and
the rest publishes. Block only when many rows fail in one run (set the number from recent runs and show it in the PR) or when a
value would show a wrong number."

"Own processing" means a check that catches a mistake in how our pipeline read, mapped or derived something (shape, consistency,
mapping). Checks on what a source sends (freshness, coverage, two-source agreement, must-have stocks) are not covered and keep
their rules. One exception, by Jack's own answer (2026-11-20, verbatim): "Brown-Forman B: no, it becomes a warning; one stock missing
from a source never holds the publish." So "주식 종류 티커로 들어온 미국 종목 (BF-B)" only warns when BF-B is missing, with or without a
reason (see "US share-class tickers" below). The same answer now covers the hand-added US stocks (#162, Jack 2026-11-21: "Yes,
warn."): one missing with no reason warns; more than 5 still fails (see "US stocks added by hand (EXTRA_US)" below).

**How it works.** The rule that picks the bad rows lives once, in `validate_data.py`. The daily run calls the same function on its
in-memory data, drops or blanks those rows, logs them and records them in `data.json` `ownDrop`; the gate then checks the file.

| Check (PR) | Function | What the run does with a bad row | Recorded as | N |
|---|---|---|---|---|
| US share-class tickers (#139): an S&P 500 joined form (`BRKB`, `BFB`) published unmapped; such a form when the record can't tell where it came from; a ticker mapped differently from the gate's table | `us_class_bad_rows` | **drops the US row** right after the US list is built (before industries, ranks, splits, the popular list and counts), together with that ticker's entries in the run's own US records (split rows from the price download, `usForeign`, `usInfoPartial`, `usFcurUnknown`, `usInfo`): its price, market cap and scores may be another security's, so blanking one value would leave wrong numbers | `ownDrop.usClass` | 5 |
| Hidden-yield reason lines (#142): a `dvLine` 2, 3 or 4 that `divCheck.proofSub` does not back (another line, a case with no line, a record that is missing or malformed, a preferred share, a stock whose yield shows, a restored stock) | `div_line_bad_rows` | **blanks that stock's `dvLine`** just before the files are written: the yield stays blank as it was and the app shows no reason line instead of one that may be wrong. A stock whose record calls for a line it does not carry is counted too (nothing to blank; it shows a blank with no reason) | `ownDrop.divLine` | 5 |

`ownDrop` is `{"usClass": {"n": rows, "rows": [[key, reason], …first 30]}, "divLine": {…}}`, written on every run (0 on a clean run).
Run log: `!! {check}: {n}건 빼고 발행` (US) or `!! {check}: {n}건 비움` (lines), with the first 30 keys and reasons, or a `· … 0건` line.

**Gate.** For each of these checks the publish fails only when (1) more than N rows were dropped or blanked in the run, or (2) a
bad value is still in the file and would show a wrong number or a wrong reason line (the drop step itself broke). 1 to N rows:
warning, naming them (detail lists "파이프라인이 뺀 미국 종목" and "파이프라인이 비운 숨긴 배당수익률의 줄"). Record problems that
show users nothing are warnings: a malformed `proofSub` (its lines are blanked and counted), a mapping that differs from the table with
no published row left, a line the record asks for but the stock lacks, and a malformed `usListSym` field the joined-form and mapping
checks don't depend on. One record problem still fails the publish, as it did before: any malformed `usListSym.mapped` row (`mapped`
only ever holds the joined-form rows, so with a bad row the gate can't tell where a joined form was mapped and can't rule out a wrong
company in the list; the site checks warn). The rows that are well formed are still read one by one, so a wrongly mapped row is still
dropped. For the lines, the count is the number of distinct stocks that lose their reason line in the run: lines blanked today, lines
still wrong in the file, and lines 2 · 3 · 4 of the previous publish that today's `proofSub` can't back because that part is missing or
malformed (the record and the lines vanishing together blank nothing, but those stocks still lose their line). These are usually
different stocks, so they are added up, not compared. The run log counts the same stocks (it reads the previous publish).
On the site checks (`--live`: deploy and watchdog) "more than N" warns instead of failing, and the US rows keep #139's live behaviour.
A file without `ownDrop` (published before #149) keeps the old rule for that row, so the live gate and the watchdog are not blocked by
it; a malformed `ownDrop` (the whole object or one entry) also keeps the old rule and adds a warning.

**N** = max(5, 3 × the highest count seen). Replayed over the last 25 publishes on the `data` branch (2026-11-06 to 11-19): 0 for
both checks every time, so N = 5 (`US_CLASS_DROP_MAX`, `DIV_LINE_BLANK_MAX`; the table is in PR #149). Jack, 2026-11-20: "Yes to “more
than 5 rows” as the default for the standing rule." For scale: the 11-19 file has
800 US stocks and 30 lines 2·3·4, so a broken record that blanks all 30 lines (or loses them with the record) fails the gate, as it should.
**The US count cannot realistically pass 5:** its rows come only from the two table forms (`BRKB`, `BFB`), at most one joined row and one
wrongly mapped row each, so about 4 a run (only a hand-made, malformed record could list more). N = 5 is the rule's floor; what protects
this check is the other fail: a row that should have been dropped is still in the file.

**When the gate warns** (rows dropped or blanked, 1 to N): the publish went out without those rows. Read the reasons in the gate's
detail list and the run log. A US row: the mapping table (`fetch_data.US_CLASS_JOINED` vs `validate_data.US_CLASS_JOINED_SET`) or
Yahoo answering a joined form; fix with the recipe in "US share-class tickers" below. A line: the pipeline's `prove_line` and
`proof_sub` disagree, or the record broke; fix the code in `DivWhy.prove`. The rows stay out until the fix ships; nothing else waits.

**When the gate fails**: "뺀 행이 기준 5 을 넘음" or "줄을 잃은 종목이 기준 5 을 넘음" means many rows broke at once: our reading is
probably broken for everyone, so nothing is published (users keep the last good data). "빼야 할 티커가 남아 실림" or "기록과 맞지 않는
줄이 남음" means the drop step did not run or did not work: fix the pipeline. "mapped 에 모양이 틀린 줄이 있어 …" means `us_tickers`
wrote a broken mapping record: fix the record code. Never raise N or skip the row to get a publish out;
a different N needs Jack's yes with new evidence.

**Our own text and the gate's word row (2026-11-24, #178).** The row "글자에 nan·None·null·undefined 없음" (`validate_data.BAD_WORD`,
frozen) reads every string in the four files. The pipeline used to write those words itself: a "never stop the publish" step stored its
error text (`pxSrc.own.err`, `usSrc.own.err`, the `ownDrop.krOwn` and `usExtraMissing` reasons), the records above stored the bad value
in the reason (`"칸 없음 d; d null"`, `role "None"`), and other record reasons printed a missing value (`usForeign.cut` "야후
financialCurrency None", a `d1Base.ex` name "nan", "마지막 확인 종가(None)"), so one caught error or one bad row stopped the whole
publish. What is true now:
- The guards and the own-check records clean their text where they write it (`fetch_data.pub_text` / `pub_err` / `own_drop_pub`).
- Right before data.json is written, `pub_sweep` runs the same cleaning over every string in the pipeline's own record fields
  (`PUB_SWEEP_KEYS`: `pxSrc`, `usSrc`, `splitsInfo`, `usForeign`, `usExtraMissing`, `usListSym`, `d1Base`, `ownDrop`; disc.json:
  `ownDrop`). Stock, company and filing rows are not touched. The reason builders are unchanged.
- The cleaning: first the literal values of the DART and ECOS keys (and `GITHUB_TOKEN`) from the environment become "…", then the text is
  cut (300 characters for error fields), then anything after `?` in a URL, a URL's user part, the ECOS key in its URL path, and
  key-like values (`key=`, `crtfc_key: …`, `('crtfc_key', '…')`, `X-Api-Key:`, `Bearer`, `Authorization`, `Cookie`) become "…", and
  each whole-word match of the gate's own pattern (imported) becomes "빈 값". Only words change, so reason prefixes the gate and
  `us_fgn_kind` read (`US_FOREIGN_CUR_WHY`) stay intact. The raw text (first 4,000 characters) stays in the run log only (GitHub masks
  registered secrets there). The app never reads these fields. `splitsInfo.err` goes to the run log only (data.json carries `noCol`).
- Source text is not rewritten: when a Yahoo summary (`de`) or a DART filer's position (`pos`) contains such a word, `own_src_text` blanks
  that one field right before the write (log: `!! 출처 글자의 관문 낱말 …: {file} n칸 비움 — {stock} {field} …`) and counts it in that
  file's `ownDrop.srcText`. More than 5 fields in one file (`SRC_TEXT_MAX`, Jack's default N; every past publish has 0 because the row
  passed): nothing is blanked, the log says so, and the word row itself fails, so no new gate row exists. disc.json is rebuilt daily
  from the whole 90-day insider window, so its count covers that window, not only the day's new filings. Insider names (`nm`: the screens
  show `{nm} · {pos}`, so a blank name would leave numbers with no name and no reason), stock names and `dk` (the field of the 2026-10
  column-shift incident) are left to the row as before.

## Checked low-PBR companies (gate warning "PBR 0.1 미만 국내 회사")

The daily gate (`validate_data.py`) warns, by name, about every Korean company with a PBR under 0.1 that the unit check
(`fetch_data.py` `unit_guard`, corp.json `unitChk`) did not flag: a PBR that low can mean a filing read in the wrong unit
(진코스텍 and 디와이에이, 2026-11-13). The 09:13 check reports every warning, so a company a person has already checked goes
on the list `PBR_LOW_CHECKED` in `validate_data.py` and is not named again. It stays quiet only while its owners' equity
(corp.json `bpsIn.eq`, 억원) is within ±20% (`PBR_LOW_BAND`) of the value written there and it has no `unitChk`; if the
equity moves further (a new report, a capital change), the warning names it again, with the old and new equity, so
someone looks again. The row's value always says how many were passed over quietly ("확인된 회사 N곳 조용히 넘김"), and the
gate's summary lists them.

To add a company (each entry, and the list itself, needs Jack's yes first: an entry exempts one company from a warning,
so it is a safety-rule change under CLAUDE.md; the list and its two entries, SG&G and 앱토크롬: Jack's yes, 2026-11-13):
1. Claude opens the company's latest filed statements on DART (the report the pipeline used, corp.json `bq`, and the
   latest 사업보고서) and checks that the unit printed over the statements is the unit of the numbers, that total assets =
   liabilities + equity, and that the report's previous year-end column equals the 사업보고서's figures.
2. Claude asks Jack in one line, with that evidence: "Quiet the low-PBR warning for {name}? (filings {rcept}: …)".
3. On his yes, one entry: the stock code → `date` (the KST day of the check), `eq` (today's corp.json `bpsIn.eq`), `why`
   (the name, why the PBR is low, and the filings' receipt numbers as `rcept` followed by the 14 digits) and `yes` ("Jack's
   yes, " and the KST day he said it). Then a PR as usual (tests, fresh-eyes review, his yes recorded under **안전 규칙
   변경**). `tests/test_unit_guard.py` checks every entry names a filing and carries his yes.

The list only quiets that warning: every FAIL row is unchanged, the unit check still blanks a flagged company's numbers
whatever the list says, and a listed company whose equity moves by more than 20% is named again. Remove an entry when the
company's PBR is back above 0.1 for good, or if a later check finds its filing wrong. The PER warning ("PER 0.1 미만 국내
회사") has no such list.

## Unit-check gate rows (공시 단위 확인)

The pipeline (`fetch_data.py` `unit_guard`) blanks every number built on a Korean company's statements when they look read
in the wrong unit, and marks the company `unitChk` (data.json and corp.json). The run log names each one on its own line
("!! 공시 단위: {code} {name} [reasons — evidence] 비운 값: …"). Four gate rows watch it; Jack said yes to the three FAIL rows
on 2026-11-13:

- **WARN "공시 단위 확인 회사 바뀜 (unitChk · 경고만)"**: a company is newly flagged (its numbers are now blank) or cleared
  since the previous publish (20 or more newly flagged also fails the next row). For a newly named company, Claude opens
  the filing the pipeline used (corp.json `bq`, or the latest 사업보고서) on DART and checks the unit printed over the
  statements against the numbers, and the report's previous year-end column against the 사업보고서. If the filing is wrong,
  nothing to do: the company stays blank until it refiles, and the line on its page says why. If the filing is right and
  the check is wrong, the reasons in the log line say which check fired; the fix is in the code or the data (a PR, with
  tests), never a looser threshold (a safety rule: ask Jack). There is no list that clears a company by hand. A cleared
  company needs nothing unless the reason is surprising (DART down clears everyone: other rows fail that run anyway).
- **FAIL "공시 단위 확인에 새로 걸린 회사 수 (20곳 이상이면 실패)"** (Jack, 2026-11-13): 20 or more Korean companies newly
  flagged in one publish, compared with the previous publish (cleared companies don't count; no previous publish, no
  FAIL). Real filing mistakes come one or two at a time, so this means our reading probably broke (a parser change, a
  change in DART's amounts or units, a bad cache), not 20 companies misfiling at once. The site keeps yesterday's data.
  First read the run's "!! 공시 단위:" lines: if they share one reason or one kind of report, fix that in the code (a PR,
  with tests) and run again. Never raise the number of 20 without Jack.
  It keeps failing until it is fixed: a failed run publishes nothing, so the next run compares with the same previous
  publish and counts the same companies as new. There is no way to wave it through; if the 20 turn out to be real,
  unrelated filing mistakes (never seen: the whole flagged population was 2 on 2026-11-13), tell Jack with the list.
  The first publish after #118 counts every flagged company as new (the previous file has no flags). Watch the
  first runs on a new reporting quarter (2026 Q3 reports: deadline 2026-11-16), when the income, cash-flow and
  quarter-EPS checks first see about 2,200 new reports in one publish.
- **FAIL "공시 단위 확인 기록 (unitChkCover)"**: the previous publish had the check's record and this run's data.json does
  not (or it is not version 1). The pipeline writes it on every run whatever DART or the cache does, so this means the
  code that runs the check or writes the record is missing: first check which commit the run used and that
  `fetch_data.py` `main` still calls `unit_guard` and writes `"unitChkCover"`. When the record's shape changes on purpose,
  bump `v` and change `validate_data.py` `check_unit_ran` in the same PR (the gate accepts only the version it knows, so
  an unchecked shape never passes).
- **FAIL "unitChkCover.hit = unitChk 종목 수"**: the number of companies the check flagged differs from the stocks marked
  in data.json, so something after the check added, dropped or changed stocks or marks. First compare the run log's
  "공시 단위 확인: N곳 비움" with the marked stocks, then look at what `main` does between `unit_guard` and writing
  data.json.

## Companies read with a corrected unit (gate warning "공시 단위를 고쳐 읽은 회사")

When a Korean company files a quarterly report with the wrong unit printed over the numbers (천원 over numbers in 원, so
every amount is 1,000 times too big), the pipeline (`fetch_data.py` `unit_fix_quarter`) divides that report only if it
can prove the factor for each statement separately: the balance sheet by the report's own previous year-end column against
the 사업보고서, the income statement and the cash-flow statement by the report's own previous-year column against last
year's same-quarter report. Then every statement must agree with a figure the unit cannot touch, including a statement
"proven" at 1 (last year's report can be wrong in the same statement): the income statement through profit ÷ the
report's own basic EPS, the balance sheet through 자본금 ÷ 액면가 (or the income statement's anchor at the same factor),
the cash-flow statement only at the factor of an anchored statement — each within 1/8 to 8 times today's share count. Any
anchor that can be computed and disagrees stops the repair. It never divides when last year's report or the 사업보고서 is
the odd one out, nor statements not in won (no anchor there). Anything it cannot prove is left as filed, and the unit check
(`unit_guard`) blanks the company's numbers as before. In a divided report the hybrid-securities distribution (자본변동표)
cannot be proven, so it is blanked and EPS and BPS use the "hybrid not placed" basis, as for any such company. A divided
company carries corp.json `unitFix` (the report and the factor per statement).

The gate fails a malformed `unitFix` (not a list, factors other than 1,000 or 1,000,000, a bad report name, a report other
than the company's `bq`, or `unitFix` together with
`unitChk`), and warns by name about every company read with a corrected unit, every day, so a person opens that filing on
DART. A company goes on the list `UNIT_FIX_CHECKED` in `validate_data.py` only with Jack's yes (same steps as the low-PBR
list above: Claude checks the filing, asks Jack in one line with the evidence, and on his yes adds the stock code →
`unitFix` (exactly the record in corp.json), `date` and `why` with the filing's `rcept`). An entry stays quiet only while
the record is the same; a new report divided, or a different factor, is named again. The list is empty today.

Known limit: the pipeline only ever divides this year's latest quarterly report. If a company never refiles the faulty
report (for example 진코스텍's 2026 반기보고서), a year later (2027.2Q as the latest quarter) that report becomes "last
year's same quarter", nothing divides it, and the unit check blanks the company again until the next quarter is the latest;
the gate's "공시 단위 확인 회사 바뀜" warning names it when that happens.

## A dated being-fixed line left after the re-read (gate warning "다시 읽은 뒤 '고치는 중' 줄이 남을 국내 회사")

Until the DART re-read, both apps showed "PER과 EPS는 계산 방법을 고치는 중이라 11월 10일에 바뀔 수 있어요." wherever a Korean PER, EPS or
ROE appeared. Since the re-read (corp.json `epsBasis` "owners") the apps drop it for every company whose `epsIn.b` is o, s or t
(`src/repair.js` `epsFixNeeded`), and the old app's 04 card shows it only with an EPS (Jack Q3, 2026-11-14). A company with a PER,
EPS or ROE but no valid `epsIn` (not a foreign issuer, not statements in another currency, not the unit check) would show that
line again with a past date. The gate warns by name (`check_eps_line_left`; 0 on 11-14). An EPS without a receipt already fails
"EPS·BPS 영수증 모양"; this row also names a company with only a ROE. It only warns, because one outdated note should not hold
back a whole publish. What to do: look at that company's `epsIn` in the run log and fix the pipeline's reading of it.

## Korean price series gate rows (국내 시계열 점검)

Each Korean stock's price series comes from Naver (FinanceDataReader), which is an adjusted series: after a split,
consolidation (병합), capital reduction (감자) or bonus/rights issue (권리락), Naver rescales every earlier bar to the new
basis. The pipeline then replaces the last ~19 sessions' bars with that day's official close (listing file 시가총액 ÷
상장주식수), because Naver's bar is the last trade including Nextrade after-hours. Until 2026-11-14 it did so on every
day, also on days before such an event, where the official close is on the old basis: 에쎈테크 and 인지디스플레 (5:1
consolidation) showed a 52-week low of 591 and 726원, STX (capital reduction during a halt, reference price 3,530 →
18,360) 3,530원, and 15 other stocks (CMG제약, 엘앤씨바이오, 코나아이 …) had the same kind of wrong low, high, drawdown,
volatility and beta.

Now (`fetch_data.py` `kr_ref_links` and `pin_why_not`) the pipeline first reads KRX's reference price (기준가) from each
listing file: Close − Changes. On an ordinary day it equals the previous file's official close; on a split, consolidation,
capital reduction, ex-rights day or a re-listing after a halt KRX sets a new one. A day's bar is replaced only when:
- no reference-price change happened between that day and today, and the official close is within 5% of Naver's bar
  (`PIN_PX_TOL`), or within 30% (`PIN_REF_TOL`, a big after-hours day) when the share count is within 2% of today's
  (`PIN_SHR_TOL`); or
- the reference price cannot be checked for that stretch (a row missing where the files around it have one, the Changes
  value missing, or a trading day without a final listing file in between): only when the share count is within 2% of
  today's **and** the close within 5% of Naver's. The share count alone is not enough: with a bonus issue the price
  changes on the ex-date and the new shares list weeks later (코나아이, 11-13).

A stock listed during the 19 sessions has no row in the files before its listing; those links are counted as "new
listing", not "unchecked" (there is no official close to copy before the listing anyway, and the same both-checks rule
applies). Before any of this, each Naver series is cleaned (`naver_clean`): a date that appears twice with different
values is left out (neither value is trusted), a date twice with the same value is kept once, and a zero, negative or
infinite value is left out. The run log says so loudly with the stock, date and values ("!! 네이버 시계열 같은 날짜 두
번"); on 2026-11-13 there were none in 2,474 series.

On 2026-11-13 the reference prices showed 18 stocks with a new basis in the 19 sessions (13 consolidations or capital
reductions, 5 ex-rights days), 14 new listings and none unchecked. The rule kept 165 of 39,778 bars as Naver's, in 23
stocks: 157 bars before a basis change in the 18 stocks, and 8 bars in 5 stocks more than 5% apart on a day the share
count had changed by more than 2%. After the replacement, `pin_audit` re-checks the finished series against Naver's own:
every bar that differs must be that day's official close and allowed by the rule. data.json `krSeries` carries the counts
(`ref.breakStocks`, `ref.unknownStocks`, `ref.newStocks`, `kept`, `bad`) and the moves below. The run log has one line per
step ("네이버 시계열 점검", "KRX 기준가 연결", "고치지 않고 네이버 봉 그대로 둔 봉", "공식 종가 고정 자기 점검", "한국 시계열 하루
±30%"). "KRX 기준가 연결" is loud when more than 100 stocks show a new reference price (the Changes column may have changed
meaning: fewer bars get replaced, none wrongly) or when any stock could not be checked; new listings alone don't make it loud.
Two gate rows read `krSeries`:

- **FAIL "국내 시계열 공식 종가 고정 자기 점검 (krSeries.bad)"**: a bar differs from Naver's series without being an allowed
  replacement, or `krSeries` is malformed, or it is missing while the previous publish had it. It only fires on an error in
  our own code: an outside source problem (Naver, a listing file) only means fewer bars are replaced, and a duplicate or
  broken Naver date is cleaned before the check. But not every error of ours fires it: the check reuses the pipeline's own
  rule and reference-price chain, so it catches a later step that changes bars (for example a new step that writes
  official closes into older days) or a drift between the pinning and the rule, while a bug in the chain itself is guarded
  by the tests (`tests/test_kr_pin_basis.py`, real 11-13 files). The run log's line "!! 공식 종가 고정 자기 점검"
  names the stocks, dates and reasons (`basis` a different basis · `far` too far from Naver's bar · `shr` share count
  unknown · `notOfficial` not that day's official close · `added` · `dropped`). Fix the code (a PR, with tests); never widen
  the 2%, 5% or 30% without Jack (a safety rule). The site keeps yesterday's data until then.
- **WARN "국내 시계열 하루 가격 제한폭 넘는 움직임 (경고만)"**: a stock's series (the three years the numbers use) has a day
  that moves more than the daily limit (±30%; KONEX ±15%), beyond what one Nextrade bar can add (5%: +36.8% / −33.3%).
  Its 52-week range, volatility, beta, drawdown or returns include that move. The row names each stock with the date, the
  move and a cause: `우리 고정이 만든 움직임` (Naver's own series has no such move there, so a replaced bar made it: usually
  an official close next to a big after-hours Naver bar just outside the 19 sessions, which is fine; if the stock is also
  named by the FAIL row, fix the code), `거래정지 뒤 재개` (after 3 or more unchanged bars or a gap: usually a 감자 Naver did not rescale, e.g.
  에이프로젠 +1,446% on 2026-05-08), `하루만 튄 봉` (one bad Naver bar that comes straight back, e.g. 티이엠씨 2023-12-28)
  or `그 밖`. On 2026-11-14 it named 18 stocks, all Naver's own; it is expected to warn every day until those days leave the
  three-year window or Naver corrects them. A newly named stock: compare Naver's chart with the KRX listing (상장주식수,
  기준가 = Close − Changes) for that date. Since 2026-11-14 every named stock's numbers are blanked (next paragraph).
  본시스템즈 (KONEX, 17,500 → 1,176,000원 since its 2025-09 listing, in +15% steps on rare trades) is real and not named.

**Stocks with a broken price history (2026-11-14, Jack: "Q2: (a), this week"; evening: "hide only the numbers whose
calculation window includes the bad day").** Whatever stocks the day's run names in `krSeries.jump` (18 on 2026-11-14:
에이프로젠, BYC우, 아센디오, 폰드그룹 …; the list changes day to day, nothing is hard-coded) are marked by `fetch_data.py`
`mark_px_bad`, right after the series check. For each, it blanks the numbers whose calculation window contains one of its
move dates, reading each window from the calculation itself (`validate_data.PX_BAD_WIN`):
- the whole series (about three years plus 40 days, `YEARS = 3`), always, because the moves are found in that series: 변동성,
  베타 with its 표준오차 and day count, 알파, 3년 수익률, 샤프, 최대 낙폭, 상승 월 비율 and the 저변동 (lz) score;
- the last 252 bars (`px.tail(252)`, `px.iloc[-252]`): 52주 최고 · 최저, 1년 수익률 (mom) and the 추세 (mz) score;
- the last 64 bars: 3개월 수익률 (r3); the last 22 bars: 1개월 수익률 (r1).

The stock carries `pxBad` (the date of its latest such move) and `pxBadF` (the blanked fields), in data.json and corp.json;
`krSeries.hidden` lists the codes. Scores and lists are made without the blanked numbers only: a stock with only old bad days
keeps its 52주 range, short returns and 추세 score (it stays in 홈's 추세 list) but leaves 낮은 변동성, the 2022 estimate and the
yearly swing. On 2026-11-14, 9 of the 18 have their 52주 range blanked (a move in the last 252 bars: 003060, 007460, 007610,
009310, 012170, 210120, 250030, 331660, 472850) and 9 keep it (only older moves: 001465, 012210, 107640, 110790, 121890, 227420,
229500, 311060, 425040). Lines: where the 52주 range is blanked, "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험
숫자는 비워 두었어요." once per screen (2.0 company page header; 예전 뱁새 기업분석, 기업 비교, 종목 고르기); otherwise "과거 주가
기록 일부에 오류가 있어서 이 숫자는 비워 두었어요." in each blanked number's place. The run log says "!! 과거 주가 기록 오류(…)로
숫자를 비운 국내 종목: N (52주까지 a · 52주는 보임 b) — …" with the fields blanked, and "추세(mz) · 저변동(lz) … 필수 종목 …".

How long a mark lasts: while a bad bar is inside the series window (not 252 days). It clears by itself, and the numbers come
back, when Naver fixes the bar or the bar ages out: 110790 크리스에프앤씨 (2023-10-20) around 11-28 and 121890 에스디시스템
(2023-10-23) around 12-01, which takes the count from 18 to 16. A stock moves from "52주까지" to "52주는 보임" by itself about a
year after its last bad day. Repairing the history is a later PR. Gate rows:

- **FAIL "과거 주가 기록 오류 종목의 숫자 비움 (pxBad)"**: a published stock named in `krSeries.jump` still has one of its
  `pxBadF` numbers (data.json or corp.json), or its 52주 range is missing although not in `pxBadF`; or `pxBadF` breaks the window
  rules (the whole-series fields missing, part of a window, a short window without the longer one, or a move within 340 calendar
  days of `pxDate` with the 52주 window not blanked: 252 bars can't be shorter than 351 days; 85 days for 3개월, 28 for 1개월); or
  the lists disagree (`jump` codes, `krSeries.hidden`, the marks), a mark is not the latest move date, or corp.json differs. It
  only fires on an error in our code: fix the code in a PR. A file without `krSeries.hidden` (the format before 2026-11-14) is
  only a warning, unless the previous publish had it or a stock carries a mark. The site keeps yesterday's data until then.
- **FAIL "새로 생긴 과거 주가 기록 오류 종목 수 (10종목 이상이면 실패)"** (`PX_BAD_NEW_FAIL`, Jack 2026-11-14: "block the publish
  … when many stocks newly break in one run"): stocks in today's `krSeries.jump` that were not in the previous publish's. The
  2026-11-14 list's 21 moves fall on 20 dates over three years, at most 2 stocks on one day (2026-05-08, two 에이프로젠 group
  stocks after one 감자), so a daily run names 0–2 new stocks. 10 or more means Naver's adjusted series or our pinning broke
  for many stocks at once (2026-11-13's pinning bug hit 18 at once): read the run log's jump line and the newly named stocks
  in the summary before anything else. Without a previous publish (live checks) it is not compared.
- **The three must-have rows** (005930, 000660, 005380, 015760, 105560, 035420, 012450; Jack 2026-11-14: "warn when one is
  affected; block the publish when two or more must-haves are affected"):
  - "필수 종목 추세 · 저변동 순위 (mz · lz)" (new): a score missing without a correct mark fails, with the reason.
  - "필수 종목 52주 최고·최저 (야후)" and "필수 종목 새 칸" (existing; changed with Jack's yes, 2026-11-14): a 52주 range or beta
    error blanked by a correct mark (in `krSeries.hidden`, consistent per `px_bad_problems`) is passed as a warning naming the
    stock.
  - One correctly marked must-have: each row that has something blanked for it warns (the 52주 row only when its bad day is
    inside the last 252 bars; a must-have with only old bad days keeps its 52주 range, so that row just passes). Two or more:
    every such row fails. So if both must-haves have only old bad days, "52주 (야후)" passes and the mz·lz and 새 칸 rows block
    the publish (저변동 and beta are whole-series numbers, always blanked). A blank without a correct mark fails as before. On 2026-11-14 none of the 296 Korean stocks worth 1조원 or more had an unexplained move (the largest named stock
    was worth 0.39조원). If it happens, look at its Naver chart and the KRX listing for that date first; never loosen a row.

Standing daily warnings until the repair PR: "국내 시계열 하루 가격 제한폭 넘는 움직임 (경고만)" (the 18 names), and "국내
beta 채움" and "국내 vol 채움" at 96.8% (floor 95%, warning under 97%; 2,395 of 2,473: volatility and beta are whole-series,
so every marked stock blanks them). 45 more marked stocks are still a pass; the 46th would fail both rows.

## Korean stocks with no trade or no change today (국내 거래 없는 종목 · 빈 d1)

The KRX listing file has no halt flag. A stock that did not trade on the price date (`pxDate`) has a row with volume 0, open 0
and trading value 0 (11-11 to 11-13: 135 to 141 such rows a day; on the 11-14 publish 66 published stocks, e.g. 금양, STX,
삼부토건, and 6 KONEX names). Until 2026-11-14 their `d1` was 0.00%, as if the price had simply not moved. Now (`fetch_data.py`
`kr_no_trade` · `kr_d1_split`, Jack 2026-11-14 with the design chat's lines of 2026-11-08):
- such a stock gets `noTrade: true`, its `d1` is blank and `d1Why` is `noTrade`; the reference price's change that day (0 for a
  halt; a KONEX price can move without a trade) goes to `ntD1`, which the app uses only for a portfolio's 오늘 amount, so holding
  a halted stock never takes that amount away;
- every other blank Korean `d1` carries its reason in `d1Why`: `range` beyond ±30% (a new listing, a split, a re-listing after a
  halt), `new` (no official close in the previous day's file), `prev` (no usable previous-day file: then every stock, except, since
  #163, the stocks whose KRX base price matches the last publish's close to the won; see "Backup days and the first volunteer-final
  day after them" below);
- data.json `d1Blank` holds the published counts per reason, `seen` (whether no-trade could be told at all) and the source
  oddities: `odd` (volume and open 0 but a trading value that is not 0, or blank: the row contradicts itself, not marked) and
  `must` (a gate must-have stock that looked like no trade: not marked, its `d1` is computed as before, so one bad row cannot
  fail "필수 종목 d1"). Nobody is marked, and every stock shows its `d1` as before (0.00% for the halted ones), when the file
  has no Volume/Open columns (`unseen: cols`), when fewer than 90% of its rows have a number in both (`unseen: blank`: the
  columns changed to blanks; on 11-11 to 11-13 every row had both), or when more than 10% of its rows look like no trade
  (`unseen: many`, a broken file; normal days are 4.7–4.9%). All of this is decided in one pure function,
  `fetch_data.kr_no_trade_plan`.
- Limit-up and limit-down moves (exactly ±30%) keep their `d1`. Before 2026-11-14, 4,030 ÷ 3,100 − 1 came out as
  30.000000000000004%, so the limit-ups of 베셀 and 모아라이프플러스 (11-12) and 디와이에이 (11-13) were blanked. The test now
  allows only that floating-point tail (`D1_LIMIT_EPS`, 1e-9): 30.004% is still blank.

The run log says "· 거래 없는 종목 (기준일 … 거래량 0 · 시가 0 · 거래대금 0): N종목 → d1 빈 칸 · noTrade (…): names" and
"· 국내 d1 빈 칸 이유 (목록 파일): 거래 없음 … · ±30% 밖 … · 직전 거래일 행 없음 … · 직전 거래일 파일을 쓸 수 없음 …", loud ("!!")
for missing columns, a broken file, a must-have that looked like no trade, a contradicting row, or a missing previous-day file.
In the app: "{md} 거래 없음 (거래정지일 수 있어요)" for `noTrade`, "오늘 등락률은 받지 못했어요." for another blank, where the change
would show (company page header, 홈 and 포트폴리오 가진 종목 rows, the 종목 tab's lists). The 종목 순위 rows have no room for those lines:
their change spot says "거래 없음" or "등락률 없음" (Jack, 2026-11-15). Jack also approved "거래정지" for halted stocks, but the KRX listing
file has no halt field (its columns are Code, ISU_CD, Name, Market, Dept, Close, ChangeCode, Changes, ChagesRatio, Open, High, Low,
Volume, Amount, Marcap, Stocks, MarketId, lateInfoMsgCd: ChangeCode is the price direction, Dept the 소속부, lateInfoMsgCd "ME005" on
every row of 11-11 to 11-13), so a halt and a day nobody traded look the same; it stays off (`src/v2/fixnote.jsx` HALT_LABEL, and a
`halt: true` mark no source writes yet) until a halt source is added. Gate rows:

- **FAIL "국내 거래 없는 종목 · 빈 d1 이유 (noTrade · d1Why)"**: only our own values disagree (`validate_data.kr_no_trade_problems`):
  a `noTrade` stock with a `d1` number, a trading value or another `d1Why`; `d1Why` with a `d1` number or an unknown reason; a
  blank `d1` of a listing stock (cls kr, not a fund) without `d1Why`; `ntD1` on a stock that traded, not a number or beyond ±30%;
  a mark on a US stock or a fund; `d1Blank` counts that differ from the stocks, `seen` false with marks, or a stock listed in
  `odd`/`must` that is marked. It never fires on the listing file itself (Jack 2026-11-13: one source glitch must not hold
  everyone's data): fix the code in a PR. A file without `d1Blank` (before 2026-11-14) is only a warning, unless the previous
  publish had it or a stock carries a mark.
- **WARN "국내 거래 없는 종목: 목록 파일의 칸 (경고만)"**: no-trade could not be told today (`unseen`: cols · blank · many), or
  it could but no published stock was marked (normal days have 135–141 such rows: the columns may have changed meaning), or a
  row contradicted itself (`odd`), or a must-have looked like no trade (`must`). The publish goes ahead with those stocks
  unmarked. If it repeats, look at that day's listing file (FinanceData cache) before anything else; the run log has the same
  case as a "!!" line.
## Korean stocks at their last confirmed close (국내 마지막 확인 종가, since #159)

Jack, 2026-11-19: "The 129 unconfirmed stocks: stop showing "이 종목의 데이터를 찾지 못했어요." Show each stock's last confirmed close
with its own date (the existing own-close mechanism), plus "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." It must never sit
under today's date label without that line."

- **When:** only on second-source days (`pxSrc.px` = `daum+yahoo`: the volunteer KRX file was not final, closes came from Daum ×
  Yahoo). A stock in that day's universe that the two sources could not confirm (KONEX: no second source; or Daum and Yahoo
  disagree, or one is missing) is carried at the **previous publish's** price (`fetch_data.py` `kr_own_close_carry`): its `pxd` is
  the previous publish's `pxDate`, or, if it was already carried, the same `pxd` and price (never re-dated). No Daum or Yahoo value
  from today is used. No `d1`. Its market-data numbers (시가총액, 52주, 출렁임, 베타, 수익률, the description's 시가총액) are copied
  from that publish; PER, PBR, 배당수익률 and the scores are made again today from that price. A company whose common stock is
  carried but whose listed 우선주 has today's close gets no EV / P/CF (`corp.json` `evNo: "ownPx"`: the two dates would mix).
- **Not carried (stays out, as before):** not in the previous publish (most KONEX names are below the top-2,500 cut), more than
  `KR_OWN_CLOSE_MAX_DAYS` (5) KRX trading days after its close, the previous publish has the same `pxDate`, or a price-history mark
  without its recorded move. The run log says `!! 국내 종가 미확인 {n}종목 … 마지막 확인 종가로 실음 {k}종목 (pxd …) — names` and
  `!! 마지막 확인 종가로도 싣지 못한 국내 종목 {m} … — names (reason)`.
- **Past the 5-day limit (Jack, 2026-11-20 a):** a stock still unconfirmed whose last confirmed close is more than 5 KRX trading
  days old is left out and recorded in `pxSrc.own.aged` (`[{t, nk, pxd}]`, `fetch_data.kr_own_aged`); the log says `!! 마지막 확인
  종가가 5거래일을 넘어 잠시 뺀 국내 종목 {n} …`. Each later second-source run keeps it there while it stays unconfirmed (from the
  previous publish's record; it is no longer in its stocks), and removes it once it is confirmed again or leaves the listing. A
  normal day writes no record. The apps show "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요." instead of "이 종목의 데이터를
  찾지 못했어요." on its company page (both apps), under its row in the 2.0 portfolios that hold it (built and 가진 종목) and on its
  관심 종목 card. **Known limit:** a carried stock the pipeline drops just before writing (`kr_own_close_final`: a wrong row), and
  every carry on a day the carry step or its check stopped (`own.err`), is not added to `aged`: it shows "이 종목의 데이터를 찾지
  못했어요." until it is confirmed again (no wrong number is shown; the gate warns about those days).
- **KONEX with #158 (Yahoo .KQ × Naver):** a KONEX stock the two sources confirmed is never carried: it is in that day's file
  (`pxSrc.fb.knx.kept`) or, below the usual market-cap cut, simply not published (`capOut`), exactly like a confirmed KOSPI or
  KOSDAQ stock below the cut. Only the KONEX stocks #158 left out (`pxSrc.fb.knx.left`) go to the carry step, with the reason
  `knx` ("야후 .KQ × 네이버로 확인 못 함 (코넥스)"); on a day the KONEX stage did not run or stopped, every KONEX stock goes there with
  the reason `mkt`, as before #158. The log line `· 코넥스 {n}종목 (야후 .KQ × 네이버): 그날 파일 … · 확인됐지만 시가총액 기준 아래라
  싣지 않음 … · 확인 못 함 …` says where each went (`!!` when the counts differ from #158's record or `left` cannot be read; then every
  KONEX stock outside the file counts as unconfirmed). A carried KONEX stock is not in `pxSrc.knx.t`, and #158's `코넥스 종가 두 출처`
  row leaves clean carries out of its comparison; the carry row warns if `pxSrc.own.unconfWhy.knx` differs from `len(left)`.
- **Normal days:** nothing changes. No Korean stock gets `pxd`.
- **data.json:** `pxSrc.own` = `{v, max, n, codes, unconf, unconfWhy, drop, dropEx, bad, aged, ind?, err?}`; `pxSrc.n` counts only stocks at
  `pxDate`. The rows the final check drops are also in `ownDrop.krOwn` (`{n, rows}`, beside the other own-processing checks; the
  carry row warns if its `n` differs from `pxSrc.own.bad.n`).
- **Gate:** `국내 자기 가격 날짜 (pxd)` fails exactly what the US `pxd` row fails (a `pxd` that is not a date before `pxDate`, or a
  `d1` beside it, still in the file). Since 2026-11-20 (Jack d: "drop a carry with a broken date and warn; block only above 5.") it
  also counts the rows the pipeline dropped in the run, per reason (`pxSrc.own.bad.why`; Jack's standing rule: more than 5 rows fail
  one check in one run): any drop warns; more than `KR_OWN_DROP_MAX` (5) for one reason fails, so nothing publishes (that check is
  broken, not one stock). Reasons are not added up (a broken date also counts as "not the previous publish's date"). A run whose
  check itself stopped (`own.err`) only warns. `국내 마지막 확인 종가 (pxSrc.own · 경고만)` only warns: a carried stock not in `pxSrc.own.codes`, on a normal day,
  older than the limit, or not the previous publish's price and date, or rows the pipeline itself dropped just before writing
  (`pxSrc.own.bad`, same function `validate_data.kr_own_close_bad`). Only clean carries (recorded, before `pxDate`, no daily change,
  within the limit, and the previous publish's price and date) are left out of the `pxDate` price checks (`한국 가격 = 공식 종가`,
  the gate's Daum × Yahoo sample and its confirmed count: `kr_own_codes`); anything else with a `pxd` is still checked as a
  `pxDate` price, and "국내 거래 없는 종목 · 빈 d1 이유" accepts a blank `d1` only for a clean carry (any other Korean `pxd` fails it, as
  before). The pipeline runs the same check right after the Korean price stage, so a dropped carry never reaches the dividend,
  income or score steps. On such a day the 국내 beta · vol 채움 rows can warn (small KONEX names often have no beta).
- **Never stops the run:** any error in the carry step (`fetch_data.kr_own_close_step`) or in the check after it is logged as
  `!! 마지막 확인 종가 단계가 오류로 멈췄어요 (…)` / `!! 마지막 확인 종가 점검이 오류로 멈췄어요 (…)`; nothing is carried (unconfirmed
  stocks are left out, as before #159), `pxSrc.own.err` holds the reason and the gate's carry row warns. Fix forward; the publish goes on.
- **Pre-publish screen check (`tests/smoke_app.py --data .`):** the scenes that compare the own-close text exactly (미국날짜,
  확인종가) first remove every real Korean `pxd` from their copy of the data (`strip_kr_carries`) and test only the ones they plant,
  so a real carry on a second-source day never fails the screen check; extra scenes run them on a copy with planted carries to
  prove it: the three stocks the 11-20 dry run really carried (`tests/fixtures/kr_own_close_real_1120.json`, rows exactly as the
  pipeline wrote them) plus 삼성전자우 and 삼성전기.
- **The 11-20 dry run (44627568844) failed this check** (smoke_app 156 / 160: 확인종가 banner and cards, both runs), so a real
  publish would have been blocked. Cause: a test bug, not the data. The old app's portfolio screen switches its own language one
  React task after the header's EN button; the scene read the banner right after the click, and on GitHub's machine that read
  came before the switch. The second check then failed because the screen was left in English. Users saw nothing wrong. Fixed
  (2026-11-20): the scene waits until the text is exactly the expected one and checks it again 0.3 s later, and the second check
  and every later check starts on the Korean screen. A third run uses a **slow screen** (`slow_screen`: React's scheduled work
  delayed 0.3 s), which opens that gap on every machine: with the old scene the same four checks fail there (the banner detail
  differs: the slow screen keeps the Korean line longer), the fixed one passes. That run tests the scene, not the app, so it runs
  only in CI and local runs on the fixture, never in this daily check (`--data`). If this check fails only on GitHub, look for a
  read right after a click that does not wait for the new text.
- **Industry words of a carried stock (review S1, 2026-11-20):** a carried row copies the previous publish's description. If that
  publish had filled the stock's industry from DART (`indSrc.dartT`) or from its common stock (`indSrc.prefT`, #146), those words
  are not copied as they are (`kr_own_ind_reset`, same rule as #146's `kr_prev_desc`): today's KRX-DESC words if it has them,
  otherwise the words are taken off and the stock is filled again today, so it is in today's `dartT`/`prefT` and the gate checks
  it. The log says "· 마지막 확인 종가 종목의 업종 글자: … 오늘 다시 채움 n · 오늘 KRX 글자로 m"; `pxSrc.own.ind` has the counts.
- **Daily lists:** a carried stock's trading value is its old day's, so it is left out of today's 거래대금 and 거래 급증 lists
  (2.0) and of `data.json` `popular`, like 큰 움직임. It stays in 시가총액 and the 기준 lists, named under the list.
- **On a warning:** read the named rows in the run summary. A carried stock with a different price or date than the previous
  publish means our carry step broke: say so to Jack; the stock itself is still labelled with its own date and line.
- **Check on the site:** search a carried stock (the log names them): its company page shows "{date} 종가" and Jack's line under the
  price; lists and portfolio totals with it say "{name}: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." (one line per date, since
  2026-11-20); the old app's 기업분석 header and the first screen's card show Jack's line under the price (English card: "We couldn't
  confirm today's close, so this shows the {date} close."). A stock in `pxSrc.own.aged`: its company page says "며칠째 종가를 확인하지
  못해서 이 종목은 잠시 빼 두었어요.".
- **Late data (#144) with a carried stock (Jack, 2026-11-20 f; 2026-11-21 answer 4: "Not all-or-nothing. Leave that one stock out
  with the approved line … and check the rest."):** on late data (the closes at most 5 trading days behind) a Korean stock priced
  at its last confirmed close whose own close is more than 5 KRX trading days before today in total, or is not a readable date,
  is left out of that day's check (`src/v2/rules.js` `lateLeftOut` / `todayCtx`; console "[v2] late data: left out of the check,
  shown with the aged line: …"). The check reads it as not in today's data (its row stays and shows "며칠째 종가를 확인하지
  못해서 이 종목은 잠시 빼 두었어요."; totals and weights leave it out; a sold-out holding is not read; a portfolio holding only that
  stock shows that row and no totals). Every other stock and portfolio is checked as usual and the screens keep "{date} 종가로
  점검했어요". The stale state ("데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요") comes only when the data itself is more than
  5 trading days late, as on main. A US stock carried at its last confirmed close (`pxc`, since #165) is left out the same way, counted
  in NYSE trading days; a US stock at Yahoo's own older bar (halted) is not touched. 내 수익 reads the same day's context: with that
  stock left out it shows no amounts on late data (its existing rule for a stock missing from the data). The old app has no
  late-data check.

## US stocks at their last confirmed close (미국 마지막 확인 종가, since #165)

Jack, 2026-11-20 (verbatim): "Also: US stocks carry like Korean ones. A US stock with no close from Yahoo carries its last confirmed
close with its own date and the same line. Block only if many are missing (set the number from history), so a Yahoo gap never stops
the Korean data again."

Why: on 11-20 Yahoo's newest US daily bars came back blank for hours (01:11 UTC: 799 of 800 tickers; 03:59 and 04:19 UTC: 200), while
the S&P 500 index bar was there. The gate row `미국 d1 채움` (≥ 98%) failed every trial run in that window, and with it the whole
publish, Korean data included.

- **What counts as "no close":** the stock's bar for `usPxDate` (the S&P 500's last finished bar) is missing, blank, infinite, 0 or
  negative (trailing bars like that are dropped first: `fetch_data.us_px_tail_clean`, so a 0 close never becomes a row priced 0), or Yahoo
  sent no usable price at all or the download for it failed (only for tickers the previous publish had, or had left out as aged).
- **Carried (`fetch_data.us_own_close_carry`, step `us_own_close_step`, inside `fetch_us` before the stock details are attached):** if the
  previous publish (`data.json` the run starts from) had the stock at its `usPxDate` close, it is published at **that price**, `pxd` = that
  publish's `usPxDate`, `pxc: true`, no `d1`. If it was already carried (`pxc`), the same price and `pxd` (never re-dated). Market numbers
  made from the price series (출렁임, 베타, 52주, 샤프, 최대낙폭, 상승 월, 모멘텀: `US_OWN_KEYS`) are copied from that publish; name, industry,
  PER, PBR, 시가총액 and 배당수익률 are attached today from that price as for any stock (won amounts use today's rate, as for any US
  price at an earlier close).
- **A newer Yahoo bar wins (review, 2026-11-20):** if today's download has the stock's own bar dated after the carried close, before
  `usPxDate` and on an NYSE day (a day with an S&P 500 bar; a stray bar on a holiday is ignored) (e.g. last publish's US date 11-18, today's 11-20, Yahoo has 11-19 but not 11-20), that bar is used instead: Yahoo's price
  and date, the series numbers up to it, `pxc: true`, no `d1` (the existing own-date row, marked). Recorded in `usSrc.own.newer`
  (`[{t, pxd, px}]`). An aged stock with such a bar comes back on the same terms (its age counts from the new date).
- **A split after the carried close (review, 2026-11-20):** if the stock has a split dated after its carried `pxd` (today's download, the
  previous publish's `splits` or the fixed table), it is not carried: that price is pre-split while the app (`held.js splitFactor`) would
  multiply the shares. It gets exactly what it got before this change: Yahoo's own-date row (Yahoo's split-adjusted series, the halted
  wording, no `pxc`), or left out when Yahoo has nothing (no aged entry, so the app says "이 종목의 데이터를 찾지 못했어요." as before).
  Recorded in `usSrc.own.split` (log `!! 마지막 확인 종가 뒤에 주식 분할이 있어 싣지 않은 미국 종목 …`). After `splits_fields` the published
  list is checked again (`us_own_split_late`: a split found only through the seed or the history backfill): a stock that had its own
  Yahoo row today gets that pre-change row back (its split row stays); one Yahoo had nothing for is removed with its new split rows
  (`split` entry with `late: true`). If the split column cannot be read even per stock, the stock is not carried either (pre-change
  path, `unread`). Every removal (final check, drop-all, late split) cleans its `umeta` records as #139 does and writes an EXTRA_US
  reason (`us_own_drop_rows`). A must-have in these states behaves as before (no exemption).
- **Details of a carried stock (review, 2026-11-20):** Yahoo's PER, PBR, 시가총액 and 배당수익률 follow Yahoo's current quote, so for a
  carried row the info cache records Yahoo's quote price (`currentPrice` / `regularMarketPrice`) as its reference and the numbers are
  rescaled to the carried close. Without a quote price, or with one more than 50% away from the carried close, a cached copy under 14 days old is kept as it was; otherwise those four numbers
  are left blank for that row (`pxBad` on the cache entry; log `마지막 확인 종가 종목 …의 상세 정보: …`).
- **Same US date again (`usSrc.own.same`):** if the previous publish already has the same `usPxDate` (a second publish the same day, which is
  what 11-20's trial runs were), the stock keeps that publish's close **and its `d1`** for that day: it is that day's confirmed close, so no
  `pxd`, no `pxc` and no line.
- **Not carried, as before (`drop`):** `none` not in the previous publish, `halted` the previous publish had it with its own Yahoo date (`pxd`
  without `pxc`: a halted stock), `bad` unreadable price or date. These keep the existing path: Yahoo's own last bar with its `pxd` (the
  existing "{티커} 가격은 {md} 종가예요." / "미국 {md} 종가"), or left out when Yahoo has nothing. Since #169 (below) a new ticker that
  waits never reaches this step, so `none` is left only for new tickers that don't wait: a ticker the previous publish left out on
  purpose (`usLeftOut`), a run whose previous `data.json` is missing, unreadable or has no US rows, and a run where the wait step
  itself stopped on an error.
- **New tickers wait for a confirmed close (since #169, Jack 2026-11-22, verbatim):** "2. No relaxation. Instead, a stock newly added to
  the S&P (or NASDAQ) list joins our list only once it has a confirmed close; until then it isn't added. Nobody can hold it in the app
  before it joins, so nothing is lost, and the check stays as it is." Why: a ticker the previous publish did not have has no last
  confirmed close to carry, so it used to go out at Yahoo's older bar with its own date, and every such stock counts as missing in
  `미국 d1 채움` (fails above 5). In trial run 44849045557 (11-21, Yahoo's 10:00–10:40 KST gap) 796 stocks were carried and 4 were
  missing: LGND, MKTX, SNDK, VRNS, none of them in that run's previous file. On a full Yahoo blank on a day the S&P list adds 6 or more
  tickers, that one row would have stopped the whole publish, Korean data included.
  **"Nobody can hold it" is not always true (review, 2026-11-22):** a ticker can drop out of one publish and come back. LGND and SNDK
  were in every `main` publish from 11-06 to 11-18, missing on 11-19 (Yahoo sent SNDK only 2–3 days of history: `spGone` "가격 이력
  3일") and back on 11-20. Safety still holds: a waiting ticker was also missing from the previous publish, so anyone holding it from
  an earlier day: the previous publish already showed it missing, and it shows the same line again ("이 종목의 데이터를 찾지 못했어요.") and no number. It can't
  be added while it waits.
  - **Rule (`fetch_data.us_new_wait`, step `us_new_wait_step` in `fetch_us`, right before the carry step):** a ticker on today's US list
    (S&P 500, NASDAQ top 400 and `EXTRA_US`, its ETFs included) that is in neither the previous publish's US stock rows (`cls` us, not a
    fund) nor its `usSrc.own.aged`, and has no close for `usPxDate` (Yahoo has its history but the day's bar is missing, blank, 0,
    negative or infinite), is **not added today**: its row is removed before the carry step, the split read, the stock details and the
    split list, so it reaches no part of the file. It joins, like any other stock, on the first run where Yahoo has its close for the US
    date. Recorded in `data.json` `usSrc.newWait` (sorted tickers; the key is there only when something waits, so a normal day's `usSrc` and US
    rows are unchanged; `units.usSrc` describes it), and its reason `새로 들어온 종목 · 확인된 종가를 기다려요 (…)` goes into `usExtraMissing` (a hand-added stock: the gate's
    EXTRA_US row warns, not fails), `usListSym.missing` (BF-B: warns) and `usListSym.spGone` (an S&P 500 ticker: named only).
  - **Tickers the previous publish left out on purpose don't wait (review, 2026-11-22):** a ticker in the previous publish's
    `usLeftOut.preferred` or `usLeftOut.krListing` (the lists `clean_us_list` removes every day; e.g. SKHY, GOOGM, GOOGN, STRC) takes its old path: the later
    steps leave it out again and record it in that day's `usLeftOut` as before (if it waited, that day's `usLeftOut` would come out empty
    and the next day would log it as joining). Log: `· 지난 발행본이 일부러 뺀 티커(usLeftOut) 중 미국 기준일 {date} 종가가 야후에 없는
    {n}: names — 기다리지 않고 예전 길 그대로 …`. Only these two lists: a ticker the previous publish left out as `badBar` (or in any
    list added later) was not in that publish, so it waits like any new ticker (verification review, 2026-11-22).
  - **Known effect:** "new" means "not in the previous publish's US rows, aged list or `usLeftOut.preferred` / `krListing`". A ticker that was missing from the
    previous publish for any one-day reason is new by this rule, and waits if Yahoo has no close for it today, where `main` would have
    published Yahoo's older bar with its own date: under 60 days of history that day (SNDK on 11-19), dropped by the carry check
    (`us_own_close_final`, `us_own_close_drop_all`) or the late split check (`us_own_split_late`), or Yahoo sending nothing for a ticker
    that had nothing to carry. It joins on the next run with a confirmed close, like any new ticker.
  - **Unchanged:** a ticker the previous publish had, or had left out as aged, keeps the carry path above; a new ticker Yahoo sends no
    price for at all (`empty`, `err`) or with under 60 days of history is left out as before, with its old reason (`usListSym.noPx`
    still picks those up); KR-listed funds, bond ETFs and gold are fixed lists outside `fetch_us` and are not touched.
  - **No previous publish** (first run, or `data.json` unreadable or with no US rows): we can't tell what is new, so today's behaviour
    stays (Yahoo's older bar with its own date) and the log says so: `!! 지난 발행본이 없거나 읽지 못했어요 (첫 실행?) — 새로 들어온 미국
    종목을 가릴 수 없어 예전 그대로예요 …` (or `!! 지난 발행본에 미국 종목 행이 없어요 — …`). An error in the step itself is logged (`!! 새로
    들어온 미국 종목을 가리다 오류로 멈췄어요 …`), every change the step made is undone, and the run goes on with today's behaviour; it
    never stops the run.
  - **Run log:** `!! 새로 들어온 미국 종목 {n} (지난 발행본에 없고 미국 기준일 {date} 종가가 야후에 없음): names — 오늘은 넣지 않아요 · 미국
    기준일 종가가 확인되면 넣어요 (usSrc.newWait …)`, then `· 새로 들어온 미국 종목 중 미국 기준일 {date} 종가가 있어 오늘 들어감 {k}: names`.
    Normal day: `· 새로 들어온 미국 종목 (지난 발행본에 없던 티커): 미국 기준일 {date} 종가가 있어 오늘 들어감 {k} · 종가를 기다림 0` (tickers the
    previous publish recorded in `usLeftOut`, such as preferred shares, are not listed as joining).
  - **Gate:** no existing row changed. `미국 d1 채움 (미국 기준일 봉)` still fails above `US_NO_CLOSE_MAX` (5) stocks with no `d1` that are
    not a clean carry; a waiting ticker is simply not in the file. New row **`미국 새 종목 확인 종가 기다림 (usSrc.newWait · 경고만)`**
    (`validate_data.check_us_new_wait`), **warning only, it never fails** (publish, deploy and watchdog alike; a warning never changes
    the gate's exit code): PASS when `usSrc.newWait` is absent or empty; WARN naming the waiting tickers, and separately those the
    previous publish's `newWait` already had ("지난 발행본부터 이어서 기다림 n: …", publish runs only: the site checks have no previous
    publish); WARN when the record is malformed (not a list of non-empty strings) or names a ticker that is in the file anyway. Before
    this change the `미국 d1 채움` row named such tickers; this row keeps a waiting ticker from going unnoticed by the morning check.
  - **On a warning:** read the named tickers. One waiting a day is Yahoo missing its close: nothing to fix, it joins with the next
    confirmed close. One "이어서 기다림" (two publishes or more) means Yahoo still has no close for it (a renamed, delisted or
    not-yet-trading ticker in the source list): check the source list (FinanceDataReader's S&P 500, Nasdaq's first 400, `EXTRA_US`);
    nothing on our side shows a wrong number while it waits.
- **Age limit:** `US_OWN_CLOSE_MAX_DAYS` = 5 NYSE trading days after the close, counted on S&P 500 daily bars up to `usPxDate` (holidays such
  as Thanksgiving have no bar, so they don't count). Past it the stock is left out and recorded in `usSrc.own.aged` (`[{t, nk, pxd}]`,
  `us_own_aged`), kept there on later runs while Yahoo still has no close, removed once it does or the ticker leaves the list. An entry
  more than 20 NYSE trading days old gets a `!! 잠시 뺀 지 20거래일이 넘은 미국 종목 …` line (a delisted or renamed ticker may still be in
  the source list: check it).
- **Never stops the run:** any error in the step is logged (`!! 마지막 확인 종가 단계(미국)가 오류로 멈췄어요 …`), the rows go back to the
  existing path, `usSrc.own.err` holds the reason, and the gate warns. Right after the US list is final, `us_own_close_final` runs the
  gate's own function (`validate_data.us_own_close_bad`) and drops a wrong row (`usSrc.own.bad`, per reason); if that check itself errors,
  every carried row is dropped (`us_own_close_drop_all`).
- **Run log:** `!! 미국 종가 미확인 {n}종목 (기준일 … · 까닭별 수): 마지막 확인 종가로 실음 {k}종목 (pxd …) — names · 지난 발행본이 같은 기준일이라
  그날 종가 · d1 을 그대로 {m}종목 — names`, `!! 마지막 확인 종가로 싣지 않은 미국 종목 …`, `!! 마지막 확인 종가가 5거래일을 넘어 잠시 뺀 미국 종목 …`,
  `· 마지막 확인 종가 점검 (미국 · 관문과 같은 함수): {n}종목 빼고 발행`. Normal day: `· 미국 종가 미확인 0종목`.
- **data.json:** `usSrc` = `{v: 1, own: {v, max, n, codes, same, newer, split, unconf, why {bar · empty · err}, drop, dropEx, bad {n, rows, why}, aged, err?}, newWait?}`;
  the stock row has `pxc: true`. `newWait` (since #169) lists the new tickers left out today while they wait for a confirmed close (above);
  `unconf` and `why` count only the stocks that went to the carry step, so waiting tickers are not in them.
- **Gate:**
  - `미국 d1 채움 (미국 기준일 봉)`: a clean carry (`validate_data.us_own_codes`: `pxc`, `pxd` before `usPxDate`, no `d1`, a price, listed in
    `usSrc.own.codes`, within 5 NYSE days, and in a publish run exactly the previous publish's price and date) is **not counted as missing**,
    however many there are (warning, named). The row **fails only when more than `US_NO_CLOSE_MAX` (5) US stocks have no `d1` and are not a
    clean carry** (Yahoo's own older bar, a wrong carry). N = max(5, 3 × the most seen): the 27 publishes on the `data` branch from 11-05 to
    11-20 had 0 such stocks each (table in the PR). A file without `usSrc` (published before this) keeps the old rule (≥ 98%).
  - `미국 필수 종목 d1` (AAPL · MSFT · NVDA): a clean carry warns (named with its date) instead of failing; no `d1` without a clean carry still fails.
  - `미국 종목 수` and `미국 종목 수 변화` (thresholds unchanged) count what main would publish for the same input (`us_px_count`):
    every row without `pxc`, plus carried and same-day rows where Yahoo had the stock's history but no bar for the US date
    (`usSrc.own.from` = `bar`: main would have published Yahoo's own-date row). Rows where Yahoo sent nothing (`empty`, `err`: main
    would have dropped them) are not counted, on both sides of the change row. So a Yahoo gap (history present, the day's bar
    missing) carries and never stops the publish, while Yahoo returning nothing for most stocks (a broken source) still fails these
    rows as before. A carried row without a recorded source fails the carry row.
  - `미국 가격이 바뀌었는지`: clean carries are left out (their price is the previous publish's by design); with nothing left to compare, it warns.
  - New `미국 마지막 확인 종가 (usSrc.own · pxc)`: **fails** on a carried row still in the file with a broken date, a `d1` beside it, a
    `pxc` mark without `pxd` (as the Korean `pxd` row), a split in `data.json splits` dated after its `pxd`, or a same-day row (`same`)
    that is not exactly the previous publish's close and `d1`, and when the pipeline dropped more than `US_OWN_DROP_MAX` (5) rows for one reason in the
    run (Jack's standing rule). A `newer` row must match its record (date and price), be an NYSE day on the S&P 500 bars and come after
    the previous publish's close date for that stock (its `pxd` if carried, else that publish's `usPxDate`, or its aged entry's date);
    otherwise it is treated as today's price (warning). It warns on carries, same-day closes, aged stocks, dropped rows and records that disagree (those rows are then
    treated as today's prices by the rows above). A run whose check itself stopped only warns.
  - `미국 자기 가격 날짜 (pxd)` is unchanged (every US `pxd` before `usPxDate`, no `d1` beside it).
- **App (both):** a carried US stock (`pxc`) reads like a Korean carry: on its own screen "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
  under its "미국 {md} 종가"; in lists and totals one line per date "{티커}: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." (in the same
  line as Korean stocks of the same date); the old app's English lists "{티커}: we couldn't confirm today's close, so this shows the {date}
  close." (one stock; two or more: "…, so these show the {date} close."; 종목 고르기 cuts to five names "… and {n} more: …" and,
  above the US cap, "US stocks: we couldn't confirm today's close, so these show the {date} close.", since 2026-11-22); a stock in `usSrc.own.aged`: "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요." on its company page and under its row in
  portfolios. A US `pxd` without `pxc` keeps "{티커} 가격은 {md} 종가예요." and "미국 {md} 종가". On late data the check leaves out a
  carried US stock whose close is more than 5 NYSE trading days old in total (`rules.lateLeftOut`, like a Korean carry: its row shows
  the aged line, the rest is checked).
- **Halted stocks:** the existing wording ("{티커} 가격은 {md} 종가예요." / "미국 {md} 종가") now remains only for stocks already halted
  before this change (and, on a run without a readable previous publish, for new tickers); a stock that stops trading after it becomes a
  carry with Jack's line and is left out after 5 NYSE trading days. Since #169 a new ticker without a close waits instead (above).
- **A long full outage:** every US stock is carried for 5 NYSE trading days (warnings); on day 6 they age out and the US count and
  must-have rows stop the publish.
- **App late cap:** counts NYSE days up to the KST date (one day stricter than the pipeline's count, the safe side).
- **Popular list:** keeps US carries (`val` is from average volume, not one day's).
- **Long lists (Jack, 2026-11-21, answers 8 and 6; market-wide lists only, the coordinator's decision the same day):** on a market-wide
  list (2.0 종목 순위, 종목 찾기 results, 내 기준으로 찾기, 후보 고르기, the 포트폴리오 만들기 preview; old app 종목 고르기 and the 기업분석
  lists; `ownCloseGroups(…, { compact: true })`) a line names at most 5 carried stocks, then "외 {n}종목" (Korean screens, US and Korean
  carries). When more than half of the US stocks in the file are carried (`data.js` `US_CARRY_WIDE`; history: partial Yahoo gaps ~200 of
  800, full blanks 799–800), the US side of those lists is one line, "미국 종목은 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
  (console: "[v2] … US stocks at their last confirmed close (more than half)"). Lists of the user's own stocks (portfolio cards, 오늘
  확인할 일, 내 수익, records, 매수 계획, 관심 종목; old app banner, memo, CSV) always name every carried stock in the existing line. Company
  pages keep the per-stock line. English screens (old app, Jack 2026-11-22): the same rules in English, "{codes} and {n} more: we couldn't confirm today's close, so these show the {date} close." and "US stocks: we couldn't confirm today's close, so these show the {date} close."; every English list line naming two or more stocks says "these show", one stock "this shows".
- **Known limit:** US carries never make a later run re-run. Since #161, later scheduled runs keep going only while a backup-day
  publish has open **Korean** closes (`already_published.open_closes` counts Korean closes only; its US count is always 0, decided in
  the #161 second review). Such a run fetches US prices again: if it publishes (more Korean stocks at that date's close, nothing lost),
  US closes Yahoo has filled since come with it; a US improvement alone never publishes on the same US date. Otherwise the carried
  closes stay until the next day's publish (a newer US date), as with Korean carries. A manual run refreshes them on a KRX-final day
  (same-date runs there publish as before); on a backup day it follows the same same-day rule as the scheduled runs.
- **On a warning:** read the named rows. Many carries on one day means Yahoo was blank for them: nothing to fix on our side; the next
  publish takes Yahoo's closes again. A wrong carry (not the previous publish's price or date) means the carry step broke: tell Jack.
- **On a failure:** "마지막 확인 종가로 싣지 못한 종목 > 5" means many US stocks had no Yahoo close **and** no previous close to carry (a
  first run without a previous publish, halted stocks, splits after the carried close, tickers the previous publish left out on purpose
  (`usLeftOut.preferred` / `krListing`), or a broken carry step; since #169 other new tickers wait instead of counting here). The previous publish stays live. Never raise N to get a publish out; a different N needs Jack's yes with
  new evidence.
- **Check on the site:** search a carried ticker (the log names them): its company page shows its date and Jack's line; a portfolio holding it
  shows "{티커}: 오늘 종가를 …". 005930 and 현대차 unchanged.

## Backup days and the first volunteer-final day after them (직전 거래일 최종본 없는 날의 d1, since #163)

A backup day is a finished trading day the volunteer KRX list has no final file for: the run builds it from Daum × Yahoo (the
two-source rule, #137; time limits in the next section) and publishes with `pxSrc.px` = `daum+yahoo`. When the volunteer list comes
back, it often posts only the newest day's final file; its files for the backup days stay the intraday copies it committed during
those days. Example (dry run 44783218618, 11-21 02:33 KST): backup days 11-17/18/19 (published 11-20 06:40, pxDate 11-19), then a
final 11-20 file (23:23 KST commit, 2,878 stocks), while the 11-17/18/19 files were last committed at 15:29, 14:52 and 14:52 KST,
before each day's close (11-19 was the CSAT day, close 16:30). That run is a normal volunteer-file day for 11-20 (pxDate 11-20,
`pxSrc.px` = `listing`, the Yahoo spot check of must-haves + sample and the KONEX Naver check as usual), except that the previous
trading day has no final file:

- **`d1`** (before #163: blank for every stock, so "필수 종목 d1" failed and nothing published). Now (`fetch_data.kr_d1_base_day`): a
  stock gets `d1` = today's official close ÷ the last publish's close − 1 only when KRX's own base price in today's final file
  (Close − Changes, the relation the "KRX 기준가 연결" check uses) equals, to the won, the close in the last publish (the data.json
  the run starts from, the same file the gate reads with `git show HEAD:data.json`). Two independent sources: KRX's base price and
  a close we already confirmed from two sources. The last publish counts only when its pxDate is the previous KOSPI trading day and
  its price source is the volunteer list or Daum × Yahoo; a row counts only when it is a confirmed close of that day (a row with its
  own price date `pxd`, a carried close, or a no-trade row does not). The ±30% and no-trade rules are unchanged. Every other stock
  keeps a blank `d1` with `d1Why` `prev`; nothing is guessed.
- The log says it in one loud line: "!! d1: 직전 거래일 최종본이 없어 KRX 기준가 × 지난 발행본 종가로 확인 n / m · 다름 k · 지난 발행본에
  없음 j · 그날 확인된 종가가 아님 c · 기준가 없음 b (…) — 다름: names with both values — …". When the last publish cannot be used:
  "!! d1: 직전 거래일 … 최종본이 없고 지난 발행본의 가격 날짜가 직전 거래일이 아니에요 … d1 을 비워요 n종목".
- data.json `d1Base` (only on such a day): `{v, day, pub, why, n, ok, diff, noPub, notConf, noBase, ex}` (`day` the previous trading
  day, `pub` the last publish's pxDate, `why` none · day · src when the last publish could not be used, counts over the processed
  stocks, up to 12 examples per reason). The gate does not read it; its rows stay as they were: "필수 종목 d1" fails if a must-have
  is still blank, "국내 d1 채움" warns below 95%.
- On the real 11-20 files: 2,371 of 2,500 confirmed, 0 differ, 88 not in the last publish (stocks the 11-19 backup did not
  confirm, such as 바이오비쥬 489460, or new to the top 2,500), 41 no-trade rows on 11-19 (all without a trade on 11-20 too). `d1`
  filled 2,370 of 2,500 (94.8%, so expect the WARN "국내 d1 채움"), every confirmed value equal to KRX's own change ratio, all 7
  must-haves present (삼성전자 −7.01%).
- **Other things that use the previous days' files** behave as on any day with a non-final file, and say so loudly ("!! … 파일의
  마지막 커밋이 … — … 그날 값은 가격 고정·거래대금에 쓰지 않아요"): `val20` averages the 20 newest final files (today and the 19 final
  days before the gap), so on 11-20 its window reaches three trading days further back; the backup days' Naver bars are not pinned
  to official closes (their only official closes were the backup files, which this run does not rebuild), so volatility, beta, 52-week
  and the price-history checks read those three bars as Naver gives them, like any unpinned day ("최근 19거래일 중 고치지 않고 네이버 봉 그대로
  둔 봉"); "KRX 기준가 연결" reads "확인 못 함" for every stock across the gap. "pxDate 뒤 끝난 거래일 없음" passes (pxDate is the
  newest day).
- **When it still stops:** if the last publish is older than the previous trading day (the backup also failed that day), every
  `d1` stays blank and "필수 종목 d1" fails: nothing publishes, the site keeps its dated data, and the next trading day publishes
  normally (today's final file is then the previous-day file). The same if a must-have's base differs (a corporate action on a
  must-have that day). Do not loosen the gate row; check the "d1:" log line and tell Jack in plain words.

## Korean second-source time limit (2차 출처 시간 한도, since #151)

When the volunteer KRX list has no final file for a finished trading day, the run builds that day from Daum's daily prices and
keeps only the stocks whose Yahoo `.KS`/`.KQ` close agrees to the won (#137, Jack's two-source rule). It asks stock by stock in
three phases: Daum daily prices (4 at a time), Yahoo daily closes (one chart per stock, 6 at a time; before this change a
yfinance batch download, 200 stocks per batch), and, for the newest day only, a Yahoo chart re-read of the stocks whose daily
close Yahoo still leaves blank (6 at a time). After the Korean day ends Yahoo leaves the newest daily close blank for hours (seen
blank at 01:40 and 02:15 KST, filled by 06:40), so runs in that window re-read about 2,770 charts.

Until 2026-11-20 each request had a limit (20 s, three tries) but no phase did, and the phases' notes were printed only at the
end. Two branch dry runs on 11-19/20 (23:19 and 00:34 KST starts) sat silent after "· 종목 목록: 2026-11-16 최종본 …" for 74 and
61 minutes and were cancelled; the same inputs had finished this stage in 3m40s twenty minutes earlier. A slow or throttling source
could hold a run for hours (Daum timing out on every try: 2,772 ÷ 4 × 66 s ≈ 12.7 hours), and one yfinance batch could wait with no
limit at all (it loops until every ticker answers, and an abandoned batch would keep the process from ending).

Now (`fetch_data.KR_FB_PHASE_BUDGET_S` = 600 s per phase; normal phase times on four runs, 11-18 03:19 · 06:40 and 11-19 22:59
KST: Daum 108–144 s, Yahoo batch 111–178 s, chart re-read 0–41 s, 41 s even for 2,764 stocks; on the first dry run with this
change, 44578437586 on the night of 11-20: Daum 133 s, Yahoo one chart per stock 31 s for 2,766 of 2,772, re-read 30 s for 2,765):
- each phase logs a line when it starts ("· 2차 출처: 다음 일별 시세 묻는 중 — …"), so a stuck run shows which source it is waiting on;
- the order is: must-have stocks, then every other stock by the market cap in the volunteer list's last **final** file, largest
  first (the day's own cache file can be the pre-market version with blank caps, so it is never used to rank), then stocks with no
  cap there by code. The log says it: "· 2차 출처 묻는 순서: 필수 종목 7 → 1차 출처 최종본 시가총액 큰 순 … → 시가총액 모름 … (코드 순)";
- when a phase runs out of time it stops asking; requests already in flight finish under their own limits (one stock: 3 tries ×
  (20 s to connect + 20 s between bytes) + at most 10 s of pauses ≈ 130 s; a DNS lookup and a server that sends a byte every few
  seconds are outside those limits, never seen). So a phase ends within about 12 minutes and the three phases within about 37
  minutes, however slow the sources are;
- between tries a stock waits 1 s, then 2 s; after a 429 ("too many requests") it waits what the server's Retry-After asks, at
  most 5 s (2 s, then 4 s when there is none); there is no wait after the last try. The Yahoo phases ask about 90 times a second
  (6 at a time, `KR_FB_META_WORKERS`); if 429 answers grow, lower that number;
- the stocks not asked are unconfirmed, exactly like a stock whose source did not answer: left out of that day's file, or, when
  it was in the previous publish, carried at that publish's confirmed close with its own date and Jack's line (see "Korean stocks
  at their last confirmed close" above); never an older price under the new date. The log says so at once ("!! 2차 출처 시간 한도 600초: 다음 일별 시세를 더 묻지 않아요 …") and in the summary ("!! 2차
  출처 시간 한도 600초 — 다음 일별 시세: 받은 n / 대상 m — 나머지 k종목은 확인 못 한 종목 (…)"); the same for 야후 일봉 종가 and 야후
  차트 다시 읽기;
- data.json `pxSrc.fb.cut` = `{s, daum, yahoo, fill}`: the limit and the stocks not asked in each phase (also kept when the second
  source ran but found no usable day; `pxSrc.chk.cut` on volunteer-file days, where only the Yahoo spot check of must-haves + sample
  can shrink);
- the gate and the watchdog show **WARN "가격 확인 시간 한도 (경고만)"** when any count is above 0 (a file from before this change
  has no record: SKIP). It never stops a publish by itself.
- The KOSPI daily series (FinanceDataReader `KS11`, read from the volunteer cache without any time limit) is now read under a
  60 s socket limit (`KR_INDEX_TIMEOUT`) and logged: "· KOSPI 일봉 (KS11 · FinanceDataReader 캐시): n일 · 마지막 … (k초)", loud
  ("!!") when its last day is before the volunteer final date or when more than 10 calendar days are missing at the start or
  between two days (that library silently skips a year file it could not read). The data step also runs with `PYTHONUNBUFFERED=1`.

What protects users when the limit hits (and what does not):
- **Must-haves:** they are asked first. If one is still unconfirmed, that day is not used: the data stays on the last volunteer
  final day and the gate fails "pxDate 뒤 끝난 거래일 없음", so nothing publishes (no old price under a new date).
- **Market-cap order:** the run publishes the top 2,500 Korean stocks by market cap among the confirmed ones, so a cut first
  removes the smallest stocks. How many can go unasked before a published stock is lost depends on how many are unconfirmed anyway:
  - On a night when Yahoo's newest daily close is still blank (runs from the close until roughly 06:40 KST, when the close is read
    from Yahoo's price just after the close), about 9% are unconfirmed (2,526 of 2,771 on 11-19), so the room is only about 25–50.
    Measured on the 11-19 data (stocks not asked → published stocks lost), market-cap order: 25 → 0 · 50 → 3 · 100 → 22 · 200 → 73
    · 240 → 104 · 300 → 156 · 440 → 278; plain code order: 50 → 34 · 100 → 68 · 200 → 159 · 240 → 195 (code order also drops
    large recent listings such as LG에너지솔루션 373220 and SK스퀘어 402340, which have high codes).
  - When Yahoo's newest daily close is filled (e.g. the 06:40 run), about 1.2% are unconfirmed and a cut of up to about 200–240
    loses none (simulated in `tests/test_kr_fb_budget.py`).
- **The count rows** stop only large cuts: "국내 종목 수" fails below 2,300 published Korean stocks, which on a blank-close night is
  about 320 stocks not asked (about 440 when the close is filled); "국내 종목 수 변화" (more than 10% from the last publish) comes later.
  Since #158 (KONEX Yahoo × Naver) these numbers hold as before on a blank-close night (no KONEX stock can be confirmed then); when the
  close is filled, the ~23 KONEX stocks a normal day publishes also count, so the floor trips at about 465 not asked instead of
  about 440, with the same number of normally-published stocks missing (see "KONEX closes: Yahoo × Naver").
  Stocks carried at their last confirmed close (`pxd`, #159) never count toward either row: both count only Korean stocks priced
  at `pxDate` (`validate_data.kr_px_count`; the row's value names the carried count beside it), so these numbers hold as on main.
- **Plainly, the gap:** on a blank-close night, from about 50 to about 320 stocks not asked, the data publishes with published
  stocks missing (about 3 at 50, about 156 at 300) and only the WARN row. A check that stops the publish there would be a new
  publish-stopping rule and needs Jack's yes. Since the last-confirmed-close change, a stock from the previous publish is carried at
  its last confirmed close with its own date and Jack's line instead of going missing (at most 5 KRX trading days).
  Since #161 a run whose KOSPI/KOSDAQ coverage falls below the floor (97%) does not publish at all, at any time of day, and
  later runs republish the same day when they confirm more ("Backup days: coverage floor and same-day updates" below).

If the WARN shows:
1. Find the phase in the run log: the "· 2차 출처: … 묻는 중" line before the "!!" line has the GitHub timestamp, so the gap shows
   which source was slow.
2. A stock that was in the previous publish shows its last confirmed close with its own date and Jack's line ("오늘 종가를 확인하지
   못해서 {date} 종가를 보여 드려요."); any other stock left out shows "이 종목의 데이터를 찾지 못했어요" (portfolios: "오늘 데이터에 없는
   종목 … 빼고 계산했어요"). Since #161 later scheduled runs **do** try to fill them in: on a backup day `already_published.py`
   lets every later start run fully while the published file still has unconfirmed Korean closes, and a run that confirms more
   (losing none) republishes the same day ("Backup days: coverage floor and same-day updates").
3. Do not raise the limit to make one run pass. If it hits on days when both sources answer at normal speed, bring the phase
   times from the logs to Jack before changing `KR_FB_PHASE_BUDGET_S`.
4. If it hits on every run (a source blocking GitHub's servers), the must-haves stay unconfirmed and nothing publishes: that is
   the two-source rule working. Tell Jack in plain words which source is down.

## KONEX closes: Yahoo × Naver (코넥스 두 출처, since #158)

Jack, 2026-11-19 (answer 5, verbatim): "Yes: Naver for KONEX only, always with Yahoo, published only when they agree to the won;
daily KONEX checking too." CLAUDE.md says the same under "Two sources for official closes".

Why KONEX needs its own pair: Daum has no KONEX (all 107 codes answer HTTP 400), so until #158 every KONEX stock (about 31 of them
are in the published top 2,500) was left out on second-source days, and on volunteer-file days no KONEX close was ever
cross-checked (`kr_primary_check` samples only KOSPI/KOSDAQ codes). Naver's daily close is the official close for KONEX only:
KONEX has no after-hours trading and Nextrade does not trade it, so Naver matched the KRX final file on 2,881 of 2,881 KONEX
stock-days (27 final days, 2026-09-15 to 11-16, no-trade days included), against 186 of 1,276 for KOSPI/KOSDAQ. Naver is never
used for KOSPI or KOSDAQ.

**Second-source days** (`fetch_data.kr_knx_phases` · `kr_knx_confirm`): after the three Daum × Yahoo phases have finished (their
order, time limit and results are unchanged), the run asks, for the KONEX stocks only, in the same order (must-haves, then the last
final file's market cap) and under the same 600 s limit per phase (`KR_FB_PHASE_BUDGET_S`):
1. Naver daily bars (`api.stock.naver.com/chart/domestic/item/{code}/day`, 4 at a time, 20 s × 3 tries per stock), from the last
   final day px0 (for the anchor check below) to the newest second-source day;
2. Yahoo `{code}.KQ` daily closes (Yahoo carries 96 of 107 KONEX stocks, mislabelled MUTUALFUND/KOSDAQ, with a quote header frozen
   since 2024-07, but the daily bars are right);
3. for the newest day, a chart re-read of the stocks Yahoo answered but left that day's close blank (stocks Yahoo does not carry
   at all are not asked again).

Normally the three KONEX phases take about 10 seconds (107 stocks; 9–10 s on the live check of 2026-11-20). In the worst case
(every request timing out) each is cut at 600 s plus the requests in flight, like the Daum × Yahoo phases, so the second source
as a whole can now take about 74 minutes instead of 37 before the run moves on (the data job's limit is 300 minutes). A KONEX
stock not asked in time is left out like any unconfirmed one.

If the KONEX stage itself breaks (an unexpected error, not a source that doesn't answer), the run says so loudly ("!! 코넥스 2차
출처 단계가 고장 났어요 …"), leaves KONEX out of that day's file as before #158, and carries on with KOSPI/KOSDAQ unchanged; the gate
row below then warns "코넥스 단계를 묻지 않았어요". The same holds when the per-day KONEX confirmation or the cut-off step breaks
("!! {day} 코넥스 2차 출처 확인이 고장 났어요 …"): that day's file gets no KONEX rows and no half-built record.

A KONEX stock is confirmed when Yahoo's close (the value used) and Naver's close (the check) agree to the won
(`KR_FB_CLOSE_TOL`). Otherwise it is left out, exactly like a KOSPI/KOSDAQ stock with one source or two that disagree: the log line
"… 코넥스 2차 출처(야후 .KQ × 네이버 종가 원 단위까지 같음): 확인 a / b종목 · 빠짐 … — 다름: … — 야후 종가 없음: …" names every stock left
out with the reason. It is a plain "·" line on a usual day and a loud "!!" line only for the unexpected, by the same rules as the gate
row below: a missing Naver bar, an unreadable value, more Yahoo gaps or disagreements than usual, fewer than half confirmed, the time
limit, or no cut-off. Expected every day: the 11 KONEX stocks Yahoo does not carry (496320 본시스템즈, 238540 나노솔루션,
0077H0, 495810 유비씨, 0203K0 송우인포텍, 0230E0, 059180 엔더블유시, 0070X0, 403810, 476710, 332190) and 3–9 stocks on a day when KRX
moved the reference price without a trade (Yahoo keeps the last traded price: EMB 11-16, Naver 2,715 · Yahoo 2,895). On the live
check of 2026-11-20 (pxDate 11-10 … 11-19): 87–93 of 107 confirmed each day, and on the five final days every confirmed close equalled
the KRX final file (447 of 447, volumes and no-trade flags too).

**Anchor check: both sources can agree on an adjusted price** (second review M1, `kr_knx_anchor` · `kr_knx_confirm(anchor=…)`).
Yahoo's close is split-adjusted (it books 무상증자 as a split too), and Naver's daily bars are 수정주가 on the endpoints we use for
KOSPI/KOSDAQ (unverified for this one). Example: backup day 11-16, last final file (px0) 11-13, a KONEX stock's split or 무상증자
ex-date 11-17. A run on 11-17 can find both sources showing 11-16's close ÷ the ratio, equal to the won, and would publish that as
the 11-16 official close with pre-action shares (wrong market cap and d1); the gate's own re-check samples KOSPI/KOSDAQ only. So a
KONEX stock is confirmed only when, in addition, Naver's close on px0 equals the official close (market cap ÷ shares) in the px0
final file. An adjustment rewrites every bar before the ex-date, px0 included, so if Naver's px0 bar is untouched, its later bars are
too; the published value equals Naver's to the won, so it is unadjusted whatever Yahoo did (if only Yahoo adjusted, the two disagree
and the stock drops out). Yahoo's px0 bar is not required: on a no-trade day where KRX moved the reference price it is the last
traded price (3–9 stocks a day), so requiring it would only drop correct stocks. A stock that fails this is left out of that day's
file, as before #158, loudly ("!!" line: "기준일 {px0} 종가가 최종본과 다름 …" with both values, or "기준일 {px0} 종가로 맞춰 보지 못함"
when the px0 file has no official close for it, such as a listing after px0, or Naver has no px0 bar), and counted in
`pxSrc.fb.knx.adj` / `noAnchor`. When there is no px0 final file at all, no KONEX stock is confirmed (no cut-off either). On the
fixtures the check changes nothing; it was not re-run live, but Naver matched the final file 107 of 107 on each final day 11-10 …
11-16, so with any of those days as px0 every stock would have passed it.

**Only the KONEX stocks a normal day would publish go into the file** (review M1, `kr_knx_cap_floor` · `kr_knx_cap_keep`): a
confirmed KONEX stock is added only when its market cap (close × listed shares) is at least the 2,500th market cap (`MAX_KR`) in the
volunteer list's last final file, the same file that sets the asking order. For 11-19 (cut-off from the 11-16 final file) that was
199억원, and 23 of the 91 confirmed KONEX stocks were above it (live check, 2026-11-20); on 11-16, a volunteer-file day, 33 KONEX
stocks were inside the top 2,500 and 31 were published (5 of those 33 are among the 11 Yahoo lacks). Why: if every confirmed KONEX
stock (about 90) were added, they would fill the gaps on a morning when many KOSPI/KOSDAQ stocks go unconfirmed, and the "국내 종목 수"
floor (2,300) would trip about 70 stocks later than on a normal day (91 confirmed vs 23 above the cut-off on 11-19). Example (tests/test_konex_two_source.py): 500 KOSPI/KOSDAQ not
asked in time leaves 2,240; all KONEX would make it 2,347 and publish with about 230 normally-published stocks missing all day; with
this rule it is 2,270 and the floor stops the publish, as it does without KONEX. When the last final file has fewer than 2,500 known
market caps the rule cannot be set, so no KONEX stock is added that day (loud: "!! 코넥스 시가총액 기준을 정할 수 없어요"). The log
names the cut-off once ("· 코넥스 시가총액 기준 … 2,500번째 시가총액 …억원 이상") and, per day, how many confirmed KONEX stocks went
in and which were left out under the cut-off ("그날 파일에 넣은 코넥스 k … · 확인됐지만 시가총액 기준 아래라 뺀 m: …").

What this changes for KOSPI/KOSDAQ, plainly: their prices, sources, checks and asking order are unchanged, but which of them are
published on a second-source day is not. The published list is the top 2,500 by market cap among confirmed stocks, so the ~23 KONEX
stocks take back their places and about as many of the smallest KOSPI/KOSDAQ stocks near the cut-off (about 200억원) drop out of that
day's file, exactly as they do on every volunteer-file day.

The #151 trip points ("Korean second-source time limit" above) are unchanged in the sense that matters: on both main and this
branch every published stock is one a normal day would publish, so the floor trips when more than 200 normally-published stocks are
missing. Counted in KOSPI/KOSDAQ stocks not asked: on a blank-close night nothing changes at all (Yahoo's newest KONEX close is blank
too and cannot be read from its frozen quote header, so no KONEX stock is confirmed or added); once the close is filled (the 06:40
run), the ~23 KONEX stocks count toward the 2,300, so the floor trips about 23 not-asked stocks later than on main (about 465 instead
of about 440), with the same number of normally-published stocks missing.

The KONEX row is built like the KRX file: close, listed shares, market cap = close × shares, volume, open, high and low from
Naver. The listed shares come from that day's list file in the volunteer cache, or, when that day has no file, from the nearest
earlier one ("!! … 캐시 파일의 종목 목록" in the log): neither Yahoo nor Naver gives a share count, so it is not cross-checked (Daum
gives it for KOSPI/KOSDAQ). The close is exact either way (official close = market cap ÷ shares); only the market cap, and so the
cut-off test above, can be a few days old after a share change. Two fields are left blank on purpose:
- **거래대금 (Amount)** on a day with trades: neither Yahoo nor Naver gives a trading value, so it is not guessed. That day's `val` is
  blank and `val20` averages the days that have one (a no-trade day has exactly 0, which is kept). What users see: nothing changes.
  `val` appears only in 2.0's 종목 순위 거래대금 and 거래 급증 lists, which only include stocks whose 20-day average is at least
  5억원; no KONEX stock is near that (the largest was 0.3억원 on 11-16). A KONEX stock's `val20` would go blank only after 11 or more
  second-source days in a row. Known bias, left as is (second review nit): a traded backup day is skipped while a no-trade day counts
  0, so a KONEX `val20` that spans backup days reads a little low; it never matters against the 5억원 cut-off.
- **전일 대비 (Changes) and the change sign/ratio:** KRX moves a KONEX reference price without a trade (EMB 11-18: previous close 2,600,
  reference 2,700) and neither source gives it, so the KRX reference-price chain (`kr_ref_links`) counts these stocks as unchecked.
  They are expected, so the log counts them on their own plain line ("· KRX 기준가 연결 — 2차 출처 날 코넥스 … 확인 못 한 종목 n:
  예상한 것이에요", `kr_ref_blank_knx`), and the main "KRX 기준가 연결" line stays "!!" only for any other unchecked stock (second
  review S3). `krSeries.ref.unknownStocks` in data.json still counts all of them, as before. No value changes: Naver's bars for KONEX
  are already the official closes, so the pinning step has nothing to replace. `d1` is unaffected (it compares official closes).

**Volunteer-file days** (`kr_knx_daily_check` · `kr_knx_check`): every KONEX stock the run processes (the published top 2,500) has
its final-file close compared with Naver's daily close for pxDate, under a 120 s limit (`KR_KNX_CHK_BUDGET_S`; normally a few
seconds). The log line "코넥스 종가 네이버 확인 (1차 출처 날 …): 같음 n / n" is loud and names every stock when one differs, has no
Naver value, was not asked in time, or Naver could not be read. Nothing is dropped and nothing stops the publish on this check:
a publish-stopping rule or dropping a mismatching stock needs Jack's yes. On the five final days 11-10 … 11-16 the check matched
107 of 107 each day.

**data.json `pxSrc`:** `pxSrc.knx` = `{px, t, n, chk}`: where the published KONEX closes came from (`listing` or `yahoo+naver`; `null`
when a second-source day had no KONEX stage), the published KONEX codes, the count by source, and the volunteer-day check
(`{src: naver, n, same, none, noneEx, diff, fail, cut {s, naver}, err}`). `pxSrc.fb.knx` (second-source days) =
`{n, conf, kept, capOut, floor, noNaver, bad, noYahoo, diff, diffEx, anchor, adj, noAnchor, adjEx, left, yMeta, cut {s, yahoo, fill, naver}}`
(conf confirmed by both sources, kept put into that day's file, capOut confirmed but under the cut-off, floor the cut-off in won,
anchor the px0 date, adj / noAnchor the stocks both sources agreed on but the anchor check left out, adjEx examples
"code name final/naver"). `pxSrc.fb.conf` now
counts every stock in that day's file, the kept KONEX stocks included (the gate's "confirmed ≥ published" test needs that once
KONEX is published; a confirmed KONEX stock under the cut-off is not counted); the other `fb` counts stay KOSPI/KOSDAQ
(Daum × Yahoo) only.

**Gate rows** (all warnings; none stops a publish):
- **WARN "코넥스 종가 두 출처 (경고만)"** (review S1). On a second-source day the value always shows the counts, the cut-off and a few
  disagreements; it warns ("— 경고: …") when Naver had no bar for some KONEX stock (Naver down or changed), when more than 15 KONEX
  stocks had no Yahoo close (`KNX_NOYAHOO_WARN`: the same 11 every day 11-10 … 11-19, plus room for a few new listings Yahoo has not
  picked up; more means Yahoo left that day's KONEX closes blank, as it does for hours after the close), when fewer than half were
  confirmed, when a value could not be trusted, when more than 20 disagreed (`KNX_DIFF_WARN`: 3–9 a day on the same eight days, all
  reference-price moves without a trade; more means a source changed), when the cut-off could not be set or is not a positive number,
  when the anchor check left out any stock (`adj` or `noAnchor` above 0; a file without these keys reads as 0), or when the stage did
  not run. The routine 3–9 disagreements alone do not warn (they are in the value every day; a warning that is on every day gets
  ignored). On a volunteer-file day it warns when a published KONEX close differs from Naver, has no Naver value, was cut by the
  time limit or Naver could not be read. On any day it warns when the record is malformed or its codes differ from the published
  KONEX stocks (read from the description's "KONEX 상장"). A file from before #PR has no `pxSrc.knx`: SKIP. It never fails.
- **"가격 확인 시간 한도 (경고만)"** also lists the KONEX phases ("코넥스 2차 출처: 묻지 못함 야후 일봉 · 야후 다시 읽기 · 네이버") and the
  volunteer-day Naver check ("1차 출처 코넥스 네이버 확인").
- The gate's own price re-check on second-source days (`http_px_alt`) still samples KOSPI/KOSDAQ only; KONEX closes rest on the
  pipeline's Yahoo × Naver record. Open for Jack: whether the gate should also re-fetch a KONEX sample (Naver × Yahoo) itself;
  stricter, but the gate would then depend on Naver.

If the KONEX row warns (read the reasons after "경고:"):
1. Second-source day, "다름 n > 20": the routine 3–9 come from KRX moving a KONEX reference price without a trade (those stocks are
   out of that day's file, "이 종목의 데이터를 찾지 못했어요." on their pages, and come back on the next day both sources agree). More
   than 20 means one source changed: compare a few names on Naver's and Yahoo's charts.
   "야후 없음 n > 15" or "확인이 절반 아래" at night: Yahoo has not filled that day's KONEX closes yet; KONEX is out of that night's file
   and comes back with the next publish (a manual run after about 06:40 KST brings it back sooner; follow the DART rule).
   "네이버 행 없음": see 3. "시가총액 기준 모름": the volunteer list's last final file had fewer than 2,500 market caps; look at that file.
   "기준일 종가 다름 n": both sources agreed, but Naver's px0 close differs from the final file. Look for a split, merger, 무상증자 or
   other ex-date after px0 for that stock (the log line names it with both values); it stays out until the volunteer file is final
   again, which is the safe outcome. If it hits many stocks at once, Naver's bars may have changed basis: compare Naver's chart with the
   final file. "기준일 맞춰 보지 못함 n": the stock has no official close in the px0 file (listed after px0) or Naver has no px0 bar.
2. Volunteer-file day, "다름": this has never happened (0 of 2,881 KONEX stock-days, 09-15 … 11-16; the live check of 11-20 found the
   same on 11-10 … 11-16). Open the KRX final file and Naver's chart for
   that stock and date and tell Jack which one is wrong; the published close is the KRX file's.
3. "네이버 값 없음" for many or "받지 못함": Naver may be blocking GitHub's servers; the KOSPI/KOSDAQ path does not use Naver, so only
   KONEX is affected (on second-source days every KONEX stock drops out).

## Backup days: coverage floor and same-day updates (2차 출처 날 확인 비율 바닥 · 같은 날 다시 발행, since #161)

Jack, 2026-11-21, verbatim: "(c), with no new timer for Jack. KRX's final file has been stuck since 11-16, so treat Daum × Yahoo as the
normal path. Publish at 06:40 with what's confirmed (carries with their date line). Later runs update that day's data when more
closes are confirmed. Hold only if confirmed coverage is below a floor; set it from last week's 06:40 coverage and show the number in
the PR." (This replaced the first version of #161, which held runs before 08:00 below 97% of the last publish.)

A backup day is a day the volunteer KRX list has no final file for the price date, so the Korean closes come from Daum × Yahoo and are
kept only where the two agree to the won (#137). Price dates 11-17 to 11-19 were backup days; the publish of 11-21 (price date
11-20) used the KRX final file again (the volunteer cache posted it late), so backup days come and go with that cache.

**One decision per run** (`tools/publish_hold.py`, step "발행 판단 (2차 출처 날 확인 비율 바닥 · 같은 날 다시 발행은 더 나을 때만)", id
`hold`, right after the data step and before the gate; at any time of day). **"The last publish" is the file the site shows: the
`data` branch's `data.json`** (read the same way as `already_published.py`; `main` only before the `data` branch exists). Main's
`HEAD` is used only to tell whether this is a same-day run when the `data` branch can't be read, and to spot a half-finished publish
(below). Before the third review it compared with main's `HEAD`: when "커밋 & 푸시" succeeded but "data 브랜치에 올리기" failed, the
next run looked "same, not better" (healthy), closed the alarm and left the site a day behind.
1. **Dates never go back.** If this run's Korean price date or US price date is earlier than the last publish's, it does not publish
   (warning "발행 보류 (날짜가 뒤로 감)"). Example: a delayed 08:17 start running at about 10:15, inside Yahoo's 10:00–10:40 gap, gets a
   US date one day older while the Korean date stays. A US date going back is a neutral hold. A **Korean** date going back also fails
   the gate row "pxDate 가 뒤로 가지 않음" (the gate compares with main's `HEAD`), so that run ends red and the watchdog alarms.
2. **Coverage floor (backup days).** Coverage = KOSPI/KOSDAQ closes confirmed by both sources (plus closes re-used from an earlier
   publish of the same day) ÷ the day's KOSPI/KOSDAQ list: (`pxSrc.fb.conf` − KONEX `fb.knx.kept` + `pxSrc.own.reuse.kk`) ÷
   (`fb.n` − `fb.mkt`), used only when the record adds up; carried closes (`pxd`, #159) never count. Below `COVERAGE_FLOOR_PCT`
   (97%) the run does not publish (warning "발행 보류 (2차 출처 확인 비율 바닥 아래)"). Exactly the floor publishes.
   Last week's 06:40 publishes (data branch): 11-19 2,743 / 2,771 = 98.99%; 11-20 2,740 / 2,771 = 98.88% (the only backup days;
   11-17 … 11-19 runs saw about 98.7%); 11-13, 11-14 and 11-17 were KRX-final days (100%). 97% of 2,771 is 2,688: up to 83 unconfirmed
   still publish. Chosen over 98% (only about 0.7 points of room) because since #159 unconfirmed stocks show their last close with
   Jack's line. A night when Yahoo has not yet filled the day's closes (about 2,526, 91%) is still held.
3. **Same-day updates.** A run with the same Korean price date as the last publish publishes only if it **loses nothing** of that
   publish (`publish_hold.lost_stocks`): every Korean stock at that date's close stays at that date's close; every carried Korean stock
   is still there, carried or now at that date's close; every US stock, fund, gold and bond row is still there; when the US date is the
   same, every US stock at the US date's close stays at that close (a US close that falls back to Yahoo's older bar or to a carry is a
   loss); every Korean stock that had d1 and still has the same close (to the won) keeps its d1 (a stock now marked 거래 없음 is not a
   loss). **And**:
   - the US date is the same and the file has **strictly more Korean stocks at that date's close** (`validate_data.kr_px_count`;
     confirmations of stocks outside the published file don't count), or
   - the US date is newer (the US update is never blocked by Korean counts).
   Otherwise: "같은 날 · 더 낫지 않음" (notice) or "지난 발행본의 종목을 잃음" (warning; the decision line names the stocks, US closes that
   went back to an older date, and stocks that lost d1). If the last publish was a KRX-final day and this run is a backup day, it does
   not publish. If this run is KRX-final (the volunteer final file for the same date appeared later in the day) the same rule applies:
   it publishes when it loses nothing and has more Korean stocks at that date's close, which it usually has (the morning's carried
   stocks now have official closes); otherwise it is "같은 날 · 더 낫지 않음" and the morning publish stays.
   - When the US date is newer, US stocks that left the list (an S&P 500 change, a carry past 5 US trading days) are not a loss
     (otherwise US prices would stall through Korean holidays such as 설 and 추석; the gate's US count rows still apply). Funds
     (including US-listed fund rows such as 379800 KODEX 미국S&P500), gold and bond rows are a fixed list and still count.
   - **Half-finished publish:** if main's `HEAD` `data.json` is a newer publish than the `data` branch's (`publishedAt` later; the last
     "data 브랜치에 올리기" failed), a run that would be "같은 날 · 더 낫지 않음" publishes instead (loud), so the `data` branch push repairs
     the site. A run that loses something is still held. An older or unreadable `HEAD` (a dry run on a branch with a stale
     `data.json`, a manual run queued behind a live run) changes nothing.
4. **When it can't decide:**
   - Today's file unreadable → no hold (warning; the gate fails on that file anyway).
   - Today's coverage can't be computed (the record doesn't add up) → the floor is skipped but the same-day rule still applies (a
     same-day file that loses stocks is held); if nothing is held, it publishes with a warning.
   - No previous file to compare (a `bootstrap` run, or a dry run whose compare commit wasn't fetched) → floor only (warning).
   - **Can't decide on a same-day run** (kind `stop`): the decision crashed, or the `data` branch couldn't be read, and today's file
     has the same Korean date as the last publish (or main's `HEAD` when the `data` branch is unreadable), or it can't tell. Exception:
     an unreadable `data` branch on a Korean-holiday morning (same Korean date as `HEAD`, newer US date) compares with `HEAD` instead. The script
     writes `hold=true`, ends with exit code 3, and the step fails: the gate, the screen check and both publish steps are skipped, the
     run is red and the watchdog alarms (not neutral). The next run tries again.
   - A crash on the day's first run (a new Korean date) → no hold (warning), as before: the gate and the screen check decide. If the
     script can't start at all (exit code other than 0 or 3), the step also falls back to no hold.

Later runs on a backup day (`already_published.py`, `open_closes`):
- The day counts as open only while the published file has unconfirmed Korean closes **that a re-ask can change**: `pxSrc.fb.open`
  (no Daum row, unreadable Daum row, Yahoo close still blank) plus `fb.knx.open` (KONEX: no Naver row, unreadable, Yahoo blank),
  minus closes re-used the same day. Persistent cases don't count: Daum and Yahoo disagreeing (about 25 a day, e.g. STX), and stocks
  Yahoo answered "no data" for (`noList`: a well-formed empty chart or Yahoo's own 404 "Not Found"; about 5 KOSPI/KOSDAQ and 11
  KONEX). A Yahoo request that failed or timed out is not "no data": that stock stays open and the next run asks again. On 11-19 that
  left 1 open stock. A day with nothing open stops early as before.
- **Quiet period.** A live (not dry) run that re-ran the live file's Korean and US price dates records in `.dart-cache/kr-rerun-v1.json`
  (saved with the DART cache) how many Korean stocks at that date's close it added, with its GitHub run number. If it added none,
  scheduled and timer starts in the next 3 hours do not collect data, but only when: that run ended **green** (the gate and the screen
  check passed; read from GitHub's public run record, without a token; if it can't be read, the run collects as usual), the record and
  the start are on the same KST day between 07:00 and 15:30 (no new Korean or US trading day can end in between), and the live file
  still has the recorded dates. The log says "!! 같은 기준일을 다시 도는 실행이에요: … 3시간이 지나기 전이라 데이터를 모으지 않아요"; the
  files stay as published, and the decision is "쉼" (quiet), which is **neutral** for the watchdog: a run that tested nothing new never
  closes an alarm. Manual runs always run. A record from an earlier day (for example Saturday's, seen on Monday) never quiets a run.
  Third review: a quiet run writes no new file, so the gate checks the live `data.json` as it is, and its row "publishedAt 12시간 이내"
  would fail on an old publish (Monday re-runs of Saturday's publish, the day after a holiday). So a run is quiet only if the live
  file's `publishedAt` is less than 11 hours old (`KR_RERUN_QUIET_PUB_AGE` = the gate's `PUBLISHED_MAX_HOURS` − 1); otherwise it runs.
  The quiet window's 15:30 end stays fixed: the special-sessions table can only move the close later, so 15:30 is never after the
  real close.
- **Fewer requests.** The second-source stage keeps the values it confirmed on the newest day (Daum row fields and Yahoo close; KONEX:
  Naver row and Yahoo close) in `.dart-cache/kr-fb-v1.json`. A later run of the same price date does not ask Daum, Yahoo or Naver
  again for a stock the published file has at that date's close when the kept values match that close to the won
  (`fetch_data.kr_fb_cache_pick`); everything else is asked (`pxSrc.fb.skip` = stocks not asked; the log line "!! 2차 출처 같은 날 다시
  쓰기 …" gives asked vs re-used). Kept values of stocks the publish does not have at that date's close are not trusted (the cache is
  saved before the gate, so it can come from a held, gate-failed or dry run).
- **Top-2,500 cut on a same-day run** (`fetch_data.kr_same_day_keep`, #161 second review): a run with the same Korean price date as a
  backup-day publish processes the top 2,500 by market cap **plus every Korean stock that publish had** (at that date's close or
  carried) that is on today's list (confirmed by both sources, or in the KRX final file). Why: on a day with more confirmed stocks than
  2,500 (11-20: 2,740), a stock carried at 06:40 and confirmed later moved into the top 2,500 and pushed out a stock published at that
  date's close (confirmed, so neither re-used nor carried), or fell below the cut itself, and every useful re-run was a loss hold. Log:
  "같은 기준일을 다시 도는 실행: 지난 발행본의 국내 종목 … 상위 밖에서 더한 종목 n" (loud when n > 0, with names). The list can then be
  slightly above 2,500 (about 2,500 plus the morning's carried stocks now confirmed); the gate's two Korean count rows have no upper
  bound (≥ 2,300; ±10% against the last publish) and the next new price date goes back to exactly the top 2,500. The first run of the
  day (the last publish is the previous day's) and runs after a KRX-final publish are unchanged.
- **d1 on the run that switches to the volunteer final file** (`fetch_data.kr_d1_same_day`, #161 second review): when the volunteer
  list posts the same date's final file later in the day while the day before is still an intraday copy, that run has no usable
  previous-day file, and the last publish is that morning's (same price date), not the previous day's that #163's path needs. Before
  this fix every Korean d1 was blank and the gate row "필수 종목 d1" failed on every later slot. Now it keeps the morning publish's d1
  for every stock whose official close equals that publish's price to the won (same previous-day base, already checked by the gate);
  a different close, a stock the morning publish did not have, had carried (`pxd`) or marked 거래 없음, or also left blank stays blank
  (d1Why prev; a morning "range" stays range). Logged loudly ("d1: 직전 거래일 … 지난 발행본이 같은 기준일 …") with counts and examples,
  in `d1Base` with `same: 1`. #163's path (the last publish is the previous trading day) is unchanged. Third review: when today's file
  has the KRX base price (Close − Changes), a morning d1 is re-used only if it is within 0.01 of the change against that base
  (rounded to 2 places); otherwise it stays blank (count `d1Base.krx`, with examples "morning → KRX"). This catches a day KRX reset the
  base (rights, splits) while the morning's d1 used the two-source previous close.
- **US closes:** same-day updates fill Korean closes only. US carries (`pxc`) never make a later run re-run (`open_closes` counts 0 for
  US). A re-run started for Korean closes fetches US prices again, and if it publishes, US closes Yahoo filled since come with it; a US
  improvement alone does not publish on the same US date. US carries otherwise wait for the next day's publish (a newer US date).
  Counting `pxc` as open was not chosen: carries can last up to 5 US trading days (also on KRX-final days, where same-date runs make
  DART calls), and the "better" rule would have to count US closes too.
- **Same-day re-use.** A stock the earlier same-day publish had at that date's close that this run could not confirm (and has no
  matching kept value for) keeps the earlier close (`fetch_data.kr_same_day_reuse`, logged, `pxSrc.own.reuse`). Not re-used, so the
  run loses it and does not publish: the sources now disagree on it, only one source gave a close today and it differs from the
  published close (third review: `pxSrc._one`, kept in memory only — Daum's close when Yahoo is blank, Yahoo's when Daum has no usable
  row), it left the list, its price-history mark lacks its move, it would
  exceed this run's confirmed count (the gate row "확인 종목 수 ≥ 발행한 국내 종목 수" stays), or it is KONEX (the day's KONEX rows are
  only this run's confirmations, so the gate's KONEX row counts stay right; earlier KONEX come back through the kept values).
- **No DART calls on a re-run of the same price date** (this run and the live file are backup days with the same Korean price date,
  whatever day the live file was published, so Monday's re-runs of Friday's data count), **and the restored DART cache covers the live
  publish** (third review, `fetch_data.dart_cache_covers`: the cache's `meta.dartAt` — the `publishedAt` of the last run whose
  financials and disclosures came from that cache with DART not down, written by `dart_cache_mark` — is at or after the live file's
  `publishedAt`). If it doesn't (the morning's cache save failed, or an older cache was restored), the run calls DART as usual
  (cache-backed: entries in the cache are not fetched again, so it is not a full-DART run) instead of rolling financials back. If the
  cache is empty, a same-day run stops before any DART call (an empty-cache DART run is a full-DART run, allowed once a day and only
  by hand); the site keeps the live publish and the run is red. Caches saved before this change have no `dartAt`, so the first
  same-day re-runs after it ships call DART once (about 670 disclosure calls plus anything missing); the first run that finishes
  writes it. Dry runs never write `dartAt` (their cache is saved in main's scope too and may lack a live run's entries). With a
  covering cache the DART client makes no requests;
  fundamentals come from the DART cache, and the 90-day re-checks and re-reads wait for the next new-day run without being counted.
  The log's DART line says how many requests it held back. The disclosure file is the live `disc.json` as it is, but only if the US
  price date is the same too and that `disc.json` belongs to the same publish as the live `data.json` (same `publishedAt`); otherwise
  disclosures are fetched from DART as before (loud). The re-used file keeps its own content date (`asOf`), so disclosures filed since
  then (for example over a weekend) come with the next new-day publish, and the file says how old its content is. A first run of the
  day makes about 670 DART calls for disclosures; repeating them on every re-run, plus a full-DART day, could pass the 20,000-a-day
  limit.

Expected requests on a backup day like 11-19 (first run at 06:40, then re-runs while 1 stock is open):

| Source | First run of the day | Full re-run | Quiet run (within 3 h of a run that added nothing) |
|---|---|---|---|
| Daum daily rows (KOSPI/KOSDAQ) | about 2,772 | about 300 (not at that date's close in the publish: about 270 below the top-2,500 cut + about 30 unconfirmed) | 0 |
| Yahoo daily closes + re-read | about 2,772 + 0–41 (about 2,770 on a Yahoo-blank night) | about 300 + a few | 0 |
| KONEX Naver + Yahoo .KQ | 107 + 107 | about 80–107 each (published KONEX are re-used; others asked) | 0 |
| Naver price series (FinanceDataReader) | about 2,500 | about 2,500 + the morning's stocks kept above the cut (a few dozen; not re-used, see below) | 0 |
| US prices (Yahoo) | about 800 | about 800 | 0 |
| DART | about 670 (disclosures) | 0 | 0 |
| Gate's own Daum × Yahoo spot check | about 412 (206 × 2) | about 412 | about 412 |

With the quiet period, a day like 11-19 has about 2–3 full re-runs at most (one every 3 hours until 15:30, plus a delayed afternoon
start after 15:30); a day with nothing open has none. The Naver price series are not re-used on a re-run: that step also builds
run-wide price-history records (official-close pins over the last 19 sessions, reference-price links, jump marks) that the gate
checks across every stock, so re-using per-stock results needs those records carried consistently; that is a separate change.

What the other pieces see:
- **Watchdog:** a run that did not publish is either **neutral**, **healthy** or **red**. Red: a `stop` decision, or a hold whose gate
  or screen check failed (for example a Korean date going back) — it alarms like any failed run. Neutral (floor hold, a US date
  going back, a lost stock, can't compare, quiet; the run itself ended green): the step "발행 판단 표시 (감시에 중립인 보류)" runs, and
  `watchdog.is_held_run` skips the run when judging
  "the last daily run" (it neither opens nor closes an alarm). Healthy ("같은 날 · 더 낫지 않음": the gate and the screen check passed
  and the dates equal the live file's): that step is skipped and the run counts like a successful run, so **an alarm opened by a red
  later run closes at the next healthy run** ("정상화됐어요"). Runs from before this marker count as neutral.
- **Deploy:** deploys only after "data 브랜치에 올리기" succeeded, so a run that did not publish deploys nothing.
- **09:13 check:** it finds publishes by "커밋 & 푸시". Its prompt will be updated by the coordinator after this merges; until then it
  does not know about holds (it may report "data not in" on a held morning without saying why). After the update it reports the
  floor, dates-back and lost-stock warnings; the same-day and quiet notices are normal.
- **Gate:** the rows that compare with the last publish pass a same-day republish unchanged (pxDate is not earlier; the KR count change
  is small; same-date prices don't move; `tests/test_publish_hold.py`, also with a re-use record and KONEX rows). No gate row changed.

Costs and limits:
- **A later run can still go red** on a source problem (the gate and the screen check run on every run). That opens a data alarm
  while the site keeps the good earlier publish; the next healthy run (a "같은 날 · 더 낫지 않음" run or a publish) closes it.
- **Floor holds all day:** if a source stays broken, every run is held and the site keeps the last publish with its date; the
  watchdog's stale-price check alarms after 15:30.
- The floor counts the whole KOSPI/KOSDAQ list, not just the ~2,500 published stocks.

What to do:
- A same-day "발행 안 함" notice is normal. A floor-hold warning on the 06:40 run: wait for the next run; if no scheduled run has
  started by about 11:00 KST, start Actions → 시세 데이터 갱신 → Run workflow (following the DART rule).
- A "날짜가 뒤로 감" warning: a source gap during that run; the next run usually has the dates back. A "종목을 잃음" warning: read which
  stocks (the decision line names them, including US closes that went back to an older date and stocks that lost d1); one-off source
  trouble clears on the next run, a repeat means the pipeline drops rows or d1 (for d1, read the run's "d1:" lines).
- A red later run on a backup day: read which row failed. If the site's data is the good earlier publish (check the date on the
  site), it is a source problem on that run; the next healthy run closes the alarm. Never loosen the row.
- Never change the floor (`COVERAGE_FLOOR_PCT`) or the quiet period (`KR_RERUN_QUIET`) without Jack's yes.

## Deploy gate: Daum spot-check time limit and refusal (관문 두 출처 확인 시간 한도 · 거절, since #157 and #164)

Jack, 2026-11-20 (verbatim): "Yes to 10 minutes, but a timeout skips the Daum spot-check with a loud warning; the deploy continues
on the other checks. An outside site must never block a code fix."

On a second-source day (data.json `pxSrc.px` = `daum+yahoo`) while the volunteer cache still has no final file for pxDate, the gate
fetches its own closes to compare: the 7 must-haves plus a 200-stock sample, about 206 stocks in all on real data (`http_px_alt`,
4 at a time, 20 s per request, three tries). The deploy and the watchdog run the gate with `--live`, and there it asks Daum only. On
11-20 at 09:03 KST the deploy sat 19 minutes in that step with no output (Daum slow); the job's only limit was 80 minutes. A normal
run takes about a minute (from here on 11-20: 54 s for 206 stocks, the whole gate 66 s).

**Who gets the limit: the deploy only.** Jack's yes names the deploy. The deploy's gate step (`deploy.yml`, "발행 관문
(validate_data.py --live, 올릴 파일 그대로)") sets `BAEPSAE_DAUM_LIMIT_S: "600"` (= `PX_ALT_LIVE_BUDGET_S`) in that step's `env`; by
hand the same is `python validate_data.py --live --daum-limit 600 --dir DIR`. A limit shorter than 600 s, or a value that is not a
number, stops the gate with FAIL before anything is fetched (a shorter limit would skip more often). Not limited, as before:
- the **watchdog** (`watchdog.py` calls `validate_data.py --live --dir …` with no limit, and removes `BAEPSAE_DAUM_LIMIT_S` from the
  environment it passes to the gate, so it can never inherit one). It opens an alert only on a gate FAIL, so a WARN would turn a
  slow-Daum watchdog run into a quiet pass. If Daum hangs there, the watchdog job's own 30-minute limit ends it, as before;
- the **daily run's gate** (publish mode) and `--bootstrap`: no limit even if one is given ("· 다음 확인 시간 한도(…)는 사이트
  점검(--live)에서만 써요 — 이 실행(publish)은 한도 없이 예전 그대로"), every stock asked, coverage short means FAIL.

In the deploy, the whole spot check has a 600 s limit:
- it logs a start line: "· 관문의 두 출처 확인 시작 (… · 다음 일별 시세 + 발행 기록): 206종목 · 동시 4 · 시간 한도 600초 (배포 — …)"
  (the watchdog says "시간 한도 없음 (예전 그대로)", the daily gate "시간 한도 없음 (발행 관문 · 예전 그대로)"), and the result line
  "관문의 두 출처 공식 종가 …" ends with "걸린 시간 n초";
- the must-haves are asked first; after 600 s no new request is sent, retries included. A request already in flight finishes under
  its own limits (20 s to connect + 20 s between bytes, so about 40 s; a DNS lookup or a server dribbling bytes is outside that,
  never seen), so the spot check ends by about 10 min 40 s at worst. All worker threads have ended when it returns;
- each stock ends in exactly one of four states (retries and their pauses are the same whatever the error):
  - **close received**;
  - **network error**: all three tries used, and the last one failed with a connection error or timeout (requests' `ConnectionError`
    or `Timeout`, Python's `ConnectionError` or `TimeoutError`) or HTTP 429 or 5xx;
  - **Daum's definite non-answer**: no row for that day, HTTP 4xx other than 429, no close in the row, or the last try failed with
    anything that is not a network error (a 200 reply that is not JSON or has the wrong shape, such as a block or captcha page). A
    stock whose last answer before the limit was one of these counts here even if its retry was cut;
  - **cut**: not asked, or not asked again after a network error, before the limit. The last errors of the stocks cut after a
    network error are kept apart from the general error examples and printed on the second "!!" line (up to five, with the count:
    "네트워크 오류 뒤 다시 묻지 못한 종목 m (마지막 오류: … (시간 한도로 다시 묻지 않음))");
- the log says it twice: at the moment ("!! 관문의 두 출처 확인 시간 한도 600초: 다음 일별 시세를 더 묻지 않아요 …") and after
  ("!! 관문의 두 출처 확인이 시간 한도 600초에 걸렸어요 (Jack 2026-11-20): 확인 n / 206종목 · 시간 한도로 건너뜀 k · 네트워크 오류 e ·
  다음이 그날 종가를 주지 않음 d … · 네트워크 오류 뒤 다시 묻지 못한 종목 m (마지막 오류: …)", ending with what the gate will do).

**What a cut skips, and what still fails.** Only the shortfall that the cut (and network errors) can explain is skipped:
- **WARN, deploy continues:** every must-have was received, cut or hit a network error, and received + cut + network errors is at
  least 90% of the stocks asked. The row **"pxDate 최종본 여부" turns WARN** with the counts ("…를 시간 한도 600초로 건너뜀 (Jack
  2026-11-20) — 한도 전에 확인 n / 206종목 (시간 한도로 건너뜀 k · 네트워크 오류 e · 다음이 그날 종가를 주지 않음 d) …"). It is a GitHub
  warning annotation, so the morning check sees it;
- **still FAIL, as before ("최종본 날짜 계산"):** a must-have that Daum definitely did not answer (no row, HTTP 4xx, no close, a
  reply that is not JSON), or
  so many definite non-answers that even counting every cut and network-error stock as received stays under 90% ("… 모두 받았다고
  쳐도 n / 206 (기준 90%) …"). These are not caused by the time limit, so the time limit does not excuse them;
- **still FAIL, as before:** the file's own record (pxSrc says second source, its date is pxDate, no must-have unconfirmed at
  publish, confirmed count ≥ published Korean stocks), pxDate before today and after that day's close + 30 min;
- **wrong closes still FAIL:** every close Daum did return is compared with the published price. "005930 = 공식 종가" must match to
  the won. Whenever the limit was hit, "한국 가격 = 공식 종가" counts the wrong closes it saw against all the stocks it meant to ask
  (about 206), treating the stocks it never received as matching: it FAILs when (asked − wrong seen) / asked is under 99%, so a FAIL
  here always means the full check would have failed too (1 wrong among 60 received: 205/206 → WARN; 2 wrong among 192 received:
  204/206 → WARN; 3 wrong: 203/206 = 98.5% → FAIL). It is a WARN while it passes, because it saw only part of the sample; a FAIL that
  would round to "99.0%" shows two decimals (e.g. "98.99%"). With no close received, both price rows WARN;
- if the limit hits after the must-haves and 90% of the sample have already answered, "pxDate 최종본 여부" is checked as before and
  passes, with a WARN that says how many were skipped; the price row is counted as above.

**When Daum refuses outright (since #164, Jack 2026-11-21).** Jack's question 3 of 11-20, verbatim: "Deploy price check when Daum
refuses instead of being slow. Your 10-minute limit covers a slow Daum. If Daum starts refusing GitHub's servers outright, the way KRX
did, nothing times out, and every code deploy stops until Daum answers again. Skip the Daum check in that case too, with the same loud
warning? It loosens a check, so it's yours. (Recommended: yes, for code deploys only. The daily data publish keeps its own two-source
checks either way.)" Jack, 2026-11-21: "3. Yes."

**Code deploys only: its own switch.** The refusal rule needs both #157's limit and its own switch `BAEPSAE_DAUM_REFUSE_SKIP=1`
(`PX_ALT_REFUSE_ENV`; by hand `--daum-refuse-skip` together with `--daum-limit 600`). The deploy's gate step sets it with
`BAEPSAE_DAUM_REFUSE_SKIP: "${{ github.event_name != 'workflow_run' && '1' || '0' }}"`: **1** for a code deploy (a merge to main = push,
or Run workflow by hand), **0** for the deploy that runs right after a data publish (`workflow_run`), which keeps only the 10-minute
limit and fails on a refusal as before. Any value other than 1, 0 or empty stops a `--live` gate with FAIL before anything is fetched.
The watchdog removes the switch (and the limit) from the environment it passes to the gate; the daily publish gate ignores both. A
code deploy logs "· 다음의 거절로 건너뛰기: 켜짐 (코드 배포 · Jack 2026-11-21)" and its start line ends "· 다음이 거절하면 (답이 정해진 21종목
이상이 모두 거절 · 필수 종목 모두) 그만 묻고 경고로 건너뛰어요 (코드 배포만)".
- **A refusal** (per stock): Daum answers HTTP 401, 403 or 451; or all three tries fail with a refused connection, a connection reset
  or abort (including "Remote end closed connection without response" and broken pipe), the far end cutting or closing TLS
  (`SSLEOFError`, `SSLZeroReturnError`), a TLS alert the far end sends that means "no" (`PX_REFUSE_TLS_ALERTS`: handshake failure,
  access denied, protocol version, insufficient security, unrecognized name), or HTTP 429. Not a refusal (unchanged): timeouts (the
  time limit covers those), HTTP 5xx, a DNS failure, a proxy error, TLS errors our own client raises (certificate verification,
  WRONG_VERSION_NUMBER, UNSAFE_LEGACY_RENEGOTIATION_DISABLED, DH_KEY_TOO_SMALL, a local HANDSHAKE_FAILURE: any such error inside the
  chain makes the whole try a non-refusal), the far end's "broken" alerts (internal error, bad record MAC), a bare connection error
  that names no cause, a 200 reply that is not JSON (it could be a block page, but it could as well be a changed address, so it stays
  a definite non-answer), HTTP 404 and other 4xx, no row for the day. Every refusal is already a #157 network error or a #157
  definite non-answer (`px_refusal_error`, `px_refusal_answer`). The examples name the innermost cause (`px_refusal_name`: "HTTP
  403", "ConnectionRefusedError", "RemoteDisconnected", "SSLEOFError", "SSLError TLSV1_ALERT_ACCESS_DENIED", "HTTP 429"), not the
  outer "HTTPSConnectionPool(host=…" text.
- **Daum refuses outright** when every stock whose Daum answer is settled so far is a refusal (no close, no "no row", nothing else),
  every must-have is among them, and there are at least `px_alt_refuse_need(asked)` of them: the smallest count that already makes
  the old 90% rule impossible even if every other stock answered (21 for 206 or 207 stocks). At that point the old check could not
  pass anyway. The must-haves are asked first, so with 4 at a time this takes seconds (403: 21–24 requests, since up to 3 more are
  already in flight; refused connections: 21–24 stocks × 3 tries). If any other answer arrives first, the rule is off for that run and
  everything behaves as before (**partial refusal = as today**).
- Then the check stops asking (retries included; requests already in flight finish under their own limits, and their closes are
  kept), logs at the moment "!! 관문의 두 출처 확인: 다음이 거절해요 — 답이 정해진 21종목이 모두 거절 (필수 종목 7 / 7 · 보기: …) …" and
  after it "!! 관문의 두 출처 확인을 다음이 거절했어요 (Jack 2026-11-21 · 코드 배포만): 거절 21종목 … · 거절 뒤 묻지 않음 n · 확인 … — 다음의
  확인을 건너뛰고 경고 ('pxDate 최종본 여부' 줄) …". The row **"pxDate 최종본 여부" turns WARN** ("…을 다음이 거절해 건너뜀 (Jack
  2026-11-21 · 코드 배포만) — 거절 21종목 (필수 종목 7 / 7 · 보기: …) · 거절 뒤 묻지 않음 n · 확인 … · 발행 때 2차 출처(다음 × 야후) 확인 …"), so
  it is in the run summary table and a GitHub warning annotation the morning check reads. The deploy continues on the other checks.
- **Still FAIL, exactly as #157:** a must-have Daum definitely answered with no close (no row, 404, a reply that is not JSON): that is
  an answer, so the refusal rule never starts; the file's own record conditions; and every close Daum did return (in-flight ones
  after the stop) is compared in the price rows by #157's rule ("005930 = 공식 종가" to the won when received; "한국 가격 = 공식 종가"
  counts wrong closes against all stocks asked, e.g. 3 wrong: 204/207 = 98.6% → FAIL). With no close received, both price rows WARN
  with "다음이 거절: …".
- Known limit after this change: a Daum outage that fails fast with **5xx**, a block that serves a **200 page that is not JSON**, a
  **DNS** failure, or a TLS failure our own client raises still blocks every code deploy (not refusals by the definition above;
  widening it needs Jack's yes). The deploy right after a data publish fails on any refusal, as before.

If the WARN shows:
1. Read "걸린 시간 n초" at the end of the line "관문의 두 출처 공식 종가 …" in the deploy log (and the counts on the "!!" line after
   it): that is Daum's speed today. (The time between the start line and the "!!" line is not reliable where the output is collected
   and printed at the end.)
2. The deploy went ahead on the other checks. Nothing to undo; the next deploy, and the watchdog's own unlimited run, check again. If
   the volunteer cache gets its final file for pxDate later, the gate compares against that file instead and Daum is not asked at all.
3. Do not shorten or raise the limit to make a run pass. If it hits on days when Daum answers at normal speed, bring the log times
   to Jack.
4. If a price row or "최종본 날짜 계산" fails on a timeout day, it is not the timeout: it is a real mismatch between Daum's close and
   the published price, a must-have Daum has no close for, or too many stocks with no close. Treat it like the same row failing on
   a normal day.
5. If the WARN says "다음이 거절해 건너뜀": read the examples on the "!!" lines ("HTTP 403", "ConnectionRefusedError", …).
   - **First check whether it is us.** If the warning first appears on a deploy whose own change touched `validate_data.py`'s Daum
     request (`PX_DAUM_DAYS`, `_daum_day_close`: address, headers, Referer), suspect our code, not Daum: a broken request can get
     403 for every stock. Revert or fix that change; the next deploy (or the watchdog) shows whether Daum answers the old request.
   - A firewall or proxy on the machine running the gate that resets connections also reads as a refusal. That can only happen on a
     hand run (GitHub's runners have no proxy); on a hand run behind a proxy, read the examples before believing "Daum refuses".
   - Otherwise one deploy is nothing to act on. If every code deploy shows it, or the watchdog's own run (no limit) or a deploy after
     a data publish fails "최종본 날짜 계산" with the same errors, Daum is blocking GitHub's servers: tell Jack in plain words, since
     code deploys then check prices only against the daily run's two-source record. Do not change the refusal definition, the alert
     list or the count to make a run pass.

## Korean dividend proof (배당 기준 증명, since #PR — Jack 2026-11-14, item 5)

A Korean payer whose dividend could not be put on today's share basis (`divSt` nc · nd) used to show "배당을 줘요" with no
yield. The daily run now tries to prove that basis (`fetch_data.py` `DivWhy.prove`, after the `dvWhy` check, before the
yield and the 배당 rank): the factor is the product of the 액면분할 · 주식병합 · 무상증자 filings after the report year
(the same DART decision lookups and cache entry as `dvWhy`; whole split ratios such as 2, 5, 0.5, and since #PR the exact bonus
ratio a 무상증자 filing gives, below), and it must agree with
the share counts, either **today** (the dividend total ÷ today's listed shares = the dividend per share ÷ the factor, ±3%) or
**yearEnd** (the shares that got the dividend = that year-end's outstanding shares in 주식의 총수 현황 ±3%, and today's
listed shares between those × the factor and the year-end issued shares × the factor plus the new shares that filed
제3자배정 · 일반공모 rights issues and bonds explain, each scaled only by the share events after its own date, +3%).
An earlier year's bar comes back only when the shares that got each year's dividend differ by the filings' factor (±15%).

**Exact bonus ratios (since #PR — Jack's explicit yes, 2026-11-15, answer 12; a loosening of the gate's whole-ratio rule, recorded
under 안전 규칙 변경).** A 무상증자 ratio that is not a whole split ratio (대한제강 ×1.6616554, TJ미디어 ×1.5, 알테오젠 ×1.3 …) is
used when all three guards hold: (a) every event whose ratio is not a whole split ratio is a bonus read from the fricDecsn · pifricDecsn
API with r = 1 + x (x = new shares per common share, the API's own value; the pipeline computes with 1 + x, `prove_exact_bonus` ·
`prove_prod`); whole events beside it (남성's ×0.1 merge from the filing) are as before; (b) the product of the events equals the
published `dpsF` to 1e-6 for every such year; (c) the proof's share-count checks pass (today or yearEnd for this year, the ±15% rule
for an earlier bar). The gate checks the same three guards on the published numbers (`validate_data.py` `exact_bonus_problem`) and
only then lets that stock's non-whole `dpsF` pass `_factor_ok` and its non-whole events pass `_dvwhy_clean` (in "국내 dps3a = dps3 ÷
배율", the two "배당 맞춤 이유" rows and "되살린 배당수익률"). Every other non-whole factor fails exactly as before: a factor the
pipeline guesses from share counts (`div_basis` uses whole ratios only), an event that is not a bonus or has no `x` or r ≠ 1 + x, a
product off by more than 1e-6, a year this run's proof did not restore, or no `dvProof`. On the 11-14 data 6 of the 7 come back
(대한제강 3.73%, TJ미디어 5.73%, 폰드그룹 4.09%, 남성 4.18%, 알테오젠 0.16%, 가온전선 0.03%); 대동기어 does not: the rights part of its
유무상증자 is a 64% 주주배정, so the rights rule below holds it (with the rights line). The earlier bars of 10 more stocks come back by
the same rule (코리안리, 더블유게임즈, 풍산홀딩스, 헥토파이낸셜, 유비쿼스, 유아이엘, 링네트, 하이텍팜, 네오오토, 제너셈).

It does **not** restore (the stock stays exactly as before, with its reason in `divCheck.proof` and the run log):
- `ratio` — a filed ratio that is neither a whole split ratio nor an exact API bonus ratio (a split or merge filing with an odd par
  value ratio, a 감자 ratio); none on 2026-11-14;
- `basis` — a spin-off or stock-dividend decision in between;
- `rights` — a 주주배정 rights issue (주주배정후 실권주 일반공모 too, and any issue whose method is not stated) of more than 10%
  was decided from half a year before the report year-end to the price date: KRX lowers the price on the 권리락 day, so today's
  price is on the new basis while the filed dividend is on the old one. This is checked on every restore path (today and
  yearEnd, whether or not new shares were needed to explain the count) and for an earlier bar when such an issue falls between
  the two years. A rights decision whose method or size could not be read is a lookup failure (`fail`), never restored.
  Dividing by the 권리락 factor is a later PR. Since #PR (Jack, 2026-11-15, answer 11) the 2.0 app says why — "유상증자로 주가 기준이
  바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요." (`dvLine` 2) — only where it is literally true: a blocking decision is read as
  주주배정 and its new shares are already in today's listed count (listing comes after payment, so the 권리락 has passed; `sh`). A
  주주배정 whose new shares are not listed yet (`shnew`) or a decision whose method is unknown (`unk`) gets no line;
- `uncounted` — a filing explains the change but its share count is not read (주식교환, 합병, 감자, 주식소각);
- `data` — the stock's dividend table cannot be matched to its share counts. Since #PR (Jack, 2026-11-15, answer 13) the case is
  recorded (`divCheck.proofSub.data`) and only a real disagreement gets the line "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서
  배당수익률은 비워 두었어요." (`dvLine` 3): `div`, the cash dividend total ÷ the dividend per share is more than 3% off both the
  company's year-end outstanding common shares (주식의 총수 현황) and today's listed shares ÷ the factor (each of the 15 on 11-14 was read
  against the raw DART tables on 2026-11-15: interim dividends in the total, the total written in the per-share cell, a total that
  includes preferred shares the table gives no amount for, a share table in units of 1,000 …). Where the company's filings lack a
  piece the calculation needs, Jack's line of 2026-11-19 ("no blank without a reason") "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서
  배당수익률은 비워 두었어요." (`dvLine` 4): `nototal` (no total: 하림지주, 한신기계, HDC, 토니모리, 펌텍코리아), `nostk` (no readable
  year-end share table: 대신밸류리츠), `pref0` (a preferred dividend row while the share table lists no separate preferred count —
  voting preferred shares are written with the common ones: 메디톡스), `nopfo`, `prefmix`. No line only for `neg` (the total is smaller
  than the preferred share of it: a disagreement or our grouping of share classes) and `noshr` (no listed share count: not a company
  filing); 0 stocks. A dividend-table reason text the run has no name for (`prove_receiving` returned a text missing from
  `PROVE_DATA_WHY`) is recorded as `other`: no line (we do not know which one is true), a loud "!! 배당 표의 이름 없는 이유" log line
  with the count, and a gate warning. Fix: read the stock's dividend table, then give the new text its case in `PROVE_DATA_WHY`
  (both files' `PROVE_SUB` if it is a new case) — never map it to a line by guess;
- `fail` — a lookup failed (DART, the per-run limit, an unreadable filing, the share report not received): nothing changes and
  the next run tries again.

`line` gets Jack's line "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요." on the 2.0 배당 tile and
tab (`dvLine` 1; since #PR `rights` and `data` can carry their own lines above, 2 and 3, in the same two places, one line at most): the proof found the share count changed and no filing at all in between (no rights issue, bond, cancellation, exchange,
spin-off or stock dividend). That one place sets both `dvWhy` nc-unexplained and `dvLine: 1` (data.json); the app shows the
line only where `dvLine` is 1, so a `dvWhy` nc-unexplained from the older #98 check alone (which looks only at rights issues and
bonds, e.g. after a spin-off) never shows it, and the stock stays exactly as before. A restored stock carries `dvProof`
(data.json), including the share events (`ev`) its factor came from.
On the 2026-11-14 publish: 29 of the 72 hidden yields come back (21 with their bars), 23 of the 86 yields without bars get their
bars back; still hidden: ratio 7, basis 4, rights 7, uncounted 2, data 22, a 32.5% yield 1; line 0. With #PR on the same data: 35
of the 72 come back (+ the 6 exact bonus ratios), 31 of the 86 get all their bars back (+ 8); still hidden: ratio 0, basis 4, rights 8 (+ 대동기어),
uncounted 2, data 22, the 32.5% yield 1; lines: 1 → 0 stocks, 2 → 8, 3 → 15, 4 → 7 (every `rights` and `data` stock has a line).

- **DART calls:** about 4 per stock the first time (the filings lists, decisions, the year-end share report, rights and
  bond counts when needed), at most 150 companies a run (`PROVE_PER_RUN`, separate from `dvWhy`'s own 150); about 160
  stocks on 2026-11-14, so the first run does most of them (about 600 calls) and the next run the rest, then 0–10 a day.
  A cached lookup is fetched again when today's listed shares have moved more than 3% since it was fetched (a new decision may
  be missing), also when the `dvWhy` check used it earlier in the same run; an entry fetched without a share count is not
  fetched again for that reason. The run log line "배당 기준 증명 조회" gives companies fetched, read from cache and stopped by the limit, and the
  stage's own DART call count. Not a full-DART run; a full-DART run adds about 640 calls to its estimate (logged separately).
- **FAIL "배당 기준 증명 기록 (divCheck.proof)"**: the counts in `divCheck.proof` differ from the stocks' `dvProof`, a named
  stock does not exist, carries a proof, shows a yield (except `fail`, which can be an earlier year only), is in two lists,
  or is listed under `line` without `dvWhy` nc-unexplained; or `dvLine` is on a stock not listed under `line` (or missing
  from one that is). It is our own bookkeeping: look at the run's "배당 기준 증명" log lines. A publish without
  `divCheck.proof` after one that had it fails too, and so does a `dvProof` or `dvLine` without it.
- **FAIL "되살린 배당수익률 = 배당 총액 ÷ 시가총액 (dvProof)"**: a restored yield does not agree with the dividend total ÷
  market cap within what the recorded year-end treasury shares and filed new shares explain, a proof's numbers differ from
  corp.json `cash3` or today's share count, its events (`ev`) do not multiply to the factor or fall outside the report
  year-end to the price date, the published per-share dividend is not the filed one ÷ the factor (to the 전), or an earlier
  bar's factor does not match the two years' dividend totals. New shares are scaled by the proof's own events, not by
  `dvWhy` (which is absent when the events multiply to 1). The ratio is the pipeline's exact one (dividend total × factor ÷
  today's shares), not one recomputed from the rounded per-share dividend. For
  yearEnd the market-cap form restates the share-count inequality; the independent parts are the dividend total against the
  year-end outstanding shares and against corp.json. That is a wrong conversion; never loosen the row. The detail list under
  the table names each stock and the failing number.
- **WARN "배당 기준 증명 경고 (되살리지 않은 이유 · 조회 실패)"**: names the stocks not restored, by reason (with the `proofSub` case and
  whether it shows a line, since #PR).
- **"숨긴 배당수익률의 줄 (divCheck.proofSub · dvLine 2 · 3 · 4)"** — since #149 under Jack's standing rule (section "Checks on our own
  processing" above): the run blanks every line the record does not back (`ownDrop.divLine`) and publishes; the row fails only when
  more than 5 distinct stocks lose their line in the run (blanked, still wrong, or lost together with a missing or malformed `proofSub`,
  counted from the previous publish, all added up) or a line the record does not back is still in the file, and warns otherwise. The rules below are
  what "backed" means, and they are the whole rule for files without `ownDrop` (#142's FAIL as written).
  (since #PR): `divCheck.proofSub` is not v1 with exactly `rights`
  and `data`, its stocks differ from the proof's `rightsT` · `dataT`, a case is unknown, or the marks differ: `dvLine` 2 must be on
  exactly the `rights` stocks with case `sh`, `dvLine` 3 on exactly the `data` stocks with case `div`, `dvLine` 4 on exactly the `data`
  stocks with case `nototal` · `nostk` · `pref0` · `nopfo` · `prefmix` (`PROVE_SUB_LINE`); a `data` stock with case `other` carries no
  line, and any `other` turns the row into a WARN (see `data` above). Our own bookkeeping only: look at the run's
  "숨긴 배당수익률의 줄" and "그대로 숨김" log lines. A file without `proofSub` (before #PR) is only a warning unless the previous publish
  had it; without it a `dvLine` 2, 3 or 4 fails the "배당 기준 증명 기록" row.

## 오늘 볼 것 data (v19.6b, since #PR): disc.json `issue`, insider `role`, US `ed` · `xd`

What the daily run writes (`fetch_data.py` `fetch_issues`, `fill_issue_bd`, `insider_pos_role`, `us_event_dates`):
- **`issue`** — 유상증자 · 전환사채 · 신주인수권부사채 decisions of Korean stocks in our list, filed in the last 90 days, and
  유무상증자 (a rights issue and a bonus issue in one decision; Jack 2026-11-19, 7a). The run reads DART's 주요사항보고서 list
  (about 25 pages), then, for each (company, kind) with a filing it has not seen, DART's structured lookup (`piicDecsn` ·
  `cvbdIsDecsn` · `bdwtIsDecsn` · `pifricDecsn`, asked from 2015 so a correction of an old decision is found).
  DART gives one row per decision, under the filing number of its newest version; an attachment-only correction keeps the
  earlier number (corrections follow this DART record: Jack's yes 2026-11-19). A row is a decision whose filing number is in
  the 90-day list. Results are cached in the DART cache
  (`{filing number}|issue|v4`: decision row · older version · missing; v4 re-reads rows parsed before the same-class rule and the
  missing-is-not-zero rule), also in a full-DART run, and dropped when the filing
  leaves the window (keys of other versions are dropped too). At most 150 (company, kind) lookups a run (`ISSUE_PER_RUN`),
  newest first; the rest wait for the next run and their newest filings show as `pend: true` with blank numbers meanwhile
  (while a pair has such a filing, its filings the list marks "정" are left out, so an outdated number never shows as current).
  A filing the lookup does not return although it should is asked again the next KST day. Share counts and amounts are read
  only as whole numbers.
- **Rights-issue numbers (Jack 2026-11-19, 7b: same class)** — `n` is the new common shares when the decision issues common
  shares, else the new 기타주식 (`cls` says which: `common` · `other`); `p` is `n` ÷ the existing shares of that same class
  (육일씨엔에쓰 2026-08-26: 2,305,918 ÷ 11,204,255 common = 20.58 %). With no existing shares of that class (DART's "-": a
  first 기타주식 issue) `p` is null; a count field that is missing, blank or unreadable is never read as 0 — that ratio is null
  too, and the log counts the two reasons apart ("비율 없음: 증자 전 기타주식이 없어 … · … 읽지 못해 …", also for `p2`). When a decision issues both classes, `n` · `p` are the common shares and `n2` · `p2` the 기타주식 (those two
  keys only then). Every rights row has `cls` (null when unknown, withdrawn or pending).
- **유무상증자 (`bonus: true`)** — the row is `kind: "rights"` with `bonus: true`; `n` · `p` · `how` describe the paid part
  (`piic_` fields), the bonus part's numbers are not carried, and `bd` is DART's own board date (`fric_bddd`), window-checked
  like any rights board date. A withdrawal is marked `wd` like a rights issue.
- **Rights-issue board date (`bd`, Q18, Jack 2026-11-19)** — DART's 유상증자 lookup has no board-date field, so after
  `fetch_issues` the run reads it from each rights filing's own document (`fill_issue_bd`, `document.xml`): only the zip's main
  file `{filing number}.xml` (never an attachment), the table row "N. 이사회결의일(결정일)" in the filed form (a correction's
  before/after table is skipped), whose value DART writes as `<TU AUNIT="DRC_DT" AUNITVALUE="YYYYMMDD">`; the cell must be one
  whole, real date and the coded value must say the same day. Withdrawn (`wd`) and pending (`pend`) rows are not read.
  - Cache: `{filing number}|issuebd|v2`, also in a full-DART run, dropped when the filing leaves the 90 days. It keeps the date
    the document gives, or "unreadable" with the reason (no date in the form, or no main file in the zip). A filing is read
    once ever; an unreadable-but-delivered document is not read again.
  - Window: `fill_issue_bd` uses the date only when it is not more than `ISSUE_BD_MAX_YEARS` (1; Jack's yes, 11-19, 7d) before
    the filing date. This is checked each time the cached date is used, so changing the limit needs no re-read. A date outside
    it leaves `bd` null and is logged separately ("!! 결의일이 공시일보다 1년 넘게 앞이라 비운 유상증자 공시 …", 8–10 a run in
    the 11-19 dry runs), apart from unreadable documents ("!! 결의일을 못 읽은 유상증자 공시 …"). These window blanks do not
    count toward the gate's N; the gate only warns about blank board dates, every day they are there. A date after the filing
    date is not handled here: it passes through and the shared step before writing (`own_check_disc`, below) blanks it and
    counts it in `ownDrop.issueBd`.
  - Retried next run (not cached): a failed or slow fetch, an empty zip, a main file that is empty or won't decode, a parser
    crash, the per-run limit (100 documents, `ISSUE_BD_PER_RUN`, newest first) and the time limit (180 s,
    `ISSUE_BD_SECONDS`). None of this stops the run or changes `issueOk`. On a day the list failed (`issueOk` false) nothing
    is read and last run's rows keep their dates.
  - Log: "유상증자 이사회 결의일(공시 원문 document.xml): 문서에서 읽음 a / 대상 b, 못 읽음 c, 기간 밖이라 비움 l, 다음 실행으로 d".
- **Withdrawals (`wd: true`, kept: Jack's yes 2026-11-19)**: DART files a withdrawal as a `[기재정정]` whose number fields are all "-" (the list never marks
  it "철" and the name has no "철회": 더코디 2026-11-05 "납입금미납으로 유상증자철회", 크라우드웍스 2026-08-21, 쏘닉스 CB 2026-11-10).
  Such a row stays, marked `wd: true` with every number blank, so the cards can skip it; the original filing is an older version
  and has no row. The run log names them ("!! 주요사항 공시 철회 …").
- **DART stops in this phase** (daily limit 020, key errors): last run's rows stay with `issueOk` false and the run goes on
  (no screen reads `issue` yet). The 지분공시 phase before it still stops the run, as before.
- **insider `role`** — 임원 when the filing names a position or 등기/비등기임원, 주요주주 when it names only a major-holder
  relation, 임원·주요주주 (exactly that text; Jack 2026-11-19, 7c) when it names both, else null. No screen reads `role` yet. DART's "-" means empty (it used to show as a position). Rows from earlier runs are fixed from the same
  day's lookup of that company; a row the run could not look up again keeps `role` null. A major holder's position is DART's
  own relation word (10%이상주주, 사실상지배주주; Jack's yes 2026-11-19); `fetch_data.INSIDER_POS_HOLDER_WORDS = False` blanks it
  instead (one line). The run log counts the words ("주요주주 줄의 직위 …").
- **US `ed` · `xd`** — from the Yahoo details the run already caches (3 days): `ed` only when Yahoo says the earnings date is not
  an estimate and it is one day; `xd` is Yahoo's ex-dividend date (midnight UTC, read as that date). Either can be in the past.

Gate rows (`validate_data.py` `check_v196b` and `check_issue_bd`), under **Jack's standing rule (2026-11-19 ~17:45 KST)**:
"Standing rule for checks on our own processing: a single bad row is dropped or blanked with a loud warning and the rest
publishes. Block only when many rows fail in one run (set the number from recent runs and show it in the PR) or when a value
would show a wrong number."

How it works for these four checks: the bad rows are picked by one function each in `validate_data.py` (`issue_bad_rows`,
`issue_bd_bad_rows`, `insider_bad_rows`, `us_date_bad_rows`). The pipeline runs the same function just before writing the file
(`fetch_data.own_check_disc` before disc.json, `own_us_dates` before data.json), drops the row or blanks the value, logs it
("!! {check}: n건 빼고 발행 / 비움 — rows (reason)", or a "·" line with 0), and records it in that file's
`ownDrop[key] = {"n": count, "rows": [[name, reason]] first 30}` (written on clean runs too, as 0). The gate reads the record
and runs the same function on the file:
- **FAIL** when this run dropped or blanked more than N rows (N = 5 for each check: the PR #145 table, 25 data-branch publishes
  and 5 branch dry runs, all 0 → max(5, 3 × 0)), or when a bad value is still in the file and would show a wrong number (the
  drop step failed).
- **WARN** (naming the rows) when 1..N rows were dropped or blanked, or a remaining bad value shows no number.
- **PASS** when 0. A file without the record (from before #PR) keeps the old rule of each row: a bad row fails. A file whose
  `ownDrop` is not an object, or whose record has the wrong shape, also keeps the old rule, plus a warning (as #149 does).
- The rule is about single rows. A whole section is never replaced: an `insider` that is not a list is left as it is and
  logged with "!!", so the gate fails (an empty list would make the 공시 tab show "no reports" as live data). An `issue` that is
  not a list is written as an empty list with `issueOk` false, the same as a day the list failed (the app shows its failed
  state; the gate warns; no screen reads `issue` yet).

| Row (key) | Bad row | Pipeline | Remaining value FAILs? |
|---|---|---|---|
| 주요사항 공시 (`disc.json` `issueShape`) | a malformed `issue` row (missing or wrong field, date outside the 90 days, method or share count on a bond, amount on a rights issue, non-positive number, a `wd` / `pend` / `cor` mark that is not true/false or a number on a `wd` / `pend` row, `cls` / `n2` / `p2` / `bonus` out of place), or a filing number that appears more than once (every copy) | drops the row (its numbers can't be trusted; no card is better than a wrong one) | yes for dates, numbers and the marks that change how numbers read (`d`, `bd`, `n`, `p`, `amt`, `n2`, `p2`, `kind`, `cls`, `bonus`, `wd`, `pend`); yes for a filing number that appears more than once (two rows could carry different numbers); no for filing number, ticker, name, method, correction mark. A non-boolean `issueOk` only warns (no screen reads `issue` yet) |
| 유상증자 이사회 결의일 (`disc.json` `issueBd`) | a rights row (not `wd`, not `pend`) whose board date is after its filing date (bonds' DART board dates are not checked for this: a known gap, as before) | blanks `bd` (the rest of the row came from DART's lookup; only our reading of the date is wrong). `fill_issue_bd` now applies only the one-year window (Jack, 11-19, 7d) and leaves "after the filing date" to this check, so a run that misreads many dates is caught by N | yes (the date labels the decision's numbers) |
| 임원 · 주요주주 역할 (`disc.json` `insiderRole`) | a `role` other than 임원, 주요주주, 임원·주요주주 or null; a row that is not an object | blanks `role` (the trade's numbers are right; the role is a title word) · drops a non-object row | yes for a non-object row (the old app reads fields of every row and throws on one that isn't an object: `src/disc.jsx` `x.s`, `src/corp.jsx` `x.t`; 2.0 reads its share count and amount); no for a bad role (no screen reads `role` yet). `insider` not a list still fails (left as it is, see above) |
| 미국 일정 (`data.json` `usDates`) | an `ed` / `xd` that is not a real YYYY-MM-DD, or one on a stock that is not American | blanks that field only; the stock row stays (prices and dividends are right; dropping a stock would break other checks such as the v19.1i dividend proof lists) | no (event dates, not dates that label a number) |

Other WARNs, unchanged: no `issue` section (a file from before #PR, e.g. the live site right after the merge), `issueOk` false
(the list failed and last run's rows were kept), 0 rows, a row whose stock left today's list, a ratio (`p` or `p2`) above
3,000 % (check the filing; STX's 1,855.66 % on 2026-10-14 is real), more than 10 % of rows without any number (normal on the
first run after the merge), rights rows with a blank board date, insider rows without `role` or with "-" as the position, no US
dates at all among more than 100 US stocks, a US date more than 400 days ahead. **SKIP** "유상증자 이사회 결의일" when there is
no `issue` section.

DART calls: the first run after the merge (no cached lookups) makes about 25 list calls, 150 lookups and up to 100 rights
documents; the next run the remaining ~75 lookups and ~60–70 documents (about 160 rights rows in 90 days on 2026-11-16); then
about 25 list calls, 10–20 lookups and 3–5 documents a run. A full-DART run with an empty cache adds up to about 275 calls
(logged separately from the pinned estimate).

## 이번 주 정리 data (v19.6e, since #170): data.json `c1w`, `wkFrom`, `usWkFrom`

What the daily run writes (`fetch_data.py`: `kr_week_closes` in `fetch_korea`, `us_week_start` · `us_c1w_add` · `us_c1w_finish` in
`fetch_us`, `fund_c1w` in `fetch_bonds` · `fetch_kr_funds`, then `c1w_step` in `main`, after every step that drops rows and before
the file is written). No new downloads and no DART calls.
- **The week.** A market's current week is Monday–Sunday of the week holding its price date (`pxDate` for Korea, `usPxDate` for
  the US). The week-start date is the last trading day before that Monday in the market's index bars (KOSPI, S&P 500): a Friday
  holiday makes it Thursday, a Monday price date makes it the Friday before. `wkFrom` and `usWkFrom` are those dates.
  **Which date a row uses (for the screen):** `usWkFrom` when `cls` is `us` and the row is not a `fund`; `wkFrom` for every other row
  (Korean stocks, bonds, ETFs, gold, and Korean-listed funds such as 379800 even though their `cls` is `us`).
- **Checks on the date** (any failure writes that market's date blank and blanks every `c1w` of that market, because a wrong week
  start would show a wrong weekly move): the date is a holiday in `data/market_holidays.csv`, or a weekday between it and the Monday
  is a trading day the index bars left out; it is more than 12 days (`C1W_FROM_MAX_DAYS`) before the price date; for Korea, a final
  listing file exists for a day between it and the Monday; for the US, more than 10 stocks (`C1W_US_BARS_MAX`) have a bar between it
  and the Monday (this catches a missing ^GSPC bar even on a day the holiday table cannot be read).
- **`c1w`** — each row's actual close on that date, price only in both markets (owner's rule: never mix units or markets):
  - Korean stocks: the official close (market cap ÷ listed shares) in that day's final listing file (`kr_recent_sessions`: the
    commit after the close + 30 minutes, or the two-source rows of a backup day; the log says which). The file is never an intraday
    or pre-market one, so the week-start close is never a partial bar. When that file is missing, `wkFrom` is still written and
    Korean `c1w` are all blank ("그날 최종본 목록 파일이 없음" in the log).
  - US stocks: the bar of that date in the same Yahoo series `price` uses. That series is Yahoo's adjusted close (yfinance 1.7.0,
    `auto_adjust=True`, no repair: the chart API's `adjclose`), which lowers every bar before an ex-dividend date by
    m = 1 − D ÷ (actual close of the trading day before). When ex-dates fall inside the week, the run undoes them from the download's
    `Dividends` column, latest first: with A = the adjusted close of the trading day before the ex-date (divided first by the later
    m's), m = A ÷ (A + D), and `c1w` = adjusted value ÷ Π m (`us_c1w_close`). So `price ÷ c1w − 1` is the price move only, as in
    Korea, and a dividend the user records in 받은 배당 is not counted twice. A present US `c1w` is on today's share basis (there is no
    split between it and today; see below).
  - Bonds, ETFs and gold: the bar of `wkFrom` in the series their `price` comes from (FinanceDataReader's Naver daily bars and the
    KRX gold market — not Yahoo's adjusted series). Gold priced from the world gold price (`est`) has no `c1w`.
- **Blank (no `c1w` key)** when:
  - the row is shown at its own older date (`pxd`, `pxc`: last confirmed close or halted; and `est` gold) — `price ÷ c1w − 1`
    would then be a move up to that row's own date, not the week, so the screen leaves the stock out and names it (Part E);
  - the series or that day's listing has no row for that date (new listings; an earlier day is never used);
  - Korea: the KRX base-price link from that day to the price date is not confirmed "ok" for every day of the week. A link is
    "ok" when that day's KRX base price (`Close − Changes`) is within 1 won of the previous trading day's close. Between final listing
    files this is `kr_ref_links`; "break" means KRX reset the base price (split, merge, capital reduction, 권리락, 무상증자, a KONEX
    base move on a no-trade day). This is stricter than the spec on purpose: in a 무상증자 the price drops on the 권리락 day while the
    new shares list weeks later, so the share-count rule alone would show a fake −54% (the same case `pin_why_not` already guards,
    코나아이 1.5×). **Days without a final listing file** (backup-source days, the volunteer cache only committed intraday — 3 of 5
    days in the week of 11-16; the first dry run had 0 / 2,474 Korean `c1w`) are checked one by one from other evidence
    (`kr_c1w_rescue`, run in `fetch_korea` after the price phase):
    - **A, KRX base day by day (`krx`, exact).** The day's base price from that day's non-final cache file (`kr_recent_sessions`
      now hands those files over, only when committed at or after that day's open — 09:00, or the special-session table's start such as
      10:00 on the CSAT day — and never when the commit time is unknown, because a pre-open file can still carry the previous day's
      values; KRX fixes the base before the open, so an intraday file has the right one — checked on the real 11-17 file: 13 / 13 equal
      the 11-16 official close), a final file, or the last backup run's Daum rows (`.dart-cache/kr-fb-v1.json`, close − change, used
      only when `prevClosingPrice` > 0 and close − change equals it: a halted stock's Daum row carries `prevClosingPrice` 0 and
      `changePrice` 0 as filler, STX 011810); the previous close from a final file, the previous publish (its `pxDate`), or the Daum
      cache when Daum and Yahoo agree to the won. Sources that disagree → blank (`conflict`); when a day's close and base are both known,
      their ratio must be inside the daily price limit (30%, KONEX 15%), else that day is a conflict too. Any reset seen → blank
      (counted as a base reset). A stock is rescued by A only when every day of the week settles this way.
      **Why A settled 0 stocks in the 11-16 week (dry run 44998856207):** the closes of 11-17 and 11-18 existed nowhere in that run
      (no final file, the previous publish was 11-19, and the Daum file did not exist yet: it came with #161 on 11-21), so the 11-18
      and 11-19 links could not be checked exactly. The next item supplies them.
    - **A with our own publishes (`pub`, Jack 2026-11-22: "take a Korean stock's last week's close from our own published data for
      that day … Use Naver only for a stock missing from our own data … Leave a stock out only if neither exists").** Only in a week
      with a day that has no final listing file (`c1w_pub_need`: the week-start day itself, or a day in between — a normal week reads
      nothing and logs "읽지 않아요"), `c1w_pub_step` reads the `data` branch history: per price date (`pxDate`) the **latest**
      publish of that day, rows of Korean stocks without `pxd`, only publishes whose price source is an official close list (a final
      file, or Daum × Yahoo equal to the won — every close published since the outage; the same rule as `kr_prev_pub_closes`, #161).
      Those closes become "the previous trading day's close" of path A.
      - **No-trade rows** (`noTrade`, e.g. 금양 001570 halted all week at 9,900): a no-trade day's official close equals that day's
        KRX base, so it is used for the day-by-day link checks only, never as the week-start `c1w` value (`c1w_pub_rows` keeps them
        apart as `nt`). Without this the 11-16 week lost 41 halted stocks that round 4 had kept via Naver.
      - **Rolled-back publishes:** the bad-data rollback below is a revert commit on `data`. Reading newest → oldest, once a publish
        with an earlier price date has appeared, an older commit with a later price date was rolled back and is never used (logged
        "되돌린 발행본이라 쓰지 않음 sha (date)"); that day then counts as having no publish.
      - **A day with no publish at all** (11-17: nothing was published with that price date) is covered by the next trading day's
        publish: its `d1` (that day's close ÷ the previous close − 1, rounded to 0.01%) gives the previous close to within ±0.005
        percentage points (`C1W_PUB_D1_HALF`) plus 1 won, and the next day's KRX base must fall inside that range ("ok"), else it is
        a reset ("break" → blank). Checked on the real 11-18 publish: the 11-18 intraday base of 2,431 / 2,431 stocks with a `d1` is
        inside the range (삼성전자: range 190,295–190,313, base 190,300). **Blind spot:** a reset smaller than the range — 0.01% or
        1–2 won, whichever is larger — would pass, and the weekly move of that stock would be off by that much. When a close of that
        day is also known from a final file or the Daum file, it must sit inside the range too (else `conflict`).
      - **Is that `d1` against the previous close, not the reset base? (reviewer S4 — verified offline on one real case.)** The 11-17
        close behind the 11-18 publish's `d1` came from Daum × Yahoo during the outage. Yahoo rewrites past closes after a split or
        merge; if Daum's daily bars did too, both could agree on an adjusted close and `d1` would be measured against the new base,
        hiding the reset. The real Daum response in `tests/fixtures/kr_two_source/daum_days.json` (fetched around 11-19, after
        유니온머티리얼 047400's 5:1 merge on 11-16) shows the bars before the merge unchanged at 746 won (and the old share count
        42,000,000), while Yahoo shows 3,730 for the same days. So Daum's past bars are **not** rewritten for a merge, the two sources
        then disagree, and that day is simply not confirmed (the stock drops out of that backup day) — the two-source rule fails
        safe. Not verified: other kinds of reset (rights issues, bonus issues, splits) in Daum's history; no such case is in the
        fixtures and checking it needs a live Daum call. The same fact underlies PR #170's use of the Daum file's closes.
      - A stock rescued this way is counted as `pub` (at least one day's previous close came only from our publishes) — exact, no
        `c1wv`. If the week-start day has no final file, that day's publish gives `c1w` itself and the [Q9] share count
        (`kr_week_closes(..., pub=)`, source "지난 발행본"); every link is then checked by A from that close. When it cannot (no
        publish of that day, the publish is unusable, or the history could not be read), all Korean `c1w` stay blank and the first
        `c1w` log line says which ("그날 지난 발행본도 없음" · "그날 지난 발행본은 쓸 수 없음 (가격 출처)" · "지난 발행본을 읽지 못함").
      - **Conflict rule:** a published close (or `d1` range) that differs by more than 1 won from a final listing file of the same day
        blanks that stock — every Korean stock, also those linked between final files (`c1w_pub_diff` → `pubDiff`, logged with "!!").
      - **How it is read (cost):** a throw-away bare repo in the runner's temp folder (the checkout's `.git` is never touched; removed
        afterwards), `git fetch --no-tags --filter=blob:none --depth=150` of `data` (commits and trees only, a few hundred KB), then
        `data.json` only for the commits needed, newest first (one file ≈ 0.5 MB downloaded, 2.7 MB unpacked — the log shows the
        unpacked total, "data.json 풀어서 21.6MB" ≈ 4 MB downloaded), stopping when every day from the week start to the day before the
        price date is found, or a publish older than every missing day appears (publishes go in date order), or the commit date is
        before the week start, or 80 publishes were read (`C1W_PUB_MAX_READ`; the log says so with "!!" when that cap stops the read
        with days still missing). The address is `GITHUB_SERVER_URL/GITHUB_REPOSITORY` (https), else the checkout's origin when it is
        an https or file address (never ssh). The repo is public, so no token is used (as `already_published.py`). Git runs with a
        minimal environment (PATH, HOME, LANG, LC_ALL, TMPDIR, proxy and CA-file settings only — no API keys, no `GIT_DIR`,
        `GIT_WORK_TREE`, `GIT_INDEX_FILE` or `GIT_CONFIG_*`), `GIT_TERMINAL_PROMPT=0`, empty `GIT_ASKPASS`, `-c credential.helper=`,
        `-c core.askPass=`, empty stdin, and `-c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30` (git gives up by itself after 30
        seconds under 1 KB/s). Dry run 45022241453 (11-22): 4.3 s.
      - **Fail-safe — exactly what happens:**
        - *Time:* one deadline for the whole read, 180 s (`C1W_PUB_DEADLINE`), checked before every git call; each call may take at
          most 120 s (`C1W_PUB_TIMEOUT`) or what is left of the 180 s, whichever is shorter. When a call runs over, its whole process
          group is killed (no `git-remote-https` left behind) and **the whole read stops there** — no further publish is tried. The
          log says "!! c1w 지난 발행본 (data 브랜치) 을 읽지 못했어요 — 시간 초과 — 거기서 멈춤 (git cat-file 이 Ns 안에 끝나지 않음 …)",
          naming the git step (fetch, log, ls-tree or cat-file), or "전체 180s 를 넘어 git … 앞에서 멈춤". The morning run is
          delayed by at most about 3 minutes.
        - *Any other failure of the read* (no usable address, fetch refused, `git log` failing, any exception): the same "!!" line
          with the reason, and **nothing from the history is used**: the later steps run exactly as in round 4 (only the previous
          publish, intraday files, the Daum file and Naver; `c1wSrc.pub` is 0; no `pubDiff`). The same happens when the read worked
          but found no publish in the week (tested: a failed read gives the same `c1w`, `c1wv`, rescue and counts as round 4).
        - *One broken or unreadable publish* (bad JSON, a download error that is not a timeout): that publish is skipped and named
          ("!! 읽지 못한 발행본 sha (…)"); the read goes on with the next commit. Its day then counts as having no publish.
        - Nothing in this step can stop the run or the publish.
      - **The 11-16 week with this (real files, real publishes, real Naver bars, price date 11-20, simulated):** Korean `c1w` 2,405 /
        2,474 (97.2%): `pub` 2,363 (exact) and Naver 42 (the halted stocks and a few missing from one publish, tagged `c1wv: "nv"`);
        blank 69: the price date's link unknown 62 (stocks missing from the 11-19 publish — Daum and Yahoo disagreed, no Yahoo
        close, KONEX), Naver basis more than 1% off 3, share count 3, a reset 1 (유니온머티리얼 5:1 merge). Dry run 45022241453
        (before the no-trade change): 2,366 (`pub` 2,363 · Naver 3).
      - **Why the 62 stay blank (`pxLink`, kept on purpose):** Naver is never trusted for the newest day — its last bar can lag a day
        or carry after-hours trades — so the price date's own link must be settled by A. A stock that is not in the publish of the day
        before the price date has no confirmed close for that day, so its link to the price date cannot be checked and it is left out.
    - **B, Naver adjusted series (`naver`), only for days A could not settle — and, when our publishes were read, only for a stock
      whose previous close of such a day is missing from every source (missing from our own publishes); a stock whose closes are all
      known but whose KRX base of a day is missing is blanked (`noBase`) without asking Naver.** Naver rewrites every bar before a reset onto the new
      basis. So: the median of Naver ÷ official close over the 5–10 linked days up to the last settled day (G0) must be within 1%
      (`C1W_NV_TOL`; real 2026-11-14 samples: normal stocks 0.0–0.7%, single days up to ±3% from after-hours trades, which is why it
      is a median); Naver must have a bar on every day after G0, no Naver day move beyond the price limit (30%, KONEX 15%: a large reset
      Naver has not applied yet), every unsettled day must have a KRX base from an intraday file or the Daum cache, within 5%
      (`PIN_PX_TOL`) of Naver's previous bar (a smaller reset Naver has not applied yet), and the price date's own link must be
      settled by A (Naver could lag on the newest day). Any missing piece → blank, with its reason.
    - **What can still slip through (rescued `naver` rows only — rare):** a reset Naver has applied that moves the basis by about 2%
      or less (1% plus the median's after-hours wobble), or one Naver has not applied yet of at most about 5% **plus that day's
      after-hours difference**: the `near` check compares the day's KRX base with Naver's previous bar, which is the last trade
      including after-hours (NXT and KRX single-price sessions), not the official close. Usually that difference is under 3%, but on
      a day with a big after-hours move it can be larger, and a reset of that size in the same direction would pass (reviewer probe
      `rev_a2_exp1`: an 8% reset with Naver's previous bar 4% under the official close is kept, −18.2% instead of about −11%). These
      are typically small 주주배정 rights issues or stock dividends on a day without a final file; the weekly move of that stock is
      then off by that much. Rows rescued by A carry no such error. Comparing with an official close instead of Naver's bar is path
      A, which needs exactly the closes that are missing. **Every row rescued by B carries `c1wv: "nv"`** (absent otherwise), so the
      screen can decide whether to use, footnote or leave out those rows (owner's decision in the screens PR).
    - **Known false blanks (lower coverage, never a wrong value):** a week whose start day has neither a final listing file nor a
      usable publish of its own (all Korean `c1w` blank; the log says why: "그날 지난 발행본도 없음" · "… 쓸 수 없음" · "… 읽지 못함"); a
      stock missing from the publish of
      the day before the price date (the price date's link stays unknown, `pxLink` — Naver is not used for the newest day); a stock with a base reset in the few days before the last settled day
      (fewer than 5 linked days to compare with Naver, `few`); a stock not in the previous publish when the price date's link is
      unknown (`pxLink`); a single after-hours day more than 5% away (`near`) or a median more than 1% away (`adj`) without any reset.
      In the 11-16 week (dry run 44998856207): Korean `c1w` 2,069 / 2,474 (83.6%), all rescued by Naver; blank 405: adj 236 · near
      98 · pxLink 62 · move 5 · base reset 1 · share count 3. Real cases blanked in the tests: 코나아이 1.5× bonus, 엘앤씨바이오 1:1 bonus, CMG제약 10:1
      merge, DGI 권리락, 유니온머티리얼 5:1 merge, and the reviewers' 000660 권리락 probes;
  - Korea, [Q9]: the listed share count changed by more than 20% between that day's file and today (`C1W_SHR_PCT`; exactly 20% is
    kept; an unknown count also blanks). That day's count is used inside the run only and is not written to data.json;
  - US: a split dated after the week start and up to the price date (the download's `Stock Splits` column, any non-zero value
    including spin-off adjustments, or a row of the published `splits`);
  - US: an ex-dividend inside the week that cannot be undone: the `Dividends` column unreadable, a blank or infinite value on a day
    with a price bar, a negative value, an ex-dividend or a capital-gains distribution after the price date in the download, a
    fund's capital-gains distribution that week, no bar on the trading day before the ex-date, or a dividend on a day (from the week
    start to the price date) whose next US trading day has no bar for that stock (yfinance 1.7.0 `safe_merge_dfs` moves a dividend
    whose ex-date has no bar onto the previous bar, so it could sit on the week start and look outside the week).
- **Log** (every run; "!!" when a market's week date or listing file could not be used, fewer than 95% of the rows priced at the
  market's date have `c1w`, a bond/ETF/gold row lacks one, any Korean row was blanked for an unconfirmed link, or a US dividend could
  not be undone). The counts use the same denominator as the 95% rule and the gate (rows priced at the market's date); rows at their
  own date are named separately:
  - "c1w (이번 주 정리 · 그 시장의 이번 주 앞 마지막 거래일 종가 · 기준일 종가 종목 중): 국내 k / n (wkFrom … · 최종본 목록 파일 | 2차 출처
    행 (두 출처로 확인한 n종목) · 자기 가격 날짜 x종목은 빼고) · 미국 k / n (usWkFrom … · 야후 일봉 · 실제 종가 기준 …) · 채권·ETF·금 k / n"
  - "c1w 국내 빈 칸 b: {reason} {count} · …" (one line per market with blanks)
  - "c1w 주식 수 20% 넘게 바뀌어 비움: n / N — code name (then → now주) …"
  - "c1w KRX 기준가가 그 사이 새로 정해져 비움 (분할 · 병합 · 감자 · 권리락 · 무상증자 · 코넥스 기준가 조정 등): n / N — …"
  - "c1w 기준가 연결을 목록 파일끼리 확인 못 함 n / N (그 사이 최종본 목록 파일이 없는 거래일: …) — 다른 자료로 확인해 실음 r (KRX 기준가로 날마다 a ·
    네이버 수정주가로 b) · 다른 자료로 본 기준가 재설정 x · 비움 k (reason counts) — code name (reason) …"
  - "c1w 기준가 연결 자료: 장중 목록 파일 … · 지난 발행본 … · 다음 보관본 … · 네이버 일봉 n종목 — 실은 종목 (예): code name (how) …" (only when n > 0;
    with our publishes read, "지난 발행본" lists every publish day used)
  - 5차, right after the week-start line of the price phase: "c1w 지난 발행본: 읽지 않아요 (그 주 날마다 최종본 목록 파일이 있어요)" in a
    normal week, else "c1w 지난 발행본 (data 브랜치 · 기준일마다 그날의 마지막 발행본 · {why}: days): 2026-11-13 db341a0 2,407종목 · 거래 없음 66
    · 2026-11-17 발행본 없음 (다음 거래일 발행본의 등락률로 그날 종가 범위 2,431종목) · … — 커밋 28개 · 읽은 발행본 8개 (data.json 풀어서 21.6MB
    · 5.8s · {why it stopped})" ("!!" when a day without a final file has neither its own publish nor a next-day range, when the
    week-start day needed for `c1w` has no publish, when a publish could not be read, or when the 80-publish cap stopped the read with
    days still missing; rolled-back publishes are named); "!! c1w 지난 발행본 (data 브랜치) 을 읽지 못했어요 — {reason} … → 오늘 받은
    자료만으로 확인해요 (4차 그대로 …)" on failure. Whenever the run could look at publishes, the link line adds "지난 발행본 종가와 KRX 기준가로
    p"; when publishes were read and used, one more line: "c1w 지난 발행본 종가 ↔ 같은 날 최종본 목록 파일: 다른 종목 n (비움) — code name (day
    발행 v · 파일 w)" ("!!" when n > 0).
- **`c1wv`** (Korean rows only): `"nv"` when that row's `c1w` was confirmed by path B (Naver); absent for rows confirmed between final
  files or by path A. **`c1wSrc`** (meta, Korean stocks): `{v: 1, listing, krx, pub, naver, blank: {reason: n}, link: {reason: n}}` —
  `listing` + `krx` + `pub` + `naver` = Korean rows with `c1w` (by how the base link was confirmed; `pub` = path A that needed our own
  publishes, present whenever the run could look at them — 0 in a normal week; `naver` = rows with `c1wv`), `blank`
  counts the Korean rows without `c1w` by the log's reasons (week, own, none, base, link, shr, bad), `link` splits `blank.link` by
  path-B reason (conflict, pxLink, noNaver, stale, move, noBase, near, few, adj, none, rows, err, and `pubDiff`: a published close
  differs from the final file of that day). Blank (`null`) when the step crashed.
  - "c1w 미국 그 주 배당락: 실제 종가로 되돌림 n (…) · 되돌리지 못해 비움 k (ticker reason …) · 그 주 분할로 비움 s (…)"
  The last four are printed every run, also with 0. If this step crashes, every `c1w` is removed, both dates are written blank, the
  run logs "!! c1w 단계가 오류로 멈췄어요" and publishes as usual. A crash while collecting one US stock's or one fund's week-start
  close leaves that row and its other fields untouched (logged, first three named).

Gate row **이번 주 시작 종가 (c1w · wkFrom · usWkFrom · 경고만)** (`validate_data.check_v196e`, after the v19.6b rows). It only
**warns**, in every mode (Jack's yes is needed before any of it may stop a publish; to be asked with the screens PR), and a crash of
the check itself is a warning too. The Korean part of its value shows how the rows were confirmed, e.g. "국내 2,366 / 2,474 (wkFrom
2026-11-13 · 목록 0 · KRX 0 · 지난 발행본 2,363 · 네이버 3)" (dry run 45022241453) ("지난 발행본" only when `c1wSrc` has `pub`). It warns when: `c1wSrc` is
missing, malformed (also a non-integer `pub`), or its counts disagree with the rows (`listing` + `krx` + `pub` + `naver` ≠ Korean
`c1w` rows, or `naver` ≠ rows with `c1wv`); a `c1wv` is anything but `"nv"` next to a Korean
`c1w`; the file has none of the three fields (a file from before #170, e.g. the live site
right after the merge); `wkFrom` / `usWkFrom` is missing, blank, not a real date, not before the Monday of the price date's week,
more than 12 days before the price date, on a weekend, or different from the gate's own count from the holiday table (read by its own
loader) or from `macro.json` `idxHist`; the holiday table cannot be read; a `c1w` is not a positive finite number, sits on a row shown
at its own date, or has no market date; fewer than 95% (`C1W_COVER_MIN`) of the Korean or US rows priced at the market's date have
`c1w`; a bond/ETF/gold row lacks it; a US, bond, ETF or gold `price ÷ c1w` is outside 0.5–2.0 (`C1W_RATIO_BAND`: down by more than
half or up by more than double in a week — it can be real; the row names the stocks to check); a Korean ratio is outside the daily
price limit compounded over the week's trading days (30%, KONEX 15%). Outside that limit usually means a base reset the blanking
missed; the exception is a 정리매매 (delisting liquidation) week, which has no limit. A Korean ratio outside 0.5–2.0 but inside the
compounded limit is only named in the value, without a warning (real theme-stock moves happen a few times a month; they should not
raise the morning alarm). When `idxHist` KOSPI or SP500 is missing or malformed, the value says which cross-checks were skipped, and a
Korean ratio outside 0.5–2.0 then warns (the limit is unknown).
The gate cannot see the base-price link itself (data.json carries only counts in `krSeries.ref`), so a Korean row the pipeline
should have blanked for an unconfirmed link is caught by the gate only if its move breaks the compounded limit.

## US stocks added by hand (EXTRA_US)

The US list is the S&P 500 (FinanceDataReader's list), Nasdaq's first 400 and `EXTRA_US` in `fetch_data.py`, every ticker in
Yahoo's form (`us_symbol`; see "US share-class tickers" below). On
2026-11-14 28 companies were added (Jack, 11-13 "Missing US stocks"; `EXTRA_US_ADDED`): BTI, ADC, NNN (Jack's names); MAIN,
WPC, STAG, EPR, OHI, ENB, BCE, TD, RY (widely held dividend stocks outside both lists); SHEL, BP, UL, TM, SONY, AZN, HSBC,
SAP, NVS, RIO, BHP, TTE, DEO, BUD, SAN, GSK (foreign companies listed in New York). SEIBro's ranking of Korean investors'
US holdings could not be read here (its page fills the table through the site's own internal calls; its open API needs a
key and was not reachable), so the list follows Jack's fallback. Left out on purpose: BNS (Yahoo's short name is "Bank Nova
Scotia Halifax Pfd 3", which the preferred-share rule drops), EPD and ET (publicly traded partnerships: a non-US seller
has 10% of the sale proceeds withheld, and several Korean brokers restricted buying them in 2023).

**To add a US stock** (one small PR):
1. `EXTRA_US_ADDED` (or `EXTRA_US`), and `US_NOT_ETF` or `US_ETFS` (the run refuses to start if a ticker has no ETF decision).
2. A foreign company (ADR or foreign ordinary share): nothing to add since #PR — the daily rule finds it (statement currency,
   or headquarters outside the US for a company outside the S&P 500; see "Which companies count as foreign" below). Check its
   Yahoo `country` once. `US_FOREIGN` stays the 21 of #126 (a floor, and pinned by a test).
3. The gate's own copy in `validate_data.py`: `US_ADDED_SET` (or `US_ETF_SET`). The tests check that the two files agree.
4. Its splits since 2016: read Yahoo's split column once (yfinance `download(..., start="2016-01-01", actions=True)`), keep
   only clean ratios, check each against the company's own announcement, and add the rows and the ticker to
   `data/us_splits_seed_more.csv` and its codes file (never to the first seed). Otherwise the daily run reads the history
   itself, 20 stocks a run, and warns (`gap`) until it is done. The gate warns once ("새 줄 정수 아닌 배율") for a seed row
   whose ratio is not a whole number or its inverse (GSK 4:5 on the first publish after 2026-11-14).
5. Check Yahoo's names (`shortName`, `longName`) against the preferred-share rule (`us_preferred_reason`), and its
   industry against `data/industry_us.csv` (an industry not in the table means no 업종 group; the run log names it).
6. Since #169 (Jack, 2026-11-22) a newly added stock joins on the first run where Yahoo has its close for the US date: until
   then it waits (`usSrc.newWait`) and `usExtraMissing` gives "새로 들어온 종목 · 확인된 종가를 기다려요 (…)", so the gate row
   below warns ("US stocks at their last confirmed close", "New tickers wait for a confirmed close").

**Gate row "손으로 더한 미국 종목 (EXTRA_US): 목록에 있거나 빠진 이유".** Every `EXTRA_US` stock must be in the day's
data, or named in `data.json` `usExtraMissing` with the reason the run left it out (Yahoo gave no prices, less than 60
days of prices, a broken bar, a preferred share, a Korean company's US listing, since #169 a new stock waiting for its first
confirmed close; if the run cannot tell, the reason says so and asks for a check). A named stock warns, with its reason.
Since #162 (Jack, 2026-11-21: "Yes, warn.", under his 11-20 rule "one stock missing from a source never holds the publish",
the same as BF-B in #149), a stock that is neither in the list nor in the record also only warns, named in the row ("이유 없이
빠짐 n: …"), the gate log ("!! 경고 …" and the "!! 손으로 더한 미국 종목 중 오늘 없는 종목" list, "BTI: 이유 없음") and the run summary. A stock
Yahoo doesn't send always had a reason, so this case means our own code lost the stock after the US list was built (no code
does today); the limit below is Jack's standing rule for checks on our own processing (section above). The publish still
fails, as before, when (1) more than 5 such stocks are missing with no reason (`US_EXTRA_QUIET_MAX`; the run writes a reason
for every stock it leaves out, so that many means the pipeline's list no longer matches the gate's own list `US_EXTRA_SET`,
or the record broke, not one stock missing. History, the 27 data-branch publishes 11-06 to 11-20 KST: the 11 with the record
(from 11-14) had 0 of 67 missing; the 16 before had all 39 stocks of the list as it was then; so N = max(5, 3 × 0) = 5,
Jack's default. The 16 older files lack the 28 added on 11-14, the kind of list mismatch this catches), (2) a stock's row is
in the list without a price and the record gives no reason (the app would show it without a price), or data.json has a row
for that ticker that is not a US stock row (`cls` not `us`, or `fund`: a wrong row, not a missing one), or (3) the record
names the stock but its reason is not text (null, empty, a number: a broken record). Stocks named with a reason never fail,
however many. A file without the record (or whose record is not an object) warns on a publish and is skipped by the site
checks (deploy, watchdog), which only warn on everything above, so code that adds a stock can go live before the next
publish brings it in.

**Gate row "미국 상장 외국 회사: 회사 합계와 맞춘 PER·PBR·배당수익률만".** For the foreign companies in the US list that
report in dollars (no `fcur`; the others are blanked by the currency rule, #114), the run compares Yahoo's per-share
numbers with company totals (`us_foreign_cuts`): PER with market cap ÷ net income to common (within 10%), PBR with
(market cap ÷ net income) × ROE (within 1.35×: narrower than √2, so a 2× ADR mistake never stays inside it; the largest
gap for a correct PBR on 2026-11-14 was BHP's 1.24×, ROE uses average equity), and the dividend yield with the dividends actually
paid in the last 350 days (Yahoo's dividend records, per ADR, in dollars) ÷ today's close (within 10%). Anything that
does not match, or cannot be compared (no net income, no ROE, no dividend records, or Yahoo did not confirm that the
statements are in dollars: then all three are blanked), is blanked and listed in
`data.json` `usForeign.cut` with the numbers, and the stock carries `fgnCut` (`{per | pbr | dy: "mismatch" | "currency"}`);
the run log prints one line per blank. On 2026-11-14 (local run): BP PER
and PBR (Yahoo PBR 7.62 is the ADR price over one ordinary share's book value; an ADR is 6 shares), HSBC PBR (7.07) and
yield (Yahoo's 2.23% leaves out the larger fourth dividend; paid in the last year: 4.18%), Diageo PBR (93.64), AB InBev
PBR (no ROE) and yield, BHP yield (Yahoo annualises the last half-year dividend: 4.98% vs 4.33% paid), AstraZeneca and
TotalEnergies yield (Yahoo's dividend records miss a payment, so the check cannot confirm a correct 1.74% / 4.38%; they
come back when Yahoo's records are complete). Shell, Novartis and Rio Tinto show all three. The row fails if a blanked
number is back (pbr also blanks the 가치 score `vz`), if a foreign company's numbers were published unchecked, if a
blanked number has no `fgnCut` mark on its stock (the app would say "자료가 없어요" instead of the reason), if a mark has
no matching `usForeign.cut` row, or if a file carries marks without the `usForeign` record. 2.0 shows each
blanked number as "–" under its label with Jack's line "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요." (Jack,
2026-11-14) right under it, in the same places as the currency line (#114): the 가치 and 배당 tiles of 요약, 내 기준과 맞는 정도
(card and sheet), the 가치 tab, 가치 자세히 and the 배당 tab. A number blanked because the statement currency was not
confirmed gets the same line (the currency line needs a currency name). **On a day the check itself stops** (run log "!! 미국
상장 외국 회사 검사가 멈췄어요"), the companies it had already finished keep their blanks and their line; every remaining
foreign company that reports in dollars (since #PR the whole `usForeign.set` without `fcur`: 40 on 2026-11-14, the 21 included)
has PER, PBR and 배당수익률 blanked unchecked, each marked `stopped`, and 2.0 shows "–" with Jack's line "오늘은 이 숫자를 확인하지
못해서 비워 두었어요." (`co.fgnStopped`, Jack 2026-11-15) in the same places — no longer "자료가 없어요". The gate row warns that day
(naming the companies; it never holds the publish). The next run checks again. A file from before #PR has no marks on such a day
(the gate reads it as before). The old app shows "–" for these, as for the currency case.

**Which companies count as foreign (since #PR; Jack, 2026-11-14 Q5: "widen it").** The run finds them by a rule every day
(`us_foreign_set` in `fetch_data.py`, never a hand list), among company shares (not ETFs or funds):
1. statements not in dollars (`fcur`, #114): their PER, PBR and yield are already blank with the currency line; this check skips
   them, so they keep exactly #114's line and never get a second one;
2. outside the S&P 500, with Yahoo's headquarters country (`country`, a new field in the US info cache) not the United States
   (Puerto Rico counts as the US), or a name that says depositary shares (ADR, ADS, American Depositary — also when Yahoo's
   31-character short name cuts it to "- American D…" or "- Americ…"; a cut shorter than "- Am" is not recognised, which matters
   only when Yahoo also leaves out the country);
3. the 21 of #126 (`US_FOREIGN`) stay in as a floor: the rule finds all of them on its own, and the run log names any that only
   the floor caught ("규칙이 찾지 못해 손으로 정한 목록(US_FOREIGN)으로 넣은 곳" — Yahoo left out the country).

S&P 500 companies are never foreign here, wherever their headquarters: S&P admits only US companies (they file 10-K reports
with dollar statements, and the shares that trade are their ordinary shares, not depositary receipts), so Yahoo's per-share
numbers for LIN, MDT, ACN, ETN, JCI, STX, CB, TEL, AON, WTW, ACGL, EG and the rest are on the same share as the price. Checked
against Yahoo on 2026-11-14 (23 such companies): PER within 1.00–1.09× of market cap ÷ net income (APTV 1.59×), PBR within
1.00–1.11× (STX 2.04×: tiny equity); putting them through this check would have blanked 10 correct yields (ACN, ALLE, AMCR,
AON, CB, EG, JCI, LYB, TEL, TT: Yahoo's dividend records miss a payment) plus APTV's PER and STX's PBR. The run log lists them
("S&P 500 회사라 외국 회사로 보지 않은 미국 밖 본사 N곳"). A company outside the S&P 500 whose country Yahoo did not give is not
counted as foreign (as #114 does for an unknown currency): the log names it, `usForeign.unknown` records it, the gate row
warns, and the next run asks Yahoo again. The run also re-reads, once, any cached entry of a company outside the S&P 500 that
has no country yet (about 270 on the first run after #PR; the S&P 500 companies are not re-read).

**When the S&P 500 list can't be trusted.** The run trusts the S&P 500 list only when it overlaps today's priced US list by at
least 400 tickers and has at most 550 (`US_SP500_MIN`, `US_SP500_MAX` in `validate_data.py`; 503 listed, 500 in our list on
2026-11-14). If FinanceDataReader fails, or renames the
symbol column so names come back instead of tickers, the overlap drops and the run does **not** apply the country rule that day:
it checks only the 21, the non-dollar companies and the companies in yesterday's published `usForeign.set` (basis `prev`), and
logs "!! S&P 500 목록을 쓸 수 없어요 …". `usForeign.sp500` records `{n, inList, ok}`; the gate row warns that day (never holds the
publish) and fails only if the record contradicts itself (ok with an overlap under 400 or a list over 550, basis `country`/`adr` on a day the list
was not trusted, `prev` on a day it was). Nothing to fix by hand: the next run reads the list again. If it repeats for days, look at
the FinanceDataReader S&P 500 listing (its columns). The same fallback (21 · non-dollar · yesterday's set, basis `error`) is used
if the rule itself crashes ("!! 미국 상장 외국 회사를 찾다가 멈췄어요"); it never widens to every company outside the S&P 500.

**Kinds of blank, and Jack's open question (the one switch).** Each blanked number carries its kind in `fgnCut` and in
`usForeign.kind`:
- `mismatch`: compared, and Yahoo's number disagreed (also a PER that Yahoo shows positive while net income is 0 or below);
- `currency`: statements not confirmed in dollars (#126) — all three blank, whatever the switch (a mixed-currency PBR is the
  TSMC 78.88 case);
- `norecord`: a yield whose dividend record or price the run could not read — blank whatever the switch. This is our own data
  missing, not the company: the gate row **warns** with the count and names ("배당 기록 · 가격을 읽지 못해 비운 배당수익률 N곳"). One or
  two names: nothing to do. Many (a whole day's download without its Dividends column blanks about 40 yields): look at the run log
  around the price download and tell Jack if it repeats;
- `nocompare`: a PER or PBR the company's own figures cannot check (a loss, or Yahoo gives no ROE) — Yahoo's number may well be
  right. On 2026-11-14 these are six PBRs: Alkermes 4.24, IREN 1.45, Roivant 7.12 and INNIO 32.31 (they look right), Bending Spoons
  19.62 (looks wrong: two share classes) and AB InBev 10.71 (unknown).

Jack's 11-13 rule blanks a number when there is nothing to compare it with, and that stays. Jack chose the line under those
blanks on 2026-11-15 (Q8): "회사 전체 숫자와 비교할 수 없어서 이 숫자는 비워 두었어요." (`co.fgnNoCmp`). The switch is
`US_FGN_NOCMP` in `validate_data.py`, now `"own"`; the pipeline and the gate follow it, and the app follows the kind the pipeline
wrote into the data:
- `"own"` (now, since #PR, Jack 2026-11-15): blank, kind `nocompare-own`; the app shows `co.fgnNoCmp` for those numbers only (a
  plain "–" if that copy key were missing — a test asks for it whenever the switch is `"own"`). After any own → line flip, keep the
  copy key until a `"line"` run has published: until then the live file still carries `nocompare-own`;
- `"line"` (= #126): blank, kind `nocompare`, the approved line "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요.";
- `"keep"`: don't blank — Yahoo's number shows, no mark; `usForeign.kept` lists those numbers. This loosens Jack's 11-13 rule for
  PER and PBR.
Changing the switch is a safety-rule change: its own PR, with Jack's yes. The gate fails a mark whose kind does not match its reason
(e.g. `mismatch` on a number that was never compared, or a yield without a dividend record marked anything but `norecord`), a
`usForeign.kind` that differs from the marks, `kept` rows under another switch or for a yield, a `nocmp` that isn't one of the three
values, or (when publishing) a file written under a different switch than the gate's; the site check (`--live`) reads each file
under its own switch.

**Rolling back #PR** is a revert PR **plus a data run**: the gate before #PR does not know the `nocompare` kind or marks on
companies outside the 21, so the reverted code's deploy check and site check fail on today's published file until a data run with
the reverted pipeline republishes it (Actions → 시세 데이터 갱신 → Run workflow, following the DART rule).

On 2026-11-14 (local run on real Yahoo data): 78 foreign companies — 38 with non-dollar statements (unchanged), 40 by
headquarters country (the 21's ten dollar reporters plus 30 more). Of the 30, 12 lose numbers: PER for BSP, GRAB, ICLR, NBIS, TRI
and WSE (Yahoo's EPS does not match the company's net income: e.g. NBIS 90.5 vs 272.6), PBR for CRDO and NBIS (outside 1.35×:
fast-growing equity, so ROE on average equity runs ahead) and for ALKS, BSP, INIO, IREN and ROIV (nothing to compare: loss or no
ROE), and the yield for TIGO and TRI (special dividends in the last year). SHOP, ARM, ARGX, CHKP, GMAB, LOGI, MELI and the
other 11 keep their numbers. Some of the 30 file US-style 10-K reports although headquartered abroad (e.g. ALKS, JAZZ, CRDO, ROIV,
LOGI, MELI); the rule cannot tell them from foreign filers without a filing-type source, so they are checked too (Jack, 2026-11-15: keep checking them) (their correct
numbers stay; ALKS, CRDO, IREN and ROIV lose their PBR). The record `data.json` `usForeign.set` lists every foreign company with
`[country, statement currency, basis]` (basis `fcur`, `country`, `adr`, `floor`, `prev` (yesterday's set, on a day the S&P 500
list was not trusted), or `error` when the run stopped while looking at that stock or the whole rule: then it is checked). The gate row now also fails if a company in `set` (no `fcur`) has numbers that were not checked,
if a mark sits on a stock outside `set` and the 21, if `set` has a bad shape or a basis that contradicts the record (`fcur`
without a currency on the stock, `country` with no country or the US, `floor` outside the 21), or if a listed company of the 21
or with `fcur` is missing from `set`: all of these are our own bookkeeping, never the market. It warns (never holds the publish)
for `unknown`, for basis `error`, for a day the S&P 500 list was not trusted, and if TSM, ASML, BABA, NVO or SHOP is listed but not
in `set`. A file without `set` (before
#PR) is read as before: the 21 only.

BHP and Rio Tinto have no 업종 group (Yahoo's "Other Industrial Metals & Mining" is not in `data/industry_us.csv`; Jack,
2026-11-14: keep it that way). EPD, ET and BNS stay out (Jack, 2026-11-14). Unilever's Yahoo "split" of 2025-12-09 (×0.888)
is a real 8-for-9 share consolidation (shares and ADSs, the ADS stays one share) on the day of the Magnum Ice Cream
demerger, which Yahoo merged with the demerger adjustment; it is in `SPLIT_OVERRIDES` as 8:9 with its sources (Unilever
RNS 2025-12-08, the shareholder circular, IRS Form 8937).

## US share-class tickers (주식 종류 티커, since #PR)

Jack, 2026-11-15: "fix Brown-Forman B, then check every share-class ticker in the S&P 500 and NASDAQ sources (dots, missing
separators, A/B classes) and add any others missing for the same reason."

**What was wrong.** FinanceDataReader reads the S&P 500 list from Wikipedia and deletes the dot from every ticker
(`Symbol.str.replace('.', '')`): Wikipedia's `BRK.B` and `BF.B` arrive as `BRKB` and `BFB`. Yahoo has no such tickers
(2026-11-15: quote type NONE, no prices), so the run asked for them, got nothing and dropped them without a word. Brown-Forman B
was never in the US list; Berkshire B was there only because `EXTRA_US` lists `BRK-B`. The old code's dot-to-dash step never fired
(the dot was already gone). The Nasdaq list (Naver) uses Nasdaq's own tickers, where the class letter is part of the ticker
(`GOOGL`, `FWONK`, `LLYVK`): those are Yahoo's tickers too.

**The rule** (`us_symbol` in `fetch_data.py`, the one place a source ticker becomes a Yahoo ticker):
- a dot, slash, space or dash before a 1–2 letter class (`BRK.B`, `BRK/B`, `BRK B`, `BRK-B`) becomes Yahoo's dash (`BRK-B`), from any source;
- a ticker with the separator already deleted is never guessed from its last letter (`BFB` could be a real ticker). Only the
  forms in `US_CLASS_JOINED` are mapped, only from the S&P 500 list, and only when the list gives the company's name and it matches
  (a blank name, or a list without a name column, counts as no match): `BRKB` → `BRK-B` (Berkshire Hathaway), `BFB` → `BF-B`
  (Brown–Forman). Evidence, 2026-11-15: Wikipedia's dotted form, the S&P constituent name, Yahoo answering the dashed form with the
  company's name ("Berkshire Hathaway Inc.", "Brown-Forman Corporation"), and nothing for the joined form;
- a plain 1–5 letter ticker stays as it is;
- anything else (a blank cell, non-English letters, a shape that is not a ticker, a joined form whose list name is blank or does
  not match) is not asked for, is logged with "!!" and is named in `data.json` `usListSym.unmapped` with the reason.

**Audit, 2026-11-15: every share-class ticker in both sources.** S&P 500 list: 503 rows (Wikipedia; FinanceDataReader's copy
has the dots deleted). Nasdaq list: 3,985 rows from Naver, of which the run reads the first 400 by market value (rank in
brackets). `EXTRA_US`: 67. Every common-share class ticker below was asked of Yahoo on 2026-11-15 and answers under the same
ticker, except `QVCGA`.

| Source | Ticker (source form) | Yahoo form | In the US list before | Action |
|---|---|---|---|---|
| S&P 500 | `BRKB` (Wikipedia `BRK.B`) | `BRK-B` | yes, only through `EXTRA_US` | mapped by the rule; `EXTRA_US` entry kept (below) |
| S&P 500 | `BFB` (Wikipedia `BF.B`) | `BF-B` | no | mapped by the rule; **added** |
| S&P 500 | `GOOGL` (Class A) / `GOOG` (Class C) | same | yes | none |
| S&P 500 | `FOXA` (Class A) / `FOX` (Class B) | same | yes | none |
| S&P 500 | `NWSA` (Class A) / `NWS` (Class B) | same | yes | none |
| S&P 500 | `LEN` (Lennar A), `MKC` (McCormick non-voting) | same | yes | none — their other class (`LEN-B`, `MKC-V`) is in neither source |
| Neither source | `BRK-A`, `BF-A` | same | no | not added: in neither source (not missing for a ticker-form reason) |
| Hand list (`EXTRA_US`) | `BRK-B` | same | yes | none |
| Nasdaq, top 400 | `GOOGL` (5), `GOOG` (9), `FWONK` (159, Liberty Formula One C), `FOXA` (164), `FCNCA` (165, First Citizens A), `FOX` (241), `NWSA` (288), `LLYVK` (372, Liberty Live C) | same | yes | none |
| Nasdaq, top 400 | `GOOGM` (320), `GOOGN` (321): depositary shares of Alphabet preferred; `METAM` (247): Meta mandatory convertible preferred | same | no (preferred rule; METAM also under 60 days) | none: not common-share classes |
| Nasdaq, below 400 | `NWS` (432) | same | yes, through the S&P 500 list | none |
| Nasdaq, below 400 | `Z` (437) / `ZG` (905) Zillow; `PAGP` (443) Plains GP Holdings Class A; `RUSHA` (524) / `RUSHB` (871) Rush; `BELFB` (653) / `BELFA` (1542) Bel Fuse; `BATRK` (657) / `BATRA` (1295) Liberty Braves; `LLYVA` (674) Liberty Live A; `FWONA` (678) Liberty Formula One A; `CENTA` (745) / `CENT` (1343) Central Garden & Pet; `LBTYA` (785) / `LBTYK` (859) / `LBTYB` (2239) Liberty Global; `LILAK` (888) / `LILA` (1581) Liberty Latin America; `GLIBK` (1047) / `GLIBA` (2514) Liberty Capital; `SENEA` (1086) / `SENEB` (1855) Seneca Foods; `PSNY` (1200) Polestar ADR Class A; `DGICA` (1274) / `DGICB` (2266) Donegal; `KELYA` (1455) / `KELYB` (2611) Kelly Services; `QVCG` (1506) QVC Group; `METC` (1557) / `METCB` (2877) Ramaco; `RDI` (2944) / `RDIB` (3160) Reading International; `UONEK` (3422) / `UONE` (3637) Urban One | same | no | none: below the top-400 cut, not a ticker-form problem |
| Nasdaq, below 400 | `QVCGA` (3655) QVC Group Series A | none: Yahoo has no price | no | none: stale entry in Naver's list |

Not counted as share classes (same company, different security): preferreds and depositary preferreds (`STRC`, `SATA`, `CHSCN`,
`AGNCN`, `FITBP`, `ACGLN`, `CHTRP`, `HBANL` …), warrants (`PSNYW`), units, rights and when-issued lines, and `HONA` (Honeywell
Aerospace, a spun-off company).

Summary, for the 14 share-class tickers the run reads (S&P 500, Nasdaq top 400, `EXTRA_US`): already fine 10 (`GOOGL`, `GOOG`,
`FOXA`, `FOX`, `NWSA`, `NWS`, `FWONK`, `LLYVK`, `FCNCA`, `BRK-B`); dot deleted 2, both mapped (`BRKB` → `BRK-B`, already in
through `EXTRA_US`; `BFB` → `BF-B`); added 1 (`BF-B`); unmappable 0; 2 preferred depositary shares left out as before (`GOOGM`,
`GOOGN`). Below the Nasdaq cut: 36 class tickers (with `NWS`, in through the S&P 500 list, and `QVCGA`, stale), all on Yahoo's
own tickers. Before → after on the real sources: the tickers asked for went from 810 to 809 (`BRKB`, `BFB` out; `BF-B` in; `BRK-B`
already there), the S&P 500 set used by #133 now holds `BRK-B` and `BF-B` (overlap with the priced list 500 → 502), and the
published US list goes from 801 to 802 companies.

**BRK-B stays in `EXTRA_US`.** The rule now covers it, but `EXTRA_US` is the floor on a day the S&P 500 list cannot be read (then
`BRK-B` stays and `BF-B` is named as missing), and the list of 67 is pinned by tests and by the gate's `US_EXTRA_SET`; removing it
would loosen that gate row.

**Both classes of one company.** The pipeline publishes every listing it gets; lists show one row per company in the app
(`engine.sameCompany`: same Yahoo short name and same total share count, as for GOOG / GOOGL). `BF-A` and `BRK-A` are in neither
source, so this PR adds no second class.

**Brown-Forman B.** It comes through the normal run: prices, Yahoo info (USD statements, so no `fcur`), an S&P 500 company so never
foreign (#133), 업종 음식료·담배 (Yahoo "Beverages - Wineries & Distilleries"). Checked against Yahoo on 2026-11-15: close $30.65
(+2.03%), market cap $14.06bn (18.759조원 at 1,333.8), PER 19.8, PBR 3.54, yield 3.01%. Its splits since 2016 are read by the first
run (one stock, under the 20-a-run cap): 2016-08-19 2-for-1 and 2018-03-01 5-for-4, both on the company's own announcements
(investors.brown-forman.com 2016-05-26; the 2018-01-23 announcement and the options adjustment notice for ex-date 2018-03-01). The
gate warns once on that first publish: "주식 분할 목록 변화 … 새 줄 정수 아닌 배율 1: BF-B 2018-03-01 ×1.25" — expected, nothing to do.

**The run record** `data.json` `usListSym`: `mapped` [[source, source ticker, Yahoo ticker]] · `unmapped` [[source, source
ticker, reason]] · `spTickers` the day's S&P 500 tickers in Yahoo form (null when the list could not be read) · `spGone` S&P 500
tickers missing from the day's list → reason (null on a day the list was not trusted, #133) · `noPx` those Yahoo gave no price at
all · `spErr` those whose processing stopped on an error (a different problem: not a sign of a dotted class) · `missing` stocks
this rule added (`BF-B`) that are not in the day's list → reason · `read` whether the run left a ticker record.

**Gate rows** (`check_us_share_class`; added as stricter-only rows in #139, and since #149 a missing BF-B warns instead of failing):
- "주식 종류 티커로 들어온 미국 종목 (BF-B): 목록에 있거나 빠진 이유" — #126's rule for the stocks this rule added
  (`US_CLASS_SET` = `fetch_data.US_CLASS_ADDED`): in the day's data, or named in `usListSym.missing` with the reason (S&P 500 list not
  read, not in today's S&P 500 list, its list name blank or not matching, too little price history …). **Since #149 (Jack, 2026-11-20:
  "Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish.")** a missing BF-B only warns,
  named with its reason, or "이유 없이 빠짐" when the run wrote none (before #149 that case failed the publish). The row fails the
  publish in one case only: BF-B's row is in the list but has no price (0, blank, negative or not a number) and no reason — the app
  would show it without a price, a wrong value (the same fail as before; the site checks only warn, as before). A published `BFB`
  with another security's numbers is the next row's job and still fails. A file without `usListSym` warns on a publish and is
  skipped by the site checks.
- "미국 목록 출처 티커 (주식 종류 · 점이 지워진 꼴)":
  - **Warns** when a joined form (`BRKB`, `BFB`) is still in that day's S&P 500 tickers (`spTickers`), published or not: the
    mapping row was lost or the rule broke. Yahoo has no such ticker, so that form normally drops for lack of a price; the "들어온 종목"
    row then gives BF-B's reason as "S&P 500 목록에 점이 지워진 꼴 BFB 로 있는데 BF-B 로 바뀌지 않음 (바꾸기 확인 필요)" — a mapping
    problem, not "S&P dropped Brown-Forman" — and `noPx` names `BFB` too. Fix the table (see the recipe below).
  - **Since #149 (Jack's standing rule, section "Checks on our own processing" above):** the run drops the rows this row would fail
    on (`us_class_bad_rows`: the joined form published from the S&P list, the same form when `spTickers` is malformed, the row of a
    ticker mapped differently from the gate's table) and records them in `ownDrop.usClass`. With that record the row fails only when
    more than 5 rows were dropped, such a row is still published, or any `mapped` row is malformed (the mapping can't be checked;
    as strict as before); other record-shape problems and a mapping that differs from the table with no published row left only warn. The bullets below are the rule for files without `ownDrop`, and what "such a row" means.
  - **Fails** only if such a form is also a published ticker. Since Yahoo has no `BFB`/`BRKB`, in practice this catches one case:
    Yahoo answering the joined form with some other security, which would put the wrong company in the list. The same letters from
    another source (a real Nasdaq company that one day gets the ticker `BFB`) are only named, so a real ticker can never block every
    publish; a file without the record names them with a warning (the source can't be told).
  - **Fails on a publish, warns on the site checks** (deploy, watchdog): a joined form mapped differently from the gate's own copy of
    the table (`US_CLASS_JOINED_SET`), or a record with a bad shape (including `spGone` without a `spTickers` list, or `spGone` names
    outside `spTickers`, which would switch the check above off). On the site checks these warn so that a later PR that adds a field
    is not blocked by the older file that is still live; the publish gate still fails them. (These rows are new in #PR, so this is
    not a loosening.)
  - **Warns** when a source ticker could not be mapped (`unmapped`), when an S&P 500 ticker got no price at all (`noPx`: what a new
    dotted class looks like), when processing an S&P 500 ticker stopped on an error (`spErr`), or when the run left no ticker record.
  - The other S&P 500 companies missing from the day's list are only named (`spGone`; e.g. VYLR, Vylor, listed 2026-10-01: 32 days
    of prices, under the 60 needed; it joins by itself in late December).

**When the gate warns "S&P 500 티커인데 야후 가격이 없음 N: XYZA"** (run log "!! S&P 500 목록 종목인데 야후가 가격을 하나도 주지 않은
티커"): S&P has probably added a share class with a dot. (1) Find the company in Wikipedia's "List of S&P 500 companies" and read
its dotted ticker (`XYZ.A`). (2) Ask Yahoo for the dashed form once (`yf.Ticker("XYZ-A").get_info()`) and check the company name.
If both agree, one small PR adds exactly these lines:
1. `fetch_data.py` `US_CLASS_JOINED`: `"XYZA": ("XYZ-A", "<a word from the S&P list name, lower-case letters only>")`;
2. `validate_data.py` `US_CLASS_JOINED_SET`: `"XYZA": "XYZ-A"`;
3. only if the stock is new to our list (not already in `EXTRA_US`): `"XYZ-A"` in `fetch_data.py` `US_CLASS_ADDED` and in
   `validate_data.py` `US_CLASS_SET` — that puts it under the "들어온 종목" gate row;
4. `tests/test_us_share_class.py` `SP_ROWS`: `("XYZA", "<the S&P list name>")`. Nothing else in the tests changes (they build their
   expectations from the tables). If step 4 is forgotten, `test_every_table_row_has_a_fixture_row` fails and names the missing row
   (for a stock added in step 3, a few more tests fail after it for the same reason).

These are added checks, so they need no separate yes (CLAUDE.md, 2026-11-07); list them under 안전 규칙 변경. Its splits since 2016
are read by the next run. If the ticker is instead a real company Yahoo does not know yet (a new listing), nothing to do. **When it
warns "S&P 500 티커를 처리하다 오류"**: look at the run log around the price download for that ticker; the next run asks again.
**When it warns "바꾸지 못함"**: the source sent a ticker in a shape the rule does not know; read the reason in the row's details and
fix the source reading or extend `us_symbol`, with a test.

**If S&P drops Brown-Forman from the index**, BF-B leaves the S&P 500 list, so it leaves our US list and the "들어온 종목" row
warns every day ("오늘 S&P 500 목록에 없음 (지수에서 빠졌는지 확인)"; if instead it says "점이 지워진 꼴 BFB 로 있는데 … 바뀌지 않음",
Brown-Forman is still in the index and the mapping is what broke). Two ways to clear it, and both need Jack's yes first: remove `BF-B` from `US_CLASS_SET`
and `US_CLASS_ADDED` (that removes a check), or move it to `EXTRA_US` and the gate's `US_EXTRA_SET` to keep it in the list by hand
(that changes the pinned list of 67 and its tests). Keep the `US_CLASS_JOINED` line either way: it is harmless when the S&P list no
longer holds `BFB`.

**Rolling back #PR**: a revert PR. The reverted gate ignores `usListSym`; the next data run drops BF-B again (users who saved it
see the existing "no longer in today's data" handling). No data run is needed for the site checks.

## Roll back

- **A bad code release** (the app looks broken after a merge): Claude opens the merged pull request, presses
  **Revert**, and merges the revert pull request. The deploy runs by itself after the merge. Ask: "뱁새 마지막 머지를
  되돌려 줘." The same applies to a merge whose deploy was blocked by the deploy check: the site is still fine, but
  `main` is ahead of it until the revert.
- **Bad data** (the numbers are wrong and the gate missed it): Claude reverts the last commit on the `data` branch
  (and, until v17.6 part 3b, the same data commit on `main`), then starts **Actions → Deploy → Run workflow**. Users get
  the previous day's data back within about 15 minutes (a deploy started by hand runs the deploy check). Ask: "뱁새 어제
  데이터로 되돌려 줘."

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
  one. It never force-pushes. A run that does not publish (below the backup-day coverage floor, or a same-day run that is not
  better: "Backup days: coverage floor and same-day updates", since #161) writes nothing to `main` or `data`.
  The first daily run after v17.6 creates the branch by itself.
- **Deploy** builds the pages from `main`, takes the four files from `data`, runs the gate's `--live` check on exactly the
  folder it is about to publish (and, when the code changes, the three real-data checks: "The deploy check" above), and
  only then publishes. It runs after every merge to `main` and after every daily run
  that published new data. Settings → Pages → Source has been **GitHub Actions** since 2026-11-06. Never switch it back
  to "Deploy from a branch": GitHub would then serve `main` as it is, without the publication gate and with the `docs/`
  folder, whose licensed pictures must not be offered as downloads. Deploy leaves `docs/` out of the site.
  Since 2026-11-12 Deploy also leaves out the development folders and files the site never reads (`tests/`, `tools/`,
  `data/`, `styleguide/` and the build and pipeline files at the top; the two lists are in `tools/assemble_site.py`) and
  refuses to publish if one gets in. A branch deploy would serve them again, including the test data under `tests/`.
- Until v17.6 part 3b, the daily run still also commits the data to `main`, so the site works either way.
- **The write token (since 2026-11-13, #113).** The daily run's checkouts no longer leave GitHub's write token in a file
  every later step could read (the credentials file the checkout's git settings point to). git gets it only in the two
  publishing steps ("커밋 & 푸시", "data 브랜치에 올리기"), through `tools/git_token_auth.sh`, after the step's receipt
  checks (the data step's gate fingerprint is checked again inside `push_data_branch.sh`). The script runs only on a
  GitHub Actions runner. Its log lines:
  - "· 토큰 확인됨: GitHub 이 받아 줬어요" — normal.
  - "!! GITHUB_TOKEN 이 이 단계의 환경에 없어요" (the workflow file lost the step's `env`) or "… 공백이 있어요" (a broken
    token value); that step pushed nothing. Fix the workflow in a PR.
  - "!! 토큰으로 원격 저장소(origin)를 세 번 다 읽지 못했어요" — nothing was pushed by that step. Read git's own error
    line just above it. A token problem shows "could not read Username" / "terminal prompts disabled", "Authentication
    failed", "error: 401" or "error: 403" (revert, below). The network or a GitHub outage shows "Could not resolve
    host", "Failed to connect", "timed out", the 60-second limit, or "error: 5xx" (don't revert; the next scheduled run
    or a rerun publishes). "unable to access" appears in both, so read the rest of that line. If
    "커밋 & 푸시" passed and "data 브랜치에 올리기" failed, `main` has the day's data and the site doesn't yet; the next
    run (or a rerun) uploads it.
  - A scheduled run uses the workflow file of the commit it was created on but checks out the latest `main`, so the
    first run that proves #113 is one created after its merge commit (its "커밋 & 푸시" log shows "토큰 확인됨").
  - If a publish fails with a token problem right after #113 merged: revert #113 as a whole (never only
    `persist-credentials`, which would leave two auth headers), but keep `tools/git_token_auth.sh` in the revert for a
    day, so a run created before the revert (new workflow, latest `main`) still finds it. The first run created after
    the revert publishes normally; a manual run on `main` with dart=cache is not a full-DART run as long as the DART
    cache exists (check "DART 캐시: dart-cache-v3-…" in its log).
  The data-collection and gate steps still receive the token for read-only GitHub API calls, so a tampered tool in the
  same job could still reach it: this narrows the exposure, it does not close it. Splitting a read-only job from the
  publishing job is the follow-up.
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
  - The app keeps its own copy of the closed days in `src/v2/tradedays.js` (Jack, 2026-11-19: on late data the daily check
    keeps running on the last close for up to 5 trading days, counted per market). After any edit to the table, copy the
    same rows there and rebuild `app.html` (`bash build-app.sh`) in the same PR: `tests/test_late_check.py` fails while the
    two differ. Days past the app's copy count every weekday, so a missing year can only stop the late check earlier.
- **Exchange-rate history and stock splits** (v19.6a data, for 2.0's 팔았어요 · 배당 받았어요; three gate rows, stricter only):
  - `macro.json` `fxHist` = `{asOf, final, rows: [[date, rate], …]}` from 2016, plus `fxHistSrc` (where the rows come from) and
    `fxHistFresh` (the last day the run read that source itself). A US record dated in the past saves the rate of its own
    date: that date's row, or the last row before it (a weekend or Korean holiday uses the last row before). **Contract,
    for every source: rows speak only for dates on or before `asOf`. The app refuses any later date, except today, which
    uses `data.json` `fx` when the data is fresh.** A date with no row on or before it is refused too (under ECOS:
    2016-01-01 to 01-03, before its first business day).
  - **Which date a record uses (for the app):** the US trading date of the purchase, sale or dividend, as the user typed
    it. Row D of each source means:
    - `ecos_close`: the Seoul 15:30 close on Korean business day D (ECOS 731Y003 · 0000003). ECOS posts it during the
      night (it was there by about 02:00 KST the next day; the exact time is not published). If the 06:40 run finds it
      missing, the history simply ends one business day earlier, the gate warns (holiday-table check below), and that
      date can be saved a day later.
    - `ecos_next`: the 매매기준율 published on the next Korean business day after D (= the average of D's own Seoul
      trading; ECOS 731Y001 · 0000001). The newest one has no row yet, so `asOf` is the business day before it.
    - `ecos`: the 매매기준율 published on D (the average of the previous business day's trading).
    - `yahoo_next`: Yahoo's next-bar open, London midnight at the end of D (08:00 or 09:00 KST the next morning); at the
      06:40 KST publish the last row is the run's live `fx` and `final` is false.
    A weekend or Korean holiday uses the last row before it.
  - The source is one switch in `fetch_data.py`, `FX_HIST_SOURCE`: `ecos_close` (Jack's choice, 2026-11-13). Never
    change it without Jack: rates already saved in users' records would then mix two bases. Measured against the end of the US trading day D (Yahoo's next-bar open), 2,727 US
    trading days 2016-01 → 2026-11; the 06:40 publish columns cover every Tue–Sat publish 2016-02 → 2026-11:

    | Option | Median (record dated D) | p90 | p99 | Max | Days over 1% | Median if the user types the Korean date (D+1) | Yesterday's US session saveable at the next 06:40 publish | Extra wait otherwise (mean · max days) | US days not saveable at a 06:40 publish (mean · max) |
    |---|---|---|---|---|---|---|---|---|---|
    | `ecos_close` | 0.25% | 0.69% | 1.44% | 3.05% | 3.5% | 0.25% | 94.5% | 0.12 · 8 | 0.08 · 6 |
    | `ecos_next` | 0.27% | 0.77% | 1.46% | 3.80% | 5.0% | 0.19% | 0.0% (a Friday-night buy waits until Tuesday) | 1.59 · 11 | 1.10 · 7 |
    | `ecos` | 0.42% | 1.17% | 2.19% | 4.35% | 14.9% | 0.29% | 94.7% | 0.11 · 8 | 0.08 · 6 |
    | `yahoo_next` | (the yardstick) | | | | | | yes, but the last row is unfinished | | 0 |

    The worst publish for every ECOS option was 2017-10-10, after the long Chuseok holiday. ECOS rows are final
    (`final` true). Yahoo's daily series also has one-day spikes (2021-03-02, 2022-12-01, 2024-11-08) that ECOS does not.
  - If the source cannot be read, the run keeps yesterday's `fxHist` exactly as it was, as long as it came from the same
    source (sources are never mixed), however many days pass: its rows are still right for their dates and the app
    refuses dates after `asOf`, so dropping it would only refuse a 2019 purchase too. `fxHistFresh` does not move while
    kept. The one exception: if today's `fx` has moved more than 10% from the kept history's last value (only possible in
    a long ECOS outage), the history is left out, because the gate would otherwise block the publish. The gate row **환율 이력 (fxHist)** warns every day it is kept (with the number of days), when `fxHist` is
    missing (the app then refuses past-dated US records with its approved line, "환율 정보를 불러오지 못해 …", so nothing
    wrong is shown), when `fxHistSrc` is missing or unknown, and when ECOS's last row is older than the Korean holiday
    table says it should be (the business day before the publish, or the one before that for `ecos_next`; 14 days when
    the table does not cover the date). It also warns when a past row changed against yesterday's file (the first five
    dates are named), when `asOf` moved backwards, or when the source changed. **FAIL** means the history is broken: out of order, a gap of more than 14 days
    for ECOS or 7 for Yahoo, a jump of more than 10% between two rows, a value outside 900–2,000, not starting in the first
    week of 2016, `asOf` not the last row, a last row after today (or on today for `ecos_next` and Yahoo), a Yahoo history
    that does not end on `fxDate`, a last value more than 10% from `fx` (the two come from different sources and times;
    unit or currency mistakes are caught by the 900–2,000 range), `final` not true/false, or `fxHistFresh` after the
    publish date. Every rate saved from it stays in users' records, so never loosen the row; ask Claude to find the cause.
  - `data.json` `splits` lists every US stock split since 2016-01-01 (`splitsFrom`), `[code, date, ratio]` (ratio = new
    shares per old share; the date is the first US trading day on the new count, or the ex-date for a stock dividend).
    It is "Yahoo plus fixes", not guaranteed complete: a small stock dividend Yahoo leaves out is only there if someone
    added it to the override table. Where the rows come from, every run:
    - the committed seed `data/us_splits_seed.csv` (129 Yahoo splits 2016-01-01 → 2026-11-12, read once on 2026-11-13 and
      reviewed) with `data/us_splits_seed_codes.txt` (the 773 stocks it covers), plus `data/us_splits_seed_more.csv` with
      `data/us_splits_seed_more_codes.txt` (the 28 stocks added by hand on 2026-11-14, read 2016-01-01 → 2026-11-13: AZN,
      BTI, GSK and SONY have a split; see "US stocks added by hand");
    - yesterday's file (every row is carried forward, also for stocks that left the list);
    - what Yahoo shows in the day's regular price download (about three years back, no extra calls);
    - for a stock in neither the seed nor yesterday's file, its history since 2016 (one call per stock, at most 20 stocks
      a run, so at most 40 requests with the one retry; new stocks first, then yesterday's `gap` in order, so a stock
      that keeps failing never blocks the others). Stocks leave and rejoin the US list most days, so expect a few such
      calls a day (about 3–6), not zero. There is no 773-call download on `main`.
    A seed row only appears while its stock is in the day's US list (a seed stock that is out today, like AAON on several
    days in late October, gets its rows the day it rejoins); once published, a row stays even when the stock leaves.
    A split, once published, is never taken out. If Yahoo drops it, changes its ratio, moves its date by up to 10 days
    (same ratio), or lists the same ratio again on a second date within 10 days, the published row stays, the second
    date is not added, and the case is listed in `splitsInfo.diff` (gate warning; if both are real, add the second
    with an override row); those warnings are
    repeated every day until someone settles them with an override row. That also covers a ticker reused by another
    company: the old company's splits stay listed and warn until an "out" row removes them.
    `splitsAsOf` is the last day the run read Yahoo itself; it renews when the split column of even one stock was read
    today, so the 6-day loud warning does not fire during a near-total partial outage: then the warning gives the number of
    stocks not read (`noCol`), which is the thing to watch; `splitsInfo` also holds `noCol` (stocks it could not read
    today), `fixed` (the override table in effect) and `fixedKept` (override rows deleted from the code; see below). On a
    first publish (yesterday's file has no list) the run leaves `splits` out if any of the ten known splits is missing
    or if it could not read Yahoo's split column at all (gate warning "없음"), so a bad first day never blocks the publish.
  - Yahoo also writes spin-offs as "splits" with ratios like 1253:1000 (GE, GE Vernova); those are not share-count
    changes, so only clean ratios are kept (the reduced fraction has a side of 20 or less: 10:1, 1:15, 3:2, 21:20).
    Real events Yahoo writes wrongly or leaves out are in `SPLIT_OVERRIDES` in `fetch_data.py`, each with its source:
    RYAAY 2024-09-30 ×2.5 (ADS ratio change, not a spin-off); UL 2025-12-09 8:9 (a share consolidation on the Magnum Ice
    Cream demerger day; Yahoo writes ×0.888); HLT 2017-01-04 and DD 2019-06-03 1:3 (reverse splits on a
    spin-off day); WTW 2016-01-05 (2.649 → 1) and TRI 2018-11-27 (×0.9079) and 2023-06-23 (×0.963957) share
    consolidations; HON 2026-06-29 1:2 (a reverse split on the Honeywell Aerospace spin-off day, Honeywell 8-K
    2026-06-05; Yahoo writes 1907:2000); CBSH's 5% stock dividends Yahoo misses (2016, 2017, 2019, 2022, 2023). FERG's 2018
    consolidation is left out: the US-traded security then was a different one (FERG is on the NYSE only from 2021-03-08),
    so no FERG record can predate it. GMAB's 2018-05-01 5:1 stays (from Yahoo, in the seed): the Nasdaq ADSs (2019) come from
    the same ADR program that traded over the counter as GMXAY before, so an earlier holder's record is the same security.
  - **To correct a split** (in a small PR): a split that should not be there gets an "out" row (ratio `None`) with its
    source; a wrong ratio gets an override row with the right ratio; a wrong date needs an "out" row for the wrong date
    plus a new row for the right one (if Yahoo already shows the right date, the "out" row alone is enough: the new date
    appears the same day). Never delete an override row: a deleted row stays in effect (taken from yesterday's
    file, listed in `fixedKept`, gate warning) until it is changed to `None` or a new ratio, so the published list never
    jumps by accident. "Out" rows are published in `splitsInfo.fixed`, so the app can remove a split it stored.
  - 2.0 reads the list for every record (a record dated before a split counts at the new share count) and stores a split
    in a portfolio only when that stock's records lie on both sides of it; a stored split then stays even if the list
    changes later.
  - **주식 분할 목록 (splits)** fails on a broken list (shape, a ratio of 1 or outside 0.001–1000 or not clean unless the
    override table gives exactly that ratio, a date before 2016 or after today, the same stock and date twice, a new row
    whose stock is not in today's data unless it is an override row, a row the table says to take out, `splitsFrom` not
    2016-01-01), when one of the ten known splits is missing (AAPL 2020, TSLA 2020 and 2022, NVDA 2021 and 2024, AMZN
    2022, GOOGL 2022, WMT 2024, CMG 2024, HLT 2017), when `splitsAsOf` is missing or after the publish date, and
    when the list is missing although yesterday's file had one. When `splitsAsOf` is more than 5 days before the publish
    date it does not stop the publish (Jack, 2026-11-13: a minor source outage must never hold back everyone's data): the
    row turns into a loud warning that starts with "!!", and the run log prints a "!! 주식 분할:" line. What it means:
    Yahoo's split column has been unreadable for 6 days or more, so a split from those days is not in the list yet and
    a user's records around it would show the old share count. Check whether Yahoo is back; if a real split happened in
    the gap, add it to the override table by hand. It warns when the list is missing on a first day, when
    part was taken over from yesterday (`splitsSrc` kept or part), on any `gap`, `noCol`, `diff` or `fixedKept`, when one
    stock has two splits within 30 days (Yahoo may have written one split twice), on the day a stock first leaves the
    list (later days only list it under "확인할 것"), and for a split dated after the US price date.
  - **주식 분할 목록 변화 (직전 발행본과)** fails when a split from yesterday's file is gone or its ratio changed (the
    pipeline must never do that; an "out" row or a new ratio in the override table only warns). It warns for a new split
    from Yahoo whose ratio is not a whole number or one over a whole number (3:2, 21:20 …: a person checks it against the
    company's notice and, if it is a spin-off, adds an "out" row); rows already reviewed, from the committed seed or the
    override table with the same ratio, do not warn when their stock rejoins the list (AAON 3:2) and for a split dated more than 7 days ago that appears
    for a stock whose history was already read.
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

## Known limits: 종목 바꾸기 in two tabs (v19.7a)

Each 바꾼 내용 저장 (and 팔고 빼기) saves the portfolio's targets as one set with its time; when two copies of the records
meet, the later set wins whole. One case still leaves the targets adding up to more or less than 100%: **both tabs changed
targets and also added or took out different stocks** (for example 담기 in one tab and − / + in the other gives 120%;
기록 없이 빼기 in one and − / + in the other, 75%; 팔고 빼기 in one and 담기 in the other, 80% or 120%; 담기 of two
different stocks, 120%). Nothing is renormalised behind the user's back. No record is lost, the 합쳤어요 line shows, and
종목 바꾸기 then opens at that 합계 (in the watch colour) with 합계를 100%로 맞추기. Until then the daily check reads each
target over the sum of the held stocks' targets, so the sum alone puts no stock out of its band.

## Known limits: plan weights in 종목 바꾸기 (v19.7a, `planW`)

Every save of a target set (바꾼 내용 저장, 팔고 빼기) writes each holding's plan weight next to it (`planW`). A holding whose
target was not changed keeps its number; the changed ones share between them what they had, so the weights always add up
to the same total. They share it in two pools (review S1): the changed stocks you hold share what they had (with a held
stock taken out), scaled by how their targets changed together; the changed stocks you never bought share the rest. The weight bands measure against that total, so changing some targets does not move the bands of the
stocks you did not touch (Jack, 2026-11-13). Before, the total was the planned share counts (`plannedQty`) added up
again, and rounding the changed stocks' counts could move an untouched band by up to about a point.

**The whole-share allowance stays (final review S2).** A stock's band is still widened by the gap between its whole
planned shares and its target: `plannedQty × planPx` over the stored total, minus the target. So a stock whose single share
is large against the plan (1 share = 27% in a plan that gives it 20%) reads 할 일 없음 after its target is changed too.
The allowance only ever widens a band.

**A changed stock reads as a brand-new plan (verification S-b, `planV`).** Measuring a changed stock's whole planned shares
against the stored total was not enough: a new `plannedQty` changes what the planned values add up to (550만 → 555만), and
on 800 random portfolios × 3 saves, 223 of 4,801 changed held stocks read differently from a brand-new plan with the same
targets, prices and amount — 142 calmer (a hidden warning: 더 안 사요 at 72% where a new plan says 45.9%, 할 일 없음 where it
says 일부 팔아요) and 81 stricter (45 extra 먼저 사요, 14 extra 일부 팔아요), with edges up to 19 points off (55 with one held
stock). So each save also stores, on every held stock whose target it changed, `planV`: the weight that brand-new plan gives
it (read from the planned share counts, as before planW) times the stored weights' total over the held stocks. The band
rule reads `planV` over that total, so the stock reads exactly as the brand-new plan does at that save, until what you
hold changes (the same 800 × 3 again, and 7 more seeds: 0 differ, 0 calmer, 0 new 일부 팔아요 or 먼저 사요; edges within
2.2e-16), and a later save that does not change it leaves it where it is. After a purchase of a stock never bought, or a
sale down to 0, every reading moves with what is held (that comes with measuring against the held stocks' weights), so
it drifts from what a brand-new plan would say by the rounding of the stocks involved. Stocks the save did not change keep their own reading (no `planV`, or the one
they had), so their bands still do not move.

- **A tab of an earlier app** (opened before this version) ignores `planW` and keeps reading `plannedQty`, which is still
  saved as a whole number. In that tab an untouched band can show slightly different edges, as before. Nothing is set
  aside, and the earlier app keeps `planW` when it writes.
- **A portfolio never saved by 종목 바꾸기** has no `planW` and is read exactly as before.
- **`planW` is read only when every held stock has a usable one.** If only some do (two copies met through an earlier
  app, a hand-made file), the bands read `plannedQty` and the console says so. A value that cannot be used (not a number,
  negative, or more than twice the plan's total; the same for `planV`) counts as missing, never as a reason to set the
  portfolio aside. The next save keeps every stored `planW` that exists and works out only the missing ones, with a
  console line. Stored weights are not used either when they add up to next to nothing against the plan's own values, or
  when one is so large that a stock with planned shares would read below a quarter of its target (its 먼저 사요 edge below
  0); the console says which. A save over weights none of which can be used, or that add up to next to nothing, works
  every one out again from the plan and says so.
- **The first save of a portfolio whose plan cannot be read** (a holding without a plan price, a dollar holding without
  the plan's exchange rate) stores no `planW` and the console says why; its bands behave as before this change.
- **Targets are read over the stocks actually held.** When a save moves weight between a stock you hold and one you never
  bought, the held stocks' targets add up to a different number, so every held stock's band moves. That is the existing
  rule for a plan only partly bought, not rounding. A save that changes held and never-bought stocks while the held
  stocks' targets keep their total (weight moved among held stocks, and among never-bought ones) moves no untouched held
  band (review S1: a fuzz of 400 such saves, 0 moved).
- **How exact "does not move" is.** A plan in won, any save after the first: the same to the last digit. The first save
  of an older portfolio (plan read from `plannedQty` before, from `planW` after): the same to the last digit when the old
  sum of the held targets was a clean number, else within about 2e-16 (the old lines keep that sum as it was). A plan
  with a dollar stock: within about 2e-16. Targets that are not whole % (3/7 of the plan): within about 1.5e-12, because
  the band rule takes the sum of the held targets to 12 decimals. No status changes in any of these.

## Known limits: stock splits in 기록 (v19.6a)

A portfolio stores a split from data.json's `splits` as soon as a saved record of that stock is dated before it, and keeps
it for good.

- **A ratio correction does not reach a stored split.** A fixed row with a new ratio (splitsInfo.fixed) changes what the
  screens apply from data.json, but a split already stored in a user's records keeps the ratio it was stored with. Only
  an "out" row (ratio `None`) reaches stored splits: the app takes that stored split out, or moves it to data.json's
  corrected date of the same stock and ratio, whenever the records still read back; otherwise it keeps it and says so in
  the console. When taking out or moving a split changes a stock's share count, that stock's 기록 sheet says "주식 분할
  정보가 바뀌어서 주식 수를 다시 계산했어요." for the rest of that visit (the console names the count before and after).
- **A wrong date corrected more than 10 days away, with a record between the two dates that needs the old one.** The
  stored split stays at the old date (the records need it) and data.json's corrected row is applied too, so those
  records can count the split twice; the console names both dates. Within 10 days (the pipeline's same-event window)
  the two are one split and only the stored one applies.

## Known limits: the date of a US record (v19.6a)

A US record takes the exchange rate of the date typed (the US date, as the line under the date field says). The rate
history (`macro.json` `fxHist`) carries a day only once that day's Seoul close has been published as final.

- **Typed with last night's US date** (for example a purchase at 02:00 KST on the 13th, US date the 12th): the record is
  refused until the morning publish carries the 12th, a wait of hours. The form says so in its own line (Jack,
  2026-11-13): "이 날짜의 환율이 아직 없어요. 보통 다음 날 아침에 들어오니, 그때 다시 저장해 주세요." It shows for a dollar
  record dated a past day after the history's last day; what was typed stays in the form. Any other missing past rate (no
  history, a date before its first row, an unfinished last row) keeps "환율 정보를 불러오지 못해 지금은 지난 날짜의 미국 종목
  기록을 저장할 수 없어요. 잠시 뒤에 다시 해 주세요."
- **Typed with the Korean date** (today) the same record saves at once, at the current rate (data.json `fx`).
- Nothing is ever saved at another day's rate, and rates already saved never change.

## Known limits: a holding sold down to 0 and kept (v19.6a, `rules.SOLD_OUT_BANDS`)

One switch with three values decides how the weight bands read such a holding. It ships as `"own"` (Jack, 2026-11-13).

- `"off"` (live before v19.6a): the holding has no status; the others are read over what is held.
- `"spec"` (spec A.1 to the letter): it counts as 0 shares for everyone's bands. In a small or concentrated portfolio the
  other holdings then read above their bands (three equal stocks: both others 일부 팔아요).
- `"own"`: its other rules are read; passing rules are not shown, failing ones show, without a status or action (never
  규칙 깨짐 or 확인 필요 as a status for 0 shares). When none fails, it is read on its own weight band over the whole plan
  (먼저 사요 or 할 일 없음), and 추가로 넣을 돈 buys it back first by the plan's own targets; when
  those goals cannot buy it back, the money goes where `"off"` puts it (when `"off"` buys nothing either, the plan's result
  stands). The app never tells the user to buy back a stock that fails any of its own rules: when one of its other rules
  reads 규칙 깨짐, 지켜봐요 or 확인 필요 (what stops new money for a held stock: a dividend cut the user confirmed, 부채비율
  over its ceiling, a figure missing today, a drop not answered yet), it gets no 먼저 사요 and no action chip, and 추가로
  넣을 돈 skips it and buys what `"off"` buys. It never looks blank (Jack, 2026-11-14): on 포트폴리오 and on its company page
  it shows the rules it fails, in the rows a held stock gets for them (never "규칙대로면 팔 때예요" for 0 shares), with the
  "다 판 종목이에요. …" line. Nothing about it shows on 홈. This holds when its 0-share weight cannot be read today too
  (nothing else held, a held stock without a price, no price or band of its own): a failing one still shows its failing
  rules; a passing one then reads as under `"off"`. Every other holding reads exactly as under `"off"`. 홈 lists only
  the stocks held, so it keeps "오늘은 할 일이 없어요"; under the sold-out row on 포트폴리오 and on its company page, once:
  "다 판 종목이에요. 다시 살 계획이 없으면 계획에서 빼 주세요." (Jack, 2026-11-13).

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

## Known limits: 관심 종목 and a tab of the earlier app (v19.6c)

뱁새 2.0 keeps the 관심 종목 list in the saved records and, since v19.6c, also beside them (`baepsae2.v1.watch`), with the
time of each edit, because a tab of the app from before v19.6c (still open, or after a revert) saves the list as it read it
and could drop newer edits. The next start of 2.0 brings back what such a tab dropped and says 합쳤어요. Each edit is stamped
later than every time this phone already holds for that stock, so a clock that was ahead or set back never makes an older
edit win. The marks behind 홈's 관심 종목 조건 row (shown, cleared) carry their own time too, so the later mark wins and the
row neither repeats nor goes missing. One rare case remains:

- **Storage full on the copy beside the records only.** The records save, the console says "could not keep the watch list
  beside the records", and that one edit has no copy beside them until the next save that fits. If a tab of the earlier app
  saves its older copy in between, that edit can be lost (about 2 in 100 such races in testing). Freeing storage (기록
  내보내기, then removing old data in the browser) ends it.
