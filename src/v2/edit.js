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
//   last      the holding the user just changed (합계를 100%로 맞추기 keeps its value).
// [B4] What saves when: anything that records money saves at once with the change it belongs to (팔고 빼기: the sale, the
// removal and the share-out of its target, sellAndRemove); everything else waits for 바꾼 내용 저장 (applyEdit). Nothing is
// written that store.js would refuse (both check the portfolio with store.deckProblem first).
//
// Targets on screen are whole % (the steppers move 1%-point steps); a stored target the user never touches keeps its exact
// value (the plan's own float) until a share-out or 합계를 100%로 맞추기 sets it. Every share-out is proportional to the
// current targets, never pushes a holding above the portfolio's 한 종목 최대 비중 (settings.maxPct, [C2]) — a holding already
// above it (a 채권·금 cushion) is never pushed higher — keeps every holding at 1% or more, and is rounded to whole % by the
// largest remainder, so the targets on screen add up to exactly 100.
// [B1]/[C3] Saving a changed target: every planPx stays; the holding's plannedQty is recomputed from the new target at its
// own planPx (so rules.planWeights' gap follows the new target and nobody else's plan values move) and its band rule is
// regenerated from the new target (engine BANDS). Every other rule of every holding stays as it is. A holding added with
// 담기 gets planPx = today's official close and a plannedQty from its target, and the rule book the build step would give
// it (deckcalc.rulesFor with this portfolio's points), setAt today.
import { BANDS, num, hasGroup } from "./engine.js";
import { rulesFor } from "./deckcalc.js";
import { withoutHolding, deckProblem, problemText, versionFor, CHANGES_MAX } from "./store.js";
import { heldUnits, UNIT, VIEW_SPLITS } from "./held.js";

export const MIN_PCT = 1;                        // a holding stays at 1% or more (빼기 is how a holding leaves)
export const REASONS = ["thesis", "rule", "better", "other"];
export const CHANGE_KINDS = ["add", "remove", "targets"];
export { CHANGES_MAX };                           // the change log keeps the newest 200 (store.js checks the same number)
const SUM_TOL = 5e-4;                            // a sum within 0.0005%-points of 100 is 100 (the plan's float targets)
const TGT_TOL = 1e-9;                            // a target this close to the stored one did not change

export const emptyDraft = () => ({ over: {}, adds: [], removed: [], maxPct: null, last: null });
const isInt = (x) => Number.isInteger(x);
const pctOf = (h) => (num(h && h.target) != null ? num(h.target) * 100 : 0);

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
// A target as shown in its stepper: whole %, or one decimal below 1% (a small stored target never reads 0%).
export const pctShown = (p) => (p > 0 && p < 0.95 ? { n: Math.round(p * 10) / 10, d: 1 } : { n: Math.round(p), d: 0 });

// Is anything waiting for 바꾼 내용 저장?
export function pending(deck, draft) {
  if (!deck || !draft) return false;
  if ((draft.adds || []).length || (draft.removed || []).length) return true;
  if (draft.maxPct != null && draft.maxPct !== capOf(deck)) return true;
  return (deck.holdings || []).some((h) => h && num(draft.over[h.t]) != null && Math.abs(draft.over[h.t] - pctOf(h)) > TGT_TOL * 100);
}

// The stepper's limits for one row: min 1%, max the cap (when set) and what the other rows leave at 1% each.
export function stepLimits(rows, t, cap) {
  const n = rows.length;
  const hi = Math.min(cap != null ? cap : 100, 100 - (n - 1) * MIN_PCT);
  return { lo: MIN_PCT, hi };
}
// One step: from the shown whole % (the stored float is rounded first), never past the limits. -> the new % or null.
export function stepped(rows, t, dir, cap) {
  const r = rows.find((x) => x.t === t);
  if (!r) return null;
  const { lo, hi } = stepLimits(rows, t, cap);
  const cur = Math.round(r.pct);
  const next = cur + dir;
  if (dir > 0 && (next > hi || r.pct >= hi - TGT_TOL)) return null;
  if (dir < 0 && next < lo) return null;
  return next;
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
  return out;
}
// Whole % that add up to `need` (an integer), each within its bounds (integers): the largest remainder.
function wholeShares(items, vals, need) {
  const fl = items.map((x) => ({ t: x.t, v: Math.max(x.lo, Math.min(x.hi, Math.floor(vals.get(x.t) + 1e-9))), f: vals.get(x.t) - Math.floor(vals.get(x.t) + 1e-9), hi: x.hi, lo: x.lo }));
  let left = need - fl.reduce((a, x) => a + x.v, 0);
  const order = [...fl].sort((p, q) => q.f - p.f || (p.t < q.t ? -1 : 1));
  for (let pass = 0; pass < 3 && left !== 0; pass++) {
    for (const x of order) {
      if (left > 0 && x.v + 1 <= x.hi) { x.v += 1; left -= 1; } else if (left < 0 && x.v - 1 >= x.lo) { x.v -= 1; left += 1; }
      if (left === 0) break;
    }
  }
  return new Map(fl.map((x) => [x.t, x.v]));
}
// Share the targets out to 100% in proportion to their current values (합계를 100%로 맞추기, a removal's share-out, 담기, the
// D2 button). anchor: the row that keeps its value (the one just changed, or the stock being added); cap: whole % or null.
// -> Map t -> whole % for every row (the anchor too: it takes what the others cannot when they are all at their bounds).
// The sum is 100 whenever the cap allows it (capCheck); otherwise every row sits at its bound and the sum stays below 100.
export function rebalance(rows, anchor, cap) {
  const a = anchor ? rows.find((r) => r.t === anchor) || null : null;
  const others = rows.filter((r) => r !== a);
  const hiOf = (r) => (cap == null ? 100 : Math.max(cap, Math.floor(r.pct + 1e-9)));
  const items = others.map((r) => ({ t: r.t, w: r.pct, lo: MIN_PCT, hi: hiOf(r) }));
  let aPct = a ? Math.round(a.pct) : 0;
  if (a) aPct = Math.max(MIN_PCT, Math.min(hiOf(a), aPct));
  // the others first: they take 100 − the anchor, within their bounds; what they cannot take (or give) moves the anchor
  const loSum = items.reduce((s, x) => s + x.lo, 0), hiSum = items.reduce((s, x) => s + x.hi, 0);
  if (a) {
    const need = 100 - aPct;
    if (need < loSum) aPct = Math.max(MIN_PCT, 100 - loSum);
    else if (need > hiSum) aPct = Math.min(hiOf(a), 100 - hiSum);
  }
  const need = Math.max(0, 100 - aPct);
  const vals = shareBounded(items, Math.min(need, hiSum));
  const whole = wholeShares(items, vals, Math.min(need, hiSum));
  const out = new Map(whole);
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
  const n = editRows(deck, draft).length;
  const { y } = capCheck(n, capOf(deck, draft));
  if (y == null) return draft;
  return fixDraft(deck, { ...draft, maxPct: y }, y);
}
// A stepper tap: the row's new %, the row remembered as the one just changed.
export const stepDraft = (draft, t, pct) => ({ ...draft, over: { ...draft.over, [t]: pct }, last: t });
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
export function groupOf(row, byT) {
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
// A holding's industry for its row ("지금 {qty}주 · {industry}"): the data's group name, or null (업종 정보 없음).
export function indOf(row, byT, names) {
  const g = groupOf(row, byT);
  if (!g) return null;
  const s = byT && byT.get(row.t);
  return (s && s.ind === g && s.indName) || names.get(g) || null;
}

// Shares held now (held.js: imported + purchases − sales), as a number of shares.
export const heldShares = (deck, t) => (heldUnits(deck).get(t) || 0) / UNIT;

// ---------------- saving ----------------
// The plan's whole amount in won (targets are shares of it): settings.amountMan, else what the plan's own numbers imply
// (Σ plannedQty × planPx × rate ÷ Σ target over the holdings that have both). null when neither is known.
export function planAmount(deck) {
  const m = num(deck && deck.settings && deck.settings.amountMan);
  if (m > 0) return m * 10000;
  let v = 0, w = 0;
  for (const h of (deck && deck.holdings) || []) {
    const q = h && h.plannedQty, px = num(h && h.planPx), t = num(h && h.target);
    const fx = usdHolding(deck, h) ? num(deck.planFx) : 1;
    if (Number.isInteger(q) && px > 0 && t > 0 && fx > 0) { v += q * px * fx; w += t; }
  }
  return v > 0 && w > 0 ? v / w : null;
}
// The same test rules.planWeights uses for a dollar holding.
const usdHolding = (deck, h) => h.cls === "us" || ((deck && deck.purchases) || []).some((p) => p && p.t === h.t && p.ccy === "USD");
// A changed target's plannedQty at the holding's own planPx (US at the plan's rate): null when it cannot be computed (no
// planPx, no amount, a dollar holding without a plan rate) — then the holding goes without one, and rules.planWeights
// gives it no gap of its own (its band is the new target's, the strict direction).
export function plannedFor(deck, h, target, fxToday = null) {
  const A = planAmount(deck), px = num(h.planPx);
  const fx = usdHolding(deck, h) ? num(deck.planFx) || num(fxToday) : 1;
  if (!(A > 0) || !(px > 0) || !(fx > 0) || !(target > 0)) return null;
  const q = Math.round((target * A) / (px * fx));
  return Number.isSafeInteger(q) && q >= 0 ? q : null;
}
export const bandRule = (target) => ({ id: "band", kind: "band", check: "checked", target, bands: BANDS.map((b) => b * target) });
// A holding with a new target: its band rule regenerated (in place, or added when it had none), its plannedQty recomputed.
export function retarget(deck, h, target, fxToday = null) {
  const rules = Array.isArray(h.rules) ? h.rules : [];
  const i = rules.findIndex((r) => r && r.id === "band");
  const nr = i >= 0 ? rules.map((r, j) => (j === i ? bandRule(target) : r)) : [...rules, bandRule(target)];
  const q = plannedFor(deck, h, target, fxToday);
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
  const rules = rulesFor(load, { s, kind: a.kind, targetW: target }, st);
  const h = { t: a.t, nk: a.nk, ...(a.cls ? { cls: a.cls } : {}), ind: hasGroup(s) ? s.ind : null, kind: a.kind, target, setAt: today, ts,
    ...(num(s.price) > 0 ? { planPx: s.price } : {}), rules };
  const q = plannedFor(deck, h, target, load && load.data ? load.data.fx : null);
  return q != null ? { ...h, plannedQty: q } : h;
}
// The change log (Part A): { at, kind, t?, nk?, reason? }, the newest CHANGES_MAX kept.
export function withChanges(deck, entries) {
  if (!entries.length) return deck;
  const all = [...(Array.isArray(deck.changes) ? deck.changes : []), ...entries];
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
// Every stored holding of deck whose target in `pcts` (Map t -> %) differs from its own: retargeted. -> { deck, changed }
function applyTargets(deck, pcts, fxToday) {
  let changed = 0;
  const holdings = deck.holdings.map((h) => {
    if (!h || !pcts.has(h.t)) return h;
    const p = pcts.get(h.t);
    if (!(num(p) > 0) || Math.abs(p - pctOf(h)) <= TGT_TOL * 100) return h;
    changed++;
    return retarget(deck, h, p / 100, fxToday);
  });
  return { deck: { ...deck, holdings }, changed };
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
  if (!sumOk(sumPct(rows))) return { ok: false, why: "sum" };
  const pcts = new Map(rows.map((r) => [r.t, r.pct]));
  const changes = [];
  let cur = data;
  for (const r of draft.removed || []) {
    const x = takeOut(cur, deckId, r.t, r.reason, today, ts);
    if (!x) return { ok: false, why: "gone" };
    cur = x.data;
    changes.push(x.change);
  }
  deck = findDeck(cur, deckId);
  const fx = load && load.data ? load.data.fx : null;
  const tg = applyTargets(deck, pcts, fx);
  deck = tg.deck;
  if (tg.changed) changes.push({ at: today, kind: "targets" });
  for (const a of draft.adds || []) {
    if (deck.holdings.some((h) => h && h.t === a.t)) return { ok: false, why: "gone" };
    const p = pcts.get(a.t);
    if (!(num(p) > 0)) return { ok: false, why: "sum" };
    deck = { ...deck, holdings: [...deck.holdings, newHolding(deck, a, p / 100, load, today, ts)] };
    changes.push({ at: today, kind: "add", t: a.t, nk: a.nk });
  }
  if (draft.maxPct != null && draft.maxPct !== capOf(deck)) deck = { ...deck, settings: { ...(deck.settings || {}), maxPct: draft.maxPct } };
  deck = withChanges(deck, changes);
  if (!check(deck, today)) return { ok: false, why: "store" };
  return { ok: true, data: putDeck(cur, deck) };
}

// 팔고 빼기 [B4]: the store after the sale (records.withRecord), then the stock taken out with its reason and its stored
// target shared out to the stored holdings left (within the cap, or the raised cap y of D2, saved with them), logged —
// one write. opts: { reason, raise (y | null), load, today, ts }. -> { ok: true, data } | { ok: false, why }
export function sellAndRemove(afterSale, deckId, t, opts) {
  const { reason, raise = null, load, today, ts } = opts;
  const x = takeOut(afterSale, deckId, t, reason, today, ts);
  if (!x) return { ok: false, why: "gone" };
  let deck = findDeck(x.data, deckId);
  const cap = raise != null ? raise : capOf(deck);
  const rows = editRows(deck, emptyDraft());
  const changes = [x.change];
  if (rows.length) {
    const tg = applyTargets(deck, rebalance(rows, null, cap), load && load.data ? load.data.fx : null);
    deck = tg.deck;
    if (tg.changed) changes.push({ at: today, kind: "targets" });
  }
  if (raise != null && raise !== capOf(deck)) deck = { ...deck, settings: { ...(deck.settings || {}), maxPct: raise } };
  deck = withChanges(deck, changes);
  if (!check(deck, today)) return { ok: false, why: "store" };
  return { ok: true, data: putDeck(x.data, deck) };
}

// The draft after the store changed under it (팔고 빼기 saved): edits of holdings that are gone are dropped; the rest stay.
export function rebaseDraft(deck, draft) {
  if (!deck) return emptyDraft();
  const has = (t) => deck.holdings.some((h) => h && h.t === t);
  const over = Object.fromEntries(Object.entries(draft.over || {}).filter(([t]) => has(t) || (draft.adds || []).some((a) => a.t === t)));
  return { ...draft, over, removed: (draft.removed || []).filter((r) => has(r.t)), adds: (draft.adds || []).filter((a) => !has(a.t)),
    last: draft.last && (has(draft.last) || (draft.adds || []).some((a) => a.t === draft.last)) ? draft.last : null };
}

// ---------------- the change log on screen ----------------
// -> [{ kind, at, t, nk, reason }] newest first, only the kinds this version knows (a later version's are kept, not shown).
export function changeList(deck) {
  const xs = Array.isArray(deck && deck.changes) ? deck.changes : [];
  return xs.map((c, i) => ({ ...c, i })).filter((c) => c && CHANGE_KINDS.includes(c.kind))
    .sort((a, b) => (a.at === b.at ? b.i - a.i : a.at < b.at ? 1 : -1));
}
