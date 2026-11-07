// Small formatting helpers shared by the company page (company.jsx) and its tabs (cotabs.jsx). No Korean here: words
// come from src/copy/v2.js. US per-share figures are $ first with 원 small (Jack's decision 7, v19.1).
import { C, fill, nf, p1, mdText, wonText } from "./format.js";
import { eokText, signedPct } from "./deckcalc.js";

export const usOf = (s) => !!s && s.cls === "us";
// The price date of this stock's market: KR pxDate, US usPxDate (never the Korean date for a US price: none then).
export const priceDate = (load, s) => (usOf(s) ? load.data.usPxDate || null : load.data.pxDate || null);
export const priceMd = (load, s) => mdText(priceDate(load, s));
// v19.3e (v19.3 Part I, board CoSummaryUS): the US header reads "{date} 종가 (미국 시간)" beside the $ price and
// "약 {won} · 환율 {fx}원" under it (one line instead of the 원 line and the rate sentence). Off until Jack says yes to the
// smoke-test edit it needs (tests/smoke_v2.py pins today's US date line "미국 {md} 종가" and "약 {n}원"): off, the header is
// exactly as before. The v19.3e smoke scenes build it on (tests/smoke_v2.py v193e_on_app).
export const US_HEAD2 = false;
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
