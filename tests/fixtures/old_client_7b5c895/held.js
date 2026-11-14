// Test fixture: src/v2/held.js exactly as on main at 7b5c895 (v19.3d2, the app live before v19.6a; this line added). The tests run the
// earlier app's code against v19.6a stores from here, so no test depends on git history (CI checks out shallow). Never edit below.
// ================= Held quantity: one rule for every screen (v19.3d; docs/tasks/v19.6-records-alerts-dark.md A.1) =================
// Pure functions, no React and no Korean text. Unit tests: tests/test_v2_store_v2.py (run through Node).
//
// Held quantity of a stock on a date = imported quantity (가진 종목 넣기, v19.3 Part F) + purchases (샀어요) dated on or
// before it − sales (팔았어요, v19.6a) dated on or before it. An imported holding without a date counts as held before
// every dated record; a dated one (금액으로 넣기: the close it was valued at) counts from its date. On the same date
// purchases come before sales. Quantities are compared in whole units of 1/10,000 share (Korea is whole shares anyway),
// never as floating sums, so a valid full sale of 0.1 + 0.2 shares is never refused.
// The daily check (rules.js heldQty), the portfolio values (pf.js, track.js) and the store's own check that no sale takes
// a holding below 0 (store.js) all read this module; the account server (v19.4) is meant to reuse it.

export const UNIT = 10000;                                     // 1 unit = 1/10,000 share
const isNum = (x) => typeof x === "number" && Number.isFinite(x);

// Units are whole numbers up to Number.MAX_SAFE_INTEGER (about 900 billion shares): a crafted file with a bigger or
// non-finite quantity or amount counts nothing (null), so no sum ever becomes Infinity or loses whole units.
const okU = (u) => Number.isSafeInteger(u);
// A quantity in units (rounded to the nearest unit), or null.
export const toUnits = (q) => { const u = isNum(q) ? Math.round(q * UNIT) : null; return u != null && okU(u) ? u : null; };
// A positive quantity with at most 4 decimals (a whole number of units).
export const okUnits = (q) => isNum(q) && q > 0 && okU(Math.round(q * UNIT)) && Math.abs(q * UNIT - Math.round(q * UNIT)) < 1e-6 && Math.round(q * UNIT) >= 1;

// The units one imported row stands for: its quantity, or (금액으로 넣기) the amount in won divided by that day's close
// (US at that day's rate), rounded to the nearest unit. A row added by name only (no stock code, not in the data) has no
// share count: null.
export function importedUnits(r) {
  if (!r || typeof r !== "object") return null;
  if (r.qty != null) return okUnits(r.qty) ? toUnits(r.qty) : null;
  if (r.amountWon != null && typeof r.t === "string") {
    const px = isNum(r.close) && r.close > 0 ? r.close * (r.ccy === "USD" ? (isNum(r.fx) && r.fx > 0 ? r.fx : NaN) : 1) : NaN;
    const u = isNum(r.amountWon) && r.amountWon > 0 && px > 0 ? Math.round((r.amountWon / px) * UNIT) : null;
    return u != null && okU(u) && u >= 1 ? u : null;
  }
  return null;
}
// An imported row valued by amount (금액으로 넣기): its share count is derived, so it can only be sold all at once (v19.6 A.2).
export const byAmount = (r) => !!r && r.qty == null && r.amountWon != null;

// The events of one record set ({ imported, purchases, sales }: a portfolio or one history entry), oldest first:
// undated imported rows first, then by date; on one date imported, then purchases, then sales.
function events(recs, t) {
  const out = [];
  const add = (list, kind, units) => {
    for (const r of Array.isArray(list) ? list : []) {
      if (!r || typeof r.t !== "string" || (t != null && r.t !== t)) continue;
      const u = units(r);
      if (u == null) continue;
      out.push({ t: r.t, date: typeof r.date === "string" ? r.date : "", kind, u });
    }
  };
  add(recs && recs.imported, 0, importedUnits);
  add(recs && recs.purchases, 1, (p) => (Number.isInteger(p.qty) && p.qty > 0 && okU(p.qty * UNIT) ? p.qty * UNIT : null));
  add(recs && recs.sales, 2, (s) => (okUnits(s.qty) ? -toUnits(s.qty) : null));
  return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.kind - b.kind));
}

// Units held per stock on `date` (inclusive; null = after every record). Map t -> units (0 included: a stock sold down to
// nothing is still listed, so a caller can tell "sold out" from "never held").
export function heldUnits(recs, date = null) {
  const m = new Map();
  for (const e of events(recs, null)) {
    if (date != null && e.date && e.date > date) continue;
    m.set(e.t, (m.get(e.t) || 0) + e.u);
  }
  return m;
}

// Shares held now per stock with more than 0 shares (Map t -> quantity as a number, units / UNIT).
export function heldQty(recs, date = null) {
  const out = new Map();
  for (const [t, u] of heldUnits(recs, date)) if (u > 0) out.set(t, u / UNIT);
  return out;
}

// The first record at which a sale takes a holding below 0 (walking the events in order), or null when none does.
// -> { t, date } | null
export function belowZero(recs) {
  const m = new Map();
  for (const e of events(recs, null)) {
    const v = (m.get(e.t) || 0) + e.u;
    if (v < 0) return { t: e.t, date: e.date || null };
    m.set(e.t, v);
  }
  return null;
}
