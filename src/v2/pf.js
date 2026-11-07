// ================= 가진 종목 넣기 · 내 포트폴리오 점검 · 포트폴리오 규칙 (v19.3d, v19.3 Parts F-G) =================
// Pure functions, no React and no Korean text: screens turn the results into copy from src/copy/v2.js.
// Unit tests: tests/test_v2_pf.py (run through Node).
//
// A portfolio made with 가진 종목 넣기 (store.js kind "imported") has no per-stock rule book, so only the four portfolio
// rules run on it (Part G): 한 종목 {stock}% 이하 · 한 업종 {ind}% 이하 · 내 기준 평균 상위 {top}% 안 · 재무 경고 0개.
// A rule that cannot be checked is "unknown" (확인하지 못했어요), never ok. Stale or failed data checks nothing.
// Principles kept here:
// - Held quantities come from held.js only (imported + 샀어요 − 팔았어요). Values at today's official close (US at
//   today's rate). A stock added by name only (not in the data) counts at its typed amount, which carries its own date.
// - Ranks are within each market (engine.percentileScores over that market's universe, the same numbers screen() uses).
//   A missing number is "blank" and "doesn't apply" (financial companies on 재무 안정) is "na": both are left out of
//   averages, and neither is ever an empty dot (an empty dot means "outside the top 50%").
// - 잘 맞아요 means what the build step means: every chosen 기준 in the top {top}% (screen()'s cut; 넉넉하게 uses 50%).
// - Stocks the 기준 cannot score (preferred shares, funds, US listings outside the universe, anything not in the data)
//   count in value, weights and the concentration rules, are left out of the 기준 averages, and are named.
// - Nothing is invented: no 평균 단가 is filled in, no quantity is guessed from a partial name, no number for a missing input.
import {
  num, CARDS, NA, universe, cardRaw, percentileScores, strictTop, hasGroup, annualDividend, fyOf, isStockLike,
} from "./engine.js";
import { R2022 } from "./y2022.js";
import { heldQty, byAmount, importedUnits } from "./held.js";
import { dayState } from "./rules.js";
import { warnings } from "./warn.js";

export const LIMITS = { stock: 30, ind: 35 };          // Part G defaults (%), editable per portfolio (store.js limits)
export const LOOSE_TOP = 50;                            // 넉넉하게 has no cut: the grouping and the 내 기준 rule use 50%
export const fitTop = (strict) => strictTop(strict) ?? LOOSE_TOP;
// Currency and market of a holding (v19.3d review): from the data's own currency, never from cls. data.json lists a
// KRX-listed fund on the S&P 500 (379800 KODEX 미국S&P500) with cls "us" but priced in won (no ccy): it is a Korean
// listing in won, whole shares. Only s.ccy "USD" is a dollar price.
export const usdOf = (s) => !!s && s.ccy === "USD";
export const marketKey = (s) => (usdOf(s) ? "us" : "kr");
export const wonPrice = (s, fx) => {
  const p = num(s && s.price);
  if (!(p > 0)) return null;
  if (!usdOf(s)) return p;
  return num(fx) > 0 ? p * fx : null;
};
export const BETA_SE_MAX = 0.5;                         // Part O.1: a beta error above this is not believed (PR #50's gate)
const EPS = 1e-9;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export const limitsOf = (deck) => ({ stock: num(deck && deck.limits && deck.limits.stock) ?? LIMITS.stock,
  ind: num(deck && deck.limits && deck.limits.ind) ?? LIMITS.ind });
export const activeOf = (points) => CARDS.filter((c) => !c.pending && (num(points && points[c.id]) || 0) > 0);

// ---------------- 평균 단가 ----------------
// The holding's average cost in its own currency: the imported row's 평균 단가 and the 샀어요 records, weighted by their
// quantities (sales do not change an average cost). null when any part of the holding has no price (an imported row
// without 평균 단가): never a guess.
export function avgOf(deck, t) {
  let q = 0, c = 0, ccy = null;
  for (const r of (deck && deck.imported) || []) {
    if (!r || r.t !== t) continue;
    const qty = r.qty != null ? num(r.qty) : (num(r.amountWon) > 0 && num(r.close) > 0 ? r.amountWon / (r.close * (r.ccy === "USD" ? num(r.fx) || NaN : 1)) : null);
    if (!(num(r.avg) > 0) || !(qty > 0)) return null;
    q += qty; c += qty * r.avg; ccy = r.ccy;
  }
  for (const p of (deck && deck.purchases) || []) {
    if (!p || p.t !== t || !(p.qty > 0) || !(num(p.price) > 0)) continue;
    if (ccy && p.ccy !== ccy) return null;
    q += p.qty; c += p.qty * p.price; ccy = p.ccy;
  }
  return q > 0 && ccy ? { avg: c / q, ccy } : null;
}

// ---------------- values and weights ----------------
// One row per held stock (held.js) plus one per stock added by name only.
// -> { rows: [{ key, t, nk, cls, s, qty, px, value, w, absent, frozen, date, byAmount, ccy }], total, ok, missing, absent }
//   ok: every row has a value today (else no weights: the rules that need them are unknown). missing: in the data but no
//   price today. absent: not in today's data at all.
export function pfRows(deck, ctx) {
  const rows = [], missing = [], absent = [];
  const byT = (ctx && ctx.byT) || new Map();
  const names = new Map(((deck && deck.holdings) || []).map((h) => [h.t, h]));
  for (const [t, qty] of heldQty(deck || {})) {
    const h = names.get(t) || {};
    const s = byT.get(t) || null;
    const px = s ? wonPrice(s, ctx && ctx.fx) : null;
    const imp = ((deck && deck.imported) || []).find((r) => r && r.t === t) || null;
    const row = { key: t, t, nk: (s && s.nk) || h.nk || t, cls: (s && s.cls) || h.cls || null, usd: s ? usdOf(s) : !!imp && imp.ccy === "USD", s, qty, px: px > 0 ? px : null,
      value: px > 0 ? qty * px : null, w: null, absent: !s, frozen: false, date: null, byAmount: byAmount(imp), ccy: imp ? imp.ccy : null };
    if (!s) absent.push(t); else if (!(px > 0)) missing.push(t);
    rows.push(row);
  }
  ((deck && deck.imported) || []).forEach((r, i) => {
    if (!r || r.t != null || !(num(r.amountWon) > 0)) return;
    rows.push({ key: "name:" + i, t: null, nk: r.nk, cls: null, s: null, qty: null, px: null, value: r.amountWon, w: null, absent: false,
      frozen: true, date: r.date || null, byAmount: true, ccy: "KRW" });
  });
  const ok = rows.length > 0 && rows.every((r) => r.value != null && r.value > 0);
  const total = ok ? rows.reduce((a, r) => a + r.value, 0) : null;
  if (ok) for (const r of rows) r.w = r.value / total;
  return { rows, total, ok, missing, absent };
}

// ---------------- 기준 ranks (Part G 1-3) ----------------
const uniMemo = new WeakMap();
function marketScores(stocks, mk, card) {
  let m = uniMemo.get(stocks);
  if (!m) { m = new Map(); uniMemo.set(stocks, m); }
  const k = mk + "|" + card.id;
  if (!m.has(k)) {
    const uni = universe(stocks, mk);
    m.set(k, { set: new Set(uni.map((s) => s.t)), sc: percentileScores(uni, card) });
  }
  return m.get(k);
}
const inUni = (stocks, s) => !!s && (s.cls === "kr" || s.cls === "us") && marketScores(stocks, s.cls, CARDS[0]).set.has(s.t);

// "상위 x%" of one score (engine screen(): 100 − score, the side its cut compares).
export const topShare = (sc) => 100 - sc;
// What a 상위 % shows: whole %, at least 1 (상위 0% means nothing). The 내 기준 rule compares this shown number.
export const shownTop = (x) => Math.max(1, Math.round(x));

// Per row and chosen 기준: { st: "num", sc, top } | { st: "na" } | { st: "blank" }; scored = in its market's universe.
// fit (잘 맞아요): scored, no blank, a number on at least one chosen 기준, and each number in the top {top}% (fitTop).
// -> { cards: [{ id, pts }], top, per: Map key -> { scored, cells, fit }, avg: { id: { x, shown } | null }, fit: [row],
//      less: [row], unscored: [row] }
export function cardStats(rows, stocks, settings) {
  const pts = (settings && settings.points) || {};
  const cards = activeOf(pts).map((c) => ({ id: c.id, pts: pts[c.id] }));
  const top = fitTop(settings && settings.strict);
  const per = new Map(), fit = [], less = [], unscored = [];
  for (const r of rows) {
    const scored = !!r.s && inUni(stocks, r.s) && isStockLike(r.s);
    const cells = {};
    let blank = false, cut = false, nums = 0;
    for (const c of cards) {
      if (!scored) { cells[c.id] = { st: "blank" }; continue; }
      const card = CARDS.find((x) => x.id === c.id);
      const raw = cardRaw(r.s, card);
      if (raw === NA) { cells[c.id] = { st: "na" }; continue; }
      const sc = raw == null ? null : marketScores(stocks, r.s.cls, card).sc.get(r.s.t);
      if (sc == null) { cells[c.id] = { st: "blank" }; blank = true; continue; }
      cells[c.id] = { st: "num", sc, top: topShare(sc) };
      nums++;
      if (!(sc > 100 - top + EPS)) cut = true;
    }
    const isFit = scored && cards.length > 0 && !blank && nums > 0 && !cut;
    per.set(r.key, { scored, cells, fit: isFit });
    if (!scored) unscored.push(r);
    else if (cards.length) (isFit ? fit : less).push(r);
  }
  return { cards, top, per, avg: averages(rows, per, cards), fit, less, unscored };
}

// Weighted average 상위 % per chosen 기준 over the rows with a number on it (weights renormalised among them).
// weights: Map key -> weight (default: each row's w). null for a 기준 no row has a number on.
export function averages(rows, per, cards, weights = null) {
  const out = {};
  for (const c of cards) {
    let ws = 0, s = 0;
    for (const r of rows) {
      const cell = per.get(r.key) && per.get(r.key).cells[c.id];
      const w = weights ? weights.get(r.key) : r.w;
      if (!cell || cell.st !== "num" || !(w > 0)) continue;
      ws += w; s += w * cell.top;
    }
    out[c.id] = ws > 0 ? { x: s / ws, shown: shownTop(s / ws) } : null;
  }
  return out;
}

// Per-stock dot (종목별로 보면): full = top 30%, half = top 50%, empty = the rest; blank (–, 데이터 없음) and na (해당 없음)
// are never an empty dot.
export function dotOf(cell) {
  if (!cell || cell.st === "blank") return "blank";
  if (cell.st === "na") return "na";
  return cell.sc > 70 + EPS ? "full" : cell.sc > 50 + EPS ? "half" : "empty";
}

// ---------------- 재무 경고 (one holding) ----------------
// The company page's own function (warn.js warnings), so the two screens always agree: "flag" when a check fired, "clear"
// only when the company page says 재무 경고 신호는 없어요 (every check ran or does not apply), else "unknown" (US holdings,
// funds, a check that did not run: the company page's partial line is not a full clear either).
export function warnOf(s, co) {
  if (!s || s.etf === true || s.fund) return "unknown";
  const w = warnings(s, co);
  if (w.flags && w.flags.length) return "flag";
  return w.allRan ? "clear" : "unknown";
}

// ---------------- the four portfolio rules ----------------
// deck: an imported portfolio · ctx: rules.todayCtx · stocks: data.json stocks (ranks).
// -> { ok: false, why, days } when the data cannot be used today (stale / failed: nothing is checked, never a ✓), else
//    { ok: true, view: pfRows, stats: cardStats, rules: [{ id, state: "ok" | "broken" | "unknown", ... }], kept, checked,
//      unchecked, broken: first broken rule or null }
//   stock: { limit, max: { t, nk, w } }        ind: { limit, top: { ind, name, w, names }, none: [names] }
//   fit:   { limit (top), avg, cards }          warn: { flagged: [names], unknown: [names] }
export function pfState(deck, ctx, stocks) {
  const state = ctx && ctx.state ? ctx.state : { ok: false, why: "loading" };
  if (!state.ok) return { ok: false, why: state.why, days: state.days ?? null };
  const view = pfRows(deck, ctx);
  const stats = cardStats(view.rows, stocks || [], deck && deck.settings);
  const lim = limitsOf(deck);
  const rules = [];
  // 1. 한 종목 {x}% 이하
  if (!view.ok) rules.push({ id: "stock", state: "unknown", limit: lim.stock });
  else {
    const m = view.rows.reduce((a, r) => (!a || r.w > a.w + EPS ? r : a), null);
    rules.push({ id: "stock", state: m.w * 100 <= lim.stock + EPS ? "ok" : "broken", limit: lim.stock, max: { t: m.t, nk: m.nk, w: m.w } });
  }
  // 2. 한 업종 {x}% 이하 (stocks with no group are left out of this rule and named)
  const ind = industryView(view);
  if (!view.ok || !ind.groups.length) rules.push({ id: "ind", state: "unknown", limit: lim.ind, none: ind.none.rows.map((r) => r.nk) });
  else {
    const g = ind.groups[0];
    rules.push({ id: "ind", state: g.w * 100 <= lim.ind + EPS ? "ok" : "broken", limit: lim.ind,
      top: { ind: g.ind, name: g.name, w: g.w, names: g.rows.map((r) => r.nk) }, none: ind.none.rows.map((r) => r.nk) });
  }
  // 3. 내 기준 평균 상위 {top}% 안: every chosen 기준's weighted average within the strictness (넉넉하게: 50%)
  const avgs = stats.cards.map((c) => stats.avg[c.id]);
  if (!view.ok || !stats.cards.length || avgs.some((a) => a == null)) rules.push({ id: "fit", state: "unknown", limit: stats.top });
  else rules.push({ id: "fit", state: avgs.every((a) => a.shown <= stats.top) ? "ok" : "broken", limit: stats.top, avg: stats.avg, cards: stats.cards });
  // 4. 재무 경고 0개 (Korean holdings with every check run; any US holding or missing check makes it unknown)
  const flagged = [], unknown = [];
  for (const r of view.rows) {
    const w = warnOf(r.s, r.t && ctx.coByT ? ctx.coByT.get(r.t) || null : null);
    if (w === "flag") flagged.push(r.nk); else if (w === "unknown") unknown.push(r.nk);
  }
  rules.push({ id: "warn", state: flagged.length ? "broken" : unknown.length ? "unknown" : "ok", flagged, unknown });
  const kept = rules.filter((x) => x.state === "ok").length;
  const checked = rules.filter((x) => x.state !== "unknown").length;
  return { ok: true, pxDate: ctx.pxDate || null, view, stats, ind, rules, kept, checked, unchecked: rules.length - checked,
    broken: rules.find((x) => x.state === "broken") || null };
}

// ---------------- 어느 업종에 몰려 있나요? ----------------
// Groups by the v17.5.1 industry group (US stocks use the same groups), largest first; stocks with no group go to
// "업종 정보 없음" (none). Each group's rows largest first. Weights only when every row has a value (view.ok).
export function industryView(view) {
  const by = new Map(), none = { w: 0, rows: [] };
  for (const r of view.rows) {
    if (r.s && hasGroup(r.s)) {
      if (!by.has(r.s.ind)) by.set(r.s.ind, { ind: r.s.ind, name: r.s.indName || null, w: 0, rows: [] });
      const g = by.get(r.s.ind);
      g.w += r.w || 0; g.rows.push(r);
    } else { none.w += r.w || 0; none.rows.push(r); }
  }
  const order = (a, b) => (b.w || 0) - (a.w || 0);
  const groups = [...by.values()].sort((a, b) => order(a, b) || (a.ind < b.ind ? -1 : 1));
  for (const g of groups) g.rows.sort(order);
  none.rows.sort(order);
  return { groups, none };
}

// A treemap of positive values in the box (x, y, w, h): squarified (Bruls et al.), items in the given order.
// -> [{ key, x, y, w, h }]
export function squarify(items, x, y, w, h) {
  const list = items.filter((it) => it.v > 0);
  const total = list.reduce((a, it) => a + it.v, 0);
  if (!list.length || !(total > 0) || !(w > 0) || !(h > 0)) return [];
  const scale = (w * h) / total;
  const areas = list.map((it) => ({ key: it.key, a: it.v * scale }));
  const out = [];
  let bx = x, by = y, bw = w, bh = h, i = 0;
  const worst = (row, side) => {
    const s = row.reduce((a, r) => a + r.a, 0), mx = Math.max(...row.map((r) => r.a)), mn = Math.min(...row.map((r) => r.a));
    return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
  };
  while (i < areas.length) {
    const side = Math.min(bw, bh);
    const row = [areas[i++]];
    while (i < areas.length && worst([...row, areas[i]], side) <= worst(row, side)) row.push(areas[i++]);
    const s = row.reduce((a, r) => a + r.a, 0);
    if (bw >= bh) {                                        // a column on the left
      const cw = s / bh;
      let cy = by;
      for (const r of row) { const rh = r.a / cw; out.push({ key: r.key, x: bx, y: cy, w: cw, h: rh }); cy += rh; }
      bx += cw; bw -= cw;
    } else {                                               // a row on top
      const rh = s / bw;
      let cx = bx;
      for (const r of row) { const rw = r.a / rh; out.push({ key: r.key, x: cx, y: by, w: rw, h: rh }); cx += rw; }
      by += rh; bh -= rh;
    }
  }
  return out;
}

// ---------------- 이 포트폴리오로 2022년을 보냈다면? (Part G 5, Part O.1) ----------------
// Per holding: its market's 2022 fall (y2022.js: Korea −24.9%, US in won −14.7%) × its β low and × its β high (β ∓ 2 ×
// betaSE); the cushion ETFs use their real 2022 result (no band). Each end added up by weight over the holdings with a
// figure; holdings without β (or a β error above 0.5) are left out (out: names, share: their weight).
// -> { ok: false, why: "none" | "half", share, out } | { ok: true, est: "range" | "one" | "uncertain", small, big (whole %,
//    size of the fall, smaller first), amountSmall, amountBig (won), share, out, known }
export function range2022(view, R = R2022) {
  if (!view.ok) return { ok: false, why: "none", share: 1, out: [] };
  let lo = 0, hi = 0, known = 0;
  const out = [];
  for (const r of view.rows) {
    const s = r.s;
    let a = null, b = null;
    if (s && (s.cls === "kr" || s.cls === "us") && !s.etf && !s.fund && num(s.beta) != null && num(s.betaSE) != null && s.betaSE <= BETA_SE_MAX) {
      const m = s.cls === "kr" ? R.kr : R.usWon;
      a = m * (s.beta - 2 * s.betaSE); b = m * (s.beta + 2 * s.betaSE);
    } else if (s && R.etf && num(R.etf[s.t]) != null) { a = R.etf[s.t]; b = R.etf[s.t]; }
    if (a == null) { out.push(r.nk); continue; }
    lo += r.w * Math.max(a, b); hi += r.w * Math.min(a, b);      // the market fell: the high β gives the bigger fall
    known += r.w;
  }
  const share = Math.max(0, 1 - known);
  if (!(known > 0)) return { ok: false, why: "none", share, out };
  if (share > 0.5 + EPS) return { ok: false, why: "half", share, out };
  const fSmall = -lo / known, fBig = -hi / known;                // size of the fall over the holdings with a figure
  const small = Math.round(fSmall * 100), big = Math.round(fBig * 100);
  const value = view.total * known;
  if (!(small > 0)) return { ok: true, est: "uncertain", share, out, known };
  return { ok: true, est: small === big ? "one" : "range", small, big, fSmall, fBig, amountSmall: value * fSmall, amountBig: value * fBig, share, out, known };
}

// ---------------- 1년 배당 (Part G 6) ----------------
// engine.annualDividend over the held quantities (Korea: the PR #49 rules; US: Yahoo's current dividend rate × value).
// A stock added by name only has no data: it counts as unknown. -> { won, unknown, unchecked, us }
export function dividendYear(view, fx, coByT) {
  const rows = view.rows.filter((r) => r.s && r.qty > 0 && r.value > 0).map((r) => ({ s: r.s, shares: r.qty, cost: r.value }));
  const d = annualDividend(rows, fx, coByT);
  const extra = view.rows.filter((r) => !r.s || !(r.value > 0)).length;
  return { ...d, unknown: d.unknown + extra, us: rows.some((r) => usdOf(r.s)) };
}

// ---------------- 비중을 바꿔 보면 (Part G 7) ----------------
// The user moved one holding to weight w (0-1): the others keep their proportions in what is left. Never suggests a
// change by itself. -> Map key -> weight
export function moveWeight(weights, key, w) {
  const cur = weights.get(key);
  if (cur == null || !Number.isFinite(w)) return weights;
  const x = Math.min(1, Math.max(0, w));
  const rest = 1 - cur;
  const out = new Map();
  for (const [k, v] of weights) out.set(k, k === key ? x : rest > EPS ? (v / rest) * (1 - x) : (1 - x) / Math.max(1, weights.size - 1));
  return out;
}

// ---------------- the report's date line ----------------
// { md: the Korean close date, krYear: the one 사업보고서 year every scored Korean holding shares (else null), us: any US }
export function reportDates(view, ctx, coByT) {
  const ys = new Set();
  for (const r of view.rows) if (r.s && r.s.cls === "kr" && isStockLike(r.s)) { const y = fyOf(r.s, coByT ? coByT.get(r.t) || null : null); if (y != null) ys.add(y); }
  return { pxDate: ctx.pxDate || null, krYear: ys.size === 1 ? [...ys][0] : null, us: view.rows.some((r) => r.usd) };
}

// ---------------- 가진 종목 넣기: search and paste ----------------
const norm = (x) => String(x || "").trim();
const listed = (s) => !!s && typeof s.t === "string" && (s.cls === "kr" || s.cls === "us" || s.cls === "bond" || s.cls === "metal");
// Korean and US listings and the bond / gold funds in the data: exact code or name first, then starts-with, then contains;
// larger market cap first within each group (a blank cap last). n results.
export function findStocks(stocks, q, n = 8) {
  const query = norm(q);
  if (!query) return [];
  const up = query.toUpperCase();
  const g = [[], [], []];
  for (const s of stocks || []) {
    if (!listed(s)) continue;
    const t = s.t.toUpperCase(), nk = String(s.nk || ""), ne = String(s.ne || "").toUpperCase();
    if (t === up || nk === query || ne === up) g[0].push(s);
    else if (t.startsWith(up) || nk.startsWith(query) || ne.startsWith(up)) g[1].push(s);
    else if (nk.includes(query) || ne.includes(up)) g[2].push(s);
  }
  const cap = (s) => (num(s.cap) != null ? s.cap : -1);
  return g.flatMap((x) => x.sort((a, b) => cap(b) - cap(a))).slice(0, n);
}
// The one stock a name or code means exactly (code, Korean name or English name, any case), or null.
function exact(stocks, q) {
  const query = norm(q), up = query.toUpperCase();
  if (!query) return null;
  const hits = (stocks || []).filter((s) => listed(s) && (s.t.toUpperCase() === up || s.nk === query || String(s.ne || "").toUpperCase() === up));
  return hits.length === 1 ? hits[0] : hits.find((s) => s.t.toUpperCase() === up) || null;
}

// A quantity token: 1234 · 1,234 (thousands groups of 3) · 12.5 · with the share unit after it (unit: the words after
// {n} in C.plan.shares, passed in by the screen: no Korean in this file). null if not one.
const QTY = /^(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?$/;
const hasDigit = (x) => /\d/.test(x);
let UNIT_WORD = "";
const bare = (tok) => (UNIT_WORD && tok.endsWith(UNIT_WORD) ? tok.slice(0, -UNIT_WORD.length) : tok);
function qtyOf(tok) {
  const m = QTY.exec(bare(tok));
  if (!m) return null;
  const v = Number(m[1].replace(/,/g, "") + (m[2] ? "." + m[2] : ""));
  return Number.isFinite(v) ? { v, dec: m[2] ? m[2].length : 0 } : null;
}
// Split one pasted line: tabs or spaces; a comma that is not a thousands separator splits too ("삼성전자,10").
function tokens(line) {
  const out = [];
  for (const raw of line.split(/[\t ]+/)) {
    const t = raw.replace(/^[,;]+|[,;]+$/g, "");
    if (!t) continue;
    if (t.includes(",") && !QTY.test(bare(t))) out.push(...t.split(",").map((x) => x.trim()).filter(Boolean));
    else out.push(t);
  }
  return out;
}

// One stock per line, its name or code, then its quantity. Nothing is added until the user confirms the preview.
// -> [{ line (1-based), text, st: "ok" | "noStock" | "noQty" | "pick", s?, qty?, q?, choices? }] (empty lines skipped)
//   noStock: no stock matches · noQty: no single clear quantity (none, several numbers, a fraction of a Korean share, more
//   than 4 decimals, 0) · pick: a partial name two or more stocks match (never guessed: the user picks one; q = the words).
export function parsePaste(text, stocks, unit = "") {
  UNIT_WORD = typeof unit === "string" ? unit.trim() : "";
  const out = [];
  String(text || "").split(/\r?\n/).forEach((raw, i) => {
    const line = raw.trim();
    if (!line) return;
    const toks = tokens(line);
    let s = null, rest = [];
    for (let k = toks.length; k >= 1 && !s; k--) {             // the longest exact name or code at the start of the line
      const hit = exact(stocks, toks.slice(0, k).join(" "));
      if (hit) { s = hit; rest = toks.slice(k); }
    }
    const base = { line: i + 1, text: line };
    if (!s) {
      const k0 = toks.findIndex((x) => qtyOf(x) != null);
      const words = (k0 < 0 ? toks : toks.slice(0, k0)).join(" ");
      const cands = words ? findStocks(stocks, words, 50).filter((x) => x.nk.includes(words) || String(x.ne || "").toUpperCase().includes(words.toUpperCase())
        || x.t.toUpperCase().startsWith(words.toUpperCase())) : [];
      if (!cands.length) { out.push({ ...base, st: "noStock" }); return; }
      rest = k0 < 0 ? [] : toks.slice(k0);
      if (cands.length > 1) {
        const q = qtyFrom(rest, null);
        out.push({ ...base, st: "pick", q: words, choices: cands.slice(0, 6), qty: q });
        return;
      }
      s = cands[0];
    }
    const qty = qtyFrom(rest, s);
    out.push(qty == null ? { ...base, st: "noQty", s } : { ...base, st: "ok", s, qty });
  });
  return out;
}
// The single quantity among the rest of a line, or null (none, or more than one number). A stock's own code repeated
// on the line is not a quantity. s null: the market is not known yet (decimals checked when the user picks).
function qtyFrom(rest, s) {
  const nums = rest.filter((x) => hasDigit(x) && !(s && x.toUpperCase() === s.t.toUpperCase()));
  if (nums.length !== 1) return null;
  const q = qtyOf(nums[0]);
  if (!q || !(q.v > 0)) return null;
  return okQty(q.v, s) ? q.v : null;
}
// A won-priced listing (Korea, the Korean funds, 379800 too): whole shares. A dollar listing: up to 4 decimals.
export function okQty(v, s) {
  if (!Number.isFinite(v) || !(v > 0)) return false;
  if (s && !usdOf(s)) return Number.isInteger(v);
  return Math.abs(v * 10000 - Math.round(v * 10000)) < 1e-6;
}

// ---------------- the portfolio saved by 매일 점검 시작하기 ----------------
// drafts: [{ t, mode: "qty" | "amount", qty, amountWon, avg }] (avg null = not given: never filled in).
// load: today's data (close, date and rate for amounts). -> the deck record (store.js validates it before saving).
export function importedRecord({ drafts, load, settings, id, name, today }) {
  const fx = num(load.data.fx);
  const holdings = [], imported = [];
  for (const d of drafts) {
    const s = load.byT.get(d.t);
    if (!s || holdings.some((h) => h.t === d.t)) continue;
    const ccy = usdOf(s) ? "USD" : "KRW";
    holdings.push({ t: s.t, nk: s.nk, cls: s.cls, ind: hasGroup(s) ? s.ind : null });
    const scored = (s.cls === "kr" || s.cls === "us") && inUni(load.data.stocks, s) && isStockLike(s);
    const base = { t: s.t, nk: s.nk, ccy, ...(num(d.avg) > 0 ? { avg: d.avg } : {}), ...(scored ? {} : { unscored: true }) };
    if (d.mode === "amount") {
      const date = usdOf(s) ? (DATE.test(s.pxd || "") ? s.pxd : load.data.usPxDate) : load.data.pxDate;
      imported.push({ ...base, amountWon: d.amountWon, close: s.price, date, ...(ccy === "USD" ? { fx } : {}) });
    } else imported.push({ ...base, qty: d.qty });
  }
  const st = settings || {};
  return { id, name, createdAt: today, pxDate: load.data.pxDate, kind: "imported",
    settings: { points: { ...(st.points || {}) }, strict: st.strict || "normal" }, holdings, purchases: [], imported };
}

// A draft is ready only when the record it makes passes store.js: a valid quantity, or an amount worth at least
// 1/10,000 share at today's close (a dollar listing also needs today's rate), and today's price.
export function draftOk(d, s, fx = null) {
  if (!s || !(num(s.price) > 0)) return false;
  if (d.mode === "amount") {
    if (!(num(d.amountWon) > 0)) return false;
    const usd = usdOf(s);
    if (usd && !(num(fx) > 0)) return false;
    return importedUnits({ t: s.t, amountWon: d.amountWon, close: s.price, ccy: usd ? "USD" : "KRW", ...(usd ? { fx } : {}) }) != null;
  }
  return okQty(num(d.qty), s);
}

// ---------------- state of the whole store's imported portfolios (홈 · 포트폴리오) ----------------
export const isImported = (deck) => !!deck && deck.kind === "imported";
// A 가진 종목 portfolio holding a dollar listing today (for "미국 종목은 현지 기준 {md} 종가예요.").
export const usHeld = (deck, load) => isImported(deck) && !!load && load.status === "ok" && [...heldQty(deck).keys()].some((t) => usdOf(load.byT.get(t)));
// Only for tests and the console: the portfolio rules' one-line summary.
export const summary = (st) => (st && st.ok ? `${st.kept}/${st.checked} kept, ${st.unchecked} unchecked` : `not checked (${st && st.why})`);
export { dayState };
