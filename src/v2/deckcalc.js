// Glue between the engine and the screens: screening, picks and the plan for the current settings,
// plus the code -> copy mapping for reasons, clashes and cautions.
import {
  screen, splitCounts, survivorCheck, candidates, preselect, size, planShares, annualDividend, estimate2022,
  deckVol, num, liquidity, isStockLike,
} from "./engine.js";
import { C, fill, nf, p1, wonText } from "./format.js";

// Everything the builder needs for the current settings. blocked = 후보 고르기 could not be filled: a market has
// fewer survivors than it must fill, or the industry limits leave too few pickable names (pre.blocked says which).
export function deckState(load, settings) {
  const res = screen(load.data.stocks, settings);
  const counts = splitCounts(settings);
  const check = survivorCheck(res, counts);
  const pinned = (settings.pinned || []).map((t) => load.byT.get(t)).filter(Boolean);
  const cands = candidates(res, counts, pinned, settings);
  const pre = preselect(cands, counts, pinned, settings);
  const shortN = Object.values(cands).reduce((a, x) => a + x.length, 0);
  // Settings that cannot all hold (e.g. 5 stocks x max 10%): found on the pre-selected list before 후보 고르기
  // (amount-free; the liquidity cap is checked again in 매수 계획 once the amount is known).
  let clash = null;
  if (!check.block && !pre.short) {
    const all = Object.values(cands).flat();
    const items = [...pre].map((t) => all.find((c) => c.t === t)).filter(Boolean);
    const sz = size({ picks: items, pinned, cushion: cushionStocks(load), settings, amountWon: 0 });
    if (!sz.ok) clash = sz.clash;
  }
  return { res, counts, check, cands, shortN, pinned, pre, clash, settings, blocked: check.block || pre.short || !!clash };
}

export const defaultPicks = (ds) => [...ds.pre];

export function pickItems(ds, picks) {
  const all = Object.values(ds.cands).flat();
  return (picks || []).map((t) => all.find((c) => c.t === t)).filter(Boolean);
}

// The cushion assets of this page ([{ s, share }]); empty unless every one of them is in the data with a price.
export function cushionStocks(load) {
  const out = load.cushion.map((c) => ({ s: load.byT.get(c.t), share: c.share }));
  return out.every((x) => x.s && num(x.s.price) > 0) ? out : [];
}

export function computePlan(load, settings, items, pinned) {
  const amountWon = settings.amountMan * 10000;
  const sz = size({ picks: items, pinned, cushion: cushionStocks(load), settings, amountWon });
  if (!sz.ok) return { ok: false, clash: sz.clash };
  const plan = planShares(sz.items, amountWon, load.data.fx);
  const div = annualDividend(plan.rows, load.data.fx);
  const y2022 = estimate2022(plan.rows, load.r2022);
  const vol = y2022.ok ? null : deckVol(plan.rows, load.data.settings, amountWon);
  return { ok: true, items: sz.items, plan, div, y2022, vol, amountWon };
}

// "일부 종목(비중 {pct}%)…": the same rounding as the current app (whole %, or one decimal below 1%, at least 0.1)
export const missingPct = (share) => (share * 100 >= 1 ? nf(Math.round(share * 100)) : nf(Math.max(share * 100, 0.1), 1));

// Stocks the user may pin as 꼭 담을 종목: company shares incl. preferred, with a price and known liquidity.
export function pinnable(load, q, pinnedTs) {
  const query = String(q || "").trim();
  if (!query) return [];
  const up = query.toUpperCase();
  const out = [];
  for (const s of load.data.stocks) {
    if (!isStockLike(s) || !(num(s.price) > 0) || liquidity(s) == null || pinnedTs.includes(s.t)) continue;
    if ((s.nk && s.nk.includes(query)) || String(s.t).toUpperCase().startsWith(up) || (s.ne && s.ne.toUpperCase().includes(up))) out.push(s);
    if (out.length >= 6) break;
  }
  return out;
}

export function deckDisplayName(settings) {
  if (settings.name && settings.name.trim()) return settings.name.trim();
  if (settings.deck && C.build.decks[settings.deck]) return fill(C.app.deckName, { name: C.build.decks[settings.deck].name });
  return C.deck.title;
}

export function reasonText(r) {
  const R = C.plan.reason;
  switch (r.code) {
    case "rank": return fill(R.rank, { rank: r.rank });
    case "indCap": return r.indName ? fill(R.indCap, { ind: r.indName }) : null;
    case "steadyMore": return R.steadyMore;
    case "steadyLess": return R.steadyLess;
    case "core": return R.core;
    case "maxCap": return fill(R.maxCap, { pct: r.pct });
    case "mktSteady": return fill(R.mktSteady, { mkt: C.pick.market[r.mk], pct: r.pct });
    case "mktVolatile": return fill(R.mktVolatile, { mkt: C.pick.market[r.mk], pct: r.pct });
    case "pinned": return R.pinned;
    case "cushion": return fill(R.cushion, { pct: r.pct });
    case "liqCap": return R.liqCap;            // pending wording: null -> left out
    default: return null;
  }
}
export const reasonsLine = (rs) => (rs || []).map(reasonText).filter(Boolean).join(" · ");

// Clash parts as separate text pieces (each one a copy string).
export function clashPieces(parts) {
  const P = C.plan.clashParts;
  const out = [];
  for (const p of parts) {
    if (p.code === "indCount") out.push([P.indCount]);
    else if (p.code === "count") out.push([P.count, fill(C.app.count, { count: p.n })]);
    else if (p.code === "max") out.push([fill(P.max, { pct: p.pct })]);
    else if (p.code === "ind" && p.indName) out.push([fill(P.ind, { ind: p.indName })]);
    else if (p.code === "mix") out.push([P.mix]);
    else if (p.code === "liq" && P.liq) out.push([P.liq]);
  }
  return out;
}

export function cautionTexts(c, s) {
  const K = C.pick.caution;
  switch (c.code) {
    case "pbrHigh": return [fill(K.pbrHigh, { metric: "PBR", x: nf(c.pbr, 2) })];
    case "debtHigh": return [fill(K.debtHigh, { pct: nf(Math.round(c.debt)) })];
    case "revFall": return [K.revFall];
    case "opFall": return [K.opFallFull || fill(K.opFall, { pct: signedPct(c.pct) })];
    case "volHigh": return K.volHigh ? [fill(K.volHigh, { vol: p1(c.vol) })] : [];
    case "divDrop": return [fill(K.divDrop, { name: s.nk, a: nf(Math.round(c.a)), b: nf(Math.round(c.b)) }), K.divDropBody];
    default: return [];
  }
}

export const aboutWon = (won) => fill(C.app.about, { x: wonText(won) });
export const signedPct = (v) => `${v < 0 ? "\u2212" : v > 0 ? "+" : ""}${p1(Math.abs(v))}%`;
