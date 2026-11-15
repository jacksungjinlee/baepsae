// ================= 연말에 확인할 숫자 (v19.6f, Part F, board TaxCheck2): the numbers, no React and no Korean =================
// Spec: docs/tasks/v19.6-records-alerts-dark.md Part F. Unit tests: tests/test_v2_tax.py (run through Node, also under other
// device time zones). The screen is src/v2/tax.jsx; its words are in src/copy/v2.js (tax.*).
//
// What this file answers, over EVERY portfolio of the store (the screen covers all of them together):
//   taxWindow(today)      is the screen open today (KST)? From Nov 1 to Dec 31 of TAX_YEAR only, and from Dec 15 the
//                         settlement-date line. Another year is closed until a PR re-checks the facts below (TAX_YEAR gate).
//   taxRecords(decks)     what the user has: a US sale dated this tax year, a US holding, a dividend dated this tax year.
//   taxOpen(decks, today) the window is open and the user has at least one of those three (the entry link on 내 수익 and
//                         the #portfolio/tax address use this one rule).
//   yearGains(decks)      this year's US realized gains in won (Part A.4: moving average, each sale at its own rate; a
//                         dollar-only lot's share at the sale date's rate), and the sales left out (gain unknown).
//   taxState(G)           below · equal · above (with the estimate) · loss, and the bar.
//   yearDivs(decks)       this year's dividend records turned back into pre-tax amounts, and the USD ones without a rate.
//   heldLosses(decks, q)  held US stocks with a negative unrealized won gain, per stock across portfolios, all or nothing.
// Nothing here is shown silently: every record left out is counted, and the screen says so (or, for a line that is not
// approved yet, leaves the whole card out and says why in the console).
//
// ---------------- the facts (re-checked 2026-11-15; re-check them in the PR that moves TAX_YEAR) ----------------
// 국세청 guide (2025; nts.go.kr cntntsId=8800), p.11: the 250만원 basic deduction a year, 20% tax + local income tax of 10%
// of it (22% in all) on the overseas-stock gain above it, and same-year netting of gains and losses. The 250만원 is one
// deduction shared with taxable Korean share gains (국내·국외 통산): a 대주주 with taxable Korean gains may have used part
// of it (a known limit). p.6-7: the 2,000만원 financial-income threshold (interest plus dividends, overseas dividends
// included) and the Korean dividend withholding, 14% with 1.4% local (15.4%). The Korea-US tax treaty's 15% US
// withholding on dividends (no official page found). Cost basis: the legal default is first-in first-out (소득세법 시행령
// §162⑤); the moving average this app uses is allowed when the broker applies it (국세청 질의회신 국제세원-229). US T+1
// settlement; the settlement date decides the tax year (비즈워치 2025-12-05). 조세특례제한법 §91의26 (국내시장 복귀계좌,
// RIA; passed 2026-03-31; hankyung.com 2026033191357, taxtimes 274352): a deduction for 2026 sales, with conditions.
// 금융투자소득세: abolished.
// Known limits (said in the v19.6f PR, not on screen): the shared 250만원 above; the 2026 환헤지 deduction (§91의27,
// proposal M5); the settlement-day rate and date (the app uses the typed trade date and its own rate: C1); 비과세 감액배당,
// ISA / pension accounts, a 30% US withholding and other countries' withholding on US-listed foreign companies (C4); and a
// trade recorded in two portfolios (counted twice; the approved "모든 포트폴리오" line).
import { recordSets, ledger, openValue } from "./lots.js";
import { C, todayKst } from "./format.js";

export const TAX_YEAR = 2026;                 // the tax law the screen's lines describe ("2026년 세법 기준")
export const CHECKED = "2026-11-15";          // the day the facts above were last re-checked
export const DEDUCTION = 2500000;             // 기본공제 250만원 a year (overseas stocks)
export const RATE_PCT = 22;                   // 양도소득세 20% + 지방소득세 2% (10% of it)
export const RATE = RATE_PCT / 100;
export const KR_WH_PM = 154;                  // Korean dividend withholding 15.4% (per mille, so the maths stays exact)
export const US_WH_PM = 150;                  // US dividend withholding 15% (treaty rate)
export const KR_WH = KR_WH_PM / 1000;
export const US_WH = US_WH_PM / 1000;
export const RIA_YEARS = [2026];              // tax years the 국내시장 복귀계좌 (RIA) deduction applies to
export const WINDOW = { from: "11-01", to: "12-31", settle: "12-15" };   // KST month-day

const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const pos = (x) => isNum(x) && x > 0;
const DATE = /^(\d{4})-(\d{2}-\d{2})$/;
// Half away from zero, to the 원 (lots.js roundRows): −0.5 → −1, 0.5 → 1; never −0.
export const roundWon = (x) => { const r = Math.sign(x) * Math.round(Math.abs(x)); return r === 0 ? 0 : r; };
// To the nearest 1,000원, half up (the two estimates: the tax and the pre-tax dividends; always 0 or more).
export const round1000 = (x) => { const r = Math.round(x / 1000) * 1000; return r === 0 ? 0 : r; };
const inYear = (date, year) => typeof date === "string" && DATE.test(date) && date.slice(0, 5) === `${year}-`;

// ---------------- the window ----------------
// today: KST "YYYY-MM-DD" (format.todayKst). -> { open, year, settle, ria }
export function taxWindow(today, taxYear = TAX_YEAR) {
  const m = DATE.exec(String(today || ""));
  if (!m) return { open: false, year: null, settle: false, ria: false };
  const year = Number(m[1]);
  const md = m[2];
  const open = year === taxYear && md >= WINDOW.from && md <= WINDOW.to;
  return { open, year, settle: open && md >= WINDOW.settle, ria: open && RIA_YEARS.includes(year) };
}
// Today in Korea from a clock reading (ms), whatever the device's own time zone.
export const taxToday = (now) => todayKst(now);

// ---------------- what the user has ----------------
// Over every portfolio and its history (A.3). A US holding: a stock held today (shares > 0) in a portfolio (never a history
// entry: those shares left with their cost) whose records are in dollars. A dividend counts only when the screen can show
// it: while the line naming a US dividend without a rate (tax.divNoFx) is not approved, such a dividend keeps the whole
// dividend card out (tax.jsx), so then no dividend of the year opens the link on its own (review B, round 1: never a link
// to an empty screen). -> { usSale, usHeld, div, divAny (any dividend dated this year), divNoFx (US ones without a rate), any }
export function taxRecords(decks, year = TAX_YEAR) {
  const out = { usSale: false, usHeld: false, div: false, divAny: false, divNoFx: 0 };
  for (const d of Array.isArray(decks) ? decks : []) {
    if (!d || typeof d !== "object") continue;
    const sets = [d, ...(Array.isArray(d.history) ? d.history : [])];
    for (const s of sets) {
      if (!s) continue;
      for (const x of Array.isArray(s.sales) ? s.sales : []) if (x && x.ccy === "USD" && inYear(x.date, year)) out.usSale = true;
      for (const x of Array.isArray(s.divs) ? s.divs : []) {
        if (!(x && pos(x.amount) && inYear(x.date, year))) continue;
        out.divAny = true;
        if (x.ccy === "USD" && !pos(x.fx)) out.divNoFx += 1;
      }
    }
    if (!out.usHeld) {
      for (const set of recordSets(d)) {
        if (set.history) continue;
        const L = ledger(set.recs, set.t, set.ctx);
        if (L.ccy === "USD" && L.held > 0) { out.usHeld = true; break; }
      }
    }
  }
  out.div = out.divAny && (out.divNoFx === 0 || !!(C.tax && C.tax.divNoFx));
  out.any = out.usSale || out.usHeld || out.div;
  return out;
}
// The one rule for the entry link (내 수익) and the #portfolio/tax address.
export function taxOpen(decks, today, taxYear = TAX_YEAR) {
  return taxWindow(today, taxYear).open && taxRecords(decks, taxYear).any;
}

// ---------------- this year's US realized gains (A.4) ----------------
// Every record set of every portfolio (history included: a stock taken out keeps its sales, A.3), dollar ledgers only,
// sales dated in `year` (the typed trade date: C1, a known limit). A sale recorded in two portfolios counts twice (the
// approved "모든 포트폴리오의 판 기록을 더했어요." line covers it). -> { gain (rounded to the 원), exact, n (counted), left
// (sales whose gain is unknown: no 평균 단가, no rate, or more than held), usdOnly (a counted sale took a dollar-only lot's
// gain at the sale date's rate) }
export function yearGains(decks, year = TAX_YEAR) {
  const out = { gain: 0, exact: 0, n: 0, left: 0, usdOnly: false };
  for (const d of Array.isArray(decks) ? decks : []) {
    if (!d || typeof d !== "object") continue;
    for (const set of recordSets(d)) {
      const L = ledger(set.recs, set.t, set.ctx);
      if (L.ccy !== "USD") continue;
      for (const s of L.sales) {
        if (!inYear(s.rec && s.rec.date, year)) continue;
        if (!isNum(s.gain)) { out.left += 1; continue; }
        out.exact += s.gain;
        out.n += 1;
        if (s.usdOnly) out.usdOnly = true;
      }
    }
  }
  out.gain = roundWon(out.exact);
  return out;
}

// ---------------- the three states (Appendix 1) ----------------
// G: the year's gain in won (rounded). -> { kind: "loss" | "below" | "equal" | "above", x (won, the line's {x}), t (the
// estimate, above only: (G − 250만원) x 22% to the nearest 1,000원), bar (0..1 of the bar to 250만원; null in the loss state) }
export const taxOf = (over) => (over > 0 ? round1000((over * RATE_PCT) / 100) : 0);
export function taxState(G) {
  if (!isNum(G)) return null;
  if (G < 0) return { kind: "loss", x: -G, t: null, bar: null };
  if (G === DEDUCTION) return { kind: "equal", x: 0, t: null, bar: 1 };
  if (G < DEDUCTION) return { kind: "below", x: DEDUCTION - G, t: null, bar: G / DEDUCTION };
  return { kind: "above", x: G - DEDUCTION, t: taxOf(G - DEDUCTION), bar: 1 };
}

// ---------------- this year's dividends, before tax ----------------
// The 2,000만원 test counts pre-tax income: Korea ÷ (1 − 15.4%), US (dollars x the record's own rate) ÷ (1 − 15%). A US
// dividend without a rate is left out and counted (noFx). C4 (known limit): a 비과세 감액배당, an ISA or pension account, or a
// 30% US withholding make this an upper or lower estimate. -> { won (rounded to 1,000원), exact, n (counted), kr, us, noFx }
export function yearDivs(decks, year = TAX_YEAR) {
  const out = { won: 0, exact: 0, n: 0, kr: 0, us: 0, noFx: 0 };
  for (const d of Array.isArray(decks) ? decks : []) {
    if (!d || typeof d !== "object") continue;
    for (const set of recordSets(d)) {
      const L = ledger(set.recs, set.t, set.ctx);
      for (const x of L.divs) {
        const r = x.rec;
        if (!inYear(r && r.date, year)) continue;
        if (r.ccy === "USD") {
          if (!pos(r.fx)) { out.noFx += 1; continue; }
          out.exact += (r.amount * r.fx * 1000) / (1000 - US_WH_PM);
          out.us += 1;
        } else {
          out.exact += (r.amount * 1000) / (1000 - KR_WH_PM);
          out.kr += 1;
        }
        out.n += 1;
      }
    }
  }
  out.won = round1000(out.exact);
  return out;
}

// ---------------- held US stocks at a loss ----------------
// q: { pxOf(t) -> today's price in dollars | null, fx: today's rate, absent: { has(t) } held stocks missing from today's
// data }. Per stock across every portfolio (history never: those shares left with their cost, A.3), all or nothing: a stock
// one of whose portfolios cannot be valued leaves whole, named by why:
//   noAvg    a lot without 평균 단가 (an imported row without one)
//   noFx     a lot whose cost has no rate (a purchase saved before Part C, or marked noFx)
//   absent   missing from today's data · noPrice in it without a price · noToday no rate today (data.json fx)
// -> { rows: [{ t, gain (rounded to the 원, below 0), usdOnly }] biggest loss first, held (US stocks held), noAvg, noFx,
//      absent, noPrice, noToday (lists of codes), usdOnly (a shown row counted a dollar-only lot at today's rate) }
export function heldLosses(decks, q) {
  const by = new Map();
  for (const d of Array.isArray(decks) ? decks : []) {
    if (!d || typeof d !== "object") continue;
    for (const set of recordSets(d)) {
      if (set.history) continue;
      const L = ledger(set.recs, set.t, set.ctx);
      if (L.ccy !== "USD" || !(L.held > 0)) continue;
      let e = by.get(set.t);
      if (!e) { e = { t: set.t, exact: 0, why: null, usdOnly: false }; by.set(set.t, e); }
      if (e.why) continue;
      if (q && q.absent && q.absent.has(set.t)) { e.why = "absent"; continue; }
      if (!(q && pos(q.fx))) { e.why = "noToday"; continue; }
      const v = openValue(L, q.pxOf(set.t), q.fx);
      if (v.value == null) { e.why = "noPrice"; continue; }
      if (v.gain == null) { e.why = v.unknown === "noRate" ? "noFx" : "noAvg"; continue; }
      e.exact += v.gain;
      if (v.usdOnly) e.usdOnly = true;
    }
  }
  const out = { rows: [], held: by.size, noAvg: [], noFx: [], absent: [], noPrice: [], noToday: [], usdOnly: false };
  for (const e of by.values()) {
    if (e.why) { out[e.why].push(e.t); continue; }
    const g = roundWon(e.exact);
    if (g < 0) out.rows.push({ t: e.t, gain: g, usdOnly: e.usdOnly });
  }
  out.rows.sort((a, b) => a.gain - b.gain || (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
  out.usdOnly = out.rows.some((r) => r.usdOnly);
  return out;
}
