# Brief: 오늘 등락률 is rounded two ways (Track 2 audit 4.10, minor; app only)

## The finding (from the audit, to be re-checked by you)
2.0 shows the same stock's 오늘 등락률 with different digits on different screens: SNDK read −16.0% on 홈 and −16.1% on 포트폴리오
on the 11-24 publish, and 135 stocks differed by 0.1%p. The audit points at `src/v2/deckcalc.js:222` vs `src/ui/components.jsx:168`
(line numbers from an older main; find the current ones). One path probably rounds an already-rounded value, or rounds a
different input (d1 in % vs a ratio), or uses Math.round vs toFixed (half-away-from-zero vs banker's / float artefacts).

## What to build (branch claude/one-rounding, worktree given, based on main 00ac1e3)
1. Reproduce on the live copy /tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/livedata_1124 (read-only; pxDate 2026-11-23):
   list every stock where the two paths give different text, and say which path is right (closest to the true value from the data).
2. Make every place in 2.0 that shows a day's change in % use ONE rounding helper (the one that is right). Search all of src/v2 and
   src/ui for other places that format d1 / 등락률 (cards, lists, 홈, 포트폴리오, 종목, 시장, 오늘 볼 것, 이번 주 정리) and route them
   through the same helper. The old app (src/*.jsx outside v2/ui) is out of scope unless it shares the helper — say what it does.
3. Same treatment for a portfolio's own day % if it shows in two places — check, report, fix only if the cause is the same.
4. No new or changed user-facing text. Signs (+/−), "0.0%", and the up/down colours must not change meaning; −0.0% must not appear.
5. Tests only added (new file, e.g. tests/test_v2_one_rounding.py, Node with the built bundle or the source module as other v2 tests do):
   the helper on edge values (x.x5 cases, negatives, float artefacts like 0.15*100), and every screen path giving the same text for the
   live copy's stocks. Never edit an existing test; if one pins the old digits, stop and report it (that needs Jack's yes).

## Rules (read /home/user/baepsae/CLAUDE.md fully first)
- `baepsae.html`/`app.html`/`app-preview.html` are build outputs: change src/, run `bash build.sh && bash build-app.sh`, commit the outputs.
- Checks before you report: full `python -m pytest tests/ -q -p no:cacheprovider` once, `python tests/smoke_v2.py`, `python tests/smoke_app.py`,
  `python tests/check_text.py`, and the three real-data checks on the live copy (read-only):
  `python tests/real_data_check.py --data D`, `python tests/smoke_launch.py --data D`, `python tests/smoke_app.py --data D`.
- The machine is shared and busy: never kill processes (no pkill/killall), never rm -rf outside your worktree, one full pytest at a time.
  If a smoke scene times out once under load, re-run it before calling it a failure.
- Docs: CHANGELOG line and a HANDOFF § 0 paragraph, both with "#?" for the PR number.
- Commit on claude/one-rounding with:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
  Do NOT push, open a PR or dispatch workflows.
- PR body to /tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/pr_rounding_body.md, sections in order: What changed · Choices I made ·
  「새 문구」 · 안전 규칙 변경 · Test evidence (with the three real-data result lines and the data's date) · Fresh-eyes review · After merge;
  end with "🤖 Generated with [Claude Code](https://claude.com/claude-code)", a blank line, "https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb".
  Never the word "coordinator".
- Report back in plain English: the cause, which stocks changed text (count + examples), what you changed, check results.
