// ================= 종목 바꾸기 · 빼기 · 담기: the maths and the store edits (v19.7a, docs/tasks/v19.7-portfolio-edit.md A–C) =================
// Pure functions, no React and no Korean text (editor.jsx turns the results into copy from src/copy/v2.js).
// Unit tests: tests/test_v197a_edit.py (run through Node).
//
// The edit screen works on a draft over the stored portfolio, never on the store itself:
//   draft = { over: { t: % }, adds: [{ t, nk, cls, ind, kind, s }], removed: [{ t, reason }], maxPct: whole % | null, last: t | null }
//   over      a target the user set (or that a share-out set), in % (a stored holding's own target is h.target × 100);
//   adds      담기: a stock to add when saved (a planned holding: no purchase), with its data row as it was picked;
//   removed   기록 없이 빼기 · 빼기 (no shares): taken out when saved, with the reason chip (thesis · rule · better · other) or null;
//   maxPct    최대 비중을 {y}%로 올리기 (D2), saved with the rest;
//   last      the holding the user just changed (합계를 100%로 맞추기 keeps its value);
//   touched   the user moved a target with − / + (only then does a save that also adds or takes out a stock log "목표 비중 바꿈").
// [B4] What saves when: anything that records money saves at once with the change it belongs to (팔고 빼기: the sale, the
// removal and the share-out of its target, sellAndRemove); everything else waits for 바꾼 내용 저장 (applyEdit). Nothing is
// written that store.js would refuse (both check the portfolio with store.deckProblem first).
//
// Targets: a stored target keeps its exact value (the plan's own float) until the user or a share-out sets it, and shows with
// one decimal when it is not a whole % (16.7%, never a 17% that would not add up). The steppers move to the next whole % and
// stop on the stored value on the way (− then + gives back exactly what was saved). Every share-out is proportional to the
// current targets, never pushes a holding above the portfolio's 한 종목 최대 비중 (settings.maxPct, [C2]) — a holding already
// above it (a 채권·금 cushion) is never pushed higher — and keeps every holding at 1% or more. With a whole-% anchor (or none) it
// is rounded to whole % by the largest remainder, so the targets add up to exactly 100; with an anchor the user left on a
// non-whole stored value, the others take the exact rest.
// [B1]/[C3] Saving a changed target: every planPx stays; the holding's plannedQty is recomputed from the new target at its
// own planPx and its band rule is regenerated from the new target (engine BANDS). Every other rule of every holding stays as
// it is. plannedQty is a whole number (store.js refuses any other, in this app and every earlier one), Math.round of
// target × the plan's amount ÷ the price. That rounding changes the plan's total, which used to move an untouched holding's
// band edges a little (round-1 review B3). Jack, 2026-11-13: every save of a target set also writes each holding's plan
// weight next to it (planW, withPlanW below), and the band rule reads that first (rules.planWeights), so an untouched
// holding's band does not move. An earlier app's tab ignores planW and keeps reading plannedQty as before. A holding added with
// 담기 gets planPx = today's official close and a plannedQty from its target, the rule book and reasons the build step gives
// a stock picked by name (꼭 담을 종목: kind "pinned", deckcalc.rulesFor with this portfolio's points), setAt today.
// Currency (round-1 Z1): a holding is in dollars when its data row is (pf.usdOf: ccy "USD") or it has a USD purchase, never
// because of cls alone (379800 KODEX 미국S&P500 is cls "us" but priced in won); a new holding stores the market of its
// currency as cls, so rules.planWeights (cls "us" = dollars) reads it the same way.
// Two tabs (round-1 S1): every save that sets targets stamps targetsTs (ms); store.unionDeck keeps the later target set whole.
import { BANDS, num, hasGroup } from "./engine.js";
import { usdOf, marketKey } from "./pf.js";
import { rulesFor } from "./deckcalc.js";
import { withoutHolding, deckProblem, problemText, versionFor, recordId, CHANGES_MAX } from "./store.js";
import { heldUnits, UNIT, VIEW_SPLITS, splitsOf, splitFactor } from "./held.js";

export const MIN_PCT = 1;                        // a holding stays at 1% or more (빼기 is how a holding leaves)
export const REASONS = ["thesis", "rule", "better", "other"];
export const CHANGE_KINDS = ["add", "remove", "targets"];
export { CHANGES_MAX };                           // the change log keeps the newest 200 (store.js checks the same number)
const SUM_TOL = 5e-4;                            // a sum within 0.0005%-points of 100 is 100 (the plan's float targets)
const TGT_TOL = 1e-9;                            // a target this close to the stored one did not change

export const emptyDraft = () => ({ over: {}, adds: [], removed: [], maxPct: null, last: null, touched: false });
const isInt = (x) => Number.isInteger(x);
const whole = (x) => Math.abs(x - Math.round(x)) < TGT_TOL;
const pctOf = (h) => (num(h && h.target) != null ? num(h.target) * 100 : 0);
// a row's stored % (null for a 담기 row): where its stepper stops on the way back
export const storedPct = (r) => (r && r.h ? pctOf(r.h) : null);

// The portfolio's 한 종목 최대 비중 as a whole %, or null (an imported or hand-made portfolio without one: no cap).
export function capOf(deck, draft = null) {
  const x = draft && draft.maxPct != null ? draft.maxPct : deck && deck.settings ? num(deck.settings.maxPct) : null;
  return x != null && x >= 1 && x <= 100 ? Math.floor(x) : null;
}
// [D2] With n holdings and a cap of x%, the targets can reach 100% only if n × x ≥ 100 (whole numbers). -> { low, y }:
// low = they cannot; y = 100 ÷ n rounded up (never above 100, never with n = 0: no line, no button).
export function capCheck(n, x) {
  if (!isInt(n) || n <= 0 || x == null) return { low: false, y: null };
  const y = Math.min(100, Math.floor((100 + n - 1) / n));
  return { low: n * x < 100, y };
}

// [D2] on the rows (round-1 S4: the spec's intent rather than its literal n × x, owner to confirm): the targets cannot reach
// 100% when every row at its own ceiling — the cap, or the row's own STORED % when that is above the cap (a 채권·금 cushion
// the share-out never pushes past what was saved, ceilingOf; round-2: stepping it 15 → 14 does not open D2) — adds up to
// less than 100. y as the spec says: 100 ÷ n rounded up (capCheck). -> { low, y }
export function d2Of(rows, cap) {
  const { y } = capCheck(rows.length, cap);
  if (y == null) return { low: false, y: null };
  const room = rows.reduce((a, r) => a + ceilingOf(r, cap), 0);
  return { low: room < 100 - SUM_TOL, y };
}

// ---------------- the edited list ----------------
// Stored holdings (minus pending removals) with their targets (the draft's first), then pending adds.
// -> [{ t, nk, h (stored holding) | null, add (draft add) | null, pct, cls }]
export function editRows(deck, draft) {
  const gone = new Set((draft.removed || []).map((r) => r.t));
  const out = [];
  for (const h of (deck && deck.holdings) || []) {
    if (!h || gone.has(h.t) || out.some((x) => x.t === h.t)) continue;
    const o = draft.over[h.t];
    out.push({ t: h.t, nk: h.nk, h, add: null, pct: num(o) != null ? o : pctOf(h), cls: h.cls || null });
  }
  for (const a of draft.adds || []) {
    if (out.some((x) => x.t === a.t)) continue;
    out.push({ t: a.t, nk: a.nk, h: null, add: a, pct: num(draft.over[a.t]) != null ? draft.over[a.t] : 0, cls: a.cls || null });
  }
  return out;
}
export const sumPct = (rows) => rows.reduce((a, r) => a + (num(r.pct) || 0), 0);
export const sumOk = (sum) => Math.abs(sum - 100) < SUM_TOL;
// The sum as shown: a whole number, or with as many decimals as it takes not to read "100" when it is not 100.
export function sumShown(sum) {
  if (sumOk(sum)) return { n: 100, d: 0 };
  for (const d of [0, 1, 2, 3]) {
    const r = Math.round(sum * 10 ** d) / 10 ** d;
    if (r !== 100) return { n: r, d };
  }
  return { n: sum, d: 3 };
}
// A target as shown: a whole % as it is; any other with one decimal (16.67 -> 16.7, 0.4 -> 0.4: never a rounded whole % that
// would not add up, round-1 S3).
export const pctShown = (p) => (whole(p) ? { n: Math.round(p), d: 0 } : { n: Math.round(p * 10) / 10, d: 1 });

// Is anything waiting for 바꾼 내용 저장?
export function pending(deck, draft) {
  if (!deck || !draft) return false;
  if ((draft.adds || []).length || (draft.removed || []).length) return true;
  if (draft.maxPct != null && draft.maxPct !== capOf(deck)) return true;
  return (deck.holdings || []).some((h) => h && num(draft.over[h.t]) != null && Math.abs(draft.over[h.t] - pctOf(h)) > TGT_TOL * 100);
}

// The stepper's limits for one row: min 1%, max the cap (when set) and what the other rows leave at 1% each. A holding stored
// above the cap (a 채권·금 cushion) may go back up to its own stored value, never higher (round-1 S3: − then + returns to it).
// byCap: the max is the cap's (the row then says why it cannot go higher, [C2]).
export function stepLimits(rows, t, cap, stored = null) {
  const n = rows.length;
  const room = 100 - (n - 1) * MIN_PCT;
  const top = cap != null ? Math.max(cap, num(stored) != null ? stored : 0) : 100;
  return { lo: MIN_PCT, hi: Math.min(top, room), byCap: cap != null && top <= room };
}
// One step: to the next whole % that way (a non-whole value goes to its floor or ceiling), stopping on the stored value when
// the step would pass it (so − then + gives back exactly what was saved), and on the limits. stored: the holding's stored
// %, or null (a 담기 row). -> the new % or null (already at the limit).
export function stepped(rows, t, dir, cap, stored = null) {
  const r = rows.find((x) => x.t === t);
  if (!r) return null;
  const { lo, hi } = stepLimits(rows, t, cap, stored);
  const cur = r.pct;
  if (dir > 0 ? cur >= hi - TGT_TOL : cur <= lo + TGT_TOL) return null;
  let next = whole(cur) ? Math.round(cur) + dir : dir > 0 ? Math.ceil(cur) : Math.floor(cur);
  if (num(stored) != null && (dir > 0 ? cur < stored - TGT_TOL && next > stored + TGT_TOL : cur > stored + TGT_TOL && next < stored - TGT_TOL)) next = stored;
  return dir > 0 ? Math.min(next, hi) : Math.max(next, lo);
}

// ---------------- share-outs ----------------
// Bounded proportional sharing: need %-points over items with weights w, lower bounds lo and upper bounds hi.
// -> Map t -> value (floats). Below the bounds' sums: every item at hi (or lo when need is below the lows).
function shareBounded(items, need) {
  const out = new Map();
  if (!items.length) return out;
  const loSum = items.reduce((a, x) => a + x.lo, 0), hiSum = items.reduce((a, x) => a + x.hi, 0);
  if (need <= loSum) { for (const x of items) out.set(x.t, x.lo); return out; }
  if (need >= hiSum) { for (const x of items) out.set(x.t, x.hi); return out; }
  const ws = items.map((x) => (x.w > 0 ? x.w : 0));
  const eq = !ws.some((w) => w > 0);
  const val = (x, i, k) => Math.min(x.hi, Math.max(x.lo, k * (eq ? 1 : ws[i])));
  const f = (k) => items.reduce((a, x, i) => a + val(x, i, k), 0);
  let a = 0, b = 1;
  while (f(b) < need && b < 1e12) b *= 2;
  for (let it = 0; it < 200; it++) { const m = (a + b) / 2; if (f(m) < need) a = m; else b = m; }
  items.forEach((x, i) => out.set(x.t, val(x, i, b)));
  // a row with no weight (a stored 0% or missing target) never grows by k: what the others cannot take goes to it, so a
  // reachable sum is always reached (round-1 nit)
  let left = need - [...out.values()].reduce((a, v) => a + v, 0);
  for (const x of items) {
    if (left <= TGT_TOL) break;
    const room = x.hi - out.get(x.t);
    if (room > 0) { const add = Math.min(room, left); out.set(x.t, out.get(x.t) + add); left -= add; }
  }
  return out;
}
// Whole % that add up to `need` (an integer), each within its bounds (integers): the largest remainder.
function wholeShares(items, vals, need) {
  const fl = items.map((x) => ({ t: x.t, v: Math.max(x.lo, Math.min(x.hi, Math.floor(vals.get(x.t) + 1e-9))), f: vals.get(x.t) - Math.floor(vals.get(x.t) + 1e-9), hi: x.hi, lo: x.lo }));
  let left = need - fl.reduce((a, x) => a + x.v, 0);
  const order = [...fl].sort((p, q) => q.f - p.f || (p.t < q.t ? -1 : 1));
  for (let moved = true; left !== 0 && moved;) {
    moved = false;
    for (const x of order) {
      if (left > 0 && x.v + 1 <= x.hi) { x.v += 1; left -= 1; moved = true; } else if (left < 0 && x.v - 1 >= x.lo) { x.v -= 1; left += 1; moved = true; }
      if (left === 0) break;
    }
  }
  return new Map(fl.map((x) => [x.t, x.v]));
}
// Share the targets out to 100% in proportion to their current values (합계를 100%로 맞추기, a removal's share-out, 담기, the
// D2 button). anchor: the row that keeps its value (the one just changed, or the stock being added); cap: whole % or null.
// -> Map t -> whole % for every row (the anchor too: it takes what the others cannot when they are all at their bounds).
// The sum is 100 whenever the cap allows it (capCheck); otherwise every row sits at its bound and the sum stays below 100.
// A row's ceiling: 100 without a cap; else the cap, or the row's STORED target when that is above it — the same top as the
// stepper's (stepLimits): a holding saved above the cap goes back up to it, never higher. Never the row's value in the draft
// (round-3: a draft value left above both, e.g. 55.26% against a saved 55% after 팔고 빼기 while other edits wait, would
// otherwise be kept as its own ceiling); a 담기 row's ceiling is the cap.
export const ceilingOf = (r, cap) => (cap == null ? 100 : Math.max(cap, num(storedPct(r)) || 0));
export function rebalance(rows, anchor, cap) {
  const a = anchor ? rows.find((r) => r.t === anchor) || null : null;
  const others = rows.filter((r) => r !== a);
  const hiOf = (r) => ceilingOf(r, cap);
  const items = others.map((r) => ({ t: r.t, w: r.pct, lo: MIN_PCT, hi: hiOf(r) }));
  let aPct = a ? a.pct : 0;
  if (a) aPct = Math.max(MIN_PCT, Math.min(hiOf(a), aPct));
  // the others first: they take 100 − the anchor, within their bounds; what they cannot take (or give) moves the anchor
  const loSum = items.reduce((s, x) => s + x.lo, 0), hiSum = items.reduce((s, x) => s + x.hi, 0);
  if (a) {
    const need = 100 - aPct;
    if (need < loSum) aPct = Math.max(MIN_PCT, 100 - loSum);
    else if (need > hiSum) aPct = Math.min(hiOf(a), 100 - hiSum);
  }
  const need = Math.max(0, 100 - aPct);
  const take = Math.min(need, hiSum);
  const vals = shareBounded(items, take);
  // whole % when the rest is a whole number: every bound rounded inward (a ceiling above the cap may not be whole)
  const ints = items.map((x) => ({ ...x, hi: Math.floor(x.hi + TGT_TOL) }));
  const intHi = ints.reduce((s, x) => s + x.hi, 0);
  const out = whole(take) && intHi >= Math.round(take) - TGT_TOL ? new Map(wholeShares(ints, vals, Math.round(take))) : new Map(vals);
  if (a) out.set(a.t, aPct);
  return out;
}
// The draft with these whole % set as targets.
const withOver = (draft, m, last = draft.last) => ({ ...draft, over: { ...draft.over, ...Object.fromEntries(m) }, last });

// 합계를 100%로 맞추기 (and the D2 button with its new cap): the draft shared out to 100%, keeping the row just changed.
export function fixDraft(deck, draft, cap = capOf(deck, draft)) {
  const rows = editRows(deck, draft);
  const keep = draft.last && rows.some((r) => r.t === draft.last) ? draft.last : null;
  return withOver(draft, rebalance(rows, keep, cap));
}
// [D2] 최대 비중을 {y}%로 올리기: the new cap (pending), then the share-out under it.
export function raiseDraft(deck, draft) {
  const rows = editRows(deck, draft);
  const { y } = capCheck(rows.length, capOf(deck, draft));
  if (y == null) return draft;
  return fixDraft(deck, { ...draft, maxPct: y }, y);
}
// A stepper tap: the row's new %, the row remembered as the one just changed.
export const stepDraft = (draft, t, pct) => ({ ...draft, over: { ...draft.over, [t]: pct }, last: t, touched: true });
// 기록 없이 빼기 · 빼기 (no shares): taken out when saved; its target is shared out to the rest now (the user can adjust).
export function removeDraft(deck, draft, t, reason) {
  const rows = editRows(deck, draft);
  if (rows.length <= 1 || !rows.some((r) => r.t === t)) return draft;
  const isAdd = (draft.adds || []).some((a) => a.t === t);
  const over = { ...draft.over };
  delete over[t];
  const next = isAdd ? { ...draft, adds: draft.adds.filter((a) => a.t !== t), over }
    : { ...draft, removed: [...(draft.removed || []).filter((r) => r.t !== t), { t, reason: REASONS.includes(reason) ? reason : null }], over };
  if (next.last === t) next.last = null;
  return withOver(next, rebalance(editRows(deck, next), null, capOf(deck, next)), next.last);
}
// 담기: the stock with its target (whole %), the others scaled to the rest in proportion. add: { t, nk, cls, ind, kind, s }.
export function addDraft(deck, draft, add, pct) {
  const base = { ...draft, adds: [...(draft.adds || []).filter((a) => a.t !== add.t), add], over: { ...draft.over, [add.t]: pct } };
  return withOver(base, rebalance(editRows(deck, base), add.t, capOf(deck, base)), add.t);
}
// What 담기 shows before it is tapped: the default share (100 ÷ (holdings + 1), rounded, within the cap) and the list after.
export function addDefault(n, cap) {
  const p = Math.round(100 / (n + 1));
  return Math.max(MIN_PCT, cap != null ? Math.min(cap, p) : p);
}
export function addPreview(deck, draft, add, pct) {
  const d = addDraft(deck, draft, add, pct);
  return editRows(deck, d);
}

// ---------------- 업종 비중 ----------------
// The bar: target weights by industry group (the v17.5.1 groups 업종별 등락 uses: data.json ind / indName), largest first,
// the holdings without a group last in one part. byT: today's data rows; names: ind -> indName from the whole data.
// -> [{ key, name | null (no group), pct }]
export function indNames(stocks) {
  const m = new Map();
  for (const s of stocks || []) if (s && hasGroup(s) && s.indName && !m.has(s.ind)) m.set(s.ind, s.indName);
  return m;
}
export const CUSHION = "cushion";                 // the bar's part (and a row's line) for 안전자산 (채권·금) holdings
const isCushion = (row) => !!(row && row.h && row.h.kind === "cushion");
export function groupOf(row, byT) {
  if (isCushion(row)) return CUSHION;
  const s = byT && byT.get(row.t);
  if (s && hasGroup(s)) return s.ind;
  const own = row.h ? row.h.ind : row.add ? row.add.ind : null;
  return typeof own === "string" && own ? own : null;
}
export function indBar(rows, byT, names) {
  const by = new Map();
  let none = 0;
  for (const r of rows) {
    const g = groupOf(r, byT);
    if (g === CUSHION) { const x = by.get(CUSHION) || { key: CUSHION, name: null, cushion: true, pct: 0 }; x.pct += r.pct; by.set(CUSHION, x); continue; }
    const name = g ? (byT && byT.get(r.t) && byT.get(r.t).ind === g ? byT.get(r.t).indName : null) || names.get(g) || null : null;
    if (!g || !name) { none += r.pct; continue; }
    const x = by.get(g) || { key: g, name, pct: 0 };
    x.pct += r.pct;
    by.set(g, x);
  }
  const out = [...by.values()].sort((a, b) => b.pct - a.pct || (a.key < b.key ? -1 : 1));
  if (none > 0) out.push({ key: "", name: null, pct: none });
  return out;
}
// A holding's industry for its row ("지금 {qty}주 · {industry}"): the data's group name, CUSHION for a 안전자산 holding (the
// screen says 안전자산 (채권·금), the build's own label), or null (업종 정보 없음).
export function indOf(row, byT, names) {
  const g = groupOf(row, byT);
  if (!g || g === CUSHION) return g;
  const s = byT && byT.get(row.t);
  return (s && s.ind === g && s.indName) || names.get(g) || null;
}

// Shares held now (held.js: imported + purchases − sales), as a number of shares.
export const heldShares = (deck, t) => (heldUnits(deck).get(t) || 0) / UNIT;
// 팔고 빼기's locked quantity for a sale dated `date` (round-2 B-2): every share held, counted on that date's share basis —
// a record dated before a split is read × r (held.js splitFactor, stored splits and data.json's), so a sale before HON's
// 1:2 of 2026-06-29 sells 2 old shares for today's 1, and one before NVDA's 10:1 sells 1/10 of today's count. The quantity
// is the one whose units, read the way held.js reads a sale, are exactly the holding (the nearest unit that does). null:
// nothing held, no date, or no such quantity (an odd ratio): 팔고 빼기 then refuses rather than leave a share behind.
export function sellAllQty(deck, t, date) {
  const u = heldUnits(deck).get(t) || 0;
  if (!(u > 0) || typeof date !== "string" || !date) return null;
  const f = splitFactor(splitsOf(deck), t, date);
  const q0 = Math.round(u / f);
  for (const d of [0, -1, 1, -2, 2]) {
    const q = q0 + d;
    if (q > 0 && Math.round(-q * f) === -u) return q / UNIT;
  }
  return null;
}

// ---------------- saving ----------------
// The plan's whole amount in won (targets are shares of it): settings.amountMan, else what the plan's own numbers imply
// (Σ plannedQty × planPx × rate ÷ Σ target over the holdings that have both). null when neither is known.
export function planAmount(deck) {
  const m = num(deck && deck.settings && deck.settings.amountMan);
  if (m > 0) return m * 10000;
  let v = 0, w = 0;
  for (const h of (deck && deck.holdings) || []) {
    const q = h && h.plannedQty, px = num(h && h.planPx), t = num(h && h.target);
    const fx = usdHolding(deck, h, null) ? num(deck.planFx) : 1;
    if (Number.isInteger(q) && px > 0 && t > 0 && fx > 0) { v += q * px * fx; w += t; }
  }
  return v > 0 && w > 0 ? v / w : null;
}
// Is a holding in dollars? Its data row's currency when the data has it (pf.usdOf, the rule pf.js and 가진 종목 넣기 use), else
// a USD purchase of it, else its stored market (cls) as rules.planWeights reads it. s: today's data row or null.
const usdHolding = (deck, h, s = null) => (s ? usdOf(s) : ((deck && deck.purchases) || []).some((p) => p && p.t === h.t && p.ccy === "USD") || h.cls === "us");
// A changed target's plannedQty at the holding's own planPx (US at the plan's rate): null when it cannot be computed (no
// planPx, no amount, a dollar holding without a plan rate) — then the holding goes without one, and rules.planWeights
// gives it no gap of its own (its band is the new target's, the strict direction).
export function plannedFor(deck, h, target, fxToday = null, s = null) {
  const A = planAmount(deck), px = num(h.planPx);
  const fx = usdHolding(deck, h, s) ? num(deck.planFx) || num(fxToday) : 1;
  if (!(A > 0) || !(px > 0) || !(fx > 0) || !(target > 0)) return null;
  const q = Math.round((target * A) / (px * fx));
  return Number.isSafeInteger(q) && q >= 0 ? q : null;
}
export const bandRule = (target) => ({ id: "band", kind: "band", check: "checked", target, bands: BANDS.map((b) => b * target) });

// ---------------- the plan's weight stored next to each holding (planW; Jack, 2026-11-13) ----------------
// Each holding's weight in the plan, as rules.planWeights reads it today: the stored planW when every holding has one, else
// the plan's own value (plannedQty × planPx, a dollar holding at the plan's rate: the same product, with the same test for
// dollars, as rules.planWeights). -> Map t -> number, or { why } when a holding's cannot be known (no plannedQty, no planPx,
// a dollar holding without the plan's rate): nothing is stored then and the bands keep reading plannedQty.
const okW = (x) => typeof x === "number" && Number.isFinite(x) && x >= 0;
export function planBase(deck) {
  const hs = ((deck && deck.holdings) || []).filter((h) => h && typeof h.t === "string");
  if (!hs.length) return { why: "no holdings" };
  if (hs.every((h) => okW(h.planW))) return new Map(hs.map((h) => [h.t, h.planW]));
  const fx = num(deck.planFx);
  const out = new Map();
  for (const h of hs) {
    const q = h.plannedQty, px = num(h.planPx), usd = usdHolding(deck, h, null);
    if (!Number.isInteger(q) || q < 0) return { why: `${h.t} has no planned share count` };
    if (!(px > 0)) return { why: `${h.t} has no plan price` };
    if (usd && !(fx > 0)) return { why: `${h.t} is in dollars and the plan has no exchange rate` };
    out.set(h.t, q * px * (usd ? fx : 1));
  }
  return out;
}
// `total` shared out in proportion to the weights ws (all 0 or more, not all 0): whole numbers by the largest remainder when
// total is a whole number (a plan in won: every sum then stays exact), else floats with the last one taking the exact rest.
function shareTotal(total, ws) {
  const sum = ws.reduce((a, w) => a + w, 0);
  const raw = ws.map((w) => (total * w) / sum);
  if (Number.isSafeInteger(total)) {
    const out = raw.map((v) => Math.floor(v + 1e-9));
    let left = total - out.reduce((a, v) => a + v, 0);
    const order = raw.map((v, i) => [v - Math.floor(v + 1e-9), i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    for (let j = 0; left !== 0; j = (j + 1) % order.length) {
      const i = order[j][1];
      if (left > 0) { out[i] += 1; left -= 1; } else if (out[i] > 0) { out[i] -= 1; left += 1; }
    }
    return out;
  }
  const head = raw.slice(0, -1);
  return [...head, Math.max(0, total - head.reduce((a, v) => a + v, 0))];
}
// The holdings a save of a target set leaves, each with its planW. before: the portfolio as it was before the edit (a stock
// the edit took out is still in it); holdings: the list after the edit; changed: the codes whose target the edit set
// (retargeted or added). A holding that was there and was not changed keeps its weight (planBase: its stored planW, or its
// plan value the first time), bit for bit; the changed ones share what is left of the plan's total — what they had, plus a
// taken-out stock's — in proportion to their new targets. So the total never changes and an untouched holding's share of
// it, the band rule's planW, is the same number after the save. Changed stocks that had no weight between them (0 planned
// shares each) share 0. When the weights cannot be known (planBase) or shared, no holding keeps a planW (never some with and
// some without) and the console says why.
export function withPlanW(before, holdings, changed) {
  const strip = (why) => {
    console.warn(`[v2] ${before && before.id}: plan weights (planW) not stored (${why}); the weight bands keep reading the planned share counts, `
      + "so a stock whose target was not changed can see its band edges move a little");
    return holdings.map((h) => { if (!h || h.planW == null) return h; const { planW: _w, ...rest } = h; return rest; });
  };
  const base = planBase(before);
  if (!(base instanceof Map)) return strip(base.why);
  const total = [...base.values()].reduce((a, b) => a + b, 0);
  const keeps = (h) => !!h && base.has(h.t) && !changed.has(h.t);
  const move = holdings.filter((h) => h && !keeps(h));
  const left = total - holdings.filter(keeps).reduce((a, h) => a + base.get(h.t), 0);
  const rest = left < 0 && left > -1e-9 * total ? 0 : left;                  // a dollar plan's sums are floats: the last bits of 0
  const ws = move.map((h) => (num(h.target) > 0 ? h.target : 0));
  if (!(total > 0)) return strip("the plan's total is 0");
  if (move.length && (rest < 0 || !ws.some((w) => w > 0))) return strip("the changed stocks' share of the plan could not be worked out");
  const shares = move.length ? shareTotal(rest, ws) : [];
  if (shares.some((v) => !okW(v))) return strip("a share could not be computed");
  const got = new Map(move.map((h, i) => [h.t, shares[i]]));
  return holdings.map((h) => (h ? { ...h, planW: keeps(h) ? base.get(h.t) : got.get(h.t) } : h));
}
// A holding with a new target: its band rule regenerated (in place, or added when it had none), its plannedQty recomputed.
export function retarget(deck, h, target, fxToday = null, s = null) {
  const rules = Array.isArray(h.rules) ? h.rules : [];
  const i = rules.findIndex((r) => r && r.id === "band");
  const nr = i >= 0 ? rules.map((r, j) => (j === i ? bandRule(target) : r)) : [...rules, bandRule(target)];
  const q = plannedFor(deck, h, target, fxToday, s);
  const { plannedQty: _q, ...rest } = h;
  return { ...rest, target, rules: nr, ...(q != null ? { plannedQty: q } : {}) };
}
// A new planned holding (담기): the rules the build step would give it, planPx today's close, plannedQty from its target.
// a: the draft add { t, nk, cls, ind, kind, s }; load: today's data (coByT for the rule book).
export function newHolding(deck, a, target, load, today, ts) {
  const st = { points: (deck.settings && deck.settings.points) || {} };
  // today's row when the data on screen has it (a newer publish may have come in since the sheet was opened), else the
  // row as it was picked
  const s = (load && load.byT && typeof load.byT.get === "function" && load.byT.get(a.t)) || a.s;
  // as the build step writes a stock picked by name (꼭 담을 종목): kind "pinned", its reason, its rule book
  const rules = rulesFor(load, { s, kind: "pinned", targetW: target }, st);
  const cls = s.cls === "kr" || s.cls === "us" ? marketKey(s) : a.cls || null;
  const h = { t: a.t, nk: s.nk || a.nk, ...(cls ? { cls } : {}), ind: hasGroup(s) ? s.ind : null, kind: "pinned", target, reasons: [{ code: "pinned" }],
    setAt: today, ts, ...(num(s.price) > 0 ? { planPx: s.price } : {}), rules };
  const q = plannedFor(deck, h, target, load && load.data ? load.data.fx : null, s);
  return q != null ? { ...h, plannedQty: q } : h;
}
// The change log (Part A): { id, at, kind, t?, nk?, reason? }, the newest CHANGES_MAX kept. Each entry carries a random id, so
// two tabs' entries of the same day and kind stay two when the copies merge.
export function withChanges(deck, entries) {
  if (!entries.length) return deck;
  const all = [...(Array.isArray(deck.changes) ? deck.changes : []), ...entries.map((c) => (c.id ? c : { id: recordId(), ...c }))];
  return { ...deck, changes: all.slice(Math.max(0, all.length - CHANGES_MAX)) };
}
const stripView = (d) => { if (!d || !d[VIEW_SPLITS]) return d; const { [VIEW_SPLITS]: _v, ...rest } = d; return rest; };
// the store with this portfolio in place, tagged with the version its parts need (a removal can bring the first history entry)
const putDeck = (data, deck) => { const out = { ...data, decks: data.decks.map((d) => (d && d.id === deck.id ? deck : d)) }; return { ...out, v: versionFor(out) }; };
const findDeck = (data, id) => (data && Array.isArray(data.decks) ? data.decks.find((d) => d && d.id === id) || null : null);

// Take stock t out (withoutHolding: its sale and dividend records move into history, with the reason), logged.
function takeOut(data, deckId, t, reason, today, ts) {
  const before = findDeck(data, deckId);
  const h = before && before.holdings.find((x) => x && x.t === t);
  if (!h) return null;
  const why = REASONS.includes(reason) ? reason : null;
  const next = withoutHolding(data, deckId, t, today, ts, why);
  if (!next) return null;
  return { data: next, change: { at: today, kind: "remove", t, nk: h.nk, ...(why ? { reason: why } : {}) } };
}
// 포트폴리오에서 빼기 outside 종목 바꾸기 (v19.6a's 포트폴리오에서도 뺄까요? → 빼기, and a stock missing from today's data): the same
// store.withoutHolding, logged in the change log too ("{date} · {name} 뺌"). -> the store, or null (nothing to remove).
export function withRemoval(data, deckId, t, today, ts) {
  const x = takeOut(data, deckId, t, null, today, ts);
  if (!x) return null;
  return putDeck(x.data, withChanges(findDeck(x.data, deckId), [x.change]));
}
// Every stored holding of deck whose target in `pcts` (Map t -> %) differs from its own: retargeted.
// -> { deck, changed (how many), ts (their codes, for withPlanW) }
function applyTargets(deck, pcts, fxToday, byT = null) {
  const ts = new Set();
  const holdings = deck.holdings.map((h) => {
    if (!h || !pcts.has(h.t)) return h;
    const p = pcts.get(h.t);
    if (!(num(p) > 0) || Math.abs(p - pctOf(h)) <= TGT_TOL * 100) return h;
    ts.add(h.t);
    return retarget(deck, h, p / 100, fxToday, (byT && typeof byT.get === "function" && byT.get(h.t)) || null);
  });
  return { deck: { ...deck, holdings }, changed: ts.size, ts };
}
const check = (deck, today) => {
  const p = deckProblem(stripView(deck), today);
  if (p) console.warn("[v2] edit not saved: " + problemText(deck, p));
  return !p;
};

// 바꾼 내용 저장: every pending edit of the draft in one store. env: { load, today, ts }.
// -> { ok: true, data } | { ok: false, why: "gone" (the portfolio is not there) | "sum" (not 100%) | "store" (store.js refused) }
export function applyEdit(data, deckId, draft, env) {
  const { load, today, ts } = env;
  let deck = findDeck(data, deckId);
  if (!deck) return { ok: false, why: "gone" };
  const rows = editRows(deck, draft);
  if (!rows.length) return { ok: false, why: "last" };                       // a portfolio keeps at least one stock
  if (!sumOk(sumPct(rows))) return { ok: false, why: "sum" };
  const pcts = new Map(rows.map((r) => [r.t, r.pct]));
  const changes = [];
  const before = deck;                                                       // for withPlanW: the plan as it was, taken-out stocks included
  let cur = data;
  for (const r of draft.removed || []) {
    const x = takeOut(cur, deckId, r.t, r.reason, today, ts);
    if (!x) return { ok: false, why: "gone" };
    cur = x.data;
    changes.push(x.change);
  }
  deck = findDeck(cur, deckId);
  const fx = load && load.data ? load.data.fx : null;
  const tg = applyTargets(deck, pcts, fx, load && load.byT);
  deck = tg.deck;
  // one line per stock added or taken out; "목표 비중 바꿈" only for a target the user moved, or a save that only moved targets
  // (a removal's or an add's own share-out is part of its line, round-1 nit)
  const moved = tg.changed > 0 && (draft.touched || (!(draft.removed || []).length && !(draft.adds || []).length));
  if (moved) changes.push({ at: today, kind: "targets" });
  for (const a of draft.adds || []) {
    if (deck.holdings.some((h) => h && h.t === a.t)) return { ok: false, why: "gone" };
    const p = pcts.get(a.t);
    if (!(num(p) > 0)) return { ok: false, why: "sum" };
    deck = { ...deck, holdings: [...deck.holdings, newHolding(deck, a, p / 100, load, today, ts)] };
    changes.push({ at: today, kind: "add", t: a.t, nk: a.nk });
  }
  // the plan's weights follow the target set (Jack, 2026-11-13): an untouched holding keeps its own
  if (tg.changed || (draft.adds || []).length || (draft.removed || []).length) {
    deck = { ...deck, holdings: withPlanW(before, deck.holdings, new Set([...tg.ts, ...(draft.adds || []).map((a) => a.t)])) };
  }
  const capMoved = draft.maxPct != null && draft.maxPct !== capOf(deck);
  if (capMoved) deck = { ...deck, settings: { ...(deck.settings || {}), maxPct: draft.maxPct } };
  if (!changes.length && capMoved) changes.push({ at: today, kind: "targets" });
  // the target set's time (two tabs: store.unionDeck keeps the later set whole, round-1 S1)
  if (tg.changed || capMoved || changes.length) deck = { ...deck, targetsTs: ts };
  deck = withChanges(deck, changes);
  if (!check(deck, today)) return { ok: false, why: "store" };
  return { ok: true, data: putDeck(cur, deck) };
}

// 팔고 빼기 [B4]: the store after the sale (records.withRecord), then the stock taken out with its reason and its stored
// target shared out to the stored holdings left (within the cap, or the raised cap y of D2, saved with them), logged —
// one write. opts: { reason, raise (y | null), load, today, ts }. -> { ok: true, data } | { ok: false, why }
// Refused: "partial" (round-1 B2: the sale did not sell every held share; the user who sells part uses 팔았어요) · "last" (it
// was the stored portfolio's only stock, round-1 B1) · "sum" (the stored holdings left cannot reach 100% under the cap: D2
// first, round-1 B1) · "gone" · "store".
export function sellAndRemove(afterSale, deckId, t, opts) {
  const { reason, raise = null, load, today, ts } = opts;
  // every refusal is said in the console with its reason (CLAUDE.md: no silent failure; the screen keeps the form)
  const no = (why, more = "") => { console.warn(`[v2] ${deckId}: sell and remove ${t} refused (${why})${more}; nothing saved`); return { ok: false, why }; };
  const before = findDeck(afterSale, deckId);
  if (!before) return no("gone");
  const left = heldUnits(before).get(t) || 0;
  if (left > 0) return no("partial", `: ${left / UNIT} shares would stay after the sale`);
  if (!(before.holdings || []).some((h) => h && h.t !== t)) return no("last");
  const x = takeOut(afterSale, deckId, t, reason, today, ts);
  if (!x) return no("gone");
  let deck = findDeck(x.data, deckId);
  const cap = raise != null ? raise : capOf(deck);
  const rows = editRows(deck, emptyDraft());
  const shared = rebalance(rows, null, cap);
  // the targets left must add up to 100% (round-1 B1: under the cap they cannot, and 팔고 빼기 waits for the D2 raise)
  if (!sumOk([...shared.values()].reduce((a, v) => a + v, 0))) return no("sum", ": the stocks left cannot reach 100% under the cap");
  const tg = applyTargets(deck, shared, load && load.data ? load.data.fx : null, load && load.byT);
  deck = { ...tg.deck, holdings: withPlanW(before, tg.deck.holdings, tg.ts) };   // the sold stock's plan weight goes to the ones its target went to
  if (raise != null && raise !== capOf(deck)) deck = { ...deck, settings: { ...(deck.settings || {}), maxPct: raise } };
  deck = withChanges({ ...deck, targetsTs: ts }, [x.change]);              // one line: the removal (its share-out is part of it)
  if (!check(deck, today)) return { ok: false, why: "store" };
  return { ok: true, data: putDeck(x.data, deck) };
}

// 팔고 빼기 writes to the stored portfolio at once (round-1 B1), so its checks read what that write will touch: the stored
// holdings left after the sale (a pending 담기 row is not stored yet and does not count; a pending removal still is, until 바꾼
// 내용 저장), at the cap the write will use (a raise already waiting in the draft is saved with it). The edited list must
// keep a stock too. -> { last (no stock would be left: 팔고 빼기 is off), low, y (D2 on the stored rows), n, names (the stored
// stocks left, as the sheet's "{n}개뿐이라" counts them), cap, up }
export function sellCheck(deck, draft, t) {
  const stored = editRows(deck, emptyDraft()).filter((r) => r.t !== t);
  const left = editRows(deck, draft).filter((r) => r.t !== t).length;
  const up = draft && draft.maxPct != null && draft.maxPct !== capOf(deck) ? draft.maxPct : null;
  const cap = up != null ? up : capOf(deck);
  const d2 = d2Of(stored, cap);
  return { last: !stored.length || !left, low: d2.low, y: d2.y, n: stored.length, names: stored.map((r) => r.nk || r.t), cap, up };
}
// The draft after the store changed under it (팔고 빼기 saved): edits of holdings that are gone are dropped; the rest stay.
export function rebaseDraft(deck, draft) {
  if (!deck) return emptyDraft();
  const has = (t) => deck.holdings.some((h) => h && h.t === t);
  const over = Object.fromEntries(Object.entries(draft.over || {}).filter(([t]) => has(t) || (draft.adds || []).some((a) => a.t === t)));
  return { ...draft, over, removed: (draft.removed || []).filter((r) => has(r.t)), adds: (draft.adds || []).filter((a) => !has(a.t)),
    last: draft.last && (has(draft.last) || (draft.adds || []).some((a) => a.t === draft.last)) ? draft.last : null };
}

// The draft after 팔고 빼기 saved (round 3): what still waits, rebased onto the stored portfolio as the sale left it (the sold
// stock gone, its target shared out, a raise saved), never onto the portfolio before the sale: a share-out there could keep a
// value above the new saved target and the cap (55.26% against a saved 55%). A target in the draft that only repeated the old
// saved one is no edit and goes; when edits still wait, they are shared out to 100% again under the new ceilings (fixDraft,
// the row just changed kept), as the old share-out of the sold stock's target did. Nothing else waiting: the saved portfolio.
// before / after: the portfolio before and after the sale's write; t: the stock sold.
export function draftAfterSale(before, after, draft, t) {
  if (!after) return emptyDraft();
  const oldPct = (u) => { const h = ((before && before.holdings) || []).find((x) => x && x.t === u); return h ? pctOf(h) : null; };
  const isAdd = (u) => (draft.adds || []).some((a) => a.t === u);
  const over = Object.fromEntries(Object.entries(draft.over || {})
    .filter(([u, p]) => u !== t && (isAdd(u) || oldPct(u) == null || Math.abs(p - oldPct(u)) > TGT_TOL * 100)));
  const x = rebaseDraft(after, { ...draft, over, adds: (draft.adds || []).filter((a) => a.t !== t), removed: (draft.removed || []).filter((r) => r.t !== t),
    maxPct: null, last: draft.last === t ? null : draft.last });
  return pending(after, x) ? fixDraft(after, x) : x;
}

// ---------------- the change log on screen ----------------
// -> [{ kind, at, t, nk, reason }] newest first, only the kinds this version knows (a later version's are kept, not shown).
export function changeList(deck) {
  const xs = Array.isArray(deck && deck.changes) ? deck.changes : [];
  return xs.map((c, i) => ({ ...c, i })).filter((c) => c && CHANGE_KINDS.includes(c.kind))
    .sort((a, b) => (a.at === b.at ? b.i - a.i : a.at < b.at ? 1 : -1));
}
