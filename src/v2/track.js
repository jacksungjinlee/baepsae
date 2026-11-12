// ================= 2.0 tracking sheet and 왜 움직였나 (v18.3 Part E) =================
// Pure functions, no React and no Korean text: screens turn the results into copy from src/copy/v2.js.
// Spec: docs/tasks/v18.3-2.0-beta.md Part E; docs/REDESIGN.md section 3 (오늘 · 포트폴리오 · 왜 움직였나) and 4.1.
// Unit tests: tests/test_v2_track.py (run through Node).
//
// Everything here reads the daily evaluation from rules.js (evaluateDeck): its weights and targets, its statuses and its
// "ok: false" when the data is stale or failed. Nothing is computed from stale or failed data, and nothing is estimated:
// a number whose input is missing is left out (ok: false), never filled in.
import { num, hasGroup, universe, priceWon, todayD1 } from "./engine.js";
import { NO_NEW_MONEY } from "./rules.js";
import { pfRows } from "./pf.js";
import { ledger, recordSets, kospiMirror } from "./lots.js";

export const GROUP_MIN = 5;           // 같은 업종 점 띠: a real industry group with at least 5 members in the same market
export const TOGETHER_SHARE = 0.8;    // "같은 업종이 다 같이 빠졌어요": the stock fell and at least 80% of its group fell
export const ADD_CAP = 1.25;          // 추가로 넣을 돈 never takes a stock above its 1.25x edge (REDESIGN 4.1)
const EPS = 1e-9;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const warned = new Set();
const warnOnce = (msg) => { if (!warned.has(msg)) { warned.add(msg); console.warn(msg); } };   // a number left out is said once

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
// -> { ok: false, why } | { ok: true, value, cost, gain, ret, start, per: { t: { qty, value, cost, ret } }, noFx: [t], absent }
//   v19.6a (A.4): cost (원금) is the REMAINING won cost of the open lots (lots.js: moving average, a sale takes the same
//   fraction of every lot's cost), so 포트폴리오 and 내 수익 agree; gain and ret are the unrealized part. With no sale it is
//   the money put in, as before. cost / gain / ret are null when any held lot has no won cost (noFx names them). value is
//   today's value of every held share at today's official close (US at today's rate). Any held stock without a price
//   today: no value.
//   v19.0c: a held stock missing from today's data altogether is left out of every total (value, cost, return) and
//   listed in absent ([{ t, nk, cls, cost }], cost = its remaining money put in, null without a won cost); the screens
//   say so with the "빼고 계산했어요" line. Every other stock must still have a price.
export function deckMoney(deck, de, ctx) {
  if (!de || !de.ok || !ctx) return { ok: false, why: "day" };
  if (de.imported) return importedMoney(deck, ctx);
  return builtMoney(deck, de, ctx);
}

function builtMoney(deck, de, ctx) {
  const gone = new Set(de.absent || []);
  const absentOf = () => de.holdings.filter((x) => gone.has(x.t)).map((x) => ({ t: x.t, nk: x.nk, cls: x.cls, cost: heldCost(deck, x.t) }));
  // the missing stocks are named even when the totals cannot be made (never silent)
  const noPrice = () => ({ ok: false, why: "price", ...(gone.size ? { absent: absentOf() } : {}) });
  if (!de.weights || !(de.weights.ok || de.weights.paused)) return noPrice();
  const held = new Set(de.holdings.filter((x) => !gone.has(x.t)).map((x) => x.t));
  const per = {};
  let value = 0;
  for (const x of de.holdings) {
    if (gone.has(x.t)) continue;
    const s = ctx.byT.get(x.t);
    const px = s ? priceWon(s, ctx.fx) : null;
    if (!(px > 0) || !(x.qty > 0)) return noPrice();
    per[x.t] = { qty: x.qty, value: x.qty * px, cost: null, ret: null };
    value += x.qty * px;
  }
  const noFx = [];
  let start = null;
  for (const t of held) {
    const L = ledger(deck, t);
    const c = openCost(L, ctx.fx);
    if (c == null) { if (!noFx.includes(t)) noFx.push(t); continue; }
    per[t].cost = c;
  }
  for (const p of (deck && deck.purchases) || []) {
    if (!p || !(p.qty > 0) || !held.has(p.t)) continue;
    if (typeof p.date === "string" && DATE.test(p.date) && (start == null || p.date < start)) start = p.date;
  }
  for (const t of Object.keys(per)) {
    const r = per[t];
    r.ret = r.cost > 0 ? r.value / r.cost - 1 : null;
  }
  const cost = noFx.length ? null : Object.values(per).reduce((a, r) => a + r.cost, 0);
  const ok = cost != null && cost > 0;
  const absent = absentOf();
  if (!held.size) return { ok: false, why: "absent", absent };   // every held stock is missing from today's data: no totals
  return { ok: true, value, cost: ok ? cost : null, gain: ok ? value - cost : null, ret: ok ? value / cost - 1 : null, start, per, noFx, absent };
}
// The remaining won cost of a stock's open lots (lots.js), dollar-only lots at today's rate; null when any is unknown.
function openCost(L, fx) {
  let c = 0;
  for (const l of L.lots) {
    if (l.own == null) return null;
    if (l.usdOnly) { if (!(num(fx) > 0)) return null; c += l.own * fx; continue; }
    if (l.won == null) return null;
    c += l.won;
  }
  return c;
}

// v19.3d (v19.3 F.1): a portfolio made with 가진 종목 넣기, read explicitly: value = every held share (held.js: imported +
// 샀어요 − 팔았어요) at today's close (US at today's rate), plus a stock added by name only at its typed amount (frozen:
// it carries its own date, and the screens never show it as live). Money put in only when every holding has a 평균 단가
// (v19.6a: its open lots' remaining cost, lots.js; an imported row's typed 평균 단가 and the 샀어요 records): never a guess.
// A US 평균 단가 typed on an imported row has no rate of its own, so it is converted at today's rate (usdToday: v19.3
// Part H's line says so); a 샀어요 record keeps its own rate. A stock missing from today's data is left out of every total
// and listed (absent), as for a built portfolio.
function importedMoney(deck, ctx) {
  const v = pfRows(deck, ctx);
  const absent = v.rows.filter((r) => r.absent).map((r) => ({ t: r.t, nk: r.nk, cls: r.cls, cost: null }));
  const live = v.rows.filter((r) => !r.absent);
  if (!live.length) return { ok: false, why: "absent", absent };
  if (live.some((r) => !(r.value > 0))) return { ok: false, why: "price", ...(absent.length ? { absent } : {}) };
  const per = {}, noAvg = [];
  let value = 0, cost = 0, usdToday = false;
  for (const r of live) {
    value += r.value;
    const L = r.t ? ledger(deck, r.t) : null;
    const c = L && r.qty > 0 ? openCost(L, ctx.fx) : null;
    if (L && L.lots.some((l) => l.usdOnly)) usdToday = true;
    if (!(c > 0)) { noAvg.push(r.key); cost = null; }
    else if (cost != null) cost += c;
    if (r.t) per[r.t] = { qty: r.qty, value: r.value, cost: c > 0 ? c : null, ret: c > 0 ? r.value / c - 1 : null };
  }
  const ok = cost != null && cost > 0;
  return { ok: true, imported: true, value, cost: ok ? cost : null, gain: ok ? value - cost : null, ret: ok ? value / cost - 1 : null, start: null, per,
    noFx: [], noAvg, usdToday, frozen: live.filter((r) => r.frozen).map((r) => ({ nk: r.nk, date: r.date })), absent };
}

// The remaining money put in for one held stock (won: lots.js), or null when any of its lots has no won cost.
export function heldCost(deck, t) {
  const L = ledger(deck, t);
  if (!L.lots.length) return null;
  return openCost(L, null);
}

// The deck without the held stocks missing from today's data (for the KOSPI comparison over the same money).
export function withoutAbsent(deck, de) {
  const gone = new Set((de && de.absent) || []);
  if (!gone.size || !deck) return deck;
  const not = (r) => !(r && gone.has(r.t));
  return { ...deck, purchases: (deck.purchases || []).filter(not), ...(Array.isArray(deck.sales) ? { sales: deck.sales.filter(not) } : {}),
    ...(Array.isArray(deck.divs) ? { divs: deck.divs.filter(not) } : {}), holdings: (deck.holdings || []).filter(not) };
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

// v19.6a (A.5 [Q4]): with sales. Each lot's money buys KOSPI at the last close before its purchase date; a sale sells the
// same fraction of that stock's KOSPI units at the last close before the sale date (lots.kospiMirror). Mine = (value now
// + sale money) / money put in − 1; KOSPI = (units still held x today's close + money from units sold) / the same money − 1.
// Dividends stay out of both sides. A stock taken out (history) counts with what was sold before it left.
//   valueOf(t): today's won value of t's held shares (evaluateDeck's own value; null = unknown). Without it (a deck with no
//   sale), each held stock's value is not needed only when there is nothing held: callers pass it.
// -> { ok: true, ret (KOSPI), mine, start, end } | { ok: false, why }
export function indexSince(deck, idx, pxDate, valueOf = null) {
  const rows = validRows(idx);
  if (!rows) return { ok: false, why: "noIndex" };
  const end = rows[rows.length - 1];
  if (!pxDate || end[0] !== pxDate || idx.asOf !== pxDate) return { ok: false, why: "end" };
  const sets = recordSets(deck).filter((x) => x.history || (deck.holdings || []).some((h) => h && h.t === x.t)
    || ["purchases", "sales"].some((k) => (deck[k] || []).some((r) => r && r.t === x.t)));
  const k = kospiMirror(sets, rows, end, valueOf || (() => null), closeBefore);
  if (!k.ok) return k;
  return { ok: true, ret: k.kospi, mine: k.mine, start: k.start, end: k.end };
}

// ---------------- today's move of the whole deck ----------------
// From each held stock's d1 (change between official closes) and its value in the daily check. Left out (null) when
// any held stock has no d1 or no value there, and for a deck with US stocks: their d1 is in dollars and yesterday's
// exchange rate is not in the data. A held stock missing from today's data (v19.0c) is left out, as in deckMoney.
export function deckDayChange(de) {
  if (!de || !de.ok || !de.weights || !(de.weights.ok || de.weights.paused) || !de.holdings.length) return null;
  const gone = new Set(de.absent || []);           // v19.0c: missing from today's data, left out like every other total
  if (gone.size >= de.holdings.length) return null;
  let now = 0, prev = 0;
  for (const x of de.holdings) {
    if (gone.has(x.t)) continue;
    const d1 = num(x.d1);
    const v = num(x.value);                           // null >= 0 is true in JavaScript: test the value itself
    if (d1 == null || x.cls === "us" || v == null || v < 0 || d1 <= -100) return null;
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
// - the 1.25x edge (band `bands[1]` from rules.js, the same edge 포트폴리오 shows) is checked against the running held
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

// ---------------- weight bands as 포트폴리오 shows them ----------------
// The band rule result of a held stock today (rules.js), when its edges were computed.
export const bandOf = (x) => ((x && x.rules) || []).find((r) => r && r.id === "band" && r.check === "checked" && r.result !== "missing"
  && Array.isArray(r.bands) && r.bands.length === 3) || null;
// Part C widens a stock's edges by the gap whole-share rounding left in the plan. Then "목표의 0.75~1.25배" is not the
// rule for that stock any more, so 포트폴리오 shows that general caption only when every held stock uses the plain edges.
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
// -> { ok: false, n } | { ok: true, n, fell, rose, avg, together, togetherUp, items: [{ id, pct }] }
//   together: the stock fell and at least 80% of its group fell · togetherUp (v19.3e): the same on a rise
// v19.1c: a stock priced at an earlier close (pxd) has no change today (engine.todayD1): never in a group, never the one shown.
export function peerGroup(s, stocks) {
  const d1 = todayD1(s);
  if (!s || !hasGroup(s) || d1 == null || (s.cls !== "kr" && s.cls !== "us")) return { ok: false, n: 0 };
  const items = universe(stocks || [], s.cls).filter((x) => hasGroup(x) && x.ind === s.ind && todayD1(x) != null).map((x) => ({ t: x.t, d1: todayD1(x) }));
  if (!items.some((x) => x.t === s.t)) items.push({ t: s.t, d1 });
  const n = items.length;
  if (n < GROUP_MIN) return { ok: false, n };
  const fell = items.filter((x) => x.d1 < 0).length;
  const rose = items.filter((x) => x.d1 > 0).length;               // v19.3e: the company page's rise-day line (Part I)
  const avg = items.reduce((a, x) => a + x.d1, 0) / n;
  return { ok: true, n, fell, rose, avg, together: d1 < 0 && fell >= TOGETHER_SHARE * n - EPS,
    togetherUp: d1 > 0 && rose >= TOGETHER_SHARE * n - EPS, items: items.map((x) => ({ id: x.t, pct: x.d1 })) };
}

// ---------------- Korean subject particle (이 / 가) ----------------
// Jack, 2026-11-02: every 규칙 깨짐 title takes the right particle, never the name alone. Returns "i" (이) or "ga" (가),
// from the last letter or digit of the name, after trailing spaces and punctuation (. , ) ] & - ·) are dropped:
// - a Hangul syllable: a final consonant -> i, else ga;
// - a digit, read as Sino-Korean: 0 영 1 일 3 삼 6 육 7 칠 8 팔 -> i; 2 이 4 사 5 오 9 구 -> ga;
// - a Latin letter, read as its name: L 엘 M 엠 N 엔 R 알 -> i; every other letter -> ga;
// - names read as a word, not letter by letter (WORD_NAMES, every such Korean stock name in the data on 2026-11-02),
//   and an English last word read as a word (WORD_ENDINGS: Group 그룹).
const SINO_I = "013678";
const LETTER_I = "LMNR";
export const WORD_NAMES = { NAVER: "ga", SOOP: "i", SIMPAC: "i", "LS ELECTRIC": "i" };   // 네이버 · 숲 · 심팩 · 일렉트릭
export const WORD_ENDINGS = { GROUP: "i" };
export function subjectParticle(name) {
  const s = String(name || "").replace(/[\s.,)\]&\-\u00b7]+$/u, "");
  const up = s.toUpperCase();
  if (Object.prototype.hasOwnProperty.call(WORD_NAMES, up)) return WORD_NAMES[up];
  const last = up.split(/\s+/).pop();
  if (Object.prototype.hasOwnProperty.call(WORD_ENDINGS, last)) return WORD_ENDINGS[last];
  if (!s) return "ga";
  const ch = s[s.length - 1], c = s.charCodeAt(s.length - 1);
  if (c >= 0xac00 && c <= 0xd7a3) return (c - 0xac00) % 28 !== 0 ? "i" : "ga";
  if (/[0-9]/.test(ch)) return SINO_I.includes(ch) ? "i" : "ga";
  if (/[A-Za-z]/.test(ch)) return LETTER_I.includes(ch.toUpperCase()) ? "i" : "ga";
  return "ga";
}

// Object particle (을 / 를) for "{check}을 확인했어요" (Jack, 2026-11-03: one check ran, option (b), the particle matched
// to the word in front of it). 을 follows a final consonant and 를 does not: the same reading as 이 / 가.
export const objectParticle = (name) => (subjectParticle(name) === "i" ? "eul" : "reul");
