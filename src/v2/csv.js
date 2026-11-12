// ================= 기록 내려받기 (엑셀에서 열려요): one CSV of every record (v19.6a, Part A.5) =================
// Pure, no Korean: the header row and the record kinds come from src/copy/v2.js (csv.head, csv.kinds) as arguments.
// Unit tests: tests/test_v2_records.py.
//
// RFC 4180: fields with a comma, a quote or a line break are quoted and quotes doubled; CRLF line ends; UTF-8 with a BOM
// (Excel then reads Korean). One row per record: 샀어요 (purchases), 팔았어요 (sales), 배당 받았어요 (divs) and v19.3d's
// imported 가진 종목 rows, of every portfolio and of the stocks taken out of it (history). Dates YYYY-MM-DD; numbers plain
// (no thousands separators). Stock codes are written as our own formula cell ="005930" so Excel keeps the leading zeros
// (Numbers and Google Sheets read it the same way). Cells of the user's own text (portfolio and stock names) that start
// with = + - @, a tab or a CR get a leading ' so a spreadsheet never runs them as a formula. 원화 금액 is left blank when
// there is no rate (never computed at another day's rate). Export only: nothing reads this file back.
import { importedUnits, UNIT } from "./held.js";
import { purchaseRate } from "./lots.js";

const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const pos = (x) => isNum(x) && x > 0;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

// One field as RFC 4180 writes it.
export function field(v) {
  const s = v == null ? "" : String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
// The user's own text: never read as a formula.
export function userText(v) {
  const s = v == null ? "" : String(v);
  return /^[=+\-@\t\r]/.test(s) ? "'" + s : s;
}
// A stock code that keeps its leading zeros in a spreadsheet (our own cell: the code is checked to be letters, digits, "." or "-").
export const codeCell = (t) => (typeof t === "string" && /^[0-9A-Za-z][0-9A-Za-z.-]*$/.test(t) ? `="${t}"` : "");
// A number written plainly: no thousands separators, no exponent, at most `d` decimals (trailing zeros dropped).
export function plain(x, d = 4) {
  if (!isNum(x)) return "";
  const s = x.toFixed(d);
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}
const won = (x) => (isNum(x) ? plain(Math.round(x), 0) : "");

// rows: [[cell, ...]] of one portfolio's records, oldest first (an undated imported row first).
function deckRows(d, name, kinds) {
  const out = [];
  const nameOf = (t, fallback) => {
    const h = (d.holdings || []).find((x) => x && x.t === t) || (d.history || []).find((e) => e && e.t === t);
    return (h && h.nk) || fallback || t || "";
  };
  const push = (date, kind, t, nk, qty, price, ccy, rate, wonAmt) => out.push({ date: date || "", cells: [userText(name), kind, date || "", codeCell(t), userText(nk),
    qty, price, ccy || "", rate, wonAmt] });
  const recs = (src, entryName) => {
    for (const r of src.imported || []) {
      if (!r) continue;
      const nk = r.t ? nameOf(r.t, r.nk) : r.nk;
      if (r.amountWon != null) {
        // 금액으로 넣기: the amount in won is the record; its share count is derived (left blank: not a typed number)
        push(DATE.test(r.date || "") ? r.date : "", kinds.imp, r.t, nk, "", pos(r.avg) ? plain(r.avg) : "", r.ccy, r.ccy === "USD" && pos(r.fx) ? plain(r.fx) : "", won(r.amountWon));
      } else {
        const q = importedUnits(r);
        const qty = q != null ? q / UNIT : null;
        const w = pos(r.avg) && qty != null && r.ccy === "KRW" ? qty * r.avg : null;      // a US 평균 단가 has no rate of its own
        push(DATE.test(r.date || "") ? r.date : "", kinds.imp, r.t, nk, plain(qty), pos(r.avg) ? plain(r.avg) : "", r.ccy, "", won(w));
      }
    }
    for (const p of src.purchases || []) {
      if (!p) continue;
      const rate = purchaseRate(p, d.planFx);
      push(p.date, kinds.buy, p.t, nameOf(p.t, entryName), plain(p.qty), plain(p.price, 6), p.ccy, p.ccy === "USD" && rate ? plain(rate) : "",
        won(rate ? p.qty * p.price * rate : null));
    }
    for (const s of src.sales || []) {
      if (!s) continue;
      const rate = s.ccy === "USD" ? (pos(s.fx) ? s.fx : null) : 1;
      push(s.date, kinds.sell, s.t, nameOf(s.t, entryName), plain(s.qty), plain(s.price, 6), s.ccy, s.ccy === "USD" && rate ? plain(rate) : "",
        won(rate ? s.qty * s.price * rate : null));
    }
    for (const x of src.divs || []) {
      if (!x) continue;
      const rate = x.ccy === "USD" ? (pos(x.fx) ? x.fx : null) : 1;
      // a dividend has no quantity: its amount (in the stock's currency, after tax) is in 가격
      push(x.date, kinds.div, x.t, nameOf(x.t, entryName), "", plain(x.amount, 2), x.ccy, x.ccy === "USD" && rate ? plain(rate) : "",
        won(rate ? x.amount * rate : null));
    }
  };
  recs(d, null);
  for (const e of d.history || []) if (e) recs({ imported: e.imported ? [e.imported] : [], purchases: e.purchases, sales: e.sales, divs: e.divs }, e.nk);
  // oldest first; undated (imported) rows first; the order records were added in on a tie
  return out.map((x, i) => ({ ...x, i })).sort((a, b) => (a.date === b.date ? a.i - b.i : a.date < b.date ? -1 : 1)).map((x) => x.cells);
}

// The whole file: BOM + header + one row per record, CRLF line ends.
// data: the store · head: the 10 header words · kinds: { buy, sell, div, imp } · nameOf(deck): the portfolio's shown name.
export function recordsCsv(data, head, kinds, nameOf = (d) => d.name) {
  const lines = [head.map(field).join(",")];
  for (const d of (data && data.decks) || []) {
    if (!d) continue;
    for (const cells of deckRows(d, nameOf(d), kinds)) lines.push(cells.map(field).join(","));
  }
  return "﻿" + lines.join("\r\n") + "\r\n";
}
export const csvName = (prefix, today) => `${prefix}-${today}.csv`;

// Save the file (the same way 기록 내보내기 saves its JSON: a blob link, revoked late for iOS Safari). -> true when started.
export function downloadCsv(text, name) {
  try {
    const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    return true;
  } catch (e) {
    console.warn("[v2] records CSV not saved: " + ((e && e.message) || e));
    return false;
  }
}
