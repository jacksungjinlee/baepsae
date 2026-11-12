// ================= 2.0: US companies whose statements are not in dollars (Jack, 2026-11-12) =================
// data.json fcur (fetch_data.py apply_us_info): the ISO code of Yahoo's financialCurrency for a US-listed company whose
// financial statements are not in dollars (TSMC "TWD", Kaspi.kz "KZT", Ericsson "SEK" ...). Yahoo's PBR and PER for such a
// company can divide the dollar price by a home-currency amount (Kaspi.kz PBR 0.01, Ericsson 0.35, TSMC 78.88 on
// 2026-11-12), so the pipeline blanks every number that may do so: per, pbr, dy (FCUR_FIELDS), and the 가치 score vz built
// from pbr. Every 2.0 reader already treats a blank as missing (never 0, never ranked: engine.cardRaw · percentileScores ·
// screen). This module only says which stocks lost numbers this way and gives the currency's Korean name for the reason
// line "주가는 달러, 재무제표는 {currency} 기준이라 이 숫자는 계산하지 않았어요." (src/copy/v2.js co.fcur; the names are
// co.curName, the one map from ISO code to Korean name). Pure, no React, no Korean. Unit tests: tests/test_us_fcur_app.py.
// A code with no Korean name (not in the map, or its name still waits for Jack): no line at all, never the raw code; the
// numbers stay blank, and the console names the code once.
import { num } from "./engine.js";

export const FCUR_FIELDS = ["per", "pbr", "dy"];
// The 기준 cards that read a blanked number (engine.js CARDS): 가치 (vz, from pbr) and 배당 (US: dy).
export const FCUR_CARDS = ["value", "div"];
const ISO = /^[A-Z]{3}$/;

// The statement currency of a US company whose statements are not in dollars, else null. Korean stocks and funds never
// (their figures do not come from Yahoo; Korean statements not in won are corp.json stmtCur, src/v2/fix.js).
export function fcurOf(s) {
  if (!s || s.cls !== "us") return null;
  const c = s.fcur;
  return typeof c === "string" && ISO.test(c) && c !== "USD" ? c : null;
}

// Does this stock carry one of the blanked numbers anyway? (The pipeline and the gate make sure it does not; a stock that
// did would show it, so the screens never put the reason line next to a number.)
export const fcurLeftover = (s) => !!fcurOf(s) && FCUR_FIELDS.some((k) => num(s[k]) != null);

const warned = new Set();
// The Korean name of an ISO code from names (the copy's co.curName), else null with one console warning per code.
export function curNameOf(code, names) {
  if (typeof code !== "string" || !code) return null;
  const n = names && typeof names === "object" && Object.prototype.hasOwnProperty.call(names, code) ? names[code] : null;
  if (typeof n === "string" && n.trim()) return n;
  if (!warned.has(code)) {
    warned.add(code);
    console.warn(`[v2] statement currency ${code}: no Korean name in src/copy/v2.js co.curName (missing or waiting for approval), `
      + "so the reason line is left out; PER, PBR and the dividend yield stay blank");
  }
  return null;
}

// The reason line for this stock, or null: line = the copy's co.fcur ("…{currency}…"), names = co.curName.
// Never beside a number: a stock that still carries one of FCUR_FIELDS gets no line (and a console warning).
const leftWarned = new Set();
export function fcurText(s, line, names) {
  const code = fcurOf(s);
  if (!code || typeof line !== "string" || !line.includes("{currency}")) return null;
  if (fcurLeftover(s)) {
    if (!leftWarned.has(s.t)) {
      leftWarned.add(s.t);
      console.warn(`[v2] ${s.t}: statements in ${code} but the data still has ${FCUR_FIELDS.filter((k) => num(s[k]) != null).join(", ")}; no reason line`);
    }
    return null;
  }
  const name = curNameOf(code, names);
  return name ? line.split("{currency}").join(name) : null;
}

// A section of 내 기준과 맞는 정도 shows the line when one of its rows is blank because of this (a 가치 or 배당 row, no rank).
// rows: company.cardRanks(...).rows (or the ones on screen).
export const fcurRowsBlank = (s, rows) => !!fcurOf(s) && (rows || []).some((r) => r && FCUR_CARDS.includes(r.id) && r.blank);
