// ================= 2.0: the two lines until the DART re-read, as screen pieces (src/repair.js says why) =================
// EpsFixNote: "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요." once per card or section that shows a Korean
// PER, EPS or a number from the same net income, under the numbers. The caller says whether its section shows one
// (fix.js epsFixFor: Korean only, and only while corp.json has no epsBasis "owners").
// IcrOffNote: "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요." where 재무 경고 is shown for a company whose
// 이자보상배율 check is switched off (corp.json flWhy.icr "off"). Both are 13 px (SIZE.xs). No Korean here: C.fix.
// After the re-read (src/repair.js items 3 and 4):
// EpsOwnersNote: "{date}부터 EPS와 ROE를 지배주주 몫으로 계산해요. 일부 규칙의 결과가 바뀔 수 있어요." once near the top of 홈
// and 포트폴리오, while the corp.json on screen carries epsBasis "owners" and today (KST) is from EPS_FIX_DATE to before EPS_FIX_DATE + 7 days
// (fix.js epsNoticeShown). Never on the example page.
// StmtCurNote: "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직 보여 드리지 않아요." once where a
// Korean company's blanked 실적 · 가치 numbers would be (fix.js stmtCurFor: corp.json stmtCur; never for US stocks).
// Both are the same quiet note as the two lines above (ui.jsx Note, 13 px).
// FcurNote (Jack, 2026-11-12): "주가는 달러, 재무제표는 {currency} 기준이라 이 숫자는 계산하지 않았어요." once where a US
// company's blanked PER · PBR · 배당수익률 would be (src/v2/fcur.js: data.json fcur; {currency} = its Korean name, no line without one).
import React from "react";
import { COLOR, SIZE, WEIGHT } from "../ui/tokens.js";
import { C, fill, mdText, todayKst } from "./format.js";
import { Note, tx } from "./ui.jsx";
import { EPS_FIX_DATE, fixNotesHidden, epsNoticeShown, stmtCurFor, epsLineKind, unitHeldFor, noStmtFor, pxBadFullFor, pxBadPartFor, pxBadHidesFor } from "./fix.js";
import { fcurOf, fcurText, pbrZeroOf, fgnCutOf } from "./fcur.js";

// The line with its date ("11월 10일"), or null when a word or the date is missing (never a line with an empty slot).
export function epsFixText() {
  const md = mdText(EPS_FIX_DATE);
  return C.fix.eps && md ? fill(C.fix.eps, { date: md }) : null;
}

// Never on the example page (fix.js fixNotesHidden), even where a card would show the line in place of its numbers.
// s: the stock of this section (one company). After the marker, a company on total profit with minority shareholders gets
// C.fix.total in the same place (fix.js epsLineKind, Jack 2026-11-08); without s the being-fixed line.
export function EpsFixNote({ show, s, style }) {
  const kind = show && !fixNotesHidden() ? epsLineKind(s) : null;
  const text = kind === "eps" ? epsFixText() : kind === "total" ? C.fix.total || null : null;
  return text ? <Note data-ui-v2={kind === "total" ? "eps-total" : "eps-fix"} style={style}>{text}</Note> : null;
}

export function IcrOffNote({ show, style }) {
  return show && C.fix.icr && !fixNotesHidden() ? <Note data-ui-v2="icr-off" style={style}>{C.fix.icr}</Note> : null;
}

// Inside a button or a tile (phrasing content only): the same line as a block span.
export function IcrOffLine({ show, style }) {
  return show && C.fix.icr && !fixNotesHidden()
    ? <span data-ui-v2="icr-off" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, ...style })}>{C.fix.icr}</span>
    : null;
}

// 공시 단위 확인 (Jack, 2026-11-13): "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요." once per section where a
// Korean company's numbers blanked by the unit check would be (fix.js unitHeldFor: data.json or corp.json unitChk; never for US
// stocks). The same quiet note (ui.jsx Note, 13 px). Shown on the example page too: it is about the data, not a fix.
// -> the line for this company, or null (not held by the unit check, a US stock, or the words not there).
export const unitChkText = (s, co) => (unitHeldFor(s, co) && C.co.unitChk ? C.co.unitChk : null);
// s: the data.json row · co: its corp.json row · show: the section really has a blanked number in it (default true).
export function UnitChkNote({ s, co, show = true, style }) {
  const text = show ? unitChkText(s, co) : null;
  return text ? <Note data-ui-v2="unit-chk" style={style}>{text}</Note> : null;
}

// 과거 주가 기록 오류 (Jack, 2026-11-14): "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요." once per
// screen for a Korean stock whose 52주 range was blanked too (fix.js pxBadFullFor: a bad day within the last 252 bars, data.json or
// corp.json pxBad · pxBadF; never for US stocks): the company page header, in the 52주 bar's place, on every tab. The same quiet note
// (ui.jsx Note, 13 px). Shown on the example page too: it is about the data, not a fix.
// -> the line for this stock, or null (not marked, only some numbers blanked, a US stock, or the words not there).
export const pxBadText = (s, co) => (pxBadFullFor(s, co) && C.co.pxBad ? C.co.pxBad : null);
export function PxBadNote({ s, co, style }) {
  const text = pxBadText(s, co);
  return text ? <Note data-ui-v2="px-bad" style={style}>{text}</Note> : null;
}
// 2026-11-14 evening (Jack): a stock whose bad day is over 252 bars back keeps its 52주 range; each blanked number says
// "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요." in its own place (fix.js pxBadPartFor). field: the data.json field that
// number is (e.g. "beta", "r36", "lz"); the line shows only when that field was blanked. -> the line, or null.
export const pxBadOneText = (s, co, field) => (pxBadPartFor(s, co) && pxBadHidesFor(s, co, field) && C.co.pxBadOne ? C.co.pxBadOne : null);
export function PxBadOneNote({ s, co, field, show = true, style }) {
  const text = show ? pxBadOneText(s, co, field) : null;
  return text ? <Note data-ui-v2="px-bad-one" style={style}>{text}</Note> : null;
}

// The unit-check line inside a rule tile (phrasing content): the reason 재무 경고 0개 could not be checked for a holding the
// unit check holds (pf.js rule "warn" unit · Jack 2026-11-13 Q14: his approved co.unitChk line, the company page's key).
export function UnitChkLine({ show = true, style }) {
  const text = show && C.co.unitChk ? C.co.unitChk : null;
  return text ? <span data-ui-v2="unit-chk-tile" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, ...style })}>{text}</span> : null;
}

// The currency line inside a rule tile (phrasing content), for a code already read (pf.js rule "warn" stmtCur): the
// reason 재무 경고 0개 could not be checked for a holding whose statements are not in won (Jack, 2026-11-08).
export function StmtCurLine({ cur, style }) {
  const text = cur && C.co.stmtCur ? fill(C.co.stmtCur, { currency: cur }) : null;
  return text ? <span data-ui-v2="stmt-cur" data-cur={cur} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, ...style })}>{text}</span> : null;
}

// The week's notice with its date ("11월 10일"), or null when a word or the date is missing.
export function epsOwnersText() {
  const md = mdText(EPS_FIX_DATE);
  return C.fix.owners && md ? fill(C.fix.owners, { date: md }) : null;
}

// load: the load state on screen (its corp.json decides) · now: ms (tests; the screen uses the clock).
export function EpsOwnersNote({ load, now, style }) {
  const text = epsNoticeShown(load, todayKst(now)) ? epsOwnersText() : null;
  return text ? <Note data-ui-v2="eps-owners" style={style}>{text}</Note> : null;
}

// The currency line for this company, or null (no stmtCur, a US stock, or the words not there). Not for a company the unit
// check holds (unitChk): its blanks are explained by the unit line beside it, once (review #118 N7: never both lines).
export function stmtCurText(s, co) {
  if (unitHeldFor(s, co)) return null;
  const cur = stmtCurFor(s, co);
  return cur && C.co.stmtCur ? fill(C.co.stmtCur, { currency: cur }) : null;
}

// No statements at all (fix.js noStmtFor, Jack 2026-11-14): "공시된 재무제표가 아직 없어서 계산할 수 없어요." once where the
// company's 실적 · 가치 · 배당 numbers would be. s: the data.json row · co: its corp.json row.
export function NoStmtNote({ s, co, show = true, style }) {
  const text = show && noStmtFor(s, co) && C.co.noStmt ? C.co.noStmt : null;
  return text ? <Note data-ui-v2="no-stmt" style={style}>{text}</Note> : null;
}

// The reason inside a rule tile (phrasing content) when a held Korean company's checks could not run for lack of input (pf.js
// rule "warn" noData · Jack 2026-11-14: his approved co.warn.noData line).
export function NoDataLine({ show = true, style }) {
  const text = show && C.co.warn && C.co.warn.noData ? C.co.warn.noData : null;
  return text ? <span data-ui-v2="warn-nodata" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, ...style })}>{text}</span> : null;
}

// s: the data.json row · co: its corp.json row. data-cur: the code shown (tests).
export function StmtCurNote({ s, co, style }) {
  const text = stmtCurText(s, co);
  return text ? <Note data-ui-v2="stmt-cur" data-cur={stmtCurFor(s, co)} style={style}>{text}</Note> : null;
}

// The reason line for a US company whose statements are not in dollars (src/v2/fcur.js), or null (no fcur, no name, no words).
export const fcurNoteText = (s) => fcurText(s, C.co.fcur, C.co.curName);

// s: the data.json row. data-cur: the ISO code (tests). Shown on the example page too: it is about the data, not a fix.
export function FcurNote({ s, style }) {
  const text = fcurNoteText(s);
  return text ? <Note data-ui-v2="fcur" data-cur={fcurOf(s)} style={style}>{text}</Note> : null;
}

// PbrZeroNote (Jack, 2026-11-13): "자료상 PBR이 0에 가깝게 나와서 확인하는 동안 비워 두었어요." right under a US stock's PBR "–" when the
// pipeline blanked a PBR that rounds to 0.00 (data.json pbrZero, src/v2/fcur.js pbrZeroOf).
export function PbrZeroNote({ s, style }) {
  return pbrZeroOf(s) && C.co.pbrZero ? <Note data-ui-v2="pbr-zero" style={style}>{C.co.pbrZero}</Note> : null;
}

// FgnCutNote (Jack, 2026-11-14): "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요." right under a US-listed foreign
// company's PER, PBR or 배당수익률 "–" when the pipeline blanked it for not matching the company's totals (data.json fgnCut,
// src/v2/fcur.js fgnCutOf). fields: the blanked numbers this section would show (default all three); the line only when one of
// them is blanked this way. data-fields: the ones it covers (tests).
export function FgnCutNote({ s, fields, style }) {
  const cut = fgnCutOf(s).filter((k) => !fields || fields.includes(k));
  return cut.length && C.co.fgnCut ? <Note data-ui-v2="fgn-cut" data-fields={cut.join(",")} style={style}>{C.co.fgnCut}</Note> : null;
}
