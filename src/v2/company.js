// ================= 2.0 company page (v19.1a, docs/tasks/v19.1-company-page.md Parts A-F) =================
// Pure functions, no React and no Korean text: the screens (src/v2/company.jsx, cotabs.jsx) turn the codes returned
// here into copy from src/copy/v2.js. Unit tests: tests/test_v2_company.py (run through Node).
//
// Every tile phrase is chosen by a fixed rule from the same numbers the tile shows (Part B), never by free text:
//   rule "na" = an input is missing ("판단할 자료가 없어요"), never a guess.
// "업종" is the `ind` group (hasGroup: never "other" / "etc" / missing) inside the same market, as 왜 움직였나 uses.
// Units: corp.json op / ni / rev are 억원; KR prices are 원; US prices are $ (data.json units).
import { num, hasGroup, universe, isStockLike, CARDS, NA, cardRaw, percentileScores, growthBasis, dividendStreak, dpsAgrees, okDy,
  krDivYield, DY_MAX } from "./engine.js";
import { STALE_DAYS } from "../data.js";
import { GROUP_MIN } from "./track.js";
import { DCF, reverseDcf } from "./dcf.js";
import { okCode } from "./routes.js";

export { DCF, dcfPerShare, reverseDcf, okAssume } from "./dcf.js";

// ---------------- thresholds (Part B; the old app's where it says so) ----------------
export const EARN_US_BAND = 3;                 // US: g3 >= 3 -> up, <= -3 -> down, else flat
export const VALUE_CHEAP = 0.8, VALUE_DEAR = 1.25, VALUE_MIN = 5;   // PBR vs the industry median; at least 5 with a PBR
export const BETA_BIG = 1.15, BETA_SMALL = 0.85;                    // the old app's 출렁임 thresholds (corp.jsx volTxt)
export const DIV_SAME = 0.03;                  // a raise within 3% reads 비슷하게 (the old app's dpsTrend band)
export const GROWTH_SAME = 1;                  // 실적 tab: within 1%p of the industry median reads 비슷하게
export const DISC_DAYS = 90;                   // fetch_data.py DISC_DAYS: disc.json keeps 90 days of insider reports
export const MILLION = 1000000;
const EPS = 1e-9;

export const round = (v, d = 0) => { const k = Math.pow(10, d); return Math.round(v * k) / k; };
export function median(vals) {
  const a = vals.filter((v) => typeof v === "number" && Number.isFinite(v)).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

// The company of a route code: a Korean or US company share in today's data (funds are not companies). null = not found.
export function findCompany(load, code) {
  if (!load || load.status !== "ok" || !okCode(code)) return null;
  const s = load.byT.get(code);
  return s && isStockLike(s) ? s : null;
}

// The stock's industry group in its own market (the stocks that can be ranked), memoised per loaded stock list.
const groupMemo = new WeakMap();
export function groupOf(stocks, s) {
  if (!s || !hasGroup(s) || (s.cls !== "kr" && s.cls !== "us") || !Array.isArray(stocks)) return [];
  let m = groupMemo.get(stocks);
  if (!m) { m = new Map(); groupMemo.set(stocks, m); }
  const key = s.cls + "|" + s.ind;
  if (!m.has(key)) m.set(key, universe(stocks, s.cls).filter((x) => hasGroup(x) && x.ind === s.ind));
  return m.get(key);
}

// ---------------- 실적 tile ----------------
// KR: operating profit [this year, last year, two years ago] (corp.json op, 억원). A loss this year comes first (적자예요),
// then up twice / down twice, else mixed. Number: the 2-year change when the base year was a profit, else this year's
// amount (a % change from a loss, or into one, means nothing). Any year missing -> na.
export function earnKr(co) {
  const op = co && Array.isArray(co.op) ? [0, 1, 2].map((i) => num(co.op[i])) : [null, null, null];
  if (op.some((x) => x == null)) return { rule: "na", op };
  const [a, b, c] = op;
  const rule = a < 0 ? "loss" : a > b && b > c ? "up" : a < b && b < c ? "down" : "mixed";
  const pct = rule !== "loss" && c > 0 ? (a / c - 1) * 100 : null;
  return { rule, op, pct, amount: pct == null ? a : null, fy: num(co.fy) };
}

// US until v19.2: g3 is Yahoo revenueGrowth (the latest quarter vs the same quarter a year ago, fetch_data.py
// apply_us_info). Shown only with the label that says so (co.tiles.usGrowth, Jack 2026-11-05; cofmt.usGrowthText).
// Never compared with a Korean figure.
export function earnUs(s) {
  const g = num(s && s.g3);
  if (g == null) return { rule: "na" };
  return { rule: g >= EARN_US_BAND ? "up" : g <= -EARN_US_BAND ? "down" : "flat", g };
}

// ---------------- 가치 tile ----------------
// PBR vs the median PBR of the industry group (same market). The median is rounded to 2 decimals, the way it is shown,
// so the two numbers on the tile always give the phrase. Fewer than 5 with a PBR (or no group) -> few.
export function valueTile(s, group) {
  const pbr = num(s && s.pbr);
  if (!(pbr > 0)) return { rule: "na" };
  const vals = (group || []).map((x) => num(x.pbr)).filter((v) => v != null && v > 0);
  if (vals.length < VALUE_MIN) return { rule: "few", pbr, n: vals.length };
  const med = round(median(vals), 2);
  const r = pbr / med;
  return { rule: r <= VALUE_CHEAP + EPS ? "cheap" : r >= VALUE_DEAR - EPS ? "dear" : "similar", pbr, med, n: vals.length };
}

// ---------------- 배당 tile ----------------
// KR yield: the latest 사업보고서's own 현금배당수익률 (data.json dy: DART alotMatter, at that year's price; the publication
// gate checks it), shown with that report year. Not dps / today's close: a split after the report, or a total dividend
// filed in the per-share row, makes that absurd (v19.1a review: 와이엔텍 28,593,458%). The per-share figures (dps, dps3)
// are used only when dps agrees with dy (engine.dpsAgrees); otherwise the trend is na (판단할 자료가 없어요).
const d3Of = (s, co) => (s && Array.isArray(s.dps3) ? s.dps3 : co && Array.isArray(co.dps3) ? co.dps3 : null);

// dps 0 -> none · a cut (latest < last year) -> cut · 2+ raises in a row -> streak · a raise of more than 3% -> raised ·
// else steady. dps missing, disagreeing with dy, last year's missing (nothing to compare), or dps3 disagreeing with dps -> na.
export function divKr(s, co) {
  const dps = num(s && s.dps), dy = okDy(s);                        // dy above 30% is not believed (engine.DY_MAX)
  const fy = num(s && s.fy) ?? (co ? num(co.fy) : null);
  const yieldPct = dy != null && fy != null ? dy : null;
  if (dps == null) return { rule: "na", dps: null, yieldPct, fy, dpsOk: false };
  if (!dpsAgrees(s)) return { rule: "na", dps, yieldPct, fy, dpsOk: false };
  if (dps === 0) return { rule: "none", dps: 0, yieldPct: fy != null ? 0 : null, fy, dpsOk: true };
  const d3 = d3Of(s, co);
  const cur = d3 ? num(d3[0]) : null, prev = d3 ? num(d3[1]) : null;
  if (cur == null || prev == null || cur !== dps) return { rule: "na", dps, yieldPct, fy, dpsOk: true };
  const base = { dps, yieldPct, fy, dpsOk: true, d3: [0, 1, 2].map((i) => num(d3[i])) };
  if (cur < prev) return { rule: "cut", ...base };
  const n = dividendStreak(d3);
  if (n >= 2) return { rule: "streak", n, ...base };
  if (cur > prev * (1 + DIV_SAME) + EPS) return { rule: "raised", ...base };
  return { rule: "steady", ...base };
}

// US until v19.2: data.json has no US dividend per share, only Yahoo's yield. Missing is not "no dividend".
export function divUs(s) {
  const dy = okDy(s);
  if (dy == null) return { rule: "na", yieldPct: null };
  return { rule: dy === 0 ? "none" : "pays", yieldPct: dy };
}

// 100만원어치 가지고 있으면 (US until v19.2): 1,000,000 x yield / 100, rounded to the nearest 1,000원 (before tax).
// null = no yield.
export function perMillion(yieldPct) {
  const y = num(yieldPct);
  if (y == null || y < 0) return null;
  return Math.round((MILLION * y) / 100 / 1000) * 1000;
}
// What the 100만원 line shows: null (no yield, or no dividend) · { under: true } (a payer whose amount is below
// 1,000원: never "약 0원") · { won } (rounded to 1,000원).
export function perMillionView(yieldPct) {
  const y = num(yieldPct);
  if (y == null || !(y > 0)) return null;
  return millionView((MILLION * y) / 100);
}
const millionView = (raw) => (raw < 1000 ? { under: true, raw } : { won: Math.round(raw / 1000) * 1000, raw });

// 100만원어치 for a Korean stock (Jack, 2026-11-05): 1,000,000 ÷ today's close (data.json price, the pxDate close) × the
// latest 사업보고서's dividend per share (dps), rounded to 1,000원, before tax. null (the line is hidden) when dps or the
// price is missing, the price is not above 0, or dps is 0 (that is 배당이 없어요: divKr "none"). The dps must be the one the
// card trusts: it agrees with the same report's yield (engine.krDivYield / dpsAgrees), so a split after the report or a
// total filed in the per-share row (와이엔텍) never turns into an absurd amount; above 30% a year is not believed (DY_MAX).
export function perMillionKr(s) {
  const y = krDivYield(s);                        // null without dps, a price above 0, or agreement with the report's yield
  if (y == null || !(y > 0) || y > DY_MAX) return null;
  return millionView((MILLION * s.dps) / s.price);
}

// 배당성향 (KR), on one basis: the report's dividend per share x shares over the same report's net income (corp.json ni[0],
// 억원), so both sides are that 사업보고서 (fy). Needs dps that agrees with dy, a profit and the share count. A result
// outside 0-100% is not shown (out: the value, for the console).
export function payout(s, co) {
  if (!s || s.cls !== "kr" || !co || !dpsAgrees(s)) return null;
  const d = num(s.dps), ni = Array.isArray(co.ni) ? num(co.ni[0]) : null;
  const sh = num(s.shr) || (num(co.shm) ? co.shm * 1e6 : null);
  const fy = num(co.fy) ?? num(s.fy);
  if (d == null || !(d > 0) || !(ni > 0) || !(sh > 0) || fy == null) return null;
  const pct = ((d * sh) / (ni * 1e8)) * 100;
  return pct > 0 && pct <= 100 ? { pct, fy } : { out: pct, fy };
}

// ---------------- 출렁임 tile ----------------
// Beta against the stock's own market. The screen shows the phrase only: single stocks have no estimation-error band
// in the data yet (CLAUDE.md: beta is shown with its band), so no bare beta number.
export function riskTile(s) {
  const b = num(s && s.beta);
  if (b == null) return { rule: "na" };
  return { rule: b > BETA_BIG ? "big" : b < BETA_SMALL ? "small" : "similar", beta: b };
}

// ---------------- 재무 경고 신호 (KR) ----------------
// The old app's flags (corp.json fl, written only when one fires): 유동비율 < 100% · 이자보상배율 < 1 · 3 years of net
// loss · 자본잠식. "No flag" is only a fact when every check really ran, and corp.json does not say which ran (financial
// sectors skip 유동비율 and 이자보상배율; a missing balance-sheet line skips others). So allRan needs the list of checks
// that ran (corp.json flRan, a field the pipeline does not write yet): until then the screen claims nothing when no flag
// fired. US: none until v19.2 (Yahoo's debtToEquity is not 부채비율).
export const WARN_CHECKS = ["cr", "icr", "l3", "imp"];
export function warnings(s, co) {
  if (!s || s.cls !== "kr" || !co) return { allRan: false, ran: null, flags: [] };
  const fl = co.fl && typeof co.fl === "object" ? co.fl : {};
  const flags = [];
  if (num(fl.cr) != null) flags.push({ code: "cr", x: fl.cr });
  if (num(fl.icr) != null) flags.push({ code: "icr", x: fl.icr });
  if (fl.l3) flags.push({ code: "l3" });
  if (fl.imp) flags.push({ code: "imp" });
  const ran = Array.isArray(co.flRan) ? WARN_CHECKS.filter((c) => co.flRan.includes(c)) : null;
  const q = typeof co.bq === "string" ? /^(\d{4})\.([1-4])Q$/.exec(co.bq) : null;
  return { allRan: !!ran && ran.length === WARN_CHECKS.length, ran, flags, fy: num(co.fy), quarter: q ? { y: Number(q[1]), q: Number(q[2]) } : null };
}

// ---------------- 내 기준과 맞는 정도 (the 8 live criteria cards) ----------------
export const RANK_CARDS = CARDS.filter((c) => !c.pending).map((c) => c.id);
// The cards the user picked: the latest saved portfolio's cards with points (CARDS order); none -> the first two.
export function myCards(decks) {
  const ds = Array.isArray(decks) ? decks : [];
  for (let i = ds.length - 1; i >= 0; i--) {
    const p = ds[i] && ds[i].settings && ds[i].settings.points;
    if (!p || typeof p !== "object") continue;
    const ids = RANK_CARDS.filter((id) => num(p[id]) > 0);
    if (ids.length) return { ids, picked: true };
  }
  return { ids: RANK_CARDS.slice(0, 2), picked: false };
}

// Rank of one stock on each card, within its market ("market") or its industry group ("ind"). Percentiles as
// engine.percentileScores (higher = better on that card, ties share a rank). top <= 50 -> { side: "top", pct } (상위),
// else { side: "bottom", pct } (하위). Financial companies on 재무 안정 -> na; a blank -> blank. Never ranks by a blank.
const rankMemo = new WeakMap();
function scoresFor(list, cardId) {
  let m = rankMemo.get(list);
  if (!m) { m = new Map(); rankMemo.set(list, m); }
  if (!m.has(cardId)) m.set(cardId, percentileScores(list, CARDS.find((c) => c.id === cardId)));
  return m.get(cardId);
}
export function cardRanks(s, stocks, scope = "market") {
  if (!s || (s.cls !== "kr" && s.cls !== "us")) return { n: 0, rows: [] };
  const list = scope === "ind" ? groupOf(stocks, s) : marketList(stocks, s.cls);
  if (scope === "ind" && list.length < GROUP_MIN) return { n: list.length, rows: [], few: true };
  const inList = list.some((x) => x.t === s.t);
  const rows = RANK_CARDS.map((id) => {
    const card = CARDS.find((c) => c.id === id);
    const raw = cardRaw(s, card);
    if (raw === NA) return { id, na: true };
    if (!inList || raw == null) return { id, blank: true };
    const sc = scoresFor(list, id);
    const v = sc.get(s.t), n = sc.size;
    if (v == null || !n) return { id, blank: true };
    const top = Math.ceil(100 - v + 100 / n - EPS);
    return top <= 50 ? { id, side: "top", pct: Math.max(1, top) } : { id, side: "bottom", pct: Math.max(1, Math.ceil(v - EPS)) };
  });
  return { n: list.length, rows };
}
const marketMemo = new WeakMap();
function marketList(stocks, cls) {
  let m = marketMemo.get(stocks);
  if (!m) { m = {}; marketMemo.set(stocks, m); }
  if (!m[cls]) m[cls] = universe(stocks, cls);
  return m[cls];
}

// ---------------- 실적 tab ----------------
// KR revenue growth vs the industry: only peers whose g3 has the same basis (engine.growthBasis: y2 = the 2-year average,
// y1 = the 1-year change; unclear rows are left out), same market. At least 5 such peers, else null.
export function growthVsInd(s, co, stocks, coByT) {
  if (!s || s.cls !== "kr") return null;
  const basis = growthBasis(s, co);
  const g = num(s.g3);
  if (!basis || g == null) return null;
  const vals = groupOf(stocks, s).filter((x) => num(x.g3) != null && growthBasis(x, coByT ? coByT.get(x.t) : null) === basis).map((x) => x.g3);
  if (vals.length < GROUP_MIN) return null;
  const med = round(median(vals), 1), mine = round(g, 1);
  return { basis, mine, med, n: vals.length, rule: mine > med + GROWTH_SAME ? "faster" : mine < med - GROWTH_SAME ? "slower" : "similar" };
}

// Annual figures oldest first for the bars and the table: [{ year, rev, op, ni }] (억원), null when any year is missing.
export function annualRows(co) {
  const fy = num(co && co.fy);
  if (!co || fy == null) return null;
  const pick = (k) => (Array.isArray(co[k]) ? [2, 1, 0].map((i) => num(co[k][i])) : [null, null, null]);
  const rev = pick("rev"), op = pick("op"), ni = pick("ni");
  return [0, 1, 2].map((i) => ({ year: fy - 2 + i, rev: rev[i], op: op[i], ni: ni[i] }));
}
// Change of the latest year vs the year before, only from a profit (or positive revenue).
export const yoy = (cur, prev) => (num(cur) != null && num(prev) != null && prev > 0 ? (cur / prev - 1) * 100 : null);

// 주가는 무엇으로 움직였나 (the old DecompCard maths, src/corp.jsx decomposeReturn): 3-year price = earnings x 눈높이 (PER),
// as multipliers (3.20배 = 9.73배 x 0.33배: a true equation). EPS then = net income two reports back / shares; EPS now is
// data.json eps (its own basis: the latest four quarters when corp.json bq is set); the rest of the price change is the
// change in PER. why: "missing" (an input is not in the data) · "loss" (a loss at either end). head: up/down x which part
// was bigger (in log terms).
export function decompose(co) {
  if (!co || num(co.r36) == null || !num(co.shm)) return { why: "missing" };
  const epsNow = num(co.eps);
  const niThen = Array.isArray(co.ni) && co.ni.length > 2 ? num(co.ni[2]) : null;
  if (epsNow == null || niThen == null) return { why: "missing" };
  if (epsNow <= 0 || niThen <= 0) return { why: "loss" };              // a real loss at one end: no split into two parts
  const epsThen = (niThen * 100) / co.shm;
  const priceRatio = 1 + co.r36 / 100;
  if (priceRatio <= 0) return { why: "missing" };
  const eF = epsNow / epsThen;
  const mF = priceRatio / eF;
  const up = priceRatio >= 1;
  const eDom = Math.abs(Math.log(eF)) >= Math.abs(Math.log(mF));
  const price = num(co.price);
  return { eF, mF, priceRatio, epsThen, epsNow, head: (up ? "up" : "down") + (eDom ? "E" : "M"),
    priceNow: price, priceThen: price != null ? price / priceRatio : null,
    perNow: price != null ? price / epsNow : null, perThen: price != null ? price / priceRatio / epsThen : null,
    fyThen: num(co.fy) != null ? co.fy - 2 : null };
}

// ---------------- 가치 tab ----------------
// The industry PBR strip: every group member with a PBR as a dot on a 0..cap scale (cap: the 90th percentile, at least
// twice the median, so a few very high PBRs do not squash the rest; dots above it sit at the right edge).
export function pbrStrip(s, group) {
  const pts = (group || []).map((x) => ({ t: x.t, v: num(x.pbr) })).filter((p) => p.v != null && p.v > 0);
  if (!pts.some((p) => p.t === s.t) && num(s.pbr) > 0) pts.push({ t: s.t, v: s.pbr });
  if (pts.length < VALUE_MIN) return null;
  const sorted = pts.map((p) => p.v).sort((a, b) => a - b);
  const med = round(median(sorted), 2);
  const p90 = sorted[Math.min(sorted.length - 1, Math.floor(0.9 * (sorted.length - 1)))];
  const cap = Math.max(p90, 2 * med, num(s.pbr) || 0) * 1.05;
  const at = (v) => Math.min(1, v / cap);
  return { n: pts.length, med, cap, dots: pts.map((p) => ({ t: p.t, x: at(p.v), mine: p.t === s.t, over: p.v > cap })), mine: at(s.pbr), medX: at(med) };
}

// Industry medians of PER, EV/EBITDA and P/영업현금흐름 (KR: corp.json evE · pcf), same group. null below 5 values.
export function indMedian(group, get) {
  const vals = (group || []).map(get).filter((v) => v != null && v > 0);
  return vals.length >= VALUE_MIN ? { med: median(vals), n: vals.length } : null;
}

// 업종 지도 (ROE x PBR): this group's companies, with a least-squares line PBR = a + b x ROE fitted on the OTHER members
// only (at least 5 with both numbers, |ROE| <= 100%), so the company itself never bends the line it is compared with.
// pos: above / below / near (within 10% of the line) — only when the company's ROE lies inside the peers' ROE range;
// outside it the line would be stretched past its data, so pos is "out" (no sentence).
export function roePbrMap(s, group) {
  const ok = (p) => p.x != null && p.y != null && p.y > 0 && Math.abs(p.x) <= 100;
  const peers = (group || []).filter((x) => x.t !== s.t).map((x) => ({ t: x.t, x: num(x.roe), y: num(x.pbr) })).filter(ok);
  const me = { t: s.t, x: num(s.roe), y: num(s.pbr) };
  if (peers.length < VALUE_MIN || me.x == null || !(me.y > 0)) return null;
  const n = peers.length, mx = peers.reduce((a, p) => a + p.x, 0) / n, my = peers.reduce((a, p) => a + p.y, 0) / n;
  const sxx = peers.reduce((a, p) => a + (p.x - mx) * (p.x - mx), 0);
  if (!(sxx > 0)) return null;
  const b = peers.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0) / sxx, a = my - b * mx;
  const lo = Math.min(...peers.map((p) => p.x)), hi = Math.max(...peers.map((p) => p.x));
  const fit = a + b * me.x;
  const pos = me.x < lo || me.x > hi ? "out" : fit > 0 && Math.abs(me.y - fit) <= 0.1 * fit ? "near" : me.y > fit ? "above" : "below";
  return { pts: [...peers.map((p) => ({ ...p, mine: false })), { ...me, mine: true }], a, b, pos, n: n + 1, range: [lo, hi] };
}

// KR only (US until v19.2), with the old DcfCard's own defaults (discount 10%, 5년 뒤 성장률 2%, the growth rate fading
// over the 5 years to it): g is the first year's growth. Start profit: the latest 사업보고서's net income (corp.json ni[0],
// fy). why: "us" · "notReady" (the old card's dcfReady, or no net income / shares) · "loss".
export function impliedGrowth(s, co, { disc = DCF.disc, term = DCF.term } = {}) {
  if (!s || s.cls !== "kr") return { why: "us" };
  if (!co || co.dcfReady !== true) return { why: "notReady" };
  const ni0 = num(co.ni && co.ni[0]);
  const price = num(s.price);
  const sharesM = num(co.shm) || (num(s.cap) && price ? (s.cap * 1e12) / price / 1e6 : null);
  if (ni0 == null || !(sharesM > 0) || !(price > 0)) return { why: "notReady" };
  const inputs = { disc, term, ni0, sharesM, fy: num(co.fy), fade: DCF.fade };
  if (ni0 <= 0) return { why: "loss", ...inputs };
  const r = reverseDcf({ price, ni0, sharesM, fade: DCF.fade, disc, term });
  if (!r) return { why: "notReady" };
  return r.edge ? { edge: r.edge, ...inputs } : { g: r.g, ...inputs };
}

// Receipts for 가치 자세히: price / BPS = PBR and price / EPS = PER, shown only when the arithmetic gives the number on
// screen (within the rounding of the data), never a receipt that disagrees with the ratio above it.
export function receipt(price, per, ratio, d) {
  const p = num(price), q = num(per), r = num(ratio);
  if (!(p > 0) || !(q > 0) || r == null) return null;
  const got = round(p / q, d);
  return Math.abs(got - r) <= Math.pow(10, -d) + EPS ? { price: p, per: q, value: r } : null;
}

// ---------------- 공시 tab (KR, disc.json) ----------------
// This company's 임원·주요주주 reports (90 days) and its 국민연금 5% filing, newest first. Amounts are estimates: shares x
// today's close (disc.json amt is the same estimate rounded to 0.1억원; it is not the trade price).
const ymd = (d) => (typeof d === "string" && /^\d{8}$/.test(d) ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : null);
export function discFor(disc, s) {
  if (!disc || !s || s.cls !== "kr") return null;
  const px = num(s.price);
  const rows = (Array.isArray(disc.insider) ? disc.insider : [])
    .filter((x) => x && x.t === s.t && Number.isInteger(x.q) && x.q !== 0 && ymd(x.d))
    .map((x) => ({ rc: x.rc, date: ymd(x.d), nm: typeof x.nm === "string" ? x.nm : "", pos: typeof x.pos === "string" && x.pos !== "-" ? x.pos : "",
      q: x.q, won: px > 0 ? Math.abs(x.q) * px : null }))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  const side = (xs) => ({ n: xs.length, won: px > 0 ? xs.reduce((a, x) => a + x.won, 0) : null });
  const n0 = (Array.isArray(disc.nps) ? disc.nps : []).find((x) => x && x.t === s.t && num(x.rt) != null && ymd(x.d)) || null;
  return { rows, buys: side(rows.filter((x) => x.q > 0)), sells: side(rows.filter((x) => x.q < 0)),
    nps: n0 ? { rt: n0.rt, chg: num(n0.chg), date: ymd(n0.d) } : null, asOf: typeof disc.asOf === "string" ? disc.asOf : null };
}

// The 공시 tab's content date and freshness, as the old app's 공시·수급 shows it: the newest filing in the file (newest),
// not the run date (asOf); stale when the file was published more than STALE_DAYS ago. listOk false = today's filing list
// did not come in, so the rows stop at newest: stale, counted from newest (at least a day). now: ms (tests).
export function discDate(disc, now = Date.now()) {
  if (!disc) return null;
  const newest = typeof disc.newest === "string" && /^\d{4}-\d{2}-\d{2}$/.test(disc.newest) ? disc.newest : null;
  const DAY = 86400000;
  const pub = Date.parse(disc.publishedAt || "");
  const sincePub = Number.isFinite(pub) ? Math.floor((now - pub) / DAY) : null;
  const sinceNewest = newest ? Math.floor((now - Date.parse(newest + "T00:00:00+09:00")) / DAY) : null;
  if (disc.listOk === false) return { date: newest, stale: true, days: Math.max(1, sinceNewest ?? 1), listOk: false };
  const stale = sincePub == null || sincePub > STALE_DAYS;
  return { date: newest, stale, days: stale ? sincePub : 0, listOk: true };
}

// ---------------- holdings ----------------
// Every saved portfolio that holds this stock today (the daily check's evaluation): [{ deckId, name, x }].
export function holdingsOf(ev, decks, t) {
  if (!ev || !ev.ok) return [];
  const out = [];
  for (const de of ev.decks) {
    if (!de || !de.ok) continue;
    const x = de.holdings.find((h) => h.t === t);
    const deck = (decks || []).find((d) => d.id === de.id);
    if (x && deck) out.push({ deckId: de.id, name: deck.name, x, deck });
  }
  return out;
}

// ---------------- fallback logo mark (Part G) ----------------
// Ten fixed colours (white letters read at 4.5:1 or more on each; no apricot, no price red or blue, no status amber),
// one per code by a stable hash, so a company keeps its colour everywhere.
export const MARK_COLORS = ["#1C2B45", "#2F5D62", "#3D5A3C", "#5B4A8B", "#6B4E3D", "#46536B", "#7A3E5D", "#355C7D", "#5E5A2E", "#4B3F72"];
export function markColor(code) {
  let h = 2166136261;
  for (const ch of String(code || "")) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; }
  return MARK_COLORS[h % MARK_COLORS.length];
}
export function markLetter(name, code) {
  const n = String(name || code || "").trim();
  const ch = n ? String.fromCodePoint(n.codePointAt(0)) : "";
  return /[a-z]/.test(ch) ? ch.toUpperCase() : ch;
}
