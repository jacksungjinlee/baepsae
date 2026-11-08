// ================= 재무 경고 신호 (KR): one function for every screen (moved from company.js in v19.3d) =================
// The company page (company.js re-exports these) and the 재무 경고 0개 portfolio rule (pf.js) read the same result, so the
// two screens always agree. Pure; no Korean here.
import { num } from "./engine.js";

// ---------------- 재무 경고 신호 (KR) ----------------
// The old app's flags (corp.json fl, written only when one fires): 유동비율 < 100% · 이자보상배율 < 1 · 3 years of net
// loss · 자본잠식. "No flag" is only a fact when every check really ran or does not apply: corp.json flRan lists the checks
// that ran (v19.1b, PR #50) and flNa the ones that do not apply (financial companies: 유동비율 and 이자보상배율). allRan =
// every one of the four is in flRan or flNa. Without flRan (files before v19.1b) the screen claims nothing when no flag
// fired. US: none until v19.2 (Yahoo's debtToEquity is not 부채비율).
export const WARN_CHECKS = ["cr", "icr", "l3", "imp"];
export const FIN_SUB_SECTORS = ["bank", "insure", "broker"];   // corp.json s (fetch_data.py FIN_SECS without holding)
export const FIN_SUB_INDS = ["bank", "insurance", "securities", "finance"];   // data.json ind: financial holding companies too
export function warnings(s, co) {
  if (!s || s.cls !== "kr" || !co) return { allRan: false, ran: null, flags: [] };
  const fl = co.fl && typeof co.fl === "object" ? co.fl : {};
  const flags = [];
  if (num(fl.cr) != null) flags.push({ code: "cr", x: fl.cr });
  if (num(fl.icr) != null) flags.push({ code: "icr", x: fl.icr });
  if (fl.l3) flags.push({ code: "l3" });
  if (fl.imp) flags.push({ code: "imp" });
  const ran = Array.isArray(co.flRan) ? WARN_CHECKS.filter((c) => co.flRan.includes(c)) : null;
  const na = Array.isArray(co.flNa) ? WARN_CHECKS.filter((c) => co.flNa.includes(c) && !(ran || []).includes(c)) : [];
  const q = typeof co.bq === "string" ? /^(\d{4})\.([1-4])Q$/.exec(co.bq) : null;
  // The line under 없어요 says which checks it is (Jack, PR #68 B7), only when the two 'not applicable' checks are exactly
  // 유동비율 and 이자보상배율 (flNa) and the two others ran (flRan):
  //   "fin"     a financial company: corp.json s bank · insure · broker, or data.json ind bank · insurance · securities ·
  //             finance (KB금융 · 신한지주 · 메리츠금융지주 · 한국금융지주 …)
  //   "holding" any other company with s holding. Once the pipeline runs those two checks for such a holding, flNa goes
  //             and this stops matching by itself (the plain line again).
  //   null      everyone else (the plain line)
  const sec = typeof co.s === "string" ? co.s : typeof s.s === "string" ? s.s : null;
  const exactNa = Array.isArray(co.flNa) && co.flNa.length === 2 && ["cr", "icr"].every((c) => co.flNa.includes(c));
  const finCo = FIN_SUB_SECTORS.includes(sec) || FIN_SUB_INDS.includes(s.ind);
  const narrow = exactNa && !!ran && ["l3", "imp"].every((c) => ran.includes(c));
  const sub = !narrow ? null : finCo ? "fin" : sec === "holding" ? "holding" : null;
  const allRan = !!ran && ran.length + na.length === WARN_CHECKS.length;
  // Jack, PR #68 B7 (2026-11-07): when every check ran except 이자보상배율, and the pipeline says that is because the
  // statements have no interest-expense line (corp.json flWhy.icr "ie"), the card says which three it checked ("확인한 …
  // 없어요"). Any other reason (no operating profit "op", a negative figure "neg", switched off "off" while the pipeline's
  // ICR_OFF holds the check back, or no reason written) claims nothing.
  const why = co.flWhy && typeof co.flWhy === "object" ? co.flWhy.icr : null;
  const partial = !flags.length && !allRan && !!ran && ["cr", "l3", "imp"].every((c) => ran.includes(c)) && !ran.includes("icr") &&
    !na.includes("icr") && why === "ie";
  // Jack, PR #68 (2026-11-07): the ratio used the cash-flow statement's interest paid (corp.json flSrc.icr "cf", v19.1f).
  // Not with an operating loss: that line shows no number, so there is no calculation to explain (review).
  const icrFlag = flags.find((f) => f.code === "icr");
  const icrCf = !!icrFlag && !(icrFlag.x < 0 || Object.is(icrFlag.x, -0)) && !!co.flSrc && typeof co.flSrc === "object" &&
    co.flSrc.icr === "cf";
  return { allRan, partial, icrCf, ran, na, sub, flags, fy: num(co.fy), quarter: q ? { y: Number(q[1]), q: Number(q[2]) } : null };
}
