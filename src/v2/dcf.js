// ================= 2.0 지금 가격이 가정하는 것 (v19.1a Part C · D): the reverse calculation =================
// Ported from the old app's DcfCard (src/corp.jsx dcfPerShare · reverseDcf), unchanged except that 2.0 holds the growth
// rate constant for the 5 years (fade off, see company.js impliedGrowth). No imports: store.js validates saved
// assumptions with okAssume without pulling in the company page's code. No Korean text.
export const DCF = { disc: 10, term: 2, lo: -30, hi: 60, discRange: [6, 16], termRange: [0, 4], step: 0.5 };   // the old DcfCard
const EPS = 1e-9;

// Model value per share (원) for net income ni0 (억원), shares sharesM (백만주), growth g1 for 5 years, then term forever.
export function dcfPerShare({ ni0, sharesM, g1, fade = false, disc, term }) {
  if (!ni0 || !sharesM || sharesM <= 0) return null;
  const d = disc / 100, tg = term / 100;
  if (d <= tg + 0.005) return null;
  let pv = 0, ni = ni0;
  for (let t = 1; t <= 5; t++) {
    const g = fade ? (g1 + ((term - g1) * (t - 1)) / 4) / 100 : g1 / 100;
    ni *= 1 + g;
    pv += ni / Math.pow(1 + d, t);
  }
  const tv = (ni * (1 + tg)) / (d - tg);
  pv += tv / Math.pow(1 + d, 5);
  return (pv / sharesM) * 100;                       // 억원 / 백만주 -> 원 per share
}
export function reverseDcf({ price, ni0, sharesM, fade = false, disc, term }) {
  if (!price || !ni0 || ni0 <= 0 || !sharesM) return null;
  const f = (g) => dcfPerShare({ ni0, sharesM, g1: g, fade, disc, term }) - price;
  let lo = DCF.lo, hi = DCF.hi;
  if (f(lo) > 0) return { edge: "low" };
  if (f(hi) < 0) return { edge: "high" };
  for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; if (f(mid) > 0) hi = mid; else lo = mid; }
  return { g: (lo + hi) / 2 };
}
// A saved calculator assumption: both numbers inside the calculator's ranges, in its 0.5 steps.
export const okAssume = (a) => !!a && Number.isFinite(a.disc) && Number.isFinite(a.term) && a.disc >= DCF.discRange[0] && a.disc <= DCF.discRange[1]
  && a.term >= DCF.termRange[0] && a.term <= DCF.termRange[1] && Math.abs(a.disc * 2 - Math.round(a.disc * 2)) < EPS && Math.abs(a.term * 2 - Math.round(a.term * 2)) < EPS;
