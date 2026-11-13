// ================= 2.0 stock lists (v19.0c): 종목 search, my portfolio's stocks, 시장 tiles =================
// (v19.5b: 거래대금 상위 종목 became the 거래대금 chip of 종목 순위, src/v2/ranks.js.)
// Pure functions, no React and no Korean text. Unit tests: tests/test_v2_lists.py (run through Node).
import { num } from "./engine.js";
import { validRows } from "./track.js";
import { heldQty } from "./held.js";
import { ownCloseGroups } from "../data.js";

const DATE = /^\d{4}-\d{2}-\d{2}$/;

// A Korean-listed company: 기업분석 (the old app, built on DART filings) has a page for it. Funds (etf) are not companies.
export const isKrCompany = (s) => !!s && s.cls === "kr" && s.etf !== true;
// v19.1a: a Korean or US company has a 2.0 company page (company.jsx). Funds (etf) are not companies.
export const isCompany = (s) => !!s && (s.cls === "kr" || s.cls === "us") && s.etf !== true && !s.fund;

// ---------------- US stocks priced at an earlier close (v19.1c, Jack 2026-11-07) ----------------
// data.json pxd: a US stock whose last close is not the US date (usPxDate) carries its own price date, and no d1. Its price
// is shown with that date, and every list or total that includes it names it in one note (ui.jsx OwnCloseNote).
// ownCloseGroups(stocks, usPxDate) -> [{ date, ts }]: one group per date, newest first; tickers in screen order, each once;
// stocks missing from today's data (null) and stocks at the US date are left out. The rule lives in src/data.js so the
// old app groups the same way. ownCloses(load, stocks): the same for the loaded data ([] before it loads).
export { ownCloseGroups };
export function ownCloses(load, stocks) {
  return load && load.status === "ok" ? ownCloseGroups(stocks, load.data.usPxDate) : [];
}

// ---------------- 종목 search ----------------
// Korean and US listings (funds included: tapping one says 기업분석 is for Korean companies only). Order: the exact code or
// name, then names (Korean or English) or codes starting with the query, then names containing it; within each group the
// larger market cap first (a blank cap goes last: it only orders the list, it never decides what is in it).
export function searchStocks(load, q, n = 20) {
  const query = String(q || "").trim();
  if (!query || !load || load.status !== "ok") return [];
  const up = query.toUpperCase();
  const groups = [[], [], []];
  for (const s of load.data.stocks) {
    if (!s || (s.cls !== "kr" && s.cls !== "us")) continue;
    const t = String(s.t).toUpperCase(), nk = String(s.nk || ""), ne = String(s.ne || "").toUpperCase();
    if (t === up || nk === query) groups[0].push(s);
    else if (t.startsWith(up) || nk.startsWith(query) || ne.startsWith(up)) groups[1].push(s);
    else if (nk.includes(query) || ne.includes(up)) groups[2].push(s);
  }
  const cap = (s) => (num(s.cap) != null ? num(s.cap) : -1);
  return groups.flatMap((g) => g.sort((a, b) => cap(b) - cap(a))).slice(0, n);
}

// ---------------- my portfolio's stocks ----------------
// Every stock held in any saved portfolio (held.js: imported + purchases − sales, more than 0 shares; v19.3d), once, in
// the order the portfolios list them, with today's row when the stock is in today's data (s) and the name saved with the
// holding otherwise.
export function myStocks(decks, load) {
  const out = [], seen = new Set();
  const byT = load && load.status === "ok" ? load.byT : new Map();
  for (const d of decks || []) {
    const bought = new Set(heldQty(d || {}).keys());
    for (const h of (d && d.holdings) || []) {
      if (!h || !bought.has(h.t) || seen.has(h.t)) continue;
      seen.add(h.t);
      const s = byT.get(h.t) || null;
      out.push({ t: h.t, nk: (s && s.nk) || h.nk || h.t, cls: (s && s.cls) || h.cls || null, s });
    }
  }
  return out;
}

// ---------------- 시장 tiles ----------------
// 코스피 and S&P 500: the last close of macro.json idxHist and its change from the close before (two official closes in a
// row); 국고채 3년: macro.json curve (level only); 원/달러: data.json fx (level only). macro.json has no daily change for the
// last two, so none is shown, never made up. Each tile carries its own content date; a value without a date it can be
// tied to is not shown either (value null: the screen shows "–"). why says what was missing (logged by the screen).
export function marketTiles(load) {
  const ok = !!(load && load.status === "ok");
  const m = ok ? load.macro : null;
  const idx = (key) => {
    const h = m && m.idxHist ? m.idxHist[key] : null;
    const rows = h ? validRows(h) : null;
    if (!rows) return { value: null, change: null, date: null, why: !ok ? "load" : !m ? "macro" : h ? "rows" : "missing" };
    const last = rows[rows.length - 1], prev = rows.length > 1 ? rows[rows.length - 2] : null;
    return { value: last[1], change: prev ? (last[1] / prev[1] - 1) * 100 : null, date: last[0], why: prev ? null : "one row" };
  };
  const kr3y = (() => {
    const c = m && m.curve;
    const i = c && Array.isArray(c.tenors) ? c.tenors.indexOf(3) : -1;
    const v = i >= 0 && Array.isArray(c.now) ? num(c.now[i]) : null;
    const date = c && DATE.test(c.date || "") ? c.date : null;
    return v == null || !date ? { value: null, date: null, why: !ok ? "load" : !m ? "macro" : "curve" } : { value: v, date, why: null };
  })();
  const fx = ok ? num(load.data.fx) : null;
  const fxDate = ok && DATE.test(load.data.fxDate || "") ? load.data.fxDate : null;
  return [
    { id: "kospi", kind: "index", ...idx("KOSPI") },
    { id: "sp500", kind: "index", ...idx("SP500") },
    { id: "kr3y", kind: "rate", ...kr3y, change: null },
    fx > 0 && fxDate ? { id: "usdkrw", kind: "fx", value: fx, change: null, date: fxDate, why: null }
      : { id: "usdkrw", kind: "fx", value: null, change: null, date: null, why: ok ? "fx" : "load" },
  ];
}
