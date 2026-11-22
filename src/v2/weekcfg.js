// ================= 이번 주 정리: the two switches (v19.6e, docs/tasks/v19.6-records-alerts-dark.md Part E) =================
// No Korean and no React here, so a later PR can flip one line.
//
// WEEKLY_ON   the 이번 주 정리 card on 홈 (weekly.jsx). On since Jack approved the two lines that name the stocks left out of the
//             week's gain (C.weekly.leftOut, C.weekly.leftOutMore; 2026-11-22): Part E says a stock without last week's close "is left
//             out of both ends and named". false hides the card everywhere (an emergency switch; the tests build both states).
// WEEK_NV     what the card does with a Korean row whose last-week close (data.json c1w) was confirmed only through Naver's adjusted
//             series (c1wv "nv", #170 RUNBOOK §이번 주 정리: a small known risk of about 5% plus that day's after-hours difference).
//             Jack, 2026-11-22: "Use Naver only for a stock missing from our own data, and then with the (c) footnote" — "note":
//               "out"  treated like a stock without c1w: left out of both ends and named;
//               "use"  used like any other row;
//               "note" (in use) used, with the footnote under the card naming them (C.weekly.nvNote). Without its words "note" is
//                      read as "out" (weekly.jsx nvMode); with more than 5 such names and no capped footnote words
//                      (C.weekly.nvNoteMore, proposed) that card is worked out as under "out" (weekly.jsx cardModel). Never used
//                      without a footnote that names them all. (The pipeline taking last week's close from our own published closes
//                      first, a separate PR, only tags fewer rows: nothing here changes.)
export const WEEKLY_ON = true;
export const WEEK_NV = "note";
export const NV_MODES = ["out", "use", "note"];
