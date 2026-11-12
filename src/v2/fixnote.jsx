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
import { EPS_FIX_DATE, fixNotesHidden, epsNoticeShown, stmtCurFor, epsLineKind } from "./fix.js";
import { fcurOf, fcurText } from "./fcur.js";

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

// The currency line for this company, or null (no stmtCur, a US stock, or the words not there).
export function stmtCurText(s, co) {
  const cur = stmtCurFor(s, co);
  return cur && C.co.stmtCur ? fill(C.co.stmtCur, { currency: cur }) : null;
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
