// Browser storage for app.html: one versioned key; every read and write inside try/catch.
// Portfolios ("decks" in the code), rule books, purchase records and the answers to 확인 필요 (confirms) live only on
// this device (no login).
// Export/import is a JSON file. confirms, planFx (deck) and planPx (holding) are optional, so records saved before
// Part C still read the same; when present they must be valid or the whole file is refused.
// v19.1a: two more optional parts, per stock (any stock, held or not): notes (내 메모: { [code]: { text, at } }) and
// assume (가치 자세히 · 이 가정 저장하기: { [code]: { disc, term, at } }). Same rule: absent is fine, present must be valid.
// The preview page (app-preview.html) uses its own key so example records never mix with real ones.
//
// ---------------- store version 2 (v19.3d; v19.3 Part F.1 and v19.6 Part A.1, one migration for both) ----------------
// Every part below is optional, so every store saved before (version 1, with or without confirms, planFx, planPx, notes,
// assume) is a valid version-2 store: it is read as it is ("migrate on read" has nothing to rewrite).
// Per portfolio:
//   kind     "imported": made with 가진 종목 넣기. It has no per-stock rule book, so only the four portfolio rules run on
//            it (pf.js); settings then holds the 기준 the user chose ({ points, strict }) and is checked here.
//   imported [row]: holdings the user already owned, one row per stock, each with a matching holding (like purchases):
//              { t, nk, ccy, qty, date?, avg?, unscored? }                 quantity: Korea whole shares, US up to 4 decimals
//              { t, nk, ccy, amountWon, close, date, fx?, avg?, unscored? } 금액으로 넣기: the amount in won with that day's
//                                                                          close (own currency), date and (US) rate; the
//                                                                          share count is derived from them (held.js)
//              { nk, ccy: "KRW", amountWon, date, unscored: true }         a stock not in the data, added by name: no code,
//                                                                          no share count; its value is the amount as of date
//            avg = 평균 단가 as typed, in the stock's currency (never filled in by the app). unscored = the 기준 could not
//            score it when it was added (a display mark; the report always decides from today's data).
//   sales    [{ t, qty, price, date, ccy, fx? }] 팔았어요 (v19.6a). qty in 1/10,000 units; a Korean sale is whole shares
//            unless the stock was imported by amount (then it can only be sold all at once, v19.6 A.2).
//   divs     [{ t, amount, ccy, date, fx? }] 배당 받았어요 (v19.6a), after tax, in the stock's currency.
//   history  [{ t, nk, out, cls?, imported?, purchases?, sales?, divs? }] records of a stock taken out of the portfolio
//            (v19.6 A.3): they need no matching holding, and a later dividend of that stock goes into its entry.
//   limits   { stock?, ind? } the two concentration rules' limits in % (defaults 30 and 35, pf.js), when the user changed them.
//   splits   [{ t, date, r }] (v19.6a, A.6): the stock splits this portfolio's records are read with (held.js): from date on,
//            one old share of t is r new ones; records dated before it stay as typed and are read at the new basis. The app
//            stores a split (from data.json splits) together with a record of that stock, so the store's own check (no sale
//            below 0 shares) reads the records exactly as the screens do and a sale of the new share count is never refused.
//            One per stock and date.
//   changes  [{ id?, at, kind, t?, nk?, reason? }] the change log of 종목 바꾸기 (v19.7a, Part A): at the date (KST), kind "add"
//            · "remove" · "targets" (a later version's kind is kept, not shown), t / nk the stock, reason the 빼기 chip (thesis
//            · rule · better · other), id a random id (two tabs' entries of the same day stay two). The app keeps the newest
//            CHANGES_MAX when it writes; a longer list (a later version's) is read as it is, never set aside. Not a
//            version-2-only part (the earlier apps keep a portfolio's fields they do not know). A history entry (above) may
//            carry reason too (v19.7a, Part B: the same chip; out is the spec's removedAt, the day it was taken out).
//   targetsTs when 종목 바꾸기 last set the target set (v19.7a round-1 S1; ms): every holding's target, plannedQty and band
//            rule, and settings.maxPct, as one edit. Two copies keep the later set whole (unionDeck), like limitsTs.
//   limitsTs when 내 규칙 정하기 last saved them (v19.3d2; ms, with or without a limits part: a 저장 at the defaults leaves
//            none), so two copies and a records file keep the later limits. Beside limits, not in it: v19.3d (#83) reads
//            limits strictly and passes portfolio keys it does not know, so a revert still reads every portfolio.
// Held quantity everywhere = imported + purchases − sales (held.js); no sale may take a holding below 0.
// Top level: watch (v19.6c, 관심 종목, v19.6 Part C): { [code]: { at, ts?, nk?, conds?: [{ k, v, hitAt? }] } }, at most WATCH_MAX (30)
// stocks: at = the date added (KST), ts = the time of the last edit (ms, so two tabs keep the later one), nk = the name when
// it was added (shown only while the stock is missing from today's data). conds: at most one per kind, k pxBelow (v > 0,
// at most 2 decimals: Korea whole won, US dollars) · pbrBelow (v > 0, 1 decimal) · dyAtLeast (v > 0, 1 decimal, %); a later
// version's kind is kept and not read. hitAt (a date): the stock's price date on the day this device first saw the condition
// met (watch.js withWatchHits); hitTs: the time that mark was set or cleared (ms; a cleared mark keeps only hitTs), so two
// copies keep the later mark (round-3 review). Both stay on this device, never in a records file (exportText) and never
// synced (Part C [Q7]).
// Not a version-2 part, so a store holding only watch stays v1: every earlier app reads such a store and keeps the part, but
// only as it read it — its write from an older copy, or its own start merging another tab's copy, puts back an older list
// (review B1). Every write of this app therefore also keeps the list beside the records (key + ".watch", see "관심 종목 beside
// the records"), and the next start of this app brings back what such a tab dropped, and says 합쳤어요.
// Times are stored as made, never rewritten. A date added after today (a clock that was ahead) is not a reason to set the list
// aside: at only sorts it. Each edit is stamped later than every time this device holds for that stock (watchSaveTime), so
// the newest edit wins even after a clock that was ahead has been corrected (round-3 review).
// gone.watch { [code]: { at, ts } }: a stock taken out of 관심 종목 (so a merge with an older copy does not bring it back);
// on this device only, like gone.notes.
// Top level: seen (v19.6b, 오늘 볼 것 · 확인했어요, v19.6 Part B.2): [{ t, kind, bd, n, p, amt, rc?, at, ts? }], at most SEEN_MAX: a
// 유상증자 · 전환사채 · 신주인수권부사채 decision (disc.json issue) the user marked 확인했어요, with the stock, the kind (rights · cb · bw), the
// board date (YYYYMMDD, or null) and the numbers as the card read them (null when blank), rc the filing it was marked on, at the
// date (KST) and ts the time (ms). A card stays hidden while an entry has its stock, kind and numbers and either its filing or
// (when the mark has a board date and at least one number) its board date: a correction with other numbers shows again (Part
// B.2), the same filing whose board date the pipeline reads a day later stays hidden, and a mark with no board date or no number
// hides only its own filing (never every such decision of the stock). An entry older than SEEN_DAYS (120) is pruned when another is added. Travels in a records file and is
// merged as a union (A.1 [Q6]: the newest time for the same entry); not a version-2 part (an earlier app keeps it as a top-level
// part it does not know).
// Top level: guideSeen (v19.3c Part E: the first-visit guide was seen, the date) — a flag of this device, so it never
// travels in a records file; until v19.3d it lived in its own key (key + ".guideSeen"), which is still read once.
// Two tabs (v19.3d review): so two copies of the records merge without losing the later edit, these optional parts are
// kept too. None of them makes a store version 2, and the earlier app reads and keeps them (it ignores fields it does
// not know):
//   ts       on a note, a saved assumption and an answer to 확인 필요: the time of the edit in ms (at is the date only);
//   id       on a purchase, sale or dividend: a random id, unique in its record set (two equal records stay two);
//   gone     top level { notes: { [code]: { at, ts } } }: a 메모 deleted (so a merge does not bring it back); it stays
//            on this device, never in a records file;
//   removed  per portfolio [{ t, at, ts }]: a stock taken out with 포트폴리오에서 빼기 (so a merge keeps it out unless the
//            holding was added again later: a holding's own ts, after the mark's; 기록 불러오기 stamps one, mergeStores);
//   wts      top level: a fingerprint of the records as this app wrote them (storeHash). The earlier app keeps it when it
//            saves (it keeps top-level parts it does not know), so on the next start it tells whether the earlier app
//            wrote from this app's last write (its changes, deletions too, are the user's) or from an older copy (then
//            this app's last write, ".mine", is merged back). Every write stamps it except the one that takes in a
//            records file (mergeStores): that write stores the file exactly as it is, and a file never carries it.
//
// Version tag: a store is written as v1 while it holds no version-2-only part (above: kind … limits), so a tab still
// running the earlier app, or a revert of this change, keeps reading it; it becomes v2 with the first such part. An
// older app moves a v2 store it cannot read to a backup key before writing its own; readStore finds that backup, puts
// it back and adds what the other tab saved (mergeTabs), and the screens say so once (C.store.merged).
//
// Checking: every field the app reads back is checked. A records FILE with one bad field is refused whole (nothing is
// stored). STORED records are checked per portfolio: a portfolio with a bad field (e.g. one bad imported row) is set
// aside with a console message naming it (portfolio, part, row, stock, reason), the other portfolios stay readable, and
// the first write keeps the stored text under a backup key, so nothing is ever lost.
import { okAssume } from "./dcf.js";
import { okUnits, belowZero, importedUnits, UNIT, okSplit } from "./held.js";

export const STORE_KEY = "baepsae2.v1";
export const PREVIEW_STORE_KEY = "baepsae2.preview.v1";
export const STORE_VERSION = 2;                      // the newest version this app reads and writes
export const BASE_VERSION = 1;                       // the tag of a store with no version-2-only part

export const emptyStore = () => ({ v: BASE_VERSION, decks: [] });

// The current app (baepsae.html) keeps its portfolios under this key. 2.0 never reads their contents or changes them:
// it only checks whether any exist, to tell a returning visitor where to find them (Part F, Jack 2026-11-01).
export const OLD_APP_SLOTS_KEY = "baepsae_v10_slots";
export function hasOldAppRecords(get = (k) => localStorage.getItem(k)) {
  try {
    const a = JSON.parse(get(OLD_APP_SLOTS_KEY) || "[]");
    return Array.isArray(a) && a.length > 0;
  } catch (e) { return false; }
}

const isStr = (x, max = 200) => typeof x === "string" && x.length > 0 && x.length <= max;
const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const isPos = (x) => isNum(x) && x > 0;
const isDate = (x) => typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x) && !Number.isNaN(Date.parse(x + "T00:00:00Z"))
  && new Date(x + "T00:00:00Z").toISOString().slice(0, 10) === x;
const pastDate = (x, today) => isDate(x) && !(today && x > today);
const plainObj = (x) => !!x && typeof x === "object" && !Array.isArray(x);
const okStockCode = (t) => isStr(t, 20) && /^[0-9A-Za-z][0-9A-Za-z.-]*$/.test(t);
const CCY = ["KRW", "USD"];
const okTs = (x) => Number.isSafeInteger(x) && x > 0;                 // a time in ms (Date.now())

// The version-2-only parts of a portfolio (any of them present makes the store v2).
export const V2_DECK_PARTS = ["kind", "imported", "sales", "divs", "history", "limits", "limitsTs", "splits"];
export const hasV2Parts = (d) => !!(d && Array.isArray(d.decks) && d.decks.some((x) => plainObj(x) && V2_DECK_PARTS.some((k) => x[k] != null)));
export const versionFor = (d) => (hasV2Parts(d) ? STORE_VERSION : BASE_VERSION);

// ---------------- one portfolio ----------------
// null when the portfolio is valid, else the first problem: { part, row (1-based) or null, t, why } (English, for the
// console: the screens use their own approved words).
const bad = (part, row, t, why) => ({ part, row: row == null ? null : row + 1, t: t || null, why });

function purchaseProblem(p, i, today, holds, part = "purchases") {
  if (!plainObj(p) || !isStr(p.t, 20)) return bad(part, i, null, "not a record with a stock code");
  if (!(Number.isInteger(p.qty) && p.qty > 0 && Number.isSafeInteger(p.qty * UNIT))) return bad(part, i, p.t, "quantity must be a whole number above 0");
  if (!isPos(p.price)) return bad(part, i, p.t, "price must be a number above 0");
  if (!pastDate(p.date, today)) return bad(part, i, p.t, "date must be a real date, not after today");
  if (!CCY.includes(p.ccy)) return bad(part, i, p.t, "currency must be KRW or USD");
  // Part E: a US purchase carries the won-per-dollar rate the plan used (for 원금 in won). Optional, so earlier records
  // still read; when present it must be a positive number on a USD purchase.
  if (p.fx != null && !(p.ccy === "USD" && isPos(p.fx))) return bad(part, i, p.t, "exchange rate only on a USD record, above 0");
  if (noFxProblem(p)) return bad(part, i, p.t, noFxProblem(p));
  if (rateTempProblem(p)) return bad(part, i, p.t, rateTempProblem(p));
  if (!holds(p.t)) return bad(part, i, p.t, "no holding with this code");
  return null;
}
// v19.6a (A.1, Part I.1): noFx: true marks a USD record saved deliberately without a rate (dated before 2016, before the
// rate history): it is left out of won totals (the noFx line), never costed at the portfolio's planFx. A USD purchase
// without fx and without this mark was saved before Part E and keeps the planFx saved with it (the same moment's rate).
function noFxProblem(r) {
  if (r.noFx == null) return null;
  return r.noFx === true && r.ccy === "USD" && r.fx == null ? null : "noFx is true, on a USD record without a rate, only";
}
// #191 (Jack, 2026-11-27): rateTemp: true marks a USD record saved at the latest rate before its date's rate was published
// (records.js rateFor); records.withOfficialRates replaces the rate and drops the mark once loaded data has that date.
function rateTempProblem(r) {
  if (r.rateTemp == null) return null;
  return r.rateTemp === true && r.ccy === "USD" && isPos(r.fx) ? null : "rateTemp is true, on a USD record with a rate, only";
}

// 평균 단가 (optional): as typed, in the stock's currency, above 0.
function importedProblem(r, i, today, holds, part = "imported") {
  if (!plainObj(r)) return bad(part, i, null, "not a row");
  const t = r.t;
  if (!isStr(r.nk, 120)) return bad(part, i, t, "name missing");
  if (!CCY.includes(r.ccy)) return bad(part, i, t, "currency must be KRW or USD");
  if (r.avg != null && !isPos(r.avg)) return bad(part, i, t, "average price (avg) must be a number above 0");
  if (r.unscored != null && r.unscored !== true) return bad(part, i, t, "unscored must be true when present");
  if (r.date != null && !pastDate(r.date, today)) return bad(part, i, t, "date must be a real date, not after today");
  if (t == null) {                                         // a stock not in the data, added by name with an amount only
    if (r.qty != null || r.close != null || r.fx != null || r.avg != null) return bad(part, i, null, "a row without a code takes an amount only");
    if (r.ccy !== "KRW" || !isPos(r.amountWon) || !isDate(r.date) || r.unscored !== true) return bad(part, i, null, "a row without a code needs an amount in won, its date and the unscored mark");
    return null;
  }
  if (!okStockCode(t)) return bad(part, i, t, "stock code is not valid");
  if (!holds(t)) return bad(part, i, t, "no holding with this code");
  const hasQ = r.qty != null, hasA = r.amountWon != null;
  if (hasQ === hasA) return bad(part, i, t, "needs a quantity or an amount, not both");
  if (hasQ) {
    if (r.close != null || r.fx != null) return bad(part, i, t, "a quantity row takes no close or rate");
    if (r.ccy === "KRW" ? !(Number.isInteger(r.qty) && r.qty > 0) : !okUnits(r.qty)) {
      return bad(part, i, t, r.ccy === "KRW" ? "quantity must be whole shares for a Korean stock" : "quantity must be above 0 with at most 4 decimals");
    }
    return null;
  }
  if (!isPos(r.amountWon)) return bad(part, i, t, "amount must be a number above 0");
  if (!isPos(r.close)) return bad(part, i, t, "close must be a number above 0");
  if (!isDate(r.date)) return bad(part, i, t, "an amount row needs the date of its close");
  if (r.ccy === "USD" ? !isPos(r.fx) : r.fx != null) return bad(part, i, t, "exchange rate on a USD row only (and required there)");
  if (importedUnits(r) == null) return bad(part, i, t, "amount is too small for one 1/10,000 share");
  return null;
}

function saleProblem(s, i, today, holds, byAmountT, part = "sales") {
  if (!plainObj(s) || !isStr(s.t, 20)) return bad(part, i, null, "not a record with a stock code");
  if (!okUnits(s.qty)) return bad(part, i, s.t, "quantity must be above 0 with at most 4 decimals");
  if (s.ccy === "KRW" && !Number.isInteger(s.qty) && !byAmountT(s.t)) return bad(part, i, s.t, "a Korean sale is whole shares");
  if (!isPos(s.price)) return bad(part, i, s.t, "price must be a number above 0");
  if (!pastDate(s.date, today)) return bad(part, i, s.t, "date must be a real date, not after today");
  if (!CCY.includes(s.ccy)) return bad(part, i, s.t, "currency must be KRW or USD");
  if (s.fx != null && !(s.ccy === "USD" && isPos(s.fx))) return bad(part, i, s.t, "exchange rate only on a USD record, above 0");
  if (noFxProblem(s)) return bad(part, i, s.t, noFxProblem(s));
  if (rateTempProblem(s)) return bad(part, i, s.t, rateTempProblem(s));
  if (!holds(s.t)) return bad(part, i, s.t, "no holding with this code");
  return null;
}

function divProblem(x, i, today, holds, part = "divs") {
  if (!plainObj(x) || !isStr(x.t, 20)) return bad(part, i, null, "not a record with a stock code");
  if (!isPos(x.amount)) return bad(part, i, x.t, "amount must be a number above 0");
  if (!CCY.includes(x.ccy)) return bad(part, i, x.t, "currency must be KRW or USD");
  if (!pastDate(x.date, today)) return bad(part, i, x.t, "date must be a real date, not after today");
  if (x.fx != null && !(x.ccy === "USD" && isPos(x.fx))) return bad(part, i, x.t, "exchange rate only on a USD record, above 0");
  if (noFxProblem(x)) return bad(part, i, x.t, noFxProblem(x));
  if (rateTempProblem(x)) return bad(part, i, x.t, rateTempProblem(x));
  if (!holds(x.t)) return bad(part, i, x.t, "no holding with this code");
  return null;
}

// A record's optional id (v19.3d review: purchases, sales and dividends saved from now on carry one, so two tabs' copies
// merge by id and two genuinely equal records stay two). Random, stable, unique within the portfolio's records.
const ID_RX = /^[A-Za-z0-9_-]{6,40}$/;
export function recordId() {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID().replace(/-/g, "").slice(0, 20);
  } catch (e) { /* fall back */ }
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
}
function idsProblem(lists, prefix) {
  const ids = new Set();
  for (const k of ["purchases", "sales", "divs"]) {
    const list = lists[k] || [];
    for (let i = 0; i < list.length; i++) {
      const r = list[i];
      if (!plainObj(r) || r.id == null) continue;
      if (typeof r.id !== "string" || !ID_RX.test(r.id)) return bad(prefix + k, i, r.t, "id is not valid");
      if (ids.has(r.id)) return bad(prefix + k, i, r.t, "the same id twice");
      ids.add(r.id);
    }
  }
  return null;
}

// One record set (a portfolio, or one history entry): its purchases, imported rows, sales and dividends; one imported row
// per stock; no sale below 0 shares.
// Ids are unique within the record set.
function recordsProblem(x, today, holds, prefix = "") {
  const lists = { purchases: x.purchases, imported: x.imported, sales: x.sales, divs: x.divs };
  for (const k of ["imported", "sales", "divs"]) if (lists[k] != null && !Array.isArray(lists[k])) return bad(prefix + k, null, null, "not a list");
  const imp = lists.imported || [];
  const byAmountT = (t) => imp.some((r) => plainObj(r) && r.t === t && r.amountWon != null);
  for (let i = 0; i < (lists.purchases || []).length; i++) { const p = purchaseProblem(lists.purchases[i], i, today, holds, prefix + "purchases"); if (p) return p; }
  const seen = new Set();
  for (let i = 0; i < imp.length; i++) {
    const p = importedProblem(imp[i], i, today, holds, prefix + "imported");
    if (p) return p;
    if (imp[i].t != null) {
      if (seen.has(imp[i].t)) return bad(prefix + "imported", i, imp[i].t, "the same stock twice");
      seen.add(imp[i].t);
    }
  }
  for (let i = 0; i < (lists.sales || []).length; i++) { const p = saleProblem(lists.sales[i], i, today, holds, byAmountT, prefix + "sales"); if (p) return p; }
  for (let i = 0; i < (lists.divs || []).length; i++) { const p = divProblem(lists.divs[i], i, today, holds, prefix + "divs"); if (p) return p; }
  const ip = idsProblem(lists, prefix);
  if (ip) return ip;
  const low = belowZero({ imported: imp, purchases: lists.purchases || [], sales: lists.sales || [], splits: x.splits, createdAt: x.createdAt });
  if (low) return bad(prefix + "sales", null, low.t, `sold more than held (${low.date || "undated"})`);
  return null;
}

function historyProblem(hs, today, splits = null, createdAt = null) {
  if (!Array.isArray(hs)) return bad("history", null, null, "not a list");
  for (let i = 0; i < hs.length; i++) {
    const h = hs[i];
    if (!plainObj(h) || !okStockCode(h.t)) return bad("history", i, null, "not an entry with a stock code");
    if (!isStr(h.nk, 120)) return bad("history", i, h.t, "name missing");
    if (!pastDate(h.out, today)) return bad("history", i, h.t, "date taken out must be a real date, not after today");
    if (h.cls != null && !isStr(h.cls, 10)) return bad("history", i, h.t, "market is not valid");
    if (h.ts != null && !okTs(h.ts)) return bad("history", i, h.t, "time taken out (ts) is not valid");
    if (h.reason != null && !isStr(h.reason, 20)) return bad("history", i, h.t, "reason is not a short name");   // v19.7a
    for (const k of ["purchases", "sales", "divs"]) if (h[k] != null && !Array.isArray(h[k])) return bad("history", i, h.t, k + " is not a list");
    if (h.imported != null && !plainObj(h.imported)) return bad("history", i, h.t, "imported is not one row");
    const recs = { purchases: h.purchases || [], sales: h.sales || [], divs: h.divs || [], imported: h.imported ? [h.imported] : [], splits, createdAt };
    const p = recordsProblem(recs, today, (t) => t === h.t, `history[${i + 1}].`);
    if (p) return p;
  }
  return null;
}

// The 기준 of an imported portfolio (its report and its 내 기준 rule read them). Only the shape is checked: whether a card
// still exists, is 준비 중 or has a new points limit is the evaluation's business (pf.js activeOf, strictTop), so a saved
// portfolio never becomes unreadable because the app's cards or strictness choices changed.
function settingsProblem(s) {
  if (!plainObj(s) || !plainObj(s.points)) return bad("settings", null, null, "the criteria points are missing");
  for (const [id, v] of Object.entries(s.points)) {
    if (!isStr(id, 40) || !(Number.isInteger(v) && v >= 0 && v <= 100)) return bad("settings", null, null, `points for ${id} are not a whole number`);
  }
  if (s.strict != null && !isStr(s.strict, 40)) return bad("settings", null, null, "strictness is not a name");
  return null;
}

// v19.6a: the stock splits a portfolio stores (see the top of this file). A split may name a stock the portfolio no longer
// holds (its records moved into history); its date is a real date (data.json lists splits up to 3 years back; one dated
// after today is not a record of the user's and is refused like any other future date).
function splitsProblem(l, today) {
  if (!Array.isArray(l)) return bad("splits", null, null, "not a list");
  const seen = new Set();
  for (let i = 0; i < l.length; i++) {
    const s = l[i];
    if (!plainObj(s) || !okStockCode(s.t) || !okSplit(s) || !isDate(s.date) || (today && s.date > today) || Object.keys(s).some((k) => !["t", "date", "r"].includes(k))) {
      return bad("splits", i, s && s.t, "not a split (code, date, ratio above 0 and not 1)");
    }
    if (seen.has(s.t + "|" + s.date)) return bad("splits", i, s.t, "the same split twice");
    seen.add(s.t + "|" + s.date);
  }
  return null;
}

// v19.7a: the change log (see the top of this file). A kind or reason this version does not know is a short name, kept and
// not shown (so a later version's entry never sets a portfolio aside).
export const CHANGES_MAX = 200;
function changesProblem(l, today) {
  if (!Array.isArray(l)) return bad("changes", null, null, "not a list");
  for (let i = 0; i < l.length; i++) {
    const c = l[i];
    if (!plainObj(c) || !pastDate(c.at, today) || !isStr(c.kind, 20)) return bad("changes", i, c && c.t, "not a change (date not after today, kind)");
    if ((c.t != null && !okStockCode(c.t)) || (c.nk != null && !isStr(c.nk, 120)) || (c.reason != null && !isStr(c.reason, 20))
      || (c.id != null && !(typeof c.id === "string" && ID_RX.test(c.id)))) {
      return bad("changes", i, c.t, "stock code, name, reason or id is not valid");
    }
  }
  return null;
}

export function deckProblem(x, today) {
  if (!plainObj(x)) return bad("deck", null, null, "not a portfolio");
  if (!isStr(x.id, 60)) return bad("id", null, null, "id missing");
  if (!isStr(x.name, 60)) return bad("name", null, null, "name missing");
  if (x.createdAt != null && !isDate(x.createdAt)) return bad("createdAt", null, null, "not a date");
  if (x.planFx != null && !isPos(x.planFx)) return bad("planFx", null, null, "rate must be above 0");   // the USD/KRW rate the plan used
  if (!Array.isArray(x.holdings) || !Array.isArray(x.purchases)) return bad("holdings", null, null, "holdings or purchases missing");
  for (let i = 0; i < x.holdings.length; i++) {
    const h = x.holdings[i];
    if (!plainObj(h) || !isStr(h.t, 20) || !isStr(h.nk, 120)) return bad("holdings", i, h && h.t, "code or name missing");
    if (h.target != null && !(isNum(h.target) && h.target >= 0 && h.target <= 1)) return bad("holdings", i, h.t, "target must be 0-1");
    if (h.plannedQty != null && !(Number.isInteger(h.plannedQty) && h.plannedQty >= 0)) return bad("holdings", i, h.t, "planned quantity not whole");
    if (h.planPx != null && !isPos(h.planPx)) return bad("holdings", i, h.t, "plan price must be above 0");   // the price the plan used
    if (h.rules != null && !Array.isArray(h.rules)) return bad("holdings", i, h.t, "rules is not a list");
    if (h.ts != null && !okTs(h.ts)) return bad("holdings", i, h.t, "time added (ts) is not valid");
  }
  if (x.removed != null) {
    if (!Array.isArray(x.removed)) return bad("removed", null, null, "not a list");
    const seen = new Set();
    for (let i = 0; i < x.removed.length; i++) {
      const r = x.removed[i];
      if (!plainObj(r) || !okStockCode(r.t) || !pastDate(r.at, today) || !okTs(r.ts) || seen.has(r.t)) return bad("removed", i, r && r.t, "not a removal mark (code, date, time), one per stock");
      seen.add(r.t);
    }
  }
  const holds = (t) => x.holdings.some((h) => h.t === t);
  if (x.splits != null) { const p = splitsProblem(x.splits, today); if (p) return p; }
  if (x.kind != null && x.kind !== "imported") return bad("kind", null, null, "unknown kind");
  if (x.imported != null && x.kind !== "imported") return bad("imported", null, null, "imported rows belong to an imported portfolio only");
  if (x.kind === "imported") {
    if (!Array.isArray(x.imported)) return bad("imported", null, null, "an imported portfolio needs its rows");
    const sp = settingsProblem(x.settings);
    if (sp) return sp;
  }
  const rp = recordsProblem(x, today, holds);
  if (rp) return rp;
  if (x.history != null) { const p = historyProblem(x.history, today, x.splits, x.createdAt); if (p) return p; }
  if (x.limits != null) {
    if (!plainObj(x.limits)) return bad("limits", null, null, "not an object");
    for (const k of Object.keys(x.limits)) {
      if (!["stock", "ind"].includes(k) || !(Number.isInteger(x.limits[k]) && x.limits[k] >= 1 && x.limits[k] <= 100)) return bad("limits", null, null, `${k} must be a whole % (1-100)`);
    }
  }
  if (x.limitsTs != null && !okTs(x.limitsTs)) return bad("limitsTs", null, null, "not a time");
  if (x.changes != null) { const p = changesProblem(x.changes, today); if (p) return p; }
  if (x.targetsTs != null && !okTs(x.targetsTs)) return bad("targetsTs", null, null, "not a time");
  if (x.confirms != null) {
    if (!Array.isArray(x.confirms)) return bad("confirms", null, null, "not a list");
    for (let i = 0; i < x.confirms.length; i++) {
      const c = x.confirms[i];
      if (!validConfirm(c, today) || !holds(c.t)) return bad("confirms", i, c && c.t, "answer is not valid");
    }
  }
  return null;
}

// "portfolio "name" (id): imported row 2 (005930): quantity must be whole shares for a Korean stock"
export function problemText(deck, p) {
  const who = plainObj(deck) ? `portfolio "${typeof deck.name === "string" ? deck.name : "?"}" (${typeof deck.id === "string" ? deck.id : "?"})` : "a portfolio";
  return `${who}: ${p.part}${p.row != null ? " row " + p.row : ""}${p.t ? " (" + p.t + ")" : ""}: ${p.why}`;
}

// ---------------- the whole store ----------------
const KNOWN_TOP = ["v", "decks", "notes", "assume", "guideSeen", "gone", "wts", "preview", "setAside", "watch", "seen"];
// -> { readable: false, why } when it is not a records store this app can read at all (not an object, an unknown or newer
// version, no portfolio list); else { readable: true, data, problems: [text] }: data keeps every valid portfolio and part,
// problems names what was set aside (a bad portfolio, a duplicate id, a bad notes / assume / guideSeen part).
export function checkStore(d, today) {
  if (!plainObj(d)) return { readable: false, why: "not an object" };
  if (d.v !== BASE_VERSION && d.v !== STORE_VERSION) return { readable: false, why: `version ${JSON.stringify(d.v)} is not one this app reads` };
  if (!Array.isArray(d.decks)) return { readable: false, why: "no portfolio list" };
  const problems = [], decks = [], ids = new Set();
  for (const x of d.decks) {
    let p = deckProblem(x, today);
    if (!p && ids.has(x.id)) p = bad("id", null, null, "the same id twice");
    if (!p && d.v === BASE_VERSION && V2_DECK_PARTS.some((k) => k !== "splits" && x[k] != null)) p = bad("version", null, null, "a version-2 part in a version-1 store");
    if (p) { problems.push(problemText(x, p)); continue; }
    ids.add(x.id);
    decks.push(x);
  }
  const data = { v: d.v, decks };
  if (d.notes != null) {
    if (validPerStock(d.notes, (n) => typeof n.text === "string" && n.text.length > 0 && n.text.length <= NOTE_MAX, today)) data.notes = d.notes;
    else problems.push("notes: not valid");
  }
  if (d.assume != null) {
    if (validPerStock(d.assume, (a) => okAssume(a), today)) data.assume = d.assume;
    else problems.push("assume (saved value assumptions): not valid");
  }
  // guideSeen is this device's flag, not a record (Jack, 2026-11-08): any real date counts as seen, also one after today
  // (written while the phone's clock was ahead), and never makes the records a problem; only a value that is not a date
  // is set aside. Records keep their own rule (no date after today).
  if (d.guideSeen != null) {
    if (isDate(d.guideSeen)) data.guideSeen = d.guideSeen;
    else problems.push("guideSeen: not a date");
  }
  if (d.wts != null) {
    if (typeof d.wts === "string" && /^[0-9a-f]{16}$/.test(d.wts)) data.wts = d.wts;
    else problems.push("wts (write fingerprint): not valid");
  }
  if (d.gone != null) {
    if (plainObj(d.gone) && (d.gone.notes == null || validPerStock(d.gone.notes, (g) => okTs(g.ts) && (g.h == null || /^[0-9a-f]{8}$/.test(g.h)), today))
      && (d.gone.watch == null || okWatchMarks(d.gone.watch))) {
      data.gone = d.gone;
    } else problems.push("gone (deleted notes or watch-list marks): not valid");
  }
  // v19.6c 관심 종목 (see the top of this file): checked like notes (a bad part is set aside with its reason, the rest reads).
  // A time after now (a clock that was ahead) is kept as stored and is never a reason to set it aside (round-3 review).
  if (d.watch != null) {
    const p = watchProblem(d.watch, today);
    if (p) problems.push("watch (the watch list): " + p); else data.watch = d.watch;
  }
  // v19.6b 오늘 볼 것 · 확인했어요 marks (see the top of this file): a bad part is set aside with its reason, the rest reads
  if (d.seen != null) {
    const p = seenProblem(d.seen);
    if (p) problems.push("seen (marks of filings the user has read): " + p); else data.seen = d.seen;
  }
  // A top-level part this version does not know (a later version's) is kept as it is, so a write from this tab never drops
  // it; this app reads nothing from it.
  for (const k of Object.keys(d)) if (!KNOWN_TOP.includes(k)) data[k] = d[k];
  return { readable: true, data, problems };
}

// Every field the app reads back is checked. One bad field anywhere -> false (a records file is refused whole).
export function validStore(d, today) {
  const r = checkStore(d, today);
  return r.readable && !r.problems.length;
}

// ---------------- per stock: 내 메모 and saved assumptions (v19.1a Part E, Part D) ----------------
export const NOTE_MAX = 500;
function validPerStock(m, ok, today) {
  if (!plainObj(m)) return false;
  for (const [t, v] of Object.entries(m)) {
    if (!okStockCode(t) || !plainObj(v) || !isDate(v.at) || (today && v.at > today) || (v.ts != null && !okTs(v.ts)) || !ok(v)) return false;
  }
  return true;
}
const perStock = (d, key) => (d && plainObj(d[key]) ? d[key] : null);

// The store with this stock's note set (text trimmed; empty text removes the note). Pure: the caller saves it.
// null = nothing valid to save (too long, a bad code or date). ts (the screens pass Date.now()): the time of the edit,
// kept on the note, and a deleted note leaves a mark under gone, so another tab's older copy never brings it back.
export function withNote(data, t, text, today, ts = null) {
  if (!okStockCode(t) || !isDate(today) || typeof text !== "string" || (ts != null && !okTs(ts))) return null;
  const v = text.trim();
  if (v.length > NOTE_MAX) return null;
  const notes = { ...(perStock(data, "notes") || {}) };
  const had = plainObj(notes[t]) ? notes[t] : null;
  if (v) notes[t] = { text: v, at: today, ...(ts ? { ts } : {}) }; else delete notes[t];
  const { notes: _n, gone: _g, ...rest } = data || {};
  const gn = { ...(data && plainObj(data.gone) && plainObj(data.gone.notes) ? data.gone.notes : {}) };
  if (v) delete gn[t]; else if (ts && had) gn[t] = { at: today, ts, h: textHash(had.text) };
  const gone = { ...(data && plainObj(data.gone) ? data.gone : {}), notes: gn };
  if (!Object.keys(gn).length) delete gone.notes;
  return { ...rest, ...(Object.keys(notes).length ? { notes } : {}), ...(Object.keys(gone).length ? { gone } : {}) };
}

// The store with this stock's 가치 자세히 assumption (discount rate and 5년 뒤 성장률, the calculator's own ranges).
export function withAssume(data, t, a, today, ts = null) {
  if (!okStockCode(t) || !isDate(today) || !okAssume(a) || (ts != null && !okTs(ts))) return null;
  return { ...data, assume: { ...(perStock(data, "assume") || {}), [t]: { disc: a.disc, term: a.term, at: today, ...(ts ? { ts } : {}) } } };
}
// A short fingerprint of a deleted note's text (FNV-1a, 8 hex digits): a deletion mark knows which note it deleted, so
// another tab's copy of that same note never comes back, whatever its time.
export function textHash(text) {
  let h = 0x811c9dc5;
  const s = String(text);
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, "0");
}
export const noteOf = (data, t) => { const n = perStock(data, "notes"); return n && plainObj(n[t]) ? n[t] : null; };
export const assumeOf = (data, t) => { const a = perStock(data, "assume"); return a && plainObj(a[t]) && okAssume(a[t]) ? a[t] : null; };
// What travels in a records file besides the portfolios (the guide flag stays on the device).
// v19.6c: 관심 종목 too, without hitAt (this device's mark, Part C [Q7]); deletion marks (gone) stay on the device.
// v19.6b: the 확인했어요 marks too (A.1 [Q6]: a records file brings them, merged as a union).
const extras = (d) => ({ ...(perStock(d, "notes") ? { notes: d.notes } : {}), ...(perStock(d, "assume") ? { assume: d.assume } : {}),
  ...(plainObj(d && d.watch) ? { watch: watchNoHits(d.watch) } : {}), ...(Array.isArray(d && d.seen) && d.seen.length ? { seen: d.seen } : {}) });

// ---------------- 오늘 볼 것 · 확인했어요 (v19.6b, v19.6 Part B.2; the shape is at the top of this file) ----------------
export const SEEN_MAX = 500;
export const SEEN_DAYS = 120;
export const SEEN_KINDS = ["rights", "cb", "bw"];
const okYmd8 = (x) => typeof x === "string" && /^\d{8}$/.test(x) && isDate(`${x.slice(0, 4)}-${x.slice(4, 6)}-${x.slice(6, 8)}`);
const okRc = (x) => typeof x === "string" && /^\d{14}$/.test(x);
const nullOr = (x, ok) => x == null || ok(x);
// null when the part is valid, else the first problem (English, for the console)
export function seenProblem(s) {
  if (!Array.isArray(s)) return "not a list";
  if (s.length > SEEN_MAX) return `more than ${SEEN_MAX} marks`;
  for (let i = 0; i < s.length; i++) {
    const e = s[i], at = `mark ${i + 1}`;
    if (!plainObj(e) || !okStockCode(e.t)) return `${at}: not a mark with a stock code`;
    if (!SEEN_KINDS.includes(e.kind)) return `${at} (${e.t}): the kind must be ${SEEN_KINDS.join(", ")}`;
    if (!nullOr(e.bd, okYmd8)) return `${at} (${e.t}): the board date must be YYYYMMDD or null`;
    if (!["n", "p", "amt"].every((k) => nullOr(e[k], isPos))) return `${at} (${e.t}): numbers must be above 0 or null`;
    if (!nullOr(e.rc, okRc)) return `${at} (${e.t}): the filing number must be 14 digits`;
    if (!isDate(e.at)) return `${at} (${e.t}): the date must be a real date`;
    if (!nullOr(e.ts, okTs)) return `${at} (${e.t}): the time must be a time in ms`;
  }
  return null;
}
export const seenOf = (data) => (data && Array.isArray(data.seen) ? data.seen.filter(plainObj) : []);
const nv = (x) => (x == null ? null : x);
// The same decision with the same numbers (a 정정 with other numbers is not), on the same filing, or on the same board date when
// the mark has one and at least one number (two blank marks would otherwise match every blank decision of that stock and kind).
// r: a disc.json issue row (or another mark).
const hasNumber = (e) => ["n", "p", "amt"].some((k) => nv(e[k]) != null);
export const seenMatch = (e, r) => !!(plainObj(e) && plainObj(r) && e.t === r.t && e.kind === r.kind
  && ["n", "p", "amt"].every((k) => nv(e[k]) === nv(r[k]))
  && ((okRc(e.rc) && e.rc === r.rc) || (e.bd != null && hasNumber(e) && nv(e.bd) === nv(r.bd))));
export const isSeen = (data, r) => seenOf(data).some((e) => seenMatch(e, r));
const seenKey = (e) => canon({ t: e.t, kind: e.kind, bd: nv(e.bd), n: nv(e.n), p: nv(e.p), amt: nv(e.amt), rc: nv(e.rc) });
// Two lists of marks: every mark of the current one, then the other's; the same mark keeps the later time (laterOf). At most
// SEEN_MAX, the newest kept in their order (a merge never makes a list the store's own check refuses).
function unionSeen(cur, other) {
  const out = [], at = new Map();
  for (const e of [...seenOf(cur), ...seenOf(other)]) {
    const k = seenKey(e);
    if (!at.has(k)) { at.set(k, out.length); out.push(e); } else out[at.get(k)] = laterOf(out[at.get(k)], e);
  }
  if (out.length <= SEEN_MAX) return out;
  const rank = out.map((e, i) => i).sort((a, b) => -editOrder(out[a], out[b]) || b - a);     // newest first (the later one on a tie)
  const keep = new Set(rank.slice(0, SEEN_MAX));
  return out.filter((e, i) => keep.has(i));
}
// The store with row r marked 확인했어요 today (ts: the time, Date.now()), marks older than SEEN_DAYS before today left out,
// at most SEEN_MAX (the newest). null when there is nothing valid to save (a row that is not a decision of the three kinds).
export function withSeen(data, r, today, ts = null) {
  if (!plainObj(r) || !okStockCode(r.t) || !SEEN_KINDS.includes(r.kind) || !isDate(today) || (ts != null && !okTs(ts))) return null;
  const e = { t: r.t, kind: r.kind, bd: okYmd8(r.bd) ? r.bd : null, n: isPos(r.n) ? r.n : null, p: isPos(r.p) ? r.p : null,
    amt: isPos(r.amt) ? r.amt : null, ...(okRc(r.rc) ? { rc: r.rc } : {}), at: today, ...(ts != null ? { ts } : {}) };
  const from = new Date(Date.parse(today + "T00:00:00Z") - SEEN_DAYS * 86400000).toISOString().slice(0, 10);
  const keep = seenOf(data).filter((x) => isDate(x.at) && x.at >= from && seenKey(x) !== seenKey(e));
  const seen = [...keep, e].slice(-SEEN_MAX);
  return seenProblem(seen) ? null : { ...data, seen };
}

// ---------------- 관심 종목 (v19.6c, v19.6 Part C; the shape is at the top of this file) ----------------
export const WATCH_MAX = 30;
export const WATCH_KINDS = ["pxBelow", "pbrBelow", "dyAtLeast"];
// v has at most d decimals (a typed number, so a float error of 1e-6 is allowed)
const decimals = (v, d) => Math.abs(v * 10 ** d - Math.round(v * 10 ** d)) < 1e-6;
// The limit of one kind's number (also what the condition sheet accepts): pxBelow 2 decimals (a Korean price is checked as
// whole won by the sheet, which knows the market), pbrBelow and dyAtLeast 1 decimal.
export const WATCH_DEC = { pxBelow: 2, pbrBelow: 1, dyAtLeast: 1 };
export const WATCH_TOP = { pxBelow: 1e12, pbrBelow: 1000, dyAtLeast: 100 };
export const okWatchValue = (k, v) => WATCH_KINDS.includes(k) && isNum(v) && v > 0 && v <= WATCH_TOP[k] && decimals(v, WATCH_DEC[k]);
function condProblem(c) {
  if (!plainObj(c) || !isStr(c.k, 20)) return "a condition without a kind";
  if (c.hitAt != null && !isDate(c.hitAt)) return "hitAt is not a date";
  if (c.hitTs != null && !okTs(c.hitTs)) return "hitTs is not a time";
  if (!WATCH_KINDS.includes(c.k)) return null;                 // a later version's kind: kept as it is, not read
  return okWatchValue(c.k, c.v) ? null : `${c.k}: the number is not valid`;
}
// v19.6c round-3 review (like limitsSaveTime for 내 규칙): the time to stamp an edit of stock t with — now, or just after the
// latest time this device already holds for that stock (its entry or deletion mark in the records, or beside them in
// key + ".watch") when that is later: a clock that was ahead and has been corrected, or set back. So the newest edit is
// always the latest, and an older edit of a stale tab never wins over it.
const watchTimes = (d, t) => [watchOf(d)[t], watchGone(d)[t]].filter(plainObj).map((x) => x.ts).filter(okTs);
export function watchSaveTime(key, data, t, now = Date.now()) {
  let x = now;
  for (const v of watchTimes(data, t)) x = Math.max(x, v + 1);
  try {
    const sw = key ? readSideWatch(key) : null;
    if (sw) for (const v of watchTimes(sideAsStore(sw), t)) x = Math.max(x, v + 1);
  } catch (e) { /* the records' times are enough */ }
  return x;
}
// gone.watch: { [code]: { at, ts } } (a date, a time)
const okWatchMarks = (m) => plainObj(m) && Object.entries(m).every(([t, g]) => okStockCode(t) && plainObj(g) && isDate(g.at) && okTs(g.ts));
// null when the 관심 종목 part is valid, else the first problem (English, for the console). max: WATCH_MAX (the side key
// beside the records, which keeps the latest state of every stock this app wrote, takes more).
export function watchProblem(w, today, max = WATCH_MAX) {
  if (!plainObj(w)) return "not an object";
  const ts = Object.keys(w);
  if (ts.length > max) return `more than ${max} stocks`;
  for (const t of ts) {
    const e = w[t];
    if (!okStockCode(t) || !plainObj(e)) return `${t}: not an entry with a stock code`;
    if (!isDate(e.at)) return `${t}: the date added must be a real date`;
    if (e.ts != null && !okTs(e.ts)) return `${t}: the time (ts) is not valid`;
    if (e.nk != null && !isStr(e.nk, 120)) return `${t}: the name is not valid`;
    if (e.conds != null) {
      if (!Array.isArray(e.conds) || e.conds.length > 10) return `${t}: conditions are not a short list`;
      const kinds = new Set();
      for (const c of e.conds) {
        const p = condProblem(c);
        if (p) return `${t}: ${p}`;
        if (kinds.has(c.k)) return `${t}: two conditions of one kind (${c.k})`;
        kinds.add(c.k);
      }
    }
  }
  return null;
}
export const watchOf = (data) => (data && plainObj(data.watch) ? data.watch : {});
// The list in screen order: the latest added first (at, then the time of the last edit, then the code). A records file's
// "own order" (Part C [Q6]) is this order of its entries too: object key order is not kept for Korean codes (a code
// without a leading zero is read as a number key and comes first).
export function watchOrder(w) {
  const m = plainObj(w) ? w : {};
  return Object.keys(m).sort((a, b) => {
    const x = m[a] || {}, y = m[b] || {};
    if (x.at !== y.at) return String(y.at) < String(x.at) ? -1 : 1;
    const tx = okTs(x.ts) ? x.ts : 0, ty = okTs(y.ts) ? y.ts : 0;
    if (tx !== ty) return ty - tx;
    return a < b ? -1 : a > b ? 1 : 0;
  });
}
// An entry without this device's hitAt marks (what a records file carries).
function noHits(e) {
  if (!plainObj(e) || !Array.isArray(e.conds)) return e;
  return { ...e, conds: e.conds.map((c) => { if (!plainObj(c) || (c.hitAt == null && c.hitTs == null)) return c; const { hitAt: _h, hitTs: _s, ...r } = c; return r; }) };
}
export const watchNoHits = (w) => Object.fromEntries(Object.entries(w).map(([t, e]) => [t, noHits(e)]));
const watchGone = (d) => (d && plainObj(d.gone) && plainObj(d.gone.watch) ? d.gone.watch : {});
// d with watch (and the gone.watch marks) replaced; an empty part is left out.
function withWatchParts(d, watch, marks) {
  const { watch: _w, gone: _g, ...rest } = d || {};
  const gone = { ...(d && plainObj(d.gone) ? d.gone : {}) };
  delete gone.watch;
  if (marks && Object.keys(marks).length) gone.watch = marks;
  return { ...rest, ...(watch && Object.keys(watch).length ? { watch } : {}), ...(Object.keys(gone).length ? { gone } : {}) };
}

// 관심 종목에 추가 (the company page). -> the store, or null: a bad code or date, already there, or full (the screen says
// WATCH_MAX). nk: the name today (shown while the stock is missing from a later day's data). ts: the time (Date.now()).
export function withWatchAdd(data, t, nk, today, ts = null) {
  const w = watchOf(data);
  if (!okStockCode(t) || !isDate(today) || (ts != null && !okTs(ts)) || plainObj(w[t]) || Object.keys(w).length >= WATCH_MAX) return null;
  const e = { at: today, ...(ts != null ? { ts } : {}), ...(isStr(nk, 120) ? { nk } : {}) };
  const marks = { ...watchGone(data) };
  delete marks[t];
  return withWatchParts(data, { ...w, [t]: e }, marks);
}
// 관심 종목에서 빼기. With a time, a deletion mark (gone.watch) keeps another tab's older copy from bringing it back.
export function withWatchRemove(data, t, today, ts = null) {
  const w = watchOf(data);
  if (!plainObj(w[t]) || !isDate(today) || (ts != null && !okTs(ts))) return null;
  const rest = { ...w };
  delete rest[t];
  const marks = { ...watchGone(data), ...(ts != null ? { [t]: { at: today, ts } } : {}) };
  return withWatchParts(data, rest, marks);
}
// The conditions of one stock: conds [{ k, v }] (one per known kind; an empty list removes them all). A condition with the
// same kind and number as before keeps its hitAt (nothing changed); a new or changed one starts without. A later version's
// conditions on the entry stay. -> the store, or null when a number is not valid.
export function withWatchConds(data, t, conds, today, ts = null) {
  const w = watchOf(data), e = w[t];
  if (!plainObj(e) || !Array.isArray(conds) || !isDate(today) || (ts != null && !okTs(ts))) return null;
  const kinds = new Set();
  for (const c of conds) {
    if (!plainObj(c) || !okWatchValue(c.k, c.v) || kinds.has(c.k)) return null;
    kinds.add(c.k);
  }
  const old = Array.isArray(e.conds) ? e.conds : [];
  const known = WATCH_KINDS.map((k) => conds.find((c) => c.k === k)).filter(Boolean).map((c) => {
    const was = old.find((x) => plainObj(x) && x.k === c.k);
    const keep = was && was.v === c.v;
    return { k: c.k, v: c.v, ...(keep && isDate(was.hitAt) ? { hitAt: was.hitAt } : {}), ...(keep && okTs(was.hitTs) ? { hitTs: was.hitTs } : {}) };
  });
  const later = old.filter((x) => plainObj(x) && !WATCH_KINDS.includes(x.k));
  const { conds: _c, ts: _t, ...base } = e;
  const next = { ...base, ...(ts != null ? { ts } : okTs(e.ts) ? { ts: e.ts } : {}), ...(known.length || later.length ? { conds: [...known, ...later] } : {}) };
  return withWatchParts(data, { ...w, [t]: next }, watchGone(data));
}
// hitAt marks set or cleared (watch.js withWatchHits decides which): marks = Map "code|kind" -> date (set) or null (clear).
// The entry's own time does not change (the user did not edit anything); the condition gets hitTs, the time of this mark
// (now, or just after its earlier mark's time), so a copy holding an older mark never wins over it (round-3 review).
// -> the store, or null when nothing changed.
export function withWatchMarks(data, marks, now = Date.now()) {
  const w = watchOf(data);
  let changed = false;
  const out = {};
  for (const [t, e] of Object.entries(w)) {
    if (!plainObj(e) || !Array.isArray(e.conds)) { out[t] = e; continue; }
    let touched = false;
    const conds = e.conds.map((c) => {
      const key = t + "|" + (plainObj(c) ? c.k : "");
      if (!plainObj(c) || !marks.has(key)) return c;
      const d = marks.get(key);
      if (d == null ? c.hitAt == null : c.hitAt === d || !isDate(d)) return c;
      touched = true;
      const hitTs = Math.max(now, okTs(c.hitTs) ? c.hitTs + 1 : 0);
      if (d == null) { const { hitAt: _h, ...r } = c; return { ...r, hitTs }; }
      return { ...c, hitAt: d, hitTs };
    });
    out[t] = touched ? { ...e, conds } : e;
    changed = changed || touched;
  }
  return changed ? { ...data, watch: out } : null;
}

// Two copies of the list (another tab's, v19.6 A.1 [Q5]): per stock, the later edit wins between an entry and a deletion
// mark (laterOf: the time, then the date; the current copy on a tie, so its hitAt stays). At most WATCH_MAX: the current
// copy's stocks first, then the other copy's, each in screen order (Part C [Q6]'s rule for 기록 불러오기); a stock left out
// makes the screens say 합쳤어요 (droppedFrom). -> { watch, marks }.
function watchState(d, t) {
  const e = watchOf(d)[t], g = watchGone(d)[t];
  const entry = plainObj(e) ? e : null, del = plainObj(g) ? { ...g, gone: true } : null;
  if (entry && del) {
    if (okTs(entry.ts)) return entry.ts >= del.ts ? entry : del;
    return isDate(entry.at) && entry.at > del.at ? entry : del;
  }
  return entry || del;
}
// The winning entry w with, per condition (the same kind and number in the other copy's entry l), the later hitAt mark of the
// two by hitTs (a mark set or cleared: withWatchMarks). So a copy that never saw today's mark (a tab of the app before v19.6c,
// a stale tab) neither drops it nor puts back a cleared one (round-3 review); a condition changed since keeps its own.
function laterHits(w, l) {
  if (!Array.isArray(w.conds) || !Array.isArray(l.conds)) return w;
  let changed = false;
  const conds = w.conds.map((c) => {
    const x = plainObj(c) && WATCH_KINDS.includes(c.k) ? l.conds.find((y) => plainObj(y) && y.k === c.k && y.v === c.v) : null;
    if (!x || !(okTs(x.hitTs) && !(okTs(c.hitTs) && c.hitTs >= x.hitTs))) return c;
    changed = true;
    const { hitAt: _h, hitTs: _s, ...r } = c;
    return { ...r, ...(isDate(x.hitAt) ? { hitAt: x.hitAt } : {}), hitTs: x.hitTs };
  });
  return changed ? { ...w, conds } : w;
}
function unionWatch(cur, other) {
  const codes = new Set([...Object.keys(watchOf(cur)), ...Object.keys(watchGone(cur)), ...Object.keys(watchOf(other)), ...Object.keys(watchGone(other))]);
  const won = {}, marks = {};
  for (const t of codes) {
    const c = watchState(cur, t), o = watchState(other, t);
    const w = laterOf(c, o);
    if (!w) continue;
    if (w.gone) { marks[t] = { at: w.at, ts: w.ts }; continue; }
    const l = w === c ? o : c;
    won[t] = l && !l.gone ? laterHits(w, l) : w;
  }
  const order = [...watchOrder(Object.fromEntries(Object.entries(won).filter(([t]) => plainObj(watchOf(cur)[t])))),
    ...watchOrder(Object.fromEntries(Object.entries(won).filter(([t]) => !plainObj(watchOf(cur)[t]))))];
  return { watch: Object.fromEntries(order.slice(0, WATCH_MAX).map((t) => [t, won[t]])), marks };
}
// 관심 종목 of a records file taken in (Part C [Q6]): this device's list first, then the file's stocks it does not hold, in the
// file's order, up to WATCH_MAX; dropped = how many did not fit (the screen says so). The file never brings hitAt. A stock this
// device had taken out comes back as an edit made now (ts) and loses its deletion mark (the file is the user's latest word).
// known: the other copies of this device's records (storedStores): a deletion mark in any of them counts.
export function watchImport(cur, inc, ts = null, known = []) {
  const mine = watchOf(cur), file = plainObj(inc && inc.watch) ? watchNoHits(inc.watch) : {};
  const marks = { ...watchGone(cur) };
  const markOf = (t) => [cur, ...(Array.isArray(known) ? known : [])].map((d) => watchGone(d)[t]).filter((g) => plainObj(g) && okTs(g.ts))
    .reduce((a, g) => (!a || g.ts > a.ts ? g : a), null);
  const out = { ...mine };
  let n = Object.keys(out).length, dropped = 0;
  for (const t of watchOrder(file)) {
    if (plainObj(out[t])) continue;
    if (n >= WATCH_MAX) { dropped++; continue; }
    const g = markOf(t);
    out[t] = g && okTs(ts) ? { ...file[t], ts: Math.max(ts, g.ts + 1) } : file[t];
    delete marks[t];
    n++;
  }
  return { watch: out, marks, dropped };
}
// mergeStores marks what it returns with the number of 관심 종목 a records file brought that did not fit (portfolio.jsx).
export const WATCH_DROPPED = Symbol("watch-list stocks a records file brought that did not fit");

// ---------------- the first-visit guide (v19.3c Part E) ----------------
// The flag of the old key (key + ".guideSeen" = "1", v19.3c): read once into the store, never written again.
export const OLD_GUIDE_SUFFIX = ".guideSeen";
export const guideSeenIn = (data) => !!(data && isDate(data.guideSeen));
// The store with the guide marked as seen today (kept when it already is). Pure: the caller saves it.
export function withGuideSeen(data, today) {
  if (!isDate(today)) return null;
  return guideSeenIn(data) ? data : { ...data, guideSeen: today };
}

// ---------------- 확인 필요: the user's answers (v18.3 Part C) ----------------
// A dividend drop is never 규칙 깨짐 on its own: the user answers 실제로 줄였어요 ("cut": the sell condition fired) or
// 줄인 게 아니에요 ("notCut": cleared). The answer is stored in the deck record as { t, rule, fy, a, b, answer, at }:
// it covers only that report year and those two numbers (주당 a원 -> b원), so a later, newer cut is asked about again,
// and so is the same report if its numbers change.
export const CONFIRM_ANSWERS = ["cut", "notCut"];
export const sameConfirm = (x, y) => !!(x && y && x.t === y.t && x.rule === y.rule && x.fy === y.fy && x.a === y.a && x.b === y.b);

function validConfirm(c, today) {
  return !!(c && typeof c === "object" && !Array.isArray(c) && isStr(c.t, 20) && c.rule === "divCut" && Number.isInteger(c.fy)
    && isNum(c.a) && isNum(c.b) && c.b >= 0 && c.b < c.a && CONFIRM_ANSWERS.includes(c.answer) && isDate(c.at) && !(today && c.at > today)
    && (c.ts == null || okTs(c.ts)));
}

// The store with one answer recorded (it replaces an earlier answer for the same item). Pure: the caller saves it.
// Returns null when the item, the answer or the deck is not valid (nothing to save). ts: the time of the answer (ms).
export function withConfirm(data, deckId, item, answer, today, ts = null) {
  const c = { t: item && item.t, rule: item && item.rule, fy: item && item.fy, a: item && item.a, b: item && item.b, answer, at: today, ...(ts != null ? { ts } : {}) };
  if (!validConfirm(c, today)) return null;
  const deck = data.decks.find((d) => d.id === deckId);
  if (!deck || !deck.holdings.some((h) => h.t === c.t)) return null;
  const confirms = [...(deck.confirms || []).filter((x) => !sameConfirm(x, c)), c];
  return { ...data, decks: data.decks.map((d) => (d.id === deckId ? { ...d, confirms } : d)) };
}

// 포트폴리오에서 빼기 (v19.0c): the store without one stock of one portfolio — its holding, its purchases, its imported row
// and its answers to 확인 필요. Pure: the caller saves it, and only when the user tapped the button (the screen offers it
// only for a stock missing from today's data). The portfolio itself stays, even with no stock left. null = nothing to remove.
// v19.6 A.3: when the stock has any sale or dividend, its records move into the portfolio's history instead of going
// away (내 수익 keeps its realized gains and dividends); with none, the old behaviour stays.
// With today's date the portfolio also keeps a removal mark { t, at, ts } (removed), so another tab's older copy that
// still holds the stock does not bring it back when the two are merged.
// v19.7a: reason (빼기's chip: thesis · rule · better · other) goes on the history entry it makes.
export function withoutHolding(data, deckId, t, today = null, ts = null, reason = null) {
  const deck = data && Array.isArray(data.decks) ? data.decks.find((d) => d && d.id === deckId) : null;
  if (!deck || typeof t !== "string" || !deck.holdings.some((h) => h && h.t === t)) return null;
  const of = (list) => (Array.isArray(list) ? list.filter((r) => r && r.t === t) : []);
  const rest = (list) => list.filter((r) => !(r && r.t === t));
  const sales = of(deck.sales), divs = of(deck.divs);
  const next = { ...deck, holdings: deck.holdings.filter((h) => h.t !== t), purchases: rest(deck.purchases),
    ...(Array.isArray(deck.confirms) ? { confirms: rest(deck.confirms) } : {}),
    ...(Array.isArray(deck.imported) ? { imported: rest(deck.imported) } : {}),
    ...(Array.isArray(deck.sales) ? { sales: rest(deck.sales) } : {}),
    ...(Array.isArray(deck.divs) ? { divs: rest(deck.divs) } : {}) };
  if (isDate(today)) {
    const when = okTs(ts) ? ts : Date.now();
    next.removed = [...(Array.isArray(deck.removed) ? deck.removed.filter((r) => !(r && r.t === t)) : []), { t, at: today, ts: when }];
  }
  if (sales.length || divs.length) {
    const h = deck.holdings.find((x) => x.t === t);
    const imp = of(deck.imported)[0];
    const out = isDate(today) ? today : [...sales, ...divs].reduce((a, r) => (r.date > a ? r.date : a), "0000-00-00");
    next.history = [...(Array.isArray(deck.history) ? deck.history : []), { t, nk: h.nk, out, ...(isDate(today) ? { ts: okTs(ts) ? ts : Date.now() } : {}), ...(h.cls ? { cls: h.cls } : {}),
      ...(imp ? { imported: imp } : {}), purchases: of(deck.purchases), sales, divs, ...(isStr(reason, 20) ? { reason } : {}) }];
  }
  return { ...data, decks: data.decks.map((d) => (d.id === deckId ? next : d)) };
}

// A new portfolio added to the store (가진 종목 넣기 · 매일 점검 시작하기). null when it is not valid (nothing saved).
export function withDeck(data, deck, today) {
  const p = deckProblem(deck, today);
  if (p) { console.warn("[v2] portfolio not saved: " + problemText(deck, p)); return null; }
  if (data.decks.some((d) => d.id === deck.id)) { console.warn("[v2] portfolio not saved: the same id twice (" + deck.id + ")"); return null; }
  return { ...data, decks: [...data.decks, deck] };
}

// ---------------- another tab (v19.6 A.1 [Q5]: no record lost, in either direction) ----------------
// Keys beside the records (key):
//   key + ".mine"               the text this app last wrote. The earlier app (a tab still open from before v19.3d)
//                               overwrites the records without looking and never touches this key, so when the records
//                               differ from it on the next start, it is merged back like any copy below. It starts once
//                               the records exist (an import into an empty storage changes no other key) and an open
//                               tab also keeps its own text when another tab writes over it (keepOwnText);
//   key + ".unreadable.<time>"  what a write found and could not read: this app's own set-aside portfolios, a newer
//                               version's store, or a v2 store an earlier-app tab moved aside before writing its own;
//   key + ".other.<time>"       what another tab had written since this tab last read or wrote (kept before this tab writes);
//   key + ".restored.<time>"    a copy of what was merged back.
// On start every readable copy (".mine", ".other.", and a v2 store with v2 parts in ".unreadable.") is merged in, newest
// first: on a tie the newer copy's value stays. A copy whose merge would not read back stays where it is (unmerged: the
// screens say records were kept aside). A copy leaves only when everything in it is stored elsewhere: merged back (then
// kept under ".restored.", of which the newest BACKUPS_KEEP stay), or held by a later write (a write skips or removes the
// copies all of whose records it holds, or a later edit replaced). Nothing else is ever pruned.
export const BACKUPS_KEEP = 3;
export const MINE = ".mine";
const BACKUP_KINDS = [".unreadable.", ".other.", ".restored."];
// The text this tab last read or wrote, per key: a write that finds anything else there knows another tab wrote meanwhile.
const lastText = new Map();
const stamp = (k) => Number(k.slice(k.lastIndexOf(".") + 1)) || 0;
const backupKeys = (key, mid) => {
  const out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (typeof k === "string" && k.startsWith(key + mid)) out.push(k);
    }
  } catch (e) { return []; }
  return out.sort((a, b) => stamp(a) - stamp(b));
};
// A backup key not in use: from time t on, the first time no key of the kinds in among holds (a new backup: no kind, so
// two copies made in one millisecond never share a time; a .restored. copy keeps its source's time when it is free).
function backupKey(key, kind, t = Date.now(), among = BACKUP_KINDS) {
  try { while (among.some((k) => localStorage.getItem(key + k + t) != null)) t++; } catch (e) { /* the write will say */ }
  return key + kind + t;
}
// A fingerprint of the records (everything but wts, preview and setAside, in canonical order): 16 hex digits.
function fnv(s, h) {
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, "0");
}
export function storeHash(d) {
  const { wts: _w, preview: _p, setAside: _s, ...rest } = plainObj(d) ? d : {};
  const t = canon(rest);
  return fnv(t, 0x811c9dc5) + fnv(t, 0x050c5d1f);
}
const stamped = (d) => ({ ...d, wts: storeHash(d) });
// mergeStores marks what it returns (a records file taken in): writeStore stores it as it is, without a fingerprint.
export const FROM_FILE = Symbol("from a records file");
// The fingerprint of the write a stored text came from (null: none, e.g. the earlier app imported a file).
function lineageOf(text) {
  try { const d = JSON.parse(text); return plainObj(d) && typeof d.wts === "string" ? d.wts : null; } catch (e) { return null; }
}
// Did the stored text a come from b's write (the earlier app saved from it: it keeps the fingerprint)? Then a's changes,
// deletions too, are the user's own: b is not merged back into it.
function sameLineage(a, b) { const x = lineageOf(a); return !!x && x === lineageOf(b); }
const readCopy = (k, today) => {
  try { const d = JSON.parse(localStorage.getItem(k)); return d && validStore(d, today) ? d : null; } catch (e) { return null; }
};
// The same record whatever the order of its fields. Records are shallow; past CANON_DEPTH (a later version's deep part)
// the part is compared as stored, and one too deep even for that compares as the same.
const CANON_DEPTH = 40;
function canon(x, depth = 0) {
  if (depth > CANON_DEPTH) { try { return JSON.stringify(x); } catch (e) { return '"\u0000deep"'; } }
  if (Array.isArray(x)) return "[" + x.map((y) => canon(y, depth + 1)).join(",") + "]";
  if (x && typeof x === "object") return "{" + Object.keys(x).sort().map((k) => JSON.stringify(k) + ":" + canon(x[k], depth + 1)).join(",") + "}";
  return JSON.stringify(x);
}
const same = (a, b) => canon(a) === canon(b);
const hasId = (r) => plainObj(r) && typeof r.id === "string";
const sameRec = (a, b) => (hasId(a) && hasId(b) ? a.id === b.id : same(a, b));
// Which of two saved values (a note, an assumption, an answer, or a deletion mark) is the later edit: x is the current
// (or a newer) copy's, y an older copy's. The later date wins, then on the same date the later time (ts, ms). On the
// same date an edit with a time beats one without: a value without one was saved before v19.3d or by the earlier app,
// and a tab left open (of either app) carries such a value unchanged, so preferring the copy written last would let a
// stale tab undo an edit made with this app (random runs: 14 such per 200 sequences, 0 with this rule). With no time on
// either side, or the same, x (never the older copy's).
// When both carry a time, the time decides (a value 기록 불러오기 brought in keeps its date but gets the time it came in).
function editOrder(x, y) {
  if (okTs(x.ts) && okTs(y.ts) && x.ts !== y.ts) return x.ts > y.ts ? 1 : -1;
  if (isDate(x.at) && isDate(y.at) && x.at !== y.at) return x.at > y.at ? 1 : -1;
  return 0;
}
function laterOf(x, y) {
  if (!x) return y;
  if (!y) return x;
  const o = editOrder(x, y);
  if (o) return o > 0 ? x : y;
  if (okTs(y.ts) && !okTs(x.ts)) return y;
  return x;
}
// a is a later edit than b by its time or date (not only by the tie rule)
const surelyLater = (a, b) => !!(a && b && editOrder(a, b) > 0);
// A portfolio's limits (내 규칙 정하기) as one edit: { limits, ts } (null: never saved, the defaults), and its values only
// (no part = the defaults) to tell two copies' limits apart.
// A limitsTs more than a day ahead of now (a clock that was fast) counts as no time at all (review 4): every merge, the
// check of what a copy holds, the side key and 기록 불러오기 then let a believable 저장 outrank it (laterOf: a time wins
// over none), and a merge writes the limits back without it. The raw time still travels (ahead): when both sides of a
// merge are that far ahead (this device's clock is the one set back, review 5), the later of the two stays and is written
// back with its time (laterLimits: still no time while merging, so a believable 저장 met later in the same merge outranks
// it whatever the order of the copies, review 6). With the clock set back by more than a day, this keeps the last 저장
// only when every copy was saved inside that gap: an older 저장 saved before it can win (and the screens say 합쳤어요).
// Known limits (review 5): A — a 저장 made with the clock more than a day fast loses to an older believable copy once the
// clock is right again (and the same for 기록 불러오기 of a file without limits); B — a time 24–48 h ahead becomes
// believable again later, and can then silently bring back an older 저장 over a later one stamped by the right clock;
// C — with the clock set back by more than a day, an older 저장 can win (see above).
const LIMITS_AHEAD = 24 * 3600 * 1000;
const believable = (ts, now = Date.now()) => okTs(ts) && ts <= now + LIMITS_AHEAD;
const limitsEdit = (d) => (plainObj(d) && (plainObj(d.limits) || d.limitsTs != null)
  ? { limits: plainObj(d.limits) ? d.limits : null, ts: believable(d.limitsTs) ? d.limitsTs : undefined,
    ...(okTs(d.limitsTs) && !believable(d.limitsTs) ? { ahead: d.limitsTs } : {}) } : null);
const laterLimits = (a, b) => (a && b && a.ahead && b.ahead
  ? { ...(b.ahead > a.ahead ? b : a), ts: undefined, ahead: Math.max(a.ahead, b.ahead), keep: true } : laterOf(a, b));
const limitValues = (l) => canon({ stock: plainObj(l) && l.stock != null ? l.stock : null, ind: plainObj(l) && l.ind != null ? l.ind : null });
// d with the limits of edit e (null: none)
const withLimitsEdit = (d, e) => {
  const { limits: _l, limitsTs: _t, ...rest } = d;
  return { ...rest, ...(e && e.limits ? { limits: e.limits } : {}),
    ...(e && okTs(e.ts) ? { limitsTs: e.ts } : e && e.keep && okTs(e.ahead) ? { limitsTs: e.ahead } : {}) };
};

// Two copies of one list of records: everything in the current copy, then what only the other one holds. A record with
// an id is the same record as the one with that id; records without an id count as a multiset (two equal sales stay two:
// each record keeps the higher of its two counts). Nothing either copy holds is dropped. where: for the console.
export function unionRecords(a, b, where = "") {
  if (!Array.isArray(a) && !Array.isArray(b)) return undefined;
  const out = [...(Array.isArray(a) ? a : [])];
  const ids = new Map(out.filter(hasId).map((r) => [r.id, r]));
  const count = new Map();
  for (const r of out) if (!hasId(r)) count.set(canon(r), (count.get(canon(r)) || 0) + 1);
  const seen = new Map();
  for (const r of Array.isArray(b) ? b : []) {
    if (hasId(r)) {
      if (!ids.has(r.id)) { out.push(r); ids.set(r.id, r); }
      else if (!same(ids.get(r.id), r)) console.warn(`[v2] ${where || "records"}: two copies hold record ${r.id} with different fields; the current copy's is kept`);
      continue;
    }
    const k = canon(r), n = (seen.get(k) || 0) + 1;
    seen.set(k, n);
    if (n > (count.get(k) || 0)) out.push(r);
  }
  return out;
}
// Is record r one of the records of history entry e (by id, or as the same record)?
const inEntry = (e, r) => ["purchases", "sales", "divs"].some((k) => (e[k] || []).some((x) => sameRec(x, r))) || (!!e.imported && same(e.imported, r));
// A history entry by its records (the day it was taken out aside: two tabs may take the same stock out on two days).
// #191 (two tabs): a record with an id stands for itself by its id, as in a portfolio's own lists (sameRec: the current copy's
// fields are kept), so an entry whose dollar record one copy moved from a temporary rate to its date's rate (records.
// withOfficialRates) is still the same entry, never two entries counting the record twice. Records without an id: as before.
const recKey = (r) => (hasId(r) ? { id: r.id } : r);
const entryKey = (e) => canon({ t: e.t, imported: e.imported || null, purchases: (e.purchases || []).map(recKey), sales: (e.sales || []).map(recKey),
  divs: (e.divs || []).map(recKey) });

// v19.7a: a holding's stored plan weight (planW) when it can be used (final review N2). It is on the scale of the plan's
// own values (won), and it must be a number that adds up: finite, 0 or more (0 is a real weight: a stock that takes no
// share of the total), and at most PLANW_TOTAL_X times the plan's total (verification N2: a save never writes one above
// twice its target's share of the amount, so twice the whole amount is never a real weight; a larger one would shrink
// every other band). The plan's total: settings.amountMan, else the planned values added up (plannedQty × planPx, a US
// holding at the plan's rate); when neither is known, a flat ceiling. The same test holds for planV (edit.withPlanV).
// Anything else counts as missing, never as a reason to set the portfolio aside: the band rule and 종목 바꾸기 fall back
// and say so in the console (rules.planWeights, edit.planBase). PLANW_MAX_X: how far the read plan weights may go above
// 1 (a stored total next to nothing against the plan's own values, rules.planWeights and edit.planBase).
export const PLANW_MAX_X = 1000;
export const PLANW_TOTAL_X = 2;
export function planWLimit(deck) {
  const m = deck && plainObj(deck.settings) ? deck.settings.amountMan : null;
  if (isNum(m) && m > 0) return PLANW_TOTAL_X * m * 10000;
  const fx = deck && isNum(deck.planFx) && deck.planFx > 0 ? deck.planFx : 1;
  let v = 0;
  for (const h of (deck && Array.isArray(deck.holdings) ? deck.holdings : [])) {
    if (plainObj(h) && Number.isInteger(h.plannedQty) && h.plannedQty > 0 && isNum(h.planPx) && h.planPx > 0) v += h.plannedQty * h.planPx * (h.cls === "us" ? fx : 1);
  }
  return v > 0 ? PLANW_TOTAL_X * v : 1e15;
}
export const planWOk = (x, limit) => typeof x === "number" && Number.isFinite(x) && x >= 0 && x <= limit;

// A holding with the target set of another copy's same holding o: its target, plannedQty, plan weight (planW, v19.7a: Jack
// 2026-11-13), plan value (planV, verification S-b) and band rule (o's; none when o has none). Every other field stays this copy's.
function withTargetSet(h, o) {
  const { target: _t, plannedQty: _q, planW: _w, planV: _v, ...rest } = h;
  const band = Array.isArray(o.rules) ? o.rules.find((r) => plainObj(r) && r.id === "band") : null;
  const rules = Array.isArray(h.rules) ? h.rules.filter((r) => !(plainObj(r) && r.id === "band")) : [];
  return { ...rest, ...(o.target != null ? { target: o.target } : {}), ...(o.plannedQty != null ? { plannedQty: o.plannedQty } : {}),
    ...(o.planW != null ? { planW: o.planW } : {}), ...(o.planV != null ? { planV: o.planV } : {}),
    ...(Array.isArray(h.rules) || band ? { rules: band ? [...rules, band] : rules } : {}) };
}
const targetSet = (d) => canon({ m: plainObj(d.settings) ? d.settings.maxPct ?? null : null,
  h: (d.holdings || []).filter(plainObj).map((h) => [h.t, h.target ?? null, h.plannedQty ?? null, (Array.isArray(h.rules) ? h.rules : []).find((r) => plainObj(r) && r.id === "band") || null,
    h.planW ?? null, h.planV ?? null]) });

// One portfolio both copies hold, both changed: the current copy leads (its name, settings, kind; its limits unless the
// other copy's were saved later, laterOf: 내 규칙 정하기 is an edit like a 메모) and every
// record either one holds is kept: holdings and imported rows by stock (the current one wins), purchases, sales,
// dividends and history entries by id or as a multiset, answers to 확인 필요 (the later answer for the same item).
// A stock one copy took out stays out: its removal mark (removed) keeps it out unless the holding was added again
// later (its ts after the mark's), and records it moved into a history entry the other copy lacks leave the portfolio's
// own lists (not counted twice).
function unionDeck(cur, other) {
  const where = `portfolio ${cur.id}`;
  // a holding both copies have: the current copy's, with the later of the two times it was added (a holding brought back
  // by 기록 불러오기 in one copy stays back however the copies meet)
  const later = (h) => {
    const o = other.holdings.find((x) => x.t === h.t);
    return o && okTs(o.ts) && !(okTs(h.ts) && h.ts >= o.ts) ? { ...h, ts: o.ts } : h;
  };
  const holdings = [...cur.holdings.map(later), ...other.holdings.filter((h) => !cur.holdings.some((x) => x.t === h.t))];
  let out = { ...other, ...cur, holdings, purchases: unionRecords(cur.purchases, other.purchases, where) || [] };
  out = withLimitsEdit(out, laterLimits(limitsEdit(cur), limitsEdit(other)));
  if (Array.isArray(cur.imported) || Array.isArray(other.imported)) {
    // rows with a code: one per stock, the current copy's wins; rows added by name only: as a multiset
    const ci = cur.imported || [], oi = other.imported || [];
    const named = unionRecords(ci.filter((r) => r.t == null), oi.filter((r) => r.t == null)) || [];
    out.imported = [...ci, ...oi.filter((r) => r.t != null && !ci.some((y) => y.t === r.t)), ...named.slice(ci.filter((r) => r.t == null).length)];
  }
  for (const k of ["sales", "divs", "history"]) { const u = unionRecords(cur[k], other[k], where); if (u) out[k] = u; }
  // v19.7a round-1 S1: the target set (each holding's target, plannedQty and band rule, and settings.maxPct) is one edit:
  // the copy whose set was saved later (targetsTs; a time more than a day ahead counts as none) gives it whole, for every
  // holding it has; a copy without a time is older than one with. Holdings added or taken out follow their own rules above
  // and below (removal marks, history). When only one copy changed targets, the sum is that edit's. When BOTH changed
  // targets and also added or took out different stocks, the later set covers only the holdings it has, so the targets can
  // add up to more or less than 100% (round-2 B-1, a known limit, RUNBOOK): no record is lost, the 합쳤어요 line shows,
  // 종목 바꾸기 opens at that 합계 with 합계를 100%로 맞추기, and the daily check reads each target over the held ones' sum
  // (rules.js ref = target / targetSum), so the sum alone flags nothing. Never renormalised here.
  const tc = believable(cur.targetsTs) ? cur.targetsTs : null, to = believable(other.targetsTs) ? other.targetsTs : null;
  if (to != null && !(tc != null && tc >= to)) {
    const oh = new Map((other.holdings || []).filter(plainObj).map((h) => [h.t, h]));
    out.holdings = out.holdings.map((h) => { const o = plainObj(h) ? oh.get(h.t) : null; return o ? withTargetSet(h, o) : h; });
    const om = plainObj(other.settings) ? other.settings.maxPct : undefined;
    if (om != null) out.settings = { ...(plainObj(out.settings) ? out.settings : {}), maxPct: om };
    out.targetsTs = to;
  }
  // v19.7a change log: every entry either copy holds (as a multiset), oldest first, the newest CHANGES_MAX kept
  if (Array.isArray(cur.changes) || Array.isArray(other.changes)) {
    const all = (unionRecords(cur.changes, other.changes, where) || []).map((c, i) => [c, i])
      .sort((a, b) => (plainObj(a[0]) && plainObj(b[0]) && a[0].at !== b[0].at ? (a[0].at < b[0].at ? -1 : 1) : a[1] - b[1])).map(([c]) => c);
    out.changes = all.slice(Math.max(0, all.length - CHANGES_MAX));
  }
  // v19.6a splits: one per stock and date, the current copy's wins (both came from the same data.json, so they agree)
  if (Array.isArray(cur.splits) || Array.isArray(other.splits)) {
    const cs = Array.isArray(cur.splits) ? cur.splits : [];
    out.splits = [...cs, ...(Array.isArray(other.splits) ? other.splits : []).filter((s) => !cs.some((y) => plainObj(y) && plainObj(s) && y.t === s.t && y.date === s.date))];
  }
  // the same stock taken out in both copies (on another day): one entry, the current copy's
  if (Array.isArray(out.history)) {
    const mine = new Set((cur.history || []).map(entryKey)), n = (cur.history || []).length;
    out.history = out.history.filter((e, i) => i < n || !mine.has(entryKey(e)));
  }
  const confirms = [...(cur.confirms || [])];
  for (const c of other.confirms || []) {
    const i = confirms.findIndex((x) => sameConfirm(x, c));
    if (i < 0) confirms.push(c); else confirms[i] = laterOf(confirms[i], c);
  }
  if (confirms.length) out.confirms = confirms;
  // taken out in one copy (records moved into history), still held in the other
  for (const [a, b] of [[cur, other], [other, cur]]) {
    for (const e of a.history || []) {
      if (a.holdings.some((h) => h.t === e.t) || !b.holdings.some((h) => h.t === e.t) || (b.history || []).some((x) => same(x, e))) continue;
      // the holding came back after the stock was taken out (기록 불러오기 or added again: its ts is later): it stays, and
      // the entry goes when the portfolio's own lists hold every record of it (else both stay: nothing is dropped)
      const back = b.holdings.find((h) => h.t === e.t);
      if (okTs(back.ts) && !(okTs(e.ts) && e.ts > back.ts)) {
        const lists = ["purchases", "sales", "divs", "imported"].flatMap((k) => out[k] || []);
        const all = ["purchases", "sales", "divs"].every((k) => (e[k] || []).every((r) => lists.some((x) => sameRec(x, r)))) && (!e.imported || lists.some((x) => same(x, e.imported)));
        if (all && Array.isArray(out.history)) out.history = out.history.filter((x) => !same(x, e));
        continue;
      }
      const keep = (r) => !(plainObj(r) && r.t === e.t && inEntry(e, r));
      for (const k of ["purchases", "sales", "divs", "imported"]) if (Array.isArray(out[k])) out[k] = out[k].filter(keep);
      const left = ["purchases", "sales", "divs", "imported"].some((k) => (out[k] || []).some((r) => plainObj(r) && r.t === e.t));
      if (!left) {
        out.holdings = out.holdings.filter((h) => h.t !== e.t);
        if (Array.isArray(out.confirms)) out.confirms = out.confirms.filter((c) => c.t !== e.t);
      }
    }
  }
  // removal marks: the later mark per stock; a stock with a mark is out unless its holding was added again after it
  const marks = new Map();
  for (const r of [...(cur.removed || []), ...(other.removed || [])]) if (plainObj(r) && (!marks.has(r.t) || r.ts > marks.get(r.t).ts)) marks.set(r.t, r);
  if (marks.size) out.removed = [...marks.values()];
  for (const r of marks.values()) {
    const h = out.holdings.find((x) => x.t === r.t);
    if (h && okTs(h.ts) && h.ts > r.ts) {
      // held again after it was taken out: the answers from before the removal (빼기 cleared them) stay cleared
      if (Array.isArray(out.confirms)) out.confirms = out.confirms.filter((c) => !(plainObj(c) && c.t === r.t && !(editOrder(c, r) > 0)));
      continue;
    }
    if (!h) continue;
    out.holdings = out.holdings.filter((x) => x.t !== r.t);
    // its own records go with it, as 빼기 does (withoutHolding): with a sale or dividend still in the lists (one copy had
    // them, the other took the stock out), they move into a history entry, so nothing is dropped and the merge stays valid
    const of = (k) => (Array.isArray(out[k]) ? out[k].filter((x) => plainObj(x) && x.t === r.t) : []);
    const sales = of("sales"), divs = of("divs");
    if (sales.length || divs.length) {
      const imp = of("imported")[0];
      out.history = [...(Array.isArray(out.history) ? out.history : []), { t: r.t, nk: h.nk, out: r.at, ts: r.ts, ...(h.cls ? { cls: h.cls } : {}),
        ...(imp ? { imported: imp } : {}), purchases: of("purchases"), sales, divs }];
    }
    for (const k of ["purchases", "imported", "confirms", "sales", "divs"]) if (Array.isArray(out[k])) out[k] = out[k].filter((x) => !(plainObj(x) && x.t === r.t));
  }
  return out;
}

// One stock's 메모 in one copy: the note, its deletion mark ({ gone: true, at, ts }), or null. A note saved over a deletion
// mark in the same copy (by the earlier app, which keeps the mark it does not know) is the later edit, unless both
// carry a time and the mark's is later.
function noteState(d, t) {
  const n = perStock(d, "notes"), g = d && plainObj(d.gone) && plainObj(d.gone.notes) ? d.gone.notes : null;
  const note = n && plainObj(n[t]) ? n[t] : null, del = g && plainObj(g[t]) ? { ...g[t], gone: true } : null;
  if (note && del) return okTs(note.ts) && note.ts < del.ts ? del : note;
  return note || del;
}
const noteStocks = (d) => [...Object.keys(perStock(d, "notes") || {}), ...Object.keys((d && plainObj(d.gone) && perStock(d.gone, "notes")) || {})];

// The current store with another copy's records added in (cur leads; nothing either holds is lost; for a note, an
// assumption or an answer the later edit wins, laterOf). null when the result would not be valid (then nothing is
// changed, the other copy stays where it is and the screens say so).
export function mergeTabs(other, cur, today) {
  const decks = [...cur.decks];
  for (const d of other.decks) {
    const i = decks.findIndex((x) => x.id === d.id);
    if (i < 0) decks.push(d);
    else if (!same(decks[i], d)) decks[i] = unionDeck(decks[i], d);
  }
  const out = { ...other, ...cur, decks };
  const notes = {}, gn = {};
  for (const t of new Set([...noteStocks(cur), ...noteStocks(other)])) {
    const c = noteState(cur, t), o = noteState(other, t);
    let w = laterOf(c, o);
    // a deletion mark wins over the very note it deleted (the same text) unless that note was saved again after it
    const del = c && c.gone ? c : o && o.gone ? o : null, note = c && !c.gone ? c : o && !o.gone ? o : null;
    if (del && note && del.h && del.h === textHash(note.text) && !(okTs(note.ts) && note.ts > del.ts)) w = del;
    if (!w) continue;
    if (w.gone) gn[t] = { at: w.at, ts: w.ts, ...(w.h ? { h: w.h } : {}) }; else notes[t] = w;
  }
  delete out.notes;
  if (Object.keys(notes).length) out.notes = notes;
  const gone = { ...((plainObj(other.gone) && other.gone) || {}), ...((plainObj(cur.gone) && cur.gone) || {}) };
  delete gone.notes;
  if (Object.keys(gn).length) gone.notes = gn;
  delete out.gone;
  if (Object.keys(gone).length) out.gone = gone;
  const assume = {}, ca = perStock(cur, "assume") || {}, oa = perStock(other, "assume") || {};
  for (const t of new Set([...Object.keys(ca), ...Object.keys(oa)])) assume[t] = laterOf(ca[t], oa[t]);
  delete out.assume;
  if (Object.keys(assume).length) out.assume = assume;
  // v19.6c 관심 종목: per stock, the later edit (an entry or a deletion mark), at most WATCH_MAX (unionWatch)
  delete out.watch;
  if (plainObj(cur.watch) || plainObj(other.watch) || Object.keys(watchGone(cur)).length || Object.keys(watchGone(other)).length) {
    const u = unionWatch(cur, other);
    if (Object.keys(u.watch).length) out.watch = u.watch;
    const g = { ...(plainObj(out.gone) ? out.gone : {}) };
    delete g.watch;
    if (Object.keys(u.marks).length) g.watch = u.marks;
    delete out.gone;
    if (Object.keys(g).length) out.gone = g;
  }
  // v19.6b 확인했어요: the union of the two lists (nothing either copy marked comes back as a card)
  delete out.seen;
  const seen = unionSeen(cur, other);
  if (seen.length) out.seen = seen;
  if (guideSeenIn(cur) || guideSeenIn(other)) out.guideSeen = guideSeenIn(cur) ? cur.guideSeen : other.guideSeen;
  delete out.preview;
  delete out.setAside;
  delete out.wts;
  if (cur.wts) out.wts = cur.wts;
  out.v = versionFor(out);
  return validStore(out, today) ? out : null;
}
// The store as a merge writes it (the same normal form, to compare with a merge result).
const normal = (d, today) => mergeTabs({ v: BASE_VERSION, decks: [] }, d, today);

// Does the merged result leave out anything a copy held (a later edit, a removal or a deletion won over it)? Then the
// screens say 합쳤어요, even when the current records did not change.
function droppedFrom(copy, res) {
  for (const d of copy.decks || []) {
    const r = (res.decks || []).find((x) => x.id === d.id);
    if (!r) return true;
    const hist = r.history || [];
    const kept = (x) => ["purchases", "imported", "sales", "divs"].some((k) => (r[k] || []).some((y) => sameRec(y, x))) || hist.some((e) => inEntry(e, x));
    if (d.holdings.some((h) => !r.holdings.some((x) => x.t === h.t) && !hist.some((e) => e.t === h.t))) return true;
    for (const k of ["purchases", "imported", "sales", "divs"]) if ((d[k] || []).some((x) => !kept(x))) return true;
    if ((d.history || []).some((e) => !hist.some((y) => entryKey(y) === entryKey(e)))) return true;
    if ((d.confirms || []).some((c) => !(r.confirms || []).some((y) => sameConfirm(y, c) && y.answer === c.answer))) return true;
    if (limitsEdit(d) && limitValues(d.limits) !== limitValues(r.limits)) return true;
    // its target set lost to another (round-1 S1): said like any edit that lost
    if (believable(d.targetsTs) && d.holdings.some((h) => { const x = r.holdings.find((y) => y.t === h.t); return x && x.target !== h.target; })) return true;
  }
  // v19.6c 관심 종목: a stock the copy watched is gone or holds other conditions (a later edit or a removal won, or the 30 cap),
  // or one it had taken out is back (hitAt and the times are not the user's words: not compared)
  const cond = (e) => canon((Array.isArray(e.conds) ? e.conds : []).map((c) => (plainObj(c) ? [c.k, c.v] : c)));
  for (const [t, e] of Object.entries(watchOf(copy))) {
    const r = watchOf(res)[t];
    if (!plainObj(r) || cond(r) !== cond(e)) return true;
  }
  for (const t of Object.keys(watchGone(copy))) if (plainObj(watchOf(res)[t]) && !plainObj(watchOf(copy)[t])) return true;
  // a note the copy had deleted is back in the result (its deletion lost to a later edit)
  for (const t of Object.keys((plainObj(copy.gone) && perStock(copy.gone, "notes")) || {})) {
    const a = noteState(copy, t), b = noteState(res, t);
    if (a && a.gone && b && !b.gone) return true;
  }
  const bare = (v) => { const { at: _a, ts: _t, ...rest } = v; return canon(rest); };
  for (const key of ["notes", "assume"]) {
    const a = perStock(copy, key) || {}, b = perStock(res, key) || {};
    if (Object.keys(a).some((t) => !plainObj(b[t]) || bare(a[t]) !== bare(b[t]))) return true;
  }
  return false;
}

// Is everything in copy d held by store y, or replaced there by a surely later edit (by date or time, never only by the
// tie rule)? Then d can go: merging it into y would change nothing, and nothing in it is the only copy of an edit.
function covers(y, d, today) {
  const m = mergeTabs(d, y, today), n = normal(y, today);
  if (!m || !n || canon(m) !== canon(n)) return false;
  for (const t of new Set(noteStocks(d))) {
    const a = noteState(d, t), b = noteState(n, t);
    if (a && b && ((a.gone ? b.gone : !b.gone && b.text === a.text) || surelyLater(b, a))) continue;
    return false;
  }
  // v19.6c 관심 종목: each stock d watches is in n with the same conditions, or replaced there by a surely later edit; each
  // stock d took out is out in n, or added again surely later
  const cond = (e) => canon((Array.isArray(e.conds) ? e.conds : []).map((c) => (plainObj(c) ? [c.k, c.v] : c)));
  for (const [t, a] of Object.entries(watchOf(d))) {
    const b = watchState(n, t);
    if (b && ((!b.gone && cond(b) === cond(a)) || surelyLater(b, a))) continue;
    return false;
  }
  for (const [t, g] of Object.entries(watchGone(d))) {
    const b = watchState(n, t);
    if (b && (b.gone || surelyLater(b, g))) continue;
    return false;
  }
  const na = perStock(n, "assume") || {};
  for (const [t, a] of Object.entries(perStock(d, "assume") || {})) {
    const b = na[t];
    if (b && (same({ ...b, at: 0, ts: 0 }, { ...a, at: 0, ts: 0 }) || surelyLater(b, a))) continue;
    return false;
  }
  for (const x of d.decks) {
    const r = n.decks.find((z) => z.id === x.id);
    for (const c of x.confirms || []) {
      const b = r && (r.confirms || []).find((z) => sameConfirm(z, c));
      if (b && (b.answer === c.answer || surelyLater(b, c))) continue;
      if (!b && r && !r.holdings.some((h) => h.t === c.t)) continue;   // its stock was taken out (a removal mark or history)
      return false;
    }
    // its limits: the same values, or replaced by limits saved surely later
    if (limitsEdit(x) && r && limitValues(x.limits) !== limitValues(r.limits) && !surelyLater(limitsEdit(r), limitsEdit(x))) return false;
  }
  return true;
}

// After a good read, the copies other tabs left are merged in, newest first (see the top of this section). raw: the
// stored text that was read. -> { data, notice, unmerged }: data = the merged records (null when they equal what was
// read); notice = say 합쳤어요 (the records changed, or a copy held something the result left out); unmerged = a copy
// could not be merged (it stays; the screens say records were kept aside). The merged store is written first; a copy
// leaves only once its ".restored." copy is written. When storage is too full to write the merged store, it is still
// used in this session and every copy stays for the next start.
function restoreMoved(key, cur, raw, today) {
  let merged = cur, unmerged = false;
  const used = [];
  const cands = [...backupKeys(key, ".unreadable.").map((k) => [k, true]), ...backupKeys(key, ".other.").map((k) => [k, false])]
    .sort((a, b) => stamp(b[0]) - stamp(a[0]));
  let mine = null;
  try { mine = localStorage.getItem(key + MINE); } catch (e) { mine = null; }
  // the records were saved from this app's last write (the earlier app keeps its fingerprint, e.g. after a revert): its
  // changes stand, and .mine follows them; otherwise they come from an older copy and .mine is merged back
  const descends = mine != null && mine !== raw && sameLineage(raw, mine);
  if (descends) { try { localStorage.setItem(key + MINE, raw); } catch (e) { /* the next write sets it */ } }
  else if (mine != null && mine !== raw) cands.unshift([key + MINE, false]);
  const copies = cands.map(([k, moved]) => [k, readCopy(k, today), moved]).filter(([, d, moved]) => d && !(moved && (d.v !== STORE_VERSION || !hasV2Parts(d))));
  // a stock one copy brought back (its holding's time) stays back whichever copy with an older removal mark is merged
  // first: every copy, and the records as read, take each holding's latest time before the merges (so the answers and
  // records of a copy that held it are not filtered out on the way)
  const best = new Map();
  for (const d of [cur, ...copies.map(([, x]) => x)]) for (const x of d.decks) for (const h of x.holdings || []) {
    if (plainObj(h) && okTs(h.ts) && !(best.get(x.id + "\u0000" + h.t) >= h.ts)) best.set(x.id + "\u0000" + h.t, h.ts);
  }
  const lift = (d) => (best.size ? { ...d, decks: d.decks.map((x) => ({ ...x, holdings: (x.holdings || []).map((h) => {
    const t = plainObj(h) ? best.get(x.id + "\u0000" + h.t) : undefined;
    return t && !(okTs(h.ts) && h.ts >= t) ? { ...h, ts: t } : h;
  }) })) } : d);
  merged = lift(cur);
  for (const [k, d0] of copies) {
    const d = lift(d0);
    const m = mergeTabs(d, merged, today);
    if (!m) { unmerged = true; console.warn(`[v2] the copy in ${k} could not be merged with the current records (the result would not read back); it is kept as it is`); continue; }
    merged = m;
    used.push([k, d0]);
  }
  if (!used.length) return { data: null, notice: false, unmerged };
  const base = normal(cur, today) || cur;
  const changed = canon(merged) !== canon(base);
  // only a portfolio's limitsTs changed (the same limits values, a later time): written back, but nothing to say (review 5).
  // The same for the first-visit flag guideSeen (Jack, 2026-11-08): this device's flag, not a record — a copy that differs
  // only in it is merged quietly (never "다른 창에서 저장한 내용과 기록을 합쳤어요…").
  const noTs = (d) => {
    const { guideSeen: _g, ...top } = d;
    // v19.6c: the 관심 종목 hitAt marks are this device's state, not the user's words: a copy that differs only in them is quiet too
    if (plainObj(top.watch)) top.watch = watchNoHits(top.watch);
    // v19.6b: so are the 확인했어요 marks (a card hidden again is nothing to check in the records)
    delete top.seen;
    return canon({ ...top, decks: (d.decks || []).map((x) => { if (!plainObj(x)) return x; const { limitsTs: _t, ...r } = x; return r; }) });
  };
  const notice = (changed && noTs(merged) !== noTs(base)) || used.some(([, d]) => droppedFrom(d, merged));
  if (changed) merged = stamped(merged);
  const text = JSON.stringify(merged);
  if (changed) {
    try {
      localStorage.setItem(key, text);
    } catch (e) {
      console.warn("[v2] could not write the merged records (storage full?): they are shown for now and every copy stays for the next start: " + ((e && e.message) || e));
      return { data: merged, notice: true, unmerged };
    }
    lastText.set(key, text);
  }
  if (changed || used.some(([k]) => k === key + MINE)) {
    try { localStorage.setItem(key + MINE, changed ? text : raw); } catch (e) { console.warn("[v2] could not update " + key + MINE + " (storage full?)"); }
  }
  for (const [k] of used) {
    if (k === key + MINE) continue;
    try {
      localStorage.setItem(backupKey(key, ".restored.", stamp(k), [".restored."]), localStorage.getItem(k));
      localStorage.removeItem(k);
    } catch (e) {
      console.warn(`[v2] merged ${k} but could not keep its copy under .restored. (storage full?): the copy stays where it is`);
    }
  }
  pruneBackups(key);
  if (notice) console.warn(`[v2] records another tab had left were merged back (${used.map(([k]) => k).join(", ")})${changed ? "" : "; nothing new, but a later edit or a removal won over something in them"}`);
  return { data: changed ? merged : null, notice, unmerged };
}
// Another tab just wrote the records (the browser's storage event, newText): when what it wrote does not hold everything
// this tab last read or wrote, this tab's text is kept as a copy, merged back on the next start. The earlier app writes
// over the records without looking; this keeps an open tab's records even before ".mine" exists. -> true when kept.
export function keepOwnText(key, newText, today) {
  try {
    const own = lastText.get(key);
    if (typeof own !== "string" || own === newText) return false;
    if (typeof newText === "string" && sameLineage(newText, own)) return false;     // saved from this tab's text: its changes stand
    const d = readText(own, today);
    if (!d) return false;
    const n = typeof newText === "string" ? readText(newText, today) : null;
    if (n && covers(n, d, today)) return false;
    const copies = [...backupKeys(key, ".other."), ...backupKeys(key, ".unreadable.")];
    if (copies.some((k) => localStorage.getItem(k) === own)) return false;          // already kept
    const k = backupKey(key, ".other.");
    localStorage.setItem(k, own);
    // this tab's earlier copy, all of which the new one holds, goes (one copy per open tab, not one per write)
    const prev = keptBy.get(key);
    if (prev && prev !== k) { const old = readCopy(prev, today); if (old && covers(d, old, today)) localStorage.removeItem(prev); }
    keptBy.set(key, k);
    console.warn("[v2] another tab wrote over records this tab had saved: kept, and merged back on the next start");
    return true;
  } catch (e) {
    console.warn("[v2] could not keep this tab's records after another tab wrote: " + ((e && e.message) || e));
    return false;
  }
}
// The page is being hidden or closed (app.jsx: pagehide, visibilitychange): when ".mine" does not exist yet (this tab
// wrote the first records into an empty storage), it starts now with what this tab last wrote or read, so a tab of the
// earlier app writing over the records later cannot drop them. -> true when written.
export function keepMine(key) {
  try {
    const own = lastText.get(key);
    if (typeof own !== "string" || localStorage.getItem(key + MINE) != null) return false;
    localStorage.setItem(key + MINE, own);
    return true;
  } catch (e) { return false; }
}
const keptBy = new Map();                                // the copy keepOwnText made last, per key (this tab's)
const readText = (t, today) => { try { const d = JSON.parse(t); return d && validStore(d, today) ? d : null; } catch (e) { return null; } };
// Only ".restored." copies are pruned to the newest BACKUPS_KEEP (never the newest); an exact duplicate of a newer copy
// of the same kind goes too. A copy that was never merged back is never pruned here (a write removes one only when it
// holds everything in it, dropCovered).
export function pruneBackups(key) {
  try {
    for (const kind of BACKUP_KINDS) {
      const ks = backupKeys(key, kind);
      const texts = ks.map((k) => localStorage.getItem(k));
      ks.forEach((k, i) => { if (i < ks.length - 1 && texts.slice(i + 1).includes(texts[i])) localStorage.removeItem(k); });
    }
    const rs = backupKeys(key, ".restored.");
    for (const k of rs.slice(0, Math.max(0, rs.length - BACKUPS_KEEP))) localStorage.removeItem(k);
  } catch (e) { /* nothing removed */ }
}
// After a write: the readable copies (".other.", ".unreadable.") all of whose records the written store or a copy this
// write just made holds (covers) are removed, so two tabs taking turns keep one copy each, not one per save.
function dropCovered(key, next, made, today) {
  const keepers = [next, ...made.map((k) => readCopy(k, today)).filter(Boolean)];
  for (const k of [...backupKeys(key, ".other."), ...backupKeys(key, ".unreadable.")]) {
    if (made.includes(k)) continue;
    const d = readCopy(k, today);
    try { if (d && keepers.some((y) => covers(y, d, today))) localStorage.removeItem(k); } catch (e) { /* it stays */ }
  }
}
// What 기록 내보내기 adds besides the records: every copy not merged back (".unreadable.", ".other.", and ".mine" while it
// differs from the records), as stored, so a portfolio that was set aside travels in the file too. [{ key, text }].
export function setAsideCopies(key) {
  const out = [];
  try {
    for (const k of [...backupKeys(key, ".unreadable."), ...backupKeys(key, ".other.")].sort((a, b) => stamp(a) - stamp(b))) {
      const text = localStorage.getItem(k);
      if (typeof text === "string") out.push({ key: k.slice(key.length + 1), text });
    }
    const mine = localStorage.getItem(key + MINE);
    if (typeof mine === "string" && mine !== localStorage.getItem(key)) out.push({ key: MINE.slice(1), text: mine });
  } catch (e) { return []; }
  return out;
}

// ---------------- 내 규칙 limits beside the records (v19.3d2 review) ----------------
// key + ".limits" = { v: 1, decks: { <portfolio id>: { limits?: { stock?, ind? }, ts } } }: each 가진 종목 portfolio's latest
// limits (내 규칙 정하기) and when they were saved (limitsTs). v19.3d (#83: a tab still open from before, or after a revert)
// never reads or writes this key, but it can drop limits: its merge keeps the current copy's limits and its check of what
// a copy holds ignores them, so a copy holding later limits can be merged away. Every write of this app records here the
// limits it writes when they were saved later than what is here; on start, limits saved later than the records hold come
// back from here (the screens say 합쳤어요 when that changes what they show). A bad entry is set aside (the whole text, as an
// ".unreadable." copy, which 기록 내보내기 carries) and the good entries are used. An entry saved more than a day after now
// (a clock set wrong) counts as bad: it would win over every later 저장. A portfolio this tab's write takes out of the
// records leaves the side key too (else re-importing it from an older file would bring back its old limits).
// Known cost (review 2, S2): 기록 불러오기 in a v19.3d tab writes the file's limits with the file's time (or none), so when
// the side key holds limits saved later, the next start of this app shows those instead, and says 합쳤어요.
// Known limit (review 3): a portfolio deleted in a v19.3d tab leaves its entry here (that app never touches this key), so
// re-importing that portfolio later from an older file without limits brings its old limits back.
// A 저장 is stamped later than the limits this tab and the side key already hold for that portfolio (limitsSaveTime), so
// the user's last 저장 wins even after the clock was set back (it was up to a day fast, then corrected).
// Known limits (review 5, see limitsEdit): A — a 저장 made with the clock more than a day fast loses to an older
// believable copy once the clock is right again, and so does 기록 불러오기 of a file without limits; B — a time 24–48 h
// ahead becomes believable again later and can then silently bring back an older 저장. A clock set days back also sets
// this key's entries aside (they look more than a day ahead): the records keep their limits, and the next 저장 writes
// the entry again. These, and the review-3 limit above, are in docs/RUNBOOK.md (Known limits: 기록 and the phone clock).
export const LIMITS_SUFFIX = ".limits";
const okLimitsPart = (l) => plainObj(l) && Object.keys(l).every((k) => ["stock", "ind"].includes(k) && Number.isInteger(l[k]) && l[k] >= 1 && l[k] <= 100);
const SIDE_AHEAD = LIMITS_AHEAD;                         // a time more than a day ahead of now is not believed
const okSideEntry = (e, now = Date.now()) => plainObj(e) && okTs(e.ts) && e.ts <= now + SIDE_AHEAD && Object.keys(e).every((k) => k === "limits" || k === "ts")
  && (e.limits == null || okLimitsPart(e.limits));
const sideText = (map) => JSON.stringify({ v: 1, decks: Object.fromEntries([...map].map(([id, e]) => [id, { ...(e.limits ? { limits: e.limits } : {}), ts: e.ts }])) });
// -> Map(id -> { limits | null, ts }) of the good entries (a bad text is set aside first and the good entries rewritten)
export function readSideLimits(key) {
  const map = new Map();
  let raw = null;
  try { raw = localStorage.getItem(key + LIMITS_SUFFIX); } catch (e) { return map; }
  if (raw == null) return map;
  let d = null;
  try { d = JSON.parse(raw); } catch (e) { d = null; }
  let bad = 0, ahead = 0;
  const now = Date.now();
  if (plainObj(d) && d.v === 1 && plainObj(d.decks)) {
    for (const [id, e] of Object.entries(d.decks)) {
      if (id && id.length <= 200 && okSideEntry(e, now)) map.set(id, { limits: e.limits || null, ts: e.ts });
      else { bad++; if (plainObj(e) && okTs(e.ts) && e.ts > now + SIDE_AHEAD) ahead++; }
    }
  } else bad = 1;
  if (bad) {
    console.warn(`[v2] ${key + LIMITS_SUFFIX}: ${bad} entr${bad === 1 ? "y" : "ies"} not readable${ahead ? ` (${ahead} saved more than a day ahead of now)` : ""}; the text is kept aside and the other ${map.size} used`);
    try {
      localStorage.setItem(backupKey(key, ".unreadable."), raw);
      if (map.size) localStorage.setItem(key + LIMITS_SUFFIX, sideText(map)); else localStorage.removeItem(key + LIMITS_SUFFIX);
    } catch (e) { console.warn("[v2] could not set aside " + key + LIMITS_SUFFIX + " (storage full?): it stays as it is"); }
  }
  return map;
}
// The time to stamp a 내 규칙 저장 of portfolio deck with: now, or just after the limits already saved for it (in the records
// this tab holds, or beside them) when those carry a later time (a clock that was fast and has been corrected). A time
// more than a day ahead of now is not believed (as beside the records): it is not carried on.
export function limitsSaveTime(key, deck, now = Date.now()) {
  let t = now;
  const near = (x) => believable(x, now);
  if (plainObj(deck) && near(deck.limitsTs)) t = Math.max(t, deck.limitsTs + 1);
  try {
    const e = plainObj(deck) ? readSideLimits(key).get(deck.id) : null;
    if (e && near(e.ts)) t = Math.max(t, e.ts + 1);
  } catch (err) { /* the records' time is enough */ }
  return t;
}
// Ids of the portfolios in text (what this tab last read or wrote) that next no longer holds — readable ones only: a
// portfolio set aside because it could not be read, or records this app cannot read at all (a later version's, after a
// revert), were not taken out by the user (they are kept aside, limits too).
function goneIds(text, next, today) {
  let d = null;
  try { d = typeof text === "string" ? JSON.parse(text) : null; } catch (e) { d = null; }
  const r = d != null ? checkStore(d, today) : null;
  if (!r || !r.readable) return [];
  const now = new Set((next.decks || []).filter(plainObj).map((x) => x.id));
  return r.data.decks.filter((x) => plainObj(x) && typeof x.id === "string" && !now.has(x.id)).map((x) => x.id);
}
// After a write: the limits it holds, where they were saved later than what the side key holds (a tie keeps the side's);
// gone: ids of portfolios this write took out (they were in what this tab last read or wrote), whose entries go.
function keepSideLimits(key, data, gone = []) {
  try {
    // records whose limits carry a time more than a day ahead are not copied here (they would be set aside on every read)
    const ahead = Date.now() + SIDE_AHEAD;
    const decks = (data.decks || []).filter((x) => plainObj(x) && x.kind === "imported" && okTs(x.limitsTs) && x.limitsTs <= ahead);
    if (!decks.length && !gone.length) return;
    const map = readSideLimits(key);
    let changed = false;
    for (const id of gone) if (map.delete(id)) changed = true;
    for (const x of decks) {
      const e = map.get(x.id);
      if (e && e.ts >= x.limitsTs) continue;
      map.set(x.id, { limits: plainObj(x.limits) ? x.limits : null, ts: x.limitsTs });
      changed = true;
    }
    if (changed) localStorage.setItem(key + LIMITS_SUFFIX, sideText(map));
  } catch (e) {
    console.warn("[v2] could not keep the limits beside the records (" + ((e && e.message) || e) + "); they are in the records");
  }
}
// On start: limits saved later than the records hold, back from the side key. -> { data, visible } (data null: nothing
// to bring back; visible: what the screens show changes) — only 가진 종목 portfolios (only they have limits). The records
// stay only when saved later, or at the same time with the same values: a v19.3d merge ({ ...other, ...cur }) can pair an
// older copy's limits with a later 저장's time, so on a tie with other values the side key's (written at that 저장) win.
function sideLimitsInto(key, data) {
  const map = readSideLimits(key);
  if (!map.size || !plainObj(data) || !Array.isArray(data.decks)) return { data: null, visible: false };
  let any = false, visible = false;
  const decks = data.decks.map((x) => {
    const e = plainObj(x) && x.kind === "imported" ? map.get(x.id) : null;
    if (!e) return x;
    const cur = limitsEdit(x);
    if (cur && okTs(cur.ts) && (cur.ts > e.ts || (cur.ts === e.ts && limitValues(cur.limits) === limitValues(e.limits)))) return x;
    any = true;
    if (limitValues(x.limits) !== limitValues(e.limits)) visible = true;
    return withLimitsEdit(x, e);
  });
  return any ? { data: { ...data, decks }, visible } : { data: null, visible: false };
}

// ---------------- 관심 종목 beside the records (v19.6c review B1) ----------------
// key + ".watch" = { v: 1, watch?: { [code]: entry }, gone?: { [code]: { at, ts } } }: the latest state of every 관심 종목 stock
// this app wrote (its entry, or its deletion mark), with its time. Why: the app on main before v19.6c (a tab still open, or a
// revert) keeps a top-level part it does not know exactly as it read it, so a write of its from an older copy puts back the
// list as that copy had it, and its own start merges another tab's copy (".mine", ".other.") its own way, keeping only its
// copy's list; neither leaves a copy behind or says 합쳤어요. That app never reads or writes this key (the 내 규칙 limits
// key, LIMITS_SUFFIX, is the same idea). Every write of this app adds what it writes here, per stock, unless what is here is
// surely later (a stale tab never replaces a later edit); on start, a stock whose state here is later than the records'
// (an addition, a condition edit, a removal) comes back into the records by the tab-merge rule (mergeTabs: per stock the
// later edit, at most WATCH_MAX with the records' stocks first), the screens say 합쳤어요 when what they show changes, and
// the key then follows the records (a stock the cap left out does not come back later). A bad text is set aside
// (".unreadable.", which 기록 내보내기 carries) and not used.
export const WATCH_SUFFIX = ".watch";
const SIDE_WATCH_MAX = 500;
function readSideWatch(key, today) {
  let raw = null;
  try { raw = localStorage.getItem(key + WATCH_SUFFIX); } catch (e) { return null; }
  if (raw == null) return null;
  let d = null;
  try { d = JSON.parse(raw); } catch (e) { d = null; }
  const ok = plainObj(d) && d.v === 1 && (d.watch == null || !watchProblem(d.watch, today, SIDE_WATCH_MAX)) && (d.gone == null || okWatchMarks(d.gone));
  if (!ok) {
    console.warn(`[v2] ${key + WATCH_SUFFIX}: not readable; the text is kept aside and not used`);
    try { localStorage.setItem(backupKey(key, ".unreadable."), raw); localStorage.removeItem(key + WATCH_SUFFIX); } catch (e) {
      console.warn(`[v2] could not set aside ${key + WATCH_SUFFIX} (${(e && e.message) || e}): it stays where it is, not used`);
    }
    return null;
  }
  return { watch: plainObj(d.watch) ? d.watch : {}, gone: plainObj(d.gone) ? d.gone : {} };
}
// the key's states as a store (for mergeTabs and storedStores)
const sideAsStore = (sw) => ({ v: BASE_VERSION, decks: [], ...(Object.keys(sw.watch).length ? { watch: sw.watch } : {}),
  ...(Object.keys(sw.gone).length ? { gone: { watch: sw.gone } } : {}) });
const watchSideText = (watch, gone) => JSON.stringify({ v: 1, ...(Object.keys(watch).length ? { watch } : {}), ...(Object.keys(gone).length ? { gone } : {}) });
// After a write: the states it holds, per stock, unless the key's own is surely later.
function keepSideWatch(key, data, today) {
  try {
    const w = watchOf(data), g = watchGone(data);
    const side = readSideWatch(key, today);
    if (!side && !Object.keys(w).length && !Object.keys(g).length) return;
    const sw = side || { watch: {}, gone: {} };
    const here = sideAsStore(sw);
    let changed = false;
    for (const t of new Set([...Object.keys(w), ...Object.keys(g)])) {
      const mine = watchState(data, t), have = watchState(here, t);
      if (!mine) continue;
      // the later edit (a tie goes to what this tab writes), with the later hitAt marks of the two (laterHits)
      const win = have && surelyLater(have, mine) ? have : mine, lose = win === mine ? have : mine;
      const next = !win.gone && lose && !lose.gone ? laterHits(win, lose) : win;
      if (have && same(have, next)) continue;
      if (next.gone) { sw.gone[t] = { at: next.at, ts: next.ts }; delete sw.watch[t]; } else { sw.watch[t] = next; delete sw.gone[t]; }
      changed = true;
    }
    if (changed) localStorage.setItem(key + WATCH_SUFFIX, watchSideText(sw.watch, sw.gone));
  } catch (e) {
    console.warn("[v2] could not keep the watch list beside the records (" + ((e && e.message) || e) + "); it is in the records");
  }
}
// On start: the records with every 관심 종목 state the key holds later (see above). -> { data (null: nothing changes), visible }.
const watchShown = (d) => canon(watchOrder(watchOf(d)).map((t) => [t, (Array.isArray(watchOf(d)[t].conds) ? watchOf(d)[t].conds : []).map((c) => (plainObj(c) ? [c.k, c.v] : c))]));
function sideWatchInto(key, data, today) {
  const sw = readSideWatch(key, today);
  if (!sw || !plainObj(data) || !Array.isArray(data.decks)) return { data: null, visible: false };
  const m = mergeTabs(sideAsStore(sw), data, today);
  if (!m) {
    console.warn("[v2] the watch list kept beside the records could not be merged (the result would not read back); the records as read are used, and the key is kept as it is");
    return { data: null, visible: false, failed: true };
  }
  const capped = (res) => Object.keys(sw.watch).some((t) => !plainObj(watchOf(res)[t]) && !watchGone(res)[t]
    && (() => { const rec = watchState(data, t); return !rec || surelyLater(watchState(sideAsStore(sw), t), rec); })());
  const same_ = canon(watchOf(m)) === canon(watchOf(data)) && canon(watchGone(m)) === canon(watchGone(data));
  const next = same_ ? data : withWatchParts(data, watchOf(m), watchGone(m));
  // what shows changed, or a later addition the 30 cap left out (the list may not change, but something the user saved is not in it)
  const visible = capped(next) || watchShown(next) !== watchShown(data);
  return { data: same_ ? null : next, visible };
}
// After the start: the key holds exactly the records' states (so a stock the 30 cap left out, or one taken out of the key's
// view, does not come back on a later start).
function sideWatchFollow(key, data, today) {
  try {
    const w = watchOf(data), g = watchGone(data);
    const cur = localStorage.getItem(key + WATCH_SUFFIX);
    if (!Object.keys(w).length && !Object.keys(g).length) { if (cur != null) localStorage.removeItem(key + WATCH_SUFFIX); return; }
    const text = watchSideText(w, g);
    if (cur !== text) localStorage.setItem(key + WATCH_SUFFIX, text);
  } catch (e) {
    console.warn("[v2] could not set " + key + WATCH_SUFFIX + " to the records' watch-list states (" + ((e && e.message) || e) + "); it keeps its own, and the next save adds to it");
  }
}

// { data, writable, locked, problems, restored, unmerged }: locked = something stored could not be read (all of it, or
// some portfolios: problems names them). It stays untouched; the first write moves it to a backup key first (see
// writeStore), so 기록 불러오기 and 샀어요 still work. restored = records another tab left were merged back and changed the
// records, or held something the merge left out (say so once). unmerged = a copy another tab left could not be merged
// (kept aside: the screens say so).
export function readStore(key = STORE_KEY, today) {
  let writable = false;
  try {
    const k = key + ".probe";
    localStorage.setItem(k, "1");
    localStorage.removeItem(k);
    writable = true;
  } catch (e) { writable = false; }
  let raw = null;
  try { raw = localStorage.getItem(key); } catch (e) { return { data: emptyStore(), writable: false, locked: false, problems: [], restored: false }; }
  let out = { data: emptyStore(), writable, locked: false, problems: [], restored: false };
  lastText.set(key, raw);
  if (raw != null) {
    let r = { readable: false, why: "not JSON" };
    try { r = checkStore(JSON.parse(raw), today); } catch (e) { /* unreadable */ }
    if (!r.readable) {
      console.warn("[v2] stored records are in an unknown format (" + r.why + "); kept as they are");
      out = { ...out, locked: true };
    } else {
      for (const p of r.problems) console.warn("[v2] set aside, kept as stored: " + p);
      out = { ...out, data: r.data, locked: r.problems.length > 0, problems: r.problems };
      let m = null;
      if (writable && !out.locked) {
        try { m = restoreMoved(key, r.data, raw, today); } catch (e) {
          // never a blank page: the records as read, every copy kept as it is, and the kept-aside line
          console.warn("[v2] merging the copies another tab left failed (" + ((e && e.message) || e) + "); every copy is kept as it is");
          m = { data: null, notice: false, unmerged: true };
        }
      }
      if (m && m.data) out = { ...out, data: m.data };
      if (m && m.notice) out = { ...out, restored: true };
      if (m && m.unmerged) out = { ...out, unmerged: true };
      // limits saved later than the records hold come back from beside them (an earlier-app tab dropped them)
      if (writable && !out.locked) {
        try {
          const s = sideLimitsInto(key, out.data);
          if (s.data && validStore(s.data, today)) {
            if (!writeStore(s.data, key, today)) console.warn("[v2] limits brought back from " + key + LIMITS_SUFFIX + " could not be written: shown for now, back again on the next start");
            out = { ...out, data: { ...s.data, v: versionFor(s.data) }, ...(s.visible ? { restored: true } : {}) };
            console.warn("[v2] limits saved later than the records held were brought back from " + key + LIMITS_SUFFIX);
          }
        } catch (e) { console.warn("[v2] could not read the limits beside the records (" + ((e && e.message) || e) + "); the records as read are used"); }
      }
      // v19.6c review B1: 관심 종목 edits saved later than the records hold come back from beside them (an earlier-app tab dropped them)
      if (writable && !out.locked) {
        try {
          const s = sideWatchInto(key, out.data, today);
          // the key follows the records only when everything in it went into them (never over the only copy of a later state)
          let follow = !s.failed;
          if (s.data && !validStore(s.data, today)) {
            follow = false;
            console.warn("[v2] watch-list edits kept beside the records would not read back merged; the records as read are used, the key is kept");
          }
          if (s.data && follow) {
            if (!writeStore(s.data, key, today)) console.warn("[v2] watch-list edits brought back from " + key + WATCH_SUFFIX + " could not be written: shown for now, back again on the next start");
            out = { ...out, data: { ...s.data, v: versionFor(s.data) }, ...(s.visible ? { restored: true } : {}) };
            console.warn("[v2] watch-list edits saved later than the records held were brought back from " + key + WATCH_SUFFIX);
          } else if (!s.data && s.visible) {
            out = { ...out, restored: true };
            console.warn("[v2] a watch-list stock kept beside the records was left out: the list already holds " + WATCH_MAX);
          }
          if (follow) sideWatchFollow(key, out.data, today);
        } catch (e) { console.warn("[v2] could not read the watch list beside the records (" + ((e && e.message) || e) + "); the records as read are used"); }
      }
    }
  }
  // this app's last write starts with the records as read, when there is none yet (see the tab section)
  if (writable && raw != null) {
    try { if (localStorage.getItem(key + MINE) == null) localStorage.setItem(key + MINE, localStorage.getItem(key)); } catch (e) { /* the next write sets it */ }
  }
  // the guide flag of v19.3c's own key, read into the store (written with the store's next save)
  if (!guideSeenIn(out.data) && isDate(today)) {
    let old = null;
    try { old = localStorage.getItem(key + OLD_GUIDE_SUFFIX); } catch (e) { old = null; }
    if (old === "1") out = { ...out, data: { ...out.data, guideSeen: today } };
  }
  return out;
}

// Before overwriting, the stored blob is checked exactly like readStore does (with today's date); anything it would
// reject on read is first copied to a backup key, so nothing unreadable is ever lost. The store written is checked too:
// a store that would not read back is never written (false, with the reason in the console). Its version tag follows
// what it holds (versionFor). The text written is also kept under key + ".mine" (see the tab section).
export function writeStore(d, key = STORE_KEY, today) {
  try {
    const plain = { ...d, v: versionFor(d) };
    let next;
    if (d && d[FROM_FILE]) { const { wts: _w, ...rest } = plain; next = rest; } else next = stamped(plain);
    const chk = checkStore(next, today);
    if (!chk.readable || chk.problems.length) {
      console.warn("[v2] records not saved, they would not read back: " + (chk.why || chk.problems.join("; ")));
      return false;
    }
    pruneBackups(key);                                          // room first (only .restored. copies and duplicates go)
    const text = JSON.stringify(next);
    const cur = localStorage.getItem(key);
    const made = [];
    const keep = (kind, t) => { const k = backupKey(key, kind); localStorage.setItem(k, t); made.push(k); };
    const parsed = (t) => { try { return JSON.parse(t); } catch (e) { return null; } };
    if (cur != null && cur !== text) {
      const c = parsed(cur);
      if (!(c && validStore(c, today))) keep(".unreadable.", cur);   // keep what we could not read
      // another tab wrote since this one last read or wrote: keep its text unless this write holds all of it; the next
      // read merges it back (restoreMoved)
      else if (lastText.has(key) && cur !== lastText.get(key) && !covers(next, c, today)) {
        keep(".other.", cur);
        console.warn("[v2] another tab had saved records since this one read them: kept, and merged back on the next start");
      }
    }
    // this app's last write is not what is stored and not what this tab wrote last: another tab (the earlier app) wrote
    // over it and the merge on start has not taken it in. Kept as a copy before .mine is replaced, unless this write holds it.
    let mine = null;
    try { mine = localStorage.getItem(key + MINE); } catch (e) { mine = null; }
    if (mine != null && mine !== cur && mine !== text && mine !== lastText.get(key) && !(cur != null && sameLineage(cur, mine))) {
      const m = parsed(mine);
      if (!(m && validStore(m, today) && covers(next, m, today))) {
        keep(".other.", mine);
        console.warn("[v2] this app's last save had been written over by another tab: kept, and merged back on the next start");
      }
    }
    try {
      localStorage.setItem(key, text);
    } catch (e) {
      // the main write failed: the stored text is still there, so a copy of it would only make the next start say 합쳤어요
      for (const k of made) { try { localStorage.removeItem(k); } catch (e2) { /* it stays: a duplicate, pruned later */ } }
      throw e;
    }
    const before = lastText.get(key);
    lastText.set(key, text);
    keepSideLimits(key, next, goneIds(before, next, today));            // 내 규칙 limits beside the records (see that section)
    keepSideWatch(key, next, today);                                     // 관심 종목 beside the records (v19.6c review B1)
    // .mine follows every write once the records exist; the very first records written into an empty storage get it
    // at the next write or start (readStore), and meanwhile an open tab keeps them itself (keepOwnText)
    if (cur != null || mine != null) {
      try { localStorage.setItem(key + MINE, text); } catch (e) { console.warn("[v2] could not update " + key + MINE + " (storage full?)"); }
    }
    dropCovered(key, next, made, today);
    return true;
  } catch (e) {
    console.warn("[v2] could not save records: " + ((e && e.message) || e));
    return false;
  }
}

export function askPersist() {
  try {
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
  } catch (e) { /* not supported */ }
}

// preview: the page importing. A preview export (example data) never goes into the live app, and a live export never
// goes into the preview: the file's own "preview" flag must match.
export function parseImport(text, today, preview = false) {
  try {
    const d = JSON.parse(text);
    if (!!(d && d.preview) !== !!preview) return null;
    if (!validStore(d, today)) return null;
    const out = { decks: d.decks, ...extras(d) };
    return { v: versionFor(out), ...out };
  } catch (e) {
    return null;
  }
}

// What is wrong with a records file, one line per problem (the console names the portfolio, the part, the row and the
// stock: v19.3 F.1 "a message naming it"). [] when nothing is.
export function importIssues(text, today) {
  let d;
  try { d = JSON.parse(text); } catch (e) { return ["not JSON"]; }
  const r = checkStore(d, today);
  return r.readable ? r.problems : [r.why];
}

// Why a file cannot be imported here (null = it can):
//   "preview" = a preview export (example data) opened in the live app -> store.otherKind;
//   "live"    = a live export opened in the preview page -> the plain 기록 불러오기 warning chip (no sentence for it);
//   "bad"     = not a records file, or one bad field -> store.importFail.
export function importProblem(text, today, preview = false) {
  let d;
  try { d = JSON.parse(text); } catch (e) { return "bad"; }
  if (!d || typeof d !== "object" || Array.isArray(d)) return "bad";
  if (!!d.preview !== !!preview) return d.preview ? "preview" : "live";
  return validStore(d, today) ? null : "bad";
}

// Imported decks replace decks with the same id; other decks are kept. Notes and assumptions the same way, per stock.
// The guide flag is this device's: it stays as it is.
// v19.3d review: what the file brings back is an edit made now. Where this device's records (cur, and known: the copies
// other tabs left, storedStores) say otherwise — a removal mark or a history entry for an imported holding, a deletion
// mark or another text for an imported note, another assumption or answer, other limits — the imported value gets the time ts, so a
// merge with an older copy keeps it (and a later edit still wins); a stock the copies hold and the file's portfolio does
// not is taken out at that time (a removal mark, dated today). Nothing else is stamped: a file imported into empty or
// identical records is stored exactly as it is.
export function mergeStores(cur, inc, ts = Date.now(), known = [], today = null) {
  if (!isDate(today) && okTs(ts)) today = new Date(ts + 9 * 3600 * 1000).toISOString().slice(0, 10);   // KST, as todayKst
  // newest first where times cannot tell (values saved without one): the records as stored now (storedStores lists them
  // first), then this tab's, then the copies
  const kn = Array.isArray(known) ? known : [];
  const all = [...kn.slice(0, 1), cur, ...kn.slice(1)].filter((x) => plainObj(x) && Array.isArray(x.decks));
  const decksOf = (id) => all.map((x) => x.decks.find((d) => plainObj(d) && d.id === id)).filter(Boolean);
  const stamp = (v) => (okTs(ts) ? { ...v, ts } : v);
  // an import never lowers a time: a value equal to this device's keeps the later of the two times (the same file
  // imported twice does not undo what the first import brought back)
  const keepLater = (v, times) => { const t = Math.max(0, ...times.filter(okTs)); return t && !(okTs(v.ts) && v.ts >= t) ? { ...v, ts: t } : v; };
  const fresh = (x) => {
    const mine = decksOf(x.id);
    const gone = (t) => mine.some((d) => (Array.isArray(d.removed) && d.removed.some((r) => plainObj(r) && r.t === t))
      || (Array.isArray(d.history) && d.history.some((e) => plainObj(e) && e.t === t)));
    const other = (c) => mine.some((d) => Array.isArray(d.confirms) && d.confirms.some((y) => sameConfirm(y, c) && y.answer !== c.answer));
    // the file replaces the portfolio: a stock this device's copies hold and the file does not is taken out now, and the
    // replaced portfolio's removal marks stay (the latest per stock): a stock the file does not hold stays out, and one it
    // brings back (its holding gets the import time, after the mark) leaves its answers from before the removal behind
    const holds = (t) => x.holdings.some((h) => h.t === t);
    const marks = new Map((Array.isArray(x.removed) ? x.removed : []).filter((r) => plainObj(r)).map((r) => [r.t, r]));
    for (const d of mine) for (const r of Array.isArray(d.removed) ? d.removed : []) if (plainObj(r) && !(marks.has(r.t) && marks.get(r.t).ts >= r.ts)) marks.set(r.t, r);
    if (okTs(ts) && isDate(today)) for (const d of mine) for (const h of d.holdings || []) if (plainObj(h) && !holds(h.t)) marks.set(h.t, { t: h.t, at: today, ts });
    const heldTimes = (t) => mine.flatMap((d) => (d.holdings || []).filter((h) => plainObj(h) && h.t === t).map((h) => h.ts));
    const sameAnswers = (c) => mine.flatMap((d) => (d.confirms || []).filter((y) => sameConfirm(y, c) && y.answer === c.answer).map((y) => y.ts));
    const holdings = x.holdings.map((h) => (gone(h.t) ? stamp(h) : keepLater(h, heldTimes(h.t))));
    // the file's answers come in now too where they differ, or on a stock it brings back (they come back with it)
    const own = (Array.isArray(x.confirms) ? x.confirms : []).map((c) => (other(c) || gone(c.t) ? stamp(c) : keepLater(c, sameAnswers(c))));
    // an answer to 확인 필요 the file lacks, on a stock the file holds: this device's latest answer stays (the file has no
    // later word on it, and an older answer must not come back through a stale copy) — unless the stock was taken out
    // after it (빼기 clears its answers)
    const lastOut = (t) => mine.flatMap((d) => (Array.isArray(d.removed) ? d.removed : []).filter((r) => plainObj(r) && r.t === t && okTs(r.ts)))
      .reduce((a, r) => (!a || r.ts > a.ts ? r : a), null);
    const add = [];
    for (const d of mine) for (const c of Array.isArray(d.confirms) ? d.confirms : []) {
      if (!plainObj(c) || !holds(c.t) || own.some((y) => sameConfirm(y, c))) continue;
      const out = lastOut(c.t);
      if (out && !(editOrder(c, out) > 0)) continue;
      const i = add.findIndex((y) => sameConfirm(y, c));
      if (i < 0) add.push(c); else add[i] = laterOf(add[i], c);
    }
    const confirms = [...own, ...add];
    // 내 규칙 (v19.3d2): the file's limits come in now where this device's copies hold other ones; a file without a limits
    // part (made before 내 규칙 정하기, or never changed) leaves this device's latest limits as they are, as for an answer
    const ownLim = mine.map(limitsEdit).filter(Boolean), fileLim = limitsEdit(x);
    // other limits come in as an edit made now, and after the latest believable time this device (or the side key) holds
    // for them (a clock that was fast and has been corrected: the same rule as limitsSaveTime)
    // (limitsEdit already gives a time more than a day ahead no time: only believable ones count here)
    const ownLatest = Math.max(0, ...ownLim.map((e) => e.ts).filter(okTs));
    const stampLim = (v) => (okTs(ts) ? { ...v, ts: Math.max(ts, ownLatest ? ownLatest + 1 : 0) } : v);
    const lim = fileLim
      ? (mine.some((d) => limitValues(d.limits) !== limitValues(x.limits)) ? stampLim(fileLim)
        : keepLater(fileLim, ownLim.filter((e) => limitValues(e.limits) === limitValues(x.limits)).map((e) => e.ts)))
      : ownLim.reduce((a, e) => laterLimits(a, e), null);
    const { confirms: _c, ...rest } = x;
    // v19.7a round-1 S1: the file's target set comes in now where this device's copies hold another one (so a copy with an
    // older set merged later never takes it back); the same set keeps the later of the times
    const tsOwn = mine.map((d) => d.targetsTs).filter((v) => believable(v));
    const setNow = mine.some((d) => targetSet(d) !== targetSet(x));
    const tts = setNow && okTs(ts) ? Math.max(ts, tsOwn.length ? Math.max(...tsOwn) + 1 : 0) : okTs(x.targetsTs) || tsOwn.length ? Math.max(okTs(x.targetsTs) ? x.targetsTs : 0, ...tsOwn) : null;
    if (tts) rest.targetsTs = tts;
    return withLimitsEdit({ ...rest, holdings, ...(confirms.length || Array.isArray(x.confirms) ? { confirms } : {}),
      ...(marks.size ? { removed: [...marks.values()] } : {}) }, lim);
  };
  const by = new Map(cur.decks.map((x) => [x.id, x]));
  for (const x of inc.decks) by.set(x.id, fresh(x));
  const out = { decks: [...by.values()] };
  const noteDiffers = (t, n) => all.some((x) => { const st = noteState(x, t); return st && (st.gone || st.text !== n.text); });
  const assumeDiffers = (t, a) => all.some((x) => { const b = (perStock(x, "assume") || {})[t]; return plainObj(b) && (b.disc !== a.disc || b.term !== a.term); });
  const sameTimes = (key, t) => all.map((x) => (perStock(x, key) || {})[t]).filter(plainObj).map((v) => v.ts);
  for (const key of ["notes", "assume"]) {
    const brought = Object.fromEntries(Object.entries(perStock(inc, key) || {}).map(([t, v]) =>
      [t, (key === "notes" ? noteDiffers(t, v) : assumeDiffers(t, v)) ? stamp(v) : keepLater(v, sameTimes(key, t))]));
    const m = { ...(perStock(cur, key) || {}), ...brought };
    if (Object.keys(m).length) out[key] = m;
  }
  if (guideSeenIn(cur)) out.guideSeen = cur.guideSeen;
  // v19.6c 관심 종목 (Part C [Q6]): this device's list first, then the file's, up to WATCH_MAX (watchImport)
  const wi = watchImport(cur, inc, ts, kn);
  if (Object.keys(wi.watch).length) out.watch = wi.watch;
  // v19.6b 확인했어요 (Part A.1 [Q6]): the union, the newest time for the same mark
  const seen = unionSeen(cur, inc);
  if (seen.length) out.seen = seen;
  if (cur && plainObj(cur.gone)) {                       // deletion marks stay on this device, minus the notes the file brings
    const gone = { ...cur.gone };
    if (plainObj(gone.notes)) {
      gone.notes = Object.fromEntries(Object.entries(gone.notes).filter(([t]) => !(perStock(inc, "notes") || {})[t]));
      if (!Object.keys(gone.notes).length) delete gone.notes;
    }
    delete gone.watch;                                  // minus the 관심 종목 the file brings back (watchImport)
    if (Object.keys(wi.marks).length) gone.watch = wi.marks;
    if (Object.keys(gone).length) out.gone = gone;
  }
  for (const k of Object.keys(cur || {})) if (!KNOWN_TOP.includes(k)) out[k] = cur[k];   // a later version's parts stay
  // the mark is not enumerable: a later edit (made by spreading these records) is an ordinary write again
  const res = Object.defineProperty({ v: versionFor(out), ...out }, FROM_FILE, { value: true });
  return Object.defineProperty(res, WATCH_DROPPED, { value: wi.dropped });
}

// aside: setAsideCopies (records this device kept aside: they travel in the file under "setAside", never read back by
// 기록 불러오기, so nothing set aside is lost when the device is).
export function exportText(d, preview = false, aside = null) {
  const v = versionFor(d);
  const more = Array.isArray(aside) && aside.length ? { setAside: aside } : {};
  return JSON.stringify(preview ? { v, preview: true, decks: d.decks, ...extras(d), ...more } : { v, decks: d.decks, ...extras(d), ...more }, null, 1);
}

// The records as stored now (another tab may have written them since this tab read) and the readable copies beside them
// (".mine", ".other.", ".unreadable."), then the limits kept beside them (key + ".limits", as portfolios holding only
// their limits): what 기록 불러오기 checks the file against (mergeStores known).
export function storedStores(key, today) {
  const out = [];
  try {
    for (const k of [key, key + MINE, ...backupKeys(key, ".other."), ...backupKeys(key, ".unreadable.")]) { const d = readCopy(k, today); if (d) out.push(d); }
    // the limits kept beside the records count as this device's too (an earlier-app tab may have dropped them from every
    // copy): a file whose limits differ from them comes in as an edit made now, and a file with none leaves the latest
    const side = readSideLimits(key);
    if (side.size) out.push({ decks: [...side].map(([id, e]) => ({ id, kind: "imported", holdings: [], ...(e.limits ? { limits: e.limits } : {}), limitsTs: e.ts })) });
    // v19.6c review B1: so are the 관심 종목 states kept beside them (a stock taken out there comes in from a file as an edit made now)
    const sw = readSideWatch(key, today);
    if (sw) out.push(sideAsStore(sw));
  } catch (e) { return out; }
  return out;
}

export function downloadRecords(d, today, prefix = "baepsae-records", preview = false, key = null) {
  try {
    const blob = new Blob([exportText(d, preview, key ? setAsideCopies(key) : null)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${prefix}-${today}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);   // early revoke can fail the download on iOS Safari ("WebKitBlobResource error 1")
    return true;
  } catch (e) {
    console.warn("[v2] export failed: " + ((e && e.message) || e));
    return false;
  }
}

// Safari (and every iOS browser, all WebKit) may clear site storage after 7 days without a visit.
export function isSafariLike(nav) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  const ua = n.userAgent || "";
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && (n.maxTouchPoints || 0) > 1);
  const safari = /Safari\//.test(ua) && !/Chrome|Chromium|CriOS|FxiOS|EdgiOS|Edg\/|Android/.test(ua);
  return ios || safari;
}

// iPhone Safari itself (v19.0c home-screen hint), never inside the app added to the home screen: on iPhone the records
// live in Safari's storage and the home-screen app has storage of its own, so moving them takes 기록 내보내기 → 기록
// 불러오기. Other iPhone browsers and in-app browsers (KakaoTalk, NAVER …) lack Safari's "Version/… Safari/" pair or
// name themselves; iPad is left out. standalone: the display-mode media query (null = ask the browser).
const NOT_SAFARI = /CriOS|FxiOS|EdgiOS|OPiOS|OPT\/|GSA\/|KAKAOTALK|NAVER|Line\/|FBAN|FBAV|Instagram|DaumApps|Whale|DuckDuckGo/i;
export function iphoneSafari(nav, standalone = null) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  const ua = n.userAgent || "";
  if (!/\((iPhone|iPod)[;\s]/.test(ua) || !/Version\/[\d.]+ .*Safari\//.test(ua) || NOT_SAFARI.test(ua)) return false;
  if (n.standalone === true) return false;
  let sa = standalone;
  if (sa == null) {
    try { sa = typeof window !== "undefined" && !!window.matchMedia && window.matchMedia("(display-mode: standalone)").matches; } catch (e) { sa = false; }
  }
  return !sa;
}
