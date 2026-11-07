# logos-run: the checked logo run (2026-11-06, one fix-up 2026-11-07)

This branch keeps the folder that `tools/logos/logodev_fetch.py --drop/--keep/--add-from` work on, after Claude's review
of every logo (run 42211099051, logo.dev Pro). It is a record, not part of the site: Deploy reads only the `logos` branch.

- `logos/` is exactly what was pushed to the `logos` branch (2,094 entries, 2,045 pictures; `logos` commit 9504c43).
- `dropped/` holds every picture that was switched off (by the job's checks or after review), so `--keep` can bring one back.
- `drops.csv` / `keeps.csv` list every switch made after review, with the reason. `review.csv`, `run.json`, `run.log`,
  `summary.md` are the run's own records (no keys: the job never writes one).
- `adds.csv` lists logos added after review from a fix-up run (`--only`, then `--add-from`), with the reason:
  2026-11-07 000270 기아 by ticker (run 42325106234, `only` = 000270, `route` = ticker, 0 credits billed). Its old 32 px
  homepage picture left `dropped/`. The fix-up's own `run.json` and `review.csv` stay in that run's artifact; `summary.md`
  here has a section for it.

Never push the GitHub artifact of a logo run (`logo-dev-fetch`) as it is: that is the unchecked run.
