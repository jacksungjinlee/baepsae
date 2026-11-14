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
// Weights compare like with like: the plan's targets are shares of the whole amount (which also holds the money left
// over and any planned stock that got 0 shares), so each held stock's target (ref) is rebased over the targets of the
// stocks actually held, and today's weight is its share of their value. Planned stocks never bought get no band.
// Whole shares: the plan's own weight (plannedQty x planPx at the plan's rate) already differs from ref by a gap g.
// The edges widen by that gap, on its side only (low 0.75 ref + min(0, g) · high 1.25 ref + max(0, g) · trim 1.4 ref +
// max(0, g)), so a deck bought as planned is never flagged on day 1 while later drift beyond the band is. Only the
// plan's numbers make the gap: what the user typed at 샀어요 (quantities, prices) and today's rate never do. 줄일 차례 needs selling one share to bring
// the weight closer to ref, 먼저 살 차례 needs buying one share to; 그만 살 차례 needs no such test.
// Principles kept here:
// - Price never triggers a rule. A daily move of 5% or more only sets `bigMove` (the 크게 움직인 종목 note). Prices
//   matter only through weights (portfolio arithmetic, REDESIGN 2.2).
// - A dividend drop is never 규칙 깨짐 on its own: it is "check" until the user says it was a real cut (then
//   "broken") or not a cut (cleared for that report). Answers live in the deck record (store.js), keyed by the report
//   year and both numbers, so a later, newer cut is asked about again. A confirmed cut stays 규칙 깨짐 whatever later
//   reports show (the sell condition fired; only the user's own answer can change it).
// - Korean dividend-trend switch off (engine.js KR_DIV_TREND, Jack 2026-11-05): a Korean dividend-cut rule is not checked
//   (준비 중, counted in "아직 자동으로 확인하지 못하는 규칙"), never passed, and today's history never fires it (no 확인 필요
//   for a drop): the per-share history cannot tell a stock split from a cut. A cut the user already confirmed
//   (실제로 줄였어요: they ruled out a split themselves) stays 규칙 깨짐, with both answers still open. US is not affected.
//   v19.1b: the switch governs only files published before v19.1b. Exact data (engine.exactData: data.json divCheck) has
//   the split-checked history on today's share basis (dps3a): the rule is checked on it whenever today's history is
//   comparable (engine.krDivHistory: divSt same · adj · zero). Not comparable today (nc · nd, or no dps3a) -> 준비 중 as
//   above (never a guessed cut), a confirmed cut still 규칙 깨짐. Answers keep their key { t, fy, a, b }: for a stock with
//   no share change (same) dps3a is dps3, so earlier answers still match; after a split the numbers differ and a drop
//   that is still there is asked about again (an answer about the old numbers never clears new ones).
// - Only reports NEWER than the rule's `since` can fire an annual rule: a fall that happened before purchase never
//   counts. A report OLDER than at purchase (the pipeline fell back a year) is not used: the input counts as missing.
// - A rule input that existed at purchase and is blank today -> "check" (missing), never 괜찮아요.
// - A held stock missing from today's data altogether (not in data.json any more, v19.0c, Jack's design): its own rules
//   read nothing (each input "missing" -> 확인 필요, as before) and its row stays; the other stocks keep their own checks.
//   Today's weights cannot be known without its value, so every other band is "paused" (no status from it, never a
//   guess): the screens say "빠진 종목이 다시 들어오거나 직접 뺄 때까지 비중은 점검하지 않아요", leave the weight bars and
//   추가로 넣을 돈 out, and count the totals without it ("오늘 데이터에 없는 종목 {n}개(…)는 빼고 계산했어요"). Nothing is
//   removed from the saved record unless the user taps 포트폴리오에서 빼기. A stock that IS in today's data but has no
//   price is different: its value is unknown, so every band of the portfolio is "missing" (확인 필요), as before.
// - Stale (data.json's staleAfter passed, v19.1c; or published more than 4 days ago, the v17.5 rule, kept as the fallback
//   and the backstop: data.js freshness) or failed data computes no status at all: the output says
//   why. A rule this version cannot read is treated as not checked (준비 중), never as passed; a rule book with no rule
//   that could be checked at all is 확인 필요, never 할 일 없음.
import { num, isFin, priceWon, fyOf, fellTwice, KR_DIV_TREND, exactData, krDivHistory, todayD1 } from "./engine.js";
import { STALE_DAYS, daysSince, ownCloseDate, backstopFirst } from "../data.js";
import { sameConfirm } from "./store.js";
import { heldQty as heldOf, heldUnits } from "./held.js";
import { unitHeld } from "../repair.js";

export const BIG_MOVE = 5;                                       // |d1| >= 5% -> 크게 움직인 종목 (never a status)
export const STATUS_ORDER = ["broken", "check", "watch", "trim", "high", "low", "none"];
const LEVEL = Object.fromEntries(STATUS_ORDER.map((s, i) => [s, i]));
const EPS = 1e-9;                                                // a weight exactly on an edge is inside the band
// Statuses that take no new money (포트폴리오 · 추가로 넣을 돈 skips them, Part E). trim and high are above 1.25x target.
export const NO_NEW_MONEY = ["broken", "check", "watch", "trim", "high"];
// The data field each checked rule reads (the {항목} of "{항목} 자료를 받지 못해 확인이 필요해요")
export const RULE_INPUT = { divCut: "dps", debtCeiling: "debt", roeFloor: "roe", opDecline: "op", band: "price" };
// 공시 단위 확인 (Jack, 2026-11-13; src/repair.js unitHeld): the rule inputs the pipeline blanks for a company whose statements were
// read in the wrong unit. Such a rule is "missing" (확인 필요), never kept or broken; its reason says why with the approved line
// (co.unitChk) instead of "{item} 자료를 받지 못해 확인이 필요해요", once per holding.
export const UNIT_INPUTS = ["debt", "roe", "op"];

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
  // v19.1c (Jack, 2026-11-07): data.json late past its staleAfter with a due date (nextPub): n counts from the morning the
  // publish was due (data.js freshness, fresh.due), so the band says the same n as the date line. Otherwise as before.
  // The count never goes down: when corp.json is itself past the 4-day rule and that warning was already showing before
  // staleAfter passed (data.js backstopFirst: a corp.json older than data.json, or a long holiday gap), the band keeps the
  // larger of the two counts. When staleAfter came first, the band says the due-day n of the date line.
  if (f.stale && f.due) {
    const keep = corpDays > STALE_DAYS && backstopFirst(load.corp.publishedAt, load.data && load.data.staleAfter);
    return { ok: false, why: "stale", days: keep ? Math.max(f.days, corpDays) : f.days };
  }
  const days = Math.max(f.days, corpDays);
  if (f.stale || days > STALE_DAYS) return { ok: false, why: "stale", days };
  return { ok: true };
}

// Everything the evaluation reads from today's data.
export function todayCtx(load, now) {
  const ok = load && load.status === "ok";
  return { state: dayState(load, now), byT: ok ? load.byT : new Map(), coByT: ok ? load.coByT : new Map(),
    fx: ok ? load.data.fx : null, pxDate: ok ? load.data.pxDate : null, usPxDate: ok ? load.data.usPxDate || null : null };
}

// ---------------- one deck ----------------
// Shares held per stock, more than 0 (v19.3d: the shared rule of held.js, imported + purchases − sales; before it, the
// purchases alone, which it still is for a portfolio with nothing else). Holdings planned but never bought are not checked.
export const heldQty = (deck) => heldOf(deck || {});

// A holding's band rule when it can be used (a target and three edges), else null.
export function bandRuleOf(h) {
  const r = h && Array.isArray(h.rules) ? h.rules.find((x) => x && x.id === "band" && x.check === "checked") : null;
  if (!r || !(num(r.target) > 0) || !Array.isArray(r.bands) || r.bands.length !== 3 || r.bands.some((x) => num(x) == null)) return null;
  return r;
}

// Today's weight of each held stock among the held stocks that have a band rule, at today's official close (US in won
// at today's rate: a currency move changes weights like a price move). targets: Map t -> the plan's target (a share of
// the whole amount); targetSum is their sum, used to rebase each target over what is actually held. If any of them has
// no price today, the value is unknown, so no weight is computed (every band is unchecked today). Without targets
// every held stock counts.
export function deckWeights(held, ctx, targets) {
  const vals = new Map(), pxs = new Map(), missing = [];
  let targetSum = 0;
  for (const [t, q] of held) {
    if (targets && !targets.has(t)) continue;
    if (targets) targetSum += targets.get(t);
    const s = ctx.byT.get(t);
    const px = s ? priceWon(s, ctx.fx) : null;
    if (!(px > 0)) { missing.push(t); continue; }
    vals.set(t, q * px);
    pxs.set(t, px);
  }
  const total = [...vals.values()].reduce((a, b) => a + b, 0);
  if (missing.length || !(total > 0)) return { ok: false, missing };
  return { ok: true, total, targetSum: targets ? targetSum : null, value: vals, px: pxs, w: new Map([...vals].map(([t, v]) => [t, v / total])) };
}

// Held stocks missing from today's data (v19.0c): no weight is computed (paused), but the value of every held stock that
// is in the data and has a price is kept (value), so the screens can count the totals without the missing ones.
// missing names the absent stocks (their own band reads "missing" price); absent says the same for the screens.
function pausedWeights(held, ctx, absent) {
  const value = new Map(), px = new Map();
  for (const [t, q] of held) {
    const s = ctx.byT.get(t);
    const p = s ? priceWon(s, ctx.fx) : null;
    if (p > 0) { value.set(t, q * p); px.set(t, p); }
  }
  return { ok: false, paused: true, missing: absent, absent, value, px };
}

// The plan's own weights among the held stocks with a band (the only source of the gap g = planW - ref):
//   plannedQty x planPx (the price the plan used, own currency), US at the plan's rate deck.planFx, as saved at 샀어요
//   (deckcalc.deckRecord). The quantities the user typed and today's rate never enter.
// Legacy path (decks saved before planPx existed, the launch night until this merge): when any of these holdings has
//   no planPx, every price is the holding's average recorded purchase price instead. plannedQty is still the plan's,
//   so buying more than planned is still flagged; only a price typo on such a deck can widen g.
// US and no plan rate (legacy decks never have one): g = 0 for the whole deck (null), the strict direction, because the
//   rate at plan time is unknown. A holding without plannedQty (a hand-made file): g = 0 for that holding (planW =
//   its ref); the others share what is left in proportion to their planned values.
export function planWeights(deck, targets) {
  const targetSum = [...targets.values()].reduce((a, b) => a + b, 0);
  const hs = [];
  for (const h of (deck && deck.holdings) || []) if (h && targets.has(h.t) && !hs.some((x) => x.t === h.t)) hs.push(h);
  if (!hs.length || !(targetSum > 0)) return null;
  const buys = ((deck && deck.purchases) || []).filter((p) => p && p.qty > 0 && num(p.price) > 0);
  const usd = (h) => h.cls === "us" || buys.some((p) => p.t === h.t && p.ccy === "USD");
  const legacy = hs.some((h) => !(num(h.planPx) > 0));
  const fx = num(deck.planFx);
  if (hs.some(usd) && (legacy || !(fx > 0))) return null;
  const avgPaid = (t) => {
    const ps = buys.filter((p) => p.t === t);
    const q = ps.reduce((a, p) => a + p.qty, 0);
    return q > 0 ? ps.reduce((a, p) => a + p.qty * p.price, 0) / q : null;
  };
  const known = new Map();
  let unknownRef = 0;
  for (const h of hs) {
    const q = h.plannedQty, px = legacy ? avgPaid(h.t) : num(h.planPx);
    if (!Number.isInteger(q) || q < 0 || !(px > 0)) { unknownRef += targets.get(h.t) / targetSum; continue; }
    known.set(h.t, q * px * (usd(h) ? fx : 1));
  }
  const sumKnown = [...known.values()].reduce((a, b) => a + b, 0);
  if (!(sumKnown > 0)) return null;
  const out = new Map();
  for (const h of hs) out.set(h.t, known.has(h.t) ? (known.get(h.t) / sumKnown) * (1 - unknownRef) : targets.get(h.t) / targetSum);
  return out;
}

const pendingOf = (r) => ({ id: r && typeof r.id === "string" ? r.id : null, kind: r && r.kind, check: "pending", result: "pending" });
const isYear = (y) => Number.isInteger(y);

// Dividend cut (sell). Today's report gives [fy, fy-1, fy-2]; each year after the purchase report is compared with the
// year before it, inside the same report (a split restated by the company stays comparable). drops lists every drop
// after purchase with the user's answer (null = not answered yet), newest first, including cuts the user confirmed
// earlier that today's report no longer shows (they stay: the sell condition fired).
// trend off (KR_DIV_TREND): a dividend-cut rule not on a US holding (only Korean holdings ever get a checked one) reads
// nothing from today's history, which may hide a split: not checked (준비 중), unless the user already confirmed a cut
// after purchase (then 규칙 깨짐 as always: the sell condition fired on their own answer).
// Exact data (v19.1b): today's comparable history (dps3a) instead; not comparable today -> as with the switch off.
function evalDiv(r, h, s, co, deck, trend) {
  if (!isYear(r.since)) return pendingOf(r);
  const out = { id: "divCut", kind: "sell", check: "checked", input: "dps", since: r.since };
  const confirms = ((deck && deck.confirms) || []).filter((c) => c && c.t === h.t && c.rule === "divCut" && isYear(c.fy) && c.fy > r.since);
  const drops = confirms.filter((c) => c.answer === "cut").map((c) => ({ t: h.t, rule: "divCut", fy: c.fy, a: c.a, b: c.b, answer: "cut" }));
  const kr = (h.cls || (s && s.cls)) !== "us";
  const exact = kr && exactData();
  // exact: the stock is in today's data but its history is not comparable (a held stock missing from the data reads
  // nothing and is "missing" below, as with the switch on)
  const hist = exact && s ? krDivHistory(s, co) : null;
  if ((exact && s && !hist) || (!exact && !trend && kr)) {
    if (!drops.length) return pendingOf(r);
    drops.sort((x, y) => y.fy - x.fy);
    const fy = s ? fyOf(s, co) : null;
    return { ...out, result: "broken", missing: false, fy, now: null, newer: fy != null && fy > r.since, drops };
  }
  const fy = s ? fyOf(s, co) : null;
  const d3 = exact ? hist : s && Array.isArray(s.dps3) ? s.dps3 : co && Array.isArray(co.dps3) ? co.dps3 : null;
  const v = d3 ? [0, 1, 2].map((i) => num(d3[i])) : [null, null, null];
  let missing = fy == null || fy < r.since || v[0] == null || v[1] == null;
  const now = missing ? null : { a: v[1], b: v[0] };             // 주당 {a}원 -> {b}원 (last year -> this report)
  for (let i = 0; !missing && i < 2; i++) {
    const y = fy - i;
    if (y <= r.since) break;                                     // before purchase: never counts
    const b = v[i], a = v[i + 1];
    if (a == null || b == null) { missing = true; break; }
    if (b < a) {
      const item = { t: h.t, rule: "divCut", fy: y, a, b };
      if (drops.some((x) => sameConfirm(x, item))) continue;     // already a confirmed cut
      const c = confirms.find((x) => sameConfirm(x, item));
      drops.push({ ...item, answer: c ? c.answer : null });
    }
  }
  drops.sort((x, y) => y.fy - x.fy);
  const result = drops.some((d) => d.answer === "cut") ? "broken" : missing ? "missing" : drops.some((d) => !d.answer) ? "check" : "ok";
  return { ...out, result, missing, fy, now, newer: fy != null && fy > r.since, drops };
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
  return { ...out, result: fellTwice(op) ? "fail" : "ok", fy, now: op, newer: true };
}

// Weight band (portfolio arithmetic, not a price rule). The stored target and bands ([0.75, 1.25, 1.4] x target) are
// shares of the plan's whole amount; they are rebased over the targets of the held stocks (ref = planTarget /
// targetSum), so target, bands and now are all shares of the held value. bands are the edges used today: the rebased
// edges (refBands) widened by the plan's gap on its side (gap = planW - ref; 0 without plan weights).
function evalBand(r, h, weights) {
  const planTarget = num(r.target);
  const planBands = Array.isArray(r.bands) ? r.bands.map(num) : [];
  if (!(planTarget > 0) || planBands.length !== 3 || planBands.some((x) => x == null)) return pendingOf(r);
  const out = { id: "band", kind: "band", check: "checked", input: "price", planTarget, planBands };
  // a held stock is missing from today's data: the other bands wait (no status) — but only a stock whose own price is in
  // today's data; one without a price is "missing" (확인 필요) as always, and so is the missing stock itself
  if (weights.paused && !weights.absent.includes(h.t) && weights.px.has(h.t)) return { ...out, target: planTarget, bands: planBands, result: "paused" };
  if (weights.paused) return { ...out, target: planTarget, bands: planBands, result: "missing", missingPrice: weights.px.has(h.t) ? weights.missing : [...new Set([...weights.missing, h.t])] };
  if (!weights.ok || !weights.w.has(h.t)) return { ...out, target: planTarget, bands: planBands, result: "missing", missingPrice: weights.missing || [] };
  const k = weights.targetSum > 0 ? weights.targetSum : 1;
  const ref = planTarget / k, refBands = planBands.map((b) => b / k);
  const planW = weights.planW ? weights.planW.get(h.t) : null;
  const gap = planW != null ? planW - ref : 0;
  const bands = [refBands[0] + Math.min(0, gap), refBands[1] + Math.max(0, gap), refBands[2] + Math.max(0, gap)];
  const v = weights.value.get(h.t), px = weights.px.get(h.t), T = weights.total, w = weights.w.get(h.t);
  // one share sold (the money leaves the stocks) or bought: is the weight then closer to ref?
  const dist = (x) => Math.abs(x - ref);
  const sellCloser = T - px > 0 && dist((v - px) / (T - px)) < dist(w) - EPS;
  const buyCloser = dist((v + px) / (T + px)) < dist(w) - EPS;
  const band = w > bands[2] + EPS && sellCloser ? "trim" : w > bands[1] + EPS ? "high" : w < bands[0] - EPS && buyCloser ? "low" : null;
  return { ...out, target: ref, refBands, bands, gap, planW, scale: k, result: band ? "band" : "ok", band, now: w };
}

// trend: the Korean dividend-trend switch (engine.js KR_DIV_TREND unless a test passes another state).
export function evalRule(r, h, s, co, deck, weights, trend = KR_DIV_TREND) {
  if (!r || typeof r !== "object" || r.check !== "checked") return pendingOf(r);
  switch (r.id) {
    case "divCut": return evalDiv(r, h, s, co, deck, trend);
    case "debtCeiling": return evalDebt(r, h, s, co);
    case "roeFloor": return evalRoe(r, h, s, co);
    case "opDecline": return evalOp(r, h, s, co);
    case "band": return evalBand(r, h, weights);
    default: return pendingOf(r);                                 // a rule this version cannot read is not checked
  }
}

// The reasons behind a holding's status, most serious first. Each one names its rule, its numbers and its report year.
// Dividend reasons carry `confirm` (the item to answer) and the current `answer`, so the screen can change it.
function reasonsOf(results, unit = false) {
  const out = [];
  let unitSaid = false;
  for (const x of results) {
    if ((x.result === "missing" || x.missing) && unit && UNIT_INPUTS.includes(x.input)) {
      // the unit check blanked this input: one reason for all of them (the line says why once), still 확인 필요
      if (!unitSaid) out.push({ level: "check", code: "missing", rule: x.id, input: x.input, fy: x.fy ?? null, unit: true });
      unitSaid = true;
    } else if (x.result === "missing" || x.missing) {
      out.push({ level: "check", code: "missing", rule: x.id, input: x.input, fy: x.fy ?? null, ...(x.missingPrice ? { missingPrice: x.missingPrice } : {}) });
    }
    if (x.id === "divCut" && x.drops) {
      for (const d of x.drops) {
        const confirm = { t: d.t, rule: "divCut", fy: d.fy, a: d.a, b: d.b };
        if (d.answer === "cut") out.push({ level: "broken", code: "divCut", rule: "divCut", fy: d.fy, a: d.a, b: d.b, confirm, answer: "cut" });
        else if (!d.answer) out.push({ level: "check", code: "divDrop", rule: "divCut", fy: d.fy, a: d.a, b: d.b, confirm, answer: null });
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

// v19.6a: a holding sold down to 0 and kept (남겨 두기). Three ways to read it, one switch (final review S1; Jack chose "own" on 2026-11-13):
//   "off"   what was live before v19.6a (v19.3d2, Jack 2026-11-08): it is left out of the band rules ("다 팔고 목표 비중만 남아
//           있어요."), the other targets are rebased over what is held.
//   "spec"  spec v19.6 A.1 to the letter: it counts as held with 0 shares and every band is read over the whole plan. It can
//           show as below its band (먼저 사요) and 추가로 넣을 돈 buys it back — but in a small or concentrated portfolio the
//           OTHER holdings then read above their bands (three equal stocks, one sold out and kept: the two left sit at 50%
//           against an edge of 46.7% and read 일부 팔아요), the false sell instruction "off" was chosen to avoid.
//   "own"   (what ships, Jack 2026-11-13) the sold-out holding is read at 0 shares against its own band over the whole
//           plan, so it reads 먼저 사요 and 추가로 넣을 돈 buys it back first, while every other holding keeps the "off"
//           reading (rebased over what is held): the sale gives no other holding a new 일부 팔아요 or 더 안 사요.
// ctx.soldOutBands ("off" · "spec" · "own"): set only by tests, to check all three.
export const SOLD_OUT_BANDS = "own";
const SOLD_OUT_MODES = ["off", "spec", "own"];

// One held stock. -> { t, nk, cls, kind, qty, status, reasons, rules, w, target, value, px, d1, pxd, bigMove, noNewMoney }
//   px (v19.6a): today's won price of one share (for 추가로 넣을 돈 when 0 shares are held: SOLD_OUT_BANDS "spec" · "own")
//   pxd (v19.1c): the stock's own price date when it is priced at an earlier close than the US date (data.json pxd), else
//   null; its d1 is then null (engine.todayD1), so it is never a 큰 움직임 and the screens name it in their notes.
export function evaluateHolding(h, deck, ctx, weights, qty) {
  const s = ctx.byT.get(h.t) || null;
  const co = ctx.coByT.get(h.t) || null;
  // ctx.krDivTrend: set only by tests, to check both states of the switch; todayCtx leaves it out (the switch applies)
  const trend = typeof ctx.krDivTrend === "boolean" ? ctx.krDivTrend : KR_DIV_TREND;
  // v19.6a (verification B1): a holding sold out and kept, read with 0 shares ("spec" · "own"), is read on its weight band
  // only: it can be 먼저 사요 or 할 일 없음, never 규칙 깨짐, 지켜봐요 or 확인 필요 for shares nobody holds, and its other rules are
  // not shown or counted (not 준비 중 either: they are not in "아직 자동으로 확인하지 못하는 규칙"). Those rules are read for one
  // thing only: the app never tells the user to buy back a stock that fails any of its own rules. When one of them reads
  // 규칙 깨짐, 지켜봐요 or 확인 필요 (the levels that stop new money for a held stock, NO_NEW_MONEY: a dividend cut, 부채비율 over
  // its ceiling, a figure missing today, a drop not answered yet), the band is not read either: no 먼저 사요, no target
  // (추가로 넣을 돈 skips it and buys what "off" buys); soldOutFails says so. Jack, 2026-11-14: it must never look blank, so the
  // rules it fails are its rule rows and reasons (the wording a held stock gets for them), with no status of its own
  // ("none": no action chip, nothing on 홈, no 규칙대로면 팔 때예요 for 0 shares).
  const zero = qty === 0;
  const full = Array.isArray(h.rules) ? h.rules : [];
  // 공시 단위 확인: a Korean stock whose statement numbers the pipeline blanked (data.json or corp.json unitChk)
  const unit = !!s && s.cls === "kr" && (unitHeld(s) || unitHeld(co));
  const fails = (x) => reasonsOf([x]).some((y) => NO_NEW_MONEY.includes(y.level));
  const failing = zero ? full.filter((r) => !(r && r.id === "band")).map((r) => evalRule(r, h, s, co, deck, weights, trend)).filter(fails) : [];
  const soldOutFails = failing.length > 0;
  const book = zero ? (soldOutFails ? [] : [bandRuleOf(h)].filter(Boolean)) : full;
  const rules = soldOutFails ? failing : book.map((r) => evalRule(r, h, s, co, deck, weights, trend));
  const reasons = reasonsOf(rules, unit);
  // No rule that could be checked at all (an empty or malformed book, only possible in a hand-made file): nothing was
  // checked, so never 할 일 없음.
  if (!soldOutFails && !rules.some((x) => x.check === "checked")) reasons.unshift({ level: "check", code: "noRules" });
  const status = soldOutFails ? "none" : reasons.length ? reasons[0].level : "none";
  const d1 = todayD1(s);
  const pxd = ownCloseDate(s, ctx.usPxDate);
  const band = rules.find((x) => x.id === "band" && x.check === "checked");
  const div = rules.find((x) => x.id === "divCut" && x.drops);
  return {
    t: h.t, nk: h.nk, cls: h.cls || (s && s.cls) || null, kind: h.kind || null, qty, ...(zero ? { soldOutFails } : {}),
    status, reasons, rules, unit,
    // every dividend drop after purchase with its answer (null / "cut" / "notCut"): the screen keeps both answers open
    divDrops: div ? div.drops : [],
    // w and target are both shares of the held value (target rebased); planTarget is the plan's share of the amount
    w: weights.ok && weights.w.has(h.t) ? weights.w.get(h.t) : null,
    target: band && band.result !== "missing" && band.result !== "paused" ? band.target : null,
    planTarget: band ? band.planTarget : num(h.target),
    value: (weights.ok || weights.paused) && weights.value && weights.value.has(h.t) ? weights.value.get(h.t) : null,
    px: weights.px && weights.px.has(h.t) ? weights.px.get(h.t) : null,
    absent: !s,                                                   // not in today's data at all (v19.0c: the row stays)
    // a note only: never changes the status. Never on a 0-share holding (verification nit: not in 홈's 큰 움직임)
    d1, pxd, bigMove: qty !== 0 && d1 != null && Math.abs(d1) >= BIG_MOVE,
    noNewMoney: soldOutFails || NO_NEW_MONEY.includes(status),
  };
}

const zeroCounts = () => Object.fromEntries(STATUS_ORDER.map((s) => [s, 0]));

// One saved deck. -> { ok: false, why, days } when the data cannot be used today (no status at all), else
// { ok: true, id, name, holdings, counts, todo, notChecked, notCheckedIds, bigMoves, weights: { ok, missing, paused },
//   absent, unheld, bandPlanned, bandHeld, rebased }   rebased: some planned stocks were never bought, so targets were rebased
//   absent: held stocks missing from today's data (v19.0c): their rows stay, the other bands are paused
//   counts: holdings per status · todo: 규칙 깨짐 + 확인 필요 (오늘 확인할 일) · notChecked: 준비 중 rules of the held
//   stocks (the "아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요" line), notCheckedIds: which kinds of rule
export function evaluateDeck(deck, ctx) {
  if (!ctx.state.ok) return { ok: false, why: ctx.state.why, days: ctx.state.days ?? null, id: deck && deck.id };
  const held = heldQty(deck);
  // v19.3d (v19.3 F.1): a portfolio made with 가진 종목 넣기 has no per-stock rule book. Its held stocks (imported rows
  // and any later records, held.js) are read here but get no per-stock status: nothing in it is 확인 필요 or 할 일 없음.
  // Only the four portfolio rules run on it (pf.js pfState), and 홈 and 포트폴리오 show those instead.
  if (deck && deck.kind === "imported") {
    return { ok: true, id: deck.id, name: deck.name, pxDate: ctx.pxDate, imported: true, held: [...held.entries()], holdings: [], counts: zeroCounts(),
      todo: 0, notChecked: 0, notCheckedIds: [], bigMoves: [], weights: { ok: false, missing: [] }, absent: [], unheld: [], bandPlanned: 0, bandHeld: 0,
      rebased: false };
  }
  // v19.3d: a holding sold down to 0 shares (its records add up to 0, held.js) is sold out, never "planned, never bought":
  // it is not in unheld (v19.6 A.1). SOLD_OUT_BANDS "off": the other targets are rebased over what is held (kept in the
  // target sum at weight 0 instead, every stock still held would read as over its target and get a wrong 비중 줄이기
  // instruction), and the rebased note ("계획한 {n}종목 중 {m}종목만 샀어요") is not about it: v19.3d2 (Jack) shows "다 팔고 목표
  // 비중만 남아 있어요." for the sold-out holding instead (soldOut), so bandPlanned leaves it out.
  // "spec": a sold-out holding with a band rule and a price today is held with 0 shares for everyone's bands.
  // "own": the same holding gets its own reading over the whole plan (the "spec" weights), beside the "off" reading of the rest.
  // Either way it is read on its band only (evaluateHolding with 0 shares): 먼저 사요 or 할 일 없음.
  const units = heldUnits(deck);
  const soldOut = (deck.holdings || []).filter((h) => h && units.has(h.t) && units.get(h.t) <= 0).map((h) => h.t);
  const mode = SOLD_OUT_MODES.includes(ctx.soldOutBands) ? ctx.soldOutBands : SOLD_OUT_BANDS;
  const targetsOf = (set) => {
    const m = new Map();
    for (const h of deck.holdings || []) {
      const b = h && set.has(h.t) && !m.has(h.t) ? bandRuleOf(h) : null;
      if (b) m.set(h.t, num(b.target));
    }
    return m;
  };
  const absent = [...held.keys()].filter((t) => !ctx.byT.has(t));
  // With a held stock missing from today's data, the weights wait for all held stocks (with or without a band rule).
  const weightsOf = (set, tg) => {
    const w = absent.length ? pausedWeights(set, ctx, absent) : deckWeights(set, ctx, tg);
    if (w.ok) w.planW = planWeights(deck, tg);
    return w;
  };
  // only one with a price today: a 0-share holding without one must not stop the weights (or the money totals) of the rest
  const cand = mode === "off" ? [] : (deck.holdings || []).filter((h) => h && soldOut.includes(h.t) && bandRuleOf(h)
    && ctx.byT.has(h.t) && priceWon(ctx.byT.get(h.t), ctx.fx) > 0).map((h) => h.t);
  const candSet = new Map([...held, ...cand.map((t) => [t, 0])]);
  const candWeights = cand.length ? weightsOf(candSet, targetsOf(candSet)) : null;
  // v19.6a (verification S-a): read with 0 shares only when those weights can be read today (something is held, every price
  // is known, nothing is missing from the data). Otherwise — every holding sold out and kept among them — they read as
  // under "off" (no status, the approved sold-out line), never 확인 필요 for a weight nobody can have.
  const zeros = candWeights && candWeights.ok ? cand : [];
  const withZeros = zeros.length ? candSet : held;
  const banded = mode === "spec" ? withZeros : held;
  const targets = targetsOf(banded);
  const weights = weightsOf(banded, targets);
  const zeroOwn = mode === "own" ? zeros : [];
  const zeroWeights = zeroOwn.length ? candWeights : null;
  const bandPlanned = new Set((deck.holdings || []).filter((h) => h && bandRuleOf(h) && (mode === "spec" ? banded.has(h.t) || !soldOut.includes(h.t) : !soldOut.includes(h.t))).map((h) => h.t)).size;
  const holdings = [], unheld = [];
  const seen = new Set();
  for (const h of deck.holdings || []) {
    if (!h || seen.has(h.t)) continue;
    seen.add(h.t);
    if (banded.has(h.t)) holdings.push(evaluateHolding(h, deck, ctx, weights, banded.get(h.t)));
    else if (zeroOwn.includes(h.t)) holdings.push(evaluateHolding(h, deck, ctx, zeroWeights, 0));
    else if (!soldOut.includes(h.t)) unheld.push(h.t);
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
    weights: { ok: weights.ok, missing: weights.ok ? [] : weights.missing, ...(weights.paused ? { paused: true } : {}) }, absent, unheld, soldOut,
    // zeroOwn ("own"): the sold-out holdings read on their own, over the whole plan (their target is not a share of what is held)
    ...(zeroOwn.length ? { zeroOwn } : {}),
    bandPlanned, bandHeld: targets.size, rebased: targets.size > 0 && targets.size < bandPlanned };
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
