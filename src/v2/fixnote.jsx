// ================= 2.0: the two lines until the DART re-read, as screen pieces (src/repair.js says why) =================
// EpsFixNote: "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요." once per card or section that shows a Korean
// PER, EPS or a number from the same net income, under the numbers. The caller says whether its section shows one
// (fix.js epsFixFor: Korean only, and only while corp.json has no epsBasis "owners").
// IcrOffNote: "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요." where 재무 경고 is shown for a company whose
// 이자보상배율 check is switched off (corp.json flWhy.icr "off"). Both are 13 px (SIZE.xs). No Korean here: C.fix.
import React from "react";
import { COLOR, SIZE, WEIGHT } from "../ui/tokens.js";
import { C, fill, mdText } from "./format.js";
import { Note, tx } from "./ui.jsx";
import { EPS_FIX_DATE, fixNotesHidden } from "./fix.js";

// The line with its date ("11월 10일"), or null when a word or the date is missing (never a line with an empty slot).
export function epsFixText() {
  const md = mdText(EPS_FIX_DATE);
  return C.fix.eps && md ? fill(C.fix.eps, { date: md }) : null;
}

// Never on the example page (fix.js fixNotesHidden), even where a card would show the line in place of its numbers.
export function EpsFixNote({ show, style }) {
  const text = show && !fixNotesHidden() ? epsFixText() : null;
  return text ? <Note data-ui-v2="eps-fix" style={style}>{text}</Note> : null;
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
