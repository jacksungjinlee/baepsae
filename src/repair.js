// ================= DART 다시 읽기 전까지의 두 안내 줄 (Jack, 2026-11-08) =================
// Shared by 뱁새 2.0 (src/v2/fix.js) and the old app (src/fixnote.jsx). Pure: no React, no Korean (the words live in
// src/copy/v2.js for 2.0 and in src/fixnote.jsx for the old app; tests/test_fix_notes.py and tests/test_reread_lines.py
// check they are the same). Items 3 and 4 (the week's notice, statements not in won) are at the end of this file.
//
// 1. PER · EPS: for many group companies the pipeline divides TOTAL net income (owners + minority interests) by the share
//    count instead of the owners' share (docs/design-chat/2026-11-08-dart-gaps.md §2: LG에너지솔루션 shows EPS 345 / PER
//    977 while owners' net income was a loss). ROE, 지금 가격이 가정하는 것 (reverse DCF), 배당성향 and the old app's
//    주가 분해 use the same net income. A full DART re-read fixes it. Until corp.json says the re-read is live
//    (top-level epsBasis === "owners"), every Korean screen section that shows one of these numbers carries the line
//    "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요." with {date} = EPS_FIX_DATE as month-day ("11월 10일").
//    After the re-read the line goes per company (epsFixNeeded: only companies whose epsIn.b is "o" or "s" lose it).
//    US stocks never get it (their figures come from SEC / Yahoo, not DART).
// 2. 이자보상배율: switched off in the pipeline for every company until the same re-read (fetch_data.py ICR_OFF, corp.json
//    flWhy.icr "off"). Wherever 재무 경고 is shown for such a company the line "이자보상배율은 계산 방법을 고치는 중이라
//    지금은 확인하지 않아요." says so. It follows flWhy.icr alone: once the pipeline turns the check back on, the field changes
//    and the line goes by itself.

// The date the re-read is planned to go live. THE ONE PLACE TO CHANGE IT (both apps read this constant).
export const EPS_FIX_DATE = "2026-11-10";
// corp.json's top-level marker the re-read writes (the pipeline builder uses the same name).
export const EPS_BASIS_OWNERS = "owners";

// true once corp.json carries the re-read marker: no PER/EPS line anywhere then. Anything else (no file, a file that
// failed to load, a missing or different value) keeps the line: a fix is never assumed.
export function epsBasisLive(corp) {
  return !!corp && typeof corp === "object" && !Array.isArray(corp) && corp.epsBasis === EPS_BASIS_OWNERS;
}

// The planned date has passed (today in KST, YYYY-MM-DD, is after EPS_FIX_DATE) and the marker is still missing: the line
// stays, and the apps warn in the console so the date gets updated (never silent).
export function epsFixLate(corp, todayIso, date = EPS_FIX_DATE) {
  return !epsBasisLive(corp) && typeof todayIso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(todayIso) && todayIso > date;
}

const warned = new Set();
// Warns once per page and place. -> true when it warned (tests).
export function warnEpsFixLate(corp, todayIso, where, date = EPS_FIX_DATE) {
  if (!epsFixLate(corp, todayIso, date) || warned.has(where)) return false;
  warned.add(where);
  console.warn(`[${where}] !! The PER/EPS line still says the DART re-read goes live on ${date}, but today (KST) is ${todayIso} `
    + `and corp.json has no epsBasis "${EPS_BASIS_OWNERS}". The line stays on every Korean PER/EPS: update EPS_FIX_DATE in src/repair.js.`);
  return true;
}

// Per company (2026-11-08, coordinator relaying the data review): the re-read writes receipts corp.json epsIn { ni, b, p, sh }
// per company, b = "o" (owners' profit) · "s" (separate statements: no minority interest) · "t" (total profit on a
// consolidated statement with no owners' line). A company is fixed only when the top-level marker is there AND its
// epsIn.b is "o" or "s"; companies still on total profit ("t", or no epsIn) keep the line after the re-read too.
export const EPS_IN_FIXED = ["o", "s"];
export function epsInFixed(co) {
  return !!co && typeof co === "object" && !!co.epsIn && typeof co.epsIn === "object" && EPS_IN_FIXED.includes(co.epsIn.b);
}
// corp: corp.json · co: that company's row in it. true = the PER/EPS line shows for this company.
// Never for a company whose statements are not in won (stmtNotWon, item 4 below; readable code or not): the re-read blanks its
// EPS and the rest, it has no epsIn, and the currency line says why; the line would otherwise stay forever with a past date.
// Once the marker is live (Jack, 2026-11-08) a company the re-read left on total profit ("t") no longer gets the being-fixed
// line: one with no owners' line but minority shareholders (epsIn.b "t", how "total", nci true: fetch_data.py eps_nci) gets
// "이 회사는 지배주주 몫 순이익을 따로 공시하지 않아, PER과 EPS를 회사 전체 순이익으로 계산했어요." in the same single-company
// places instead (epsTotalNeeded); other "t" companies (no minority shareholders, or how "hybrid") and foreign issuers
// (900xxx · 950xxx, statements in a foreign currency) show neither line. Companies with no epsIn, an unknown b or a malformed
// epsIn keep the line as before. Before the marker nothing changes.
export const isForeignIssuer = (t) => typeof t === "string" && t.length === 6 && t[0] === "9";
export function epsInTotal(co) {
  return !!co && typeof co === "object" && !!co.epsIn && typeof co.epsIn === "object" && co.epsIn.b === "t";
}
// After the marker: neither line's place, except through epsTotalNeeded ("t" or a foreign issuer).
export const epsTotalSide = (co) => epsInTotal(co) || (!!co && typeof co === "object" && isForeignIssuer(co.t));
export function epsFixNeeded(corp, co) {
  return !stmtNotWon(co) && !unitHeld(co) && !(epsBasisLive(corp) && (epsInFixed(co) || epsTotalSide(co)));
}
// epsIn.b "t" from a statement with no owners' line (how "total") and with minority shareholders (nci true).
export function epsTotalNci(co) {
  return epsInTotal(co) && co.epsIn.how === "total" && co.epsIn.nci === true;
}
// true = the total-profit line shows for this company (corp: corp.json on screen · co: its row).
export function epsTotalNeeded(corp, co) {
  return epsBasisLive(corp) && !stmtNotWon(co) && !unitHeld(co) && epsTotalNci(co);
}

// The net income (억원) and share count (백만주) on which this company's EPS stands, for the report year fy − i (corp.json
// ni / nio3 are [fy, fy−1, fy−2]): i = 2 is 주가는 무엇으로 움직였나's 'then' end, i = 0 the reverse DCF's start profit.
// Both ends of a calculation must share one basis with the EPS shown (corp.json eps):
//   no epsIn (files before the re-read): eps = total net income ÷ common shares, so ni[i] ÷ shm, exactly as before
//   epsIn.b "o": owners' net income nio3[i] ÷ epsIn.sh (common + listed preferred shares, a count)
//   epsIn.b "s": ni[i] ÷ epsIn.sh (separate statements: total and owners' profit are the same)
//   신종자본증권 (v19.1f review 3): when the annual reports have owners' hybrid-capital payouts, the re-read writes nio3 as
//   the owners' profit after them, with the payouts as the receipt nio3Hyb [fy, fy−1, fy−2]. "o" already reads nio3; "s"
//   reads nio3 too when that receipt is there (ni is before the payouts: a mixed basis), and a year nio3 lacks is then
//   missing (never ni). The receipt decides, not epsIn.hyb (that one can come from the latest four quarters alone, when
//   the pipeline writes no hybrid-net nio3: a leftover nio3 there is not on EPS's basis, e.g. 예림당 ni[2] 181.2 vs nio3[2]
//   90.1). Fresh-eyes review of the re-read lines, 2026-11-08.
//   A year missing on that basis (ni null) is just missing data: the cards say what they always say (자료가 없어요 · no
//   card), as for a file before the re-read (review of PR #89: 13 companies with a 3-year return miss ni[2] today).
//   epsIn.b "t", any other value, or no share count: { bad: true } — the card shows no numbers, only the PER/EPS line
//   (never a mixed basis, never a guess).
// -> { basis: "today" | "o" | "s", ni, sharesM } (ni null = that year is missing) | { bad: true } | null
const finite = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
// The yearly profit series EPS stands on, after the re-read: "o", or "s" with the hybrid receipt nio3Hyb -> nio3; "s" -> ni.
// e: corp.json epsIn (b "o" or "s"). Shared by epsBase and 2.0's 배당성향 (company.js payout).
export function epsNiSeries(co, e) {
  return e.b === "o" || (e.b === "s" && Array.isArray(co.nio3Hyb)) ? co.nio3 : co.ni;
}
export function epsBase(co, i) {
  if (!co || typeof co !== "object") return null;
  const at = (arr) => (Array.isArray(arr) ? finite(arr[i]) : null);
  const e = co.epsIn;
  if (e == null) return { basis: "today", ni: at(co.ni), sharesM: finite(co.shm) };
  if (typeof e !== "object" || !(finite(e.sh) > 0) || !EPS_IN_FIXED.includes(e.b)) return { bad: true };
  return { basis: e.b, ni: at(epsNiSeries(co, e)), sharesM: e.sh / 1e6 };
}

// The period behind a per-share figure, for its label ("최근 4개 분기" or "사업보고서"). in: corp.json epsIn or bpsIn. When
// the re-read wrote one with p, p decides ("fy" = the 사업보고서; "ttm" = the latest four quarters to this company's bq, which
// is what the DART re-read writes for epsIn and bpsIn; "YYYY.QQ" = the latest four quarters to that quarter);
// otherwise corp.json bq (the TTM quarter, as before) or the 사업보고서. -> { fy: true } | { y, q } | null (a p that
// cannot be read, or "ttm" without a readable bq: no label rather than a wrong one).
const Q_RX = /^(\d{4})\.([1-4])Q$/;
function periodOf(p, bq) {
  if (p === "fy") return { fy: true };
  const q = p === "ttm" ? bq : p;
  const m = typeof q === "string" ? Q_RX.exec(q) : null;
  return m ? { y: Number(m[1]), q: Number(m[2]) } : null;
}
export function periodFrom(co, key) {
  if (!co || typeof co !== "object") return null;
  const r = co[key];
  if (r && typeof r === "object" && r.p != null) return periodOf(r.p, co.bq);
  const m = typeof co.bq === "string" ? Q_RX.exec(co.bq) : null;
  return m ? { y: Number(m[1]), q: Number(m[2]) } : { fy: true };
}
export const epsPeriod = (co) => periodFrom(co, "epsIn");
export const bpsPeriod = (co) => periodFrom(co, "bpsIn");

// The 이자보상배율 check is switched off for this company (corp.json flWhy.icr "off"; financial companies never carry it).
// Not for a company whose statements are not in won (stmtNotWon): no signal is computed for it at all, and the currency line
// says why.
export function icrOff(co) {
  return !!co && typeof co === "object" && !!co.flWhy && typeof co.flWhy === "object" && co.flWhy.icr === "off" && !stmtNotWon(co) && !unitHeld(co);
}

// ================= After the re-read: the week's notice and statements not in won (Jack, 2026-11-08) =================
// 3. For a week from the re-read, 2.0's 홈 and 포트폴리오 carry one notice "{date}부터 EPS와 ROE를 지배주주 몫으로 계산해요.
//    일부 규칙의 결과가 바뀔 수 있어요." ({date} = EPS_FIX_DATE as month-day): only while the corp.json on screen carries
//    epsBasis "owners" AND today (KST, YYYY-MM-DD) is from EPS_FIX_DATE to before EPS_FIX_DATE + EPS_NOTICE_DAYS. Before the
//    marker there is nothing to announce (the per-company line above says it); before the date it names it would read
//    wrong ("11월 10일부터" on the 9th), and from EPS_FIX_DATE + 7 days it goes by itself.
// 4. The re-read blanks the statement amounts (매출 · 영업이익 · 순이익 · 자본, PER · PBR · EPS · BPS and their receipts) of a
//    Korean company whose DART statements are not in won, and writes that currency in corp.json stmtCur ("USD"; absent
//    otherwise; validate_data.py lets through only a three-letter code other than KRW). Where those numbers would be, both
//    apps say "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직 보여 드리지 않아요." with the code as written.
export const EPS_NOTICE_DAYS = 7;
const ISO_RX = /^(\d{4})-(\d{2})-(\d{2})$/;
// "YYYY-MM-DD" + n calendar days -> "YYYY-MM-DD" (a date, not a time: no time zone involved). null for a date that does
// not exist ("2026-02-30") or anything else.
export function isoPlusDays(iso, n) {
  const m = typeof iso === "string" ? ISO_RX.exec(iso) : null;
  if (!m || !Number.isInteger(n)) return null;
  const y = Number(m[1]), mo = Number(m[2]) - 1, d = Number(m[3]);
  const at = new Date(Date.UTC(y, mo, d));
  if (at.getUTCFullYear() !== y || at.getUTCMonth() !== mo || at.getUTCDate() !== d) return null;
  return new Date(Date.UTC(y, mo, d + n)).toISOString().slice(0, 10);
}
// corp: the corp.json on screen · todayIso: today in KST. true = the week's notice shows.
export function epsNoticeOn(corp, todayIso, date = EPS_FIX_DATE) {
  const end = isoPlusDays(date, EPS_NOTICE_DAYS);
  return epsBasisLive(corp) && !!end && typeof todayIso === "string" && ISO_RX.test(todayIso) && todayIso >= date && todayIso < end;
}

// The currency of this company's statements when it is not won (corp.json stmtCur), exactly as written: "USD". null when
// the field is absent, or holds anything but a three-letter upper-case code other than KRW and XXX (no line with an odd
// slot; warnStmtCur says so in the console).
// "XXX" (ISO 4217 'no currency') is what the pipeline writes for a currency name it cannot read (fetch_data.py
// norm_currency): unreadable here too, never "원화가 아닌 XXX로".
const CUR_RX = /^[A-Z]{3}$/;
const CUR_NOT = ["KRW", "XXX"];
export function stmtCurOf(co) {
  const c = co && typeof co === "object" ? co.stmtCur : null;
  return typeof c === "string" && CUR_RX.test(c) && !CUR_NOT.includes(c) ? c : null;
}
// The statements are not in won: corp.json stmtCur is there and is not "KRW", readable or not ("XXX" too). This decides
// everything hidden for such a company (empty parts, untrue reasons, the two being-fixed lines); stmtCurOf only decides
// whether the currency line can be printed (fresh-eyes review, 2026-11-08: an unreadable code must not switch the hiding off).
export function stmtNotWon(co) {
  return !!co && typeof co === "object" && co.stmtCur != null && co.stmtCur !== "KRW";
}
const warnedCur = new Set();
// A stmtCur that cannot be shown: warns once per page, place and company. -> true when it warned (tests).
export function warnStmtCur(co, where) {
  if (!co || typeof co !== "object" || co.stmtCur == null || stmtCurOf(co)) return false;
  const k = where + "|" + co.t;
  if (warnedCur.has(k)) return false;
  warnedCur.add(k);
  console.warn(`[${where}] !! ${co.t}: corp.json stmtCur ${JSON.stringify(co.stmtCur)} is not a currency code the line can show (three `
    + "capital letters, not KRW, not XXX = unreadable): no currency line, so its blank statement amounts show with no reason on screen.");
  return true;
}

// ================= 5. 공시 단위 확인 (Jack, 2026-11-13) =================
// Some filings are read in the wrong unit: the 2026 반기보고서 of 진코스텍 and 디와이에이 head their statements "(단위 : 천원)" over
// numbers that are in 원, so DART holds every amount 1,000 times too large (PER and PBR came out 0.0). The pipeline
// (fetch_data.py unit_guard) checks every Korean company on every run and, for one that fails, blanks every number built on its
// statements (PER · PBR · EPS · BPS · ROE · 부채비율 · 영업이익률 · 매출 증가율 · the 3-year amounts · equity · EV multiples · receipts ·
// 재무 경고, and the 가치 · 퀄리티 scores) and marks it with unitChk, a list of reasons ("bs" assets ≠ liabilities + equity ·
// "scale" a quarterly report's balance sheet 100 times or more off the 사업보고서 · "is" / "cf" its previous-period income or
// cash-flow column 100 times or more off last year's same-quarter report · "eps" profit ÷ shares 300 times or more off the report's
// own 기본주당이익 · "cap" 자본금 ÷ 액면가 300 times or more off the share count; eps and cap only for statements in won), in
// data.json and corp.json. Dividends stay (a separate table). Such a company shows the unit line, never the currency line too
// (review #118 N7: a company with both stmtCur and unitChk).
// Where those numbers would be, both apps say "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요." once per section
// (2.0: src/copy/v2.js co.unitChk; the old app: src/fixnote.jsx FIX_UNIT). Such a company never gets the being-fixed, total-profit
// or 이자보상배율 lines above: the numbers they would explain are not shown. row: a data.json stock or a corp.json company.
export function unitHeld(row) {
  return !!row && typeof row === "object" && Array.isArray(row.unitChk) && row.unitChk.length > 0;
}
