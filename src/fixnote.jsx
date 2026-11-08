// ================= 예전 뱁새: DART 다시 읽기 전까지의 두 안내 줄 (Jack, 2026-11-08) =================
// 왜 · 언제 사라지는지: src/repair.js. 2.0 과 같은 글자예요 (src/copy/v2.js C.fix · tests/test_fix_notes.py 가 같은지 봐요).
// 예전 뱁새는 글을 자기 코드에 두고 2.0 코드(src/v2 · src/copy)를 가져오지 않아서, 두 줄을 여기에 한 번 더 적어요.
//   EpsFixLine  한국 PER · EPS 나 같은 순이익으로 계산한 숫자(ROE · 배당성향 · 주가 분해 · DCF)가 보이는 칸마다 한 줄.
//               corp.json 에 epsBasis "owners" 가 생기면 사라져요. 한국어 화면에서만 (영어 화면의 글은 Jack 의 승인 전이라 없어요).
//   IcrOffLine  이자보상배율이 꺼진 회사(corp.json flWhy.icr "off")의 재무 신호 밑. flWhy.icr 가 바뀌면 사라져요.
// 글자는 12px 이에요 (2.0 의 12px 바닥과 같게).
import React, { useEffect, useState } from "react";
import { C } from "./tokens.js";
import { mdOf, kstDate, loadCorpOnce } from "./data.js";
import { EPS_FIX_DATE, epsBasisLive, icrOff, warnEpsFixLate } from "./repair.js";

export { icrOff };
export const FIX_EPS = "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 fix.eps
export const FIX_ICR = "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 fix.icr
// "11월 9일" (data.js mdOf: 예전 뱁새의 월 · 일 표시). 날짜를 못 만들면 null (빈 자리가 있는 줄은 보이지 않아요)
export function fixEpsText() {
  const md = mdOf(EPS_FIX_DATE, "ko");
  return md ? FIX_EPS.replace("{date}", md) : null;
}

const LINE = { fontSize: 12, color: C.sub, lineHeight: 1.6, marginTop: 8, wordBreak: "keep-all", overflowWrap: "break-word" };

// 기업분석 · 첫 화면 성적표: 화면이 읽은 corp.json 으로 정해요 (그 파일에 표시가 없으면 줄이 있어요).
export function EpsFixLine({ corp, show = true, style }) {
  const on = show && !epsBasisLive(corp);
  useEffect(() => { if (on) warnEpsFixLate(corp, kstDate(Date.now()), "뱁새"); }, [on, corp]);
  const text = on ? fixEpsText() : null;
  return text ? <div data-fix="eps" style={{ ...LINE, ...style }}>{text}</div> : null;
}

// 포트폴리오(data.json 으로 그려요): corp.json 을 한 번 받아(data.js loadCorpOnce, 다른 칸과 같이 써요) 표시를 봐요.
// 받는 중이거나 받지 못하면 줄이 있어요 (고쳐졌다고 짐작하지 않아요).
let CORP_LIVE = null;
export function useEpsBasisLive(want) {
  const [live, setLive] = useState(CORP_LIVE);
  useEffect(() => {
    if (!want || CORP_LIVE !== null) return undefined;
    let alive = true;
    loadCorpOnce().then((d) => {
      if (d && !d.failed) {
        CORP_LIVE = epsBasisLive(d);
        warnEpsFixLate(d, kstDate(Date.now()), "뱁새");
      }
      if (alive) setLive(d && !d.failed ? CORP_LIVE : null);
    });
    return () => { alive = false; };
  }, [want]);
  return live;
}
export function EpsFixLineLoaded({ show = true, style }) {
  const live = useEpsBasisLive(show);
  const text = show && live !== true ? fixEpsText() : null;
  return text ? <div data-fix="eps" style={{ ...LINE, ...style }}>{text}</div> : null;
}

// co: corp.json 의 그 회사 줄.
export function IcrOffLine({ co, show = true, style }) {
  return show && icrOff(co) ? <div data-fix="icr" style={{ ...LINE, ...style }}>{FIX_ICR}</div> : null;
}
