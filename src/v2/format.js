// Number and date formatting for app.html. Every word comes from src/copy/v2.js.
import { C, fill } from "../copy/v2.js";

export { C, fill };

export const nf = (v, d = 0) => Number(v).toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
const MINUS = "−";
export const signed = (s, neg) => (neg ? MINUS : "") + s;

export function mdText(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  return m ? fill(C.app.md, { m: Number(m[2]), d: Number(m[3]) }) : null;
}

// Won amounts: 만원 style; below 1만원 in 원.
export function wonText(won) {
  const a = Math.abs(won);
  if (a >= 10000) return signed(fill(C.app.man, { n: nf(Math.round(a / 10000)) }), won < 0 && Math.round(a / 10000) > 0);
  return signed(fill(C.app.won, { n: nf(Math.round(a)) }), won < 0 && Math.round(a) > 0);
}

export const manText = (man) => fill(C.app.man, { n: nf(man) });

// Percent with one decimal (no sign), e.g. "12.3"
export const p1 = (v) => nf(Math.round(v * 10) / 10, 1);
export const p0 = (v) => nf(Math.round(v));

export function priceText(s) {
  if (s.cls === "us") return "$" + nf(s.price, 2);
  return fill(C.app.won, { n: nf(Math.round(s.price)) });
}

// Today in Korea (YYYY-MM-DD), whatever the device clock's zone.
export function todayKst(now) {
  const d = new Date(now == null ? Date.now() : now);
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(d);
  const g = (t) => parts.find((p) => p.type === t).value;
  return `${g("year")}-${g("month")}-${g("day")}`;
}
