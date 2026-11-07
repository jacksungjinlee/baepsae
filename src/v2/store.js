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
// Held quantity everywhere = imported + purchases − sales (held.js); no sale may take a holding below 0.
// Top level: guideSeen (v19.3c Part E: the first-visit guide was seen, the date) — a flag of this device, so it never
// travels in a records file; until v19.3d it lived in its own key (key + ".guideSeen"), which is still read once.
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
import { okUnits, belowZero, importedUnits } from "./held.js";

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

// The version-2-only parts of a portfolio (any of them present makes the store v2).
export const V2_DECK_PARTS = ["kind", "imported", "sales", "divs", "history", "limits"];
export const hasV2Parts = (d) => !!(d && Array.isArray(d.decks) && d.decks.some((x) => plainObj(x) && V2_DECK_PARTS.some((k) => x[k] != null)));
export const versionFor = (d) => (hasV2Parts(d) ? STORE_VERSION : BASE_VERSION);

// ---------------- one portfolio ----------------
// null when the portfolio is valid, else the first problem: { part, row (1-based) or null, t, why } (English, for the
// console: the screens use their own approved words).
const bad = (part, row, t, why) => ({ part, row: row == null ? null : row + 1, t: t || null, why });

function purchaseProblem(p, i, today, holds, part = "purchases") {
  if (!plainObj(p) || !isStr(p.t, 20)) return bad(part, i, null, "not a record with a stock code");
  if (!(Number.isInteger(p.qty) && p.qty > 0)) return bad(part, i, p.t, "quantity must be a whole number above 0");
  if (!isPos(p.price)) return bad(part, i, p.t, "price must be a number above 0");
  if (!pastDate(p.date, today)) return bad(part, i, p.t, "date must be a real date, not after today");
  if (!CCY.includes(p.ccy)) return bad(part, i, p.t, "currency must be KRW or USD");
  // Part E: a US purchase carries the won-per-dollar rate the plan used (for 원금 in won). Optional, so earlier records
  // still read; when present it must be a positive number on a USD purchase.
  if (p.fx != null && !(p.ccy === "USD" && isPos(p.fx))) return bad(part, i, p.t, "exchange rate only on a USD record, above 0");
  if (!holds(p.t)) return bad(part, i, p.t, "no holding with this code");
  return null;
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
  if (!holds(s.t)) return bad(part, i, s.t, "no holding with this code");
  return null;
}

function divProblem(x, i, today, holds, part = "divs") {
  if (!plainObj(x) || !isStr(x.t, 20)) return bad(part, i, null, "not a record with a stock code");
  if (!isPos(x.amount)) return bad(part, i, x.t, "amount must be a number above 0");
  if (!CCY.includes(x.ccy)) return bad(part, i, x.t, "currency must be KRW or USD");
  if (!pastDate(x.date, today)) return bad(part, i, x.t, "date must be a real date, not after today");
  if (x.fx != null && !(x.ccy === "USD" && isPos(x.fx))) return bad(part, i, x.t, "exchange rate only on a USD record, above 0");
  if (!holds(x.t)) return bad(part, i, x.t, "no holding with this code");
  return null;
}

// One record set (a portfolio, or one history entry): its purchases, imported rows, sales and dividends; one imported row
// per stock; no sale below 0 shares.
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
  const low = belowZero({ imported: imp, purchases: lists.purchases || [], sales: lists.sales || [] });
  if (low) return bad(prefix + "sales", null, low.t, `sold more than held (${low.date || "undated"})`);
  return null;
}

function historyProblem(hs, today) {
  if (!Array.isArray(hs)) return bad("history", null, null, "not a list");
  for (let i = 0; i < hs.length; i++) {
    const h = hs[i];
    if (!plainObj(h) || !okStockCode(h.t)) return bad("history", i, null, "not an entry with a stock code");
    if (!isStr(h.nk, 120)) return bad("history", i, h.t, "name missing");
    if (!pastDate(h.out, today)) return bad("history", i, h.t, "date taken out must be a real date, not after today");
    if (h.cls != null && !isStr(h.cls, 10)) return bad("history", i, h.t, "market is not valid");
    for (const k of ["purchases", "sales", "divs"]) if (h[k] != null && !Array.isArray(h[k])) return bad("history", i, h.t, k + " is not a list");
    if (h.imported != null && !plainObj(h.imported)) return bad("history", i, h.t, "imported is not one row");
    const recs = { purchases: h.purchases || [], sales: h.sales || [], divs: h.divs || [], imported: h.imported ? [h.imported] : [] };
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
  }
  const holds = (t) => x.holdings.some((h) => h.t === t);
  if (x.kind != null && x.kind !== "imported") return bad("kind", null, null, "unknown kind");
  if (x.imported != null && x.kind !== "imported") return bad("imported", null, null, "imported rows belong to an imported portfolio only");
  if (x.kind === "imported") {
    if (!Array.isArray(x.imported)) return bad("imported", null, null, "an imported portfolio needs its rows");
    const sp = settingsProblem(x.settings);
    if (sp) return sp;
  }
  const rp = recordsProblem(x, today, holds);
  if (rp) return rp;
  if (x.history != null) { const p = historyProblem(x.history, today); if (p) return p; }
  if (x.limits != null) {
    if (!plainObj(x.limits)) return bad("limits", null, null, "not an object");
    for (const k of Object.keys(x.limits)) {
      if (!["stock", "ind"].includes(k) || !(Number.isInteger(x.limits[k]) && x.limits[k] >= 1 && x.limits[k] <= 100)) return bad("limits", null, null, `${k} must be a whole % (1-100)`);
    }
  }
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
const KNOWN_TOP = ["v", "decks", "notes", "assume", "guideSeen", "preview", "setAside"];
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
    if (!p && d.v === BASE_VERSION && V2_DECK_PARTS.some((k) => x[k] != null)) p = bad("version", null, null, "a version-2 part in a version-1 store");
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
  if (d.guideSeen != null) {
    if (pastDate(d.guideSeen, today)) data.guideSeen = d.guideSeen;
    else problems.push("guideSeen: not a date up to today");
  }
  // A top-level part this version does not know (a later version's, e.g. v19.6's 관심 종목) is kept as it is, so a write
  // from this tab never drops it; this app reads nothing from it.
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
    if (!okStockCode(t) || !plainObj(v) || !isDate(v.at) || (today && v.at > today) || !ok(v)) return false;
  }
  return true;
}
const perStock = (d, key) => (d && plainObj(d[key]) ? d[key] : null);

// The store with this stock's note set (text trimmed; empty text removes the note). Pure: the caller saves it.
// null = nothing valid to save (too long, a bad code or date).
export function withNote(data, t, text, today) {
  if (!okStockCode(t) || !isDate(today) || typeof text !== "string") return null;
  const v = text.trim();
  if (v.length > NOTE_MAX) return null;
  const notes = { ...(perStock(data, "notes") || {}) };
  if (v) notes[t] = { text: v, at: today }; else delete notes[t];
  const { notes: _n, ...rest } = data || {};
  return Object.keys(notes).length ? { ...rest, notes } : rest;
}

// The store with this stock's 가치 자세히 assumption (discount rate and 5년 뒤 성장률, the calculator's own ranges).
export function withAssume(data, t, a, today) {
  if (!okStockCode(t) || !isDate(today) || !okAssume(a)) return null;
  return { ...data, assume: { ...(perStock(data, "assume") || {}), [t]: { disc: a.disc, term: a.term, at: today } } };
}
export const noteOf = (data, t) => { const n = perStock(data, "notes"); return n && plainObj(n[t]) ? n[t] : null; };
export const assumeOf = (data, t) => { const a = perStock(data, "assume"); return a && plainObj(a[t]) && okAssume(a[t]) ? a[t] : null; };
// What travels in a records file besides the portfolios (the guide flag stays on the device).
const extras = (d) => ({ ...(perStock(d, "notes") ? { notes: d.notes } : {}), ...(perStock(d, "assume") ? { assume: d.assume } : {}) });

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
    && isNum(c.a) && isNum(c.b) && c.b >= 0 && c.b < c.a && CONFIRM_ANSWERS.includes(c.answer) && isDate(c.at) && !(today && c.at > today));
}

// The store with one answer recorded (it replaces an earlier answer for the same item). Pure: the caller saves it.
// Returns null when the item, the answer or the deck is not valid (nothing to save).
export function withConfirm(data, deckId, item, answer, today) {
  const c = { t: item && item.t, rule: item && item.rule, fy: item && item.fy, a: item && item.a, b: item && item.b, answer, at: today };
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
export function withoutHolding(data, deckId, t, today = null) {
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
  if (sales.length || divs.length) {
    const h = deck.holdings.find((x) => x.t === t);
    const imp = of(deck.imported)[0];
    const out = isDate(today) ? today : [...sales, ...divs].reduce((a, r) => (r.date > a ? r.date : a), "0000-00-00");
    next.history = [...(Array.isArray(deck.history) ? deck.history : []), { t, nk: h.nk, out, ...(h.cls ? { cls: h.cls } : {}),
      ...(imp ? { imported: imp } : {}), purchases: of(deck.purchases), sales, divs }];
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
// Backup keys: key + ".unreadable.<time>" (what a write found and could not read: this app's, or an earlier app's that
// moved a v2 store aside), key + ".other.<time>" (what another tab had written since this tab last read or wrote: kept
// before this tab writes, merged back on the next read) and key + ".restored.<time>" (a copy of what was merged back).
// Each kind keeps its newest BACKUPS_KEEP entries; the newest is never removed.
export const BACKUPS_KEEP = 3;
const BACKUP_KINDS = [".unreadable.", ".other.", ".restored."];
// The text this tab last read or wrote, per key: a write that finds anything else there knows another tab wrote meanwhile.
const lastText = new Map();
const backupKeys = (key, mid) => {
  const out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (typeof k === "string" && k.startsWith(key + mid)) out.push(k);
    }
  } catch (e) { return []; }
  return out.sort((a, b) => Number(a.slice(a.lastIndexOf(".") + 1)) - Number(b.slice(b.lastIndexOf(".") + 1)));
};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const later = (a, b) => (a && b && typeof b.at === "string" && typeof a.at === "string" && b.at > a.at ? b : a);

// A list both copies hold: everything in the current copy, then whatever only the other one has (the same record is
// the same JSON). Nothing is dropped; a record one tab deleted can come back, which the notice asks the user to check.
const unionList = (a, b) => {
  if (!Array.isArray(a) && !Array.isArray(b)) return undefined;
  const out = [...(Array.isArray(a) ? a : [])];
  for (const x of Array.isArray(b) ? b : []) if (!out.some((y) => same(y, x))) out.push(x);
  return out;
};
// One portfolio both copies hold, both changed: the current copy leads (its name, settings, kind, limits) and every
// record either one holds is kept: holdings (by stock), imported rows (by stock: the current row wins), purchases, sales,
// dividends and history entries (by identity), answers to 확인 필요 (the later answer for the same item).
function unionDeck(cur, other) {
  const holdings = [...cur.holdings, ...other.holdings.filter((h) => !cur.holdings.some((x) => x.t === h.t))];
  const out = { ...other, ...cur, holdings, purchases: unionList(cur.purchases, other.purchases) || [] };
  const imp = Array.isArray(cur.imported) || Array.isArray(other.imported)
    ? [...(cur.imported || []), ...(other.imported || []).filter((r) => r.t == null ? !(cur.imported || []).some((y) => same(y, r))
      : !(cur.imported || []).some((y) => y.t === r.t))] : undefined;
  if (imp) out.imported = imp;
  for (const k of ["sales", "divs", "history"]) { const u = unionList(cur[k], other[k]); if (u) out[k] = u; }
  const confirms = [...(cur.confirms || [])];
  for (const c of other.confirms || []) {
    const i = confirms.findIndex((x) => sameConfirm(x, c));
    if (i < 0) confirms.push(c); else confirms[i] = later(confirms[i], c);
  }
  if (confirms.length) out.confirms = confirms;
  return out;
}

// The current store with another copy's records added in (cur leads; nothing either holds is lost). null when the result
// would not be valid (then nothing is changed and the other copy stays where it is).
export function mergeTabs(other, cur, today) {
  const decks = [...cur.decks];
  for (const d of other.decks) {
    const i = decks.findIndex((x) => x.id === d.id);
    if (i < 0) decks.push(d);
    else if (!same(decks[i], d)) decks[i] = unionDeck(decks[i], d);
  }
  const out = { ...other, ...cur, decks };
  for (const key of ["notes", "assume"]) {
    const m = { ...(perStock(other, key) || {}) };
    for (const [t, x] of Object.entries(perStock(cur, key) || {})) m[t] = m[t] ? later(x, m[t]) : x;
    if (Object.keys(m).length) out[key] = m;
  }
  if (guideSeenIn(cur) || guideSeenIn(other)) out.guideSeen = guideSeenIn(cur) ? cur.guideSeen : other.guideSeen;
  delete out.preview;
  out.v = versionFor(out);
  return validStore(out, today) ? out : null;
}

// After a good read, copies another tab left behind are merged back in:
//   ".other.<time>"      any readable store: what another tab had written before this one overwrote it (writeStore).
//   ".unreadable.<time>" only a v2 store with v2 parts, and only while the current store has none: an earlier-app tab
//                        moved it aside and wrote its own. A current store with v2 parts was written by this version
//                        after that, so it leads and the backup stays as it is.
// Each merged copy is kept under ".restored.<time>". -> the merged store, or null when nothing was merged.
function restoreMoved(key, cur, today) {
  let merged = null;
  const used = [];
  const cands = [...backupKeys(key, ".unreadable.").map((k) => [k, true]), ...backupKeys(key, ".other.").map((k) => [k, false])]
    .sort((a, b) => stamp(a[0]) - stamp(b[0]));
  for (const [k, moved] of cands) {
    let d = null;
    try { d = JSON.parse(localStorage.getItem(k)); } catch (e) { d = null; }
    if (!d || !validStore(d, today)) continue;
    if (moved && (d.v !== STORE_VERSION || !hasV2Parts(d) || hasV2Parts(merged || cur))) continue;
    const m = mergeTabs(d, merged || cur, today);
    if (!m) { console.warn(`[v2] the copy in ${k} could not be merged with the current records; both are kept as they are`); continue; }
    merged = m;
    used.push(k);
  }
  if (!merged) return null;
  try {
    const text = JSON.stringify(merged);
    localStorage.setItem(key, text);
    lastText.set(key, text);
    for (const k of used) {
      localStorage.setItem(key + ".restored." + stamp(k), localStorage.getItem(k));
      localStorage.removeItem(k);
    }
  } catch (e) {
    console.warn("[v2] could not merge back the records another tab left: " + ((e && e.message) || e));
    return null;
  }
  pruneBackups(key);
  console.warn(`[v2] records another tab had left were merged back (${used.join(", ")})`);
  return merged;
}
const stamp = (k) => Number(k.slice(k.lastIndexOf(".") + 1)) || 0;
// A new backup key: a time not used yet for that kind.
function backupKey(key, kind) {
  let t = Date.now();
  try { while (localStorage.getItem(key + kind + t) != null) t++; } catch (e) { /* the write will say */ }
  return key + kind + t;
}
// Each kind keeps its newest BACKUPS_KEEP copies (never the newest one removed).
export function pruneBackups(key) {
  try {
    for (const kind of BACKUP_KINDS) {
      const ks = backupKeys(key, kind);
      for (const k of ks.slice(0, Math.max(0, ks.length - BACKUPS_KEEP))) localStorage.removeItem(k);
    }
  } catch (e) { /* nothing removed */ }
}
// What 기록 내보내기 adds besides the records: every copy not merged back (".unreadable." and ".other."), as stored, so a
// portfolio that was set aside travels in the file too. [{ key, text }], newest last.
export function setAsideCopies(key) {
  const out = [];
  try {
    for (const k of [...backupKeys(key, ".unreadable."), ...backupKeys(key, ".other.")].sort((a, b) => stamp(a) - stamp(b))) {
      const text = localStorage.getItem(k);
      if (typeof text === "string") out.push({ key: k.slice(key.length + 1), text });
    }
  } catch (e) { return []; }
  return out;
}

// { data, writable, locked, problems, restored }: locked = something stored could not be read (all of it, or some
// portfolios: problems names them). It stays untouched; the first write moves it to a backup key first (see writeStore),
// so 기록 불러오기 and 샀어요 still work. restored = records another tab had moved aside were put back (say so once).
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
      const merged = writable && !out.locked ? restoreMoved(key, r.data, today) : null;
      if (merged) out = { ...out, data: merged, restored: true };
    }
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
// what it holds (versionFor).
export function writeStore(d, key = STORE_KEY, today) {
  try {
    const next = { ...d, v: versionFor(d) };
    const chk = checkStore(next, today);
    if (!chk.readable || chk.problems.length) {
      console.warn("[v2] records not saved, they would not read back: " + (chk.why || chk.problems.join("; ")));
      return false;
    }
    const cur = localStorage.getItem(key);
    if (cur != null) {
      let ok = false;
      try { ok = validStore(JSON.parse(cur), today); } catch (e) { ok = false; }
      if (!ok) localStorage.setItem(backupKey(key, ".unreadable."), cur);   // keep what we could not read
      // another tab wrote since this one last read or wrote: keep its text; the next read merges it back (restoreMoved)
      else if (lastText.has(key) && cur !== lastText.get(key)) {
        localStorage.setItem(backupKey(key, ".other."), cur);
        console.warn("[v2] another tab had saved records since this one read them: kept, and merged back on the next start");
      }
    }
    const text = JSON.stringify(next);
    localStorage.setItem(key, text);
    lastText.set(key, text);
    pruneBackups(key);
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
export function mergeStores(cur, inc) {
  const by = new Map(cur.decks.map((x) => [x.id, x]));
  for (const x of inc.decks) by.set(x.id, x);
  const out = { decks: [...by.values()] };
  for (const key of ["notes", "assume"]) {
    const m = { ...(perStock(cur, key) || {}), ...(perStock(inc, key) || {}) };
    if (Object.keys(m).length) out[key] = m;
  }
  if (guideSeenIn(cur)) out.guideSeen = cur.guideSeen;
  for (const k of Object.keys(cur || {})) if (!KNOWN_TOP.includes(k)) out[k] = cur[k];   // a later version's parts stay
  return { v: versionFor(out), ...out };
}

// aside: setAsideCopies (records this device kept aside: they travel in the file under "setAside", never read back by
// 기록 불러오기, so nothing set aside is lost when the device is).
export function exportText(d, preview = false, aside = null) {
  const v = versionFor(d);
  const more = Array.isArray(aside) && aside.length ? { setAside: aside } : {};
  return JSON.stringify(preview ? { v, preview: true, decks: d.decks, ...extras(d), ...more } : { v, decks: d.decks, ...extras(d), ...more }, null, 1);
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
