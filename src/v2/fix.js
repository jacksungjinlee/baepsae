// ================= 2.0: the two lines until the DART re-read (src/repair.js says why) =================
// The PER/EPS line depends on corp.json: its top-level epsBasis and, per company, epsIn.b (repair.js epsFixNeeded). The
// whole app reads that one way: load.js resolveLoad calls setEpsBasis(corp) once per load (the way engine.setDataShape
// works), so a screen that only has a held stock (daily.jsx) knows it too. Until a file is loaded the line is on (a fix is
// never assumed). Pure; no Korean (src/copy/v2.js C.fix).
import { EPS_FIX_DATE, epsBasisLive, epsInFixed, icrOff, warnEpsFixLate } from "../repair.js";
import { kstDate } from "../data.js";

export { EPS_FIX_DATE, icrOff };

let live = false;
let fixed = new Set();        // codes whose epsIn.b is "o" or "s" (only read when live)
// corp: the loaded corp.json (null when it failed). now: ms (tests). preview: the example page (fixed dates: no warning).
export function setEpsBasis(corp, { now, preview = false } = {}) {
  live = epsBasisLive(corp);
  fixed = new Set(live && Array.isArray(corp.companies) ? corp.companies.filter(epsInFixed).map((c) => c.t) : []);
  if (!preview && corp) warnEpsFixLate(corp, kstDate(now == null ? Date.now() : now), "v2");
  return live;
}
export const epsBasisIsLive = () => live;

// The PER/EPS line for a section showing one Korean stock's PER, EPS or a number from the same net income (ROE, the reverse
// DCF, 배당성향, 주가는 무엇으로 움직였나). s: the data.json row (or anything with t and cls). US and funds: never. After the
// re-read: only for companies still on total profit (epsIn.b "t" or no epsIn).
export const epsFixFor = (s) => !!s && s.cls === "kr" && !(live && fixed.has(s.t));
// Same, for a section where several stocks show such numbers (any one that needs it is enough).
export const epsFixForAny = (rows) => Array.isArray(rows) && rows.some(epsFixFor);
