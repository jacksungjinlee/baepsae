# Brief: one failed gold download must not drop the market assumptions (Track 2 audit 3.5, minor)

## The finding (checked by the coordinator on main 00ac1e3)
`fetch_data.py` ~17190–17255 (main). The run downloads Yahoo GC=F (gold, USD). If that download fails or comes back empty,
`gold_usd` is None, so the column "mt" is missing, and the block `if len(j) > MIN_DAYS and "mt" in j.columns:` skips ALL of
`settings.mktVol`, `usVol`, `mtVol`, `rhoKrUs`, `rhoKrMt`, `rhoUsMt`, and the bond ones (`bdVol`, `rhoKrBd`, `rhoUsBd`, `rhoMtBd`).
The log then says "!! 시장 가정 계산에 쓸 날이 {len(j)}일뿐 — 기본값을 써요", which is the wrong reason (the days were enough; gold was missing).
So one failed gold download silently replaces Korean/US volatility and the Korea–US correlation with the app's defaults.

## What to build (pipeline; branch claude/gold-corr, worktree given)
1. Compute every number whose inputs exist: kr/us vol and rhoKrUs need only kr and us; bond ones need bd; gold ones need mt.
   Keep exactly today's numbers when everything is present (prove: same settings dict on a fixture with all columns).
2. The log says what happened and why, with counts: which keys were computed, which were left out, and the real reason
   ("국제 금값(GC=F)을 받지 못해 금 관련 값은 기본값" or the like — log text is not user-facing, but keep the house style).
   No silent fallback (CLAUDE.md "No silent failure").
3. Find out what BOTH apps do when one of these keys is missing but others are present (src/, src/v2/): do they fall back
   per key, or treat the whole block as missing? Do they show a default as if computed, with no line saying so? Report it
   precisely (file:line). Do NOT add any user-facing text: new Korean wording needs Jack's approval. If a screen shows a default
   value with no say-why line today, list it as a finding for the coordinator, don't fix it here.
4. Consider a warning-only gate row in validate_data.py that names the settings keys that are missing vs the previous publish
   (never able to fail the publish; also warning-only if it crashes). Check how existing warning-only rows are written and follow
   that pattern. If the gate already covers this, say so and skip.
5. Tests only added (new file tests/test_gold_corr.py): gold missing → kr/us/bond keys present, gold keys absent, right log line;
   all present → identical to today's output; bond missing; too few days → defaults with the true reason. Never edit an existing test.

## Rules (from /home/user/baepsae/CLAUDE.md — read it fully first)
- Never loosen a safety rule; never edit existing tests or thresholds; never NaN/Infinity into JSON (`write_json`, `_fin`).
- Dates in KST. No ISO date literals in src/.
- Docs: add a CHANGELOG line with "#?" for the PR number and a HANDOFF § 0 paragraph (both "#?"); RUNBOOK if a gate row is added.
- Checks before you report: `bash build.sh && bash build-app.sh` (pages should be byte-identical to main: pipeline only),
  full `python -m pytest tests/ -q -p no:cacheprovider` once, `python tests/check_text.py`.
- Real-data checks are needed only if the site's served files change (they shouldn't). Run the gate on the live copy:
  `python validate_data.py --dir <copy> --live` on /tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/livedata_1124 (read-only; copy it first if you need to modify).
- The machine is shared and busy: never kill processes (no pkill/killall), never rm -rf outside your worktree, one full pytest at a time.
- Commit on claude/gold-corr with the attribution lines below; do NOT push, do NOT open a PR, do NOT dispatch workflows.
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
- Write the PR body (sections in order: What changed · Choices I made · 「새 문구」 · 안전 규칙 변경 · Test evidence · Fresh-eyes review · After merge)
  to /tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/pr_goldcorr_body.md, ending with:
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  (blank line)
  https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
  Never the word "coordinator" in docs or the PR body.
- Report back in plain English: what changed, numbers before/after on the live copy, what the apps do with a missing key, open questions.
