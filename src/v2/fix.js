// ================= 2.0: the two lines until the DART re-read (src/repair.js says why) =================
// The PER/EPS line depends on corp.json: its top-level epsBasis and, per company, epsIn.b (repair.js epsFixNeeded). The
// whole app reads that one way: load.js resolveLoad calls setEpsBasis(corp) once per load (the way engine.setDataShape
// works), so a screen that only has a held stock (daily.jsx) knows it too. Until a file is loaded the line is on (a fix is
// never assumed). Pure; no Korean (src/copy/v2.js C.fix).
import { EPS_FIX_DATE, epsBasisLive, epsInFixed, epsTotalNci, epsTotalSide, isForeignIssuer, icrOff, warnEpsFixLate, epsNoticeOn, stmtCurOf, stmtNotWon, warnStmtCur, unitHeld, pxBad } from "../repair.js";
import { kstDate } from "../data.js";

export { EPS_FIX_DATE, icrOff };

let live = false;
let fixed = new Set();        // codes whose epsIn.b is "o" or "s" (only read when live)
let notWon = new Set();       // codes whose statements are not in won (repair.js stmtNotWon): never the PER/EPS line
let units = new Set();        // codes whose numbers are blanked by the unit check (repair.js unitHeld, corp.json unitChk): never the PER/EPS line
let total = new Set();        // codes on total profit with minority shareholders (epsIn.b "t" · how total · nci true; only read when live)
let side = new Set();         // codes on total profit ("t") of any kind (only read when live; foreign issuers by their code)
let hidden = false;           // the example page (app-preview.html, fictional data): neither line (PR #89 review)
// corp: the loaded corp.json (null when it failed). now: ms (tests). preview: the example page (no lines, no warning).
export function setEpsBasis(corp, { now, preview = false } = {}) {
  hidden = !!preview;
  live = epsBasisLive(corp);
  fixed = new Set(live && Array.isArray(corp.companies) ? corp.companies.filter(epsInFixed).map((c) => c.t) : []);
  notWon = new Set(corp && Array.isArray(corp.companies) ? corp.companies.filter(stmtNotWon).map((c) => c.t) : []);
  units = new Set(corp && Array.isArray(corp.companies) ? corp.companies.filter(unitHeld).map((c) => c.t) : []);
  total = new Set(live && Array.isArray(corp.companies) ? corp.companies.filter(epsTotalNci).map((c) => c.t) : []);
  side = new Set(live && Array.isArray(corp.companies) ? corp.companies.filter(epsTotalSide).map((c) => c.t) : []);
  if (!preview && corp) warnEpsFixLate(corp, kstDate(now == null ? Date.now() : now), "v2");
  return live;
}
export const epsBasisIsLive = () => live;
export const fixNotesHidden = () => hidden;
// The 이자보상배율 line for this corp.json row (repair.js icrOff), never on the example page.
export const icrOffShown = (co) => !hidden && icrOff(co);

// The PER/EPS line for a section showing one Korean stock's PER, EPS or a number from the same net income (ROE, the reverse
// DCF, 배당성향, 주가는 무엇으로 움직였나). s: the data.json row (or anything with t and cls). US and funds: never. After the
// re-read: only for companies still on total profit (epsIn.b "t" or no epsIn). Never for a company whose statements are not
// in won (stmtCur): its numbers are blanked and the currency line says why (repair.js epsFixNeeded, the old app's rule).
// After the re-read (Jack, 2026-11-08; repair.js epsFixNeeded): companies on total profit ("t") and foreign issuers lose the
// being-fixed line; those with no owners' line and minority shareholders (repair.js epsTotalNeeded) get the total-profit line in
// the same places instead. So this stays the one question each section asks ("does this stock get a line here?"), and
// epsLineKind(s) says which line.
const tSide = (t) => side.has(t) || isForeignIssuer(t);
export const epsFixFor = (s) => !hidden && !!s && s.cls === "kr" && !notWon.has(s.t) && !units.has(s.t) && !unitHeld(s)
  && !(live && (fixed.has(s.t) || (tSide(s.t) && !total.has(s.t))));
// "eps" (the being-fixed line) | "total" (after the marker, for that company) — which words EpsFixNote shows.
export const epsLineKind = (s) => (live && !!s && total.has(s.t) ? "total" : "eps");
// A card whose numbers are left out for lack of one basis (repair.js epsBase bad): after the marker, a "t" company without
// the total-profit line (or a foreign issuer) has no line to put in their place, so the card is left out (not a bare title).
export const epsBasisCardGone = (s) => live && !!s && tSide(s.t) && !total.has(s.t);
// Same, for a section where several stocks show such numbers (any one that needs it is enough).
export const epsFixForAny = (rows) => Array.isArray(rows) && rows.some(epsFixFor);

// 공시 단위 확인 (Jack, 2026-11-13; repair.js unitHeld): a Korean stock whose statement numbers the pipeline blanked (data.json or
// corp.json unitChk). Decides where the line "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요." goes and which parts
// with no numbers are left out. s: the data.json row · co: its corp.json row (either may be missing). US stocks and funds: never.
export const unitHeldFor = (s, co) => !!s && s.cls === "kr" && (unitHeld(s) || unitHeld(co));
// The 기준 cards whose numbers the unit check blanks (engine.js CARDS: 가치 vz · 수익성 roe · 안정성 debt · 성장 g3).
export const UNIT_CARDS = ["value", "profit", "stable", "growth"];
// A section of 내 기준과 맞는 정도 shows the line when one of its rows is blank because of this. rows: company.cardRanks(...).rows.
export const unitRowsBlank = (s, co, rows) => unitHeldFor(s, co) && (rows || []).some((r) => r && UNIT_CARDS.includes(r.id) && r.blank);

// 과거 주가 기록 오류 (Jack, 2026-11-14; repair.js pxBad): a Korean stock whose price-history numbers the pipeline blanked
// (data.json or corp.json pxBad: 52주 최고 · 최저, 변동성, 베타, 수익률, 낙폭 and the 추세 · 저변동 scores). Decides where the line
// "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요." goes (once per screen: the company page header,
// where the 52주 bar would be) and which parts with no numbers are left out or held at "–" (the 출렁임 tile and card, 주가는
// 무엇으로 움직였나). s: the data.json row · co: its corp.json row (either may be missing). US stocks and funds: never.
export const pxBadFor = (s, co) => !!s && s.cls === "kr" && (pxBad(s) || pxBad(co));

// The week's notice on 홈 and 포트폴리오 (repair.js epsNoticeOn): read from the load on screen (its corp.json), never on the
// example page. load: the load state · todayIso: today in KST.
export const epsNoticeShown = (load, todayIso) => !hidden && !!load && load.status === "ok" && !load.preview && epsNoticeOn(load.corp, todayIso);

// Statements not in won (repair.js stmtCurOf): the currency code for a Korean stock whose corp.json row carries stmtCur,
// else null (US stocks and funds never: their figures do not come from DART). s: the data.json row · co: its corp.json row.
// Statements not in won at all (repair.js stmtNotWon, readable code or not): what decides the hiding on the company page.
export const stmtNotWonFor = (s, co) => !!s && s.cls === "kr" && stmtNotWon(co);
export function stmtCurFor(s, co) {
  if (!s || s.cls !== "kr" || !co) return null;
  warnStmtCur(co, "v2");
  return stmtCurOf(co);
}
