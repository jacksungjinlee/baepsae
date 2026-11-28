// ================= 소액주주 배당수익률: the switch (2026-11-23; Jack 2026-11-19 Q6 "a later PR, labelled as the 소액주주 rate") =================
// No Korean and no React here, so a later PR can flip one line.
//
// SMALL_YIELD.on   show a 차등배당 company's 소액주주 yield (data.json dytSmall: the 사업보고서's dividend per share that its own note
//                  says the small shareholders get, over today's close; fetch_data.small_holder_div) where the company page's 배당 tile,
//                  its 배당 tab and 두 종목 비교's 배당수익률 cell now say "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 …"
//                  (dvLine 3), labelled as the 소액주주 rate (C.co.div.smallBasis) with its line (C.co.div.smallLine). Off until Jack
//                  approves those two lines; with the switch on and either line still null, nothing changes either
//                  (company.js divSmallView · the screens check both). 관심 종목 follows this switch too (Jack, 2026-11-27, answer 14:
//                  "Yes, use the 소액주주 yield where it exists (관심 종목 배당수익률 condition), labelled as such."): its 배당수익률
//                  condition reads the 소액주주 yield where the all-holder yield is blank and the company page would show it, labelled
//                  on the chip, in the condition sheet and on 홈's 관심 종목 조건 row, with the line once under the card and once
//                  under the sheet's 배당수익률 field (watch.js watchSmall). 종목 순위, 내 기준으로 찾기 and plans keep the all-shareholder yield (dyt) whatever this says. 예전 뱁새
//                  shows no label (#183 review: its 배당수익률 is the report's own yield, which nobody checked to be the 소액주주 rate).
// An object, so the tests can build both states from one bundle; the app never writes to it.
export const SMALL_YIELD = { on: false };
