// ================= 이번 주 정리: the two switches (v19.6e, docs/tasks/v19.6-records-alerts-dark.md Part E) =================
// No Korean and no React here, so a later PR can flip one line.
//
// WEEKLY_ON   the 이번 주 정리 card on 홈 (weekly.jsx). false: built and tested (tests/test_v196e_weekly.py, the smoke scenes build
//             it with the switch on), never shown. It stays off until Jack approves the line that names the stocks left out of the
//             week's gain (C.weekly.leftOut, proposed in docs/tasks/v18.3-new-strings-pending.md): Part E says a stock without
//             last week's close "is left out of both ends and named", and the card cannot name it without that line.
// WEEK_NV     what the card does with a Korean row whose last-week close (data.json c1w) was confirmed only through Naver's adjusted
//             series on a backup-day week (c1wv "nv", #170 RUNBOOK §이번 주 정리: a small known risk of about 5% plus that day's
//             after-hours difference). Jack has not decided yet:
//               "out"  (default) treated like a stock without c1w: left out of both ends and named;
//               "use"  used like any other row;
//               "note" used, with a footnote under the card (C.weekly.nvNote; its wording waits for Jack, so until then nothing
//                      is shown and the console says so).
export const WEEKLY_ON = false;
export const WEEK_NV = "out";
export const NV_MODES = ["out", "use", "note"];
