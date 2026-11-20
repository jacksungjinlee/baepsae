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
reason (see "US share-class tickers" below).

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
  halt), `new` (no official close in the previous day's file), `prev` (no usable previous-day file: then every stock);
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
## Korean stocks at their last confirmed close (국내 마지막 확인 종가, since #?)

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
- **Normal days:** nothing changes. No Korean stock gets `pxd`.
- **data.json:** `pxSrc.own` = `{v, max, n, codes, unconf, drop, dropEx, bad, aged, ind?, err?}`; `pxSrc.n` counts only stocks at `pxDate`.
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
  stocks are left out, as before #?), `pxSrc.own.err` holds the reason and the gate's carry row warns. Fix forward; the publish goes on.
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
- **Late data (#144) with a carried stock (Jack, 2026-11-20 f):** on late data the daily check stops when a held Korean stock's own
  close is more than 5 KRX trading days before today in total, or is not a readable date (`src/v2/rules.js` `lateCap`; console
  "[v2] late data: the check is not run: …"). Every stock the check reads counts: shares held, sold-out holdings kept in a portfolio,
  가진 종목 rows. Every portfolio then shows the usual stale state for that day (one state for all portfolios). 내 수익 and 연말에
  확인할 숫자 do not use this cap: they show amounts with their dates (and Jack's line), not a check result.

## US stocks at their last confirmed close (미국 마지막 확인 종가, since #?)

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
  list is checked again (`us_own_split_late`: a split found only through the seed or the history backfill): such a row is removed, with
  its new split rows, its `umeta` records (as #139 does) and an EXTRA_US reason (`split` entry with `late: true`). A must-have in this
  state behaves as before (no exemption).
- **Details of a carried stock (review, 2026-11-20):** Yahoo's PER, PBR, 시가총액 and 배당수익률 follow Yahoo's current quote, so for a
  carried row the info cache records Yahoo's quote price (`currentPrice` / `regularMarketPrice`) as its reference and the numbers are
  rescaled to the carried close. Without a quote price, or with one more than 50% away from the carried close, a cached copy under 14 days old is kept as it was; otherwise those four numbers
  are left blank for that row (`pxBad` on the cache entry; log `마지막 확인 종가 종목 …의 상세 정보: …`).
- **Same US date again (`usSrc.own.same`):** if the previous publish already has the same `usPxDate` (a second publish the same day, which is
  what 11-20's trial runs were), the stock keeps that publish's close **and its `d1`** for that day: it is that day's confirmed close, so no
  `pxd`, no `pxc` and no line.
- **Not carried, as before (`drop`):** `none` not in the previous publish, `halted` the previous publish had it with its own Yahoo date (`pxd`
  without `pxc`: a halted stock), `bad` unreadable price or date. These keep the existing path: Yahoo's own last bar with its `pxd` (the
  existing "{티커} 가격은 {md} 종가예요." / "미국 {md} 종가"), or left out when Yahoo has nothing.
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
- **data.json:** `usSrc` = `{v: 1, own: {v, max, n, codes, same, newer, split, unconf, why {bar · empty · err}, drop, dropEx, bad {n, rows, why}, aged, err?}}`;
  the stock row has `pxc: true`.
- **Gate:**
  - `미국 d1 채움 (미국 기준일 봉)`: a clean carry (`validate_data.us_own_codes`: `pxc`, `pxd` before `usPxDate`, no `d1`, a price, listed in
    `usSrc.own.codes`, within 5 NYSE days, and in a publish run exactly the previous publish's price and date) is **not counted as missing**,
    however many there are (warning, named). The row **fails only when more than `US_NO_CLOSE_MAX` (5) US stocks have no `d1` and are not a
    clean carry** (Yahoo's own older bar, a wrong carry). N = max(5, 3 × the most seen): the 27 publishes on the `data` branch from 11-05 to
    11-20 had 0 such stocks each (table in the PR). A file without `usSrc` (published before this) keeps the old rule (≥ 98%).
  - `미국 필수 종목 d1` (AAPL · MSFT · NVDA): a clean carry warns (named with its date) instead of failing; no `d1` without a clean carry still fails.
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
  line as Korean stocks of the same date); the old app's English lists "{티커}: We couldn't confirm today's close, so this shows the {date}
  close."; a stock in `usSrc.own.aged`: "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요." on its company page and under its row in
  portfolios. A US `pxd` without `pxc` keeps "{티커} 가격은 {md} 종가예요." and "미국 {md} 종가". The late-data check (`rules.lateCap`) counts a
  carried US close in NYSE trading days and stops above 5 in total, like a Korean carry.
- **Halted stocks:** the existing wording ("{티커} 가격은 {md} 종가예요." / "미국 {md} 종가") now remains only for stocks already halted
  before this change and for new tickers; a stock that stops trading after it becomes a carry with Jack's line and is left out after 5
  NYSE trading days.
- **A long full outage:** every US stock is carried for 5 NYSE trading days (warnings); on day 6 they age out and the US count and
  must-have rows stop the publish.
- **App late cap:** counts NYSE days up to the KST date (one day stricter than the pipeline's count, the safe side).
- **Popular list:** keeps US carries (`val` is from average volume, not one day's).
- **Ranking note on a full-blank day:** lists every carried ticker in one sentence (a shorter line needs new wording; not changed).
- **Known limit:** after a publish with US carries, later scheduled runs that day stop early (`already_published.py`: `pxDate` and `usPxDate`
  are current), so the carried closes stay until the next day's publish, as with Korean carries. A manual run can refresh them.
- **On a warning:** read the named rows. Many carries on one day means Yahoo was blank for them: nothing to fix on our side; the next
  publish takes Yahoo's closes again. A wrong carry (not the previous publish's price or date) means the carry step broke: tell Jack.
- **On a failure:** "마지막 확인 종가로 싣지 못한 종목 > 5" means many US stocks had no Yahoo close **and** no previous close to carry (new
  tickers, a first run without a previous publish, or a broken carry step). The previous publish stays live. Never raise N to get a
  publish out; a different N needs Jack's yes with new evidence.
- **Check on the site:** search a carried ticker (the log names them): its company page shows its date and Jack's line; a portfolio holding it
  shows "{티커}: 오늘 종가를 …". 005930 and 현대차 unchanged.

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
- **Plainly, the gap:** on a blank-close night, from about 50 to about 320 stocks not asked, the data publishes with published
  stocks missing (about 3 at 50, about 156 at 300) and only the WARN row. A check that stops the publish there would be a new
  publish-stopping rule and needs Jack's yes. Since the last-confirmed-close change, a stock from the previous publish is carried at
  its last confirmed close with its own date and Jack's line instead of going missing (at most 5 KRX trading days).

If the WARN shows:
1. Find the phase in the run log: the "· 2차 출처: … 묻는 중" line before the "!!" line has the GitHub timestamp, so the gap shows
   which source was slow.
2. A stock that was in the previous publish shows its last confirmed close with its own date and Jack's line ("오늘 종가를 확인하지
   못해서 {date} 종가를 보여 드려요."); any other stock left out shows "이 종목의 데이터를 찾지 못했어요" (portfolios: "오늘 데이터에 없는
   종목 … 빼고 계산했어요"). Either way this lasts for that whole day's data. Later scheduled runs do **not** fill them in: once pxDate and usPxDate are current, `already_published.py` skips the
   rest of the day's scheduled runs, so they come back with the next day's publish. Only a manual run brings them back sooner
   (after about 06:40 KST it re-reads far fewer Yahoo charts); follow the DART rule for manual runs.
3. Do not raise the limit to make one run pass. If it hits on days when both sources answer at normal speed, bring the phase
   times from the logs to Jack before changing `KR_FB_PHASE_BUDGET_S`.
4. If it hits on every run (a source blocking GitHub's servers), the must-haves stay unconfirmed and nothing publishes: that is
   the two-source rule working. Tell Jack in plain words which source is down.

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

**Gate row "손으로 더한 미국 종목 (EXTRA_US): 목록에 있거나 빠진 이유".** Every `EXTRA_US` stock must be in the day's
data, or named in `data.json` `usExtraMissing` with the reason the run left it out (Yahoo gave no prices, less than 60
days of prices, a broken bar, a preferred share, a Korean company's US listing; if the run cannot tell, the reason says so
and asks for a check). A named stock warns, with its reason. The publish fails only when a missing stock has no reason in
the record at all: the run writes one for every stock it leaves out, so this catches a pipeline list that no longer matches
the gate's own list (`US_EXTRA_SET`) or a broken record. A file without the record warns on a publish and is skipped by the
site checks (deploy, watchdog), which also only warn on a missing reason, so code that adds a stock can go live before
the next publish brings it in.

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
