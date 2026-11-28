// ================= 이번 주 정리 (v19.6e, docs/tasks/v19.6-records-alerts-dark.md Part E, board Weekly2) =================
// The numbers behind 홈's weekly card (weekly.jsx). Pure functions, no React and no Korean text (the words come from
// src/copy/v2.js C.weekly). Unit tests: tests/test_v196e_weekly.py (run through Node). The two switches are in weekcfg.js.
//
// When (weekState; coordinator's rule of 2026-11-22, rounds 2 and 3, after "once the week's data is final" and "a Friday holiday
// makes Thursday the last day"): the week of pxDate (Monday to Sunday) is final when no Korean trading day comes after pxDate up to
// that Sunday, no US trading day comes after usPxDate up to that Sunday (tradedays.js, the app's copy of both holiday tables), and
// data.json publishedAt is on a KST date after pxDate (the close is in). So a normal week is final from Saturday's publish; a week
// whose Friday both markets close (Christmas 2026) from Friday's publish of Thursday's closes (already_published.py skips the Saturday
// runs then); a week where only Korea closes on Friday (2027-12-31) or only the US (Good Friday) once the other market's last close
// is in; the week of 2026-12-28 (Korea closed 12-31 and 01-01, the US only 01-01) from Friday 01-01's publish, which brings the US
// 12-31 close; and a file still at Thursday's close of a market that traded on Friday (a partial week) never. The card then stays until the next Korean close is published (it
// moves pxDate into a new week). A file without the week's start date (wkFrom: from before #170, or a day the pipeline could not
// set the Korean week) has no card. The caller also needs 홈's own daily check on fresh data (weekly.jsx: never on late, stale or
// failed data) and a portfolio block.
// Records "this week" are those dated Monday to Sunday (KST) of that week; "at the start" is every record dated before that
// Monday (held.js, so an undated 가진 종목 row counts as held before every dated record).
//
// 내 포트폴리오 (weekMoney), per stock of the portfolio (its records and the entries of stocks taken out this week, lots.recordSets):
//   gain = value now − value at the start − buys this week + sales this week; % = gain ÷ (value at the start + buys this week).
//   value at the start = shares held at the start × c1w (data.json, Part I.2: last week's close on today's share basis).
//   value now = shares held at the week's end (records dated up to its Sunday) × today's official close.
//   A USD price takes macro.json fxHist at both ends (coordinator, round 2: one source for the week): the rate of usWkFrom at the
//   start and the rate of usPxDate now, each "the close on that date, or the last close before it" (Part I.1, records.rateFor; never
//   data.json fx, which 홈's other numbers keep using: since 2026-11-24 it is fxHist's last row when the run read ECOS, else Yahoo's
//   rate, data.json fxSrc says which). A date fxHist does not reach leaves the stock out ("fx"), unless
//   only Korean non-trading days lie between fxHist's last row (marked final) and that date: that row is then its rate (weekRate,
//   round 3: ECOS has no row on a Korean holiday such as 2026-12-31, when the US trades).
//   buys = 샀어요 records of the week at their own rate (lots.purchaseRate); sales = 팔았어요 records of the week at their own rate.
//   A 가진 종목 row dated in the week (금액으로 넣기 dates its row with that day's close) is not a buy: nothing says it was bought then.
//   A stock whose week cannot be worked out is left out of both ends and named (left: [{ t, nk, why }], never counted as 0). One
//   stock is either counted or named, never both (a stock with a history entry and a holding again counts only when both do):
//     none · own · week · nv   no usable c1w for shares held at the start (blank; priced at its own date; its market's week date
//                              could not be read or the US prices are from another week; Naver-confirmed under WEEK_NV "out")
//     split                    a stock split recorded after its c1w date (the portfolio's or data.json's splits): c1w would be
//                              on the old share basis (the pipeline blanks such a c1w; this is the screen's own guard)
//     fx                       a USD amount without a rate (fxHist at either end, a record's own)
//     absent · price           not in today's data, or no price today, while shares are held at the week's end
//     made                     an undated 가진 종목 row of a portfolio made after the week began (its start holding is unknown)
//     imp                      a 가진 종목 row dated in the week (금액으로 넣기 or a dated quantity: not a 샀어요 record)
//     out                      taken out of the portfolio from the week's Monday on, either with shares left in its history entry
//                              (기록 없이 빼기) or with no history entry at all (no sale or dividend: store.withoutHolding drops its
//                              records, and only the removal mark (removed) and the change log (changes, kind "remove", also from
//                              종목 바꾸기) remain). A stock the change log names may never have been bought (종목 바꾸기 can take out a
//                              planned stock); it is named all the same: the records cannot tell, and a name is never hidden.
//     name                     a row added by name only (no code, not in the data: its week cannot be checked)
//   코스피 (kospiWeek): macro.json idxHist KOSPI, over the same money as the portfolio's (Jack, 2026-11-27, answer 13: "Yes, same
//   money flows"; Track 2 audit 4.1), by 내 수익's own rule (v19.6a A.5 [Q4], lots.kospiMirror): each counted stock's value at
//   the start is one lot bought at wkFrom's close; each counted 샀어요 record's won amount buys 코스피 at the last close before
//   its date (track.closeBefore's rule: a record saved with the price left empty carries that close); each counted 팔았어요
//   record sells the same fraction of that stock's 코스피 units as of its shares, at the last close before its date. 코스피's
//   gain is divided by the portfolio's own denominator (value at the start + buys this week), so both percentages answer the
//   same question. A week with no buy or sale is the plain change, close of wkFrom to close of pxDate (both rows must be there).
//   Dividends stay out of both, as in the portfolio's gain. The tile's words are unchanged ("코스피 {pct}").
// 받은 배당 (weekDivs): dividend records of the week, the stocks taken out included, in won (USD at the record's own rate; one
//   without a rate is counted in noFx, the approved tax.divNoFx line names the count).
// 공시 (weekFilings): v19.6b's own cards (look.js issueCards · insiderCards · npsCards, the same rules: held stocks, 1억원, the
//   approved shapes) for the stocks held at the week's end, dated in the week. A 확인했어요 mark does not take a filing out of the
//   week's count. The insider cards come back as a list: the screen counts only the ones 오늘 볼 것 can show (while look.js ROLE_OF
//   is null, none). Only when today's filings were checked (home.filingsChecked) and the day's 주요사항 list came in; otherwise the
//   tile is left out (never a count from a list that stopped). No Korean stock held: no tile (the filings are Korean).
// 다음 주 (nextWeek): look.dateRows (US 실적 발표 and 배당락일 of the held stocks) for next Monday to Sunday, none before today.
// 가장 많이 움직인 종목 (weekMover): the held stock with the largest |price ÷ c1w − 1|; its reason only from 왜 움직였나's
//   same-industry rule (track.peerGroup: GROUP_MIN, TOGETHER_SHARE) run on the week's moves: "fell" (it fell and at least 80% of
//   its group fell) or "rose" (the mirror, [Q12]); otherwise none.
import { num, isUsdPrice } from "./engine.js";
import { isDay, isTradingDay } from "./tradedays.js";
import { heldUnits, UNIT, VIEW_SPLITS, importedUnits, okUnits, unitEvents } from "./held.js";
import { purchaseRate, recordSets, splitSince, dataSplits } from "./lots.js";
import { validRows, peerGroup } from "./track.js";
import { issueCards, insiderCards, npsCards, dateRows, addDays, ROLE_OF } from "./look.js";
import { filingsChecked, holdsKorean } from "./home.js";
import { discDate } from "./company.js";
import { rateFor, rateEnv } from "./records.js";
import { kstDate } from "../data.js";
import { WEEK_NV } from "./weekcfg.js";

// The largest gap (days) between a market's week start and the price date the pipeline writes (fetch_data C1W_FROM_MAX_DAYS).
export const FROM_MAX_DAYS = 12;
const dayNum = (iso) => Date.parse(iso + "T00:00:00Z") / 86400000;
const inWeek = (d, w) => isDay(d) && d >= w.mon && d <= w.sun;

// ---------------- the week ----------------
// The Monday and Sunday of the week holding iso (YYYY-MM-DD).
export function weekOf(iso) {
  const back = (new Date(dayNum(iso) * 86400000).getUTCDay() + 6) % 7;
  const mon = addDays(iso, -back);
  return { mon, sun: addDays(mon, 6) };
}
// The week-start dates the rows' c1w use (data.json wkFrom · usWkFrom), each only when it is a real date before the week's Monday
// and at most FROM_MAX_DAYS before its market's price date; the US one also only when the US prices are from the same week as the
// Korean ones (usPxDate in pxDate's week), so a US move is never another week's. -> { kr, us, usSame }
export function weekStarts(data) {
  const out = { kr: null, us: null, usSame: false };
  if (!data || !isDay(data.pxDate)) return out;
  const { mon } = weekOf(data.pxDate);
  const ok = (from, px) => isDay(from) && isDay(px) && from < weekOf(px).mon && dayNum(px) - dayNum(from) <= FROM_MAX_DAYS;
  if (ok(data.wkFrom, data.pxDate)) out.kr = data.wkFrom;
  out.usSame = isDay(data.usPxDate) && weekOf(data.usPxDate).mon === mon;
  if (out.usSame && ok(data.usWkFrom, data.usPxDate)) out.us = data.usWkFrom;
  return out;
}

// Whether the week's numbers are final, and its dates. data: data.json.
// -> { ok: true, mon, sun, start (the Sunday before), first (the week's first Korean trading day), to (pxDate), nextMon, nextSun,
//      starts } | { ok: false, why: "pxDate" | "publishedAt" | "open" (a Korean trading day is still to come that week) | "usOpen"
//      (a US trading day after usPxDate that week, or no readable usPxDate in it) | "notFinal" (published on or before pxDate) | "wkFrom" }
export function weekState(data) {
  if (!data || !isDay(data.pxDate)) return { ok: false, why: "pxDate" };
  const pub = Date.parse(data.publishedAt || "");
  if (!Number.isFinite(pub)) return { ok: false, why: "publishedAt" };
  const { mon, sun } = weekOf(data.pxDate);
  for (let d = addDays(data.pxDate, 1); d <= sun; d = addDays(d, 1)) if (isTradingDay(d, "KR")) return { ok: false, why: "open" };
  // the US side of the same week (round 3): its last close must be in too (a US date before the week counts as open: the safe side)
  if (!isDay(data.usPxDate) || data.usPxDate > sun || data.usPxDate < mon) return { ok: false, why: "usOpen" };
  for (let d = addDays(data.usPxDate, 1); d <= sun; d = addDays(d, 1)) if (isTradingDay(d, "US")) return { ok: false, why: "usOpen" };
  if (!(kstDate(pub) > data.pxDate)) return { ok: false, why: "notFinal" };
  const starts = weekStarts(data);
  if (!starts.kr) return { ok: false, why: "wkFrom" };
  let first = null;
  for (let d = mon; d <= data.pxDate && !first; d = addDays(d, 1)) if (isTradingDay(d, "KR")) first = d;
  return { ok: true, mon, sun, start: addDays(mon, -1), first: first || data.pxDate, to: data.pxDate,
    nextMon: addDays(mon, 7), nextSun: addDays(mon, 13), starts };
}

// ---------------- one stock's week ----------------
// Its last-week close and the date it is from. s: a data.json row · starts: weekStarts · nv: WEEK_NV (weekly.jsx passes the mode in
// effect) · splits: [{ t, date, r }] (the portfolio's stored ones, data.json's) · today: KST.
// -> { c1w, date, nv (confirmed through Naver) } | { why: "absent" | "own" | "none" | "week" | "nv" | "split" }
// A c1wv other than "nv" (the gate warns on any) is read the same way: not confirmed between final files.
export function c1wOf(s, starts, nv = WEEK_NV, splits = null, today = null) {
  if (!s) return { why: "absent" };
  if (s.pxd != null) return { why: "own" };
  const c = num(s.c1w);
  if (!(c > 0)) return { why: "none" };
  const date = s.cls === "us" && !s.fund ? starts && starts.us : starts && starts.kr;
  if (!date) return { why: "week" };
  if (splits && splitSince(splits, s.t, date, today)) return { why: "split" };
  const flagged = s.c1wv != null;
  if (flagged && nv === "out") return { why: "nv" };
  return { c1w: c, date, nv: flagged };
}
// The week's move of one stock in % (price ÷ c1w − 1), or null (no usable c1w, or no price).
export function weekPct(s, starts, nv = WEEK_NV, splits = null, today = null) {
  const c = c1wOf(s, starts, nv, splits, today);
  const px = s ? num(s.price) : null;
  return c.c1w && px > 0 ? (px / c.c1w - 1) * 100 : null;
}

// ---------------- 내 포트폴리오 ----------------
// deck: the portfolio as the screens read it (with data.json's splits, held.js VIEW_SPLITS) · q: { byT, week (weekState), rateAt(date)
// -> won per dollar from fxHist | null, usPxDate, nv, splits, today }.
// -> { ok, gain, pct, start, buys, sells, end, n, left: [{ t, nk, why }], per: [{ t, nk, start, end, buys, sells, gain, nv }], nvUsed: [t],
//      legs: [{ t, start, u0, ev: [{ date, won, u }] }] (kospiWeek: one per counted record set, its value and share units at the
//      start, then its counted buys (+won, +units) and sales (−won, −units) of the week in held.js's order: by date, buys first) }
export function weekMoney(deck, q) {
  const w = q.week;
  const out = { start: 0, buys: 0, sells: 0, end: 0, n: 0, left: [], per: [], nvUsed: [], legs: [] };
  if (!deck) return { ok: false, gain: null, pct: null, ...out };
  const names = new Map(((deck.holdings) || []).filter((h) => h && h.t).map((h) => [h.t, h.nk]));
  const leave = (t, nk, why) => { if (!out.left.some((x) => x.t === t && x.nk === nk)) out.left.push({ t, nk, why }); };
  // made after the week began (a portfolio's createdAt is the KST date it was made): its undated rows' start holding is unknown
  const madeLate = isDay(deck.createdAt) && deck.createdAt > w.start;
  const endRate = q.rateAt(q.usPxDate);
  const rows = [];                                                            // one per record set: { t, nk, why } | { t, nk, r }
  const hist = new Set();                                                     // stocks with a history entry taken out from Monday on
  for (const set of recordSets(deck)) {
    const t = set.t;
    const entry = set.history ? (deck.history || [])[set.entry] : null;
    if (entry && !(isDay(entry.out) && entry.out >= w.mon)) continue;          // taken out before the week (or no readable date)
    if (entry) hist.add(t);
    const recs = set.history ? { ...set.recs, splits: deck.splits, [VIEW_SPLITS]: deck[VIEW_SPLITS], createdAt: deck.createdAt } : deck;
    const s = q.byT && q.byT.get(t) ? q.byT.get(t) : null;
    const nk = (s && s.nk) || names.get(t) || (entry && entry.nk) || t;
    const uStart = heldUnits(recs, w.start).get(t) || 0;
    const uEnd = heldUnits(recs, w.sun).get(t) || 0;
    const imp = (Array.isArray(recs.imported) ? recs.imported : []).filter((r) => r && r.t === t);
    let buys = 0, sells = 0, start = 0, end = 0, why = null, moved = false, nvRow = false;
    const moneyOf = new Map();                                                // this set's counted buys and sales: record -> won (+ in, − out)
    for (const p of Array.isArray(recs.purchases) ? recs.purchases : []) {
      if (!p || p.t !== t || !inWeek(p.date, w) || !(Number.isInteger(p.qty) && p.qty > 0) || !(num(p.price) > 0)) continue;
      moved = true;
      const r = purchaseRate(p, deck.planFx);
      if (!r) why = why || "fx"; else { const won = p.qty * p.price * r; buys += won; moneyOf.set(p, won); }
    }
    for (const r of imp) {
      if (!inWeek(r.date, w) || importedUnits(r) == null) continue;
      moved = true;
      why = why || "imp";                                                     // dated in the week: not a 샀어요 record (round 2, M2)
    }
    for (const x of Array.isArray(recs.sales) ? recs.sales : []) {
      if (!x || x.t !== t || !inWeek(x.date, w) || !okUnits(x.qty) || !(num(x.price) > 0)) continue;
      moved = true;
      const r = x.ccy === "USD" ? (num(x.fx) > 0 ? x.fx : null) : 1;
      if (!r) why = why || "fx"; else { const won = x.qty * x.price * r; sells += won; moneyOf.set(x, -won); }
    }
    if (!(uStart > 0) && !(uEnd > 0) && !moved) continue;                     // not part of this week
    const usRow = !!s && s.cls === "us" && !s.fund;
    if (uStart > 0) {
      if (madeLate && imp.some((r) => !r.date && importedUnits(r) != null)) why = why || "made";
      const c = c1wOf(s, q.week.starts, q.nv, q.splits, q.today);
      if (!c.c1w) why = why || c.why;
      else {
        const rate = isUsdPrice(s) ? q.rateAt(c.date) : 1;
        if (!(rate > 0)) why = why || "fx"; else { start = (uStart / UNIT) * c.c1w * rate; nvRow = c.nv; }
      }
    }
    if (uEnd > 0) {
      if (entry && entry.out <= w.sun) why = why || "out";
      else if (!s) why = why || "absent";
      else if (s.pxd != null) why = why || "own";                              // its price is another day's close, not the week's end
      else if (usRow && !q.week.starts.usSame) why = why || "week";
      else {
        const px = num(s.price);
        const rate = isUsdPrice(s) ? endRate : 1;
        if (!(px > 0)) why = why || "price";
        else if (!(rate > 0)) why = why || "fx";
        else end = (uEnd / UNIT) * px * rate;
      }
    }
    // the 코스피 side of this set (kospiWeek): its counted records with the share units held.js counts them for, in its order
    // (a record held.js does not count keeps u null: kospiWeek then leaves 코스피 out, never a guess)
    const ev = [];
    if (moneyOf.size) {
      const seen = new Set();
      for (const e of unitEvents(recs, t)) {
        if (!moneyOf.has(e.r) || seen.has(e.r)) continue;
        seen.add(e.r);
        ev.push({ date: e.r.date, won: moneyOf.get(e.r), u: e.u });
      }
      for (const [rec, won] of moneyOf) if (!seen.has(rec)) ev.push({ date: rec.date, won, u: null });
    }
    rows.push(why ? { t, nk, why } : { t, nk, r: { t, nk, start, end, buys, sells, gain: end - start - buys + sells, nv: nvRow },
      leg: { t, start, u0: start > 0 ? uStart : 0, ev } });
  }
  // taken out from the week's Monday on with no history entry (no sale or dividend): its records are gone (round 2, M1)
  const gone = new Map();
  for (const r of Array.isArray(deck.removed) ? deck.removed : []) if (r && typeof r.t === "string" && isDay(r.at) && r.at >= w.mon) gone.set(r.t, names.get(r.t) || null);
  for (const c of Array.isArray(deck.changes) ? deck.changes : []) {
    if (c && c.kind === "remove" && typeof c.t === "string" && isDay(c.at) && c.at >= w.mon) gone.set(c.t, gone.get(c.t) || (typeof c.nk === "string" ? c.nk : null));
  }
  for (const [t, nk] of gone) {
    if (hist.has(t)) continue;                                                 // its history entry speaks for it (counted or named above)
    const s = q.byT && q.byT.get(t);
    rows.push({ t, nk: (s && s.nk) || nk || t, why: "out" });
  }
  // one stock is counted whole or named, never both (round 2): any row of it left out takes every row of it out
  const lost = new Map();
  for (const x of rows) if (x.why && !lost.has(x.t)) lost.set(x.t, x);
  for (const x of rows) {
    if (lost.has(x.t)) { const l = lost.get(x.t); leave(l.t, l.nk, l.why); continue; }
    const r = x.r;
    out.start += r.start; out.end += r.end; out.buys += r.buys; out.sells += r.sells;
    out.legs.push(x.leg);                                                      // only a counted row's money: the same as buys · sells
    if (!out.per.some((p) => p.t === r.t)) out.n += 1;
    if (r.nv && !out.nvUsed.includes(r.t)) out.nvUsed.push(r.t);
    out.per.push(r);
  }
  // a row added by name only: no code, so its week cannot be checked (its value is the amount typed)
  for (const r of Array.isArray(deck.imported) ? deck.imported : []) {
    if (r && r.t == null && num(r.amountWon) > 0 && !(isDay(r.date) && r.date > w.sun)) leave(null, r.nk, "name");
  }
  const base = out.start + out.buys;
  const gain = out.end - out.start - out.buys + out.sells;
  const ok = out.n > 0 && base > 0;
  return { ok, gain: ok ? gain : null, pct: ok ? (gain / base) * 100 : null, ...out };
}

// 코스피's week (Jack, 2026-11-27, answer 13: the same money flows as the portfolio's). money: weekMoney's result (its start, buys,
// sells and legs); without it, or in a week with no counted buy or sale, the plain change from the close of wkFrom to the close of
// pxDate, exactly as before. With them, 내 수익's rule (v19.6a A.5 [Q4], lots.kospiMirror), one leg per counted record set:
//   its value at the start buys 코스피 at wkFrom's close (one lot); a buy's won amount (the portfolio's: USD at the record's own
//   rate) buys 코스피 at kospiBefore's close of its date; a sale sells the same fraction of the leg's 코스피 units as of its shares
//   (held.js units), at kospiBefore's close of its date, so the 코스피 side never holds less than nothing.
//   코스피's gain = units still held × pxDate's close + money from units sold − start − buys, over the portfolio's own denominator
//   (start + buys).
// -> { pct } | { pct, flows (records used) } | { pct: null, why }: "rows" (no readable rows) · "start" · "end" (wkFrom's or pxDate's
// row missing) · "flow" (a record's close missing: kospiBefore) · "sum" (the legs do not add up to the portfolio's start, buys and
// sales) · "units" (a sale while the leg holds no shares by held.js's count, or a record held.js does not count: records the
// store refuses). Every why leaves the 코스피 part out of the tile as before (weekly.jsx says which in the console); never a
// number made up.
export function kospiWeek(macro, data, starts, money = null) {
  const rows = validRows(macro && macro.idxHist ? macro.idxHist.KOSPI : null);
  if (!rows) return { pct: null, why: "rows" };
  const a = starts && starts.kr ? rows.find((r) => r[0] === starts.kr) : null;
  const b = data ? rows.find((r) => r[0] === data.pxDate) : null;
  if (!a || !b) return { pct: null, why: !a ? "start" : "end" };
  const legs = money && Array.isArray(money.legs) ? money.legs : [];
  if (!legs.some((l) => l && Array.isArray(l.ev) && l.ev.length)) return { pct: (b[1] / a[1] - 1) * 100 };
  const start = num(money.start), buys = num(money.buys), sells = num(money.sells);
  if (start == null || buys == null || sells == null || !(start + buys > 0)) return { pct: null, why: "sum" };
  let s0 = 0, fin = 0, fout = 0;
  for (const l of legs) {
    if (!l || num(l.start) == null || !Array.isArray(l.ev)) return { pct: null, why: "sum" };
    s0 += l.start;
    for (const e of l.ev) { if (!e || num(e.won) == null) return { pct: null, why: "sum" }; if (e.won > 0) fin += e.won; else fout -= e.won; }
  }
  if (Math.abs(s0 - start) > 0.5 || Math.abs(fin - buys) > 0.5 || Math.abs(fout - sells) > 0.5) return { pct: null, why: "sum" };
  let kNow = 0, kSold = 0, n = 0;
  for (const l of legs) {
    let units = l.start / a[1];                                               // 코스피 units of this leg: its start value at wkFrom's close
    let held = l.u0;                                                          // its share units (held.js)
    for (const e of l.ev) {
      if (!Number.isInteger(e.u)) return { pct: null, why: "units" };
      const k = kospiBefore(rows, e.date, a[0], b[0]);
      if (!k) return { pct: null, why: "flow" };
      n += 1;
      if (e.won > 0) { units += e.won / k; held += e.u; continue; }
      const u = -e.u;                                                         // a sale's units (held.js writes them below 0)
      if (u === 0) continue;                                                  // counted as 0 units after every share was sold (#184)
      if (!(held > 0)) return { pct: null, why: "units" };
      const du = units * Math.min(1, u / held);
      kSold += du * k;
      units -= du;
      held -= u;
    }
    kNow += units * b[1];
  }
  const gain = kNow + kSold - start - buys;
  return { pct: (gain / (start + buys)) * 100, flows: n };
}
// 코스피's close for a record dated d: the last close strictly before d (track.closeBefore's rule, as 내 수익's 코스피: a 샀어요 or
// 팔았어요 record saved with the price left empty carries the last published close, the one before its date), never before from
// (wkFrom: a Monday record takes wkFrom's close) and never after to (pxDate), and only when every day between that row and d is a
// Korean non-trading day (a weekend, a holiday; tradedays.js): a Korean trading day without its row is a missing close. -> close | null
export function kospiBefore(rows, d, from, to) {
  if (!isDay(d) || !isDay(from) || !isDay(to)) return null;
  let hit = null;
  for (const r of rows) { if (r[0] >= d || r[0] > to) break; hit = r; }
  if (!hit || hit[0] < from) return null;
  for (let x = addDays(hit[0], 1); x < d; x = addDays(x, 1)) if (isTradingDay(x, "KR")) return null;
  return hit[1];
}

// ---------------- 받은 배당 ----------------
// -> { won, n, noFx } (n: records counted; noFx: USD records without a rate, left out and counted)
export function weekDivs(deck, w) {
  const out = { won: 0, n: 0, noFx: 0 };
  const lists = [deck && deck.divs, ...((deck && deck.history) || []).map((e) => e && e.divs)];
  for (const l of lists) {
    for (const x of Array.isArray(l) ? l : []) {
      if (!x || !inWeek(x.date, w) || !(num(x.amount) > 0)) continue;
      const rate = x.ccy === "USD" ? (num(x.fx) > 0 ? x.fx : null) : 1;
      if (!rate) { out.noFx += 1; continue; }
      out.won += x.amount * rate;
      out.n += 1;
    }
  }
  return out;
}

// ---------------- 공시 ----------------
// held: Set of the codes held at the week's end · byT: today's data rows · now: for the filings' freshness (tests).
// -> { ok: true, kinds: { rights, cb, bw, nps }, ins: [insider cards of the week], skipped } | { ok: false, why: "none" | "noKr" |
//    "disc" | "stale" | "issue" }. The screen counts the insider cards it can show (kinds.ins) and adds them up.
export const FILING_KINDS = ["rights", "cb", "bw", "ins", "nps"];
export function weekFilings(disc, held, w, byT, now) {
  if (!held || !held.size) return { ok: false, why: "none" };
  const kr = [...held].some((t) => { const s = byT && byT.get(t); return s ? s.cls === "kr" : /^\d{6}$/.test(t); });
  if (!kr) return { ok: false, why: "noKr" };
  if (!disc || disc.status !== "ok" || !disc.data) return { ok: false, why: "disc" };
  if (!filingsChecked(disc, discDate(disc.data, now == null ? Date.now() : now))) return { ok: false, why: "stale" };
  const iss = issueCards(disc, held, w.sun, null, byT);
  if (iss.fail || iss.missing) return { ok: false, why: "issue" };
  const cover = { held, watched: new Set(), all: held };
  const kinds = { rights: 0, cb: 0, bw: 0, nps: 0 };
  for (const c of iss.cards) if (inWeek(c.date, w)) kinds[c.kind] += 1;
  for (const c of npsCards(disc, cover, w.sun, byT)) if (inWeek(c.date, w)) kinds.nps += 1;
  const ins = insiderCards(disc, cover, w.sun, byT, ROLE_OF).cards.filter((c) => inWeek(c.date, w));
  return { ok: true, kinds, ins, skipped: iss.skipped };
}

// ---------------- 다음 주 ----------------
// -> [{ t, nk, date, kind, s }] next Monday to Sunday (US local dates), earliest first (look.dateRows). As on Part B's 일정 card, never
// a date before today (KST; the Yahoo cache can be days old): when the card still shows into next week (a long holiday before the
// next Korean close), the rows start today.
export function nextWeek(byT, held, w, today = null) {
  const cover = { held, watched: new Set(), all: held };
  const from = isDay(today) && today > w.nextMon ? today : w.nextMon;
  return from > w.nextSun ? [] : dateRows(byT, cover, from, w.nextSun, null);
}

// ---------------- 가장 많이 움직인 종목 ----------------
// -> { t, nk, s, pct, why: "fell" | "rose" | null, n, nv } | null (no held stock with a week's move, or the largest rounds to 0.0%)
export function weekMover(held, byT, stocks, starts, nv = WEEK_NV, splits = null, today = null) {
  let best = null;
  for (const t of [...held].sort()) {
    const s = byT && byT.get(t);
    const m = weekPct(s, starts, nv, splits, today);
    if (m == null) continue;
    if (!best || Math.abs(m) > Math.abs(best.pct) + 1e-12) best = { t, s, pct: m };
  }
  if (!best || Math.round(Math.abs(best.pct) * 10) === 0) return null;
  const g = peerGroup(best.s, stocks, (x) => weekPct(x, starts, nv, splits, today));
  const why = g.ok && g.together ? "fell" : g.ok && g.togetherUp ? "rose" : null;
  // nv: its last-week close was confirmed through Naver (the footnote names it under WEEK_NV "note")
  return { t: best.t, nk: best.s.nk || best.t, s: best.s, pct: best.pct, why, n: g.ok ? g.n : 0, nv: !!c1wOf(best.s, starts, nv, splits, today).nv };
}

// ---------------- the week's exchange rate ----------------
// fxHist only (records.rateFor without its today branch, which reads data.json fx): the close of that date or the last one before it
// (Part I.1). Round 3: a date after fxHist's last row whose days in between are all Korean non-trading days (ECOS writes no row on a
// Korean holiday, e.g. 2026-12-31 while the US trades) takes that last row, only when fxHist marks it final; any other gap has no rate.
// Weekly only: rateFor itself is unchanged for its other callers. load: the data · today: KST. -> (date) => won per dollar | null
export function weekRate(load, today) {
  const env = { ...rateEnv(load, today), today: null };
  const fh = env.fxHist;
  return (date) => {
    const r = rateFor(date, env);
    if (r.ok) return num(r.fx) > 0 ? r.fx : null;
    if (r.why !== "notYet" || !fh || fh.final !== true) return null;
    const rows = validRows(fh);
    const last = rows ? rows[rows.length - 1] : null;
    if (!last || !(num(last[1]) > 0) || fh.asOf !== last[0]) return null;
    for (let d = addDays(last[0], 1); d <= date; d = addDays(d, 1)) if (isTradingDay(d, "KR")) return null;
    return last[1];
  };
}

// ---------------- the card of one portfolio ----------------
// deck: the portfolio (the screens' view) · load: the data · ctx: rules.todayCtx (byT) · disc: app.jsx's · nv: the WEEK_NV mode in
// effect (weekly.jsx) · now: tests. -> { ok: false, why } | { ok: true, week, money, kospi, divs, files, next, mover, kr, held }
export function weeklyModel({ deck, load, ctx, disc = null, nv = WEEK_NV, now = null } = {}) {
  if (!deck || !load || load.status !== "ok" || !load.data) return { ok: false, why: "load" };
  const week = weekState(load.data);
  if (!week.ok) return { ok: false, why: week.why };
  const byT = (ctx && ctx.byT) || load.byT || new Map();
  const today = kstDate(now == null ? Date.now() : now);
  const rateAt = weekRate(load, today);
  const splits = [...dataSplits(load.data).list, ...(Array.isArray(deck.splits) ? deck.splits : []), ...(Array.isArray(deck[VIEW_SPLITS]) ? deck[VIEW_SPLITS] : [])];
  const money = weekMoney(deck, { byT, week, rateAt, usPxDate: load.data.usPxDate, nv, splits, today });
  const held = new Set([...heldUnits(deck, week.sun)].filter(([, u]) => u > 0).map(([t]) => t));
  return {
    ok: true, week, nv, held, money,
    kospi: kospiWeek(load.macro, load.data, week.starts, money),
    divs: weekDivs(deck, week),
    files: weekFilings(disc, held, week, byT, now),
    next: nextWeek(byT, held, week, today),
    mover: weekMover(held, byT, load.data.stocks || [], week.starts, nv, splits, today),
    kr: holdsKorean([deck], byT),
  };
}

// ---------------- 닫기: this week's card hidden on this device ----------------
// A per-device convenience (localStorage, never in the records): { w: the week's Monday, ids: [portfolio id] }. Another week's
// value reads as nothing closed. Every read and write inside try/catch; blocked storage hides the card for this visit only.
export const WEEK_KEY = "baepsae2.weekly.v1";
export const PREVIEW_WEEK_KEY = "baepsae2.preview.weekly.v1";
export const CLOSED_MAX = 50;
export function readClosed(key, mon) {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "null");
    if (v && typeof v === "object" && v.w === mon && Array.isArray(v.ids)) return v.ids.filter((x) => typeof x === "string" && x.length <= 200);
  } catch (e) { /* unreadable or blocked: nothing closed */ }
  return [];
}
// -> true when it was saved
export function closeWeek(key, mon, id) {
  const ids = [...new Set([...readClosed(key, mon), id])].slice(-CLOSED_MAX);
  try { localStorage.setItem(key, JSON.stringify({ w: mon, ids })); return true; } catch (e) {
    console.warn("[v2] weekly: the card's close mark was not saved on this device (" + ((e && e.message) || e) + "); it stays closed for this visit");
    return false;
  }
}
