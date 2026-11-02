// ================= 2.0 daily rule check (v18.3 Part C) =================
// Pure functions, no React and no Korean text: screens turn the codes returned here into copy from src/copy/v2.js.
// Spec: docs/tasks/v18.3-2.0-beta.md "The rules that matter most here" + Part C; docs/REDESIGN.md sections 2 and 4.1.
// Unit tests: tests/test_v2_rules.py (run through Node).
//
// Each saved holding carries the rule book written at purchase (engine.js ruleBook): every rule is "checked" (with its
// purchase-time number and report year `since`) or "pending" (준비 중). Every day this module reads today's data rows
// and gives each held stock one status, in this order (REDESIGN 2.1):
//   1. a sell condition fired                       -> "broken"  (규칙 깨짐)
//   2. something needs the user's confirmation      -> "check"   (확인 필요: shown as 지켜봐요 with the reason)
//      a keep condition fails                       -> "watch"   (지켜봐요)
//   3. the weight is outside its band               -> "trim" (> 1.4x target) · "high" (> 1.25x) · "low" (< 0.75x)
//   4. none of these                                -> "none"    (할 일 없음)
// Principles kept here:
// - Price never triggers a rule. A daily move of 5% or more only sets `bigMove` (the 크게 움직인 종목 note). Prices
//   matter only through weights (portfolio arithmetic, REDESIGN 2.2).
// - A dividend drop is never 규칙 깨짐 on its own: it is "check" until the user says it was a real cut (then
//   "broken") or not a cut (cleared for that report). Answers live in the deck record (store.js), keyed by the report
//   year and both numbers, so a later, newer cut is asked about again.
// - Only reports NEWER than the rule's `since` can fire an annual rule: a fall that happened before purchase never
//   counts. A report OLDER than at purchase (the pipeline fell back a year) is not used: the input counts as missing.
// - A rule input that existed at purchase and is blank today -> "check" (missing), never 괜찮아요.
// - Stale (published more than 4 days ago, the v17.5 rule) or failed data computes no status at all: the output says
//   why. A rule this version cannot read is treated as not checked (준비 중), never as passed.
import { num, isFin, priceWon, fyOf } from "./engine.js";
import { STALE_DAYS, daysSince } from "../data.js";
import { sameConfirm } from "./store.js";

export const BIG_MOVE = 5;                                       // |d1| >= 5% -> 크게 움직인 종목 (never a status)
export const STATUS_ORDER = ["broken", "check", "watch", "trim", "high", "low", "none"];
const LEVEL = Object.fromEntries(STATUS_ORDER.map((s, i) => [s, i]));
const EPS = 1e-9;                                                // a weight exactly on a band edge is inside the band
// Statuses that take no new money (내 덱 · 추가로 넣을 돈 skips them, Part E). trim and high are above 1.25x target.
export const NO_NEW_MONEY = ["broken", "check", "watch", "trim", "high"];
// The data field each checked rule reads (the {항목} of "{항목} 자료를 받지 못해 확인이 필요해요")
export const RULE_INPUT = { divCut: "dps", debtCeiling: "debt", roeFloor: "roe", opDecline: "op", band: "price" };

// ---------------- can the check run today? ----------------
// load: the state from load.js (status, fresh, data, corp, preview). -> { ok: true } | { ok: false, why, days }
//   why: "loading" · "fail" (a file did not load or was refused) · "stale" (days = days since publication) ·
//        "undated" (a publication time that cannot be read: we cannot tell whether the data is fresh)
// corp.json is checked too: the annual rules read it. The preview page (fictional data with a fixed date) skips it.
export function dayState(load, now) {
  if (!load || load.status === "loading") return { ok: false, why: "loading" };
  if (load.status !== "ok") return { ok: false, why: "fail" };
  if (load.preview) return { ok: true };
  const f = load.fresh || {};
  const corpDays = daysSince(load.corp && load.corp.publishedAt, now);
  if (f.days == null || corpDays == null) return { ok: false, why: "undated" };
  const days = Math.max(f.days, corpDays);
  if (f.stale || days > STALE_DAYS) return { ok: false, why: "stale", days };
  return { ok: true };
}

// Everything the evaluation reads from today's data.
export function todayCtx(load, now) {
  const ok = load && load.status === "ok";
  return { state: dayState(load, now), byT: ok ? load.byT : new Map(), coByT: ok ? load.coByT : new Map(),
    fx: ok ? load.data.fx : null, pxDate: ok ? load.data.pxDate : null };
}

// ---------------- one deck ----------------
// Shares held per stock (purchases with qty > 0). Holdings planned but never bought are not checked.
export function heldQty(deck) {
  const m = new Map();
  for (const p of (deck && deck.purchases) || []) if (p && p.qty > 0) m.set(p.t, (m.get(p.t) || 0) + p.qty);
  return m;
}

// Today's weight of each held stock in the deck, at today's official close (US in won at today's rate). If any held
// stock has no price today, the deck's value is unknown, so no weight is computed (every band is unchecked today).
export function deckWeights(held, ctx) {
  const vals = new Map(), missing = [];
  for (const [t, q] of held) {
    const s = ctx.byT.get(t);
    const px = s ? priceWon(s, ctx.fx) : null;
    if (!(px > 0)) { missing.push(t); continue; }
    vals.set(t, q * px);
  }
  const total = [...vals.values()].reduce((a, b) => a + b, 0);
  if (missing.length || !(total > 0)) return { ok: false, missing };
  return { ok: true, total, value: vals, w: new Map([...vals].map(([t, v]) => [t, v / total])) };
}

const pendingOf = (r) => ({ id: r && typeof r.id === "string" ? r.id : null, kind: r && r.kind, check: "pending", result: "pending" });
const isYear = (y) => Number.isInteger(y);

// Dividend cut (sell). Today's report gives [fy, fy-1, fy-2]; each year after the purchase report is compared with the
// year before it, inside the same report (a split restated by the company stays comparable).
function evalDiv(r, h, s, co, deck) {
  if (!isYear(r.since)) return pendingOf(r);
  const out = { id: "divCut", kind: "sell", check: "checked", input: "dps", since: r.since };
  const fy = s ? fyOf(s, co) : null;
  const d3 = s && Array.isArray(s.dps3) ? s.dps3 : co && Array.isArray(co.dps3) ? co.dps3 : null;
  const v = d3 ? [0, 1, 2].map((i) => num(d3[i])) : [null, null, null];
  if (fy == null || fy < r.since || v[0] == null || v[1] == null) return { ...out, result: "missing", fy };
  const now = { a: v[1], b: v[0] };                              // 주당 {a}원 -> {b}원 (last year -> this report)
  const drops = [];
  for (let i = 0; i < 2; i++) {
    const y = fy - i;
    if (y <= r.since) break;                                     // before purchase: never counts
    const b = v[i], a = v[i + 1];
    if (a == null || b == null) return { ...out, result: "missing", fy, now };
    if (b < a) {
      const item = { t: h.t, rule: "divCut", fy: y, a, b };
      const c = ((deck && deck.confirms) || []).find((x) => sameConfirm(x, item));
      drops.push({ ...item, answer: c ? c.answer : null });
    }
  }
  const result = drops.some((d) => d.answer === "cut") ? "broken" : drops.some((d) => !d.answer) ? "check" : "ok";
  return { ...out, result, fy, now, newer: fy > r.since, drops };
}

// 부채비율 ceiling (keep, Korean company shares only; financial companies: not applicable).
function evalDebt(r, h, s, co) {
  if (!isYear(r.since) || num(r.limit) == null) return pendingOf(r);
  const out = { id: "debtCeiling", kind: "keep", check: "checked", input: "debt", since: r.since, limit: r.limit };
  if (s && isFin(s)) return { ...out, result: "na" };            // 금융회사는 해당 없음 (liabilities are its business)
  const fy = s ? fyOf(s, co) : null;
  const v = s ? num(s.debt) : null;
  if (v == null || fy == null || fy < r.since) return { ...out, result: "missing", fy };
  return { ...out, result: v > r.limit ? "fail" : "ok", fy, now: v, newer: fy > r.since };
}

// ROE floor (keep, from a 수익성 card). US ROE is Yahoo's trailing figure: it has no report year.
function evalRoe(r, h, s, co) {
  const us = (h.cls || (s && s.cls)) === "us";
  if (num(r.floor) == null || (!us && !isYear(r.since))) return pendingOf(r);
  const out = { id: "roeFloor", kind: "keep", check: "checked", input: "roe", since: us ? null : r.since, limit: r.floor };
  const fy = us || !s ? null : fyOf(s, co);
  const v = s ? num(s.roe) : null;
  if (v == null || (!us && (fy == null || fy < r.since))) return { ...out, result: "missing", fy };
  return { ...out, result: v < r.floor ? "fail" : "ok", fy, now: v, newer: us ? null : fy > r.since };
}

// Operating profit down 2 years running (keep, annual). corp.json op = [fy, fy-1, fy-2] in 억원 from the 사업보고서
// of year fy (DART fnlttSinglAcntAll, reprt_code 11011: thstrm, frmtrm, bfefrmtrm). A newer report than at purchase
// fails the rule when op[0] < op[1] < op[2] (any sign: a deeper loss is a fall too).
function evalOp(r, h, s, co) {
  if (!isYear(r.since)) return pendingOf(r);
  const out = { id: "opDecline", kind: "keep", check: "checked", input: "op", since: r.since };
  const fy = s ? fyOf(s, co) : co ? num(co.fy) : null;
  const op = co && Array.isArray(co.op) ? [0, 1, 2].map((i) => num(co.op[i])) : [null, null, null];
  if (fy == null || fy < r.since || op[0] == null) return { ...out, result: "missing", fy };
  if (fy === r.since) return { ...out, result: "ok", fy, now: op, newer: false };   // the purchase report: nothing new
  if (op[1] == null || op[2] == null) return { ...out, result: "missing", fy, now: op };
  return { ...out, result: op[0] < op[1] && op[1] < op[2] ? "fail" : "ok", fy, now: op, newer: true };
}

// Weight band (portfolio arithmetic, not a price rule). bands = [0.75, 1.25, 1.4] x target, as stored at purchase.
function evalBand(r, h, weights) {
  const target = num(r.target);
  const bands = Array.isArray(r.bands) ? r.bands.map(num) : [];
  if (!(target > 0) || bands.length !== 3 || bands.some((x) => x == null)) return pendingOf(r);
  const out = { id: "band", kind: "band", check: "checked", input: "price", target, bands };
  if (!weights.ok) return { ...out, result: "missing", missingPrice: weights.missing };
  const w = weights.w.get(h.t);
  const band = w < bands[0] - EPS ? "low" : w > bands[2] + EPS ? "trim" : w > bands[1] + EPS ? "high" : null;
  return { ...out, result: band ? "band" : "ok", band, now: w };
}

export function evalRule(r, h, s, co, deck, weights) {
  if (!r || typeof r !== "object" || r.check !== "checked") return pendingOf(r);
  switch (r.id) {
    case "divCut": return evalDiv(r, h, s, co, deck);
    case "debtCeiling": return evalDebt(r, h, s, co);
    case "roeFloor": return evalRoe(r, h, s, co);
    case "opDecline": return evalOp(r, h, s, co);
    case "band": return evalBand(r, h, weights);
    default: return pendingOf(r);                                 // a rule this version cannot read is not checked
  }
}

// The reasons behind a holding's status, most serious first. Each one names its rule, its numbers and its report year.
function reasonsOf(results) {
  const out = [];
  for (const x of results) {
    if (x.result === "missing") {
      out.push({ level: "check", code: "missing", rule: x.id, input: x.input, fy: x.fy ?? null, ...(x.missingPrice ? { missingPrice: x.missingPrice } : {}) });
    } else if (x.id === "divCut" && x.drops) {
      for (const d of x.drops) {
        if (d.answer === "cut") out.push({ level: "broken", code: "divCut", rule: "divCut", fy: d.fy, a: d.a, b: d.b });
        else if (!d.answer) out.push({ level: "check", code: "divDrop", rule: "divCut", fy: d.fy, a: d.a, b: d.b, confirm: { t: d.t, rule: "divCut", fy: d.fy, a: d.a, b: d.b } });
      }
    } else if (x.result === "fail") {
      if (x.id === "debtCeiling") out.push({ level: "watch", code: "debtOver", rule: x.id, now: x.now, limit: x.limit, fy: x.fy });
      if (x.id === "roeFloor") out.push({ level: "watch", code: "roeUnder", rule: x.id, now: x.now, limit: x.limit, fy: x.fy });
      if (x.id === "opDecline") out.push({ level: "watch", code: "opFell2", rule: x.id, op: x.now, fy: x.fy });
    } else if (x.result === "band") {
      out.push({ level: x.band, code: "band", rule: "band", band: x.band, now: x.now, target: x.target, bands: x.bands });
    }
  }
  return out.sort((a, b) => LEVEL[a.level] - LEVEL[b.level]);
}

// One held stock. -> { t, nk, cls, kind, qty, status, reasons, rules, w, target, value, d1, bigMove, noNewMoney }
export function evaluateHolding(h, deck, ctx, weights, qty) {
  const s = ctx.byT.get(h.t) || null;
  const co = ctx.coByT.get(h.t) || null;
  const book = Array.isArray(h.rules) ? h.rules : [];
  const rules = book.map((r) => evalRule(r, h, s, co, deck, weights));
  const reasons = reasonsOf(rules);
  // No rule book at all (only possible in a hand-made file): nothing was checked, so never 할 일 없음.
  if (!book.length) reasons.unshift({ level: "check", code: "noRules" });
  const status = reasons.length ? reasons[0].level : "none";
  const d1 = s ? num(s.d1) : null;
  const band = rules.find((x) => x.id === "band");
  return {
    t: h.t, nk: h.nk, cls: h.cls || (s && s.cls) || null, kind: h.kind || null, qty,
    status, reasons, rules,
    w: weights.ok ? weights.w.get(h.t) : null, target: band && band.target != null ? band.target : num(h.target),
    value: weights.ok ? weights.value.get(h.t) : null,
    d1, bigMove: d1 != null && Math.abs(d1) >= BIG_MOVE,          // a note only: never changes the status
    noNewMoney: NO_NEW_MONEY.includes(status),
  };
}

const zeroCounts = () => Object.fromEntries(STATUS_ORDER.map((s) => [s, 0]));

// One saved deck. -> { ok: false, why, days } when the data cannot be used today (no status at all), else
// { ok: true, id, name, holdings, counts, todo, notChecked, notCheckedIds, bigMoves, weights: { ok, missing }, unheld }
//   counts: holdings per status · todo: 규칙 깨짐 + 확인 필요 (오늘 확인할 일) · notChecked: 준비 중 rules of the held
//   stocks (the "아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요" line), notCheckedIds: which kinds of rule
export function evaluateDeck(deck, ctx) {
  if (!ctx.state.ok) return { ok: false, why: ctx.state.why, days: ctx.state.days ?? null, id: deck && deck.id };
  const held = heldQty(deck);
  const weights = deckWeights(held, ctx);
  const holdings = [], unheld = [];
  const seen = new Set();
  for (const h of deck.holdings || []) {
    if (!h || seen.has(h.t)) continue;
    seen.add(h.t);
    if (!held.has(h.t)) { unheld.push(h.t); continue; }
    holdings.push(evaluateHolding(h, deck, ctx, weights, held.get(h.t)));
  }
  const counts = zeroCounts();
  let notChecked = 0;
  const ids = new Set();
  for (const x of holdings) {
    counts[x.status]++;
    for (const r of x.rules) if (r.result === "pending") { notChecked++; if (r.id) ids.add(r.id); }
  }
  return { ok: true, id: deck.id, name: deck.name, pxDate: ctx.pxDate, holdings, counts, todo: counts.broken + counts.check,
    notChecked, notCheckedIds: [...ids], bigMoves: holdings.filter((x) => x.bigMove).map((x) => x.t),
    weights: { ok: weights.ok, missing: weights.ok ? [] : weights.missing }, unheld };
}

// Every saved deck. Stale or failed data: { ok: false, why, days } and no deck is evaluated.
export function evaluateAll(decks, ctx) {
  if (!ctx.state.ok) return { ok: false, why: ctx.state.why, days: ctx.state.days ?? null, decks: [] };
  const out = (decks || []).map((d) => evaluateDeck(d, ctx));
  const counts = zeroCounts();
  for (const d of out) for (const k of STATUS_ORDER) counts[k] += d.counts[k];
  return { ok: true, decks: out, counts, todo: counts.broken + counts.check, notChecked: out.reduce((a, d) => a + d.notChecked, 0),
    bigMoves: out.flatMap((d) => d.bigMoves) };
}
