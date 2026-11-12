// ================= 기록: 샀어요 · 팔았어요 · 배당 받았어요 on an existing portfolio (v19.6a, Part A.1–A.3) =================
// Pure functions, no React and no Korean text (records.jsx turns the results into copy from src/copy/v2.js).
// Spec: docs/tasks/v19.6-records-alerts-dark.md A.1 (store rules), A.2 (screens), A.3 (taking a stock out), Part I.1 (the
// exchange rate of a record's date). Unit tests: tests/test_v2_records.py (run through Node).
//
// Every edit returns the whole store (the caller saves it with store.writeStore, which checks it again) or a refusal
// { ok: false, why } the screen turns into an approved line. Nothing is saved that the store's own check would refuse.
import { recordId, deckProblem, problemText } from "./store.js";
import { belowZero, heldUnits, UNIT, toUnits, okUnits, byAmount, VIEW_SPLITS } from "./held.js";
import { ledger, splitsToStore, purchaseRate } from "./lots.js";
import { validRows } from "./track.js";

const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const pos = (x) => isNum(x) && x > 0;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const realDate = (x) => typeof x === "string" && DATE.test(x) && new Date(x + "T00:00:00Z").toISOString().slice(0, 10) === x;

// ---------------- the exchange rate of a record's date (A.1, Part I.1) ----------------
// A new USD record saves the won-per-dollar rate of its own date: today's from data.json fx (as 샀어요 always did), a past
// date's from macro.json fxHist ({ asOf, rows: [[date, close], ...] }, USD/KRW closes since 2016): the close on that date,
// or the last close before it. Never another day's rate:
//   - a date before 2016 (or before fxHist's first close) is saved without a rate (Part I.1: left out of won totals, the
//     existing noFx line says so);
//   - a past date after fxHist's last close: only when fxHist ends on data.json's own FX date and the data is not stale
//     (then no close has been published since, so the last close is that day's rate); else not saved yet (the approved
//     "환율 정보를 불러오지 못해 …" line);
//   - no fxHist, or one that cannot be read: a past-dated USD record is not saved yet (the same line).
// env: { today, fx, fxDate, fxHist, stale }. -> { ok: true, fx } | { ok: true, fx: null, before: true } | { ok: false, why }
export const FX_FROM = "2016-01-01";
export function rateFor(date, env) {
  const e = env || {};
  if (!realDate(date)) return { ok: false, why: "date" };
  if (date < FX_FROM) return { ok: true, fx: null, before: true };
  if (date === e.today) return pos(e.fx) ? { ok: true, fx: e.fx } : { ok: false, why: "noToday" };
  const rows = validRows(e.fxHist);
  if (!rows || typeof e.fxHist.asOf !== "string" || e.fxHist.asOf !== rows[rows.length - 1][0]) return { ok: false, why: "noHist" };
  if (date < rows[0][0]) return { ok: true, fx: null, before: true };
  const last = rows[rows.length - 1];
  if (date > last[0]) {
    if (last[0] === e.fxDate && !e.stale && !(e.today && date > e.today)) return { ok: true, fx: last[1] };
    return { ok: false, why: "old" };
  }
  let lo = 0, hi = rows.length - 1, hit = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (rows[mid][0] <= date) { hit = rows[mid]; lo = mid + 1; } else hi = mid - 1;
  }
  return hit ? { ok: true, fx: hit[1] } : { ok: true, fx: null, before: true };
}
// The env rateFor reads, from the app's load state (data.json, macro.json) and today's date.
export function rateEnv(load, today) {
  const ok = load && load.status === "ok";
  return { today, fx: ok ? load.data.fx : null, fxDate: ok ? load.data.fxDate || null : null, fxHist: ok && load.macro ? load.macro.fxHist || null : null,
    stale: !!(ok && load.fresh && load.fresh.stale) };
}

// ---------------- what a portfolio holds of one stock ----------------
// -> { held (units now, splits applied), byAmount (its imported row was put in by amount: only a full sale, by 판 금액),
//      first (the first dated record of the stock, or null), avg ({ avg, ccy } | null), ccy, inHoldings, inHistory }
export function stockState(deck, t) {
  const units = heldUnits(deck).get(t) || 0;
  const imp = (deck.imported || []).find((r) => r && r.t === t) || null;
  const dates = [];
  for (const k of ["purchases", "sales"]) for (const r of deck[k] || []) if (r && r.t === t && realDate(r.date)) dates.push(r.date);
  for (const r of deck.imported || []) if (r && r.t === t && realDate(r.date)) dates.push(r.date);
  dates.sort();
  const L = ledger(deck, t);
  const ccy = L.ccy || (imp && imp.ccy) || null;
  return { held: units, qty: units / UNIT, byAmount: !!imp && byAmount(imp), first: dates[0] || null,
    avg: L.avgOwn != null && L.avgOwn > 0 ? { avg: L.avgOwn, ccy } : null, ccy, ledger: L,
    inHoldings: (deck.holdings || []).some((h) => h && h.t === t), inHistory: (deck.history || []).some((e) => e && e.t === t) };
}

// The portfolios a 기록 for stock t can go to (the company page): a holding (held, sold out, or planned) or a stock taken out
// of it (history: 배당 받았어요 only). -> [deck]
export const decksFor = (data, t) => ((data && data.decks) || []).filter((d) => d && ((d.holdings || []).some((h) => h && h.t === t)
  || (d.history || []).some((e) => e && e.t === t)));

// ---------------- checks before saving ----------------
// Parse a typed number ("1,234.5" -> 1234.5); "" -> null; anything else NaN.
export function typed(v) {
  const s = String(v == null ? "" : v).replace(/,/g, "").trim();
  if (s === "") return null;
  return /^\d+(\.\d+)?$/.test(s) ? Number(s) : NaN;
}
const decimals = (x, d) => Math.abs(x * 10 ** d - Math.round(x * 10 ** d)) < 1e-6;

// A sale of stock t (in the stock's currency; Korea whole shares unless imported by amount).
// input: { qty, price, date, amountWon (by amount only) } as typed; s: the stock's data row (its close is the default price).
// -> { ok: true, rec, proceedsWon, ... } | { ok: false, why: "input" | "tooMany" | "tooEarly" | "rate" | "noPrice" }
export function checkSale(deck, t, input, s, env) {
  const st = stockState(deck, t);
  const usd = st.ccy === "USD" || (s && s.ccy === "USD");
  const ccy = usd ? "USD" : "KRW";
  const date = input.date || env.today;
  if (!realDate(date) || date > env.today) return { ok: false, why: "input" };
  if (st.first && date < st.first) return { ok: false, why: "tooEarly" };
  let qty, price;
  const r = usd ? rateFor(date, env) : { ok: true, fx: null };
  if (st.byAmount) {
    // a holding put in by amount has no real share count: it is sold all at once, by 판 금액 (won)
    const amt = typed(input.amountWon);
    if (!(pos(amt) && Number.isInteger(amt))) return { ok: false, why: "input" };
    if (!(st.held > 0)) return { ok: false, why: "tooMany" };
    if (!r.ok) return { ok: false, why: "rate" };
    if (usd && !pos(r.fx)) return { ok: false, why: "rate" };
    qty = st.held / UNIT;
    price = usd ? amt / r.fx / qty : amt / qty;
  } else {
    const q = typed(input.qty);
    if (!(pos(q) && (usd ? okUnits(q) : Number.isInteger(q)))) return { ok: false, why: "input" };
    const p = typed(input.price);
    if (Number.isNaN(p) || (p != null && !pos(p)) || (usd && p != null && !decimals(p, 4))) return { ok: false, why: "input" };
    price = p == null ? (s && pos(s.price) ? s.price : null) : p;
    if (!pos(price)) return { ok: false, why: "noPrice" };
    qty = q;
    if (!r.ok) return { ok: false, why: "rate" };
  }
  const rec = { id: recordId(), t, qty, price, date, ccy, ...(usd && pos(r.fx) ? { fx: r.fx } : {}) };
  const sales = [...(deck.sales || []), rec];
  if (belowZero({ ...deck, sales, splits: splitsToStore(deck, t) || deck.splits })) return { ok: false, why: "tooMany" };
  return { ok: true, rec };
}

// One more purchase (샀어요 on an existing portfolio): whole shares (required), price blank -> the latest close.
export function checkPurchase(deck, t, input, s, env) {
  const st = stockState(deck, t);
  const usd = st.ccy ? st.ccy === "USD" : !!(s && s.ccy === "USD");
  const date = input.date || env.today;
  if (!realDate(date) || date > env.today) return { ok: false, why: "input" };
  const q = typed(input.qty);
  if (!(pos(q) && Number.isInteger(q))) return { ok: false, why: "input" };
  const p = typed(input.price);
  if (Number.isNaN(p) || (p != null && !pos(p))) return { ok: false, why: "input" };
  const price = p == null ? (s && pos(s.price) ? s.price : null) : p;
  if (!pos(price)) return { ok: false, why: "noPrice" };
  const r = usd ? rateFor(date, env) : { ok: true, fx: null };
  if (!r.ok) return { ok: false, why: "rate" };
  return { ok: true, rec: { id: recordId(), t, date, qty: q, price, ccy: usd ? "USD" : "KRW", ...(usd && pos(r.fx) ? { fx: r.fx } : {}) } };
}

// A dividend received (after tax, as the brokerage deposit shows it): Korea whole won, US dollars with up to 2 decimals.
export function checkDiv(deck, t, input, s, env) {
  const st = stockState(deck, t);
  const hist = (deck.history || []).filter((e) => e && e.t === t).slice(-1)[0];
  const ccy = st.ccy || (hist && ((hist.purchases || [])[0] || (hist.sales || [])[0] || hist.imported || {}).ccy) || (s && s.ccy === "USD" ? "USD" : "KRW");
  const usd = ccy === "USD";
  const date = input.date || env.today;
  if (!realDate(date) || date > env.today) return { ok: false, why: "input" };
  const a = typed(input.amount);
  if (!(pos(a) && (usd ? decimals(a, 2) : Number.isInteger(a)))) return { ok: false, why: "input" };
  const r = usd ? rateFor(date, env) : { ok: true, fx: null };
  if (!r.ok) return { ok: false, why: "rate" };
  return { ok: true, rec: { id: recordId(), t, amount: a, ccy: usd ? "USD" : "KRW", date, ...(usd && pos(r.fx) ? { fx: r.fx } : {}) } };
}

// ---------------- the store with one record more ----------------
// kind: "purchases" | "sales" | "divs". A dividend of a stock the portfolio no longer holds goes into its latest history
// entry (store.js: "a later dividend of that stock goes into its entry"). The portfolio keeps the splits the screens applied
// to that stock (lots.splitsToStore), so the stored records read back exactly as they were shown and checked.
// -> the new store, or null when the result would not pass store.js (nothing to save; the console says why).
export function withRecord(data, deckId, kind, rec, today) {
  const deck = data && Array.isArray(data.decks) ? data.decks.find((d) => d && d.id === deckId) : null;
  if (!deck || !rec || !["purchases", "sales", "divs"].includes(kind)) return null;
  const t = rec.t;
  const holds = (deck.holdings || []).some((h) => h && h.t === t);
  const sp = splitsToStore(deck, t);
  let next;
  if (holds) next = { ...deck, [kind]: [...(deck[kind] || []), rec] };
  else if (kind === "divs") {
    const i = (deck.history || []).map((e, j) => (e && e.t === t ? j : -1)).filter((j) => j >= 0).pop();
    if (i == null) return null;
    next = { ...deck, history: deck.history.map((e, j) => (j === i ? { ...e, divs: [...(e.divs || []), rec] } : e)) };
  } else return null;
  if (sp) next.splits = sp;
  const p = deckProblem(stripView(next), today);
  if (p) { console.warn("[v2] record not saved: " + problemText(next, p)); return null; }
  return { ...data, decks: data.decks.map((d) => (d && d.id === deckId ? next : d)) };
}
const stripView = (d) => { if (!d || !d[VIEW_SPLITS]) return d; const { [VIEW_SPLITS]: _v, ...rest } = d; return rest; };

// ---------------- the records of one stock in one portfolio (the record sheet's list) ----------------
// -> [{ key, kind: "imp" | "buy" | "sell" | "div", rec, list, entry (history index or null), index, date, ccy, qty, amount }]
//   newest first; an undated imported row last. Imported rows (가진 종목) are listed but not deleted here (가진 종목 넣기
//   edits them).
export function recordsOf(deck, t) {
  const out = [];
  const add = (list, kind, entry, arr) => (arr || []).forEach((r, i) => {
    if (!r || r.t !== t) return;
    out.push({ key: `${entry == null ? "d" : "h" + entry}.${list}.${i}`, kind, rec: r, list, entry, index: i, date: realDate(r.date) ? r.date : null, ccy: r.ccy,
      qty: kind === "div" ? null : r.qty != null ? r.qty : null, amount: kind === "div" ? r.amount : kind === "imp" && r.amountWon != null ? r.amountWon : null });
  });
  add("imported", "imp", null, deck.imported);
  add("purchases", "buy", null, deck.purchases);
  add("sales", "sell", null, deck.sales);
  add("divs", "div", null, deck.divs);
  (deck.history || []).forEach((e, i) => {
    if (!e || e.t !== t) return;
    add("imported", "imp", i, e.imported ? [e.imported] : []);
    add("purchases", "buy", i, e.purchases);
    add("sales", "sell", i, e.sales);
    add("divs", "div", i, e.divs);
  });
  const ORDER = { imp: 0, buy: 1, sell: 2, div: 3 };
  return out.sort((a, b) => (a.date === b.date ? ORDER[b.kind] - ORDER[a.kind] : a.date == null ? 1 : b.date == null ? -1 : a.date < b.date ? 1 : -1));
}

// The store without one record (지우기 + confirm). Refused when it would leave a later sale bigger than the shares held
// (the approved "이 기록을 지우면 판 주식이 산 주식보다 많아져요 …" line): { ok: false, why: "below" }. Imported rows are not
// deleted here. -> { ok: true, data } | { ok: false, why }
export function withoutRecord(data, deckId, item, today) {
  const deck = data && Array.isArray(data.decks) ? data.decks.find((d) => d && d.id === deckId) : null;
  if (!deck || !item || !["purchases", "sales", "divs"].includes(item.list)) return { ok: false, why: "gone" };
  const drop = (arr) => {
    if (!Array.isArray(arr) || !arr[item.index] || arr[item.index] !== item.rec) return null;
    return arr.filter((_, i) => i !== item.index);
  };
  let next;
  if (item.entry == null) {
    const l = drop(deck[item.list]);
    if (!l) return { ok: false, why: "gone" };
    next = { ...deck, [item.list]: l };
    if (belowZero(next)) return { ok: false, why: "below" };
  } else {
    const e = (deck.history || [])[item.entry];
    const l = e ? drop(e[item.list]) : null;
    if (!l) return { ok: false, why: "gone" };
    const ne = { ...e, [item.list]: l };
    if (belowZero({ imported: ne.imported ? [ne.imported] : [], purchases: ne.purchases || [], sales: ne.sales || [], splits: deck.splits,
      [VIEW_SPLITS]: deck[VIEW_SPLITS], createdAt: deck.createdAt })) return { ok: false, why: "below" };
    next = { ...deck, history: deck.history.map((x, j) => (j === item.entry ? ne : x)) };
  }
  const p = deckProblem(stripView(next), today);
  if (p) { console.warn("[v2] record not deleted: " + problemText(next, p)); return { ok: false, why: "store" }; }
  return { ok: true, data: { ...data, decks: data.decks.map((d) => (d && d.id === deckId ? next : d)) } };
}

// The won amounts of a sale for the result card: 판 금액 and 산 가격보다 (moving average, lots.js), before it is saved.
// -> { proceedsOwn, proceedsWon (null: no rate), gain (null: noCost / noRate), why, usdOnly, removedWon, pct }
export function salePreview(deck, rec) {
  const L = ledger({ ...deck, sales: [...(deck.sales || []), rec] }, rec.t);
  const s = L.sales.find((x) => x.rec === rec);
  if (!s) return null;
  const base = s.removedWon != null ? s.removedWon + (s.removedUsdOwn > 0 && pos(s.rate) ? s.removedUsdOwn * s.rate : 0) : null;
  return { proceedsOwn: s.proceedsOwn, proceedsWon: s.proceedsWon, gain: s.gain, why: s.why, usdOnly: s.usdOnly,
    pct: s.gain != null && base > 0 ? (s.gain / base) * 100 : null };
}

// Does stock t have no shares left in this portfolio after the records (a full sale: 포트폴리오에서도 뺄까요?)
export const soldOutNow = (deck, t) => (deck.holdings || []).some((h) => h && h.t === t) && !((heldUnits(deck).get(t) || 0) > 0)
  && (deck.sales || []).some((s) => s && s.t === t);

export { purchaseRate };
