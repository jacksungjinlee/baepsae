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
year's same-quarter report. Then the divided numbers must agree with a figure the unit cannot touch: profit ÷ the report's
own basic EPS, or 자본금 ÷ 액면가, within 1/8 to 8 times today's share count. It never divides when last year's report or
the 사업보고서 is the odd one out. Anything it cannot prove is left as filed, and the unit check (`unit_guard`) blanks
the company's numbers as before. A divided company carries corp.json `unitFix` (the report and the factor per statement).

The gate fails a malformed `unitFix` (factors other than 1,000 or 1,000,000, a bad report name, or `unitFix` together with
`unitChk`), and warns by name about every company read with a corrected unit, every day, so a person opens that filing on
DART. A company goes on the list `UNIT_FIX_CHECKED` in `validate_data.py` only with Jack's yes (same steps as the low-PBR
list above: Claude checks the filing, asks Jack in one line with the evidence, and on his yes adds the stock code →
`unitFix` (exactly the record in corp.json), `date` and `why` with the filing's `rcept`). An entry stays quiet only while
the record is the same; a new report divided, or a different factor, is named again. The list is empty today.

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
  one. It never force-pushes.
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
