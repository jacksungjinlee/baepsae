# logos-run: the checked logo run (2026-11-06)

This branch keeps the folder that `tools/logos/logodev_fetch.py --drop/--keep` work on, after Claude's review of every
logo (run 42211099051, logo.dev Pro). It is a record, not part of the site: Deploy reads only the `logos` branch.

- `logos/` is exactly what was pushed to the `logos` branch (2,093 entries, 2,044 pictures).
- `dropped/` holds every picture that was switched off (by the job's checks or after review), so `--keep` can bring one back.
- `drops.csv` / `keeps.csv` list every switch made after review, with the reason. `review.csv`, `run.json`, `run.log`,
  `summary.md` are the run's own records (no keys: the job never writes one).

Never push the GitHub artifact of a logo run (`logo-dev-fetch`) as it is: that is the unchecked run.
