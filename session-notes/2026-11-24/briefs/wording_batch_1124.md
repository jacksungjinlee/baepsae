# 「새 문구」 drafts, batch 2026-11-24 (for Jack's yes, word for word)

Read first: CLAUDE.md, docs/BAEPSAE_VOICE.md, src/copy/v2.js. Code read on the PR #177 branch (`claude/home-today-bought-after`,
4bf0470 = main + #177). Nothing in the repo was edited.

How I counted characters: **fixed** = the line without its {placeholders}; **filled** = with sample values ({md} "11월 20일",
{n} 2, {names} "삼성전자, 현대차", {max} 5). **Width** = measured in Pretendard at 13 px (SIZE.xs, the size of every note
line here), wrapping only at spaces (keep-all), on a 390 px phone with 16 px page gutters. Box widths: 홈 card text 322 px,
이번 주 정리 notes 350 px, 오늘 볼 것 card about 290 px, 가치 tab note about 300 px.

Approved words reused: "빼고 계산했어요" (8 approved lines), "{names} 외 {n}종목" (krOwnCloseListMore, leftOutMore),
"{n}건" (weekly.count, look), "보여 드려요" (rank.groupLine, find.sub), "비워 두었어요" / "잠시 비워 두었어요" (pbrZero, unitChk),
"주식 분할" (rec.splitFixed), "자료" for a US source without naming it (pbrZero, fgnCut), quoting an on-screen label with
' ' (app.oldAppNote, hint.move), "비교했어요" (deck.vsNoDiv, deck.vsSold).

---

## 1. 홈 portfolio card, the 오늘 line (PR #177, highest priority)

| | |
|---|---|
| **Where** | 홈, the portfolio card (home2.jsx `MoneyCard`). Around it: name on the left, "{md} 종가" on the right; the big value with "오늘 {amount} ({pct})" beside it; then "산 가격보다 {amount} ({pct}) · 평균 단가를 넣은 {n}종목 기준"; then any notes (usd-today, missing stock, own close). The 가진 종목 card below lists each stock with its own day move (e.g. −7.0%). Proposed spot: a `Note` right after the 산 가격보다 line, shown only when 오늘 is on screen (not late) and the day's parts are mixed (some 샀어요 record dated on or after {md}). |
| **A** | {md}부터 산 주식은 산 뒤 움직임만 '오늘'에 넣었어요. |
| **B** | {md}부터 산 주식은 사기 전 움직임을 '오늘'에서 뺐어요. |
| **Chars** | A: 29 fixed / 36 filled, 297 px, **1 line** in 322 px. B: 30 fixed / 37 filled, 309 px, **1 line** in 322 px. (Over the 34 target once {md} is filled, but both fit one line at 13 px on a 390 px phone; on a 320 px phone they take two.) |
| **Gloss** | A: "For shares bought on or after {md}, only the move after you bought them is in '오늘'." B: "For shares bought on or after {md}, the move before you bought them is taken out of '오늘'." |
| **Notes** | **Why not the brief's literal "산 가격부터" (count from their purchase price):** it is false in one case. For a 샀어요 record dated *after* {md} with a typed price P different from {md}'s close C (e.g. bought Monday morning at 69,500 while the data still has Friday's 70,000), 오늘 counts 0 for those shares (lots.dayShare "after": in neither end), while "산 가격부터" reads as C − P. A and B are true in every case: shares dated on {md} count from their own price to the close (the move before the purchase is out, the move after it is in); shares dated after {md} count nothing (all of the move in the data is before the purchase; none is after it). Holdings bought before {md} are not mentioned, so the line never contradicts them. "'오늘'" in quotes points at the label on the card (approved style for labels), so the line cannot be read as explaining 산 가격보다, which is "since you bought" by definition. "부터" makes {md} itself included (on or after). Only 샀어요 records are "산 주식": a 가진 종목 row (금액으로 넣기 included, even one dated {md}) counts as held over the change (lots.js "imp"), so the line, which speaks only of 산 주식, stays true when such rows are in the same portfolio. Shown only with a 오늘 number (no line on late data or with US holdings, where 오늘 is left out). |

**For the builder:** `home.js dayMove` (the 가진 종목 path) returns `{ pct, amount }` and drops `mixed`; the line needs it passed
through, as `track.deckDayMove` already returns it for built portfolios.

---

## 2. 이번 주 정리 → 내 포트폴리오 "{%} · 코스피 {%}" (audit 4.1), wording for option (b)

| | |
|---|---|
| **Where** | 홈, 이번 주 정리 card (weekly.jsx). Around it: navy header "{first day} ~ {pxDate}", 이번 주 정리; a 2×2 grid of tiles, the 내 포트폴리오 tile with the week's % big and "{±won} · 코스피 {±%}" under it; 받은 배당, 공시, 다음 주 tiles; 가장 많이 움직인 종목; note lines (the left-out line, etc.); 닫기. Proposed for (b): when `money.buys > 0` (a 샀어요 record dated in the week was counted), the tile's second line keeps only "{±won}" and this line goes into the note lines under the tiles. It does not fit inside the tile: the tile's text box is about 147 px, so it would wrap to 3 or 4 lines there. |
| **A** | 이번 주에 산 주식이 있어서 코스피와는 비교하지 않았어요. |
| **B** | 이번 주에 산 주식은 산 가격부터 계산해서 코스피와는 비교하지 않았어요. |
| **Chars** | A: 32, 296 px, **1 line** in 350 px. B: 40, 370 px, 2 lines. |
| **Gloss** | A: "Some shares were bought this week, so we didn't compare with KOSPI." B: "Shares bought this week count from their purchase price, so we didn't compare with KOSPI." |
| **Notes** | True whenever it shows: it shows only when the week's money includes a 샀어요 record dated Monday to Sunday of the card's week (weekly.js `inWeek(p.date, w)`), and that is exactly when the portfolio's % starts those shares at their own price while 코스피 runs the whole week. Here "산 가격부터" (B) is true in every case, unlike item 1: weekMoney counts a week's purchase as end value minus its own cost, whatever its date in the week. "산" is the app's word for 샀어요 records; a 가진 종목 row dated in the week is not a purchase and is already left out ("imp", item 3), so it never sets this line off. Not blaming: it states the fact. Not covered: a sale in the week also makes the two a little different (the sold money stops moving at the sale while 코스피 keeps going). The brief scopes (b) to money coming in, so the trigger is purchases only. |

---

## 3. 이번 주 정리 left-out line for made-this-week, entered-this-week and taken-out stocks (audit 4.4)

| | |
|---|---|
| **Where** | The note lines under the 이번 주 정리 tiles (weekly.jsx `weeklyView`, ids "left"), next to the approved line "이번 주 움직임을 확인하지 못한 종목 {n}개({names})는 빼고 계산했어요." The new line takes the stocks whose `why` is `made`, `imp` or `out`; every other reason keeps the approved line. With more than 5 names (LEFT_NAMES) the capped twin shows, the same as leftOutMore. |
| **A** (one line for all three) | 이번 주 들어 넣거나 뺀 종목 {n}개({names})는 빼고 계산했어요.<br>Capped twin: 이번 주 들어 넣거나 뺀 {names} 외 {n}종목은 빼고 계산했어요. |
| **B** (one line per group) | made: 이번 주 들어 만든 포트폴리오라 종목 {n}개({names})는 빼고 계산했어요.<br>Capped: 이번 주 들어 만든 포트폴리오라 {names} 외 {n}종목은 빼고 계산했어요.<br>imp: 이번 주 들어 넣은 종목 {n}개({names})는 빼고 계산했어요.<br>Capped: 이번 주 들어 넣은 {names} 외 {n}종목은 빼고 계산했어요.<br>out: 이번 주 들어 뺀 종목 {n}개({names})는 계산에 넣지 않았어요.<br>Capped: 이번 주 들어 뺀 {names} 외 {n}종목은 계산에 넣지 않았어요. |
| **Chars** | A: 31 fixed / 41 filled, 356 px, 2 lines (twin 30 / 40, 2 lines). The approved leftOut is 35 / 45, 2 lines. B made: 35 / 45, 2 lines (twin 34 / 44). B imp: 28 / 38, 1 line (twin 27 / 37). B out: 30 / 40, 1 line (twin 29 / 39). |
| **Gloss** | A: "The {n} stocks entered or taken out since this week began ({names}) were left out of the calculation." B made: "This portfolio was made after the week began, so its {n} stocks ({names}) were left out." B imp: "The {n} stocks entered since this week began … were left out." B out: "The {n} stocks taken out since this week began … weren't included in the calculation." |
| **Notes** | **Why "이번 주 들어" (since this week began) and not "이번 주에" (this week):** the card stays on screen through Sunday *and the following Monday*, because Monday's close is published only on Tuesday's early runs. Three things can happen on that Monday and still land in these groups: a portfolio made on Monday is "made" (`createdAt > w.start`, no upper bound); a stock taken out on Monday with no records left is "out" (`removed`/`changes` at `>= w.mon`, no upper bound); a 금액으로 넣기 row entered on Saturday, Sunday or Monday carries the price date (Friday), so it is "imp" by date. "이번 주에 넣은/뺀" would be false for the Monday actions; "이번 주 들어" (from the week's start up to now) is true for all of them. "넣은/뺀" are the app's own words for 가진 종목 넣기 and 빼기, never "산": 샀어요 purchases in the week are counted (item 2), so they must not sound left out. "made" needs an undated 가진 종목 row, which was entered when the portfolio was made, so "넣은" is true for it too: B's imp line could cover made as well, if Jack wants two lines instead of three. In A, "뺀 … 빼고" repeats a root word. I kept the approved ending on purpose (easier to approve); the other natural endings ("계산에 넣지 않았어요") clash with "넣거나". B's out line uses "계산에 넣지 않았어요" to avoid "뺀 … 빼고". The line names only the stocks left out, so a mid-week 샀어요 stock being counted never contradicts it. |

---

## 4. 오늘 볼 것 → 다가오는 일정 (audit 4.3): the rows past 5

| | |
|---|---|
| **Where** | 오늘 볼 것 page, the 다가오는 일정 card (todaylook.jsx `DatesCard`). Around it: calendar chip and "다가오는 일정"; up to 5 rows "{md} · logo · {name} · 실적 발표/배당락일", earliest first (look.js `dateRows`, DATES_MAX 5, today to today + 7 days); then "미국 종목은 미국 현지 날짜예요." and, with a Korean holding, "한국 종목 일정은 아직 보여 드리지 못해요." Proposed: one more row or line right under the 5th row, before the US-date note, only when there are more than 5. Not on 홈 (its 다가오는 일정 row shows only the first date and opens this page) and not on the weekly 다음 주 tile (it has no cap). |
| **A** | 외 {n}건 |
| **B** | 날짜가 가까운 {max}건만 보여 드려요. {n}건이 더 있어요. |
| **Chars** | A: 3 fixed / 4 filled, 1 line. B: 28 fixed / 30 filled, 258 px, 1 line in about 290 px. |
| **Gloss** | A: "{n} more". B: "Only the {max} nearest dates are shown. There are {n} more." |
| **Notes** | "건" because each row is one event (a stock with both 실적 발표 and 배당락일 in the window is two rows), matching the approved "{n}건" counts. A follows the approved "{names} 외 {n}종목" shape; as a row under a list, "외 {n}건" alone is natural Korean. B also gives the reason, which the "say what and why" rule asks for, but it tells the reader about events they cannot open anywhere. True in every case: n = all events in the window minus the {max} shown, and it shows only when n ≥ 1. The ones not shown are always the later dates, because the list is sorted earliest first. {max} keeps DATES_MAX in one place. **For the builder:** `dateRows` slices to DATES_MAX before returning, so the total needs `dateRows(…, max = null)` or a count. |

---

## 5. (Optional, lowest) US stock whose PBR is blanked right after a split (SNDK 8:1, 11-20)

| | |
|---|---|
| **Where** | Where PBR shows "–" on the stock's 가치 tab; by the approved pbrZero / fgnCut place rule also 한눈에 가치 칸, 가치 자세히 and 내 기준의 가치 줄, once in each place where the number is blank. Around it on the 가치 tab: "업종보다 … 거래되고 있어요" head, the PBR cell "–" with "업종 {x}배", the PBR strip, the basis line. Same spot as "자료상 PBR이 0에 가깝게 나와서 확인하는 동안 비워 두었어요." |
| **A** | PBR 자료가 아직 주식 분할 전 기준이라 비워 두었어요. |
| **B** | 주식 분할 뒤 자료가 바뀔 때까지 PBR은 잠시 비워 두었어요. |
| **Chars** | A: 32, 278 px, 1 line in about 300 px. B: 35, 304 px, 2 lines. (pbrZero, already approved for the same spots, is 36 and 2 lines.) |
| **Gloss** | A: "The source's PBR is still on the pre-split share count, so we left it blank." B: "After the stock split, we left PBR blank for a while until the source updates." |
| **Notes** | Neither line promises a time. B's "잠시" is the approved unitChk word, and "바뀔 때까지" is a condition, not a date. A is true if the pipeline blanks PBR only when it finds the source's book value per share still on the old count (the SNDK check). B is true if the blank lifts as soon as the source updates. If the build instead blanks for a fixed number of days after any split, neither is exact, and a mechanism-free line fits better: "주식 분할 직후에는 PBR 자료가 틀릴 수 있어서 잠시 비워 두었어요." (32 chars, "Right after a split the PBR data can be wrong, so we left it blank for a while.") "자료" without naming Yahoo follows pbrZero and fgnCut. |

---

## Recommendation (one line each)

1. **B**: "사기 전 움직임을 '오늘'에서 뺐어요" answers the exact puzzle (the row says −7%, 오늘 says 0원: the fall came before the purchase), is true for shares bought on {md} and after it, and fits one line.
2. If Jack picks (b): **A**, one line, true whenever money came in. If he picks (a), note that the tile would then show a 코스피 number different from the index's own week, which may need its own line later.
3. **A** plus its capped twin: two strings instead of six, true for all three groups including what happens on the Monday after the week.
4. **A** "외 {n}건": matches the approved "외 {n}종목" shape and fits as a row. Use B only if Jack wants the reason spelled out.
5. **A** if the build blanks PBR by checking the source; otherwise the mechanism-free line in the notes.
