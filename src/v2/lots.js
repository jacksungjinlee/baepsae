// ================= Lots: 평균 단가, gains, dividends and the exchange-rate split (v19.6a, Part A.4–A.6) =================
// Pure functions, no React and no Korean text (screens turn the results into copy from src/copy/v2.js).
// Spec: docs/tasks/v19.6-records-alerts-dark.md A.4 (gains), A.5 (내 수익, KOSPI comparison, 미국 종목 수익 어디서 왔나), A.6
// (splits). Unit tests: tests/test_v2_lots.py (run through Node).
//
// Moving average (이동평균, the 평균 단가 most Korean brokerage apps show). Each purchase is a lot with its won cost (its saved
// rate, else the portfolio's planFx, as track.purchaseWon does); each imported row (가진 종목 넣기) is a lot with its typed
// 평균 단가. A sale reduces EVERY open lot by the same fraction (sold ÷ held before the sale): quantity and cost carry
// forward. Quantities are in 1/10,000-share units (held.js) at today's share basis (splits, held.js): a record dated
// before a split is read as quantity x r, price / r, the same money.
//   realized gain (won) = sale qty x price x sale rate − the won cost the sale removed (Korea: rate 1)
//   a lot whose cost is known only in dollars (an imported US row: a 평균 단가 and no rate of its own, "dollar-only"):
//     its share of a sale gains (dollar proceeds − dollar cost removed) x the sale-date rate; held, it counts at today's
//     rate (dollar 평균 단가 x quantity x today's rate, [Q11]), so its won return equals its dollar return
//   a lot with no cost (an imported row without 평균 단가): no gain for a sale that touches it, never a guess
//   a USD purchase without any rate (records from before Part C): no won cost (the existing noFx line)
// Nothing here is rounded: the screens round once, and the rows they add up (내 수익) are rounded before they are added.
import { UNIT, toUnits, okUnits, importedUnits, splitsOf, splitFactor, splitDateOf, VIEW_SPLITS, okSplit, sameSplit, heldUnits } from "./held.js";
import { deckProblem, problemText } from "./store.js";

const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const pos = (x) => isNum(x) && x > 0;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const EPS_U = 1e-6;                                         // units: a float sum this close to 0 is 0

// The won-per-dollar rate a USD purchase was saved with: its own fx, else the portfolio's planFx (Part C: the same data.json
// rate, saved at the same moment, by 샀어요 before Part E saved a rate on each purchase). null: none. v19.6a: a record
// marked noFx (saved on purpose without a rate: dated before 2016) never takes planFx, which is another day's rate.
export const purchaseRate = (p, planFx) => (p && p.ccy === "USD" ? (pos(p.fx) ? p.fx : p.noFx !== true && pos(planFx) ? planFx : null) : 1);

// ---------------- data.json splits (A.6) ----------------
// Does a split of stock t fall after `date` and on or before today (a record dated `date` is read at another share basis
// than today's close)? Then today's close is never that record's default price: the price must be typed (round-3 review:
// a sale dated before AMD's 1:2 took today's post-split close for pre-split shares, "산 가격보다 +217.9%"). splits: the
// splits as the screens apply them ([{ t, date, r }]: a portfolio's stored ones and data.json's).
export function splitSince(splits, t, date, today = null) {
  return typeof date === "string" && !!date && (splits || []).some((s) => s && s.t === t && typeof s.date === "string" && s.date > date && (!today || s.date <= today));
}

// data.json `splits`: [[code, date, ratio], ...] (every US split since 2016-01-01, data.json splitsFrom; a row once published
// is carried forward for good; ratio = new shares per old share; the date is the first US trading day on the new count, so a
// record dated that day is already at the new count). Malformed entries are left out (counted, so the screens' console says
// so). A split an "out" row of splitsInfo.fixed names is left out too (the pipeline already drops it; this is the backstop).
// -> { list: [{ t, date, r }], bad, out }
export function dataSplits(data) {
  const raw = data && Array.isArray(data.splits) ? data.splits : [];
  const outs = outSplits(data);
  const list = [];
  let bad = 0, out = 0;
  for (const x of raw) {
    const s = Array.isArray(x) && x.length === 3 ? { t: x[0], date: x[1], r: x[2] } : null;
    if (!(s && okSplit(s))) { bad++; continue; }
    if (outs.some((o) => o.t === s.t && o.date === s.date)) { out++; continue; }
    list.push(s);
  }
  return { list, bad, out };
}
// data.json splitsInfo.fixed (#117): the pipeline's override rows [code, date, ratio | null, source]. A row with ratio null
// ("out") says that split was wrong: never apply it, and take it out of a portfolio that stored it (withoutOutSplits).
// -> [{ t, date }] (rows that are not [code, date, null, …] are not "out" rows and are ignored here)
const DAY = /^\d{4}-\d{2}-\d{2}$/;
export function outSplits(data) {
  const info = data && data.splitsInfo && typeof data.splitsInfo === "object" && !Array.isArray(data.splitsInfo) ? data.splitsInfo : null;
  const rows = info && Array.isArray(info.fixed) ? info.fixed : [];
  return rows.filter((x) => Array.isArray(x) && x.length >= 3 && typeof x[0] === "string" && x[0] && typeof x[1] === "string" && DAY.test(x[1]) && x[2] === null)
    .map((x) => ({ t: x[0], date: x[1] }));
}
// The store with every stored split an "out" row names taken out or moved, one split at a time (round-2 review A2: each
// stored split on its own, never all or nothing per portfolio). An "out" row names a wrong split by stock and date (#117
// RUNBOOK: a wrong date gets an "out" row for that date plus a row for the right one, at any distance), so only that exact
// stored split is touched. For each one, in this order:
//   removed  the records read back without it (store.deckProblem: no sale below 0) — taken out;
//   moved    they do not, but they do with data.json's split of the same stock and ratio stored in its place (the
//            corrected date: the nearest such row, A1) — the stored split moves there. That reads every record exactly
//            as data.json does: the moved split is one the screens already apply from data.json, so it is never counted
//            twice (held.sameSplit, and the stored one wins);
//   kept     neither (a record between the two dates needs the old one) — the stored split stays and, within the
//            pipeline's same-event window (held.SAME_SPLIT_DAYS), data.json's row for it is not applied on top
//            (sameSplit: the stored one wins). Said loudly; a same-ratio row further away is named in `also`, as it may be
//            the same event counted twice (a known limit, logged).
// No record is ever lost or refused. dataList: data.json's splits as read (dataSplits(data).list). A share count a removal
// or a move changes is reported (`held`: { t, before, after } in units, as the screens count them), for the console.
// -> { data (the same object when nothing changes), removed, moved, kept }: removed / kept = [{ id, t, date, r, why?, also? }],
//    moved = [{ id, t, date, r, to }]; removed and moved also carry held.
export function withoutOutSplits(data, outs, today = null, dataList = []) {
  const removed = [], moved = [], kept = [];
  if (!data || !Array.isArray(data.decks) || !outs || !outs.length) return { data, removed, moved, kept };
  let changed = false;
  const decks = data.decks.map((d) => {
    if (!d || !Array.isArray(d.splits) || !d.splits.length) return d;
    const hits = d.splits.filter((s) => s && outs.some((o) => o.t === s.t && o.date === s.date));
    if (!hits.length) return d;
    const { [VIEW_SPLITS]: _v, ...plain } = d;
    let next = plain;
    const withSplits = (deck, list) => { const out = { ...deck, splits: list }; if (!list.length) delete out.splits; return out; };
    // the share count the screens show: the stored splits with data.json's on top (withDataSplits)
    const view = (dataList || []).filter((x) => x && (!today || x.date <= today));
    const heldOf = (deck, t) => heldUnits({ ...deck, [VIEW_SPLITS]: view.filter((x) => x.t === t) }).get(t) || 0;
    for (const s of hits) {
      const rest = next.splits.filter((x) => x !== s);
      const trial = withSplits(next, rest);
      const before = heldOf(next, s.t);
      if (!deckProblem(trial, today)) {
        removed.push({ id: d.id, t: s.t, date: s.date, r: s.r, held: { t: s.t, before, after: heldOf(trial, s.t) } });
        next = trial;
        continue;
      }
      // the corrected date: data.json's splits of the same stock and ratio (never one an "out" row names, never after today),
      // nearest first, that the records read back with
      const day = (x) => Date.parse(x + "T00:00:00Z") / 86400000;
      const cands = (dataList || []).filter((x) => x && x.t === s.t && Math.abs(x.r - s.r) < 1e-9 && x.date !== s.date && (!today || x.date <= today)
        && !outs.some((o) => o.t === x.t && o.date === x.date) && !rest.some((y) => y && y.t === x.t && y.date === x.date))
        .sort((a, b) => Math.abs(day(a.date) - day(s.date)) - Math.abs(day(b.date) - day(s.date)) || (a.date < b.date ? -1 : 1));
      let done = false;
      for (const c of cands) {
        const t2 = withSplits(next, [...rest, { t: c.t, date: c.date, r: c.r }]);
        if (deckProblem(t2, today)) continue;
        moved.push({ id: d.id, t: s.t, date: s.date, r: s.r, to: c.date, held: { t: s.t, before, after: heldOf(t2, s.t) } });
        next = t2;
        done = true;
        break;
      }
      if (done) continue;
      const also = cands.filter((c) => !sameSplit(c, s)).map((c) => c.date);
      kept.push({ id: d.id, t: s.t, date: s.date, r: s.r, why: problemText(trial, deckProblem(trial, today)), ...(also.length ? { also } : {}) });
    }
    if (next === plain) return d;
    changed = true;
    return d[VIEW_SPLITS] ? { ...next, [VIEW_SPLITS]: d[VIEW_SPLITS] } : next;
  });
  return { data: changed ? { ...data, decks } : data, removed, moved, kept };
}

// The store with data.json's splits put on an in-memory copy of every portfolio that has records of a split stock (held.js
// VIEW_SPLITS: a Symbol key, never written). Portfolios without one are the same objects. A split dated after today is not
// applied (a pipeline that lists one early must not move anyone's shares).
export function withDataSplits(data, splits, today = null) {
  if (!data || !Array.isArray(data.decks)) return data;
  const byT = new Map();
  for (const s of splits || []) {
    if (today && s.date > today) continue;
    if (!byT.has(s.t)) byT.set(s.t, []);
    byT.get(s.t).push(s);
  }
  let changed = false;
  const decks = data.decks.map((d) => {
    if (!d || typeof d !== "object") return d;
    const mine = stocksOf(d).flatMap((t) => byT.get(t) || []);
    if (!mine.length) {
      // an earlier copy's splits (the data changed since): taken off, never carried on
      if (!d[VIEW_SPLITS]) return d;
      changed = true;
      const { [VIEW_SPLITS]: _v, ...rest } = d;
      return rest;
    }
    changed = true;
    return { ...d, [VIEW_SPLITS]: mine };
  });
  return changed ? { ...data, decks } : data;
}
// Every stock code a portfolio has a record or holding of (its history included).
export function stocksOf(d) {
  const out = new Set();
  for (const h of (d && d.holdings) || []) if (h && typeof h.t === "string") out.add(h.t);
  for (const k of ["purchases", "sales", "divs", "imported"]) for (const r of (d && d[k]) || []) if (r && typeof r.t === "string") out.add(r.t);
  for (const e of (d && d.history) || []) if (e && typeof e.t === "string") out.add(e.t);
  return [...out];
}
// The splits the store keeps for stock t (store.js splits): a split of data.json that the screens apply to t is stored as
// soon as a saved record of t is dated before it (a purchase, an imported row or a sale; a dividend too while the stock is
// held). Round-2 review: a buy-and-hold user keeps the split even if data.json later stops listing it (it lists 3 years);
// the store's own check then reads the records exactly as the screens do. A record dated on the split day is already at
// the new basis and needs nothing. The same split stored a few days apart is one split (held.sameSplit).
// deck: the portfolio as it is (with a new record, when one is being saved). -> the full list to store, or null.
export function splitsToStore(deck, t) {
  const have = Array.isArray(deck && deck.splits) ? deck.splits : [];
  const view = (deck && Array.isArray(deck[VIEW_SPLITS]) ? deck[VIEW_SPLITS] : [])
    .filter((s) => s.t === t && !have.some((y) => y && ((y.t === s.t && y.date === s.date) || sameSplit(y, s))));
  if (!view.length) return null;
  const dates = recordDates(deck, t, true);
  const need = view.filter((s) => dates.some((d) => d && d < s.date));
  return need.length ? [...have, ...need.map((s) => ({ t: s.t, date: s.date, r: s.r }))] : null;
}
// The dates of stock t's saved records in this portfolio and its history (an undated imported row: the day the portfolio was
// made). divs: also its dividends while the stock is held.
function recordDates(deck, t, divs = false) {
  const dates = [];
  const add = (list) => { for (const r of Array.isArray(list) ? list : list ? [list] : []) if (r && r.t === t) dates.push(splitDateOf(r, deck)); };
  for (const k of ["imported", "purchases", "sales"]) add(deck && deck[k]);
  for (const e of (deck && deck.history) || []) if (e && e.t === t) { add(e.imported); add(e.purchases); add(e.sales); }
  if (divs && deck && (heldUnits(deck).get(t) || 0) > 0) add(deck.divs);
  return dates;
}
// The store with every split its records need stored (splitsToStore for each stock with a data.json split), or the same
// object when nothing is missing. The app saves it once when data.json brings a split (round-2 review: without waiting for
// a new record). -> { data, added: [{ id, t, date, r }] }
export function withStoredSplits(data) {
  if (!data || !Array.isArray(data.decks)) return { data, added: [] };
  const added = [];
  let changed = false;
  const decks = data.decks.map((d) => {
    if (!d || !Array.isArray(d[VIEW_SPLITS]) || !d[VIEW_SPLITS].length) return d;
    let next = d;
    for (const t of [...new Set(d[VIEW_SPLITS].map((s) => s.t))]) {
      const sp = splitsToStore(next, t);
      if (!sp) continue;
      for (const s of sp.slice((next.splits || []).length)) added.push({ id: d.id, t: s.t, date: s.date, r: s.r });
      next = { ...next, splits: sp };
    }
    if (next !== d) changed = true;
    return next;
  });
  return { data: changed ? { ...data, decks } : data, added };
}
// The stored splits data.json does not list: said loudly once each (round-1 review). data.json lists every split since 2016
// and carries a published row forward for good (#117), so a stored split it does not list is one the pipeline took out (an
// "out" row: withoutOutSplits removes it where the records allow), or one stored from an older file. -> [{ id, t, date }]
export function storedNotInData(data, splits) {
  const out = [];
  for (const d of (data && data.decks) || []) for (const s of Array.isArray(d && d.splits) ? d.splits : []) {
    if (s && !(splits || []).some((x) => (x.t === s.t && x.date === s.date && x.r === s.r) || sameSplit(x, s))) out.push({ id: d.id, t: s.t, date: s.date, r: s.r });
  }
  return out;
}
// The splits that changed a record of stock t in this portfolio (a record dated before the split), oldest first:
// [{ date, r }] (the record sheet's lines, Appendix 1). A split after every record, or before every record, changed nothing.
export function splitsFor(deck, t) {
  const dates = [];
  const add = (list) => { for (const r of Array.isArray(list) ? list : list ? [list] : []) if (r && r.t === t) dates.push(splitDateOf(r, deck)); };
  for (const k of ["imported", "purchases", "sales"]) add(deck && deck[k]);
  for (const e of (deck && deck.history) || []) if (e && e.t === t) { add(e.imported); add(e.purchases); add(e.sales); }
  return (splitsOf(deck).get(t) || []).filter((s) => dates.some((d) => d && d < s.date));
}

// ---------------- one stock's ledger ----------------
// recs: a record set ({ imported?, purchases?, sales?, divs?, splits?, createdAt? }: a portfolio or one history entry; a
// history entry's imported row is one object, its splits and createdAt come from its portfolio: pass ctx).
// -> { t, ccy, lots: [open lots], sales: [per sale], divs: [per dividend], putIn: { won, own, unknown, usdOnlyOwn },
//      removedWon (won cost taken out by sales, null when any was unknown), held (units now), avgOwn }
// lot: { kind: "imp" | "buy", u (units, may be fractional after a sale), own (cost in the stock's currency, null = unknown),
//        won (won cost at the lot's rate, null = unknown), rate (won per unit of currency; 1 for KRW; null), usdOnly, date }
// sale: { rec, u, proceedsOwn, rate, proceedsWon, removedWon, gain, why: null | "noCost" | "noRate", usdOnly, over }
export function ledger(recs, t, ctx = {}) {
  const sp = splitsOf({ splits: ctx.splits != null ? ctx.splits : recs.splits, [VIEW_SPLITS]: ctx.view != null ? ctx.view : recs[VIEW_SPLITS] });
  const createdAt = ctx.createdAt != null ? ctx.createdAt : recs.createdAt;
  const planFx = ctx.planFx != null ? ctx.planFx : recs.planFx;
  const f = (r) => splitFactor(sp, t, splitDateOf(r, { createdAt }));
  const ev = [];
  const imp = Array.isArray(recs.imported) ? recs.imported : recs.imported ? [recs.imported] : [];
  for (const r of imp) {
    if (!r || r.t !== t) continue;
    const u0 = importedUnits(r);
    if (u0 == null) continue;
    ev.push({ kind: 0, date: typeof r.date === "string" ? r.date : "", r, u: u0 * f(r) });
  }
  for (const p of Array.isArray(recs.purchases) ? recs.purchases : []) {
    if (!p || p.t !== t || !(Number.isInteger(p.qty) && p.qty > 0)) continue;
    ev.push({ kind: 1, date: p.date || "", r: p, u: p.qty * UNIT * f(p) });
  }
  for (const s of Array.isArray(recs.sales) ? recs.sales : []) {
    if (!s || s.t !== t || !okUnits(s.qty)) continue;
    ev.push({ kind: 2, date: s.date || "", r: s, u: toUnits(s.qty) * f(s) });
  }
  ev.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.kind - b.kind));
  let ccy = null;
  const lots = [], sales = [];
  const putIn = { won: 0, own: 0, unknown: false, noRate: false, usdOnlyOwn: 0 };
  let removedWon = 0, removedUsdOwn = 0, removedKnown = true;
  for (const e of ev) {
    const r = e.r;
    ccy = ccy || r.ccy;
    if (e.kind === 0) {
      // the typed 평균 단가 is per share as typed: the money is qty-as-typed x avg (a split does not change it)
      const qtyTyped = importedUnits(r) / UNIT;
      const own = pos(r.avg) ? qtyTyped * r.avg : null;
      const usd = r.ccy === "USD";
      const lot = { kind: "imp", u: e.u, own, won: own != null && !usd ? own : null, rate: usd ? null : 1, usdOnly: usd && own != null, date: r.date || null };
      lots.push(lot);
      if (own == null) putIn.unknown = true;
      else if (usd) putIn.usdOnlyOwn += own;
      else { putIn.won += own; putIn.own += own; }
      continue;
    }
    if (e.kind === 1) {
      const own = r.qty * r.price;
      const rate = purchaseRate(r, planFx);
      const lot = { kind: "buy", u: e.u, own, won: rate ? own * rate : null, rate, usdOnly: false, date: r.date || null };
      lots.push(lot);
      if (lot.won == null) { putIn.unknown = true; putIn.noRate = true; } else { putIn.won += lot.won; putIn.own += own; }
      continue;
    }
    // a sale: every open lot shrinks by the same fraction
    const held = lots.reduce((a, l) => a + l.u, 0);
    const out = { rec: r, u: e.u, proceedsOwn: r.qty * r.price, rate: r.ccy === "USD" ? (pos(r.fx) ? r.fx : null) : 1,
      proceedsWon: null, removedWon: 0, removedUsdOwn: 0, removedOwn: 0, gain: null, why: null, usdOnly: false, over: false };
    out.proceedsWon = out.rate ? out.proceedsOwn * out.rate : null;
    if (!(held > EPS_U)) { out.over = true; out.why = "noCost"; sales.push(out); removedKnown = false; continue; }
    const frac = Math.min(1, e.u / held);
    if (e.u > held + 0.5) out.over = true;                 // more than held (the store refuses it; never counted)
    let gain = 0, why = null, lost = false;
    for (const l of lots) {
      if (!(l.u > EPS_U)) continue;
      const du = l.u * frac, share = du / e.u;              // this lot's part of the sale
      const dOwn = l.own != null ? l.own * frac : null, dWon = l.won != null ? l.won * frac : null;
      if (l.own == null) { why = why || "noCost"; lost = true; }
      else if (l.usdOnly) {
        out.usdOnly = true;
        out.removedUsdOwn += dOwn;
        if (out.rate == null) why = why || "noRate";
        else gain += (out.proceedsOwn * share - dOwn) * out.rate;
      } else if (dWon == null) { why = why || "noRate"; lost = true; }
      else {
        out.removedWon += dWon;
        if (out.proceedsWon == null) why = why || "noRate";
        else gain += out.proceedsWon * share - dWon;
      }
      if (dOwn != null && out.removedOwn != null) out.removedOwn += dOwn; else out.removedOwn = null;
      l.u -= du;
      if (l.own != null) l.own -= dOwn;
      if (l.won != null) l.won -= dWon;
    }
    if (out.over) why = why || "noCost";
    out.why = why;
    out.gain = why ? null : gain;
    if (lost) { out.removedWon = null; removedKnown = false; } else { removedWon += out.removedWon; removedUsdOwn += out.removedUsdOwn; }
    sales.push(out);
  }
  for (const l of lots) if (Math.abs(l.u) <= EPS_U) { l.u = 0; if (l.own != null) l.own = 0; if (l.won != null) l.won = 0; }
  const divs = [];
  for (const x of Array.isArray(recs.divs) ? recs.divs : []) {
    if (!x || x.t !== t || !pos(x.amount)) continue;
    ccy = ccy || x.ccy;
    const rate = x.ccy === "USD" ? (pos(x.fx) ? x.fx : null) : 1;
    divs.push({ rec: x, won: rate ? x.amount * rate : null });
  }
  const open = lots.filter((l) => l.u > 0);
  const heldU = open.reduce((a, l) => a + l.u, 0);
  const avgOwn = heldU > 0 && open.every((l) => l.own != null) ? open.reduce((a, l) => a + l.own, 0) / (heldU / UNIT) : null;
  return { t, ccy, lots: open, sales, divs, putIn, removedWon: removedKnown ? removedWon : null, removedUsdOwn, held: heldU, avgOwn };
}

// ---------------- today's value of the open lots ----------------
// px: today's price in the stock's own currency · fx: today's won-per-dollar rate (the same data.json rate the values use).
// -> { value, cost, gain, unknown: null | "noCost" | "noRate", usdOnly } — cost/gain null when any open lot's cost is
// unknown. value null without a price (or a USD stock without today's rate).
export function openValue(L, px, fx) {
  const usd = L.ccy === "USD";
  const rate = usd ? (pos(fx) ? fx : null) : 1;
  const qty = L.held / UNIT;
  const value = pos(px) && rate ? qty * px * rate : (qty === 0 ? 0 : null);
  let cost = 0, unknown = null, usdOnly = false;
  for (const l of L.lots) {
    if (l.own == null) { unknown = unknown || "noCost"; continue; }
    if (l.usdOnly) { usdOnly = true; if (rate) cost += l.own * rate; else unknown = unknown || "noRate"; continue; }
    if (l.won == null) { unknown = unknown || "noRate"; continue; }
    cost += l.won;
  }
  if (unknown) return { value, cost: null, gain: null, unknown, usdOnly };
  return { value, cost, gain: value != null ? value - cost : null, unknown: null, usdOnly };
}

// 미국 종목 수익, 어디서 왔나 (A.5): over the open lots that carry a rate (a purchase's own), 주가 = (today's price − the lot's
// price) x quantity x lot rate; 환율 = today's price x quantity x (today's rate − lot rate). They add up exactly to those
// lots' won gain. Dollar-only lots (no rate of their own) are left out and counted. -> { price, rate, gain, value, cost,
// own (remaining dollar cost of the counted lots), lotRate (one rate) | null, avgRate (weighted by remaining dollar cost),
// rates (distinct rates), leftOut: count of stocks with dollar-only lots, noRate: stocks with a lot without any rate }
export function fxSplit(ledgers, pxOf, fx) {
  const out = { price: 0, rate: 0, value: 0, cost: 0, own: 0, n: 0, rates: [], leftOut: [], noRate: [] };
  if (!pos(fx)) return null;
  for (const L of ledgers) {
    if (L.ccy !== "USD" || !(L.held > 0)) continue;
    const px = pxOf(L.t);
    if (!pos(px)) continue;
    // round-2 review: a stock with any lot that has no rate at all (a purchase saved before Part C without one, or marked
    // noFx) is left out whole, as 내 수익's three rows leave it out (the noFx line names it): never half of it here
    if (L.lots.some((l) => !l.usdOnly && (!pos(l.rate) || l.own == null || l.won == null))) { out.noRate.push(L.t); continue; }
    let counted = false;
    for (const l of L.lots) {
      if (l.usdOnly) { if (!out.leftOut.includes(L.t)) out.leftOut.push(L.t); continue; }
      const q = l.u / UNIT, lotPx = l.own / q;
      out.price += (px - lotPx) * q * l.rate;
      out.rate += px * q * (fx - l.rate);
      out.value += px * q * fx;
      out.cost += l.won;
      out.own += l.own;
      if (!out.rates.some((r) => Math.abs(r - l.rate) < 1e-9)) out.rates.push(l.rate);
      counted = true;
    }
    if (counted) out.n += 1;
  }
  if (!out.n) return { ...out, empty: true };
  out.gain = out.value - out.cost;
  out.avgRate = out.own > 0 ? out.cost / out.own : null;
  out.lotRate = out.rates.length === 1 ? out.rates[0] : null;
  return out;
}

// ---------------- KOSPI over the same money, with sales (A.5 [Q4]) ----------------
// Each lot's money buys KOSPI at the last close before its purchase date (as before); a sale sells the same fraction of
// that stock's KOSPI units at the last close before the sale date. Mine = (value now + sale money) / money put in − 1;
// KOSPI = (units still held x today's close + money from units sold) / the same money − 1. Dividends stay out of both.
// Stocks taken out (history entries) count with what was sold before they left: their unsold shares leave with their
// cost (A.3), so with their KOSPI units.
// sets: [{ recs, ctx, t, history }] · valueOf(t): today's won value of t's held shares (null: unknown).
// -> { ok: true, mine (null when a held stock's value is unknown), kospi, start, end, putIn } | { ok: false, why }
export function kospiMirror(sets, rows, end, valueOf, closeBefore) {
  let putIn = 0, now = 0, kNow = 0, kSold = 0, start = null, mineKnown = true;
  for (const { recs, ctx, t, history } of sets) {
    const L = ledgerWithEvents(recs, t, ctx);
    if (!L) continue;
    let units = 0;                                          // this stock's KOSPI units
    let held = 0;                                           // this stock's share units (to take fractions)
    let put = 0, soldMoney = 0;
    for (const e of L.events) {
      if (e.kind === 0) return { ok: false, why: "imported" };
      if (e.kind === 1) {
        const won = e.won;
        if (won == null) return { ok: false, why: "cost" };
        if (!DATE.test(e.date)) return { ok: false, why: "date" };
        const s = closeBefore(rows, e.date);
        if (!s) return { ok: false, why: "start" };
        units += won / s[1];
        held += e.u;
        put += won;
        if (start == null || e.date < start) start = e.date;
        continue;
      }
      if (!(held > EPS_U)) return { ok: false, why: "sale" };
      if (e.proceedsWon == null) return { ok: false, why: "cost" };
      if (!DATE.test(e.date)) return { ok: false, why: "date" };
      const s = closeBefore(rows, e.date);
      if (!s) return { ok: false, why: "start" };
      const frac = Math.min(1, e.u / held);
      const du = units * frac;
      kSold += du * s[1];
      units -= du;
      held -= e.u;
      soldMoney += e.proceedsWon;
    }
    if (history) {
      // what was not sold left with its cost: only the sold part's money stays in
      put = L.removedWon;
      if (put == null) return { ok: false, why: "cost" };
      if (L.removedUsdOwn > 0) return { ok: false, why: "imported" };
      units = 0;
    } else {
      const v = held > EPS_U ? valueOf(t) : 0;
      if (v == null) mineKnown = false; else now += v;
    }
    putIn += put;
    now += soldMoney;
    kNow += units * end[1];
  }
  if (!(putIn > 0)) return { ok: false, why: "cost" };
  return { ok: true, mine: mineKnown ? now / putIn - 1 : null, kospi: (kNow + kSold) / putIn - 1, start, end: end[0], putIn };
}
// The ledger with its events in order (purchases with their won cost, sales with their won proceeds) for kospiMirror.
function ledgerWithEvents(recs, t, ctx) {
  const L = ledger(recs, t, ctx);
  const sp = splitsOf({ splits: ctx && ctx.splits != null ? ctx.splits : recs.splits, [VIEW_SPLITS]: ctx && ctx.view != null ? ctx.view : recs[VIEW_SPLITS] });
  const createdAt = ctx && ctx.createdAt != null ? ctx.createdAt : recs.createdAt;
  const planFx = ctx && ctx.planFx != null ? ctx.planFx : recs.planFx;
  const f = (r) => splitFactor(sp, t, splitDateOf(r, { createdAt }));
  const events = [];
  const imp = Array.isArray(recs.imported) ? recs.imported : recs.imported ? [recs.imported] : [];
  for (const r of imp) if (r && r.t === t) events.push({ kind: 0, date: r.date || "" });
  for (const p of Array.isArray(recs.purchases) ? recs.purchases : []) {
    if (!p || p.t !== t || !(Number.isInteger(p.qty) && p.qty > 0)) continue;
    const rate = purchaseRate(p, planFx);
    events.push({ kind: 1, date: p.date || "", u: p.qty * UNIT * f(p), won: rate ? p.qty * p.price * rate : null });
  }
  for (const s of Array.isArray(recs.sales) ? recs.sales : []) {
    if (!s || s.t !== t || !okUnits(s.qty)) continue;
    const rate = s.ccy === "USD" ? (pos(s.fx) ? s.fx : null) : 1;
    events.push({ kind: 2, date: s.date || "", u: toUnits(s.qty) * f(s), proceedsWon: rate ? s.qty * s.price * rate : null });
  }
  events.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.kind - b.kind));
  return { ...L, events };
}

// ---------------- one portfolio: every stock, its history included ----------------
// The record sets of a portfolio: its own records per stock, then each history entry (A.3), with the portfolio's splits,
// createdAt and planFx. -> [{ recs, ctx, t, history: bool, entry }]
export function recordSets(deck) {
  const out = [];
  if (!deck) return out;
  const ctx = { splits: deck.splits || null, view: deck[VIEW_SPLITS] || null, createdAt: deck.createdAt || null, planFx: deck.planFx || null };
  const own = new Set();
  for (const k of ["imported", "purchases", "sales", "divs"]) for (const r of deck[k] || []) if (r && typeof r.t === "string") own.add(r.t);
  for (const h of deck.holdings || []) if (h && typeof h.t === "string") own.add(h.t);
  for (const t of own) out.push({ recs: deck, ctx, t, history: false });
  (deck.history || []).forEach((e, i) => {
    if (!e || typeof e.t !== "string") return;
    out.push({ recs: { imported: e.imported ? [e.imported] : [], purchases: e.purchases || [], sales: e.sales || [], divs: e.divs || [] }, ctx, t: e.t, history: true, entry: i });
  });
  return out;
}

// ---------------- 내 수익 (A.5) for one portfolio ----------------
// Two owner decisions wait (round-1 review B, C); each is one switch, the default is what ships now:
//   RETURNS_PARTIAL false (all or nothing per stock): a stock counts in all three rows and in the money put in, or not
//     at all (one basis for the rows and 수익률, "평균 단가를 넣은 종목 기준"). true: every part that is known counts
//     (dividends always, every computable sale gain, the unrealized part when its cost is known); 수익률 then only when no
//     stock was counted in part (partial: true says so, the screen leaves 수익률 out).
//   RETURNS_EXACT false (만원 rule, roundRows): rows in 만원 when every non-zero row is at least 1만원, else 원. true: always
//     exact 원 ("18만 8,000원" once app.manWon is approved), as on the board.
export const RETURNS_PARTIAL = false;
export const RETURNS_EXACT = false;
// q: { pxOf(t) -> today's price in the stock's currency | null, fx: today's rate, absent: Set of codes missing from today's
// data }. opts: { partial } (tests: both states of RETURNS_PARTIAL). Every stock left out (in full or in part) is named,
// never counted as 0:
//   noAvg   a lot has no 평균 단가 (an imported row without one), or a sale's gain could not be computed for that reason
//   noFx    a USD record has no rate (a purchase from before Part C, or a record dated before 2016: the existing noFx line,
//           which also says 원금 and 수익률 were not computed, so cost is null then)
//   absent  a held stock missing from today's data; noPrice a held stock in the data without a price today: both left out
//           and named on screen with the approved missing-stock line (round-1 review: never console only)
// Rows: held (가진 종목, unrealized), sold (판 종목, realized; a stock taken out keeps them, A.3), divs (받은 배당, after tax).
// cost (산 금액 전체): the won cost of every lot of the counted stocks, shares sold later included; a stock taken out counts
// with the cost its sales removed (its unsold shares left with their cost, A.3); dollar-only lots at today's rate ([Q11]).
// soldOut: sales whose gain could not be computed (the approved "수익을 계산하지 못한 판 기록 {n}건" line).
// usdOnly: a held dollar-only lot was counted at today's rate (the approved usdToday line); usdOnlySold: a counted sale took
// its gain from a dollar-only lot at the sale date's rate (the approved rec.usdOnly line).
export function returnsOf(deck, q, opts = {}) {
  const partial = typeof opts.partial === "boolean" ? opts.partial : RETURNS_PARTIAL;
  const out = { held: 0, sold: 0, divs: 0, cost: 0, n: 0, noAvg: [], noFx: [], absent: [], noPrice: [], soldOut: 0,
    heldAny: false, soldAny: false, divAny: false, usdOnly: false, usdOnlySold: false, partial: false, ledgers: [] };
  const name = (k, t) => { if (!out[k].includes(t)) out[k].push(t); };
  for (const set of recordSets(deck)) {
    const L = ledger(set.recs, set.t, set.ctx);
    if (!set.history) out.ledgers.push(L);
    if (!L.lots.length && !L.sales.length && !L.divs.length && !L.putIn.unknown && !(L.putIn.won > 0)) continue;   // planned, never bought
    const usdRate = L.ccy === "USD" ? (pos(q.fx) ? q.fx : null) : 1;
    for (const s of L.sales) if (s.gain == null) out.soldOut += 1;
    // what is known of this stock, part by part
    const lost = [];                                       // why a part is unknown: "noFx" · "noAvg" · "absent" · "noPrice"
    if (L.putIn.noRate || L.sales.some((s) => s.why === "noRate") || L.divs.some((d) => d.won == null)) lost.push("noFx");
    if (L.putIn.unknown && !L.putIn.noRate) lost.push("noAvg");
    if (L.sales.some((s) => s.gain == null && s.why !== "noRate")) lost.push("noAvg");
    let held = null, heldUsdOnly = false;
    if (!set.history && L.held > 0) {
      if (q.absent && q.absent.has(set.t)) lost.push("absent");
      else {
        const v = openValue(L, q.pxOf(set.t), q.fx);
        if (v.value == null) lost.push(L.ccy === "USD" && !pos(q.fx) ? "noFx" : "noPrice");
        else if (v.gain == null) lost.push(v.unknown === "noRate" ? "noFx" : "noAvg");
        else { held = v.gain; heldUsdOnly = v.usdOnly; }
      }
    }
    let cost = null;
    if (set.history) cost = L.removedWon == null ? null : L.removedWon + (L.removedUsdOwn > 0 ? (usdRate ? L.removedUsdOwn * usdRate : NaN) : 0);
    else cost = L.putIn.unknown ? null : L.putIn.won + (L.putIn.usdOnlyOwn > 0 ? (usdRate ? L.putIn.usdOnlyOwn * usdRate : NaN) : 0);
    if (cost != null && !isNum(cost)) { lost.push("noFx"); cost = null; }
    if (cost == null && !lost.length) lost.push("noAvg");
    for (const k of lost) name(k, set.t);
    if (lost.length && !partial) continue;                // all or nothing: the whole stock leaves (named above)
    if (lost.length) out.partial = true;
    // partial (or nothing lost): every known part counts
    if (cost != null && !lost.length) { out.cost += cost; out.n += 1; }
    if (held != null && !set.history && L.held > 0) { out.held += held; out.heldAny = true; if (heldUsdOnly) out.usdOnly = true; }
    for (const s of L.sales) if (s.gain != null) { out.sold += s.gain; out.soldAny = true; if (s.usdOnly) out.usdOnlySold = true; }
    for (const d of L.divs) if (d.won != null) { out.divs += d.won; out.divAny = true; }
  }
  if (out.noFx.length || out.partial) out.cost = null;     // 수익률 only on one basis
  return out;
}

// ---------------- rounding rows so they add up on screen (A.5) ----------------
// Round each row to the unit the screen shows (만원 when every non-zero row is at least 1만원, else 원; RETURNS_EXACT or
// opts.exact: always 원), then the total is the sum of the rounded rows: the screen adds up exactly. 수익률 is never taken
// from these rounded rows (15,000원 x 3 shows as 2만원 x 3; the return is 45,000 / cost, not 60,000 / cost).
// -> { unit, rows: [rounded], total }
export function roundRows(values, opts = {}) {
  const exact = typeof opts.exact === "boolean" ? opts.exact : RETURNS_EXACT;
  const nz = values.filter((v) => isNum(v) && Math.round(v) !== 0);
  const unit = !exact && nz.length && nz.every((v) => Math.abs(v) >= 10000) ? 10000 : 1;
  // half rounds away from zero on both sides (Math.round would take −15,000 to −1만 but +15,000 to +2만)
  const rnd = (x) => Math.sign(x) * Math.round(Math.abs(x));
  const rows = values.map((v) => (isNum(v) ? rnd(v / unit) * unit : null));
  const total = rows.reduce((a, v) => a + (v || 0), 0);
  return { unit, rows: rows.map((v) => (v === 0 ? 0 : v)), total: total === 0 ? 0 : total };
}
// 수익률 of 내 수익 from the exact sums (never the rounded rows), in %, or null without the money put in.
export const returnsPct = (r) => (r && r.cost != null && r.cost > 0 ? ((r.held + r.sold + r.divs) / r.cost) * 100 : null);
