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
//   StmtCurLine 재무제표를 원화가 아닌 통화로 공시한 한국 회사(corp.json stmtCur, repair.js stmtCurOf): 기업분석 투자지표 칸에 한 번,
//               첫 화면 성적표(한국어)에서는 '적자이거나 재무 데이터가 아직 없어요.' 자리에. 그런 회사에는 위의 두 줄이 없어요.
//   UnitChkLine 공시 단위 확인에 걸린 한국 회사(corp.json unitChk, repair.js unitHeld — Jack 2026-11-13): 재무제표로 만든 숫자가 비어요.
//               StmtCurLine 과 같은 자리에 한 번 (한국어만 · 영어 글은 승인되지 않아 영어 성적표에는 줄이 없어요). 위의 두 줄도 없어요.
//   PxBadLine   과거 주가 기록 오류 (data.json · corp.json pxBad, repair.js pxBad — Jack 2026-11-14): 주가 기록으로 만든 숫자(52주 · 베타 ·
//               변동성 · 수익률 · 낙폭 · 모멘텀 · 저변동 점수)가 비어요. 화면마다 한 번: 기업분석 머리의 베타 줄 자리, 기업 비교 표 밑, 포트폴리오
//               종목 고르기에서 펼친 종목의 52주 막대 자리 (한국어만 · 영어 글은 승인되지 않아 영어 화면에는 줄이 없어요).
//               2026-11-14 저녁 (Jack): 52주까지 비운 종목만 (움직임이 252봉 안). 움직임이 그보다 오래된 종목은 52주가 보이고, 비운 숫자마다
//               그 자리에 PxBadOneLine "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요." (repair.js pxBadFull · pxBadHides).
//   FundPbrLine 미국 ETF · 펀드의 PBR 과 가치 점수 (Jack 2026-11-27): 펀드에는 회사의 장부가가 없어 보이지 않아요 (data.js mergeStocks).
//               "ETF는 회사가 아니어서 PBR과 가치 점수를 계산하지 않아요." — 종목 고르기에서 펼친 그 종목의 칸 밑 · 내 포트폴리오의 성향 막대 밑
//               (담은 미국 펀드가 가치 평균에서 빠질 때), 화면마다 한 번 (한국어만 · 영어 글은 승인되지 않아 영어 화면은 "–" 만).
// 글자는 12px 이에요 (2.0 의 12px 바닥과 같게).
import React, { useEffect, useState } from "react";
import { C } from "./tokens.js";
import { mdOf, kstDate, loadCorpOnce, ownCloseGroups, ownCloseDate } from "./data.js";
import { EPS_FIX_DATE, epsBasisLive, epsFixNeeded, epsInFixed, epsTotalNci, epsTotalNeeded, epsTotalSide, icrOff, warnEpsFixLate, stmtCurOf, stmtNotWon, warnStmtCur, unitHeld, pxBad, pxBadFull, pxBadHides } from "./repair.js";

export { icrOff };
export const FIX_EPS = "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 fix.eps
export const FIX_ICR = "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 fix.icr
export const FIX_EPS_EN = "PER and EPS are being recalculated and may change on {date}.";       // Jack 승인 2026-11-08 (DeepL 확인) — 영어 화면
export const FIX_ICR_EN = "Interest coverage isn't checked while we fix how it's calculated.";   // Jack 승인 2026-11-08 (DeepL 확인) — 영어 화면
export const FIX_STMT_CUR = "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직 보여 드리지 않아요.";   // Jack 승인 2026-11-08 (DeepL 확인) — 2.0 co.stmtCur
export const FIX_STMT_CUR_EN = "This company files its statements in {currency}, so we don't show its financial figures yet.";   // Jack 승인 2026-11-08 (전달) — 영어 첫 화면 성적표
// 다시 읽은 뒤: 지배주주 줄이 없고 소수주주가 있는 회사(epsIn.b "t" · nci true)에만, PER · EPS 줄 자리에 (repair.js epsTotalNeeded). 영어 글은
// 승인되지 않아 영어 화면에는 없어요. 다시 읽은 뒤에는 PER · EPS 줄이 어느 회사에도 없어요 (날짜가 지났어요).
export const FIX_TOTAL = "이 회사는 지배주주 몫 순이익을 따로 공시하지 않아, PER과 EPS를 회사 전체 순이익으로 계산했어요.";   // Jack 승인 2026-11-08 (전달) — 2.0 fix.total
export const FIX_UNIT = "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요.";   // Jack 승인 2026-11-13 — 2.0 co.unitChk (한국어만)
export const FIX_PX_BAD = "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요.";   // Jack 승인 2026-11-14 — 2.0 co.pxBad (한국어만)
export const FIX_PX_BAD_ONE = "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요.";   // Jack 승인 2026-11-14 저녁 — 2.0 co.pxBadOne (한국어만)
// 2026-11-27 (Jack, answer 12: "Yes, hide them: …"): 미국 ETF · 펀드의 PBR 과 가치 점수는 보이지 않아요 (repair.js fundRow · data.js mergeStocks 가 빼요).
// 2.0 co.fundPbr 와 같은 글자 (tests/test_fund_pbr_app.py 가 같은지 봐요) · 한국어 화면만 (영어 글은 승인되지 않아 영어 화면은 "–" 만, pxBad 줄처럼).
export const FIX_FUND_PBR = "ETF는 회사가 아니어서 PBR과 가치 점수를 계산하지 않아요.";   // Jack 승인 2026-11-27 — 2.0 co.fundPbr (한국어만)
// 2026-11-19 (Jack): 오늘 종가를 두 출처로 확인하지 못해 마지막 확인 종가(pxd)로 실은 국내 종목 — 2.0 app.krOwnClose 와 같은 글자
// (tests/test_kr_own_close.py 가 같은지 봐요). 그 줄의 영어 글은 승인되지 않아서, 영어 화면은 승인된 영어 문장 "{names}: priced at the {md} close."
// (detail.jsx T_OWN_CLOSE.en · 리뷰 M4) 로 그 종목(코드)과 날짜를 말해요. 목록 · 합계에는 FIX_OWN_CLOSE (detail.jsx T_OWN_CLOSE.ko · 2.0
// app.ownClose 와 같은 글자) 다음에 이 줄.
export const FIX_KR_OWN_CLOSE = "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요.";   // Jack 승인 2026-11-19
export const FIX_OWN_CLOSE = "{names} 가격은 {md} 종가예요.";                               // Jack 승인 2026-11-07 (detail.jsx T_OWN_CLOSE.ko)
export const FIX_OWN_CLOSE_EN = "{names}: priced at the {md} close.";                         // Jack 승인 2026-11-07 (detail.jsx T_OWN_CLOSE.en)
// 2026-11-20 (Jack, b · c · a): 목록 · 합계는 날짜마다 한 줄 (이름 + Jack 의 줄 · 2.0 app.krOwnCloseList 와 같은 글자) · 영어 화면은 승인된 영어
// 문장 (한 종목: 그 문장 · 목록: 2026-11-22 부터 아래의 영어 목록 줄) · 나이 상한을 넘어 잠시 뺀 종목은 '찾지 못했어요' 대신 Jack 의 줄 (2.0 app.krOwnAged)
export const FIX_KR_OWN_CLOSE_LIST = "{names}: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요.";   // Jack 승인 2026-11-20
export const FIX_KR_OWN_CLOSE_EN = "We couldn't confirm today's close, so this shows the {date} close.";   // Jack 승인 2026-11-20
export const FIX_KR_AGED = "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요.";                   // Jack 승인 2026-11-20
// 2026-11-21 (Jack, answers 8 · 6): 목록 줄의 이름은 5개까지 + '외 {n}종목' · 그날 미국 종목의 절반 넘게 마지막 확인 종가면 미국 쪽은 한 줄 (2.0 app.krOwnCloseListMore ·
// app.usOwnCloseAll 와 같은 글자). 시장 전체 목록만 (종목 고르기 · 기업분석의 목록) — 내 보유 목록(배너 · 주문 메모 · CSV)은 모든 이름을 적어요
export const FIX_KR_OWN_CLOSE_LIST_MORE = "{names} 외 {n}종목: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요.";   // Jack 승인 2026-11-21
export const FIX_US_OWN_CLOSE_ALL = "미국 종목은 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요.";                // Jack 승인 2026-11-21
export const FIX_OWN_LIST_MAX = 5;
// 2026-11-22 (Jack, verbatim: "1. Yes, with "these show" when several stocks are listed: * "AAPL, MSFT, NVDA, AMZN, GOOGL and 2 more: we couldn't
// confirm today's close, so these show the Nov 20 close." * "US stocks: we couldn't confirm today's close, so these show the Nov 20 close.""):
// 예전 뱁새 영어 화면의 목록 줄 ({names} = 코드 · {date} = "Nov 20"). 시장 전체 목록(종목 고르기)은 한국어 줄과 같은 규칙 (코드 5개까지 +
// "and {n} more" · 미국 상한을 넘으면 미국 쪽은 "US stocks: …" 한 줄) · 내 보유 목록은 모든 코드. 줄이 종목 둘 이상을 말하면 "these show",
// 한 종목이면 "this shows" · 콜론 뒤는 소문자 "we". 한 종목 카드의 문장(FIX_KR_OWN_CLOSE_EN, 앞에 코드 없음)은 그대로예요.
export const FIX_KR_OWN_CLOSE_LIST_EN_ONE = "{names}: we couldn't confirm today's close, so this shows the {date} close.";                // Jack 승인 2026-11-22
export const FIX_KR_OWN_CLOSE_LIST_EN = "{names}: we couldn't confirm today's close, so these show the {date} close.";                    // Jack 승인 2026-11-22
export const FIX_KR_OWN_CLOSE_LIST_MORE_EN = "{names} and {n} more: we couldn't confirm today's close, so these show the {date} close.";  // Jack 승인 2026-11-22
export const FIX_US_OWN_CLOSE_ALL_EN = "US stocks: we couldn't confirm today's close, so these show the {date} close.";                   // Jack 승인 2026-11-22
// 자리 채우기: 넣는 글에 '$' 가 있어도 그대로 들어가요 (String.replace 의 '$&' 같은 뜻이 생기지 않게 함수로)
const fillOwn = (tpl, v) => tpl.replace(/\{(names|n|date)\}/g, (m, k) => (v[k] == null ? m : String(v[k])));
// 한 종목 (data.json 종목 또는 corp.json 회사 — 회사 줄에는 cls 가 없어서 marketDate 로 그 데이터의 pxDate 를 받아요): 줄 또는 null.
// lang "en": 승인된 영어 문장 ("We couldn't confirm today's close, so this shows the Nov 16 close.")
// 2026-11-20 (Jack, US carry): a US stock carried because Yahoo had no close (data.json pxc: true) reads the same (marketDate: usPxDate).
export function krOwnCloseText(c, marketDate = null, lang = "ko") {
  const d = c && (c.cls == null || c.cls === "kr" || (c.cls === "us" && c.pxc === true)) ? ownCloseDate(c, marketDate) : null;
  const md = d ? mdOf(d, lang === "en" ? "en" : "ko") : null;
  if (!md) return null;
  return lang === "en" ? FIX_KR_OWN_CLOSE_EN.replace("{date}", md) : FIX_KR_OWN_CLOSE.replace("{date}", md);
}
// 목록의 한 줄 (한국어: Korean names · 영어: codes): "{names}: …"
// names: 이은 글 (", " 로 · 내 보유 목록: 모두 적어요) 또는 이름 목록 (시장 전체 목록: 5개를 넘으면 앞 5개 + 한국어 '외 {n}종목' · 영어 "and {n} more")
// 영어 (Jack 2026-11-22): 이 줄이 말하는 종목이 하나면 "this shows", 둘 이상이면 "these show" (이은 글은 ", " 로 세요 — 영어 화면의 이름은 코드라
// ", " 가 들어 있지 않아요)
export function krOwnCloseListLine(names, date, lang = "ko") {
  const md = mdOf(date, lang === "en" ? "en" : "ko");
  if (!md) return null;
  const arr = Array.isArray(names) ? names : null;
  if (lang === "en") {
    if (arr && arr.length > FIX_OWN_LIST_MAX) {
      return fillOwn(FIX_KR_OWN_CLOSE_LIST_MORE_EN, { names: arr.slice(0, FIX_OWN_LIST_MAX).join(", "), n: arr.length - FIX_OWN_LIST_MAX, date: md });
    }
    const all = arr || String(names).split(", ");
    return fillOwn(all.length > 1 ? FIX_KR_OWN_CLOSE_LIST_EN : FIX_KR_OWN_CLOSE_LIST_EN_ONE, { names: all.join(", "), date: md });
  }
  if (arr && arr.length > FIX_OWN_LIST_MAX) {
    return FIX_KR_OWN_CLOSE_LIST_MORE.replace("{names}", arr.slice(0, FIX_OWN_LIST_MAX).join(", ")).replace("{n}", String(arr.length - FIX_OWN_LIST_MAX)).replace("{date}", md);
  }
  return FIX_KR_OWN_CLOSE_LIST.replace("{names}", arr ? arr.join(", ") : names).replace("{date}", md);
}
// 2026-11-21 (Jack, answer 6): 그날 미국 종목의 절반 넘게 마지막 확인 종가일 때 미국 쪽의 한 줄 · 영어 화면 (Jack 2026-11-22): "US stocks: …"
export function usOwnCloseAllLine(date, lang = "ko") {
  const en = lang === "en";
  const md = mdOf(date, en ? "en" : "ko");
  return md ? fillOwn(en ? FIX_US_OWN_CLOSE_ALL_EN : FIX_US_OWN_CLOSE_ALL, { date: md }) : null;
}
export function KrOwnCloseLine({ c, marketDate = null, style, lang = "ko" }) {
  const text = krOwnCloseText(c, marketDate, lang === "en" ? "en" : "ko");
  return text ? <div data-fix="kr-own-close" data-t={c.t} data-pxd={c.pxd} style={{ ...LINE, ...style }}>{text}</div> : null;
}
// 여러 회사 (기업분석의 목록 · 표): 마지막 확인 종가로 실은 회사를 날짜마다 한 문장 + Jack 의 줄. 없으면 null. list: corp.json 회사들 (cls 없음 → 국내)
export function krOwnCloseListText(list) {
  const out = [];
  for (const g of ownCloseGroups((list || []).filter(Boolean).map((c) => ({ ...c, cls: "kr" })), null)) {
    const line = krOwnCloseListLine(g.names || g.ts, g.date, "ko");
    if (!line) return null;
    out.push(line);
  }
  return out.length ? out.join(" ") : null;
}
export function KrOwnCloseListLine({ list, style }) {
  const text = krOwnCloseListText(list);
  return text ? <div data-fix="kr-own-close-list" style={{ ...LINE, ...style }}>{text}</div> : null;
}
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
// 다시 읽은 뒤(표시가 있으면): 총 순이익("t") 회사 · 해외 기업은 고치는 중 줄이 없고, 그중 "t" + how total + nci 는 한 회사 칸에서만
// 총 순이익 줄(FIX_TOTAL, "이 회사는 …"). many: 여러 회사가 함께 보이는 칸 (목록 · 표 · 그래프) — 총 순이익 줄은 없어요 (리뷰 2).
// force(숫자를 뺀 칸)는 예전처럼 줄이 있되, "t" · 해외 기업이면 총 순이익 줄이거나 없어요. -> "eps" | "total" | null
export function epsLineKind({ corp, cos, show = true, force = false, many = false }) {
  if (!epsBasisLive(corp)) return force || (show && (!Array.isArray(cos) || cos.some((c) => epsFixNeeded(corp, c)))) ? "eps" : null;
  if (!(force || show)) return null;
  if (!Array.isArray(cos)) return "eps";
  if (force ? cos.some((c) => !stmtNotWon(c) && !epsTotalSide(c)) : cos.some((c) => epsFixNeeded(corp, c))) return "eps";
  return !many && cos.some((c) => epsTotalNeeded(corp, c)) ? "total" : null;
}
export function EpsFixLine({ corp, cos, show = true, force = false, many = false, style, lang = "ko" }) {
  const kind = epsLineKind({ corp, cos, show, force, many });
  useEffect(() => { if (kind === "eps") warnEpsFixLate(corp, kstDate(Date.now()), "뱁새"); }, [kind, corp]);
  const text = kind === "eps" ? fixEpsText(lang) : kind === "total" && lang !== "en" ? FIX_TOTAL : null;
  return text ? <div data-fix={kind} data-lang={lang === "en" ? "en" : "ko"} style={{ ...LINE, ...style }}>{text}</div> : null;
}

// 포트폴리오(data.json 으로 그려요): corp.json 을 한 번 받아(data.js loadCorpOnce, 다른 칸과 같이 써요) 표시와 회사마다의 epsIn 을
// 봐요. 받는 중이거나 받지 못하면 줄이 있어요 (고쳐졌다고 짐작하지 않아요). -> null (모름) | { live, fixed: Set(코드) }
let CORP_FIX = null;
// 받은 corp.json 으로 정하는 상태 (순수): live · fixed(epsIn.b "o" · "s") · notWon(재무제표를 원화가 아닌 통화로 공시한 회사, repair.js
// stmtNotWon, 읽을 수 없는 코드도 — 숫자가 비어 있어요: 줄 없음 · 2026-11-13: 공시 단위 확인에 걸린 회사(unitHeld)도 같아요)
export function corpFixState(d) {
  const live = epsBasisLive(d);
  const cos = d && Array.isArray(d.companies) ? d.companies : [];
  return { live, fixed: new Set(live ? cos.filter((c) => epsInFixed(c) || epsTotalSide(c)).map((c) => c.t) : []),
    notWon: new Set(cos.filter((c) => stmtNotWon(c) || unitHeld(c)).map((c) => c.t)),
    total: new Set(live ? cos.filter((c) => epsTotalNci(c) && !stmtNotWon(c)).map((c) => c.t) : []) };
}
// 그 칸에 줄이 필요한지: 상태를 모르면(받는 중 · 못 받음) 있어요. 아니면 그 칸의 코드 중 하나라도 고쳐지지 않았고 원화 재무제표인 회사가 있을 때.
// (다시 읽은 뒤 fixed 에는 총 순이익("t") 회사 · 해외 기업도 들어 있어요: 그 회사들은 고치는 중 줄이 없어요.)
export function epsFixNeedLoaded(st, codes) {
  return !st || !Array.isArray(codes) || codes.some((t) => !st.notWon.has(t) && !(st.live && st.fixed.has(t)));
}
// 다시 읽은 뒤: 한 회사(one, 코드)의 칸에서 그 회사가 총 순이익 줄이 필요할 때 (상태를 모르면 없어요: 그때는 위의 PER · EPS 줄).
export const epsTotalNeedLoaded = (st, one) => !!st && st.live && typeof one === "string" && st.total.has(one);
export function useEpsFixState(want) {
  const [st, setSt] = useState(CORP_FIX);
  useEffect(() => {
    if (!want || CORP_FIX !== null) return undefined;
    let alive = true;
    loadCorpOnce().then((d) => {
      if (d && !d.failed) {
        CORP_FIX = corpFixState(d);
        if (!CORP_FIX.live) warnEpsFixLate(d, kstDate(Date.now()), "뱁새");
      }
      if (alive) setSt(d && !d.failed ? CORP_FIX : null);
    });
    return () => { alive = false; };
  }, [want]);
  return st;
}
// codes: 그 칸에 PER · ROE 가 보이는 한국 종목 코드들. one: 한 회사의 칸이면 그 코드 — 총 순이익 줄은 그 회사로만 정해요 (같은 업종 표의
// 다른 회사로는 아니에요). 여러 회사의 칸(one 없음)에는 총 순이익 줄이 없어요 (리뷰 2).
export function EpsFixLineLoaded({ show = true, codes, one, style, lang = "ko" }) {
  const st = useEpsFixState(show);
  const kind = !show ? null : epsFixNeedLoaded(st, codes) ? "eps" : epsTotalNeedLoaded(st, one) ? "total" : null;
  const text = kind === "eps" ? fixEpsText(lang) : kind === "total" && lang !== "en" ? FIX_TOTAL : null;
  return text ? <div data-fix={kind} data-lang={lang === "en" ? "en" : "ko"} style={{ ...LINE, ...style }}>{text}</div> : null;
}

// co: corp.json 의 그 회사 줄.
export function IcrOffLine({ co, show = true, style, lang = "ko" }) {
  return show && icrOff(co) ? <div data-fix="icr" data-lang={lang === "en" ? "en" : "ko"} style={{ ...LINE, ...style }}>{fixIcrText(lang)}</div> : null;
}

// 기업분석: 재무제표를 원화가 아닌 통화로 공시한 회사의 줄 (repair.js stmtCurOf: corp.json stmtCur 그대로, 예: USD). c: corp.json 의 그 회사 줄.
// 기업분석은 한국 회사만 보여요 (미국 종목은 corp.json 에 없어요).
// lang "en": 영어 첫 화면 성적표 (FIX_STMT_CUR_EN).
export function stmtCurLineText(c, lang = "ko") {
  warnStmtCur(c, "뱁새");
  const cur = stmtCurOf(c);
  return cur ? (lang === "en" ? FIX_STMT_CUR_EN : FIX_STMT_CUR).replace("{currency}", cur) : null;
}
// 공시 단위 확인 (Jack, 2026-11-13): c 는 corp.json 의 그 회사 줄. 기업분석은 한국어 화면이라 lang 이 없어요.
export function UnitChkLine({ c, style }) {
  return unitHeld(c) ? <div data-fix="unit-chk" style={{ ...LINE, ...style }}>{FIX_UNIT}</div> : null;
}
// 과거 주가 기록 오류 (Jack, 2026-11-14): c 는 corp.json 의 그 회사 줄 또는 data.json 의 그 종목 (repair.js pxBad). 한국어 화면에서만 (lang 이
// "en" 이면 줄 없이 — 영어 글은 승인되지 않았어요).
export function PxBadLine({ c, style, lang = "ko" }) {
  return pxBadFull(c) && lang !== "en" ? <div data-fix="px-bad" style={{ ...LINE, ...style }}>{FIX_PX_BAD}</div> : null;
}
// 2026-11-14 저녁 (Jack): 52주는 보이고 field(예: "beta" · "r36") 가 비었을 때, 그 숫자 자리에 한 번 (한국어 화면만).
export function PxBadOneLine({ c, field, style, lang = "ko" }) {
  return pxBad(c) && !pxBadFull(c) && pxBadHides(c, field) && lang !== "en"
    ? <div data-fix="px-bad-one" style={{ ...LINE, ...style }}>{FIX_PX_BAD_ONE}</div> : null;
}
// 2026-11-27 (Jack): 미국 ETF · 펀드 (합친 줄의 fundNoBook · cls "us" — 379800 도) 의 PBR 이 비어 있으면 그 자리에 한 번 (한국어 화면만).
// 종목 고르기의 펼친 종목 ("PER / PBR" 칸이 "… / –") · 내 포트폴리오의 성향 (담은 미국 펀드가 가치 평균에서 빠질 때 · show 로). 숫자 옆에는 없어요.
export const fundPbrRow = (s) => !!s && s.fundNoBook === true && s.cls === "us" && s.pbr == null;
// 내 포트폴리오의 성향: 담은 미국 펀드가 가치 점수(vz)가 없어 가치 평균에서 빠질 때 (#203 리뷰: PBR 이 아니라 빠지는 가치 점수로 봐요 — 사용자가
// 종목 데이터 수정에 PBR 을 적어도 펀드는 여전히 빠지고 줄도 남아요). 종목 고르기의 줄은 위의 fundPbrRow ("PER / PBR" 칸이 "… / –" 일 때).
export const fundVzOut = (s) => !!s && s.fundNoBook === true && s.cls === "us" && typeof s.vz !== "number";
export function FundPbrLine({ c, show, style, lang = "ko" }) {
  const on = show === undefined ? fundPbrRow(c) : !!show;
  return on && lang !== "en" ? <div data-fix="fund-pbr" style={{ ...LINE, ...style }}>{FIX_FUND_PBR}</div> : null;
}
// 리뷰 #118 N7: 공시 단위 확인에 걸린 회사(unitChk)면 통화 줄 대신 단위 줄(UnitChkLine)만 — 두 줄을 겹쳐 보이지 않아요.
export function StmtCurLine({ c, style }) {
  const text = unitHeld(c) ? null : stmtCurLineText(c);
  return text ? <div data-fix="stmt-cur" data-cur={stmtCurOf(c)} style={{ ...LINE, ...style }}>{text}</div> : null;
}
