// ================= 예전 뱁새: DART 다시 읽기 전까지의 두 안내 줄 (Jack, 2026-11-08) =================
// 왜 · 언제 사라지는지: src/repair.js. 2.0 과 같은 글자예요 (src/copy/v2.js C.fix · tests/test_fix_notes.py 가 같은지 봐요).
// 예전 뱁새는 글을 자기 코드에 두고 2.0 코드(src/v2 · src/copy)를 가져오지 않아서, 두 줄을 여기에 한 번 더 적어요.
//   EpsFixLine  한국 PER · EPS 나 같은 순이익으로 계산한 숫자(ROE · 배당성향 · 주가 분해 · DCF)가 보이는 칸마다 한 줄.
//               corp.json 에 epsBasis "owners" 가 생기고 그 회사의 epsIn.b 가 "o" · "s" 이면 사라져요 (repair.js epsFixNeeded: 다시 읽은
//               뒤에도 총 순이익("t")인 회사는 남아요).
//   IcrOffLine  이자보상배율이 꺼진 회사(corp.json flWhy.icr "off")의 재무 신호 밑. flWhy.icr 가 바뀌면 사라져요.
//   영어 화면 (Jack 승인 2026-11-08, DeepL 확인): 한국어 줄이 보이는 자리와 같은 규칙으로 FIX_EPS_EN · FIX_ICR_EN (lang "en").
//               날짜는 예전 뱁새의 영어 월 · 일 (data.js mdOf "en": "Nov 10"). 기업분석(src/corp.jsx)은 영어 화면에서도 한국어로만
//               보이는 칸이라 lang 을 넘기지 않아요 (한국어 줄 그대로). 영어 줄은 첫 화면 성적표와 포트폴리오(src/detail.jsx)에서.
//   StmtCurLine 재무제표를 원화가 아닌 통화로 공시한 한국 회사(corp.json stmtCur, repair.js stmtCurOf): 기업분석 투자지표 칸에 한 번.
// 글자는 12px 이에요 (2.0 의 12px 바닥과 같게).
import React, { useEffect, useState } from "react";
import { C } from "./tokens.js";
import { mdOf, kstDate, loadCorpOnce } from "./data.js";
import { EPS_FIX_DATE, epsBasisLive, epsFixNeeded, epsInFixed, icrOff, warnEpsFixLate, stmtCurOf, warnStmtCur } from "./repair.js";

export { icrOff };
export const FIX_EPS = "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 fix.eps
export const FIX_ICR = "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 fix.icr
export const FIX_EPS_EN = "PER and EPS are being recalculated and may change on {date}.";       // Jack 승인 2026-11-08 (DeepL 확인) — 영어 화면
export const FIX_ICR_EN = "Interest coverage isn't checked while we fix how it's calculated.";   // Jack 승인 2026-11-08 (DeepL 확인) — 영어 화면
export const FIX_STMT_CUR = "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직 보여 드리지 않아요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 co.stmtCur
// "11월 10일" · 영어 화면 "Nov 10" (data.js mdOf: 예전 뱁새의 월 · 일 표시). 날짜를 못 만들면 null (빈 자리가 있는 줄은 보이지 않아요)
export function fixEpsText(lang = "ko") {
  const en = lang === "en";
  const md = mdOf(EPS_FIX_DATE, en ? "en" : "ko");
  return md ? (en ? FIX_EPS_EN : FIX_EPS).replace("{date}", md) : null;
}
export const fixIcrText = (lang = "ko") => (lang === "en" ? FIX_ICR_EN : FIX_ICR);

const LINE = { fontSize: 12, color: C.sub, lineHeight: 1.6, marginTop: 8, wordBreak: "keep-all", overflowWrap: "break-word" };

// 기업분석 · 첫 화면 성적표: 화면이 읽은 corp.json 과 그 칸에 숫자가 보이는 회사들(cos, corp.json 의 줄)로 정해요 — 그중 하나라도
// 고쳐지지 않았으면 줄이 있어요. force: 두 끝을 같은 기준에 세울 수 없어 숫자를 빼고 이 줄만 보이는 칸 (repair.js epsBase).
// lang: "en" on the old app's English screens (첫 화면 성적표 · 포트폴리오); 기업분석 passes none (Korean only).
export function EpsFixLine({ corp, cos, show = true, force = false, style, lang = "ko" }) {
  const on = force || (show && (!Array.isArray(cos) || cos.some((c) => epsFixNeeded(corp, c))));
  useEffect(() => { if (on && !epsBasisLive(corp)) warnEpsFixLate(corp, kstDate(Date.now()), "뱁새"); }, [on, corp]);
  const text = on ? fixEpsText(lang) : null;
  return text ? <div data-fix="eps" data-lang={lang === "en" ? "en" : "ko"} style={{ ...LINE, ...style }}>{text}</div> : null;
}

// 포트폴리오(data.json 으로 그려요): corp.json 을 한 번 받아(data.js loadCorpOnce, 다른 칸과 같이 써요) 표시와 회사마다의 epsIn 을
// 봐요. 받는 중이거나 받지 못하면 줄이 있어요 (고쳐졌다고 짐작하지 않아요). -> null (모름) | { live, fixed: Set(코드) }
let CORP_FIX = null;
export function useEpsFixState(want) {
  const [st, setSt] = useState(CORP_FIX);
  useEffect(() => {
    if (!want || CORP_FIX !== null) return undefined;
    let alive = true;
    loadCorpOnce().then((d) => {
      if (d && !d.failed) {
        const live = epsBasisLive(d);
        CORP_FIX = { live, fixed: new Set(live && Array.isArray(d.companies) ? d.companies.filter(epsInFixed).map((c) => c.t) : []) };
        if (!live) warnEpsFixLate(d, kstDate(Date.now()), "뱁새");
      }
      if (alive) setSt(d && !d.failed ? CORP_FIX : null);
    });
    return () => { alive = false; };
  }, [want]);
  return st;
}
// codes: 그 칸에 PER · ROE 가 보이는 한국 종목 코드들.
export function EpsFixLineLoaded({ show = true, codes, style, lang = "ko" }) {
  const st = useEpsFixState(show);
  const need = !st || !Array.isArray(codes) || codes.some((t) => !(st.live && st.fixed.has(t)));
  const text = show && need ? fixEpsText(lang) : null;
  return text ? <div data-fix="eps" data-lang={lang === "en" ? "en" : "ko"} style={{ ...LINE, ...style }}>{text}</div> : null;
}

// co: corp.json 의 그 회사 줄.
export function IcrOffLine({ co, show = true, style, lang = "ko" }) {
  return show && icrOff(co) ? <div data-fix="icr" data-lang={lang === "en" ? "en" : "ko"} style={{ ...LINE, ...style }}>{fixIcrText(lang)}</div> : null;
}

// 기업분석: 재무제표를 원화가 아닌 통화로 공시한 회사의 줄 (repair.js stmtCurOf: corp.json stmtCur 그대로, 예: USD). c: corp.json 의 그 회사 줄.
// 기업분석은 한국 회사만 보여요 (미국 종목은 corp.json 에 없어요).
export function stmtCurLineText(c) {
  warnStmtCur(c, "뱁새");
  const cur = stmtCurOf(c);
  return cur ? FIX_STMT_CUR.replace("{currency}", cur) : null;
}
export function StmtCurLine({ c, style }) {
  const text = stmtCurLineText(c);
  return text ? <div data-fix="stmt-cur" data-cur={stmtCurOf(c)} style={{ ...LINE, ...style }}>{text}</div> : null;
}
