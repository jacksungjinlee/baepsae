// ================= DART 다시 읽기 전까지의 두 안내 줄 (Jack, 2026-11-08) =================
// Shared by 뱁새 2.0 (src/v2/fix.js) and the old app (src/fixnote.jsx). Pure: no React, no Korean (the words live in
// src/copy/v2.js for 2.0 and in src/fixnote.jsx for the old app; tests/test_fix_notes.py checks they are the same).
//
// 1. PER · EPS: for many group companies the pipeline divides TOTAL net income (owners + minority interests) by the share
//    count instead of the owners' share (docs/design-chat/2026-11-08-dart-gaps.md §2: LG에너지솔루션 shows EPS 345 / PER
//    977 while owners' net income was a loss). ROE, 지금 가격이 가정하는 것 (reverse DCF), 배당성향 and the old app's
//    주가 분해 use the same net income. A full DART re-read fixes it. Until corp.json says the re-read is live
//    (top-level epsBasis === "owners"), every Korean screen section that shows one of these numbers carries the line
//    "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요." with {date} = EPS_FIX_DATE as month-day ("11월 9일").
//    US stocks never get it (their figures come from SEC / Yahoo, not DART).
// 2. 이자보상배율: switched off in the pipeline for every company until the same re-read (fetch_data.py ICR_OFF, corp.json
//    flWhy.icr "off"). Wherever 재무 경고 is shown for such a company the line "이자보상배율은 계산 방법을 고치는 중이라
//    지금은 확인하지 않아요." says so. It follows flWhy.icr alone: once the pipeline turns the check back on, the field changes
//    and the line goes by itself.

// The date the re-read is planned to go live. THE ONE PLACE TO CHANGE IT (both apps read this constant).
export const EPS_FIX_DATE = "2026-11-09";
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

// The 이자보상배율 check is switched off for this company (corp.json flWhy.icr "off"; financial companies never carry it).
export function icrOff(co) {
  return !!co && typeof co === "object" && !!co.flWhy && typeof co.flWhy === "object" && co.flWhy.icr === "off";
}
