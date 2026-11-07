// Number and date formatting for app.html. Every word comes from src/copy/v2.js.
import { C, fill } from "../copy/v2.js";
import { staleWordsLate } from "../data.js";

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

// v19.1c (Jack, 2026-11-07, design chat): wherever a list or a total includes a US stock priced at an earlier close
// (data.json pxd), one short note names it: "AAPL, TSLA 가격은 11월 5일 종가예요. NVDA 가격은 11월 4일 종가예요." — one
// sentence per date, newest first, joined with a space; names = the tickers, all of them, ", ". groups: data.js
// ownCloseGroups (stocklist.js). null when there is nothing to say (or a date cannot be written: never a sentence without it).
export function ownCloseText(groups) {
  const out = [];
  for (const g of groups || []) {
    const md = mdText(g && g.date);
    if (!md || !g.ts || !g.ts.length) return null;
    out.push(fill(C.app.ownClose, { names: g.ts.join(", "), md }));
  }
  return out.length ? out.join(" ") : null;
}

// The stale part of a date line (Jack, 2026-11-07): n <= 1 (the due day: n counts from the morning the publish was due, data.js
// freshness) "갱신이 늦어지고 있어요", from n = 2 "{n}일째 갱신이 멈췄어요" as before. data.js staleWordsLate.
export const staleText = (n) => (staleWordsLate(n) ? C.app.staleLate : fill(C.app.stale, { n }));
// The same rule for the 홈 band (and 포트폴리오's line): n <= 1 "데이터 갱신이 늦어지고 있어 오늘은 점검하지 않았어요."
// (today.staleLate, Jack 2026-11-07), from n = 2 "데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요" (today.stale).
export const todayStaleText = (n) => (staleWordsLate(n) ? C.today.staleLate : fill(C.today.stale, { n }));

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
