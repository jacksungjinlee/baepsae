# 뱁새 2.0 "say why" audit (for the design chat)

**Jack's rule (2026-11-08):** whenever 뱁새 adjusts, hides, leaves out, estimates or can't show something, the screen says what happened and why, in one short line.

**What was audited:** every 2.0 screen in `src/v2/` and `src/copy/v2.js` (app.html): 홈 (first visit, returning, stale, failed), 포트폴리오 (built and 가진 종목 portfolios, 추가로 넣을 돈, records), 포트폴리오 만들기 (시작 · 기준 · 빼기 · 조건 · 후보 고르기 · 매수 계획 · 샀어요), 가진 종목 넣기 and 점검, 왜 움직였나, 회사 pages (#stocks/CODE: 요약 · 실적 · 가치 · 배당 · 공시 · 가치 자세히 · 실적 자세히), 종목, 시장, 소개, menus, the preview page.

**Base:** `origin/main` e0dbc23 (PR #83). Also read `claude/v19.3e-home` a2eb233 (draft PR #85, new 홈 and company pages). The **#85** column says where that branch differs.

**Counts:** measured on today's live data (published 2026-11-08 01:49 KST, prices of 11월 6일): 2,470 Korean company pages (59 of them 우선주), 740 US company pages. "always" = every visit; "user data" = depends on the user's own portfolio.

**Priority:** high = a user could take a number or a claim as complete or live when it isn't. Medium = something is missing or adjusted and the screen says nothing (or only half). Low = rare or minor.

**Nothing here is approved.** Proposed lines reuse approved wording where it exists (marked "approved"). The "Same line as" column groups rows one line could serve (see the list under the table).

## The table

| # | Pri | Screen (route · card) | Trigger | Current text (verbatim) | Says why? | Proposed line | Today | #85 | Same line as |
|---|---|---|---|---|---|---|---|---|---|
| 1 | high | 회사 #stocks/CODE · 요약 · 재무 경고 (amber row and its sheet) | A warning fired, but 이자보상배율 is switched off in the pipeline for every company until the DART re-read | "재무 경고 신호 {n}개" + the list. Nothing about 이자보상배율 | no (the count reads as all four checks) | Under the list: "이자보상배율은 계산 방법을 고치는 동안 잠시 빼 두었어요." | 745 KR pages | same | D4 |
| 2 | high | 포트폴리오 만들기 #portfolio/build · 매수 계획 · 연 배당금 | The plan holds US stocks. Their dividend is Yahoo's current rate made into a year, not the past year | "연 배당금 (지난 1년 기준)" · "세전 금액이에요" | no (label says past year) | Add the approved 점검 line: "미국 종목은 최근 배당을 1년치로 환산한 값이에요." | every plan with US stocks | same | – |
| 3 | high | 홈 #home · 오늘 볼 것 (#85 only) | Filing rows come only from disc.json, which loads only after a company page is opened in this visit. Without it, the calm card can still show | No filing rows, and "오늘은 할 일이 없어요" | no (claims nothing to look at; filings were never checked) | Fix first (load disc.json on 홈). Until then: "공시는 회사 페이지를 한 번 연 뒤에 보여 드려요." and no calm card | every 홈 visit before a company page is opened (the calm card: users with only 가진 종목 portfolios) | #85 only | – |
| 4 | high | 포트폴리오 · 홈 · 가진 종목 portfolio rule tile "한 종목 {x}% 이하" / "한 업종 {x}% 이하" | Share is just over the limit (e.g. 30.4% against 30%) and is rounded to a whole % | "최대 30%" with the ! mark, or "{group}이 30%예요. 내 규칙은 30%까지예요." | no (the number contradicts the !) | No new words: show one decimal when rounding hides the break | user data | fixed on #85 (limitPct) | – |
| 5 | high | 포트폴리오 만들기 · 기준 step · 내 점수 meter | The count already leaves out stocks under 5억 daily trading value and 우선주. The 5억 line appears only on the next step (빼기) | "지금 기준이면 회사 {n}개가 남아요" | no | "거래대금이 하루 5억원보다 적은 종목과 우선주는 처음부터 빼고 셌어요." | 1,364 of 2,411 KR companies (57%) under 5억 · 59 우선주 | same | D5 |
| 6 | med | 회사 · 요약 · 재무 경고 card | No warning fired, but 이자보상배율 is off (or another check had no input), so nothing can be claimed | nothing shown (card hidden) | no | Reuse approved head "확인한 재무 경고 신호는 없어요" with the new sub: "이자보상배율은 계산 방법을 고치는 동안 잠시 빼 두었어요." When another check also had no input: "필요한 자료가 없어 재무 경고 신호를 다 확인하지 못했어요." | 1,663 KR pages (1,423 with the other three checks run, 240 with fewer) | same (chips only when the card shows) | D4 |
| 7 | med | 포트폴리오 · 홈 hero (#85) · 점검 headline · rule tile "재무 경고 0개" | Any Korean non-financial holding (이자보상배율 off) or any US stock / ETF | "확인하지 못했어요" | no | KR: "이자보상배율을 잠시 빼 두어 확인하지 못했어요" · US/ETF: "미국 종목과 ETF는 아직 확인하지 않아요" | almost every 가진 종목 portfolio (삼성전자 + 현대차 → unknown) | same | D4, D7 |
| 8 | med | 홈 verdict band · 포트폴리오 card · 왜 움직였나 · #85 hero | Any 준비 중 rule (감사의견 · 대규모 인수 · 횡령·배임 are 준비 중 for every stock) | "아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요" | no | "자동으로 확인할 자료가 아직 없는 규칙이 {n}개 있어요" | every built portfolio | same | D6 |
| 9 | med | 포트폴리오 · {name} 규칙 보기 · 매수 계획 · 내 투자 규칙 · 회사 · 다시 볼 조건 · 왜 움직였나 | A rule shown as 준비 중 | "{rule}" · "아직 자동으로 확인할 수 없어요" · [준비 중] | no | 감사의견 문제 · 본업과 상관없는 대규모 인수 · 횡령·배임 공시: "이 공시는 아직 자동으로 읽지 못해요." · CET1 · 지급여력비율: "이 비율은 아직 데이터에 없어요." · 배당 삭감 (history not comparable): "주식 수가 바뀌어 작년 배당과 비교할 수 없어요." | every held stock (3 disclosure rules each) · banks · insurers · 156 KR payers not comparable | same | D6, D3 |
| 10 | med | 회사 · 요약 · 배당 tile, 배당 tab (known gap) | Korean payer whose dividend per today's share could not be verified after a share-count change (divSt nc · nd): no 배당수익률, no 100만원어치, no 배당성향 | Tile: "배당을 줘요" (no number) · Tab: "배당을 줘요" and nothing else | no | Tile: "주식 수가 바뀌어 수익률은 확인하지 못했어요" · Tab: "주식 수가 바뀌어 1주당 배당을 맞춰 보지 못했어요. 그래서 배당수익률은 빼 두었어요." | 70 KR pages (69 nc/nd) | same | D3 |
| 11 | med | 회사 · 배당 tab | Payer whose history is not comparable (nc · nd) but today's yield is verified: no trend headline, no bars | "배당을 줘요" + yield | no (why no trend) | "주식 수가 고르지 않게 바뀌어 해마다 배당을 비교하지 않았어요." | 87 KR pages | same | D3 |
| 12 | med | 포트폴리오 만들기 · 후보 고르기 · 근거 수치 | 배당수익률 row dropped for an unverified KR payer | nothing (row missing) | no | Row "배당수익률" with "확인하지 못했어요" plus the D3 reason | up to 70 stocks | same | D3 |
| 13 | med | 매수 계획 · 점검 · 연 배당금 | Unverified KR payer left out of the total | "배당을 확인하지 못한 종목 {n}개({names})는 빼고 계산했어요." | partly (why is circular) | "주식 수가 바뀌어 배당을 맞춰 보지 못한 종목 {n}개({names})는 빼고 계산했어요." | user data | same | D3 |
| 14 | med | 회사 · 요약 · 출렁임 tile, 가치 tab (출렁임 card hidden) (known gap) | No β (too little price history: new listings, trading halts) or β error above 0.5 | Tile: "자료가 없어요" · Tab: nothing | no | No β: "주가 기록이 모자라 계산하지 못했어요." · Big error: "오차가 너무 커서 보여 드리지 않아요." | 71 no β (KR 59, US 12) · 5 big error | same | D2 |
| 15 | med | 회사 · 요약 · 실적 tile, 실적 tab, 실적 자세히 | corp.json has no 영업이익 for the 3 years (often a data gap, see below) | "자료가 없어요" · tab shows only "{year}년 사업보고서 기준" | no | KR: "사업보고서에서 영업이익을 찾지 못했어요." · US (no revenue growth): "야후 파이낸스 자료에 매출 증가율이 없어요." | 228 KR (incl. 삼성SDI, 고려아연, 현대로템) · 17 US | same | D1 |
| 16 | med | 회사 · 요약 · 가치 tile, 가치 tab | No PBR | "자료가 없어요" | no | KR: "사업보고서 자료가 없어 PBR을 계산하지 못했어요." · US: "야후 파이낸스 자료에 PBR이 없어요." | KR 164 (59 우선주) · US 57 (ABBV, BKNG …) | same | D1, D5 |
| 17 | med | 회사 · 요약 · 배당 tile, 배당 tab | No 주당 배당 in the data | "자료가 없어요" | no | "사업보고서에서 주당 배당을 찾지 못했어요." (우선주: D5) | 81 KR (59 우선주 incl. 삼성전자우, 22 others incl. KCC) | same | D1, D5 |
| 18 | med | 회사 · 실적 tab · 주가는 무엇으로 움직였나 | An input is missing (not a loss year) | "자료가 없어요" | no | No 3-year price: "3년 주가 기록이 없어 나눠 볼 수 없어요." · Report data: "사업보고서 자료가 모자라 나눠 볼 수 없어요." | 367 KR (153 no 3-year price, 214 report data) | same | D1, D2 |
| 19 | med | 회사 · 가치 tab · 지금 가격이 가정하는 것 | No 순이익 in corp.json | nothing (card hidden) | no | Keep the card: "사업보고서에서 순이익을 찾지 못해 계산하지 못했어요." | 229 KR | same | D1 |
| 20 | med | 회사 · 가치 tab · 지금 가격이 가정하는 것 (#85 only) | 2년 전 순이익 missing or 0 or below: the "지난 2년 실제 이익" bar and its sentence are dropped | nothing | no | "2년 전 순이익이 없거나 적자라 지난 2년과 비교하지 않았어요." | 166 KR (of 924 with a number) | #85 only | – |
| 21 | med | 회사 · 배당 tab · 배당성향 (#85: 이익 중 얼마를 배당으로 줬나요?) | 순이익 0 or below, or cash dividends above 순이익 | nothing | no | "순이익이 0 이하라 배당성향을 계산하지 않았어요." · "배당금이 순이익보다 많아 배당성향은 빼 두었어요." | 251 KR (163 · 88) | same hide rule, new card | – |
| 22 | med | 회사 · 우선주 pages (whole page) | 우선주 rows carry no report year, PBR, 주당 배당 or 실적 | "자료가 없어요" on most tiles, "–" on every rank | no | One line under the header: "우선주라 회사 숫자는 보통주 페이지에서 볼 수 있어요." | 59 pages (삼성전자우, 현대차2우B …) | same | D5 |
| 23 | med | 회사 · 요약 · 내 기준과 맞는 정도 (and its sheet) | No input for that 기준, or the stock is not ranked (우선주) | "–" | no | One note under the rows: "–는 자료가 없어 순위를 매기지 않은 칸이에요." · 우선주: "우선주는 순위를 매기지 않아요." | 622 pages with at least one "–" · 48 all "–" | same | D8, D5 |
| 24 | med | 회사 · 공시 tab | More than 10 reports in 90 days: the list stops at 10, the count covers all | "최근 90일 임원·주요주주 지분 변동 보고 {n}건" + 10 rows | no | Under the list: "가장 최근 10건만 보여 드려요." | 59 KR pages (up to 80 reports) | same | – |
| 25 | med | 회사 · US pages (요약 · 가치 · tab bar) | No 재무 경고, no 지금 가격이 가정하는 것, no 공시 tab, no 실적 자세히, no EV/EBITDA · P/영업현금흐름, no industry growth comparison | nothing (실적 and 배당 already have their approved "…SEC 자료를 더한 뒤에…" lines) | no | Same approved pattern: "재무 경고 신호와 공시는 미국 공시(SEC) 자료를 더한 뒤에 보여 드려요." · 가치: "지금 가격이 가정하는 것은 미국 공시(SEC) 자료를 더한 뒤에 보여 드려요." | 740 US pages | same | D7 |
| 26 | med | 홈 · portfolio strip "오늘 {pct}" (#85: "오늘 {amount} ({pct})") | Portfolio holds a US stock (yesterday's rate is not in the data), or a holding has no change today, or a typed-amount holding | nothing (the 오늘 figure is just missing) | no | US: "어제 환율 자료가 없어 오늘 변화는 계산하지 않았어요." · Other: "오늘 등락률이 없는 종목이 있어 오늘 변화는 계산하지 않았어요." | every portfolio with a US stock | same rule, new card | – |
| 27 | med | 포트폴리오 · 홈 · 가진 종목 portfolio 원금 · 수익 | Any holding without 평균 단가 (the field is optional) | nothing | no | "평균 단가를 넣지 않은 종목이 있어 원금과 수익률은 계산하지 않았어요." (same shape as approved deck.noFx) | user data | 홈 on #85 already says it ("평균 단가를 넣은 {n}종목 기준"); 포트폴리오 tab still nothing | D9 |
| 28 | med | 포트폴리오 만들기 · 조건 · 비중 정하는 방식 | 공개매수·합병 handling is not built, but the sentence says it happens | "공개매수·합병 같은 일이 걸린 종목은 어떤 방식을 골라도 적게 담아요." [준비 중] | no (reads as active) | "공개매수·합병 같은 일은 아직 자동으로 확인하지 못해 비중에 반영하지 않아요." | always | same | D6 |
| 29 | med | 가진 종목 넣기 · 점검 #portfolio/import · headline | 우선주, ETF, bond/gold funds, stocks not in the data get no 기준 score | "기준 점수를 매길 수 없는 종목 {n}개({names})는 비중에만 넣었어요." | partly (no why) | "우선주·ETF처럼 기준 점수가 없는 종목 {n}개({names})는 비중에만 넣었어요." | user data | same | D5 |
| 30 | med | Every list or total with a US stock priced at an earlier close (홈, 포트폴리오, 종목, 후보 고르기, 추가로 넣을 돈) | US stock whose latest close did not come in (pxd) | "{names} 가격은 {md} 종가예요." | partly (no why, no word that its 오늘 change is left out) | "{names}는 그 뒤 종가를 받지 못해 {md} 종가로 계산했어요." | 0 today | same | – |
| 31 | med | 가진 종목 넣기 · 금액으로 넣기, then 포트폴리오 rows | Amount is turned into shares at that day's close; afterwards the value moves with the price and no quantity is shown | "수량 대신 금액" (button) · later nothing | no | "넣은 금액은 그날 종가로 주식 수로 바꿔 두었어요." | user data | same | – |
| 32 | low | 포트폴리오 · 홈 · 가진 종목 rule tiles 한 종목 / 한 업종 / 내 기준 | A holding has no price today, no 업종 for any holding, or no holding can be scored | "확인하지 못했어요" | no | "오늘 가격이 없는 종목이 있어 확인하지 못했어요" · "업종 정보가 없어 확인하지 못했어요" · "기준 점수를 매길 종목이 없어 확인하지 못했어요" | 0 today | same | – |
| 33 | low | 매수 계획 · 조건 step · 점검 · 2022 note | Holdings whose β exists but whose error is above 0.5 are counted as "no data" | "일부 종목(비중 {pct}%)은 베타·변동성 자료가 없어요. 위험 수치는 나머지 종목으로 계산했어요." | partly (reason wrong for those) | "일부 종목(비중 {pct}%)은 베타가 없거나 오차가 너무 커요. 위험 수치는 나머지 종목으로 계산했어요." | 5 stocks | same | D2 |
| 34 | low | 포트폴리오 만들기 · 조건 · 2022년 같은 해가 오면 | Any sizing method cannot give a 2022 figure: the whole row is dropped | nothing | no | Reuse approved plan.riskHalf / riskNone ("…위험 수치를 계산할 수 없어요.") | user choices | same | – |
| 35 | low | 점검 · 포트폴리오 전체로 보면 · 종목별로 보면 · 비중을 바꿔 보면 | No input for that 기준 | "–" (screen reader: "데이터 없음") | no | Legend: "–는 자료가 없어 순위를 매기지 않은 칸이에요." | user data | same | D8 |
| 36 | low | 포트폴리오 · KOSPI comparison boxes | macro.json missing, KOSPI history ends on another day, bought before the 3-year history | nothing | no | "같은 기간 코스피 기록이 없어 비교하지 못했어요." | 0 today | same | D9 |
| 37 | low | 홈 (main) · portfolio strip 수익률 | A US purchase saved without a rate (old records) | nothing on 홈 (포트폴리오 says approved deck.noFx) | no | Show approved deck.noFx on 홈 too | old records only | 홈 rebuilt, same gap | D9 |
| 38 | low | 포트폴리오 · 홈 · portfolio value | A held stock has no price today: the value disappears | nothing (#85: the whole money card is left out) | no | "{names}의 오늘 가격이 없어 평가 금액을 계산하지 못했어요." | 0 today | card dropped | – |
| 39 | low | 포트폴리오 · 홈 · built portfolio with a sale or imported row | 원금, return and KOSPI wait for the lot maths (v19.6a) | nothing | no | "판 기록이 있어 원금과 수익률은 아직 계산하지 않아요." | 0 (no screen makes a sale yet) | same | D9 |
| 40 | low | 포트폴리오 · 홈 · stale data | Values, weights and 추가로 넣을 돈 are hidden too | "데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요" | partly (says no check, not that amounts are hidden) | "데이터가 {n}일째 갱신되지 않아 오늘은 점검도, 금액 계산도 하지 않았어요" | stale days | same | – |
| 41 | low | 왜 움직였나 #home/why | Data turns stale or fails, or the stock leaves the data while the page is open | empty page (back button only) | no | Reuse approved today.stale / app.loadFail / co.notFound | rare | same | – |
| 42 | low | 회사 · header (#85 also 홈 가진 종목 change cell) | No change today (trading halted or change missing) | price + "{md} 종가", no % | no | "오늘 등락률은 받지 못했어요." | 4 (STX, 인지디스플레, 에쎈테크: no trading · 한진칼우) | same | – |
| 43 | low | 회사 · header · 52주 range bar | 52-week low/high missing | nothing | no | "52주 주가 기록이 모자라 범위를 그리지 않았어요." | 29 | same | D2 |
| 44 | low | 회사 · 실적 tab · 업종과 매출 증가 비교 | Fewer than 5 peers whose growth was calculated the same way | nothing | no | "같은 방식으로 계산한 업종 회사가 5개보다 적어 비교하지 않았어요." | 317 KR | same | – |
| 45 | low | 회사 · 가치 tab (main) · 지금 가격이 가정하는 것, second bar | 매출 증가율 basis unclear: bar dropped | nothing | no | (replaced on #85 by row 20) | 15 KR | replaced | – |
| 46 | low | 회사 · 가치 자세히 · 업종 지도 | Fewer than 5 peers (map hidden) · ROE outside the peers' range (no sentence) | nothing | no | "업종 회사가 5개보다 적어 지도를 그리지 않았어요." · "ROE가 업종 범위 밖이라 추세선과 비교하지 않았어요." | 265 · 146 KR | same | – |
| 47 | low | 회사 · 요약 · 실적 tile | Profit this year but a loss two years ago: the amount is shown instead of the 2-year change (tab: no "1년 전보다" after a loss year) | "영업이익 {x}" | no | "2년 전이 적자라 금액으로 보여 드려요." | 219 KR | same | – |
| 48 | low | 회사 · 내 기준과 맞는 정도 sheet | 업종 안에서 switch hidden (group under 5 or no group) | nothing | no | "업종 회사가 5개보다 적어 업종 안 순위는 없어요." | 10 | same | – |
| 49 | low | 회사 · US header (#85 only) | $ price converted to 원 | main: "원화는 {md} 환율 {fx}원으로 바꾼 값이에요." (says why) · #85: "약 {won} · 환율 {fx}원" | #85: partly (rate's date dropped) | Keep the date: "약 {won} · {md} 환율 {fx}원" | 740 US pages | differs | – |
| 50 | low | 회사 · 요약 · 보유 줄 (main) | Stock held only in a 가진 종목 portfolio | nothing | no | (fixed on #85: "내 포트폴리오의 {x}%") | user data | fixed | – |
| 51 | low | 점검 · date line | Korean holdings use different report years | "{date} 종가" (the "한국 {year}년 사업보고서" piece is dropped) | no | "회사마다 사업보고서 연도가 달라요." | user data | same | – |
| 52 | low | 시장 #market · 홈 · 시장 한눈에 | A value missing or undated | "–" | no | Under the tile: "자료를 받지 못했어요" | 0 today | same | D8 |
| 53 | low | 시장 · 국고채 3년 · 원/달러 tiles | The data has no daily change for these two | nothing (other tiles show a %) | no | "하루 변화 자료는 없어요." | always | same | – |
| 54 | low | 포트폴리오 만들기 · 빼기 · 투자주의·관리종목 · 상장 2년 미만 · 중국 매출 · 담배·술·도박 | Switch not built | [준비 중] | no | "아직 자료가 없어 켤 수 없어요." | always | same | D6 |
| 55 | low | 포트폴리오 만들기 · 기준 · 배당 성장 card | Card not built | "준비 중이에요" | no | "배당 증가율 자료가 아직 없어요." | always | same | D6 |
| 56 | low | 포트폴리오 만들기 · 가진 종목 넣기 (whole screen) | Data lacks a field the builder needs | 뱁이 + [준비 중] | no | "필요한 데이터가 아직 다 들어오지 않았어요." | 0 today | same | – |
| 57 | low | 가진 종목 넣기 · 종목 rows | Stock has no price today: 점검 button stays off | nothing | no | "오늘 가격이 없는 종목은 넣을 수 없어요." | 0 today | same | – |
| 58 | low | 소개 #about · 숫자 줄 | Data stale: figures row hidden | nothing | no | none needed (no number is shown); or "데이터가 멈춘 동안은 숫자를 빼 두어요." | stale days | same | – |
| 59 | low | 미리 보기 (app-preview.html) · 회사 page | 공시 tab, glossary, sources, old-app links absent | nothing ("예시 데이터" label only) | no | "미리 보기에는 공시가 없어요." | preview only | same | – |
| 60 | low | 종목 #stocks · 최근 본 종목 | A recently viewed stock left today's data | nothing (row dropped) | no | "오늘 데이터에 없는 종목은 빼고 보여 드려요." | rare | same | – |

## One line for several rows (duplicates)

- **D1** "사업보고서에서 {항목}을 찾지 못했어요." (영업이익 · 주당 배당 · 순이익; PBR as "사업보고서 자료가 없어 PBR을 계산하지 못했어요.") → rows 15, 16, 17, 18, 19.
- **D2** "주가 기록이 모자라 계산하지 못했어요." (and "3년 주가 기록이 없어…", "52주 주가 기록이 모자라…") → rows 14, 18, 33, 43.
- **D3** "주식 수가 바뀌어 1주당 배당을 맞춰 보지 못했어요." → rows 9 (배당 삭감), 10, 11, 12, 13.
- **D4** "이자보상배율은 계산 방법을 고치는 동안 잠시 빼 두었어요." → rows 1, 6, 7. Remove all three lines when the v19.1f re-read turns the check back on.
- **D5** 우선주 lines ("우선주라 회사 숫자는 보통주 페이지에서 볼 수 있어요." · "우선주는 순위를 매기지 않아요." · "…우선주는 처음부터 빼고 셌어요.") → rows 5, 16, 17, 22, 23, 29.
- **D6** "자동으로 확인할 자료가 아직 없어요" family → rows 8, 9, 28, 54, 55.
- **D7** "…미국 공시(SEC) 자료를 더한 뒤에 보여 드려요." (approved pattern) → rows 7 (US part), 25.
- **D8** "–는 자료가 없어 순위를 매기지 않은 칸이에요." → rows 23, 35, 52.
- **D9** "{이유}가 있어 원금과 수익률은 계산하지 않았어요." (shape of approved deck.noFx) → rows 27, 36, 37, 39.

## Data problems, not wording gaps (for the pipeline, not the design chat)

1. **이자보상배율 is off for every company** (corp.json flWhy.icr "off" on 2,385 rows; pipeline ICR_OFF). This alone causes rows 1, 6 and 7. The real fix is the v19.1f re-read. The lines above only cover the gap.
2. **DART figures missing for big companies.** 81 Korean common stocks have a report year but no statements at all (카카오뱅크, 삼성증권, 넷마블, 롯데케미칼, 아시아나항공, 코오롱인더 …). 59 more have revenue but no 영업이익 for any of three years (삼성SDI, 고려아연, 현대로템, SKC, 원익IPS …; 32 of them do have 순이익). This drives most of rows 15 to 19. It looks like a parsing gap (account names), so worth a pipeline check before writing lines for it.
3. **우선주 carry no company figures** (59 pages: no report year, PBR, 주당 배당, 실적). 삼성전자우 shows "배당 · 자료가 없어요" although it pays a dividend. The pipeline could copy the common stock's figures.
4. **22 common stocks with no 주당 배당** (KCC, KCC글라스, 네패스 …), 10 of them with a report year.
5. **#85 홈 filings** depend on disc.json being loaded by a company page first (row 3). That is a loading problem, not wording.
6. **main rounding bug** in the 가진 종목 rule tiles (row 4), already fixed on #85.
7. **3 halted stocks** (STX, 인지디스플레, 에쎈테크: 0 trading value, no daily change) show a price as "11월 6일 종가" with nothing saying trading is halted.
8. **Not a bug, but big:** 1,364 of 2,411 Korean companies (57%) fall under the 5억 trading-value floor and never reach 포트폴리오 만들기 (row 5).

## Already says what happened and why (no change needed)

- 오늘 데이터에 없는 종목 {n}개({names})는 빼고 계산했어요. · 빠진 종목이 다시 들어오거나 직접 뺄 때까지 비중은 점검하지 않아요.
- 환율 기록이 없는 미국 종목이 있어 원금과 수익률은 계산하지 못했어요.
- 배당 정보가 없는 종목 {n}개는 0원으로 계산했어요.
- 일부 종목(비중 {pct}%)은 베타·변동성 자료가 없어요… · …절반을 넘어 위험 수치를 계산할 수 없어요. · 담은 종목 모두 … 계산할 수 없어요. (see row 33 for one wording fix)
- 2022: 오차가 너무 커서 추정하지 않았어요. · …어림한 값이에요 / 범위예요 · 실제 결과가 아니라 추정이에요. · 범위는 베타를 계산할 때 생기는 오차를 반영했어요. · 출처 줄
- β band: 과거 주가로 계산한 범위예요 (값이에요). 앞으로도 같다는 뜻은 아니에요.
- 지금 가격이 가정하는 것: 예측이 아니라 지금 가격을 거꾸로 읽은 숫자예요… · 30% / 60% edge lines · 순이익이 0 이하라 이 계산을 할 수 없어요.
- 주가는 무엇으로 움직였나: 적자인 해가 있어서 이익과 눈높이로 나눌 수 없어요. · 지난 3년을 둘로 나눠 본 것뿐, 예측이 아니에요.
- Split-adjusted dividends: 주식 수가 달라진 만큼 지금 1주 기준으로 다시 계산한 금액이에요… · …{years}년 배당은 지금 1주 기준으로 다시 계산했어요.
- 배당: {fy}년 사업보고서 주당 배당과 오늘 주가로 계산했어요. · 야후 파이낸스의 배당수익률로 계산했어요. · 1년에 1,000원이 안 돼요 · 세전 금액이에요 · 작년과 비교할 기록이 없어요 · 미국 종목은 최근 배당을 1년치로 환산한 값이에요. (점검)
- 업종 비교 자료가 부족해요 · 업종과 비교할 자료가 부족해요 (PBR peers under 5; 21 US pages)
- 재무 경고: 확인한 재무 경고 신호는 없어요 + 이자 비용 sub · 금융회사라 / 지주회사라 … 확인해요. · 현금흐름표의 이자 지급액으로 계산했어요.
- 공시: 금액은 보고된 주식 수에 지금 주가를 곱해 어림한 값이에요. · 증여, 상속, 주식 보상… · 5% 이상 대량보유 보고 기준이에요.
- US: 미국 종목은 현지 기준 {md} 종가예요. · 원화는 {md} 환율 {fx}원으로 바꾼 값이에요. (main) · {md} 종가와 환율 {fx}원 기준이에요… · 미국 종목은 1달러 {fx}원으로 계산 · 미국 종목은 달러로 계산한 수익을 오늘 환율로 바꿨어요. · 연도별 실적은 / 주당 배당과 연도별 배당은 미국 공시(SEC) 자료를 더한 뒤에 보여 드려요.
- 고른 기준 카드가 없어서 가치·배당 카드를 먼저 보여 드려요. · ETF·펀드는 회사 페이지가 없어요.
- 포트폴리오 만들기: 자료가 없어 빠진 종목 {n}개 · 하루 평균 거래대금이 5억원보다 적은 종목은 항상 제외해요… (빼기 step) · 기준선 messages (few · short · zero · indFix · clash) · 같은 업종은 2개까지… · 거래대금이 적어 줄임 · {ind} 업종은 최대 1/3 · 1주 가격이 비싼 종목은… · {n}종목을 1주씩 사기에도 부족해요… · 점수 기준을 거치지 않고 직접 담은 종목이에요.
- 계획한 {n}종목 중 {m}종목만 샀어요. 목표 비중은 산 종목끼리 다시 나눠 계산해요.
- {item} 자료를 받지 못해 확인이 필요해요 · 특별배당이나 액면분할 때문인지 / 지난번 배당에 특별배당이 들어 있었는지 확인해 주세요.
- 추가로 넣을 돈: 규칙에 걸렸거나 이미 많이 담긴 종목은 사지 않아요. · 이 금액으로는 살 수 있는 종목이 없어요… · 지금은 새로 살 종목이 없어요…
- #85 홈: 산 가격보다 … · 평균 단가를 넣은 {n}종목 기준
- Stale and failed: 데이터가 {n}일째 갱신되지 않아 / 갱신이 늦어지고 있어 오늘은 점검하지 않았어요 · 데이터가 {n}일째 갱신되지 않았어요. {date} 종가 기준 결과예요. · {n}일째 갱신이 멈췄어요 / 갱신이 늦어지고 있어요 (the app cannot know why a publish stopped) · 데이터를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요. (cause not knowable to a user; keep)
- 기록: 이 기기에서는 기록을 저장할 수 없어요… · 이전에 저장한 기록을 읽지 못해 따로 보관해 두었어요. · 다른 창에서 저장한 내용과 기록을 합쳤어요… · 기록 파일을 읽지 못했어요… · 미리 보기에서 만든 기록은 여기서 불러올 수 없어요. · {n}번째 줄은 종목을 찾지 못해 / 수량을 읽지 못해 넣지 않았어요. · '{q}'에 맞는 종목이 여러 개예요…
