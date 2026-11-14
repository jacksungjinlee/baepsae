// Test fixture: src/v2/ranks.js exactly as on claude/v19.5b-rankings at 94eea80 (v19.5b, not on this branch's base; this line added).
// tests/test_v197a_edit.py checks src/v2/fitpct.js gives the same 내 기준 numbers as its criteriaPct. Never edit below.
// ================= 홈 · 종목 순위 (v19.5b, docs/tasks/v19.5-home-lists-and-icon.md Part A) =================
// The seven lists behind the 종목 순위 card (rank.jsx): 시가총액 · 거래대금 · 거래 급증 · 기준별 · 내 기준 · 배당수익률 ·
// 업종별 등락. Pure functions, no React and no Korean text. Unit tests: tests/test_v2_ranks.py (run through Node).
//
// Rules every list keeps (spec Part A; CLAUDE.md "never rank by a blank field"):
// - Ranked within one market (kr or us), never the two together.
// - Only the build engine's universe (engine.universe: common shares with a price; no ETF or fund, no Korean preferred
//   share, no US preferred or depositary share by name or ticker) that passes the trading-value floor exactly as the build
//   step reads it (engine.liquidity: Korea val20, the 20-day average; US val, Yahoo's 3-month average; both 억원, at least
//   engine.LIQ_FLOOR_EOK = 5). A stock whose floor value is blank is left out (screen() does the same).
// - A stock without the list's number is left out, never ranked as 0.
// - Ties (the same number) are broken by market cap, larger first (a blank cap last), then by code so the order is stable.
// 업종별 등락 is the exception to the floor: its average must be exactly 왜 움직였나's 업종 평균 (track.peerGroup), so it
// uses peerGroup's own set (the universe with a change today) and never a second calculation.
import { CARDS, NA, num, universe, liquidity, LIQ_FLOOR_EOK, isFin, hasGroup, todayD1, dytOf, okDy, exactData,
  screen, percentileScores, cardRaw, activeCards, sameCompany, exclusionsHit, fyOf, growthBasis } from "./engine.js";
import { peerGroup, GROUP_MIN } from "./track.js";
import { warnings } from "./warn.js";

export { GROUP_MIN };
// The chips, in Jack's order (spec Part A).
export const RANK_CHIPS = ["cap", "val", "surge", "crit", "mine", "div", "ind"];
export const RANK_TOP = 10;            // the rolling list on 홈
export const RANK_FULL = 30;           // 전체 보기: the still list on the 종목 tab
export const SURGE_X = 2;              // 거래 급증: today's trading value at least 2x the 20-day average …
export const SURGE_CAP_JO = 0.3;       // … and a market cap of at least 3,000억원 (data.json cap is in 조원)
const EPS = 1e-9;

// 기준별: the second chip row (spec: 가치 · 수익성 · 재무 안정 · 낮은 변동성 · 추세 · 성장; 배당 and 대형주 have their own chips,
// pending cards never show). Each card ranks by the real value its basis line names, in the card's direction:
//   가치 (vz = 100 − percentile of pbr)  → pbr, lower first         "PBR 낮은 순"; only a PBR above 0 (see below)
//   수익성 (roe)                          → roe, higher first        "ROE 높은 순"
//   재무 안정 (debt, 해당 없음 for 금융)   → debt, lower first; financial companies left out (해당 없음, never ranked)
//   낮은 변동성 (lz = 100 − percentile of vol) → vol, lower first    "주가 변동 작은 순"
//   추세 (mz = percentile of mom)         → mom, higher first        "최근 1년 수익률 높은 순" (mom = the last close ÷ the close
//                                                                     252 trading days before − 1, fetch_data.perf_stats)
//   성장 (g3)                             → g3, higher first         "매출 증가율 높은 순"
// v19.5b decisions (Jack, 2026-11-12): one measure per market and a minimum size on the two report lists:
//   성장 KR: only a 2-year average (engine.growthBasis "y2", the rule the 후보 고르기 and company-page labels use: a g3 that is a
//            1-year change, or whose basis cannot be told from corp.json's rounded revenue, leaves the list). The base year's
//            revenue (rev[2], the year before last, 억원) must be at least MIN_EOK (100억원).
//   성장 US: g3 is Yahoo's revenueGrowth (the latest quarter against the same quarter a year before), as the pipeline keeps it.
//   수익성 KR: the equity the ROE is computed on (corp.json roeIn.eq, else eq when the ROE has no receipt) at least MIN_EOK.
//   US 수익성 · 성장 have no minimum yet: data.json has no US revenue or equity figure (the pipeline can add one).
// The pipeline's vz · lz · mz are rounded percentiles of exactly these fields (fetch_data.add_percentiles), so the order is the
// card's and the ties are gone. A test keeps this table in step with engine.CARDS.
// report: the card's number comes from the 사업보고서 (fy), so a Korean list of it may say "{year}년 사업보고서 기준" (rank.jsx).
// 가치 is not: its PBR is today's close ÷ the latest quarter's equity (corp.json bpsIn, bq), so its date line is the close date
// only (the company page's rule: a quarter label or no line, never a wrong year).
// pos (가치 only): a PBR of 0 or below is not a valuation (a negative book value, or a figure that rounds to 0 because one of
// its inputs is off: 진코스텍 and BRK-B on 2026-11-11), so it is left out like a blank instead of heading the list as the
// cheapest stock. The 가치 card itself still ranks them first (engine.cardRaw reads vz): a pipeline follow-up.
// US 가치 backup guard (Jack, 2026-11-12, J4): a US PBR far below what the company's own PER and ROE imply (PER > 0, ROE > 0
// and PBR < PER × ROE ÷ 100 ÷ US_PBR_LOW) is a book value in another currency than the price (Yahoo: KSPI, ERIC on
// 2026-11-11), so that row is left out. One-sided: a PBR far above is left in. The console names every row 가치 leaves out.
// Korean 가치 guard (Jack, 2026-11-13): a PBR that rounds to 0.00 (under KR_PBR_MIN, after the PBR ≤ 0 rule) is never a real
// valuation, so that row is left out too; the console names those rows (code and name) with a count. No other threshold.
export const CRIT = [
  { id: "value", field: "pbr", dir: -1, report: false, pos: true },
  { id: "profit", field: "roe", dir: 1, report: true },
  { id: "stable", field: "debt", dir: -1, finNA: true, report: true },
  { id: "lowVol", field: "vol", dir: -1, report: false },
  { id: "trend", field: "mom", dir: 1, report: false },
  { id: "growth", field: "g3", dir: 1, report: true },
];
export const critOf = (id) => CRIT.find((c) => c.id === id) || null;
// The cards a 내 기준 date line counts as report-based (KR: "{date} 종가 · {year}년 사업보고서 기준"). 배당 (dyt = the 사업보고서
// dividend ÷ today's close) is too; 가치 (latest-quarter equity, see above) · 낮은 변동성 · 추세 · 대형주 are not.
export const REPORT_CARDS = ["profit", "stable", "growth", "div"];
export const MIN_EOK = 100;            // 성장 (KR base-year revenue) · 수익성 (KR equity): at least 100억원 (corp.json 억원)
export const US_PBR_LOW = 4;           // the US 가치 guard: PBR under a quarter of PER × ROE ÷ 100
export const KR_PBR_MIN = 0.005;       // the Korean 가치 guard: a PBR under this rounds to 0.00

const capOf = (s) => { const c = num(s && s.cap); return c == null ? -Infinity : c; };
const byCode = (a, b) => (a.s.t < b.s.t ? -1 : a.s.t > b.s.t ? 1 : 0);

// items [{ s, v, … }] -> the same items, best first: v in the direction dir (1 = higher first, −1 = lower first), then the
// larger market cap, then the code. Items whose v is not a number are dropped (never ranked as 0).
export function ranked(items, dir = 1) {
  return items.filter((x) => num(x.v) != null).sort((a, b) => dir * (b.v - a.v) || capOf(b.s) - capOf(a.s) || byCode(a, b));
}

// One company, one row (Jack, 2026-11-08: "one company = one"): the US list carries some companies once per share class
// (GOOG · GOOGL, NWS · NWSA), each with the whole company's market cap. In a ranked list only the better-placed listing of a
// company stays (engine.sameCompany: the same name and the same total share count; FOX · FOXA stay two). Korean listings are
// never merged (preferred shares are already out of the universe).
export function oneEach(rows) {
  const kept = new Map();
  const out = [];
  for (const r of rows) {
    const name = r.s && r.s.cls === "us" && typeof r.s.nk === "string" ? r.s.nk.trim().replace(/\s+/g, " ").toLowerCase() : "";
    const same = name ? kept.get(name) : null;
    if (same && same.some((x) => sameCompany(x, r.s))) continue;
    if (name) kept.set(name, [...(same || []), r.s]);
    out.push(r);
  }
  return out;
}

// The stocks of one market a list may show: the build universe over the trading-value floor (see the top of this file). The
// console says once per loaded file and market how many the floor left out, and why (no floor value, or under 5억): at info
// level, and as a warning when a stock had no floor value (blank figures are a data problem; under 5억 is the rule working).
const baseMemo = new WeakMap();
export function rankBase(stocks, mk) {
  if (!Array.isArray(stocks)) return [];
  let m = baseMemo.get(stocks);
  if (!m) { m = {}; baseMemo.set(stocks, m); }
  if (!m[mk]) {
    const uni = universe(stocks, mk);
    let blank = 0, under = 0;
    m[mk] = uni.filter((s) => {
      const l = liquidity(s);
      if (l == null) { blank++; return false; }
      if (l < LIQ_FLOOR_EOK) { under++; return false; }
      return true;
    });
    console[blank > 0 ? "warn" : "info"](`[v2] rank lists (${mk}): ${m[mk].length} of ${uni.length} stocks over the trading-value floor; left out ${blank} with no `
      + `${mk === "kr" ? "val20" : "val"} and ${under} under ${LIQ_FLOOR_EOK} eok won`);
  }
  return m[mk];
}

// 1. 시가총액: cap (조원), largest first.
export const capList = (stocks, mk) => oneEach(ranked(rankBase(stocks, mk).map((s) => ({ s, v: num(s.cap) })), 1));
// 2. 거래대금: val (억원), largest first. Korea: that day's trading value; US: Yahoo's 3-month daily average (the line says so).
export const valList = (stocks, mk) => oneEach(ranked(rankBase(stocks, mk).map((s) => ({ s, v: num(s.val) })), 1));
// 3. 거래 급증 (Korea only; null under 미국: US data has no day's value or 20-day average): val ÷ val20, only at SURGE_X or
//    more and only for a market cap of SURGE_CAP_JO (3,000억원) or more. [] = none today (the screen says so).
export function surgeList(stocks, mk) {
  if (mk !== "kr") return null;
  return ranked(rankBase(stocks, mk).map((s) => {
    const v = num(s.val), avg = num(s.val20), cap = num(s.cap);
    const x = v != null && v >= 0 && avg > 0 ? v / avg : null;
    return { s, v: x != null && x >= SURGE_X - EPS && cap != null && cap >= SURGE_CAP_JO - EPS ? x : null };
  }), 1);
}
// 4. 기준별: one card of CRIT (see the table above). null for an unknown card. coByT (corp.json by code) is needed for the Korean
//    성장 and 수익성 lists (their basis and minimum size); without it those lists have no row.
const fin = (x) => typeof x === "number" && Number.isFinite(x);
// -> the reason a stock of the base is left out of card c's list, or null when it is in (critValue then is its number)
function critOut(c, s, mk, coByT) {
  const v = num(s[c.field]);
  if (v == null) return "blank";
  if (c.finNA && isFin(s)) return "fin";
  if (c.pos && !(v > 0)) return "pbrNotAbove0";
  if (c.id === "value" && mk === "kr" && v < KR_PBR_MIN) return "pbrRoundsTo0";
  if (c.id === "value" && mk === "us") {
    const per = num(s.per), roe = num(s.roe);
    if (per > 0 && roe > 0 && v < (per * roe) / 100 / US_PBR_LOW) return "pbrFarUnder";
  }
  if (mk === "kr" && (c.id === "growth" || c.id === "profit")) {
    const co = coByT ? coByT.get(s.t) || null : null;
    if (c.id === "growth") {
      const rev = co && Array.isArray(co.rev) ? co.rev : null;
      if (!rev || !rev.some(fin)) return "noRevenue";
      const b = growthBasis(s, co);
      if (b !== "y2") return b === "y1" ? "oneYear" : "basisUnclear";
      if (!(rev[2] >= MIN_EOK)) return "smallBase";
    } else {
      const eq = co && co.roeIn && fin(co.roeIn.eq) ? co.roeIn.eq : co && fin(co.eq) ? co.eq : null;
      if (eq == null) return "noEquity";
      if (eq < MIN_EOK) return "smallEquity";
    }
  }
  return null;
}
const critValue = (c, s, mk, coByT) => (critOut(c, s, mk, coByT) ? null : num(s[c.field]));
// The console names, once per loaded file, market and card, what the list leaves out besides blanks: counts, and the tickers of
// the 가치 rules (PBR at or below 0, the US guard).
const critNoted = new WeakMap();
function noteCrit(stocks, mk, c, coByT) {
  let m = critNoted.get(stocks);
  if (!m) { m = new Set(); critNoted.set(stocks, m); }
  const k = mk + "|" + c.id + "|" + (coByT ? 1 : 0);
  if (m.has(k)) return;
  m.add(k);
  const why = {};
  for (const s of rankBase(stocks, mk)) {
    const r = critOut(c, s, mk, coByT);
    if (r && r !== "blank" && r !== "fin") (why[r] = why[r] || []).push(r === "pbrRoundsTo0" ? `${s.t} ${s.nk || ""}`.trim() : s.t);
  }
  const parts = Object.entries(why).map(([r, ts]) => (c.id === "value" ? `${r} ${ts.length}: ${ts.join(", ")}` : `${r} ${ts.length}`));
  if (parts.length) console.info(`[v2] rank lists (${mk}): the ${c.id} list leaves out ${parts.join("; ")}`);
}
export function critList(stocks, mk, id, coByT = null) {
  const c = critOf(id);
  if (!c) return null;
  if (Array.isArray(stocks)) noteCrit(stocks, mk, c, coByT);
  return oneEach(ranked(rankBase(stocks, mk).map((s) => ({ s, v: critValue(c, s, mk, coByT) })), c.dir));
}
// "rows" (a row), "none" (the card's figure is there but no stock qualifies) or "nodata" (no stock of the base has the figure, or
// a Korean 성장 · 수익성 list has no corp.json to check its basis and size against).
export function critState(stocks, mk, id, coByT = null) {
  const c = critOf(id);
  if (!c) return null;
  const base = rankBase(stocks, mk);
  if (base.some((s) => !critOut(c, s, mk, coByT))) return "rows";
  if (mk === "kr" && (id === "growth" || id === "profit") && !(coByT && coByT.size)) return "nodata";
  return base.some((s) => num(s[c.field]) != null) ? "none" : "nodata";
}
// 6. 배당수익률. Korea: only the verified today's-close yield (engine.dytOf: data.json dyt, 0–30%; a file without the split
//    check (no divCheck) has none, so the list is empty and the screen says why in the console). US: Yahoo's yield as the
//    pipeline keeps it (data.json dy = Yahoo info dividendYield, the latest dividend rate a year ÷ the price, adjusted to
//    today's close; engine.okDy, 0–30%). warn: a Korean company with a 재무 경고 signal (warn.warnings(s, co).flags: 유동비율
//    under 100% · 이자보상배율 under 1 · 3 years of net loss · 자본잠식, corp.json fl) keeps its place and gets a chip.
const divValue = (s, mk) => (mk === "kr" ? (exactData() ? dytOf(s) : null) : okDy(s));
export function divList(stocks, mk, coByT = null) {
  const kr = mk === "kr";
  return oneEach(ranked(rankBase(stocks, mk).map((s) => {
    const v = divValue(s, mk);
    const w = kr && coByT ? warnings(s, coByT.get(s.t) || null) : null;
    return { s, v, warn: !!(w && w.flags.length) };
  }), 1));
}

// ---------------- 5. 내 기준 ----------------
// The latest portfolio (the last in store order, as company.myCards reads it) whose 기준 points give a live card at least 1
// point. null when there is none (the 내 기준 chip is hidden).
const LIVE = CARDS.filter((c) => !c.pending).map((c) => c.id);
export function pointsDeck(decks) {
  const ds = Array.isArray(decks) ? decks : [];
  for (let i = ds.length - 1; i >= 0; i--) {
    const p = ds[i] && ds[i].settings && ds[i].settings.points;
    if (p && typeof p === "object" && LIVE.some((id) => num(p[id]) > 0)) return ds[i];
  }
  return null;
}
// THE 내 기준 number of a stock (v19.7 Part D [B3]; v19.5b's 내 기준 list is its first reader, v19.7b's finder, compare
// screen and 담기 sheet will read it too): the stock's weighted 기준 score with these points (screen()'s own total: each
// card's percentile within the market's universe, 해당 없음 cards left out of the weights) as a percentile among all
// scorable stocks of the market (the universe, a number on every card that has points; before the trading-value floor, 빼기
// and any filter, so a stock a filter drops still has a number). -> Map t -> x for "상위 {x}%" (1 = the best 1%; ties share
// the average rank, as company.cardRanks reads one card). A stock that cannot be scored is not in the map ("—", never 0).
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
// The 내 기준 list: the build step's engine (engine.screen) with this portfolio's points and 빼기 switches, within the chosen
// market only (its 한국/미국 mix does not apply: the switch picks the market) and with no strictness cut (the list is a top
// 10 anyway); 꼭 담을 종목 are not set aside. Best total first, ties by market cap. Each row carries pct (criteriaPct).
// null without settings.
const mineMemo = new WeakMap();
export function mineList(stocks, mk, settings) {
  if (!settings || !settings.points) return null;
  const key = mk + "|" + JSON.stringify([settings.points, settings.exclude || {}]);
  let m = Array.isArray(stocks) ? mineMemo.get(stocks) : null;
  if (Array.isArray(stocks) && !m) { m = new Map(); mineMemo.set(stocks, m); }
  if (m && m.has(key)) return m.get(key);
  const out = mineRows(stocks, mk, settings);
  if (m) m.set(key, out);
  return out;
}
function mineRows(stocks, mk, settings) {
  const st = { ...settings, exclude: { ...(settings.exclude || {}) }, strict: "loose", mix: mk === "us" ? "us" : "kr", pinned: [] };
  const res = screen(stocks, st);
  const m = res.markets[mk];
  const pcts = criteriaPct(stocks, mk, settings.points);
  return oneEach(ranked((m ? m.survivors : []).map((x) => ({ s: x.s, v: x.total, pct: pcts.has(x.t) ? pcts.get(x.t) : null })), 1));
}
// Whether a 내 기준 list rests on a report number (KR date line): any card with points among REPORT_CARDS.
export const mineUsesReport = (points) => activeCards(points || {}).some((c) => REPORT_CARDS.includes(c.id));

// ---------------- 7. 업종별 등락 ----------------
// Every real industry group (engine.hasGroup) of the market with at least GROUP_MIN (5) companies priced today, exactly as
// 왜 움직였나 counts and averages them (track.peerGroup on one of its members: the universe with a change today, the plain
// average of today's changes). -> [{ ind, name, n, rose, fell, avg, cap, members }] highest average first (ties: the group's
// total market cap, then the group id). members: the group's stocks of that average, largest market cap first (the three
// logos, and the list a tap opens). name: the group's name as data.json writes it (indName of its largest member).
const indMemo = new WeakMap();
export function indGroups(stocks, mk) {
  if (!Array.isArray(stocks)) return [];
  let m = indMemo.get(stocks);
  if (!m) { m = {}; indMemo.set(stocks, m); }
  if (m[mk]) return m[mk];
  const uni = universe(stocks, mk);
  const byT = new Map(uni.map((s) => [s.t, s]));
  const first = new Map();
  for (const s of uni) if (hasGroup(s) && todayD1(s) != null && !first.has(s.ind)) first.set(s.ind, s);
  // peerGroup is asked with only that group's stocks of the market, in the file's order: its universe and same-group filter keep
  // exactly the stocks, in the same order, that it keeps from the whole file (each is a test on the stock alone), so its n, rose,
  // fell and average are the same numbers, without scanning the whole file once per group (a test compares the two).
  const ofInd = new Map();
  for (const s of stocks) if (s && s.cls === mk && first.has(s.ind)) (ofInd.get(s.ind) || ofInd.set(s.ind, []).get(s.ind)).push(s);
  const out = [];
  for (const [ind, s0] of first) {
    const g = peerGroup(s0, ofInd.get(ind));
    if (!g.ok) continue;
    const members = g.items.map((x) => byT.get(x.id)).filter(Boolean)
      .sort((a, b) => capOf(b) - capOf(a) || (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
    const named = members.find((s) => typeof s.indName === "string" && s.indName) || null;
    const cap = members.reduce((a, s) => a + (num(s.cap) || 0), 0);
    out.push({ ind, name: named ? named.indName : null, n: g.n, rose: g.rose, fell: g.fell, avg: g.avg, cap, members });
  }
  out.sort((a, b) => b.avg - a.avg || b.cap - a.cap || (a.ind < b.ind ? -1 : a.ind > b.ind ? 1 : 0));
  m[mk] = out;
  return out;
}
// 업종별 등락 on 홈 (Jack, 2026-11-12): two parts, "많이 오른 업종" (the highest averages first) and "많이 내린 업종" (the lowest
// first), at most n each. A group is in a part only when its average, as shown (one decimal), is above or below 0: a group that
// reads "0.0%" neither rose nor fell, and a falling group is never called one that rose a lot. -> { up: [...], down: [...] }
// (the 종목 tab's 전체 보기 shows every group, highest first: indGroups itself).
export function indParts(groups, n = 5) {
  const gs = Array.isArray(groups) ? groups : [];
  const r = (g) => Math.round(g.avg * 10);
  return { up: gs.filter((g) => r(g) > 0).slice(0, n), down: gs.filter((g) => r(g) < 0).reverse().slice(0, n) };
}
// The line under a group: "{n}개 중 {k}개 오름" when the average is 0 or up (k = companies up today), "{n}개 중 {k}개 내림"
// when it is down (k = companies down today). -> { up, k }
export const groupWord = (g) => (g.avg >= 0 ? { up: true, k: g.rose } : { up: false, k: g.fell });
// The companies of one group by market cap (the window a tapped group row opens): [{ s, v: cap }]. null when the group is
// not in the list.
// A company listed twice (US share classes, GOOGL · GOOG, NWS · NWSA) is one row here (oneEach), as in every other list; the
// group's line keeps peerGroup's own n and k (왜 움직였나's numbers).
export function groupList(stocks, mk, ind) {
  const g = indGroups(stocks, mk).find((x) => x.ind === ind);
  return g ? oneEach(g.members.map((s) => ({ s, v: num(s.cap) }))) : null;
}

// ---------------- the card's choice, remembered on this device ----------------
// { mk: "kr" | "us", chip: RANK_CHIPS, crit: CRIT id }. First open: 한국 · 시가총액 · 가치. The last choice is kept in this
// browser only (a per-viewer convenience: losing it loses nothing); every read and write inside try/catch, and anything that
// does not read as a choice reads as the first one. The preview page keeps its own key.
export const RANK_KEY = "baepsae2.rank.v1";
export const PREVIEW_RANK_KEY = "baepsae2.preview.rank.v1";
export const FIRST_PICK = { mk: "kr", chip: "cap", crit: "value" };
export function okPick(p) {
  return !!p && typeof p === "object" && (p.mk === "kr" || p.mk === "us") && RANK_CHIPS.includes(p.chip) && !!critOf(p.crit);
}
export function readPick(key = RANK_KEY) {
  try {
    const p = JSON.parse(localStorage.getItem(key) || "null");
    if (okPick(p)) return { mk: p.mk, chip: p.chip, crit: p.crit };
  } catch (e) { /* unreadable or blocked: the first choice */ }
  return { ...FIRST_PICK };
}
// -> true when it was saved
export function savePick(p, key = RANK_KEY) {
  if (!okPick(p)) return false;
  try { localStorage.setItem(key, JSON.stringify({ mk: p.mk, chip: p.chip, crit: p.crit })); return true; } catch (e) {
    console.warn("[v2] rank card choice not saved: " + ((e && e.message) || e));
    return false;
  }
}

// The chips shown for a market: all seven in order, without the two that do not apply: 거래 급증 under 미국 (no day's value or
// 20-day average) and 내 기준 when no portfolio has 기준 points (mine false). A chip whose list is empty stays (Jack, 2026-11-12):
// the card says why in place of the list (chipState: the data is missing, or nothing qualifies).
export function chipsFor(mk, mine) {
  return RANK_CHIPS.filter((c) => !(c === "surge" && mk !== "kr") && !(c === "mine" && !mine));
}
// The chip shown for a choice: the chosen one when it is offered, else the first chip.
export const shownChip = (chip, chips) => (chips.includes(chip) ? chip : chips[0]);

// One list for the card. -> { rows: [{ s, v, warn?, pct? }] | groups [...] , kind } or null when the chip is not offered.
// kind: "stock" (rows of stocks) or "ind" (rows of groups).
export function rankRows(load, mk, chip, crit, deck = null) {
  if (!load || load.status !== "ok") return null;
  const stocks = load.data.stocks;
  switch (chip) {
    case "cap": return { kind: "stock", rows: capList(stocks, mk) };
    case "val": return { kind: "stock", rows: valList(stocks, mk) };
    case "surge": { const r = surgeList(stocks, mk); return r ? { kind: "stock", rows: r } : null; }
    case "crit": { const r = critList(stocks, mk, crit, load.coByT || null); return r ? { kind: "stock", rows: r } : null; }
    case "mine": { const r = deck ? mineList(stocks, mk, deck.settings) : null; return r ? { kind: "stock", rows: r } : null; }
    case "div": return { kind: "stock", rows: divList(stocks, mk, load.coByT) };
    case "ind": return { kind: "ind", rows: indGroups(stocks, mk) };
    default: return null;
  }
}

// ---------------- what each chip has (cheap checks: no ranking, no engine screen, no 업종 scan) ----------------
// The card works out only the chosen chip's list (v19.5b review: every list at once made 홈's last long task ~500 ms at 4x CPU
// throttle). What every chip has is decided by these scans over the market's stocks, each exactly as wide as its list (a unit
// test holds "rows" equal to the list being non-empty). Each is "rows", "none" (the list's figures are there but no stock
// qualifies: "지금은 이 순위에 들어갈 종목이 없어요.", 거래 급증 its own approved line) or "nodata" (no stock of the market has the
// figure the list needs: "필요한 데이터가 아직 없어 이 순위를 보여 드릴 수 없어요."); Jack, 2026-11-12.
// 거래 급증: "nodata" when no stock over the floor has both val and val20 (the console says so with the count). null under 미국.
export function surgeState(stocks, mk) {
  if (mk !== "kr") return null;
  const base = rankBase(stocks, mk);
  const withData = base.filter((s) => num(s.val) != null && num(s.val) >= 0 && num(s.val20) > 0);
  if (!withData.length) return { state: "nodata", n: 0, of: base.length };
  const hit = withData.some((s) => s.val / s.val20 >= SURGE_X - EPS && num(s.cap) != null && s.cap >= SURGE_CAP_JO - EPS);
  return { state: hit ? "rows" : "none", n: withData.length, of: base.length };
}
// 내 기준 has a row exactly when screen() keeps one stock: over the floor, not removed by a 빼기 switch that is on, a number on
// every card with points (해당 없음 is fine) and at least one card that is not 해당 없음.
export function mineHasRows(stocks, mk, settings) {
  const points = (settings && settings.points) || {};
  const active = activeCards(points);
  if (!active.length) return false;
  const ex = (settings && settings.exclude) || {};
  return rankBase(stocks, mk).some((s) => {
    if (exclusionsHit(s).some((k) => ex[k])) return false;
    let real = false;
    for (const c of active) {
      const raw = cardRaw(s, c);
      if (raw == null) return false;
      if (raw !== NA) real = true;
    }
    return real;
  });
}
// 업종별 등락 has a row exactly when one real industry group of the market has GROUP_MIN companies priced today (peerGroup's set).
export function indHasGroups(stocks, mk) {
  const n = new Map();
  for (const s of universe(stocks || [], mk)) {
    if (!hasGroup(s) || todayD1(s) == null) continue;
    const k = (n.get(s.ind) || 0) + 1;
    if (k >= GROUP_MIN) return true;
    n.set(s.ind, k);
  }
  return false;
}
// 내 기준: "rows", "nodata" when a card with points has no figure for any stock of the market (e.g. 배당 on a file without the
// split check), else "none" (the 빼기 switches or the blanks leave nobody).
export function mineState(stocks, mk, settings) {
  if (mineHasRows(stocks, mk, settings)) return "rows";
  const base = rankBase(stocks, mk);
  const active = activeCards((settings && settings.points) || {});
  const bare = active.some((c) => !base.some((s) => { const raw = cardRaw(s, c); return raw != null && raw !== NA; }));
  return bare || !active.length ? "nodata" : "none";
}
// 배당수익률: "nodata" when the market has no yield figure at all (Korea: a file without the split check has no verified yield).
function divState(base, mk) {
  if (base.some((s) => divValue(s, mk) != null)) return "rows";
  if (mk === "kr" && !exactData()) return "nodata";
  return base.some((s) => num(mk === "kr" ? s.dyt : s.dy) != null) ? "none" : "nodata";
}
// 업종별 등락: "nodata" when no stock of the market has a change today, "none" when no group has GROUP_MIN of them.
function indState(stocks, mk) {
  if (indHasGroups(stocks, mk)) return "rows";
  return universe(stocks || [], mk).some((s) => todayD1(s) != null) ? "none" : "nodata";
}
// -> { base: the number of stocks over the floor (0: the market has no data at all, the card shows the load-failure message),
//      cap, val, div, ind, mine (null without a portfolio with points), surge (null under 미국), crit: { [card]: state } }
export function chipState(load, mk, deck = null) {
  if (!load || load.status !== "ok") return null;
  const stocks = load.data.stocks;
  const base = rankBase(stocks, mk);
  if (mk === "kr") mustMissing(stocks);
  const has = (f) => (base.some((s) => num(s[f]) != null) ? "rows" : "nodata");
  const ss = surgeState(stocks, mk);
  return {
    base: base.length,
    cap: has("cap"),
    val: has("val"),
    surge: ss ? ss.state : null,
    surgeOf: ss,
    crit: Object.fromEntries(CRIT.map((c) => [c.id, critState(stocks, mk, c.id, load.coByT || null)])),
    mine: deck ? mineState(stocks, mk, deck.settings) : null,
    div: divState(base, mk),
    ind: indState(stocks, mk),
  };
}

// ---------------- the date line's basis (KR) ----------------
// What a Korean list's date line adds after "{date} 종가" (Jack, 2026-11-12):
//   "report":  "{year}년 사업보고서 기준" (app.reportYear), only when it is true for every row shown (oneReportYear), else
//              nothing: 배당수익률, 기준별 수익성 · 재무 안정 · 성장, and 내 기준 with points on one of those cards (with or
//              without 가치: when its other statement cards have points too, the year line, or nothing when the rows' years differ).
//   "quarter": "각 회사의 최근 분기 재무제표 기준" (rank.quarter): 기준별 가치 (PBR = today's close ÷ the latest quarter's
//              equity, corp.json bpsIn · bq), and 내 기준 when 가치 is its only statement card with points.
//   null:      nothing (prices only: 시가총액 · 거래대금 · 거래 급증 · 낮은 변동성 · 추세 · 업종별 등락; every US list).
export function dateBasis(mk, chip, crit, points = null) {
  if (mk !== "kr") return null;
  if (chip === "div") return "report";
  if (chip === "crit") return crit === "value" ? "quarter" : critOf(crit) && critOf(crit).report ? "report" : null;
  if (chip === "mine") {
    if (mineUsesReport(points)) return "report";
    return activeCards(points || {}).some((c) => c.id === "value") ? "quarter" : null;
  }
  return null;
}
export const listReport = (mk, chip, crit, points = null) => dateBasis(mk, chip, crit, points) === "report";
// The one report year of the rows shown (fyOf: data.json fy, else corp.json fy), or null when a row has none or the rows span two
// years (then the line shows the close date only; the console names the years). -> { year, years: [sorted distinct], missing }
export function oneReportYear(rows, coByT = null) {
  const years = new Set();
  let missing = 0;
  for (const r of rows || []) {
    const y = fyOf(r.s, coByT ? coByT.get(r.s.t) || null : null);
    if (y == null) missing++; else years.add(y);
  }
  const ys = [...years].sort();
  return { year: ys.length === 1 && !missing ? ys[0] : null, years: ys, missing };
}

// ---------------- must-haves ----------------
// validate_data.MUST (a test keeps the two lists equal): a Korean must-have in today's data that is missing from the 시가총액 list
// (left out by the universe, the floor or a blank cap) is a loud console warning naming it. -> the missing codes.
export const MUST_KR = ["005930", "000660", "005380", "015760", "105560", "035420", "012450"];
const mustMemo = new WeakMap();
export function mustMissing(stocks) {
  if (!Array.isArray(stocks)) return [];
  if (mustMemo.has(stocks)) return mustMemo.get(stocks);
  const there = MUST_KR.filter((t) => stocks.some((s) => s && s.t === t && s.cls === "kr"));
  const listed = new Set(capList(stocks, "kr").map((r) => r.s.t));
  const out = there.filter((t) => !listed.has(t));
  if (out.length) console.warn(`[v2] rank lists: must-have Korean companies missing from the market-cap list (universe, floor or blank cap): ${out.join(", ")}`);
  mustMemo.set(stocks, out);
  return out;
}
