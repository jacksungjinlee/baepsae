## What changed

- **홈 no longer names the US close date for a portfolio with no US close in it.** 홈 decided "a US stock is held" by the stock's market label (`cls` "us"). 379800 KODEX 미국S&P500 carries that label, but it trades on the Korean exchange, in won, at the Korean close. So after a US holiday a portfolio made with 포트폴리오 만들기 holding only 379800 showed "미국 종목은 현지 기준 11월 25일 종가예요." though none of its prices is a US close. The next time this would show: Friday 11-27's morning publish (Korean close 11-26, US close 11-25, Thanksgiving).
- 홈 now decides by the stock's currency in today's data (`pf.usdOf`: priced in dollars), exactly like #187's 포트폴리오 line and the existing 가진 종목 check (`usHeld`). `src/v2/home2.jsx` (the 홈 people see) and `src/v2/today.jsx` (the old 홈 behind the HOME2 emergency switch, off-path today) get the same one-line change.
- Unchanged: a real US stock held (AAPL) still shows the line; a US stock sold down to 0 and kept still doesn't on 홈 (`x.qty !== 0`); a normal day (both close dates the same) shows no line.
- In today's published data 379800 is the only row labelled US but priced in won (800 rows are priced in dollars, 801 labelled US).
- No new wording; the line itself is the approved `app.usClose`.

## Choices I made

- Same rule and same code shape as #187's 포트폴리오 line: `usdOf(load.byT.get(x.t))`, with 홈's existing `x.qty !== 0` kept beside it.
- A held stock missing from today's data now never triggers the line (it has no price today, so no US close is shown for it). Same as #187's 포트폴리오.
- The old 홈 behind the HOME2 switch kept its own "shares held" rule as it was (any holding of a portfolio that still holds something); only `cls` → `usdOf` changed there. So on that off-path screen, a US stock sold out and kept beside a held Korean stock still shows the line, as before this PR (and as 포트폴리오 does). Not changed here.

## 「새 문구」

없음. No user-facing text added or changed (the US close line is the approved `app.usClose`, now shown in fewer cases).

## 안전 규칙 변경

- **Edited (not loosened):** `tests/test_v196a_approved.py::test_home_counts_only_shares_held`, one expected string, nothing else in the test:
  `b.de.holdings.some((x) => x.cls === "us" && x.qty !== 0)` → `b.de.holdings.some((x) => usdOf(load.byT.get(x.t)) && x.qty !== 0)`.
  The test pins the code text so that a sold-out kept holding (0 shares) never counts on 홈; `x.qty !== 0` is still in the pinned text, so that property is pinned exactly as before. The other half of the string changed because the code it copies changed (US = priced in dollars, not the `cls` label). Nothing it rejected before is accepted now: the line shows in a subset of the cases it showed before. The new behavioural test below also checks the sold-out case.
- **Added:** `tests/test_v2_home_usd.py` (3 tests), rendering 홈 and the old 홈 (HOME2 off, built from a temporary copy of `src`) with react-dom/server on the test fixtures.

## Test evidence

- `bash build.sh && bash build-app.sh`: OK. `app.html` and `app-preview.html` rebuilt and committed; `baepsae.html` unchanged.
- `python -m pytest tests/ -q -p no:cacheprovider`: 5169 passed, 1 skipped (14 min)
- `python -m pytest tests/test_v2_home_usd.py -q`: 3 passed. After a US holiday (pxDate 2026-11-26, usPxDate 2026-11-25), on both 홈s: 379800 only → no line · 379800 + 삼성전자 → no line · AAPL only → one line "미국 종목은 현지 기준 11월 25일 종가예요." · AAPL + 379800 → that line · AAPL sold out → no line; 홈 also: AAPL sold out and kept (in the check with 0 shares) beside 삼성전자 → no line, AAPL held beside 삼성전자 → the line. Normal day (both dates 11-26): no line anywhere.
- The new tests catch the bug: with main's `home2.jsx` and `today.jsx`, 2 of 3 fail (379800 only shows the line on both 홈s); with `&& x.qty !== 0` removed from 홈, the sold-out test fails.
- `python tests/smoke_v2.py`: 942 / 942 통과
- `python tests/smoke_app.py`: 176 / 176 통과
- `python tests/check_text.py`: 글자 점검: 페이지 4개 · JSON 87개 · 문제 0개
- Real data (data branch copy of the 11-24 publish, pxDate 2026-11-23, published 2026-11-24 06:40 KST): real_data_check.py --data 3 / 3 · smoke_launch.py --data 14 / 14 · smoke_app.py --data 171 / 171

## Fresh-eyes review

Not run yet. One Opus 5.5 Extra high reviewer (app-only PR). Its findings and fixes go here.

## After merge

- Watch the deploy; check the live site: search 005930 and 현대차, open every tab, check the dates.
- On Friday 11-27 (pxDate 11-26, usPxDate 11-25): 홈 with a portfolio holding a real US stock shows "미국 종목은 현지 기준 11월 25일 종가예요."; with only 379800 (or 379800 and Korean stocks) it doesn't.
- For Jack (phone): nothing to look at; the line only disappears where it was wrong.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
