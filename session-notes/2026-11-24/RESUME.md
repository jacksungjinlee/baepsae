# Resume note — paused 2026-11-24 ~13:50 KST (Jack near weekly usage limit; resume Wednesday)

Jack (11-24): "hold on anything new and wrap up anything you are currently working on so that you may continue starting from Wednesday."
Standing orders from Jack's 11-23 message still apply (Track 1 / Track 2, reviewer mix, max 4 helpers, CLAUDE.md). Stop new work if he says usage is at 95%.

## Live state
- main = 26db255 (#189 merged ~13:40 KST). Live data: pxDate 2026-11-23, published 11-24 06:40. Site checked OK after #182 (11월 23일, 005930 177,500원, 현대차 247,500원, 0 errors).
- **Known live wrong number:** SNDK PER 0.1 (Yahoo per-share not split-adjusted). Fix = #188.
- Only scheduled task: 09:13 KST morning data check (trig_01BGc9nmRuJcg6dsL1wNZX5E, Tue–Sat, fresh session, silent on normal days). Left ON.
- Next publish 11-25 06:40: first data with #189 (log `· 팩터 점수 (국내/미국) …`, gate row `팩터 점수 …` → PASS `모두 같음`), #182 log `켜면 고칠 …`, #185 usSize, #178/#183 lines.

## Open PRs and the next step for each
| PR | Branch @ head | State | Next |
|---|---|---|---|
| #188 SNDK split cross-check | claude/split-cross-check @ e676f45 (main merged before #189) | r2 fixes done; dry run 45319852241 was running at pause | read dry-run result; merge main again; apply `proposed_bad_paths.patch` ONLY after Jack's Q1 yes; CI; merge; then consider a same-day data run so SNDK is fixed before next morning |
| #192 fx = official close | claude/fx-official @ 600b003 | round-1 fixes committed by builder (B1 gate 10% row compares Yahoo again, stale-ECOS fallback, …) but its checks were NOT finished when stopped | re-run full pytest, check_text, builds identical, real-data 3, gate on copy; update body (pr-bodies/pr_fxofficial_body.md, not yet updated for r1); Fable r2; dry run; merge |
| #186 KR splits | claude/kr-splits @ ca929ea | dry run green but DART lookups not exercised (same-pxDate rest) | second dry run after 16:00 KST on a new pxDate; upload body (pr-bodies/pr_krsplits_body.md); needs Jack's yes on reading filing text |
| #191 US trade dates | claude/us-dates @ 1660391 | reviewed, ready | Jack Q3 (rateNotYet → today's rate). Asked 11-24 ~12:50; 12-hour rule was ~00:50 11-25 but HELD by the pause — ask again before acting |
| #190 홈 US line by currency | claude/home-usd @ 7092b01 | reviewed | Jack Q2 (pinned test line edit); update body (defensive wording) |
| #179 KR dividends / #181 27 non-dollar / #180 DART quarter retry | see pr-bodies | waiting | #179 Q6, #181 Q7/Q8, #180 dry run after a publish |
| (no PR) gold-corr, audit 3.5 | claude/gold-corr @ c23c66c | **WIP, untested** (builder stopped mid-build) | finish per briefs/brief_goldcorr.md, then PR + Opus+Fable + dry run |
| (no PR) one rounding, audit 4.10 | claude/one-rounding @ 50f9365 | committed, checks not confirmed | run checks per briefs/brief_rounding.md, PR, one Opus review |

All branches behind main need `git merge origin/main` (docs conflicts: keep both sides; app pages: rebuild).

## Questions waiting for Jack (asked)
- Q1 #188: change one test expectation (test_bad_paths…) from "published" to "blanked".
- Q2 #190: update one pinned test line.
- Q3 #191: US trade dated NY-today before the morning publish saves with today's rate instead of "이 날짜의 환율이 아직 없어요."
- Q4: hide US fund PBR (+ 가치 score) on old-app 종목 고르기/성향 and 2.0 두 종목 비교 — needs design-chat line.
- Q5: 10-minute time limit on the gate's two-source price check (hit = no publish that run) — category 2.
- Morning 11-24 Q1–Q9 (v19.6b pin edits, Part L skip?, #179, #181, …) still open.
- New wording follow-up: 데이터 출처 page names FinanceDataReader for 환율 (ECOS after #192).

## Files here
pr-bodies/ (latest local PR descriptions, some not uploaded), reviews/, briefs/, morning_audit_list_1124.md (Track 2 ranked list), jack_1123_answers.md, notes_tail.md (last log lines), proposed_bad_paths.patch (#188 Q1).
