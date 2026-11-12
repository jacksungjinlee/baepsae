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
  screen, percentileScores, cardRaw, activeCards, sameCompany, exclusionsHit, fyOf } from "./engine.js";
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
// The pipeline's vz · lz · mz are rounded percentiles of exactly these fields (fetch_data.add_percentiles), so the order is the
// card's and the ties are gone. A test keeps this table in step with engine.CARDS.
// report: the card's number comes from the 사업보고서 (fy), so a Korean list of it may say "{year}년 사업보고서 기준" (rank.jsx).
// 가치 is not: its PBR is today's close ÷ the latest quarter's equity (corp.json bpsIn, bq), so its date line is the close date
// only (the company page's rule: a quarter label or no line, never a wrong year).
// pos (가치 only): a PBR of 0 or below is not a valuation (a negative book value, or a figure that rounds to 0 because one of
// its inputs is off: 진코스텍 and BRK-B on 2026-11-11), so it is left out like a blank instead of heading the list as the
// cheapest stock. The 가치 card itself still ranks them first (engine.cardRaw reads vz): a pipeline follow-up.
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
// 4. 기준별: one card of CRIT (see the table above). null for an unknown card.
const critValue = (c, s) => {
  const v = c.finNA && isFin(s) ? null : num(s[c.field]);
  return c.pos && !(v > 0) ? null : v;
};
export function critList(stocks, mk, id) {
  const c = critOf(id);
  if (!c) return null;
  return oneEach(ranked(rankBase(stocks, mk).map((s) => ({ s, v: critValue(c, s) })), c.dir));
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

// The chips shown for a market: all seven in order, without 거래 급증 under 미국 and without 내 기준 when no portfolio has 기준
// points (mine false). empty: chips whose list has no row at all and no approved empty line (rank.jsx passes them), left out
// too (never an empty box).
export function chipsFor(mk, mine, empty = []) {
  return RANK_CHIPS.filter((c) => !(c === "surge" && mk !== "kr") && !(c === "mine" && !mine) && !empty.includes(c));
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
    case "crit": { const r = critList(stocks, mk, crit); return r ? { kind: "stock", rows: r } : null; }
    case "mine": { const r = deck ? mineList(stocks, mk, deck.settings) : null; return r ? { kind: "stock", rows: r } : null; }
    case "div": return { kind: "stock", rows: divList(stocks, mk, load.coByT) };
    case "ind": return { kind: "ind", rows: indGroups(stocks, mk) };
    default: return null;
  }
}

// ---------------- which chips have rows (cheap checks: no ranking, no engine screen, no 업종 scan) ----------------
// The card works out only the chosen chip's list (v19.5b review: every list at once made 홈's last long task ~500 ms at 4x CPU
// throttle). Whether the other chips have any row is decided by these scans over the market's stocks, each exactly as wide as its
// list (a unit test holds each check equal to its list being non-empty).
// 거래 급증: "rows" (at least one), "none" (today's figures are there and nobody qualifies: the approved empty line) or "nodata"
// (no stock over the floor has both val and val20: the chip is not offered, the console says so with the count). null under 미국.
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
// -> { cap, val, div, ind: bool, surge: surgeState | null, crit: { [card]: bool }, mine: bool | null (no portfolio) }
export function chipState(load, mk, deck = null) {
  if (!load || load.status !== "ok") return null;
  const stocks = load.data.stocks;
  const base = rankBase(stocks, mk);
  if (mk === "kr") mustMissing(stocks);
  return {
    cap: base.some((s) => num(s.cap) != null),
    val: base.some((s) => num(s.val) != null),
    surge: surgeState(stocks, mk),
    crit: Object.fromEntries(CRIT.map((c) => [c.id, base.some((s) => critValue(c, s) != null)])),
    mine: deck ? mineHasRows(stocks, mk, deck.settings) : null,
    div: base.some((s) => divValue(s, mk) != null),
    ind: indHasGroups(stocks, mk),
  };
}

// ---------------- the date line's report year ----------------
// Whether a list rests on 사업보고서 numbers (KR only): 배당수익률, 기준별 수익성 · 재무 안정 · 성장, 내 기준 with points on one of
// those cards. Its date line may add "{year}년 사업보고서 기준" (app.reportYear) only when it is true for every row shown.
export function listReport(mk, chip, crit, points = null) {
  if (mk !== "kr") return false;
  if (chip === "div") return true;
  if (chip === "crit") return !!(critOf(crit) && critOf(crit).report);
  if (chip === "mine") return mineUsesReport(points);
  return false;
}
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
