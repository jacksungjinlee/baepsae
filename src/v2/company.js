// ================= 2.0 company page (v19.1a, docs/tasks/v19.1-company-page.md Parts A-F) =================
// Pure functions, no React and no Korean text: the screens (src/v2/company.jsx, cotabs.jsx) turn the codes returned
// here into copy from src/copy/v2.js. Unit tests: tests/test_v2_company.py (run through Node).
//
// Every tile phrase is chosen by a fixed rule from the same numbers the tile shows (Part B), never by free text:
//   rule "na" = an input is missing ("판단할 자료가 없어요"), never a guess.
// "업종" is the `ind` group (hasGroup: never "other" / "etc" / missing) inside the same market, as 왜 움직였나 uses.
// Units: corp.json op / ni / rev are 억원; KR prices are 원; US prices are $ (data.json units).
import { num, hasGroup, universe, isStockLike, CARDS, NA, cardRaw, percentileScores, growthBasis, dividendStreak, dpsAgrees, okDy,
  krDivYield, DY_MAX, KR_DIV_TREND, SPLIT_GUARD, splitGuarded, krYieldToday, exactData, krDivHistory, krDivState, divStOf, betaBand } from "./engine.js";
import { STALE_DAYS } from "../data.js";
import { GROUP_MIN } from "./track.js";
import { DCF, reverseDcf } from "./dcf.js";
import { okCode } from "./routes.js";
import { epsBase } from "../repair.js";

export { DCF, dcfPerShare, reverseDcf, okAssume } from "./dcf.js";

// ---------------- thresholds (Part B; the old app's where it says so) ----------------
export const EARN_US_BAND = 3;                 // US: g3 >= 3 -> up, <= -3 -> down, else flat
export const VALUE_CHEAP = 0.8, VALUE_DEAR = 1.25, VALUE_MIN = 5;   // PBR vs the industry median; at least 5 with a PBR
export const BETA_BIG = 1.15, BETA_SMALL = 0.85;                    // the old app's 출렁임 thresholds (corp.jsx volTxt)
export const DIV_SAME = 0.03;                  // a raise within 3% reads 비슷하게 (the old app's dpsTrend band)
export const GROWTH_SAME = 1;                  // 실적 tab: within 1%p of the industry median reads 비슷하게
export const DISC_DAYS = 90;                   // fetch_data.py DISC_DAYS: disc.json keeps 90 days of insider reports
export const MILLION = 1000000;
const EPS = 1e-9;

export const round = (v, d = 0) => { const k = Math.pow(10, d); return Math.round(v * k) / k; };
export function median(vals) {
  const a = vals.filter((v) => typeof v === "number" && Number.isFinite(v)).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

// The company of a route code: a Korean or US company share in today's data (funds are not companies). null = not found.
export function findCompany(load, code) {
  if (!load || load.status !== "ok" || !okCode(code)) return null;
  const s = load.byT.get(code);
  return s && isStockLike(s) ? s : null;
}

// The stock's industry group in its own market (the stocks that can be ranked), memoised per loaded stock list.
const groupMemo = new WeakMap();
export function groupOf(stocks, s) {
  if (!s || !hasGroup(s) || (s.cls !== "kr" && s.cls !== "us") || !Array.isArray(stocks)) return [];
  let m = groupMemo.get(stocks);
  if (!m) { m = new Map(); groupMemo.set(stocks, m); }
  const key = s.cls + "|" + s.ind;
  if (!m.has(key)) m.set(key, universe(stocks, s.cls).filter((x) => hasGroup(x) && x.ind === s.ind));
  return m.get(key);
}

// ---------------- 실적 tile ----------------
// KR: operating profit [this year, last year, two years ago] (corp.json op, 억원). A loss this year comes first (적자예요),
// then up twice / down twice, else mixed. Number: the 2-year change when the base year was a profit, else this year's
// amount (a % change from a loss, or into one, means nothing). Any year missing -> na.
export function earnKr(co) {
  const op = co && Array.isArray(co.op) ? [0, 1, 2].map((i) => num(co.op[i])) : [null, null, null];
  if (op.some((x) => x == null)) return { rule: "na", op };
  const [a, b, c] = op;
  const rule = a < 0 ? "loss" : a > b && b > c ? "up" : a < b && b < c ? "down" : "mixed";
  const pct = rule !== "loss" && c > 0 ? (a / c - 1) * 100 : null;
  return { rule, op, pct, amount: pct == null ? a : null, fy: num(co.fy) };
}

// US until v19.2: g3 is Yahoo revenueGrowth (the latest quarter vs the same quarter a year ago, fetch_data.py
// apply_us_info). Shown only with the label that says so (co.tiles.usGrowth, Jack 2026-11-05; cofmt.usGrowthText).
// Never compared with a Korean figure.
export function earnUs(s) {
  const g = num(s && s.g3);
  if (g == null) return { rule: "na" };
  return { rule: g >= EARN_US_BAND ? "up" : g <= -EARN_US_BAND ? "down" : "flat", g };
}

// ---------------- 가치 tile ----------------
// PBR vs the median PBR of the industry group (same market). The median is rounded to 2 decimals, the way it is shown,
// so the two numbers on the tile always give the phrase. Fewer than 5 with a PBR (or no group) -> few.
export function valueTile(s, group) {
  const pbr = num(s && s.pbr);
  if (!(pbr > 0)) return { rule: "na" };
  const vals = (group || []).map((x) => num(x.pbr)).filter((v) => v != null && v > 0);
  if (vals.length < VALUE_MIN) return { rule: "few", pbr, n: vals.length };
  const med = round(median(vals), 2);
  const r = pbr / med;
  return { rule: r <= VALUE_CHEAP + EPS ? "cheap" : r >= VALUE_DEAR - EPS ? "dear" : "similar", pbr, med, n: vals.length };
}

// ---------------- 배당 tile ----------------
// The Korean dividend trend (늘렸어요 · 줄였어요 · 비슷하게 · N년 연속, and the 3-year bars) is OFF (Jack, 2026-11-05) until the
// pipeline gives a split-adjusted per-share history: after a split the per-share dividend drops with no real cut, and the
// data has no per-report share count to tell the two apart. This one switch turns it back on; both states are tested.
// The switch is engine.js KR_DIV_TREND (re-exported here): the same one turns off the 배당 감소 caution and the
// dividend-cut rule of 후보 고르기 · 포트폴리오 · 홈. It lives in engine.js because engine.js and rules.js need it too and
// importing this file from them would make an import cycle.
//   off: dps > 0 -> pays (배당을 줘요) · dps 0 -> none (배당이 없어요) · missing or contradictory (dps 0 with a yield, or a
//        payer whose report says 0%) -> na (자료가 없어요, and no number is shown with it).
//   on:  the trend rules below; a yield with no earlier year to compare -> noPrev (작년과 비교할 기록이 없어요).
// v19.1b: that history now exists (dps3a, PR #50). With such a file (engine.exactData) divKr reads it: the trend is on for
// every comparable stock (engine.krDivHistory: divSt same · adj · zero) and off (pays · none · na, as above) for nc · nd,
// whatever the switch says. The switch stays for files published before v19.1b.
export { KR_DIV_TREND };

// KR yield on today's price and the interim split guard (Jack, 2026-11-05): engine.js krYieldToday · splitGuarded ·
// SPLIT_GUARD, re-exported here. They live in engine.js because the portfolio's expected dividend (engine.annualDividend)
// uses the same guard (Jack, 2026-11-05), and importing this file from engine.js would make an import cycle.
export { SPLIT_GUARD, splitGuarded, krYieldToday };
// The guard's count for the console (no silent hiding): Korean payers with a report year whose dps passes the 1/3x-3x
// check and the 30% cap but which the 1.8x guard hides. -> { hidden, of, examples: [{ t, ratio }] } (largest first, 5).
// of = Korean payers with a report year that pass the 1/3x-3x check and the cap (the ones that would show a yield).
export function splitGuardCount(stocks, coByT) {
  const hit = [];
  let of = 0;
  if (exactData()) return { hidden: 0, of: 0, examples: [] };      // exact data: no guard (divCheckCount says what was hidden)
  for (const s of stocks || []) {
    if (!s || s.cls !== "kr" || !(num(s.dps) > 0) || !dpsAgrees(s)) continue;
    const co = coByT ? coByT.get(s.t) : null;
    if ((num(s.fy) ?? (co ? num(co.fy) : null)) == null) continue;
    const y = krDivYield(s);
    if (y == null || y > DY_MAX) continue;
    of += 1;
    const dy = num(s.dy);
    if (splitGuarded(s)) hit.push({ t: s.t, ratio: dy > 0 ? Math.round((y / dy) * 100) / 100 : null });
  }
  hit.sort((a, b) => (b.ratio ?? 0) - (a.ratio ?? 0));
  return { hidden: hit.length, of, examples: hit.slice(0, 5) };
}
const d3Of = (s, co) => (s && Array.isArray(s.dps3) ? s.dps3 : co && Array.isArray(co.dps3) ? co.dps3 : null);

// Exact data (v19.1b): the console line for the split check (no silent hiding). Korean payers (dps > 0) with a report year:
// how many show a yield (dyt verified) and how many do not, and the divSt counts of all Korean stocks with one.
// -> { payers, shown, hidden, st: { same, adj, nc, nd, zero }, examples: [codes without a yield, 5] } or null (older files).
export function divCheckCount(stocks, coByT) {
  if (!exactData()) return null;
  const st = { same: 0, adj: 0, nc: 0, nd: 0, zero: 0 };
  let payers = 0, shown = 0;
  const miss = [];
  for (const s of stocks || []) {
    if (!s || s.cls !== "kr") continue;
    const co = coByT ? coByT.get(s.t) : null;
    const k = divStOf(s, co);
    if (k in st) st[k] += 1;
    if (!(num(s.dps) > 0) || (num(s.fy) ?? (co ? num(co.fy) : null)) == null) continue;
    payers += 1;
    if (krYieldToday(s) != null) shown += 1; else miss.push(s.t);
  }
  return { payers, shown, hidden: payers - shown, st, examples: miss.slice(0, 5) };
}

// trend on: dps 0 -> none · a cut (latest < last year) -> cut · 2+ raises in a row -> streak · a raise of more than 3% ->
// raised · else steady. dps missing or disagreeing with dy -> na; no earlier year on record -> noPrev when a yield is
// shown, else na; a record that disagrees with dps (dps3[0] !== dps) -> na with no yield (자료가 없어요 never beside a number).
export function divKr(s, co, trend = KR_DIV_TREND) {
  if (exactData()) return divKrExact(s, co);
  const dps = num(s && s.dps), dy = num(s && s.dy);
  const fy = num(s && s.fy) ?? (co ? num(co.fy) : null);
  const ok = dpsAgrees(s);
  const yieldPct = ok && fy != null ? krYieldToday(s) : null;      // dps 0 with no price -> null (nothing was computed)
  if (dps == null) return { rule: "na", dps: null, yieldPct: null, fy, dpsOk: false };
  if (!ok) {
    // the per-share figure and the report's yield disagree: no yield, no per-share figure. With the trend off a payer
    // (dps > 0, the report's yield not 0) still reads 배당을 줘요; a contradiction (dps 0 with a yield, or the reverse) is na.
    const pays = !trend && dps > 0 && (dy == null || dy > 0);
    return { rule: pays ? "pays" : "na", dps, yieldPct: null, fy, dpsOk: false };
  }
  if (dps === 0) return { rule: "none", dps: 0, yieldPct, fy, dpsOk: true };
  if (!trend) return { rule: "pays", dps, yieldPct, fy, dpsOk: true };
  const d3 = d3Of(s, co);
  const cur = d3 ? num(d3[0]) : null, prev = d3 ? num(d3[1]) : null;
  if (cur != null && cur !== dps) return { rule: "na", dps, yieldPct: null, fy, dpsOk: true };
  if (cur == null || prev == null) return { rule: yieldPct != null ? "noPrev" : "na", dps, yieldPct, fy, dpsOk: true };
  const base = { dps, yieldPct, fy, dpsOk: true, d3: [0, 1, 2].map((i) => num(d3[i])) };
  if (cur < prev) return { rule: "cut", ...base };
  const n = dividendStreak(d3);
  if (n >= 2) return { rule: "streak", n, ...base };
  if (cur > prev * (1 + DIV_SAME) + EPS) return { rule: "raised", ...base };
  return { rule: "steady", ...base };
}

// Exact data (v19.1b): the same rules on the split-checked history, and one rule for what is known (engine.krDivState,
// shared with the 배당 card, 후보 고르기, the plan's 연 배당금, 100만원어치 and 배당성향): the report's own yield (dy) is
// never used. dps = the latest report's dividend per TODAY's share (dps3a[0]: the report's figure divided by the exact
// split factor since, so it matches today's price and the yield shown) and yieldPct = dyt, both only when verified
// (dpsOk), the yield with a report year as before.
//   dps missing -> na · dps 0 -> none · a payer: not comparable (divSt nc · nd, or no dps3a) -> pays (배당을 줘요), never
//   a trend · comparable -> the trend rules on whole won (cut · streak · raised · steady), noPrev when last year is blank
//   and a yield is shown (else na).
function divKrExact(s, co) {
  const fy = num(s && s.fy) ?? (co ? num(co.fy) : null);
  const st = krDivState(s, co);
  if (!st) return { rule: "na", dps: null, yieldPct: null, fy, dpsOk: false };
  const yieldPct = fy != null ? st.y : null;
  if (st.zero) return { rule: "none", dps: 0, yieldPct, fy, dpsOk: true };
  // adjFrom (Jack, PR #68 B3): the report's own figure (won) when the per-share figure shown was recalculated for a share
  // count change (dpsF[0], the latest year's factor, is not 1: a split, a bonus issue or a consolidation), so the 배당 tab
  // can say what the report says. Only under the figure it describes: a stock whose latest year is unadjusted gets none,
  // even when an earlier bar is.
  const f0 = num(((s && Array.isArray(s.dpsF) ? s.dpsF : co && Array.isArray(co.dpsF) ? co.dpsF : null) || [])[0]);
  const raw = num(s && s.dps);
  const adjFrom = st.now != null && f0 != null && f0 !== 1 && raw > 0 ? raw : null;
  const view = { dps: st.now, yieldPct, fy, dpsOk: st.now != null, ...(adjFrom != null ? { adjFrom } : {}) };
  // adjYears (Jack, PR #68 2022/bars): the earlier report years (not the latest) whose bar was recalculated for a share count
  // change (that year's dpsF is not 1), oldest first, for the note under the bars. Only years that have a bar.
  const F = (s && Array.isArray(s.dpsF) ? s.dpsF : co && Array.isArray(co.dpsF) ? co.dpsF : null) || [];
  const adjYearsOf = (d3) => (fy == null ? [] : [2, 1].filter((i) => d3[i] != null && num(F[i]) != null && num(F[i]) !== 1).map((i) => fy - i));
  const d3 = krDivHistory(s, co);                          // whole won
  if (!d3 || !(d3[0] > 0)) return { rule: "pays", ...view };
  const cur = d3[0], prev = d3[1];
  if (prev == null) return { rule: yieldPct != null ? "noPrev" : "na", ...view, ...(yieldPct != null ? {} : { dps: null, dpsOk: false }) };
  const base = { ...view, d3, adjYears: adjYearsOf(d3) };
  if (cur < prev) return { rule: "cut", ...base };
  const n = dividendStreak(d3);
  if (n >= 2) return { rule: "streak", n, ...base };
  if (cur > prev * (1 + DIV_SAME) + EPS) return { rule: "raised", ...base };
  return { rule: "steady", ...base };
}

// US until v19.2: data.json has no US dividend per share, only Yahoo's yield. Missing is not "no dividend".
export function divUs(s) {
  const dy = okDy(s);
  if (dy == null) return { rule: "na", yieldPct: null };
  return { rule: dy === 0 ? "none" : "pays", yieldPct: dy };
}

// 100만원어치 가지고 있으면 (US until v19.2): 1,000,000 x yield / 100, rounded to the nearest 1,000원 (before tax).
// null = no yield.
export function perMillion(yieldPct) {
  const y = num(yieldPct);
  if (y == null || y < 0) return null;
  return Math.round((MILLION * y) / 100 / 1000) * 1000;
}
// What the 100만원 line shows: null (no yield, or no dividend) · { under: true } (a payer whose amount is below
// 1,000원: never "약 0원") · { won } (rounded to 1,000원).
export function perMillionView(yieldPct) {
  const y = num(yieldPct);
  if (y == null || !(y > 0)) return null;
  return millionView((MILLION * y) / 100);
}
const millionView = (raw) => (raw < 1000 ? { under: true, raw } : { won: Math.round(raw / 1000) * 1000, raw });

// 100만원어치 for a Korean stock (Jack, 2026-11-05): 1,000,000 ÷ today's close (data.json price, the pxDate close) × the
// latest 사업보고서's dividend per share (dps), rounded to 1,000원, before tax. null (the line is hidden) when dps or the
// price is missing, the price is not above 0, or dps is 0 (that is 배당이 없어요: divKr "none"). The dps must be the one the
// card trusts: it agrees with the same report's yield (engine.krDivYield / dpsAgrees), so a split after the report or a
// total filed in the per-share row (와이엔텍) never turns into an absurd amount; above 30% a year is not believed (DY_MAX).
// Exact data (v19.1b): the dividend per today's share (dps3a[0], data.json else corp.json) ÷ today's close, only for a
// verified payer (engine.krDivState), so the line, the yield and the per-share figure on the tab always agree.
export function perMillionKr(s, co = null) {
  if (exactData()) {
    const st = krDivState(s, co);
    return st && !st.zero && st.now != null && st.y > 0 && num(s.price) > 0 ? millionView((MILLION * st.now) / s.price) : null;
  }
  const y = krYieldToday(s);                      // null without dps, a price above 0, agreement with the report's yield, <= 30%
  if (y == null || !(y > 0)) return null;
  return millionView((MILLION * s.dps) / s.price);
}

// 배당성향 (KR), on one basis: the report's dividend per share x shares over the same report's net income (corp.json ni[0],
// 억원), so both sides are that 사업보고서 (fy). Needs dps that agrees with dy, a profit and the share count. A result
// outside 0-100% is not shown (out: the value, for the console).
// Exact data (v19.1b): the report's own totals, 현금배당금총액 over 당기순이익 (corp.json cash3[0] / ni[0], both 억원, the
// same 사업보고서), for a payer (engine.krDivState: dps above 0). No share count and no per-share figure, so no split can
// enter it, and no guess (no cross-check, no split guard). The same 0-100% rule.
// 2026-11-08 (data review of the DART re-read): for a group company the payout ratio is dividends ÷ the OWNERS' net income.
// After the re-read (corp.json epsIn, nio3 in 억원): epsIn.b "o" with nio3[0] -> cash3[0] / nio3[0] (basis "o"). "s"
// (separate statements: total = owners') and files before the re-read (no epsIn) -> cash3[0] / ni[0] exactly as before
// (basis "s"; no basis field before the re-read). "t", or "o" without nio3[0] -> still cash3[0] / ni[0], basis "total": the screen keeps the PER/EPS
// line under it (cotabs DivTab), since its line otherwise goes once the company's EPS is fixed.
export function payout(s, co) {
  if (!s || s.cls !== "kr" || !co) return null;
  if (exactData()) {
    const st = krDivState(s, co);
    const e = co.epsIn && typeof co.epsIn === "object" ? co.epsIn : null;
    const nio0 = e && e.b === "o" && Array.isArray(co.nio3) ? num(co.nio3[0]) : null;
    const basis = !e ? "today" : nio0 != null ? "o" : e.b === "s" ? "s" : "total";
    const cash = Array.isArray(co.cash3) ? num(co.cash3[0]) : null;
    const ni0 = basis === "o" ? nio0 : Array.isArray(co.ni) ? num(co.ni[0]) : null;
    const fy0 = num(co.fy) ?? num(s.fy);
    if (!st || st.zero || !(cash > 0) || !(ni0 > 0) || fy0 == null) return null;
    const p = (cash / ni0) * 100;
    const b = e ? { basis } : {};                  // files before the re-read: the same result as before, nothing added
    return p > 0 && p <= 100 ? { pct: p, fy: fy0, ...b } : { out: p, fy: fy0, ...b };
  }
  if (!dpsAgrees(s)) return null;
  if (splitGuarded(s)) return null;               // split guard: today's share count may be after a split (older files)
  const d = num(s.dps), ni = Array.isArray(co.ni) ? num(co.ni[0]) : null;
  const sh = num(s.shr) || (num(co.shm) ? co.shm * 1e6 : null);
  const fy = num(co.fy) ?? num(s.fy);
  if (d == null || !(d > 0) || !(ni > 0) || !(sh > 0) || fy == null) return null;
  const pct = ((d * sh) / (ni * 1e8)) * 100;
  return pct > 0 && pct <= 100 ? { pct, fy } : { out: pct, fy };
}

// ---------------- 출렁임 tile ----------------
// Beta against the stock's own market (Korea: 코스피, US: S&P 500). CLAUDE.md: beta is shown with its band, never bare.
// Exact data (v19.1b, Part O.1 of docs/tasks/v19.3-portfolio-pictures-accounts.md): band = beta -/+ 2 x betaSE
// (engine.betaBand), each end rounded to 0.1 (lo, hi; one = both ends the same after rounding). No betaSE, or betaSE above
// 0.5 (a broken price history) -> na (자료가 없어요): no phrase, no range, no bare beta.
// Older files (no betaSE in the data): the phrase only, as before, and no number.
export const round1 = (v) => { const r = Math.round(v * 10) / 10; return r === 0 ? 0 : r; };     // never −0
export function riskTile(s) {
  const b = num(s && s.beta);
  if (b == null) return { rule: "na" };
  const rule = b > BETA_BIG ? "big" : b < BETA_SMALL ? "small" : "similar";
  if (!exactData()) return { rule, beta: b };
  const band = betaBand(s);
  if (!band) return { rule: "na", beta: b, noBand: true };
  const lo = round1(band.lo), hi = round1(band.hi);
  return { rule, beta: b, band: { lo, hi, one: lo === hi, se: band.se } };
}

// ---------------- 재무 경고 신호 (KR): src/v2/warn.js (v19.3d: shared with the portfolio rule) ----------------
export { WARN_CHECKS, FIN_SUB_SECTORS, FIN_SUB_INDS, warnings } from "./warn.js";

// ---------------- 내 기준과 맞는 정도 (the 8 live criteria cards) ----------------
export const RANK_CARDS = CARDS.filter((c) => !c.pending).map((c) => c.id);
// The cards the user picked: the latest saved portfolio's cards with points (CARDS order); none -> the first two.
export function myCards(decks) {
  const ds = Array.isArray(decks) ? decks : [];
  for (let i = ds.length - 1; i >= 0; i--) {
    const p = ds[i] && ds[i].settings && ds[i].settings.points;
    if (!p || typeof p !== "object") continue;
    const ids = RANK_CARDS.filter((id) => num(p[id]) > 0);
    if (ids.length) return { ids, picked: true };
  }
  return { ids: RANK_CARDS.slice(0, 2), picked: false };
}

// Rank of one stock on each card, within its market ("market") or its industry group ("ind"). Percentiles as
// engine.percentileScores (higher = better on that card, ties share a rank). top <= 50 -> { side: "top", pct } (상위),
// else { side: "bottom", pct } (하위). Financial companies on 재무 안정 -> na; a blank -> blank. Never ranks by a blank.
const rankMemo = new WeakMap();
function scoresFor(list, cardId) {
  let m = rankMemo.get(list);
  if (!m) { m = new Map(); rankMemo.set(list, m); }
  if (!m.has(cardId)) m.set(cardId, percentileScores(list, CARDS.find((c) => c.id === cardId)));
  return m.get(cardId);
}
export function cardRanks(s, stocks, scope = "market") {
  if (!s || (s.cls !== "kr" && s.cls !== "us")) return { n: 0, rows: [] };
  const list = scope === "ind" ? groupOf(stocks, s) : marketList(stocks, s.cls);
  if (scope === "ind" && list.length < GROUP_MIN) return { n: list.length, rows: [], few: true };
  const inList = list.some((x) => x.t === s.t);
  const rows = RANK_CARDS.map((id) => {
    const card = CARDS.find((c) => c.id === id);
    const raw = cardRaw(s, card);
    if (raw === NA) return { id, na: true };
    if (!inList || raw == null) return { id, blank: true };
    const sc = scoresFor(list, id);
    const v = sc.get(s.t), n = sc.size;
    if (v == null || !n) return { id, blank: true };
    const top = Math.ceil(100 - v + 100 / n - EPS);
    return top <= 50 ? { id, side: "top", pct: Math.max(1, top) } : { id, side: "bottom", pct: Math.max(1, Math.ceil(v - EPS)) };
  });
  return { n: list.length, rows };
}
const marketMemo = new WeakMap();
function marketList(stocks, cls) {
  let m = marketMemo.get(stocks);
  if (!m) { m = {}; marketMemo.set(stocks, m); }
  if (!m[cls]) m[cls] = universe(stocks, cls);
  return m[cls];
}

// ---------------- 실적 tab ----------------
// KR revenue growth vs the industry: only peers whose g3 has the same basis (engine.growthBasis: y2 = the 2-year average,
// y1 = the 1-year change; unclear rows are left out), same market. At least 5 such peers, else null.
export function growthVsInd(s, co, stocks, coByT) {
  if (!s || s.cls !== "kr") return null;
  const basis = growthBasis(s, co);
  const g = num(s.g3);
  if (!basis || g == null) return null;
  const vals = groupOf(stocks, s).filter((x) => num(x.g3) != null && growthBasis(x, coByT ? coByT.get(x.t) : null) === basis).map((x) => x.g3);
  if (vals.length < GROUP_MIN) return null;
  const med = round(median(vals), 1), mine = round(g, 1);
  return { basis, mine, med, n: vals.length, rule: mine > med + GROWTH_SAME ? "faster" : mine < med - GROWTH_SAME ? "slower" : "similar" };
}

// Annual figures oldest first for the bars and the table: [{ year, rev, op, ni }] (억원), null when any year is missing.
export function annualRows(co) {
  const fy = num(co && co.fy);
  if (!co || fy == null) return null;
  const pick = (k) => (Array.isArray(co[k]) ? [2, 1, 0].map((i) => num(co[k][i])) : [null, null, null]);
  const rev = pick("rev"), op = pick("op"), ni = pick("ni");
  return [0, 1, 2].map((i) => ({ year: fy - 2 + i, rev: rev[i], op: op[i], ni: ni[i] }));
}
// Change of the latest year vs the year before, only from a profit (or positive revenue).
export const yoy = (cur, prev) => (num(cur) != null && num(prev) != null && prev > 0 ? (cur / prev - 1) * 100 : null);

// 주가는 무엇으로 움직였나 (the old DecompCard maths, src/corp.jsx decomposeReturn): 3-year price = earnings x 눈높이 (PER),
// as multipliers (3.20배 = 9.73배 x 0.33배: a true equation). EPS then = net income two reports back / shares; EPS now is
// data.json eps (its own basis: the latest four quarters when corp.json bq is set); the rest of the price change is the
// change in PER. why: "missing" (an input is not in the data) · "loss" (a loss at either end) · "basis" (2026-11-08: the
// two ends cannot stand on one basis, src/repair.js epsBase: no numbers, the PER/EPS line instead). head: up/down x which
// part was bigger (in log terms).
// The 'then' end shares EPS now's basis: a file before the DART re-read has eps = total profit ÷ common shares, so ni[2] ÷
// shm as always; after it eps = owners' profit ÷ (common + listed preferred), so nio3[2] (or ni[2] for separate statements)
// ÷ epsIn.sh. Mixing them made 현대차's 이익 part about 25% too low and its 눈높이 part about 33% too high (data review).
export function decompose(co) {
  if (!co || num(co.r36) == null) return { why: "missing" };
  const base = epsBase(co, 2);
  if (base.bad) return { why: "basis" };
  if (!base.sharesM) return { why: "missing" };
  const epsNow = num(co.eps);
  const niThen = base.ni;
  if (epsNow == null || niThen == null) return { why: "missing" };
  if (epsNow <= 0 || niThen <= 0) return { why: "loss" };              // a real loss at one end: no split into two parts
  const epsThen = (niThen * 100) / base.sharesM;
  const priceRatio = 1 + co.r36 / 100;
  if (priceRatio <= 0) return { why: "missing" };
  const eF = epsNow / epsThen;
  const mF = priceRatio / eF;
  const up = priceRatio >= 1;
  const eDom = Math.abs(Math.log(eF)) >= Math.abs(Math.log(mF));
  const price = num(co.price);
  return { eF, mF, priceRatio, epsThen, epsNow, head: (up ? "up" : "down") + (eDom ? "E" : "M"),
    priceNow: price, priceThen: price != null ? price / priceRatio : null,
    perNow: price != null ? price / epsNow : null, perThen: price != null ? price / priceRatio / epsThen : null,
    fyThen: num(co.fy) != null ? co.fy - 2 : null };
}

// ---------------- 가치 tab ----------------
// The industry PBR strip: every group member with a PBR as a dot on a 0..cap scale (cap: the 90th percentile, at least
// twice the median, so a few very high PBRs do not squash the rest; dots above it sit at the right edge).
export function pbrStrip(s, group) {
  const pts = (group || []).map((x) => ({ t: x.t, v: num(x.pbr) })).filter((p) => p.v != null && p.v > 0);
  if (!pts.some((p) => p.t === s.t) && num(s.pbr) > 0) pts.push({ t: s.t, v: s.pbr });
  if (pts.length < VALUE_MIN) return null;
  const sorted = pts.map((p) => p.v).sort((a, b) => a - b);
  const med = round(median(sorted), 2);
  const p90 = sorted[Math.min(sorted.length - 1, Math.floor(0.9 * (sorted.length - 1)))];
  const cap = Math.max(p90, 2 * med, num(s.pbr) || 0) * 1.05;
  const at = (v) => Math.min(1, v / cap);
  return { n: pts.length, med, cap, dots: pts.map((p) => ({ t: p.t, x: at(p.v), mine: p.t === s.t, over: p.v > cap })), mine: at(s.pbr), medX: at(med) };
}

// Industry medians of PER, EV/EBITDA and P/영업현금흐름 (KR: corp.json evE · pcf), same group. null below 5 values.
export function indMedian(group, get) {
  const vals = (group || []).map(get).filter((v) => v != null && v > 0);
  return vals.length >= VALUE_MIN ? { med: median(vals), n: vals.length } : null;
}

// 업종 지도 (ROE x PBR): this group's companies, with a least-squares line PBR = a + b x ROE fitted on the OTHER members
// only (at least 5 with both numbers, |ROE| <= 100%), so the company itself never bends the line it is compared with.
// pos: above / below / near (within 10% of the line) — only when the company's ROE lies inside the peers' ROE range;
// outside it the line would be stretched past its data, so pos is "out" (no sentence).
export function roePbrMap(s, group) {
  const ok = (p) => p.x != null && p.y != null && p.y > 0 && Math.abs(p.x) <= 100;
  const peers = (group || []).filter((x) => x.t !== s.t).map((x) => ({ t: x.t, x: num(x.roe), y: num(x.pbr) })).filter(ok);
  const me = { t: s.t, x: num(s.roe), y: num(s.pbr) };
  if (peers.length < VALUE_MIN || me.x == null || !(me.y > 0)) return null;
  const n = peers.length, mx = peers.reduce((a, p) => a + p.x, 0) / n, my = peers.reduce((a, p) => a + p.y, 0) / n;
  const sxx = peers.reduce((a, p) => a + (p.x - mx) * (p.x - mx), 0);
  if (!(sxx > 0)) return null;
  const b = peers.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0) / sxx, a = my - b * mx;
  const lo = Math.min(...peers.map((p) => p.x)), hi = Math.max(...peers.map((p) => p.x));
  const fit = a + b * me.x;
  const pos = me.x < lo || me.x > hi ? "out" : fit > 0 && Math.abs(me.y - fit) <= 0.1 * fit ? "near" : me.y > fit ? "above" : "below";
  return { pts: [...peers.map((p) => ({ ...p, mine: false })), { ...me, mine: true }], a, b, pos, n: n + 1, range: [lo, hi] };
}

// KR only (US until v19.2), with the old DcfCard's own defaults (discount 10%, 5년 뒤 성장률 2%, the growth rate fading
// over the 5 years to it): g is the first year's growth. Start profit: the latest 사업보고서's net income (corp.json ni[0],
// fy). why: "us" · "notReady" (the old card's dcfReady, or no net income / shares) · "loss" · "basis" (2026-11-08: no
// basis shared with EPS, src/repair.js epsBase: no numbers, the PER/EPS line instead).
// Start profit and share count stand on EPS's basis: before the DART re-read total profit ni[0] ÷ common shares (as always);
// after it owners' profit nio3[0] (separate statements: ni[0]) ÷ epsIn.sh (common + listed preferred).
export function impliedGrowth(s, co, { disc = DCF.disc, term = DCF.term } = {}) {
  if (!s || s.cls !== "kr") return { why: "us" };
  if (!co || co.dcfReady !== true) return { why: "notReady" };
  const base = epsBase(co, 0);
  if (base.bad) return { why: "basis" };
  const ni0 = base.ni;
  const price = num(s.price);
  const sharesM = base.basis === "today" ? num(co.shm) || (num(s.cap) && price ? (s.cap * 1e12) / price / 1e6 : null) : base.sharesM;
  if (ni0 == null || !(sharesM > 0) || !(price > 0)) return { why: "notReady" };
  const inputs = { disc, term, ni0, sharesM, fy: num(co.fy), fade: DCF.fade };
  if (ni0 <= 0) return { why: "loss", ...inputs };
  const r = reverseDcf({ price, ni0, sharesM, fade: DCF.fade, disc, term });
  if (!r) return { why: "notReady" };
  return r.edge ? { edge: r.edge, ...inputs } : { g: r.g, ...inputs };
}

// Receipts for 가치 자세히: price / BPS = PBR and price / EPS = PER, shown only when the arithmetic gives the number on
// screen (within the rounding of the data), never a receipt that disagrees with the ratio above it.
export function receipt(price, per, ratio, d) {
  const p = num(price), q = num(per), r = num(ratio);
  if (!(p > 0) || !(q > 0) || r == null) return null;
  const got = round(p / q, d);
  return Math.abs(got - r) <= Math.pow(10, -d) + EPS ? { price: p, per: q, value: r } : null;
}

// ---------------- 공시 tab (KR, disc.json) ----------------
// This company's 임원·주요주주 reports (90 days) and its 국민연금 5% filing, newest first. Amounts are estimates: shares x
// today's close (disc.json amt is the same estimate rounded to 0.1억원; it is not the trade price).
const ymd = (d) => (typeof d === "string" && /^\d{8}$/.test(d) ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : null);
export function discFor(disc, s) {
  if (!disc || !s || s.cls !== "kr") return null;
  const px = num(s.price);
  const rows = (Array.isArray(disc.insider) ? disc.insider : [])
    .filter((x) => x && x.t === s.t && Number.isInteger(x.q) && x.q !== 0 && ymd(x.d))
    .map((x) => ({ rc: x.rc, date: ymd(x.d), nm: typeof x.nm === "string" ? x.nm : "", pos: typeof x.pos === "string" && x.pos !== "-" ? x.pos : "",
      q: x.q, won: px > 0 ? Math.abs(x.q) * px : null }))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  const side = (xs) => ({ n: xs.length, won: px > 0 ? xs.reduce((a, x) => a + x.won, 0) : null });
  const n0 = (Array.isArray(disc.nps) ? disc.nps : []).find((x) => x && x.t === s.t && num(x.rt) != null && ymd(x.d)) || null;
  return { rows, buys: side(rows.filter((x) => x.q > 0)), sells: side(rows.filter((x) => x.q < 0)),
    nps: n0 ? { rt: n0.rt, chg: num(n0.chg), date: ymd(n0.d) } : null, asOf: typeof disc.asOf === "string" ? disc.asOf : null };
}

// The 공시 tab's content date and freshness, as the old app's 공시·수급 shows it: the newest filing in the file (newest),
// not the run date (asOf); stale when the file was published more than STALE_DAYS ago. listOk false = today's filing list
// did not come in, so the rows stop at newest: stale, counted from newest (at least a day). now: ms (tests).
export function discDate(disc, now = Date.now()) {
  if (!disc) return null;
  const newest = typeof disc.newest === "string" && /^\d{4}-\d{2}-\d{2}$/.test(disc.newest) ? disc.newest : null;
  const DAY = 86400000;
  const pub = Date.parse(disc.publishedAt || "");
  const sincePub = Number.isFinite(pub) ? Math.floor((now - pub) / DAY) : null;
  const sinceNewest = newest ? Math.floor((now - Date.parse(newest + "T00:00:00+09:00")) / DAY) : null;
  if (disc.listOk === false) return { date: newest, stale: true, days: Math.max(1, sinceNewest ?? 1), listOk: false };
  const stale = sincePub == null || sincePub > STALE_DAYS;
  return { date: newest, stale, days: stale ? sincePub : 0, listOk: true };
}

// ---------------- holdings ----------------
// Every saved portfolio that holds this stock today (the daily check's evaluation): [{ deckId, name, x }].
export function holdingsOf(ev, decks, t) {
  if (!ev || !ev.ok) return [];
  const out = [];
  for (const de of ev.decks) {
    if (!de || !de.ok) continue;
    const x = de.holdings.find((h) => h.t === t);
    const deck = (decks || []).find((d) => d.id === de.id);
    if (x && deck) out.push({ deckId: de.id, name: deck.name, x, deck });
  }
  return out;
}

// ---------------- fallback logo mark (Part G) ----------------
// Ten fixed colours (white letters read at 4.5:1 or more on each; no apricot, no price red or blue, no status amber),
// one per code by a stable hash, so a company keeps its colour everywhere.
export const MARK_COLORS = ["#1C2B45", "#2F5D62", "#3D5A3C", "#5B4A8B", "#6B4E3D", "#46536B", "#7A3E5D", "#355C7D", "#5E5A2E", "#4B3F72"];
export function markColor(code) {
  let h = 2166136261;
  for (const ch of String(code || "")) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; }
  return MARK_COLORS[h % MARK_COLORS.length];
}
export function markLetter(name, code) {
  const n = String(name || code || "").trim();
  const ch = n ? String.fromCodePoint(n.codePointAt(0)) : "";
  return /[a-z]/.test(ch) ? ch.toUpperCase() : ch;
}
