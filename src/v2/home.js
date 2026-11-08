// ================= 홈 (v19.3e, v19.3 Part H, board Home2): the numbers behind the new 홈 =================
// Pure functions, no React and no Korean text: home2.jsx turns the results into copy from src/copy/v2.js.
// Unit tests: tests/test_v2_home.py (run through Node).
//
// One block per portfolio that holds something today (the same portfolios 홈 showed before v19.3e, in store order):
//   rules   the four portfolio rules (pf.js pfState) for the hero: ✓, ! or 확인하지 못했어요, never ✓ on stale data
//   money   value, 오늘 {±amount} ({±%}) and 산 가격보다 {±amount} ({±%}) · 평균 단가를 넣은 {n}종목 기준
//   rows    가진 종목 {n}개: name, weight, today's change, in the navy shades by weight (Part C)
// Principles kept here:
// - Nothing is computed from stale or failed data: the caller passes the daily check's own ev (rules.js evaluateAll) and
//   gets nothing back when it is not ok.
// - 산 가격보다 counts only holdings with a 평균 단가 (Part H, acceptance 5): an imported row's typed 평균 단가 or 샀어요
//   records (they count as one). A holding without one is left out of both sides, never filled in. The money put in is
//   the 포트폴리오 tab's own (track.js deckMoney: built portfolios at the rate saved with each purchase, imported ones in
//   their own currency, US at today's rate with usdToday set so the screen says so). A built portfolio with a sale waits
//   for the lot maths (v19.6a), exactly as on 포트폴리오: no line.
// - 오늘 is the change between the last two official closes of every holding still in today's data (engine.todayD1: a US
//   stock priced at an earlier close, v19.1c pxd, has no change today). Left out (null) when
//   any of them has no change, a holding is valued by a typed amount only (it does not move), or a US listing is held
//   (its change is in dollars on another day and yesterday's rate is not in the data): the rule track.deckDayChange
//   already keeps for built portfolios.
import { num, todayD1 } from "./engine.js";
import { pfRows, pfState, isImported } from "./pf.js";
import { deckMoney, deckDayChange, lotsPending } from "./track.js";
import { heldQty } from "./held.js";

const EPS = 1e-9;

// Today's change of a set of holdings: [{ value (won), d1 (%), usd, frozen }] -> { pct, amount } | null.
export function dayMove(items) {
  if (!items || !items.length) return null;
  let now = 0, prev = 0;
  for (const x of items) {
    const v = num(x && x.value), d1 = num(x && x.d1);
    if (!x || x.frozen || x.usd || v == null || !(v >= 0) || d1 == null || d1 <= -100) return null;
    now += v;
    prev += v / (1 + d1 / 100);
  }
  return prev > 0 ? { pct: (now / prev - 1) * 100, amount: now - prev } : null;
}

// 산 가격보다: over the holdings whose money put in is known. per: deckMoney's per-stock { value, cost } (won).
// -> { n, cost, value, gain, ret, usdToday } | null (no holding with a 평균 단가)
export function gainOf(per, usdToday = false) {
  let n = 0, cost = 0, value = 0;
  for (const r of Object.values(per || {})) {
    const c = num(r && r.cost), v = num(r && r.value);
    if (!(c > 0) || !(v >= 0)) continue;
    n += 1; cost += c; value += v;
  }
  if (!n || !(cost > 0)) return null;
  return { n, cost, value, gain: value - cost, ret: value / cost - 1, usdToday: !!usdToday };
}

// The money card of one portfolio. deck: stored · de: evaluateDeck for it · ctx: rules.todayCtx.
// -> { ok: false, why, absent } | { ok: true, value, day: { pct, amount } | null, gain: gainOf | null, absent }
export function homeMoney(deck, de, ctx) {
  const m = deckMoney(deck, de, ctx);
  if (!m || !m.ok) return { ok: false, why: (m && m.why) || null, absent: (m && m.absent) || [] };
  let day = null;
  if (isImported(deck)) {
    const v = pfRows(deck, ctx);
    const live = v.rows.filter((r) => !r.absent);
    day = dayMove(live.map((r) => ({ value: r.value, d1: r.s ? todayD1(r.s) : null, usd: r.usd, frozen: r.frozen })));
  } else {
    const pct = deckDayChange(de);
    if (pct != null && Number.isFinite(pct) && pct > -100) day = { pct, amount: m.value - m.value / (1 + pct / 100) };
  }
  // A built portfolio with a sale or an imported row: 원금 waits for v19.6a (track.deckMoney leaves every cost out).
  const gain = !isImported(deck) && lotsPending(deck) ? null : gainOf(m.per, isImported(deck) && m.usdToday && usdCounted(deck, m.per, ctx));
  return { ok: true, value: m.value, day, gain, absent: m.absent || [] };
}

// usdToday only when a dollar 평균 단가 is among the holdings counted in 산 가격보다 (pf.avgOf in dollars).
function usdCounted(deck, per, ctx) {
  for (const [t, r] of Object.entries(per || {})) {
    if (!(num(r && r.cost) > 0)) continue;
    const s = ctx && ctx.byT ? ctx.byT.get(t) : null;
    if (s && s.ccy === "USD") return true;
  }
  return false;
}

// The 가진 종목 rows of one portfolio: [{ key, t, nk, w, d1, absent, frozen, usd, status, bigMove }], largest weight first
// (rows without a weight keep their order after them). status · bigMove: the built portfolio's own daily check
// (de.holdings), so its chips stay as they were.
// w: a 가진 종목 portfolio's share of everything held, only when every holding has a value today (pf.pfRows). A built
// portfolio's weight is its daily check's own (rules.deckWeights: the share among the held stocks with a 비중 규칙, x.w), the
// number its 비중 규칙 line on 포트폴리오 shows (tracking.jsx WeightLine), so the two screens agree. When a held stock of it
// has no such weight (its 비중 규칙 is off), every row of that portfolio takes its share of the whole instead (pf.pfRows),
// so no row is blank and every number under "비중" is a share of the same whole.
export function holdingRows(deck, de, ctx) {
  const v = pfRows(deck, ctx);
  const ev = new Map(((de && de.holdings) || []).map((x) => [x.t, x]));
  const imp = isImported(deck);
  const own = !imp && v.rows.every((r) => { const x = r.t ? ev.get(r.t) : null; return !!x && num(x.w) != null; });
  const rows = v.rows.map((r, i) => {
    const x = r.t ? ev.get(r.t) : null;
    const w = own ? x.w : v.ok ? r.w : null;
    return { key: r.key, t: r.t, nk: r.nk, w, d1: !r.absent && r.s ? todayD1(r.s) : null, absent: r.absent, frozen: r.frozen,
      usd: r.usd, i, x: x || null };
  });
  rows.sort((a, b) => (b.w ?? -1) - (a.w ?? -1) || a.i - b.i);
  return { rows, ok: v.ok };
}

// The portfolios 홈 shows: each saved portfolio holding something today, in store order (a built one with nothing bought
// yet is left out, as before v19.3e). ev: rules.evaluateAll (ok). -> [{ deck, de }]
export function heldDecks(decks, ev) {
  if (!ev || !ev.ok) return [];
  const out = [];
  for (const d of decks || []) {
    const de = ev.decks.find((x) => x.id === d.id);
    if (!de || !de.ok) continue;
    if (isImported(d) ? heldQty(d).size > 0 || (d.imported || []).some((r) => r && r.t == null && num(r.amountWon) > 0) : de.holdings.length > 0) out.push({ deck: d, de });
  }
  return out;
}

// One block per portfolio: { deck, de, st, money: homeMoney, list: holdingRows }. st: the four portfolio rules (pf.pfState)
// for a portfolio made with 가진 종목 넣기 only (Jack, 2026-11-08); a portfolio made with 포트폴리오 만들기 keeps its own
// per-stock rules and bands (the verdict band, today.jsx Hero) and is never judged by the four rules: st null.
export function homeBlocks(decks, ev, ctx, stocks) {
  return heldDecks(decks, ev).map(({ deck, de }) => ({ deck, de, st: isImported(deck) ? pfState(deck, ctx, stocks || []) : null,
    money: homeMoney(deck, de, ctx), list: holdingRows(deck, de, ctx) }));
}

// ---------------- 오늘 볼 것 · 공시 (Jack, 2026-11-08: "{name} 공시 {n}건 · {first filing title} · {date}") ----------------
// 홈 loads disc.json itself, once per visit, when a saved portfolio holds a Korean stock (app.jsx, home.holdsKorean; a
// company page loads the same file). Rows come from what is loaded, never from a list that stopped (company.discDate stale,
// or today's list did not come in): then none. One row per held stock with 임원·주요주주 지분 변동 reports dated within the
// last FILING_DAYS days (KST today included): n = those reports, date = the newest one's, up = the direction only when every
// one of them agrees (true: all raised the stake, false: all lowered it), else null ("지분 변동 보고", Jack 2026-11-08).
export const FILING_DAYS = 7;
const ymdOf = (d) => (typeof d === "string" && /^\d{8}$/.test(d) ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : null);
const dayNum = (iso) => Date.parse(iso + "T00:00:00Z") / 86400000;
// disc: app.jsx's { status, data } · held: Set of held codes · today: KST YYYY-MM-DD · fresh: company.discDate(disc.data).
// -> [{ t, n, date, up: true | false | null }] newest first
export function filingRows(disc, held, today, fresh) {
  if (!filingsChecked(disc, fresh) || !held || !held.size || !today) return [];
  const by = new Map();
  for (const x of Array.isArray(disc.data.insider) ? disc.data.insider : []) {
    if (!x || !held.has(x.t) || !Number.isInteger(x.q) || x.q === 0) continue;
    const date = ymdOf(x.d);
    if (!date || date > today || dayNum(today) - dayNum(date) >= FILING_DAYS) continue;
    const cur = by.get(x.t) || { t: x.t, n: 0, date: null, ups: 0, downs: 0 };
    cur.n += 1;
    if (x.q > 0) cur.ups += 1; else cur.downs += 1;
    if (cur.date == null || date > cur.date) cur.date = date;
    by.set(x.t, cur);
  }
  return [...by.values()].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.t < b.t ? -1 : 1))
    .map(({ ups, downs, ...r }) => ({ ...r, up: downs === 0 ? true : ups === 0 ? false : null }));
}
// Whether today's filings were checked: disc.json loaded and its list current (not stopped, today's list came in).
export const filingsChecked = (disc, fresh) => !!(disc && disc.status === "ok" && disc.data && fresh && !fresh.stale);

// Whether a saved portfolio holds a Korean stock today (the filings are about Korean companies): held records (held.js
// heldQty: 샀어요 · 팔았어요 · 가진 종목) of a stock whose market is 한국: the market saved with the holding, else the one in
// today's data (byT: load.byT · ctx.byT, when loaded), else for a 가진 종목 row its currency (a won listing).
// decks: store.data.decks.
export function holdsKorean(decks, byT = null) {
  for (const d of decks || []) {
    if (!d) continue;
    const cls = new Map((d.holdings || []).filter((h) => h && h.t && h.cls).map((h) => [h.t, h.cls]));
    const ccy = new Map((d.imported || []).filter((r) => r && r.t && r.ccy).map((r) => [r.t, r.ccy]));
    for (const t of heldQty(d).keys()) {
      const s = byT && typeof byT.get === "function" ? byT.get(t) : null;
      const c = cls.get(t) || (s && s.cls) || (ccy.has(t) ? (ccy.get(t) === "USD" ? "us" : "kr") : null);
      if (c === "kr") return true;
    }
  }
  return false;
}

// 오늘 볼 것's concentration card: the broken 한 업종 rule of a portfolio (its group, share, companies and limit), or null.
export function concentration(st) {
  const r = st && st.ok ? st.rules.find((x) => x.id === "ind" && x.state === "broken") : null;
  if (!r || !r.top || !r.top.name) return null;
  return { deckId: null, name: r.top.name, w: r.top.w, names: r.top.names || [], limit: r.limit };
}

// A portfolio made with 가진 종목 넣기 with nothing to look at today ("오늘은 할 일이 없어요" may show, on 오늘 볼 것 or in the
// band above): its four rules ran on today's data, none broke, the three that judge its weights and ranks (한 종목 · 한 업종 ·
// 내 기준) were all checked, and on everything it holds: no holding left out of 한 업종 (업종 정보 없음: pf.industryView's
// none, e.g. a typed-amount row with no ticker) and none left out of 내 기준 (unscored: ETFs, preferred shares, listings
// outside the universe, a typed-amount row; or a blank on a chosen 기준), since 홈 does not name what was left out. Its
// value is known too (the money card shows, no held stock missing from today's data). Only 재무 경고 may stay 확인하지
// 못했어요 (a US holding always leaves it so): the hero names it ("아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요"). A block
// with no rules (a portfolio made with 포트폴리오 만들기) is never quiet here: its band speaks. block: homeBlocks' { st, money }.
export const JUDGED_RULES = ["stock", "ind", "fit"];
export function quietBlock(block) {
  const st = block && block.st, m = block && block.money;
  if (!st || !st.ok || st.broken || !(st.checked > 0) || !Array.isArray(st.rules)) return false;
  if (JUDGED_RULES.some((id) => { const r = st.rules.find((x) => x.id === id); return !r || r.state !== "ok"; })) return false;
  if (!st.ind || !st.ind.none || st.ind.none.rows.length > 0) return false;                       // 업종 정보 없음
  if (!st.stats || !Array.isArray(st.stats.unscored) || st.stats.unscored.length > 0) return false;  // 기준 점수를 매길 수 없는 종목
  for (const r of (st.view && st.view.rows) || []) {                                               // a blank on a chosen 기준
    const p = st.stats.per && st.stats.per.get(r.key);
    if (!p || Object.values(p.cells).some((c) => c.st === "blank")) return false;
  }
  return !!(m && m.ok && !(m.absent && m.absent.length));
}

// The weight bar's length: the share of the portfolio against a full bar. A portfolio made with 가진 종목 넣기: the 한 종목
// limit (board Home2: a full bar = the limit). A portfolio made with 포트폴리오 만들기 is never judged by that rule
// (Jack, 2026-11-08): its full bar is the whole portfolio (barOf(w, 100)), so a bar never hints at a limit it does not have.
export const barOf = (w, limit) => (num(w) != null && num(limit) > 0 ? Math.min(1, Math.max(0, (w * 100) / limit)) : 0);
// A weight in whole % (at least one decimal under 1%, so a small holding never reads 0%).
export const weightPct = (w) => { const p = w * 100; return p > 0 && p < 0.95 ? Math.round(p * 10) / 10 : Math.round(p); };
export { EPS };
