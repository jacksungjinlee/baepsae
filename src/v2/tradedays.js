// ================= Trading days for the late check (Jack, 2026-11-19) =================
// "When data is late, still run the portfolio check on the last official close, with its date ("11월 16일 종가로
// 점검했어요."), for up to 5 trading days. Skip it only after that." (Jack, 2026-11-19)
// The weekday closures of the Korean exchange (KR) and the NYSE (US), copied from data/market_holidays.csv (the pipeline's
// own table: fetch_data.py next_session · nextPub · staleAfter). tests/test_late_check.py fails when the two differ: after
// a table edit (a 임시공휴일, next year's rows every December: RUNBOOK) copy the rows here too and rebuild app.html.
// Days outside the table count as trading days on every weekday: a missing holiday can only make the late check stop
// earlier, never later. No Korean here.
export const CAL_START = "2026-01-01";
export const CAL_END = "2027-12-31";
export const CLOSED = {
  KR: new Set([
  "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02", "2026-05-01", "2026-05-05", "2026-05-25",
  "2026-06-03", "2026-07-17", "2026-08-17", "2026-09-24", "2026-09-25", "2026-10-05", "2026-10-09", "2026-12-25",
  "2026-12-31", "2027-01-01", "2027-02-08", "2027-02-09", "2027-03-01", "2027-05-03", "2027-05-05", "2027-05-13",
  "2027-07-19", "2027-08-16", "2027-09-14", "2027-09-15", "2027-09-16", "2027-10-04", "2027-10-11", "2027-12-27",
  "2027-12-31",
  ]),
  US: new Set([
  "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
  "2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
  "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
  ]),
};

const ISO = /^\d{4}-\d{2}-\d{2}$/;
const dayNo = (iso) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))) / 86400000;
const isoOf = (n) => new Date(n * 86400000).toISOString().slice(0, 10);
// A real calendar date written YYYY-MM-DD (2026-02-30 is not one).
export const isDay = (v) => typeof v === "string" && ISO.test(v) && isoOf(dayNo(v)) === v;

// Is this date (YYYY-MM-DD) a trading day of the market ("KR" · "US")? Weekends never are; inside the table its closures
// are not; outside the table every weekday is (the stricter side).
export function isTradingDay(iso, market) {
  const w = new Date(dayNo(iso) * 86400000).getUTCDay();
  if (w === 0 || w === 6) return false;
  if (iso < CAL_START || iso > CAL_END) return true;
  return !CLOSED[market].has(iso);
}

// The trading days d of the market with from < d <= to (YYYY-MM-DD each), or null when either date cannot be read. A day
// counts from its first minute in Korea (00:00 KST), before its market opens: the stricter side. 0 when to <= from.
export function tradingDaysAfter(from, to, market) {
  if (!isDay(from) || !isDay(to) || !CLOSED[market]) return null;
  let n = 0;
  for (let d = dayNo(from) + 1, end = dayNo(to); d <= end; d++) if (isTradingDay(isoOf(d), market)) n++;
  return n;
}

// ---------------- the late check (rules.js checkState) ----------------
// How late the closes in data.json are on the Korean date today (YYYY-MM-DD): the trading days that began after each
// market's own last close, the larger of the two (KRX days after pxDate, NYSE days after usPxDate; a portfolio can hold
// both). -> { n, kr, us } or null when a date cannot be read (then nothing is checked on late data, as before).
export const LATE_CHECK_DAYS = 5;
export function lateDays(data, today) {
  if (!data || !isDay(today)) return null;
  const kr = tradingDaysAfter(data.pxDate, today, "KR");
  const us = tradingDaysAfter(data.usPxDate, today, "US");
  if (kr == null || us == null) return null;
  return { n: Math.max(kr, us), kr, us };
}
