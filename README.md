# logos-run: the checked logo run (2026-11-06, one fix-up 2026-11-07)

This branch keeps the folder that `tools/logos/logodev_fetch.py --drop/--keep/--add-from` work on, after Claude's review
of every logo (run 42211099051, logo.dev Pro). It is a record, not part of the site: Deploy reads only the `logos` branch.

- `logos/` is exactly what was pushed to the `logos` branch (2,111 entries, 2,061 pictures; `logos` commit 8843d9b).
- `dropped/` holds every picture that was switched off (by the job's checks or after review), so `--keep` can bring one back.
- `drops.csv` / `keeps.csv` list every switch made after review, with the reason. `review.csv`, `run.json`, `run.log`,
  `summary.md` are the run's own records (no keys: the job never writes one).
- `adds.csv` lists logos added after review from a fix-up run (`--only`, then `--add-from`), with the reason:
  2026-11-07 000270 기아 by ticker (run 42325106234, `only` = 000270, `route` = ticker, 0 credits billed). Its old 32 px
  homepage picture left `dropped/`. The fix-up's own `run.json` and `review.csv` stay in that run's artifact; `summary.md`
  here has a section for it.

Never push the GitHub artifact of a logo run (`logo-dev-fetch`) as it is: that is the unchecked run.

2026-11-07 (Jack: a company's own group logo is correct): 8 pictures dropped by the job's 'shared' check came back with
`--keep` after Claude looked at each one — 대상 · 대상홀딩스 (대상 mark), 효성화학 (Hyosung H), 신한서부티엔디리츠 (Shinhan S),
삼양케이씨아이 (SAMYANG, its own homepage), 아이티센코어 · 아이티센피엔에스 (아이티센 symbol), 아모센스 (AMO). Hosting icons and other
companies' logos stay dropped (삼성전기's dropped picture reads SAMSUNG HEAVY INDUSTRIES, so it stays dropped). See `keeps.csv`.


2026-11-07 (Jack: retry the letter marks through every logo.dev route, PR #70): run 42357789298 retried the 136 largest Korean letter marks (272 credits); Claude looked at all 26 pictures it found and approved 8. The fix-up run 42359697867 (`only` = those 8, `extra_routes`, 0 credits billed, pictures identical) was added with `--add-from`: GS (+ GS우, brandmark = the 49 x 30 mark in gs.co.kr's own header), ISC (brandmark), 원익홀딩스 (ISIN; same oval as wonikholdings.kr's logo), 파라다이스 (brandmark), 아이에스동서 (ticker), 전진건설로봇, 필옵틱스 (same P as its own favicon), 씨어스 (homepage). Not added: photos, banners, 삼성중공업's logo for 삼성전기, other organisations' logos, an old 하나투어 mark, a subsidiary lockup for 비에이치, 펩트론 (2.7:1, too wide).
