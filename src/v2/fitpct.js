// ================= 내 기준 상위 {x}%: one number per stock (v19.7 Part D [B3]) =================
// THE one function (spec [B3]) is v19.5b's ranks.js criteriaPct (branch claude/v19.5b-rankings at 94eea80), which v19.7a's
// base (v19.6a) does not have yet. This file is that function copied word for word, so the 담기 sheet (Part C) reads the same
// number v19.5b's 내 기준 list, v19.7b's finder and the compare screen read. When v19.5b is merged, this file becomes one
// line: export { criteriaPct } from "./ranks.js"; (tests/test_v197a_edit.py checks the two give the same numbers while both
// exist). Pure; no Korean here.
import { NA, universe, percentileScores, cardRaw, activeCards } from "./engine.js";

const EPS = 1e-9;

// The stock's weighted 기준 score with these points (screen()'s own total: each card's percentile within the market's
// universe, 해당 없음 cards left out of the weights) as a percentile among all scorable stocks of the market (the universe,
// a number on every card that has points; before the trading-value floor, 빼기 and any filter, so a stock a filter drops
// still has a number). -> Map t -> x for "상위 {x}%" (1 = the best 1%; ties share the average rank, as company.cardRanks
// reads one card). A stock that cannot be scored is not in the map ("—", never 0).
const pctMemo = new WeakMap();
export function criteriaPct(stocks, mk, points) {
  const key = mk + "|" + JSON.stringify(points || {});
  let m = Array.isArray(stocks) ? pctMemo.get(stocks) : null;
  if (Array.isArray(stocks) && !m) { m = new Map(); pctMemo.set(stocks, m); }
  if (m && m.has(key)) return m.get(key);
  const out = new Map();
  const active = activeCards(points || {});
  if (active.length && Array.isArray(stocks)) {
    const uni = universe(stocks, mk);
    const pct = active.map((c) => [c, percentileScores(uni, c)]);
    const totals = [];
    for (const s of uni) {
      let wsum = 0, psum = 0, blank = false;
      for (const [c, sc] of pct) {
        const raw = cardRaw(s, c);
        if (raw === NA) continue;
        if (raw == null) { blank = true; break; }
        wsum += points[c.id] * sc.get(s.t);
        psum += points[c.id];
      }
      if (!blank && psum > 0) totals.push([s.t, wsum / psum]);
    }
    totals.sort((a, b) => a[1] - b[1]);
    const n = totals.length;
    let i = 0;
    while (i < n) {
      let j = i;
      while (j + 1 < n && totals[j + 1][1] === totals[i][1]) j++;
      const v = (100 * ((i + j) / 2 + 1)) / n;
      const top = Math.max(1, Math.ceil(100 - v + 100 / n - EPS));
      for (let k = i; k <= j; k++) out.set(totals[k][0], top);
      i = j + 1;
    }
  }
  if (m) m.set(key, out);
  return out;
}
