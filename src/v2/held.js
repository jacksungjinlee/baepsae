// ================= Held quantity: one rule for every screen (v19.3d; docs/tasks/v19.6-records-alerts-dark.md A.1) =================
// Pure functions, no React and no Korean text. Unit tests: tests/test_v2_store_v2.py (run through Node).
//
// Held quantity of a stock on a date = imported quantity (가진 종목 넣기, v19.3 Part F) + purchases (샀어요) dated on or
// before it − sales (팔았어요, v19.6a) dated on or before it. An imported holding without a date counts as held before
// every dated record; a dated one (금액으로 넣기: the close it was valued at) counts from its date. On the same date
// purchases come before sales. Quantities are compared in whole units of 1/10,000 share (Korea is whole shares anyway),
// never as floating sums, so a valid full sale of 0.1 + 0.2 shares is never refused. After a split whose ratio does not give
// whole units, every screen, the ledger (lots.js) and the store's check count them one way (count() below, Track 2 audit 1.1).
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

// ---------------- stock splits (v19.6a, docs/tasks/v19.6-records-alerts-dark.md A.6) ----------------
// A split { t, date, r }: from `date` on, one old share of t is r new shares (4 for a 4:1 split, 0.1 for a 10:1 주식병합).
// Records stay as typed; a record dated before the split is read at the new basis (quantity x r, price / r; its money is
// the same). Two sources:
//   recs.splits          the splits a portfolio stored with its records (store.js validates the store with these only, so a
//                        sale of the new share count is never refused: the app stores the split with the record that needs it);
//   recs[VIEW_SPLITS]    data.json's splits for that portfolio's stocks, put on an in-memory copy of the portfolio for the
//                        screens (lots.js withDataSplits). A Symbol key: JSON.stringify and the store's checks never see it,
//                        so it is never written.
// The same split in both counts once: the same stock and ratio within SAME_SPLIT_DAYS days is one split (round-2 review:
// a stored split and data.json's dated a few days apart, e.g. the decision day and the effective day, must never apply
// twice: 101 shares instead of 11). SAME_SPLIT_DAYS is the pipeline's same-event window (fetch_data.py
// SPLIT_SAME_EVENT_DAYS, #117: 10 days), round-2 review A1. The first one met wins (the stored one). An imported row without a date counts as typed on the day the portfolio was made
// (recs.createdAt): a split after that day applies to it, one before it does not (the user typed the new share count).
export const VIEW_SPLITS = Symbol("data.json splits for the screens");
const SPLIT_DATE = /^\d{4}-\d{2}-\d{2}$/;
export const SAME_SPLIT_DAYS = 10;
const dayNo = (d) => Date.parse(d + "T00:00:00Z") / 86400000;
// Are a and b the same split (the same stock and ratio, dated at most SAME_SPLIT_DAYS days apart)?
export const sameSplit = (a, b) => !!a && !!b && a.t === b.t && Math.abs(a.r - b.r) < 1e-9 && Math.abs(dayNo(a.date) - dayNo(b.date)) <= SAME_SPLIT_DAYS;
export const okSplit = (s) => !!s && typeof s === "object" && typeof s.t === "string" && s.t.length > 0 && typeof s.date === "string" && SPLIT_DATE.test(s.date)
  && isNum(s.r) && s.r > 0 && s.r !== 1 && s.r <= 1000 && s.r >= 0.001;
// Every split of the record set, one per (stock, date), oldest first. Map t -> [{ date, r }].
export function splitsOf(recs) {
  const m = new Map();
  const kept = [];
  for (const s of [...(recs && Array.isArray(recs.splits) ? recs.splits : []), ...(recs && Array.isArray(recs[VIEW_SPLITS]) ? recs[VIEW_SPLITS] : [])]) {
    if (!okSplit(s) || kept.some((k) => (k.t === s.t && k.date === s.date) || sameSplit(k, s))) continue;
    kept.push(s);
    if (!m.has(s.t)) m.set(s.t, []);
    m.get(s.t).push({ date: s.date, r: s.r });
  }
  for (const l of m.values()) l.sort((a, b) => (a.date < b.date ? -1 : 1));
  return m;
}
// The factor a record of stock t dated `date` is read with: the product of r over its splits dated after it (1: none).
// Dates on both sides are US trading dates (#117 RUNBOOK): a split's date is the first US trading day on the new count, and a
// record's is the trading date the user typed, so a record dated on the split day is already at the new count (factor 1).
export function splitFactor(splits, t, date) {
  const l = splits && splits.get(t);
  if (!l || !date) return 1;
  let f = 1;
  for (const s of l) if (date < s.date) f *= s.r;
  return f;
}
// The date a record counts from for splits: its own, or (an undated imported row) the day the portfolio was made.
export const splitDateOf = (r, recs) => (r && typeof r.date === "string" && r.date ? r.date
  : recs && typeof recs.createdAt === "string" ? recs.createdAt : "");
// A record's units at today's basis, exactly (u x f, not rounded), or null when they are not a safe whole number once rounded.
const scaled = (u, f) => (u == null ? null : f === 1 ? u : (okU(Math.round(u * f)) ? u * f : null));

// ---------------- counting a split's odd units (Track 2 audit 1.1) ----------------
// A record dated before a split is read x f. When that gives whole units (no split, a 4:1, a 1:10 of whole shares), the
// record counts exactly that. When it does not (DD's 1:3, UL's 8:9, HON's 1:2 on a 0.0001-share sale, a 금액으로 넣기 row:
// one old DD share is 3,333.33… units), the units have to be rounded, and two counts are possible:
//   each     every record rounded on its own (the only count before 2026-11-24, what main showed): 1 + 1 old DD shares are
//            3,333 + 3,333, so a sale of the 2 old shares (6,667) went below 0 and was refused;
//   running  the running total of the exact units, rounded after each record (a record counts for the change it makes):
//            3,333 + 3,334, and that sale leaves exactly 0.
// The two are the same whenever every record gives whole units, so records without such a split count exactly as before.
// One count is used for all of a stock's records (every screen, the ledger and the store's check, so the share count,
// 평균 단가 and gains always agree), position by position (review round 1): a position closes at a sale that takes either
// count to exactly 0 while that count never went below 0 in it (the count that closed it is used for it; each-record when
// both do). Everything held was sold, so the next record starts a new position from 0 (no 0.0001주 carried into a later
// purchase). The open position uses each-record while it stays at or above 0 (what main showed), else the running count.
// When that reading goes below 0, the running count over the whole history (no restart) is used if it stays at or above 0
// (#184 round 2: 4 old DD shares sold as 3.9998 and 0.0002, exactly 0, where each-record closes early and leaves 2/3 of a
// unit for the second sale), else main's own count (each-record over the whole history), so records saved and checked by
// main read back exactly as main read them. The store refuses only records that go below 0 by all three.
function count(list) {
  const main = list.map((e) => Math.round(e.x) || 0);        // || 0: never -0
  let m = 0, mainOk = true;
  for (const k of main) { m += k; if (m < 0) mainOk = false; }
  const out = new Array(list.length);
  let start = 0, x = 0, run = 0, each = 0, runOk = true, eachOk = true;
  const ru = [], eu = [];
  const take = (end, useEach) => { for (let i = start; i < end; i++) out[i] = useEach ? eu[i - start] : ru[i - start]; };
  for (let i = 0; i < list.length; i++) {
    x += list[i].x;
    const n = Math.round(x) || 0;
    ru.push(n - run);
    run = n;
    if (run < 0) runOk = false;
    eu.push(main[i]);
    each += main[i];
    if (each < 0) eachOk = false;
    if (list[i].kind === 2 && ((eachOk && each === 0) || (runOk && run === 0))) {
      take(i + 1, eachOk && each === 0);                       // a position closed: everything held was sold
      start = i + 1;
      x = 0; run = 0; each = 0; runOk = true; eachOk = true; ru.length = 0; eu.length = 0;
    }
  }
  let ok = true;
  if (start < list.length) { take(list.length, eachOk); if (!eachOk && !runOk) ok = false; }
  let use = out;
  if (!ok) {
    // the running count over the whole history, then main's
    const whole = [];
    let wx = 0, wr = 0, wholeOk = true;
    for (const e of list) { wx += e.x; const n = Math.round(wx) || 0; whole.push(n - wr); wr = n; if (wr < 0) wholeOk = false; }
    use = wholeOk ? whole : mainOk ? main : out;
  }
  list.forEach((e, i) => { e.u = use[i]; });
}

// The events of one record set ({ imported, purchases, sales }: a portfolio or one history entry), oldest first:
// undated imported rows first, then by date; on one date imported, then purchases, then sales.
// v19.6a: units at today's share basis (splits above), counted as count() says. -> [{ t, date, kind (0 imported · 1
// purchase · 2 sale), x (exact units), u (the whole units it counts for; a sale below 0), r (the record) }]
function events(recs, t) {
  const out = [];
  const sp = splitsOf(recs);
  const add = (list, kind, units) => {
    for (const r of Array.isArray(list) ? list : []) {
      if (!r || typeof r.t !== "string" || (t != null && r.t !== t)) continue;
      const u0 = units(r);
      if (u0 == null) continue;
      const x = scaled(u0, splitFactor(sp, r.t, splitDateOf(r, recs)));
      if (x == null) continue;
      out.push({ t: r.t, date: typeof r.date === "string" ? r.date : "", kind, x, u: 0, r });
    }
  };
  add(recs && recs.imported, 0, importedUnits);
  add(recs && recs.purchases, 1, (p) => (Number.isInteger(p.qty) && p.qty > 0 && okU(p.qty * UNIT) ? p.qty * UNIT : null));
  add(recs && recs.sales, 2, (s) => (okUnits(s.qty) ? -toUnits(s.qty) : null));
  out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.kind - b.kind));
  const byT = new Map();
  for (const e of out) { if (!byT.has(e.t)) byT.set(e.t, []); byT.get(e.t).push(e); }
  for (const l of byT.values()) count(l);
  return out;
}

// The events of stock t in a record set, as every count reads them (lots.js ledger: one count for the share count and the
// lots): [{ kind, date, u, x, r }] oldest first, u in whole units and x exact (a sale's below 0).
export const unitEvents = (recs, t) => events(recs, t).map(({ kind, date, u, x, r }) => ({ kind, date, u, x, r }));

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

// A sale of every share of t held now, dated `date`: its quantity in units on that date's share basis (a record dated before
// a split is read x r, so a sale before HON's 1:2 sells 2 old shares for today's 1), one that leaves exactly 0 by the
// count above (searched as below). null: nothing held, no date, or no such quantity (an odd ratio the other way:
// a 4:1 split cannot take 1 new share from a sale dated before it). edit.js 팔고 빼기 and records.js (a holding put in by
// amount, sold all at once) both use it.
export function sellAllUnits(recs, t, date) {
  if (!recs || typeof recs !== "object") return null;
  const evs = events(recs, t);
  // the count in use and the exact units of the open position (since the last sale that left exactly 0)
  let u = 0, open = 0;
  for (const e of evs) { u += e.u; open += e.x; if (e.kind === 2 && u === 0) open = 0; }
  if (!(u > 0) || typeof date !== "string" || !date) return null;
  const f = splitFactor(splitsOf(recs), t, date);
  const sales = Array.isArray(recs.sales) ? recs.sales : [];
  const tried = new Set();
  // the nearest to the count in use (what the screens show; main searched from it), and, for a date before a split, first
  // to the open position's exact units on that date's basis (3 old DD shares, not the 0.9999 new ones shown x 3); either
  // way the other one next (#184 review round 1, N1: the count in use can be more than 2 units from the exact one)
  // A quantity that leaves 0 but takes the holding below 0 on the way (a record after `date`) is the answer only when none
  // leaves 0 without that (#184 round 2, N1); the store's check refuses it then, as main's did.
  const near = [Math.round(u / f), Math.round(open / f)];
  let first = null;
  for (const q0 of f === 1 ? near : near.reverse()) {
    for (const d of [0, -1, 1, -2, 2]) {
      const q = q0 + d;
      if (!(q > 0) || tried.has(q)) continue;
      tried.add(q);
      const trial = { ...recs, sales: [...sales, { t, qty: q / UNIT, date }] };
      if ((heldUnits(trial).get(t) || 0) !== 0) continue;
      if (!belowZero(trial)) return q;
      if (first == null) first = q;
    }
  }
  return first;
}

// A holding of t left with part of a share by a split on `date` (Jack, 2026-11-27, answer 11: "팔았어요 accepts fractions (same unit as the
// spec, 1/10,000 share)"): the units held on that date (records dated on or before it), read on that date's share basis (today's basis ÷
// the splits after the date), are not a whole number of shares. A Korean 주식병합 or a 5:2 split leaves such a part (15 shares through a 1:10
// merge are 1.5); the company pays it out in cash, and the user records that as a sale of it. Korean records are whole shares otherwise.
export function fracHeld(recs, t, date) {
  if (!recs || typeof recs !== "object" || typeof t !== "string" || typeof date !== "string" || !date) return false;
  const u = heldUnits(recs, date).get(t) || 0;
  if (!(u > 0)) return false;
  const f = splitFactor(splitsOf(recs), t, date);
  const x = Math.round(u / f);
  return Number.isSafeInteger(x) && x % UNIT !== 0;
}

// Shares held now per stock with more than 0 shares (Map t -> quantity as a number, units / UNIT).
export function heldQty(recs, date = null) {
  const out = new Map();
  for (const [t, u] of heldUnits(recs, date)) if (u > 0) out.set(t, u / UNIT);
  return out;
}

// The first record at which main's own count (each record rounded on its own, over the whole history: held.js at 511fd6f)
// takes a holding below 0 (of stock t only, when given), or null. An older tab, or main's code after a revert, refuses a portfolio this finds below 0 and
// sets it aside: the app stores a data.json split with the records only when this stays null too (app.jsx, review round 1).
export function belowZeroEach(recs, t = null) {
  const m = new Map();
  for (const e of events(recs, t)) {
    const v = (m.get(e.t) || 0) + (Math.round(e.x) || 0);
    if (v < 0) return { t: e.t, date: e.date || null };
    m.set(e.t, v);
  }
  return null;
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
