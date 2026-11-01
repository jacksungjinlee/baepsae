// ================= 2.0 deck engine (v18.3 Part B) =================
// Pure functions, no React and no Korean text: screens turn the codes returned here into copy from src/copy/v2.js.
// Spec: docs/tasks/v18.3-2.0-beta.md Part B; sizing docs/REDESIGN.md section 4.3; rules section 4.2 + Part C table.
// Unit tests: tests/test_v2_engine.py (run through Node).
//
// Principles kept here:
// - Rank within each market (KR and US separately). Never rank by a blank: a stock blank on any card that has points
//   is left out and counted. "Not applicable" (financial companies on the stability card) is not a blank.
// - A missing industry group is never treated as one group (no shared cap, no "max 2" between ungrouped stocks).
// - Limits are never relaxed silently: settings that cannot all hold return { ok: false, clash: [...] }.
// - No estimates for missing inputs: features whose data is missing are switched off by the screens.

import { R2022 } from "./y2022.js";

export const NA = "na";                                        // card does not apply to this stock (not a blank)
// Financial companies (stability card "해당 없음", no debt-ratio rules). The data contract (v17.5.1) fixes this set;
// "fin" is the umbrella group 금융 that small financial groups merge into. Change it here only.
export const FINANCIAL_INDS = ["bank", "insurance", "securities", "finance", "fin"];
export const HOLDING_IND = "holding";
export const LIQ_FLOOR_EOK = 5;          // 5억원 of 20-day average trading value (KR val20; US val is a 3-month average)
export const LIQ_SHARE = 0.1;            // a position may be at most 10% of one day's average trading value
export const IND_CAP = 1 / 3;            // one industry group at most 1/3 of the deck
export const MAX_PER_IND = 2;            // at most 2 stocks per industry group
export const TILT = [0.6, 1.4];          // tilts stay within 0.6-1.4x of an equal weight
export const BANDS = [0.75, 1.25, 1.4];  // weight bands (REDESIGN 4.1)
export const MIN_PER_STOCK_MAN = 20;     // step 4: warn when the amount gives less than 20만원 per stock
// Debt ratio rules apply to Korean company shares only: KR debt = liabilities / equity (DART), while US debt is
// debt / equity (Yahoo), a different ratio. The US label waits for Jack's wording (pending strings).
export const DEBT_CAUTION = 100;         // 주의할 점: debt ratio above 100% (KR, not financials)
export const DEBT_EXCLUDE = 200;         // 빼기 switch: debt ratio above 200% (KR, not financials)
export const hasKrDebt = (s) => s.cls === "kr" && !isFin(s) && num(s.debt) != null;
export const CUSHION_ASSETS = [{ t: "114260", share: 0.5 }, { t: "132030", share: 0.5 }]; // KODEX KTB 3Y, KODEX gold futures (H)
export const PINNED_MAX = 3;
export const COUNT_RANGE = [5, 30];
const EPS = 1e-9;

// Catch-all ids are never an industry group (no peer comparison, no shared cap, no "max 2").
export const NOT_GROUPS = ["etc", "other"];

export const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
export const hasGroup = (s) => typeof s.ind === "string" && s.ind.length > 0 && !NOT_GROUPS.includes(s.ind);
export const isFin = (s) => hasGroup(s) && FINANCIAL_INDS.includes(s.ind);
export const isPreferred = (s) => s.cls === "kr" && typeof s.t === "string" && !s.t.endsWith("0");  // KRX: common shares end in 0
export const isStockLike = (s) => (s.cls === "kr" || s.cls === "us") && !s.fund && s.etf !== true;
export const inUniverse = (s) => isStockLike(s) && !isPreferred(s) && num(s.price) > 0;

// ---------------- settings ----------------
export const CARDS = [
  { id: "value", field: { kr: "vz", us: "vz" }, dir: 1 },
  { id: "div", field: { kr: "divYield", us: "dy" }, dir: 1 },
  { id: "divGrowth", pending: true },
  { id: "growth", field: { kr: "g3", us: "g3" }, dir: 1 },
  { id: "profit", field: { kr: "roe", us: "roe" }, dir: 1 },
  { id: "stable", field: { kr: "debt", us: "debt" }, dir: -1, finNA: true },
  { id: "lowVol", field: { kr: "lz", us: "lz" }, dir: 1 },
  { id: "trend", field: { kr: "mz", us: "mz" }, dir: 1 },
  { id: "payout", pending: true },
  { id: "large", field: { kr: "cap", us: "cap" }, dir: 1 },
];
export const POINTS_TOTAL = 10;
export const POINTS_MAX = 5;

// Starting decks: points from Jack's mockup (spec table). hidden = not shown in the beta.
export const DECKS = [
  { id: "steadyDiv", points: { div: 4, divGrowth: 3, stable: 2, lowVol: 1 }, hidden: true },   // needs 배당 성장
  { id: "deepValue", points: { value: 5, stable: 3, profit: 2 } },
  { id: "garp", points: { growth: 4, value: 3, profit: 3 } },
  { id: "quality", points: { profit: 4, stable: 3, large: 3 } },
  { id: "cheapQuality", points: { profit: 5, value: 5 }, hidden: true },                     // until 가치 includes PER
  { id: "strict", points: { profit: 4, value: 3, stable: 3 }, strict: "strict" },
  { id: "lowVol", points: { lowVol: 4, stable: 3, div: 3 } },
  { id: "trend", points: { trend: 5, growth: 3, profit: 2 } },
  { id: "payout", points: { payout: 4, value: 3, div: 3 }, hidden: true },
  { id: "theme", points: { growth: 3, trend: 3, profit: 2, stable: 2 }, hidden: true },     // needs themes
  { id: "krUs", points: { profit: 3, value: 2, div: 2, stable: 2, lowVol: 1 }, mix: "k55" },
  { id: "income", points: { div: 5, stable: 3, lowVol: 2 } },
  { id: "divGrowth", points: { divGrowth: 5, profit: 3, stable: 2 }, hidden: true },
];
export const STRICT = [{ id: "loose", top: null }, { id: "normal", top: 50 }, { id: "strict", top: 30 }, { id: "very", top: 10 }];
export const MIX = [{ id: "kr", kr: 1 }, { id: "k73", kr: 0.7 }, { id: "k55", kr: 0.5 }, { id: "k37", kr: 0.3 }, { id: "us", kr: 0 }];
export const METHODS = ["calm", "even", "conviction"];
export const MAX_PCTS = [10, 15, 20, 25];
export const CUSHIONS = [0, 10, 20, 30];
export const EXCLUDE_LIVE = ["loss", "debt", "noDiv", "holding"];
export const EXCLUDE_PENDING = ["warned", "young", "china", "sin"];

export const strictTop = (id) => (STRICT.find((x) => x.id === id) || STRICT[1]).top;
export const mixKr = (id) => (MIX.find((x) => x.id === id) || MIX[1]).kr;

export function defaultSettings() {
  return { deck: null, points: {}, strict: "normal", exclude: { loss: false, debt: false, noDiv: false, holding: false },
    amountMan: 0, mix: "k73", count: 6, method: "even", maxPct: 20, cushion: 0, name: "", pinned: [] };
}

export function applyDeck(settings, deckId) {
  const d = DECKS.find((x) => x.id === deckId);
  const base = { ...settings, deck: deckId || null, points: {}, strict: "normal", mix: settings.mix };
  if (!d) return base;
  return { ...base, points: { ...d.points }, strict: d.strict || "normal", mix: d.mix || settings.mix };
}

export const pointsUsed = (points) => CARDS.reduce((a, c) => a + (c.pending ? 0 : points[c.id] || 0), 0);
export const activeCards = (points) => CARDS.filter((c) => !c.pending && (points[c.id] || 0) > 0);

// ---------------- features ----------------
// A field counts as live when at least one relevant record carries it. Until then the feature that needs it is hidden.
export function detectFeatures(data, corp, macro) {
  const stocks = (data && data.stocks) || [];
  const kr = stocks.filter((s) => s.cls === "kr");
  const comps = (corp && corp.companies) || [];
  return {
    etf: stocks.some((s) => Object.prototype.hasOwnProperty.call(s, "etf")),
    ind: kr.some((s) => hasGroup(s)),
    val20: kr.some((s) => num(s.val20) != null),
    d1: kr.some((s) => num(s.d1) != null),
    fy: comps.some((c) => num(c.fy) != null),
    dps0: kr.some((s) => s.dps === 0),
    idxHist: !!(macro && macro.idxHist && typeof macro.idxHist === "object"),
  };
}
export const BUILD_NEEDS = ["ind", "dps0", "val20", "fy", "etf"];
export const missingForBuild = (f) => BUILD_NEEDS.filter((k) => !f[k]);

// ---------------- values ----------------
export function cardRaw(s, card) {
  if (card.finNA && isFin(s)) return NA;
  const f = card.field[s.cls === "us" ? "us" : "kr"];
  if (f === "divYield") {
    const d = num(s.dps), p = num(s.price);
    return d == null || !(p > 0) ? null : (d / p) * 100;
  }
  return num(s[f]);
}

// KR: 20-day average (val20); US: the 3-month average (val). Both 억원. null = unknown.
export const liquidity = (s) => (s.cls === "kr" ? num(s.val20) : num(s.val));

export function priceWon(s, fx) {
  const p = num(s.price);
  if (p == null) return null;
  if (s.cls === "us") return num(fx) != null ? p * fx : null;
  return p;
}

// Percentile score 0-100 within the list (ties share the average rank); higher = better on that card.
export function percentileScores(list, card) {
  const vals = [];
  for (const s of list) {
    const v = cardRaw(s, card);
    if (typeof v === "number") vals.push([s.t, v * card.dir]);
  }
  vals.sort((a, b) => a[1] - b[1]);
  const n = vals.length, out = new Map();
  let i = 0;
  while (i < n) {
    let j = i;
    while (j + 1 < n && vals[j + 1][1] === vals[i][1]) j++;
    const rank = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) out.set(vals[k][0], (100 * rank) / n);
    i = j + 1;
  }
  return out;
}

export function exclusionsHit(s) {
  const hit = [];
  const opm = num(s.opm), debt = num(s.debt);
  if (opm != null && opm < 0) hit.push("loss");
  if (hasKrDebt(s) && debt > DEBT_EXCLUDE) hit.push("debt");
  if (s.cls === "kr" && s.dps === 0) hit.push("noDiv");
  if (s.ind === HOLDING_IND) hit.push("holding");
  return hit;
}

export function marketsOf(settings) {
  const k = mixKr(settings.mix);
  return [...(k > 0 ? ["kr"] : []), ...(k < 1 ? ["us"] : [])];
}

// ---------------- screening ----------------
// Universe -> liquidity floor -> 빼기 switches -> blanks left out -> strictness cut-off -> score order.
export function screen(stocks, settings) {
  const active = activeCards(settings.points);
  const top = strictTop(settings.strict);
  const pinned = new Set(settings.pinned || []);
  const res = { markets: {}, blanks: 0, survivors: 0, liqOut: 0, excludeCounts: { loss: 0, debt: 0, noDiv: 0, holding: 0 }, active: active.map((c) => c.id) };
  for (const mk of marketsOf(settings)) {
    const uni = stocks.filter((s) => s.cls === mk && inUniverse(s));
    const pct = Object.fromEntries(active.map((c) => [c.id, percentileScores(uni, c)]));
    const surv = [];
    let blanks = 0;
    for (const s of uni) {
      const liq = liquidity(s);
      if (liq == null) { blanks++; continue; }
      if (liq < LIQ_FLOOR_EOK) { res.liqOut++; continue; }
      const ex = exclusionsHit(s);
      for (const k of ex) res.excludeCounts[k]++;
      if (ex.some((k) => settings.exclude[k])) continue;
      if (!active.length || pinned.has(s.t)) continue;
      let blank = false, cut = false, wsum = 0, psum = 0;
      const scores = {};
      for (const c of active) {
        const raw = cardRaw(s, c);
        if (raw === NA) { scores[c.id] = NA; continue; }
        if (raw == null) { blank = true; break; }
        const sc = pct[c.id].get(s.t);
        scores[c.id] = sc;
        if (top != null && !(sc > 100 - top + EPS)) cut = true;
        wsum += settings.points[c.id] * sc;
        psum += settings.points[c.id];
      }
      if (blank) { blanks++; continue; }
      if (psum === 0 || cut) continue;
      surv.push({ t: s.t, s, scores, total: wsum / psum });
    }
    surv.sort((a, b) => b.total - a.total || (a.t < b.t ? -1 : 1));
    res.markets[mk] = { survivors: surv, blanks, universe: uni.length };
    res.blanks += blanks;
    res.survivors += surv.length;
  }
  return res;
}

export function topOverall(res, n) {
  return Object.values(res.markets).flatMap((m) => m.survivors).sort((a, b) => b.total - a.total || (a.t < b.t ? -1 : 1)).slice(0, n);
}

// The card that adds the most to a stock's score (for the one-line reason "배당 95점").
export function bestCard(item, points) {
  let best = null;
  for (const [id, sc] of Object.entries(item.scores)) {
    if (sc === NA) continue;
    const v = (points[id] || 0) * sc;
    if (!best || v > best.v) best = { id, score: sc, v };
  }
  return best;
}

// How many core stocks per market: closest to the mix that the max-per-stock limit can hold.
export function splitCounts(settings) {
  const N = settings.count, P = (settings.pinned || []).length, coreN = Math.max(0, N - P);
  const k = mixKr(settings.mix);
  if (k >= 1) return { kr: coreN, us: 0 };
  if (k <= 0) return { kr: 0, us: coreN };
  if (coreN < 2) return { kr: coreN, us: 0 };
  const coreW = (1 - settings.cushion / 100) * (coreN / N), maxW = settings.maxPct / 100, ideal = coreN * k;
  let best = null;
  for (let n = 1; n <= coreN - 1; n++) {
    const ok = n * maxW >= coreW * k - EPS && (coreN - n) * maxW >= coreW * (1 - k) - EPS;
    const d = Math.abs(n - ideal);
    if (ok && (!best || d < best.d - EPS)) best = { n, d };
  }
  const n = best ? best.n : Math.min(coreN - 1, Math.max(1, Math.round(ideal)));
  return { kr: n, us: coreN - n };
}

// Per market that needs stocks, with that market's own count:
//   zero  = nothing passed (block) · short = fewer than the stocks it must fill (block: 후보 고르기 could not be filled)
//   few   = fewer than 2x the stocks needed (warning only)
export function survivorCheck(res, counts) {
  const markets = [];
  for (const mk of Object.keys(res.markets)) {
    const need = counts[mk] || 0, have = res.markets[mk].survivors.length;
    if (need <= 0) continue;
    if (have === 0) markets.push({ mk, have, need, state: "zero" });
    else if (have < need) markets.push({ mk, have, need, state: "short" });
    else if (have < 2 * need) markets.push({ mk, have, need, state: "few" });
  }
  const block = markets.some((x) => x.state === "zero" || x.state === "short");
  return { zero: markets.some((x) => x.state === "zero"), block, few: markets.some((x) => x.state === "few"), markets };
}

// Equal-weight estimate used while picking: each pinned stock gets (1 - cushion) / N, each core pick its market's
// share of the rest divided by that market's count. Sizing later tilts within 0.6-1.4x of these.
export function weightPlan(settings, counts) {
  const N = settings.count, P = (settings.pinned || []).length;
  const stockW = 1 - settings.cushion / 100, eDeck = stockW / N, core = stockW - P * eDeck, k = mixKr(settings.mix);
  return { eDeck, e: { kr: counts.kr ? (core * k) / counts.kr : 0, us: counts.us ? (core * (1 - k)) / counts.us : 0 } };
}

// 후보 고르기: top 2 x n per market (pinned excluded). If the industry limits (max 2 per group, group <= 1/3 at
// equal weights) would leave fewer than n pickable names among them, further pickable survivors are added.
export function candidates(res, counts, pinnedStocks = [], plan = null) {
  const out = {};
  const picked = [];
  for (const mk of Object.keys(res.markets)) {
    const need = counts[mk] || 0, list = [];
    let got = 0;
    for (const c of res.markets[mk].survivors) {
      if (list.length >= 2 * need && got >= need) break;
      const pickable = got < need && !canAdd(c.s, picked, pinnedStocks, counts, plan);
      if (list.length < 2 * need || pickable) list.push(c);
      if (pickable) { got++; picked.push(c.s); }
    }
    out[mk] = list;
  }
  return out;
}

export function indCounts(list) {
  const m = new Map();
  for (const s of list) if (hasGroup(s)) m.set(s.ind, (m.get(s.ind) || 0) + 1);
  return m;
}

// Pre-select n per market in score order, keeping every industry limit (see canAdd). Returns the picked codes and,
// when a market cannot be filled, which limits stopped it (blocked: [{ code: "industry" | "indCap", ind, indName }]).
export function preselect(cands, counts, pinnedStocks, plan = null) {
  const picked = [], stopped = [];
  for (const mk of Object.keys(cands)) {
    let n = 0;
    for (const c of cands[mk]) {
      if (n >= (counts[mk] || 0)) break;
      const why = canAdd(c.s, picked.map((x) => x.s), pinnedStocks, counts, plan);
      if (why === "industry" || why === "indCap") { stopped.push({ code: why, ind: c.s.ind, indName: c.s.indName }); continue; }
      if (why) continue;
      picked.push(c);
      n++;
    }
  }
  const short = Object.keys(cands).some((mk) => picked.filter((x) => x.s.cls === mk).length < (counts[mk] || 0));
  const seen = new Set();
  const blocked = short ? stopped.filter((x) => { const k = x.code + x.ind; if (seen.has(k)) return false; seen.add(k); return true; }) : [];
  return Object.assign(picked.map((x) => x.t), { short, blocked });
}

// Can this stock be added? -> null, "market" (that market is full), "industry" (2 already in its group, pinned
// included) or "indCap" (its group would pass 1/3 of the deck at equal weights, pinned included).
export function canAdd(stock, pickedStocks, pinnedStocks, counts, plan = null) {
  const inMk = pickedStocks.filter((s) => s.cls === stock.cls).length;
  if (inMk >= (counts[stock.cls] || 0)) return "market";
  if (!hasGroup(stock)) return null;
  const same = [...pickedStocks, ...pinnedStocks].filter((s) => hasGroup(s) && s.ind === stock.ind);
  if (same.length >= MAX_PER_IND) return "industry";
  if (plan) {
    const w = pinnedStocks.filter((s) => hasGroup(s) && s.ind === stock.ind).length * plan.eDeck
      + pickedStocks.filter((s) => hasGroup(s) && s.ind === stock.ind).reduce((a, s) => a + (plan.e[s.cls] || 0), 0)
      + (plan.e[stock.cls] || 0);
    if (w > IND_CAP + 1e-9) return "indCap";
  }
  return null;
}

// Can this stock be pinned (꼭 담을 종목)? -> null | "full" | "industry" (a third stock in one group)
export function canPin(stock, pinnedStocks) {
  if (pinnedStocks.length >= PINNED_MAX) return "full";
  if (hasGroup(stock) && pinnedStocks.filter((s) => hasGroup(s) && s.ind === stock.ind).length >= MAX_PER_IND) return "industry";
  return null;
}

// ---------------- sizing (REDESIGN 4.3) ----------------
// Weights w_i = min(cap_i, k * base_i) with sum = total; k found by bisection. Returns null if the caps cannot hold total.
export function cappedFill(base, caps, total) {
  if (total <= EPS) return base.map(() => 0);
  const capSum = caps.reduce((a, b) => a + b, 0);
  if (capSum < total - 1e-7) return null;
  if (capSum <= total + 1e-12) return caps.slice();
  const at = (k) => base.map((b, i) => Math.min(caps[i], k * b));
  const sum = (w) => w.reduce((a, b) => a + b, 0);
  let lo = 0, hi = 1;
  while (sum(at(hi)) < total && hi < 1e15) hi *= 2;
  for (let it = 0; it < 200; it++) {
    const mid = (lo + hi) / 2;
    if (sum(at(mid)) < total) lo = mid; else hi = mid;
  }
  return at(hi);
}

// Multipliers with mean 1, each within [lo, hi]: m_i = clip(r_i + c) with r = raw / mean(raw), c found by bisection.
export function boundedTilts(raw, lo = TILT[0], hi = TILT[1]) {
  const n = raw.length;
  if (!n) return [];
  const mean = raw.reduce((a, b) => a + b, 0) / n;
  const r = raw.map((x) => (mean > 0 && Number.isFinite(x) ? x / mean : 1));
  const g = (c) => r.reduce((acc, x) => acc + Math.min(hi, Math.max(lo, x + c)), 0) / n - 1;
  let a = lo - Math.max(...r), b = hi - Math.min(...r);
  for (let it = 0; it < 200; it++) {
    const c = (a + b) / 2;
    if (g(c) < 0) a = c; else b = c;
  }
  const c = (a + b) / 2;
  return r.map((x) => Math.min(hi, Math.max(lo, x + c)));
}

function steadiness(stocks) {
  const inv = stocks.map((s) => { const v = num(s.vol); return v != null && v > 0 ? 1 / v : null; });
  const ok = inv.filter((x) => x != null);
  const mean = ok.length ? ok.reduce((a, b) => a + b, 0) / ok.length : null;
  // extremes pulled to the average: halfway between the stock's own figure and the group's mean (no vol -> neutral 1)
  return inv.map((x) => (x == null || !mean ? 1 : 0.5 * (x / mean) + 0.5));
}

function rawTilts(items, method) {
  const sc = items.map((x) => Math.max(1, x.total || 0));
  const mean = sc.reduce((a, b) => a + b, 0) / (sc.length || 1);
  const fit = sc.map((x) => x / mean);
  const st = steadiness(items.map((x) => x.s));
  if (method === "calm") return { raw: st, st };
  if (method === "conviction") return { raw: fit, st };
  return { raw: fit.map((f, i) => 0.5 * f + 0.5 * st[i]), st };
}

// picks: [{ t, s, total }] (core picks, any market); pinned: [stock]; cushion: [{ s, share }] (all cushion assets).
export function size({ picks, pinned = [], cushion = [], settings, amountWon }) {
  const N = picks.length + pinned.length;
  const maxW = settings.maxPct / 100, cushW = settings.cushion / 100, stockW = 1 - cushW;
  const k = mixKr(settings.mix);
  const clashOut = (parts) => ({ ok: false, clash: dedupe(parts) });
  if (N === 0) return clashOut([{ code: "count", n: 0 }]);
  if (cushW > 0 && !cushion.length) return clashOut([{ code: "cushion" }]);
  const counts = indCounts([...picks.map((p) => p.s), ...pinned]);
  const over = [...counts.entries()].filter(([, n]) => n > MAX_PER_IND);
  if (over.length) {
    const named = (g) => [...picks.map((p) => p.s), ...pinned].find((s) => s.ind === g);
    return clashOut(over.map(([g]) => ({ code: "indCount", ind: g, indName: named(g).indName })));
  }
  const liqCap = (s) => {
    if (!(amountWon > 0)) return Infinity;
    const l = liquidity(s);
    return l == null ? 0 : (LIQ_SHARE * l * 1e8) / amountWon;
  };
  const eDeck = stockW / N;
  const items = [];
  // pinned: an equal share of the stock part, still capped
  let pinnedSum = 0;
  for (const s of pinned) {
    const cap = Math.min(maxW, liqCap(s));
    const w = Math.min(eDeck, cap);
    pinnedSum += w;
    items.push({ t: s.t, s, kind: "pinned", w, cap, why: w < eDeck - EPS ? (cap === maxW ? "max" : "liq") : null });
  }
  const core = stockW - pinnedSum;
  const groups = [];
  for (const mk of ["kr", "us"]) {
    const share = mk === "kr" ? k : 1 - k;
    const members = picks.filter((p) => p.s.cls === mk);
    const T = core * share;
    if (T > EPS && !members.length) return clashOut([{ code: "mix" }]);
    if (!members.length) continue;
    const e = T / members.length;
    const { raw, st } = rawTilts(members, settings.method);
    const m = boundedTilts(raw);
    const g = { mk, T, e, share, members: members.map((p, i) => ({ ...p, m: m[i], st: st[i], base: e * m[i],
      capMax: maxW, capLiq: liqCap(p.s), capTilt: TILT[1] * e })) };
    groups.push(g);
  }
  const frozen = new Map();          // t -> weight fixed by the industry cap
  const indFrozen = new Set();
  let weights = new Map();
  for (let iter = 0; iter < 40; iter++) {
    weights = new Map();
    for (const g of groups) {
      const fixedSum = g.members.reduce((a, x) => a + (frozen.has(x.t) ? frozen.get(x.t) : 0), 0);
      const free = g.members.filter((x) => !frozen.has(x.t));
      const rem = g.T - fixedSum;
      for (const x of g.members) if (frozen.has(x.t)) weights.set(x.t, frozen.get(x.t));
      if (!free.length) {
        if (Math.abs(rem) > 1e-7) return clashOut(groupClash(g, free, indFrozen, N, settings));
        continue;
      }
      const caps = free.map((x) => Math.min(x.capMax, x.capLiq, x.capTilt));
      const w = cappedFill(free.map((x) => x.base), caps, rem);
      if (!w) return clashOut(groupClash(g, free, indFrozen, N, settings));
      free.forEach((x, i) => weights.set(x.t, w[i]));
    }
    // industry cap over every stock (pinned + core); ungrouped stocks never share a cap
    const sums = new Map();
    const all = [...items.map((x) => ({ t: x.t, s: x.s, w: x.w, pinned: true })),
      ...groups.flatMap((g) => g.members.map((x) => ({ t: x.t, s: x.s, w: weights.get(x.t) || 0, pinned: false })))];
    for (const x of all) if (hasGroup(x.s)) sums.set(x.s.ind, (sums.get(x.s.ind) || 0) + x.w);
    const viol = [...sums.entries()].filter(([, v]) => v > IND_CAP + 1e-7);
    if (!viol.length) break;
    for (const [ind] of viol) {
      const mem = all.filter((x) => x.s.ind === ind);
      const pin = mem.filter((x) => x.pinned).reduce((a, x) => a + x.w, 0);
      const coreMem = mem.filter((x) => !x.pinned);
      const coreSum = coreMem.reduce((a, x) => a + x.w, 0);
      const room = IND_CAP - pin;
      if (room < -1e-9 || coreSum <= EPS) {
        return clashOut([{ code: "count", n: N }, ...cappedInds(indFrozen, all), { code: "ind", ind, indName: mem[0].s.indName }]);
      }
      const scale = room / coreSum;
      for (const x of coreMem) { frozen.set(x.t, x.w * scale); indFrozen.add(x.t); }
    }
    if (iter === 39) return clashOut([{ code: "ind" }]);
  }
  for (const g of groups) {
    for (const x of g.members) {
      const w = weights.get(x.t) || 0;
      items.push({ t: x.t, s: x.s, kind: "core", w, total: x.total, m: x.m, st: x.st, mk: g.mk, share: g.share,
        cap: Math.min(x.capMax, x.capLiq), capMax: x.capMax, capLiq: x.capLiq,
        why: indFrozen.has(x.t) ? "ind" : w >= x.capMax - 1e-7 ? "max" : w >= x.capLiq - 1e-7 ? "liq" : null });
    }
  }
  if (cushW > 0) for (const c of cushion) items.push({ t: c.s.t, s: c.s, kind: "cushion", w: cushW * c.share, cap: cushW * c.share, why: null });
  const two = k > 0 && k < 1;
  const coreItems = items.filter((x) => x.kind === "core").sort((a, b) => b.total - a.total || (a.t < b.t ? -1 : 1));
  coreItems.forEach((x, i) => { x.rank = i + 1; });
  for (const x of items) x.reasons = reasonsFor(x, settings, two);
  return { ok: true, items };
}

function dedupe(parts) {
  const seen = new Set();
  return parts.filter((p) => { const key = p.code + (p.ind || ""); if (seen.has(key)) return false; seen.add(key); return true; });
}

// Every group that was held at 1/3 (each named once)
function cappedInds(indFrozen, members) {
  const out = [], seen = new Set();
  for (const x of members) {
    if (!indFrozen.has(x.t) || seen.has(x.s.ind)) continue;
    seen.add(x.s.ind);
    out.push({ code: "ind", ind: x.s.ind, indName: x.s.indName });
  }
  return out;
}

// The limits that clash when a market's share cannot be filled: stock count, max per stock (when it binds), every
// industry group held at 1/3, the liquidity cap, and the Korea:US split.
function groupClash(g, free, indFrozen, N, settings) {
  const parts = [];
  const bind = free.map((x) => Math.min(x.capMax, x.capLiq, x.capTilt));
  const usedMax = free.some((x, i) => Math.abs(bind[i] - x.capMax) < 1e-9 && x.capMax <= x.capLiq);
  const usedLiq = free.some((x, i) => x.capLiq < x.capMax && Math.abs(bind[i] - x.capLiq) < 1e-9);
  parts.push({ code: "count", n: N });
  if (usedMax || !free.length) parts.push({ code: "max", pct: settings.maxPct });
  parts.push(...cappedInds(indFrozen, g.members));
  if (usedLiq) parts.push({ code: "liq" });
  if (g.share < 1) parts.push({ code: "mix" });
  return parts;
}

function reasonsFor(x, settings, two) {
  if (x.kind === "cushion") return [{ code: "cushion", pct: settings.cushion }];
  const out = [];
  if (x.kind === "pinned") out.push({ code: "pinned" });
  else {
    const steady = x.st > 1.02 ? "more" : x.st < 0.98 ? "less" : null;
    const mkt = (more) => ({ code: more ? "mktSteady" : "mktVolatile", mk: x.mk, pct: Math.round(x.share * 100) });
    if (settings.method === "conviction") out.push({ code: "rank", rank: x.rank });
    else if (settings.method === "calm") out.push(two && steady ? mkt(steady === "more") : { code: steady === "more" ? "steadyMore" : steady === "less" ? "steadyLess" : "core" });
    else {
      out.push({ code: "rank", rank: x.rank });
      if (steady) out.push(two ? mkt(steady === "more") : { code: steady === "more" ? "steadyMore" : "steadyLess" });
    }
  }
  if (x.why === "max") out.push({ code: "maxCap", pct: settings.maxPct });
  if (x.why === "ind") out.push({ code: "indCap", ind: x.s.ind, indName: x.s.indName });
  if (x.why === "liq") out.push({ code: "liqCap" });
  return out;
}

// ---------------- plan: whole shares ----------------
// Round down to whole shares, then add one share at a time to the name furthest below its target (nearest-share
// rounding), never past the money, the stock's cap or the industry cap.
export function planShares(items, amountWon, fx) {
  const rows = items.map((it) => {
    const px = priceWon(it.s, fx);
    const target = it.w * amountWon;
    const shares = px > 0 ? Math.floor(target / px + 1e-9) : 0;
    return { t: it.t, s: it.s, kind: it.kind, px, target, targetW: it.w, shares, capWon: (it.kind === "cushion" ? it.w : it.cap) * amountWon, reasons: it.reasons };
  });
  let spent = rows.reduce((a, r) => a + (r.px > 0 ? r.shares * r.px : 0), 0);
  const indCost = () => {
    const m = new Map();
    for (const r of rows) if (r.kind !== "cushion" && hasGroup(r.s)) m.set(r.s.ind, (m.get(r.s.ind) || 0) + r.shares * r.px);
    return m;
  };
  for (let guard = 0; guard < 10000; guard++) {
    const ic = indCost();
    let best = null;
    for (const r of rows) {
      if (!(r.px > 0)) continue;
      const cost = r.shares * r.px, short = r.target - cost;
      if (short < r.px / 2 - 1e-6) continue;
      if (spent + r.px > amountWon + 1e-6) continue;
      if (cost + r.px > r.capWon + 1e-6) continue;
      if (r.kind !== "cushion" && hasGroup(r.s) && (ic.get(r.s.ind) || 0) + r.px > IND_CAP * amountWon + 1e-6) continue;
      if (!best || short > best.short) best = { r, short };
    }
    if (!best) break;
    best.r.shares += 1;
    spent += best.r.px;
  }
  for (const r of rows) { r.cost = r.px > 0 ? r.shares * r.px : 0; r.w = amountWon > 0 ? r.cost / amountWon : 0; }
  const cheapest = rows.reduce((a, r) => (r.px > 0 && (a == null || r.px < a) ? r.px : a), null);
  const oneEach = rows.reduce((a, r) => a + (r.px > 0 ? r.px : 0), 0);
  return { rows, spent, left: amountWon - spent, cheapest, tooSmall: amountWon > 0 && amountWon < oneEach };
}

// Past-year dividend before tax. KR: dps x shares (0 = paid nothing). US and ETFs: dy x amount. Unknown counts as 0.
export function annualDividend(rows, fx) {
  let won = 0, unknown = 0;
  for (const r of rows) {
    if (!(r.shares > 0)) continue;
    const s = r.s;
    if (s.cls === "kr") {
      const d = num(s.dps);
      if (d == null) unknown++; else won += d * r.shares;
    } else {
      const dy = num(s.dy);
      if (dy == null) unknown++; else won += (dy / 100) * r.cost;
    }
  }
  return { won, unknown };
}

// "2022년처럼 떨어지면": market's 2022 won return x beta per stock; cushion ETFs their own 2022 return.
// Holdings without a figure (no beta) are assumed to move like the rest (the v17.5 rule of the current app): the rate
// comes from the holdings with data and applies to the whole amount bought. missing = their share of the money.
// None with data -> { ok: false, none: true }.
export function estimate2022(rows, R = R2022) {
  let won = 0, known = 0, total = 0;
  for (const r of rows) {
    if (!(r.shares > 0)) continue;
    const s = r.s;
    total += r.cost;
    let ret = null;
    if (s.cls === "kr" || s.cls === "us") {
      const b = num(s.beta);
      if (b != null && !s.etf && !s.fund) ret = (s.cls === "kr" ? R.kr : R.usWon) * b;
      else if (R.etf && R.etf[s.t] != null) ret = R.etf[s.t];
    } else if (R.etf && R.etf[s.t] != null) ret = R.etf[s.t];
    if (ret == null || !Number.isFinite(ret)) continue;
    won += ret * r.cost;
    known += r.cost;
  }
  if (!(known > 0)) return { ok: false, none: true };
  return { ok: true, won: (won / known) * total, missing: total > 0 ? 1 - known / total : 0 };
}

// Yearly volatility of the deck (fraction of the money bought), one factor per market with correlations from
// data.json settings. Used only when the 2022 line cannot be shown. -> { vol, missing } or null (no holding has data).
export function deckVol(rows, st, amountWon) {
  const F = { kr: num(st && st.mktVol), us: num(st && st.usVol), bond: num(st && st.bdVol), metal: num(st && st.mtVol) };
  const rho = { "kr|us": st && st.rhoKrUs, "kr|metal": st && st.rhoKrMt, "us|metal": st && st.rhoUsMt, "kr|bond": st && st.rhoKrBd,
    "us|bond": st && st.rhoUsBd, "metal|bond": st && st.rhoMtBd };
  const r = (a, b) => (a === b ? 1 : num(rho[`${a}|${b}`]) ?? num(rho[`${b}|${a}`]));
  if (!(amountWon > 0)) return null;
  const expo = { kr: 0, us: 0, bond: 0, metal: 0 };
  let idio = 0;
  // holdings without vol or beta are assumed to move like the rest: weights are taken within the holdings with data
  const usable = (x) => { const s = x.s, c = s.cls; return num(s.vol) != null && c in expo && F[c] != null && ((c !== "kr" && c !== "us") || num(s.beta) != null); };
  const known = rows.filter((x) => x.shares > 0 && usable(x)).reduce((a, x) => a + x.cost, 0);
  if (!(known > 0)) return null;
  for (const x of rows) {
    if (!(x.shares > 0) || !usable(x)) continue;
    const w = x.cost / known, s = x.s, v = num(s.vol), c = s.cls;
    if (c === "kr" || c === "us") {
      const b = num(s.beta);
      expo[c] += (w * b * F[c]) / 100;
      idio += w * w * Math.max(0, (v / 100) ** 2 - (b * F[c] / 100) ** 2);
    } else expo[c] += (w * v) / 100;
  }
  const keys = Object.keys(expo).filter((k) => expo[k] !== 0);
  let sys = 0;
  for (const a of keys) for (const b of keys) {
    const rr = r(a, b);
    if (rr == null) return null;
    sys += expo[a] * expo[b] * rr;
  }
  const v = Math.sqrt(Math.max(0, sys + idio));
  const total = rows.filter((x) => x.shares > 0).reduce((a, x) => a + x.cost, 0);
  return Number.isFinite(v) ? { vol: v, missing: total > 0 ? 1 - known / total : 0 } : null;
}

// ---------------- 주의할 점 (cautions) ----------------
// Context per market: each industry group's PBR 75th percentile (groups with 5+ members) and the market's 80th
// percentile of volatility.
export function cautionContext(stocks) {
  const ctx = { pbrP75: new Map(), volP80: {} };
  const q = (arr, p) => { const a = [...arr].sort((x, y) => x - y); const i = (a.length - 1) * p, lo = Math.floor(i); return a[lo] + (a[Math.ceil(i)] - a[lo]) * (i - lo); };
  for (const mk of ["kr", "us"]) {
    const uni = stocks.filter((s) => s.cls === mk && inUniverse(s));
    const groups = new Map();
    for (const s of uni) {
      if (!hasGroup(s) || num(s.pbr) == null || s.pbr <= 0) continue;
      if (!groups.has(s.ind)) groups.set(s.ind, []);
      groups.get(s.ind).push(s.pbr);
    }
    for (const [g, arr] of groups) if (arr.length >= 5) ctx.pbrP75.set(`${mk}|${g}`, q(arr, 0.75));
    const vols = uni.map((s) => num(s.vol)).filter((v) => v != null);
    if (vols.length >= 5) ctx.volP80[mk] = q(vols, 0.8);
  }
  return ctx;
}

// Returns { items: [{ code, ... }], ran: [codes of the checks that had data] }. co = corp.json company (KR) or null.
export function cautions(s, co, ctx) {
  const items = [], ran = [];
  const pbr = num(s.pbr), p75 = hasGroup(s) ? ctx.pbrP75.get(`${s.cls}|${s.ind}`) : null;
  if (pbr != null && pbr > 0 && p75 != null) { ran.push("pbr"); if (pbr > p75) items.push({ code: "pbrHigh", pbr }); }
  if (hasKrDebt(s)) { ran.push("debt"); if (s.debt > DEBT_CAUTION) items.push({ code: "debtHigh", debt: s.debt }); }
  const rev = co && Array.isArray(co.rev) ? co.rev.map(num) : null;
  if (rev && rev.length >= 3 && rev.slice(0, 3).every((x) => x != null)) {
    ran.push("rev");
    if (rev[0] < rev[1] && rev[1] < rev[2]) items.push({ code: "revFall" });
  }
  // operating profit down 2 years running: the keep rule would already fail at purchase, so it is a caution instead
  if (opFell2(co)) { ran.push("op"); items.push({ code: "opFall", pct: (co.op[0] / co.op[1] - 1) * 100 }); }
  else if (co && Array.isArray(co.op) && co.op.slice(0, 3).filter((x) => num(x) != null).length >= 3) ran.push("op");
  const vol = num(s.vol), p80 = ctx.volP80[s.cls];
  if (vol != null && p80 != null) { ran.push("vol"); if (vol > p80) items.push({ code: "volHigh", vol }); }
  const d3 = s.cls === "kr" ? (Array.isArray(s.dps3) ? s.dps3 : co && Array.isArray(co.dps3) ? co.dps3 : null) : null;
  if (d3 && num(d3[0]) != null && num(d3[1]) != null) {
    ran.push("div");
    if (d3[0] < d3[1]) items.push({ code: "divDrop", a: d3[1], b: d3[0] });   // never 규칙 깨짐 on its own: 확인 필요
  }
  return { items, ran };
}

// ---------------- 내 투자 규칙 (rule book) ----------------
// Each rule: { id, kind: "sell" | "keep" | "band", check: "checked" | "pending", ...inputs at purchase }.
// Statuses follow the v18.3 Part C table. The daily evaluation loop is Part C (not here).
export const fyOf = (s, co) => num(s.fy) ?? (co ? num(co.fy) : null);

export function dividendStreak(d3) {
  if (!Array.isArray(d3)) return 0;
  let n = 0;
  for (let i = 0; i + 1 < d3.length; i++) {
    if (num(d3[i]) != null && num(d3[i + 1]) != null && d3[i] > d3[i + 1]) n++; else break;
  }
  return n;
}

export const debtLimitFor = (debt) => Math.max(100, Math.ceil((debt * 1.25) / 10) * 10);
// Operating profit [latest, prior, two years ago] fell twice in a row (positive base years only)
export function opFell2(co) {
  const op = co && Array.isArray(co.op) ? co.op.slice(0, 3).map(num) : [];
  return op.length === 3 && op.every((x) => x != null) && op[1] > 0 && op[0] < op[1] && op[1] < op[2];
}
export const roeFloorFor = (roe) => Math.max(0, Math.floor(roe / 2));

export function ruleBook(s, co, points, targetW) {
  const rules = [];
  const fy = fyOf(s, co);
  // Korean annual inputs (DART) must carry their report year; without it the rule is not shown as checked.
  const dated = s.cls !== "kr" || fy != null;
  // Rules are generated only when they hold at purchase: an input that already breaks a rule shows as a caution in
  // 후보 고르기 (주의할 점) and the rule is not added silently.
  // 1. common sell conditions
  const dps = num(s.dps);
  const d3 = Array.isArray(s.dps3) ? s.dps3 : co && Array.isArray(co.dps3) ? co.dps3 : null;
  const prev = d3 ? num(d3[1]) : null;
  if (s.cls === "kr" && dps === 0) { /* pays nothing: no dividend-cut rule */ }
  else if (s.cls === "kr" && dps != null && dps > 0 && dated && prev != null) {
    if (dps >= prev) rules.push({ id: "divCut", kind: "sell", check: "checked", input: "dps", dps, prev, dps3: d3, streak: dividendStreak(d3), fy });
    /* dividend already lower than the year before: 확인 필요 caution, no rule */
  } else rules.push({ id: "divCut", kind: "sell", check: "pending" });
  rules.push({ id: "audit", kind: "sell", check: "pending" });
  rules.push({ id: "embezzle", kind: "sell", check: "pending" });
  rules.push({ id: "acquisition", kind: "sell", check: "pending" });
  // 2. keep conditions from the deck's cards and the industry
  if ((points.stable || 0) > 0 && s.cls === "kr" && !isFin(s)) {
    const debt = num(s.debt);
    rules.push(debt != null && dated ? { id: "debtCeiling", kind: "keep", check: "checked", input: "debt", debt, limit: debtLimitFor(debt), fy }
      : { id: "debtCeiling", kind: "keep", check: "pending" });
  }
  if ((points.profit || 0) > 0) {
    const roe = num(s.roe);
    if (roe != null && roe > 0 && dated) rules.push({ id: "roeFloor", kind: "keep", check: "checked", input: "roe", roe, floor: roeFloorFor(roe), fy: s.cls === "kr" ? fy : null });
  }
  if (s.cls === "kr" && dated && co && Array.isArray(co.op) && co.op.filter((x) => num(x) != null).length >= 2 && !opFell2(co)) {
    rules.push({ id: "opDecline", kind: "keep", check: "checked", input: "op", op: co.op.map(num), fy });
  }
  if (s.ind === "bank") rules.push({ id: "cet1", kind: "keep", check: "pending" });
  if (s.ind === "insurance") rules.push({ id: "kics", kind: "keep", check: "pending" });
  // 3. weight bands (portfolio arithmetic, not a price rule)
  if (targetW > 0) rules.push({ id: "band", kind: "band", check: "checked", target: targetW, bands: BANDS.map((b) => b * targetW) });
  return rules;
}
