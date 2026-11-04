// Small formatting helpers shared by the company page (company.jsx) and its tabs (cotabs.jsx). No Korean here: words
// come from src/copy/v2.js. US per-share figures are $ first with 원 small (Jack's decision 7, v19.1).
import { C, fill, nf, p1, mdText, wonText } from "./format.js";
import { eokText } from "./deckcalc.js";

export const usOf = (s) => !!s && s.cls === "us";
// The price date of this stock's market: KR pxDate, US usPxDate (never the Korean date for a US price: none then).
export const priceDate = (load, s) => (usOf(s) ? load.data.usPxDate || null : load.data.pxDate || null);
export const priceMd = (load, s) => mdText(priceDate(load, s));
// The date beside a price: KR "11월 3일 종가" (why.close), US "미국 11월 3일 종가" (pending; before: the approved sentence).
export function closeLine(load, s) {
  const md = priceMd(load, s);
  if (!md) return null;
  if (!usOf(s)) return fill(C.why.close, { md });
  return C.co.usClose ? fill(C.co.usClose, { md }) : fill(C.app.usClose, { md });
}
// "약 445,900원" under a $ price, at today's rate (data.json fx), rounded to 100원.
export function wonOfUsd(load, usd) {
  const fx = load.data.fx;
  if (!(typeof fx === "number" && fx > 0) || !(typeof usd === "number" && Number.isFinite(usd))) return null;
  return fill(C.app.about, { x: fill(C.app.won, { n: nf(Math.round((usd * fx) / 100) * 100) }) });
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
