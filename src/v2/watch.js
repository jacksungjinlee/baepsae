// ================= 2.0: 관심 종목 (v19.6c, docs/tasks/v19.6-records-alerts-dark.md Part C, board Watch2) =================
// The conditions of a watched stock checked on today's data, the 관심 종목 조건 rows of 홈's 오늘 볼 것, and the hitAt marks
// (the store part and its edits are in store.js). Pure: no React. Words come from src/copy/v2.js (C.watch). Unit tests:
// tests/test_v196c_watch.py.
//
// The three kinds (Part C; Jack, 2026-11-19, Q15: 주가 and PBR fire at or below the entered number, 배당수익률 at or above):
//   pxBelow   주가 at or below v: the stock's official close (Korea whole won; US dollars, 2 decimals) — data.json price.
//   pbrBelow  PBR at or below v: data.json pbr as the company page shows it (2 decimals). Blank when 0 or below (the spec), when the
//             pipeline blanked it (US statements not in dollars fcur, a foreign company's mismatch fgnCut, a US PBR near 0
//             pbrZero, the Korean unit check unitChk: the field is then missing) and when one of the 가치 list's guards
//             catches it (ranks.pbrGuardOf: a Korean PBR that rounds to 0.00, a US PBR far under its own PER × ROE): a
//             number the app itself does not trust never fires a condition. The console names those (watchGuardNote).
//   dyAtLeast 배당수익률 at least v (%): Korea only the verified today's-close yield (engine.dytOf, a file with the split check:
//             exactData); US the same current yield as 종목 순위's 배당수익률 list (engine.okDy). Shown as the company page
//             shows it (cofmt.yieldText: one decimal, two below 0.1%).
//             A 차등배당 company whose all-holder yield is blank (Jack, 2026-11-27, answer 14: "Yes, use the 소액주주 yield where it
//             exists (관심 종목 배당수익률 condition), labelled as such."): its 소액주주 yield (data.json dytSmall) where the company
//             page shows it (company.js divSmallView: the switch smallcfg.js SMALL_YIELD.on, exact data, the numbers agree, dvLine 3
//             or none, a payer with no all-holder yield) and both copy keys C.co.div.smallBasis · smallLine are set; never while
//             the all-holder yield (dytOf) is there. condState marks it small: the chip and 홈's row say "{y} · {smallBasis}" and
//             the card shows smallLine once (watch.jsx). Rounded, judged, marked and dated exactly like the all-holder yield.
// Each value is compared as it is shown, so the chip's "지금 {now}" and its state never disagree: "지금 75,000원" meets a
// 75,000원 price condition, "지금 0.80배" a 0.8배 PBR condition, "지금 4.0%" a 4% 배당수익률 condition.
// A blank value is never met (the chip says 정보 없음), never a hit, and never clears a hitAt.
// Met and the hit need fresh data (rules.dayState ok, the same rule as 홈's daily check): on stale or failed data the
// values still show beside the stale date line (or nothing, with the load-failure message), never a green check.
// hitAt (store.js): the stock's price date (KR pxDate, US usPxDate) on the first day this device saw the condition met on
// fresh data. The 오늘 볼 것 row shows while the data still shows that same close (e.g. from Friday evening's publish through a
// Monday holiday, with that close's date under it), never again for a condition that stays met; fresh data that shows it not
// met clears the mark (so the next time it is met it shows once more). v19.6c review S1: a stock priced at an earlier close
// than its market's (data.json pxd: a US halt) is never judged (its price is not today's: no check, no mark, no row); a value
// dated before the stored mark (an older publish still inside its freshness window) neither sets nor clears it; and when
// the records cannot be written (locked, storage full) there is no row at all, since no mark could keep it from repeating.
import { C, fill, nf } from "./format.js";
import { num, exactData, dytOf, okDy } from "./engine.js";
import { dayState } from "./rules.js";
import { pbrGuardOf } from "./ranks.js";
import { priceDate, timesText, yieldText } from "./cofmt.js";
import { subjectParticle } from "./track.js";
import { WATCH_KINDS, watchOf, watchOrder, withWatchMarks } from "./store.js";
import { divSmallView } from "./company.js";

export { WATCH_KINDS };
const round = (x, d) => Math.round(x * 10 ** d) / 10 ** d;
const usOf = (s) => !!s && s.cls === "us";

// The 소액주주 yield (%) the dyAtLeast condition reads for a Korean stock, else null: only where the all-holder yield is blank
// (dytOf) and the company page would show it (divSmallView, which also needs exact data and the switch), with both lines set.
// Without the corp row: divSmallView reads it only through krDivState's dps3a, which matters only when dyt is there.
function smallDy(s) {
  const Dv = C.co && C.co.div;
  if (!s || s.cls !== "kr" || !exactData() || dytOf(s) != null || !Dv || !Dv.smallBasis || !Dv.smallLine) return null;
  const v = divSmallView(s);
  return v ? v.y : null;
}
// Is the dyAtLeast value of s the 소액주주 yield? (Then the screens label it and the card says why.)
export const watchSmall = (s, k) => k === "dyAtLeast" && smallDy(s) != null;

// The value of kind k for stock s as the screens show it, else null (blank).
export function watchValue(s, k) {
  if (!s || (s.cls !== "kr" && s.cls !== "us")) return null;
  if (k === "pxBelow") {
    const p = num(s.price);
    return p > 0 ? (usOf(s) ? round(p, 2) : Math.round(p)) : null;
  }
  if (k === "pbrBelow") {
    const x = num(s.pbr);
    if (!(x > 0) || pbrGuardOf(s)) return null;
    const r = round(x, 2);
    return r > 0 ? r : null;
  }
  if (k === "dyAtLeast") {
    const y = usOf(s) ? okDy(s) : exactData() ? dytOf(s) ?? smallDy(s) : null;
    if (y == null) return null;
    return y > 0 && y < 0.1 ? round(y, 2) : round(y, 1);
  }
  return null;
}
// Is the shown value on the condition's side of v? pxBelow · pbrBelow at or below (≤, Jack 2026-11-19, Q15: "넣은 값 이하가
// 되면"), dyAtLeast at or above (≥). The 1e-9 only absorbs floating-point noise in the rounded values (both sides are shown
// with at most 2 decimals), so an equal shown value is met and the next shown step either way is decided by the sign.
export const condMet = (k, val, v) => (k === "dyAtLeast" ? val >= v - 1e-9 : val <= v + 1e-9);

// Fresh data: the daily check's own rule (stale, failed or undated data checks nothing).
export const watchFresh = (load, now) => !!load && load.status === "ok" && dayState(load, now).ok;

// The entered number as the chip shows it, and so as it is judged: a Korean price in whole won (condText shows
// Math.round(v)). The sheet only takes whole won, but store.js takes 2 decimals for any price, so a hand-edited records
// file can bring 74999.5: it reads "주가 75,000원 이하" and is judged as 75,000원 by the chip, the mark and the 홈 row alike
// (delta review, 2026-11-19). The stored number is left as it is. US prices, PBR and yields are shown and judged as stored.
export const condV = (s, c) => (c.k === "pxBelow" && s && !usOf(s) ? Math.round(c.v) : c.v);

// One condition on today's data: { k, v, val, state, date } — v the entered number as shown (condV) · state "met" · "not"
// (fresh data, a number) · "blank" (no number) · "stale" (a number, data not fresh, or the stock priced at an earlier close
// than its market's: shown, never judged). date = the stock's price date. small: true only when val is the 소액주주 yield
// (watchSmall; the key is left out otherwise, so every other result is exactly as before).
const marketDate = (load, s) => (usOf(s) ? load.data.usPxDate : load.data.pxDate) || null;
export function condState(load, s, c, fresh) {
  const val = watchValue(s, c.k), v = condV(s, c);
  const date = s && load && load.status === "ok" ? priceDate(load, s) : null;
  if (val == null) return { k: c.k, v, val: null, state: "blank", date };
  const sm = watchSmall(s, c.k) ? { small: true } : {};
  if (!fresh || !date || date !== marketDate(load, s)) return { k: c.k, v, val, state: "stale", date, ...sm };
  return { k: c.k, v, val, state: condMet(c.k, val, v) ? "met" : "not", date, ...sm };
}
// The conditions of an entry this app reads, in kind order (a later version's kinds are left out).
export const condsOf = (e) => WATCH_KINDS.map((k) => (e && Array.isArray(e.conds) ? e.conds.find((c) => c && c.k === k) : null)).filter(Boolean);

// ---------------- hitAt ----------------
// What fresh data says about each mark: Map "code|kind" -> the price date (set: met and no mark yet) or null (clear: a number
// that is not met). Nothing for blank values, stocks missing from the data, or data that is not fresh.
export function watchMarks(data, load, now) {
  const out = new Map();
  if (!watchFresh(load, now)) return out;
  const w = watchOf(data);
  for (const t of Object.keys(w)) {
    const s = load.byT.get(t);
    if (!s) continue;
    for (const c of condsOf(w[t])) {
      const st = condState(load, s, c, true);
      if (c.hitAt != null && st.date && st.date < c.hitAt) continue;             // an older close than the mark's: no word on it
      if (st.state === "met" && c.hitAt == null) out.set(t + "|" + c.k, st.date);
      else if (st.state === "not" && c.hitAt != null) out.set(t + "|" + c.k, null);
    }
  }
  return out;
}
// The store with the marks fresh data asks for, or null when nothing changes (app.jsx writes it; idempotent).
export function withWatchHits(data, load, now) {
  const m = watchMarks(data, load, now);
  return m.size ? withWatchMarks(data, m, now == null ? Date.now() : now) : null;
}
// 오늘 볼 것's 관심 종목 조건 rows: each condition met on fresh data that this device saw met first on today's close (no mark
// yet: it is being set now, or a mark of this same date), in list order then kind order. [{ t, s, k, v, val, date }], plus
// small: true where val is the 소액주주 yield (the row's line then labels it, as the chip does).
// canMark: the records can be written (writable, not locked); without it no row (the mark could not stop it repeating).
export function watchHits(data, load, now, canMark = true) {
  if (!canMark || !watchFresh(load, now)) return [];
  const w = watchOf(data), out = [];
  for (const t of watchOrder(w)) {
    const s = load.byT.get(t);
    if (!s) continue;
    for (const c of condsOf(w[t])) {
      const st = condState(load, s, c, true);
      if (st.state === "met" && (c.hitAt == null || c.hitAt === st.date)) {
        out.push({ t, s, k: c.k, v: st.v, val: st.val, date: st.date, ...(st.small ? { small: true } : {}) });
      }
    }
  }
  return out;
}

// ---------------- words ----------------
// The condition as the chip names it: "주가 75,000원 이하" · "주가 $150.00 이하" · "PBR 0.8배 이하" · "배당수익률 4% 이상".
const oneDec = (v) => nf(v, Math.round(v * 10) % 10 ? 1 : 0);          // 0.8 · 4 (no ".0": the board's "4% 이상")
export function condText(k, v, us) {
  const W = C.watch.c;
  if (k === "pxBelow") return us ? fill(W.pxUs, { x: nf(v, 2) }) : fill(W.pxKr, { x: nf(Math.round(v)) });
  if (k === "pbrBelow") return fill(W.pbr, { x: oneDec(v) });
  if (k === "dyAtLeast") return fill(W.dy, { x: oneDec(v) });
  return null;
}
// The value as "지금 {now}" shows it: "84,200원" · "$148.50" · "1.30배" (the company page's PBR) · "4.2%" (its yield).
// small (a 소액주주 yield, condState / watchHits): labelled as the company page labels it, "{y} · {C.co.div.smallBasis}" (두 종목
// 비교's cell; the 요약 tile "배당수익률 {y} · …"). Only a small value from watch.js comes here, so the label is set.
export function nowValue(k, val, us, small = false) {
  if (k === "pxBelow") return us ? "$" + nf(val, 2) : fill(C.app.won, { n: nf(val) });
  if (k === "pbrBelow") return timesText(val, 2);
  if (k === "dyAtLeast") return small && C.co.div.smallBasis ? `${yieldText(val)} · ${C.co.div.smallBasis}` : yieldText(val);
  return null;
}
// "{condition} 조건에 맞아요. 지금 {now}이에요." (이에요 / 예요 by the last syllable of {now}: track.subjectParticle's reading).
// A US price is read "…달러" ("$148.50" = 백사십팔 점 오 달러), so it always takes 예요 (review B1). small: as nowValue.
export function hitText(k, v, val, us, small = false) {
  const now = nowValue(k, val, us, small), condition = condText(k, v, us);
  const ye = (k === "pxBelow" && us) || subjectParticle(now) !== "i";
  return fill(ye ? C.watch.hitYe : C.watch.hit, { condition, now });
}

// The console line for the stocks whose PBR a 가치 guard kept from firing a condition (no silent hiding), once per load; and
// the one for the stocks whose 배당수익률 condition reads the 소액주주 yield (watchSmall: only with the switch on and both lines).
const guardSaid = new WeakSet();
export function watchGuardNote(data, load) {
  if (!load || load.status !== "ok" || guardSaid.has(load)) return;
  guardSaid.add(load);
  const w = watchOf(data);
  const hit = Object.keys(w).filter((t) => condsOf(w[t]).some((c) => c.k === "pbrBelow")).map((t) => load.byT.get(t)).filter((s) => s && num(s.pbr) > 0 && pbrGuardOf(s));
  if (hit.length) console.warn(`[v2] watch list: PBR left blank by the value guards for ${hit.length} stock(s): ${hit.map((s) => `${s.t} (${pbrGuardOf(s)})`).join(", ")}`);
  const small = Object.keys(w).filter((t) => condsOf(w[t]).some((c) => c.k === "dyAtLeast")).map((t) => load.byT.get(t)).filter((s) => watchSmall(s, "dyAtLeast"));
  if (small.length) console.info(`[v2] watch list: dividend yield on the small-shareholder basis (dytSmall, labelled) for ${small.length} stock(s): ${small.map((s) => `${s.t} (${s.dytSmall}%)`).join(", ")}`);
}
