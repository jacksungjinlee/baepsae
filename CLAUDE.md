# CLAUDE.md — 뱁새 (Baepsae)

Standing rules for every Claude Code session in this repo. Read this file fully before doing anything.
Then read, in order: `docs/HANDOFF.md` (full context), `docs/BAEPSAE_VOICE.md` (before writing ANY Korean UI text),
and the current task in `docs/tasks/`: the lowest version number whose Status line is not DONE.

## What this is

뱁새 is a free, educational investment-research web app for Korean retail investors in their 1st–3rd year of real
investing. Live at https://jacksungjinlee.github.io/baepsae/. Owner: Jack (Sung Jin) Lee — 이성진, INSEAD MBA 26J.
Tagline: "황새 말고, 내 걸음으로".

## Who you are working with

- Jack makes product and design decisions. **He does not write or read code, and he does not open GitHub.** He works
  from the Claude desktop app (Code tab, Cloud sessions) and claude.ai chat. You own the whole GitHub process (below).
- Explain in plain English, short and direct. Lead with problems and risks, not reassurance. No jargon without a one-line gloss.
- Korean UI text: natural Korean a real person would say (see the voice guide). Never translation-style Korean.
- Write KRW amounts in 만원 style even in English (e.g. "150만원").
- Product and feature design happens with Jack in claude.ai chat and reaches you as spec files in `docs/tasks/`.
  Follow the spec. If it conflicts with what the code actually does, **stop and report** — don't improvise.

## The two disasters

Two things must never happen:
1. **Users see wrong or stale data without knowing it.**
2. **The site breaks.**

Every rule below exists to prevent one of them. In Oct 2026 both happened for a month, silently (`docs/HANDOFF.md` § 5).

## Safety rules are frozen

- `validate_data.py` thresholds, the must-have stock list, freshness limits, and every test in `tests/` are safety
  rules. **Never loosen, skip, comment out, delete or special-case them to make a run or a PR pass.** This includes
  adding `|| true`, `continue-on-error`, `if: always()` on a publish/commit step, or try/except that hides a failure.
- If you believe a safety rule is wrong, stop. Ask Jack in this chat with the evidence (and record it under
  **안전 규칙 변경** in the PR), and let him decide. Default answer: fix the data or the code, not the rule.
- Publishing is always gated: no workflow may commit or deploy data that has not passed `validate_data.py`.

## How work ships (non-negotiable)

1. Never push directly to `main`. Work on your session branch, open a pull request, and merge it yourself when the
   merge rules below allow (§ GitHub process). `main` changes only by merging a PR.
2. `baepsae.html` is a **build output**. Change `src/` and rebuild with `bash build.sh`; never hand-edit it. Until v17.6
   moves the build into the deploy workflow, commit the rebuilt `baepsae.html` in the same PR as the `src/` change.
3. Never commit `data.json`, `corp.json`, `disc.json` or `macro.json` from a session. Only the daily workflow writes
   them (on `main` until v17.6, then on the `data` branch).
4. Before merging (or asking Jack, when § GitHub process says to ask):
   - all tests pass (CI green once v17.6 lands);
   - a **fresh-eyes review**: spawn a subagent that did not write the change, give it the diff, the task spec and this
     file, and ask it to find bugs and rule violations. Fix what it finds and summarize it in the PR.
5. Every PR description contains, in this order:
   - **What changed** — plain English, 3–8 bullets, written for Jack.
   - **「새 문구」** — every new or changed user-facing Korean string, verbatim (before → after). "없음" if none.
   - **안전 규칙 변경** — any change to a safety rule, with reason. Normally "없음".
   - **Test evidence** — commands run and results.
   - **Fresh-eyes review** — what it found and what you fixed.
   - **After merge** — what you will run and check yourself, and anything Jack should look at on his phone, or "없음".
6. One version per PR. Small and reviewable beats big.

## GitHub process — you own it (Jack's standing rule, 2026-10-31)

Jack does not open GitHub. You create branches, open pull requests, merge them, start and watch workflow runs, and roll
back. If GitHub refuses a merge or a workflow start because of permissions, tell Jack in plain words exactly which
setting to change (where it is and what to click), never just "go to GitHub".

**Merge on your own only when ALL of these are true:**
- `bash build.sh`, `pytest tests/` and the phone-size smoke test (`python tests/smoke_app.py`) pass — and, once v17.6
  lands, the GitHub `ci` check is green;
- the fresh-eyes subagent review is done and its findings are fixed;
- for pipeline changes: a green `dry_run` on your branch, with the validation summary in the PR;
- no safety rule is loosened.

**Ask Jack first, in this chat, with a short yes/no question in plain words** (never send him to GitHub), when a change:
- adds or changes user-facing Korean text — show him the 「새 문구」 table in the chat;
- changes what users see or how a feature works, beyond what an approved spec already says;
- needs him to pay for, sign up for, or change a setting in anything;
- is v17.5 or v17.6 — open the PR, tell him its number, and wait for his "merge" (his claude.ai chat reviews it first).
  This rule ends after v17.6.

**Never — even if Jack asks casually; explain why first:**
- loosen, skip or delete a safety rule or test;
- merge with a failing check;
- force-push or rewrite `main`'s history;
- commit data files from a session;
- run more than one full-DART run in a KST day (a `dart=full` run, or any DART-on run that starts with an empty or
  missing DART cache — e.g. the first run on a new branch or the first run on `main` after a cache loss);
- print or move secrets.

**After every merge:**
1. Watch the next relevant workflow run until it finishes. Start one yourself if the change needs it, following the
   DART rule above.
2. Check the live site yourself (https://jacksungjinlee.github.io/baepsae/): search 005930 and 현대차, open every tab,
   check the dates.
3. If anything is wrong, revert the merge right away (a revert PR that you merge), tell Jack what happened, then fix
   forward in a new PR.
4. Send Jack a 3–6 line plain-English summary: what changed for users, what you checked, anything he should look at
   on his phone.

**Keep `docs/CHANGELOG.md`:** one line per merge — KST date, PR number, plain-English summary — so Jack and his
claude.ai chat can follow the history. Add the line in the same PR when you can, otherwise right after the merge.

## Testing — before every PR

- `bash build.sh` succeeds.
- `pytest tests/` and `python tests/smoke_app.py` pass. The smoke test runs headless Chromium on the locally served site:
  - search finds 삼성전자 and 현대차;
  - every tab opens;
  - the detail app mounts in KO, EN and quick modes;
  - with broken data, the load-failure message appears;
  - zero page errors.
- Pipeline changes: a full `dry_run=true` workflow run on your branch is green, and its validation summary is in the PR.
- 0 emoji and 0 banned words in `baepsae.html`. Images with Korean text: render with Noto CJK fonts by explicit path and
  look at them before shipping.

## Engineering rules learned the hard way

- **No silent failure.** Every fallback logs loudly with counts ("· TTM 합성 성공: 2,341 / 2,476"). A fallback that hides a
  problem is a bug. In the app, failing to load data must show a message — never empty results or example data
  presented as live.
- **Never write NaN or Infinity into JSON.** Browsers reject the whole file. Use `write_json()` (`allow_nan=False`). In
  Python, `float("nan") or 0` is still NaN — use `_fin()`, never `x or 0`, on numbers.
- **Data publishes in stages.** Check completeness *and* finality, not just existence. The pre-market listing file
  has every market cap blank; the midday file looks complete but has intraday prices.
- **Prices are official closes with one date.** Every KR number derives from one `pxDate` (the official close date).
  Cut every series to that date. Never mix today's partial bar into "closing" data.
- **All dates in KST** (`ZoneInfo("Asia/Seoul")`). The runner's clock is UTC; `date.today()` there is a bug.
- **Never mix units or markets.** Same unit for the same field across KR and US; rank factors within each market.
- **A date shown to users describes the content**, not the run time. Each section carries its own content date.
- **Never select or rank by a field that might be blank.** Assert that the result contains the stocks it must contain.
- An edit that changes two places must verify both changed. Scripts that print "OK" without checking are how past
  releases broke.
- External sources are unreliable (KRX blocks GitHub's servers; volunteer caches change behavior). Retry, fall back,
  and log which source was used.
- Secrets (`DART_API_KEY`, `ECOS_API_KEY`) live in GitHub Actions secrets and the Claude Code cloud environment. Never
  print, commit or document their values.

## Product rules (locked — change only if Jack says so)

- Education, not advice. No 추천, no target prices, no promised returns. Numbers are framed as "what today's price
  assumes", never as forecasts. Footer: 교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다.
- Long-only. No leverage, short-selling or speculation features.
- Cards lead with the conclusion (Verdict line), then evidence. Computed ratios show their inputs ("receipts").
- Won-first framing. Beta shown with its estimation-error band; alpha shown as past-only.
- 기업분석 is Korean-listed companies only (built on DART filings). US stocks live in the portfolio tool.
- Mascot 뱁이: only Jack's own artwork (`baepi-1.png` … `baepi-9.png`, `icon-*.png`). Never redraw, generate or
  "improve" it.
- Factor labels: formal name + sorting basis as a small second line (가치 / PBR 낮은 순).
- Credit line: `이성진, INSEAD MBA 26J` (KO) · `Jack (Sung Jin) Lee, INSEAD MBA 26J` (EN).

## Repo map

| Path | What it is |
|---|---|
| `src/*.jsx`, `src/*.js` | App source (React, bundled by esbuild). Entry `src/main.jsx` → `src/shell.jsx` |
| `template.html` | HTML shell: meta/OG tags, GoatCounter, manifest. `build.sh` injects the bundle at `/*BUNDLE*/` |
| `baepsae.html` | Built app (the live page). `index.html` only redirects to it |
| `fetch_data.py` | Daily data pipeline (Python 3.11) → `data.json`, `corp.json`, `macro.json`, `disc.json` |
| `validate_data.py` | Publication gate (created in v17.5) |
| `.github/workflows/update-data.yml` | Daily run, weekdays 21:30 UTC (06:30 KST), plus manual "Run workflow" |
| `sw.js`, `manifest.webmanifest` | Service worker and home-screen install metadata |
| `tests/` | Pipeline unit tests and the app smoke test (created in v17.5) |
| `docs/` | Handoff, voice guide, task specs, runbook, `CHANGELOG.md` (one line per merge) |

## When you finish a task

Tell Jack, in plain English:
- what changed;
- what you could not do and why;
- the PR number and whether it is merged (and if not, the one yes/no question you need answered);
- the after-merge summary (3–6 lines) once merged and checked, including anything to look at on his phone.
