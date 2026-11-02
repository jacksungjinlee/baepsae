// ================= 2.0 tracking sheet and 왜 움직였나 (v18.3 Part E) =================
// Pure functions, no React and no Korean text: screens turn the results into copy from src/copy/v2.js.
// Spec: docs/tasks/v18.3-2.0-beta.md Part E; docs/REDESIGN.md section 3 (오늘 · 내 덱 · 왜 움직였나) and 4.1.
// Unit tests: tests/test_v2_track.py (run through Node).
//
// Everything here reads the daily evaluation from rules.js (evaluateDeck): its weights and targets, its statuses and its
// "ok: false" when the data is stale or failed. Nothing is computed from stale or failed data, and nothing is estimated:
// a number whose input is missing is left out (ok: false), never filled in.
import { num, hasGroup, universe, priceWon } from "./engine.js";
import { NO_NEW_MONEY } from "./rules.js";

export const GROUP_MIN = 5;           // 같은 업종 점 띠: a real industry group with at least 5 members in the same market
export const TOGETHER_SHARE = 0.8;    // "같은 업종이 다 같이 빠졌어요": the stock fell and at least 80% of its group fell
export const ADD_CAP = 1.25;          // 추가로 넣을 돈 never takes a stock above its 1.25x edge (REDESIGN 4.1)
const EPS = 1e-9;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

// ---------------- money put in (원금) ----------------
// One purchase in won, from the purchase record (qty x price). KRW as is. USD x the exchange rate recorded when it was
// saved: the purchase's own fx (Part E), else the deck's planFx (Part C: the same data.json rate, saved at the same
// moment). A USD purchase saved with neither (records from before them) has no won cost: the deck's 원금 and return
// are then left out, never converted at today's rate.
export function purchaseWon(p, planFx) {
  if (!p || !(Number.isInteger(p.qty) && p.qty > 0) || !(num(p.price) > 0)) return null;
  if (p.ccy === "KRW") return p.qty * p.price;
  if (p.ccy === "USD") { const fx = num(p.fx) > 0 ? p.fx : num(planFx) > 0 ? planFx : null; return fx ? p.qty * p.price * fx : null; }
  return null;
}

// Value, money put in and return of one deck.
//   deck: the stored deck · de: evaluateDeck(deck, ctx) for it · ctx: todayCtx (the same prices and rate).
// -> { ok: false, why } | { ok: true, value, cost, gain, ret, start, per: { t: { qty, value, cost, ret } }, noFx: [t] }
//   cost / gain / ret are null when any held purchase has no won cost (noFx names them). value is today's value of
//   every held share at today's official close (US at today's rate). Any held stock without a price today: no value.
export function deckMoney(deck, de, ctx) {
  if (!de || !de.ok || !ctx) return { ok: false, why: "day" };
  if (!de.weights || !de.weights.ok) return { ok: false, why: "price" };
  const held = new Set(de.holdings.map((x) => x.t));
  const per = {};
  let value = 0;
  for (const x of de.holdings) {
    const s = ctx.byT.get(x.t);
    const px = s ? priceWon(s, ctx.fx) : null;
    if (!(px > 0) || !(x.qty > 0)) return { ok: false, why: "price" };
    per[x.t] = { qty: x.qty, value: x.qty * px, cost: 0, ret: null };
    value += x.qty * px;
  }
  const noFx = [];
  let start = null;
  for (const p of (deck && deck.purchases) || []) {
    if (!p || !(p.qty > 0) || !held.has(p.t)) continue;
    const c = purchaseWon(p, deck.planFx);
    if (c == null) { if (!noFx.includes(p.t)) noFx.push(p.t); per[p.t].cost = null; continue; }
    if (per[p.t].cost != null) per[p.t].cost += c;
    if (typeof p.date === "string" && DATE.test(p.date) && (start == null || p.date < start)) start = p.date;
  }
  for (const t of Object.keys(per)) {
    const r = per[t];
    r.ret = r.cost > 0 ? r.value / r.cost - 1 : null;
  }
  const cost = noFx.length ? null : Object.values(per).reduce((a, r) => a + r.cost, 0);
  const ok = cost != null && cost > 0;
  return { ok: true, value, cost: ok ? cost : null, gain: ok ? value - cost : null, ret: ok ? value / cost - 1 : null, start, per, noFx };
}

// ---------------- KOSPI over the same dates ----------------
// The deck's purchases, each bought at roughly the last official close before its purchase date (샀어요 records the
// plan's close by default), compared with KOSPI from the last close before each purchase date to today's close.
// Several purchase dates are weighted by the won put in on each (what the same money would have done in KOSPI).
// Today's close must be the data's own pxDate (the same date the deck's value uses), else nothing is shown.
//   idx: macro.json idxHist.KOSPI ({ asOf, rows: [[date, close], ...] }) · pxDate: data.json pxDate
// -> { ok: true, ret, start, end } | { ok: false, why }
export function closeBefore(rows, date) {
  let lo = 0, hi = rows.length - 1, out = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (rows[mid][0] < date) { out = rows[mid]; lo = mid + 1; } else hi = mid - 1;
  }
  return out;
}

export function validRows(idx) {
  const rows = idx && Array.isArray(idx.rows) ? idx.rows : null;
  if (!rows || !rows.length) return null;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (!Array.isArray(r) || r.length !== 2 || typeof r[0] !== "string" || !DATE.test(r[0]) || !(num(r[1]) > 0)) return null;
    if (i && !(rows[i - 1][0] < r[0])) return null;
  }
  return rows;
}

export function indexSince(deck, idx, pxDate) {
  const rows = validRows(idx);
  if (!rows) return { ok: false, why: "noIndex" };
  const end = rows[rows.length - 1];
  if (!pxDate || end[0] !== pxDate || idx.asOf !== pxDate) return { ok: false, why: "end" };
  let w = 0, grown = 0, start = null;
  for (const p of (deck && deck.purchases) || []) {
    if (!p || !(p.qty > 0)) continue;
    const c = purchaseWon(p, deck.planFx);
    if (c == null) return { ok: false, why: "cost" };
    if (typeof p.date !== "string" || !DATE.test(p.date)) return { ok: false, why: "date" };
    const s = closeBefore(rows, p.date);
    if (!s) return { ok: false, why: "start" };               // bought before the 3 years of history
    w += c;
    grown += c * (end[1] / s[1]);
    if (start == null || p.date < start) start = p.date;
  }
  if (!(w > 0)) return { ok: false, why: "cost" };
  return { ok: true, ret: grown / w - 1, start, end: end[0] };
}

// ---------------- today's move of the whole deck ----------------
// From each held stock's d1 (change between official closes) and its value in the daily check. Left out (null) when
// any held stock has no d1 or no value there, and for a deck with US stocks: their d1 is in dollars and yesterday's
// exchange rate is not in the data.
export function deckDayChange(de) {
  if (!de || !de.ok || !de.weights || !de.weights.ok || !de.holdings.length) return null;
  let now = 0, prev = 0;
  for (const x of de.holdings) {
    const d1 = num(x.d1);
    if (d1 == null || x.cls === "us" || !(num(x.value) >= 0) || d1 <= -100) return null;
    now += x.value;
    prev += x.value / (1 + d1 / 100);
  }
  return prev > 0 ? (now / prev - 1) * 100 : null;
}

// ---------------- 추가로 넣을 돈 ----------------
// New money for one deck, in whole shares (Korean and US alike), most underweight name first.
//   de: evaluateDeck output · amountWon: the typed amount in won.
// Weights, targets and statuses are the daily check's own (rules.js): w and target are shares of the held stocks
// that have a weight band (targets rebased over what was actually bought), with its one-share rounding slack.
// Skipped: 규칙 깨짐, 확인 필요 and 지켜봐요 (no new money until the next report), anything above its 1.25x edge
// (그만 살 차례 · 줄일 차례: the statuses rules.js gives, and the same edge checked here so the two screens never
// disagree), and stocks without a target or a price. Planned stocks that were never bought (0 shares) are not in the
// daily check (no status: their rules were not read today), so they get nothing here either; de.unheld names them.
// Money left unspent never enters the deck, so it must not make a name look smaller than it will be:
// - the goal of each name is its target x the deck's value after the money that CAN go in. With skipped names, the
//   eligible ones can only grow until together they reach their combined target share (S below); the rest stays.
// - the 1.25x edge (band `bands[1]` from rules.js, the same edge 내 덱 shows) is checked against the running held
//   total (today's value + the money spent so far + the share being considered). Buying one name only lowers the
//   others' weights, so no bought name ends above its edge.
// A name is filled one share at a time, most underweight first, while that share still closes at least half its gap.
// -> { ok, buys: [{ t, nk, shares, cost }], spent, left, eligible, skipped, unheld, cheapest }
//   cheapest: the lowest share price among the eligible names (the screen says "금액을 늘려 보세요" only when even that
//   one share costs more than the amount; when the edges stop every buy, more money would not help).
export function addMoney(de, amountWon) {
  if (!de || !de.ok || !de.weights || !de.weights.ok) return { ok: false };
  const A = Math.floor(num(amountWon) || 0);
  const skipped = [];
  const rows = [];
  let total = 0;
  for (const x of de.holdings) if (num(x.target) > 0) total += num(x.value) || 0;   // the value the targets share
  for (const x of de.holdings) {
    const target = num(x.target), value = num(x.value), w = num(x.w);
    const px = x.qty > 0 && value > 0 ? value / x.qty : null;
    const hi = highEdge(x, target);
    if (NO_NEW_MONEY.includes(x.status)) { skipped.push({ t: x.t, why: x.status }); continue; }
    if (!(target > 0) || hi == null) { skipped.push({ t: x.t, why: "target" }); continue; }
    if (!(px > 0) || w == null) { skipped.push({ t: x.t, why: "price" }); continue; }
    if (w > hi + EPS) { skipped.push({ t: x.t, why: "high" }); continue; }
    rows.push({ t: x.t, nk: x.nk, px, value, target, hi, shares: 0 });
  }
  const out = { ok: true, buys: [], spent: 0, left: Math.max(0, A), eligible: rows.map((r) => r.t), skipped, unheld: de.unheld || [],
    cheapest: rows.length ? Math.min(...rows.map((r) => r.px)) : null };
  if (!(A > 0) || !rows.length || !(total > 0)) return out;
  const order = new Map(rows.map((r) => [r.t, r.value / (r.target * total)]));
  // S: what the eligible names can take before they hold their combined target share (tE = their targets' sum, vE
  // their value): vE + S = tE x (total + S). With nothing skipped (tE = 1) all of the amount can go in.
  const tE = rows.reduce((a, r) => a + r.target, 0), vE = rows.reduce((a, r) => a + r.value, 0);
  const S = tE >= 1 - 1e-9 ? A : Math.max(0, Math.min(A, (tE * total - vE) / (1 - tE)));
  const goalTotal = total + S;
  let left = A, held = total;                                    // held: today's value + what was bought so far
  for (let guard = 0; guard < 100000; guard++) {
    let best = null;
    for (const r of rows) {
      if (r.px > left + EPS) continue;
      if (r.value + r.px > r.hi * (held + r.px) + EPS) continue;          // never past the edge, at the running total
      if (r.target * goalTotal - r.value < r.px / 2 - EPS) continue;      // the share must close at least half its gap
      const ratio = r.value / (r.target * held);                 // most underweight first (weight now / target)
      if (!best || ratio < best.ratio - EPS || (Math.abs(ratio - best.ratio) <= EPS && r.t < best.r.t)) best = { r, ratio };
    }
    if (!best) break;
    best.r.shares += 1;
    best.r.value += best.r.px;
    left -= best.r.px;
    held += best.r.px;
  }
  out.buys = rows.filter((r) => r.shares > 0).sort((a, b) => order.get(a.t) - order.get(b.t) || (a.t < b.t ? -1 : 1))
    .map((r) => ({ t: r.t, nk: r.nk, shares: r.shares, cost: r.shares * r.px }));
  out.spent = out.buys.reduce((a, b) => a + b.cost, 0);
  out.left = A - out.spent;
  return out;
}

// What 추가로 넣을 돈 says when nothing can be bought: "none" = CSV 79 ("이 금액으로는 … 금액을 늘려 보세요"), only when
// even the cheapest eligible share costs more than the amount; "noneEligible" = every name is skipped, or the edges
// stop every buy (more money would not help). null when something is bought or no amount is typed.
export function addMessage(r, amountWon) {
  if (!r || !r.ok || !(amountWon > 0) || r.buys.length) return null;
  return r.eligible.length && r.cheapest > amountWon ? "none" : "noneEligible";
}

// ---------------- weight bands as 내 덱 shows them ----------------
// The band rule result of a held stock today (rules.js), when its edges were computed.
export const bandOf = (x) => ((x && x.rules) || []).find((r) => r && r.id === "band" && r.check === "checked" && r.result !== "missing"
  && Array.isArray(r.bands) && r.bands.length === 3) || null;
// Part C widens a stock's edges by the gap whole-share rounding left in the plan. Then "목표의 0.75~1.25배" is not the
// rule for that stock any more, so 내 덱 shows that general caption only when every held stock uses the plain edges.
export const plainEdges = (de) => ((de && de.holdings) || []).every((x) => {
  const b = bandOf(x);
  return !b || !Array.isArray(b.refBands) || b.bands.every((v, i) => Math.abs(v - b.refBands[i]) < 1e-9);
});

// ---------------- 오늘's counts ----------------
// held: the evaluated decks with holdings. Counts are of distinct stocks (a stock held in two decks is one stock).
// -> { todoTs: Set, rest, restCalm, allNone }   restCalm: every other stock is 할 일 없음 ("나머지 n종목은 이상 없어요")
//    allNone: every holding is 할 일 없음 (the eyebrow "오늘은 할 일이 없어요", REDESIGN 2.1 steps 1-3 all clear)
export function todayCounts(held) {
  const all = (held || []).flatMap((de) => de.holdings || []);
  const todoTs = new Set(all.filter((x) => x.status === "broken" || x.status === "check").map((x) => x.t));
  const rest = new Set(all.map((x) => x.t).filter((t) => !todoTs.has(t))).size;
  return { todoTs, rest, restCalm: rest > 0 && all.every((x) => todoTs.has(x.t) || x.status === "none"),
    allNone: all.length > 0 && all.every((x) => x.status === "none") };
}

// ---------------- 왜 움직였나: 규칙 n개가 모두 지켜지고 있어요 ----------------
// Counts only what was really checked today: rules shown in the rule book (shown: which optional rules have approved
// wording, { roe, op }) checked against a report newer than the purchase one (a rule whose only report is the purchase
// report has nothing new to compare), plus the weight band (checked every day). 0, so the line is left out, when the
// stock is not 할 일 없음, when any shown rule does not hold, or when nothing newer was checked at all.
export function keptCount(x, shown = {}) {
  if (!x || x.status !== "none") return 0;
  const rules = (x.rules || []).filter((r) => r && r.check === "checked" && r.kind !== "band" && r.result !== "na"
    && (r.id === "divCut" || r.id === "debtCeiling" || (r.id === "roeFloor" && shown.roe) || (r.id === "opDecline" && shown.op)));
  if (!rules.every((r) => r.result === "ok")) return 0;
  const band = (x.rules || []).find((r) => r && r.id === "band" && r.check === "checked");
  if (band && band.result !== "ok") return 0;
  return rules.filter((r) => r.newer === true).length + (band ? 1 : 0);
}

// The 1.25x edge rules.js used today for this holding (its band result: a share of the held value), or, for a hand-made
// evaluation without a band result, 1.25x the target.
function highEdge(x, target) {
  const b = (x.rules || []).find((r) => r && r.id === "band" && r.check === "checked" && r.result !== "missing");
  if (b && Array.isArray(b.bands) && num(b.bands[1]) > 0) return b.bands[1];
  return target > 0 && !(x.rules || []).some((r) => r && r.id === "band") ? ADD_CAP * target : null;
}

// ---------------- 왜 움직였나: the same industry today ----------------
// Every common share of the stock's own industry group in the same market with a d1 today (the stock itself always
// included). Only a real group (hasGroup: never "other" or "etc", never a missing group) with at least GROUP_MIN members.
// -> { ok: false, n } | { ok: true, n, fell, avg, together, items: [{ id, pct }] }
export function peerGroup(s, stocks) {
  if (!s || !hasGroup(s) || num(s.d1) == null || (s.cls !== "kr" && s.cls !== "us")) return { ok: false, n: 0 };
  const items = universe(stocks || [], s.cls).filter((x) => hasGroup(x) && x.ind === s.ind && num(x.d1) != null);
  if (!items.some((x) => x.t === s.t)) items.push(s);
  const n = items.length;
  if (n < GROUP_MIN) return { ok: false, n };
  const fell = items.filter((x) => x.d1 < 0).length;
  const avg = items.reduce((a, x) => a + x.d1, 0) / n;
  return { ok: true, n, fell, avg, together: s.d1 < 0 && fell >= TOGETHER_SHARE * n - EPS, items: items.map((x) => ({ id: x.t, pct: x.d1 })) };
}

// ---------------- Korean particle ----------------
// True when the name ends in a Hangul syllable with a final consonant (then the subject particle is the one in the
// approved sentence). Names ending in a vowel, Latin letters or digits return false: the screen then uses the other
// form or leaves the particle out.
export function endsInBatchim(name) {
  const s = String(name || "").trim();
  if (!s) return false;
  const c = s.charCodeAt(s.length - 1);
  return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0;
}
