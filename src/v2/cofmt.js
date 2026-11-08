// Small formatting helpers shared by the company page (company.jsx) and its tabs (cotabs.jsx). No Korean here: words
// come from src/copy/v2.js. US per-share figures are $ first with 원 small (Jack's decision 7, v19.1).
import { C, fill, nf, p1, mdText, wonText } from "./format.js";
import { eokText, signedPct } from "./deckcalc.js";
import { stockPriceDate } from "../data.js";

export const usOf = (s) => !!s && s.cls === "us";
// The price date of this stock: its market's date (KR pxDate, US usPxDate: never the Korean date for a US price, none then),
// or, v19.1c (Jack, 2026-11-07), the stock's own date when it is priced at an earlier close (data.json pxd: "미국 11월 4일
// 종가" on the company page, its tiles, source lines and date lines; no new words). A pxd that cannot be read: no date at
// all (the price is not at the market's date, and a wrong date is worse than none). data.js stockPriceDate.
export const priceDate = (load, s) => stockPriceDate(s, usOf(s) ? load.data.usPxDate : load.data.pxDate);
export const priceMd = (load, s) => mdText(priceDate(load, s));
// The date of the company page's date lines (DateLine: "{md} 기준" and the stale warning beside it). Normally the price date
// above. A pxd that cannot be read leaves the price without a date, but must not take the date line and its stale warning
// away with it: the line falls back to the market's date (US usPxDate, KR pxDate), with a console warning once per stock.
// No market date (a US stock in a file without usPxDate): none, as before.
const LINE_WARNED = new Set();
export function lineDate(load, s) {
  const d = priceDate(load, s);
  if (d || !s || s.pxd == null) return d;
  const market = stockPriceDate(null, usOf(s) ? load.data.usPxDate : load.data.pxDate);
  if (market && !LINE_WARNED.has(String(s.t))) {
    LINE_WARNED.add(String(s.t));
    console.warn(`[v2] ${s.t}: pxd ${JSON.stringify(s.pxd)} cannot be read; its price shows no date, the date line uses the market date ${market}`);
  }
  return market;
}
// v19.3e (v19.3 Part I, board CoSummaryUS): the US header reads "{date} 종가 (미국 시간)" beside the $ price and
// "약 {won} · 환율 {fx}원" under it (one line instead of the 원 line and the rate sentence). On since Jack's yes (2026-11-08);
// off is the header before v19.3e.
export const US_HEAD2 = true;
// The date beside a price: KR "11월 3일 종가" (why.close), US "미국 11월 3일 종가" (pending; before: the approved sentence).
export function closeLine(load, s) {
  const md = priceMd(load, s);
  if (!md) return null;
  if (!usOf(s)) return fill(C.why.close, { md });
  if (US_HEAD2 && C.co.usCloseTime) return fill(C.co.usCloseTime, { date: md });
  return C.co.usClose ? fill(C.co.usClose, { md }) : fill(C.app.usClose, { md });
}
// "약 445,900원" under a $ price, at today's rate (data.json fx), rounded to 100원.
export function wonOfUsd(load, usd) {
  const fx = load.data.fx;
  if (!(typeof fx === "number" && fx > 0) || !(typeof usd === "number" && Number.isFinite(usd))) return null;
  return fill(C.app.about, { x: fill(C.app.won, { n: nf(Math.round((usd * fx) / 100) * 100) }) });
}
// US_HEAD2: "약 445,900원 · 환율 1,390.5원" (the rate with one decimal, as the sentence it replaces).
export function wonLineUsd(load, usd) {
  const fx = load.data.fx;
  if (!C.co.usWon || !(typeof fx === "number" && fx > 0) || !(typeof usd === "number" && Number.isFinite(usd))) return null;
  return fill(C.co.usWon, { won: fill(C.app.won, { n: nf(Math.round((usd * fx) / 100) * 100) }), fx: nf(Math.round(fx * 10) / 10, 1) });
}
// The rate's own date under a US price, "원화는 {md} 환율 {fx}원으로 바꾼 값이에요.", or null. Without US_HEAD2 (or without
// its one line) always, as before. With it, whenever the rate is from another day than the price date the header shows
// (closeLine: the US close, or the stock's own earlier close), so the won amount never reads as that day's rate.
export function fxDateLine(load, s) {
  const fx = load.data.fx, md = mdText(load.data.fxDate);
  if (!usOf(s) || !C.co.fxWon || !md || !(typeof fx === "number" && fx > 0) || !(typeof s.price === "number" && Number.isFinite(s.price))) return null;
  if (US_HEAD2 && wonLineUsd(load, s.price) && md === priceMd(load, s)) return null;
  return fill(C.co.fxWon, { md, fx: nf(Math.round(fx * 10) / 10, 1) });
}
// The US 실적 figure says what it is (Jack, 2026-11-05): Yahoo's revenueGrowth is the latest quarter's revenue against the
// same quarter a year before, never a yearly or 3-year rate. "최근 분기 매출, 1년 전보다 +16.4%" (pending: null until then, and
// the number is left out with it, so it never shows without this label). g: a finite number, else null.
export function usGrowthText(g) {
  const L = C.co.tiles.usGrowth;
  return L && typeof g === "number" && Number.isFinite(g) ? fill(L, { pct: signedPct(g) }) : null;
}
// 지금 가격이 가정하는 것, first sentence (Jack, 2026-11-05): g >= 0 (0 included) -> headUp "… {g}% 는다는 …", g < 0 ->
// headDown "… {g}% 준다는 …" with g shown without its minus sign. g: the first-year rate already rounded to one decimal
// (cotabs Dcf); -0 reads as 0 (는다). Not a finite number, or the sentence not there -> null.
export function dcfHeadText(g) {
  if (typeof g !== "number" || !Number.isFinite(g)) return null;
  const L = g < 0 ? C.co.dcf.headDown : C.co.dcf.headUp;
  return L ? fill(L, { g: p1(Math.abs(g)) }) : null;
}
export const timesText = (x, d = 1) => fill(C.pick.receipt.times, { x: nf(x, d) });
// "12.3%", "−3.2%" (U+2212, as everywhere in 2.0), "0.0%" (no sign once rounded to zero).
export const pctText = (x) => { const r = Math.round(x * 10) / 10; return `${r < 0 ? "\u2212" : ""}${p1(Math.abs(r))}%`; };
// A dividend yield: two decimals below 0.1% so a payer never reads "0.0%" (삼천당제약 0.02%).
export const yieldText = (y) => (y > 0 && y < 0.1 ? `${nf(y, 2)}%` : pctText(y));
// "2.4만원" / "7,000원": 만원 style with one decimal when needed (so the 1,000원 rounding stays visible).
export function manWon(won) {
  if (won >= 10000) return fill(C.app.man, { n: nf(won / 10000, won % 10000 ? 1 : 0) });
  return fill(C.app.won, { n: nf(won) });
}
// Large won amounts: from 1억원 in 억원 · 조원 (the approved units, deckcalc.eokText), below that in 만원 style.
export function bigWon(won) {
  if (Math.abs(won) >= 1e8 && eokText(won / 1e8)) return eokText(won / 1e8);
  return wonText(won);
}
// Beta with its band (v19.1b data, Part O.1): one decimal, the true minus sign "−" (U+2212) for a negative end, "0.0" for
// zero. riskBandText: the 출렁임 tile's number ("코스피 1% → 평균 0.9~1.1%") or, with line = true, the 출렁임 line of the
// 가치 tab ("코스피가 1% 움직일 때 평균 …% 움직였어요."); both ends the same after rounding -> the single-number wording.
// Korea reads against 코스피, the US against S&P 500. r: company.js riskTile; no band -> null (no number, never a bare beta).
export const betaText = (v) => `${v < 0 ? "−" : ""}${nf(Math.abs(v), 1)}`;
export function riskBandText(s, r, line = false) {
  const b = r && r.band;
  if (!b) return null;
  const mk = usOf(s) ? "us" : "kr";
  const L = line ? (b.one ? C.co.risk.one : C.co.risk.band) : (b.one ? C.co.tiles.riskOne : C.co.tiles.riskBand);
  const t = L && L[mk];
  if (!t) return null;
  return b.one ? fill(t, { x: betaText(b.lo) }) : fill(t, { lo: betaText(b.lo), hi: betaText(b.hi) });
}
// The note under the 출렁임 line: a range ("과거 주가로 계산한 범위예요. …") or one number ("… 값이에요. …").
export const riskBandNote = (r) => (r && r.band ? (r.band.one ? C.co.risk.oneNote : C.co.risk.bandNote) || null : null);
