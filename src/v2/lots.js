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
import { UNIT, toUnits, okUnits, importedUnits, splitsOf, splitFactor, splitDateOf, VIEW_SPLITS, okSplit } from "./held.js";

const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const pos = (x) => isNum(x) && x > 0;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const EPS_U = 1e-6;                                         // units: a float sum this close to 0 is 0

// The won-per-dollar rate a USD purchase was saved with: its own fx, else the portfolio's planFx (Part C: the same data.json
// rate, saved at the same moment). null: none.
export const purchaseRate = (p, planFx) => (p && p.ccy === "USD" ? (pos(p.fx) ? p.fx : pos(planFx) ? planFx : null) : 1);

// ---------------- data.json splits (A.6) ----------------
// data.json `splits`: [[code, date, ratio], ...] (last 3 years; ratio = new shares per old share). Malformed entries are left
// out (counted, so the screens' console says so). -> { list: [{ t, date, r }], bad }
export function dataSplits(data) {
  const raw = data && Array.isArray(data.splits) ? data.splits : [];
  const list = [];
  let bad = 0;
  for (const x of raw) {
    const s = Array.isArray(x) && x.length === 3 ? { t: x[0], date: x[1], r: x[2] } : null;
    if (s && okSplit(s)) list.push(s); else bad++;
  }
  return { list, bad };
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
// The splits a new record of stock t should be stored with (store.js splits): what the screens applied to that stock
// (the portfolio's stored ones and data.json's), so the stored records read back exactly as they were shown.
export function splitsToStore(deck, t) {
  const have = Array.isArray(deck && deck.splits) ? deck.splits : [];
  const add = (deck && Array.isArray(deck[VIEW_SPLITS]) ? deck[VIEW_SPLITS] : []).filter((s) => s.t === t && !have.some((y) => y && y.t === s.t && y.date === s.date));
  return add.length ? [...have, ...add.map((s) => ({ t: s.t, date: s.date, r: s.r }))] : null;
}
// The splits applied to stock t in this portfolio, oldest first: [{ date, r }] (the record sheet's lines, Appendix 1).
export function splitsFor(deck, t) {
  return splitsOf(deck).get(t) || [];
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
    let counted = false;
    for (const l of L.lots) {
      if (l.usdOnly) { if (!out.leftOut.includes(L.t)) out.leftOut.push(L.t); continue; }
      if (!pos(l.rate) || l.own == null || l.won == null) { if (!out.noRate.includes(L.t)) out.noRate.push(L.t); continue; }
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
// q: { pxOf(t) -> today's price in the stock's currency | null, fx: today's rate, absent: Set of codes missing from today's
// data }. The screen's basis is "평균 단가를 넣은 종목 기준" (Appendix 1): a stock is counted only when all its money is known,
// and then in all three rows and in the money put in, so the rows and 수익률 share one basis. Every stock left out is named,
// never counted as 0:
//   noAvg   a lot has no 평균 단가 (an imported row without one)
//   noFx    a USD record has no rate (a purchase from before Part C, or a record dated before 2016: the existing noFx line,
//           which also says 원금 and 수익률 were not computed, so cost is null then)
//   absent  a held stock missing from today's data (the existing missing-stock line)
//   noPrice a held stock in the data without a price today (no numbers at all: as deckMoney)
// Rows: held (가진 종목, unrealized), sold (판 종목, realized; a stock taken out keeps them, A.3), divs (받은 배당, after tax).
// cost (산 금액 전체): the won cost of every lot of the counted stocks, shares sold later included; a stock taken out counts
// with the cost its sales removed (its unsold shares left with their cost, A.3); dollar-only lots at today's rate ([Q11]).
// soldOut: sales whose gain could not be computed (the approved "수익을 계산하지 못한 판 기록 {n}건" line).
export function returnsOf(deck, q) {
  const out = { held: 0, sold: 0, divs: 0, cost: 0, n: 0, noAvg: [], noFx: [], absent: [], noPrice: [], soldOut: 0,
    heldAny: false, soldAny: false, divAny: false, usdOnly: false, ledgers: [] };
  const name = (k, t) => { if (!out[k].includes(t)) out[k].push(t); };
  for (const set of recordSets(deck)) {
    const L = ledger(set.recs, set.t, set.ctx);
    if (!set.history) out.ledgers.push(L);
    if (!L.lots.length && !L.sales.length && !L.divs.length && !L.putIn.unknown && !(L.putIn.won > 0)) continue;   // planned, never bought
    const usdRate = L.ccy === "USD" ? (pos(q.fx) ? q.fx : null) : 1;
    for (const s of L.sales) if (s.gain == null) out.soldOut += 1;
    let why = null;
    if (L.putIn.noRate || L.sales.some((s) => s.why === "noRate") || L.divs.some((d) => d.won == null)) why = "noFx";
    else if (L.putIn.unknown || L.sales.some((s) => s.gain == null)) why = "noAvg";
    let held = 0, usdOnly = false;
    if (!why && !set.history && L.held > 0) {
      if (q.absent && q.absent.has(set.t)) why = "absent";
      else {
        const v = openValue(L, q.pxOf(set.t), q.fx);
        if (v.value == null) why = L.ccy === "USD" && !pos(q.fx) ? "noFx" : "noPrice";
        else if (v.gain == null) why = v.unknown === "noRate" ? "noFx" : "noAvg";
        else { held = v.gain; usdOnly = v.usdOnly; }
      }
    }
    let cost = null;
    if (!why) {
      if (set.history) cost = L.removedWon == null ? null : L.removedWon + (L.removedUsdOwn > 0 ? (usdRate ? L.removedUsdOwn * usdRate : NaN) : 0);
      else cost = L.putIn.won + (L.putIn.usdOnlyOwn > 0 ? (usdRate ? L.putIn.usdOnlyOwn * usdRate : NaN) : 0);
      if (cost == null) why = "noAvg";
      else if (!isNum(cost)) why = "noFx";
    }
    if (why) { name(why, set.t); continue; }
    out.n += 1;
    out.cost += cost;
    if (!set.history && L.held > 0) { out.held += held; out.heldAny = true; }
    for (const s of L.sales) { out.sold += s.gain; out.soldAny = true; if (s.usdOnly) usdOnly = true; }
    for (const d of L.divs) { out.divs += d.won; out.divAny = true; }
    if (usdOnly) out.usdOnly = true;
  }
  if (out.noFx.length) out.cost = null;
  return out;
}

// ---------------- rounding rows so they add up on screen (A.5) ----------------
// Round each row to the unit the screen shows (만원 when every non-zero row is at least 1만원, else 원), then the total is
// the sum of the rounded rows: the screen adds up exactly. -> { unit, rows: [rounded], total }
export function roundRows(values) {
  const nz = values.filter((v) => isNum(v) && Math.round(v) !== 0);
  const unit = nz.length && nz.every((v) => Math.abs(v) >= 10000) ? 10000 : 1;
  const rows = values.map((v) => (isNum(v) ? Math.round(v / unit) * unit : null));
  const total = rows.reduce((a, v) => a + (v || 0), 0);
  return { unit, rows: rows.map((v) => (v === 0 ? 0 : v)), total: total === 0 ? 0 : total };
}
