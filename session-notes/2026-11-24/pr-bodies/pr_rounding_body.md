## What changed
- A stock's 오늘 등락률 now shows the same digits on every 2.0 screen (Track 2 audit 4.10, minor; app only). On the 11-24 publish, 144 stocks read 0.1%p apart between 홈 and 포트폴리오, e.g. 우리금융지주 (d1 −3.95): −3.9% on 홈 and its company page, −4.0% on 포트폴리오; 선익시스템 (+0.15): +0.2% on 홈, +0.1% on 포트폴리오; 이월드 (−0.05): a grey "0.0%" on 홈, a blue "−0.1%" on 포트폴리오.
- Cause: two roundings. 홈, the company page, 종목 list, 관심 종목, 순위, 시장, 왜 움직였나 and 이번 주 정리 used `deckcalc.signedPct` (Math.round: a half goes up, so −3.95 → −3.9 but +3.95 → +4.0). The list rows (포트폴리오, the old home's rows, a built portfolio's return since purchase) and the 왜 움직였나 dot strip used `components.jsx fmtPct` (toFixed: decided by how the computer stores the number, so +0.15 → +0.1 but +0.25 → +0.3). data.json `d1` has two decimals, so a d1 ending in 5 is exactly halfway.
- Neither old way was "right": worked back from the official closes (integer won, KRX tick sizes), for the 198 Korean d1s ending in 5 whose true change could be pinned down, Math.round matched the true one-decimal value 100 times, toFixed 111, the new rule 102. The two-decimal file alone cannot tell which side a half is on.
- Now one helper, `src/ui/pct.js`: `signedPct` (the text) and `shownPct` (the value as shown). One decimal, a half away from zero (the usual 반올림: −3.95 → −4.0%, +3.95 → +4.0%, a rise and a fall of the same size read the same), floating-point noise never decides a half, never "−0.0%". `deckcalc.signedPct` is that same function and `fmtPct` calls it.
- Colours and "is it 0.0%?" checks that follow the shown number now use `shownPct` too (홈 rows, money card and gain line, 순위 rows and 업종 head, 업종별 등락's two parts, 이번 주 정리 tile and mover, the 국민연금 change line), so text and colour always agree: a −0.05% day is now a blue −0.1% on 홈. Colours taken from the raw value are unchanged.
- What users see on the 11-24 publish: 232 stocks read a tenth differently somewhere. 193 are falls ending in 5, now a tenth lower everywhere (88 of them where both old ways had agreed, e.g. 한미반도체 −1.95: −1.9% → −2.0%); 39 are rises ending in 5 whose list-row text goes up a tenth to match 홈 (선익시스템 +0.1% → +0.2%). No wording changed.
- The portfolio's own 오늘 % shows in one live place (홈's money card; the older today.jsx strip is off while HOME2 is on), already through `signedPct`: nothing else to fix. The old app (예전 뱁새) shows no daily change at all, and `baepsae.html` is byte-for-byte unchanged.
- New test file `tests/test_v2_one_rounding.py` (also runs on a real data folder: `python tests/test_v2_one_rounding.py --data DIR`). `styleguide.html` rebuilt because it bundles `src/ui/components.jsx` (its examples show the same digits as before).

## Choices I made
- Which rounding is "right": since the data cannot decide a half, I took the usual rule (a half away from zero, Excel ROUND / 반올림) over keeping Math.round everywhere. Keeping Math.round would have changed only the list rows (144 stocks), but it shows a fall of 3.95% as −3.9% next to a rise of 3.95% as +4.0%, and a −0.05% day as "0.0%": Math.round is half-up, not half-away-from-zero, for negatives. toFixed was ruled out by its float noise (+0.15 → +0.1 but +0.25 → +0.3).
- Put the helper in `src/ui/pct.js` (no imports, no Korean, no colours) so both `src/ui` and `src/v2` read it without `src/ui` depending on 2.0's copy files; the old app does not import it.
- The list rows now write 1,000% and up with a comma (`+1,431.6%`), as every other 2.0 percent already did (`fmtPct` used toFixed, which has no comma). Only a since-purchase return of 1,000%+ on a built portfolio's row would show it.
- Routed the "as shown" colour and zero checks through `shownPct` too, including two that are not a day's change (the 국민연금 %p change line and 이번 주 정리's week %), because they print `signedPct` text and their checks must agree with it. Untouched: other one-decimal numbers that are not signed changes (weights, ROE, yields, volatility, `cofmt.pctText`, `format.p1`).
- Not changed (needs Jack's yes, a test edit): `tests/smoke_v2.py`'s mirrors `signed_pct` / `js_round` and the indParts `r10` lambda still copy the old Math.round. No scene hits a negative half today (smoke_v2 passes), but a future scene that does would need that mirror updated.

## 「새 문구」
없음 (digits only; no Korean string added or changed).

## 안전 규칙 변경
없음. No existing test or `validate_data.py` threshold edited. One test file added: `tests/test_v2_one_rounding.py` (app-only, fixed fixture data, no dependence on a particular day or stock; not part of the daily run's screen checks).

## Test evidence
<!-- filled in below -->

## Fresh-eyes review
Pending: one Opus 5.5 (Extra high) reviewer with the diff, the brief and CLAUDE.md (app-only PR, not a pipeline PR).

## After merge
- Watch the deploy; on the live site, search 005930 and 현대차, open every tab, check the dates.
- On the live data, pick a stock whose 오늘 등락률 ends in 5 at two decimals (the daily file's d1) and check 홈, 포트폴리오 and its company page show the same digits.
- For Jack's phone: nothing to approve. A few stocks' 오늘 % now read a tenth further from zero on 홈 (e.g. −3.9% → −4.0%), and the same number on 홈, 포트폴리오 and the company page.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
