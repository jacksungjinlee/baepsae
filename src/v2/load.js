// Data loading for app.html. Same-origin files only, through src/data.js (loadJson: no-store fetch, NaN repair).
// v19.1a: disc.json too, but only when a company page opens (loadDisc).
// Only the v17.5 format is accepted: data.json and corp.json must carry pxDate and publishedAt, macro.json publishedAt
// (macro.json has no price date in the v17.5 format). Anything else is a load failure, never example data.
// The preview page (app-preview.html) does not fetch anything: it passes its embedded fictional files to resolveLoad.
import { loadJson, freshness } from "../data.js";
import { detectFeatures, missingForBuild, CUSHION_ASSETS, setDataShape } from "./engine.js";
import { R2022 } from "./y2022.js";

// publishedAt must be a time we can read: without it we cannot tell whether the data is fresh, so the file is refused
// like any other format problem (the load-failure message), never treated as fresh.
export const isV175 = (d) => !!(d && typeof d === "object" && !Array.isArray(d) && d.pxDate && d.publishedAt
  && typeof d.publishedAt === "string" && Number.isFinite(Date.parse(d.publishedAt)));

export const CHECKS = {
  data: (d) => isV175(d) && Array.isArray(d.stocks) && d.stocks.length > 0,
  corp: (d) => isV175(d) && Array.isArray(d.companies),
  macro: (d) => !!(d && typeof d === "object" && d.publishedAt),
  // v19.1a: disc.json (the 공시 tab): the v17.5 file with its two lists and its content date (asOf, YYYY-MM-DD)
  disc: (d) => !!(d && typeof d === "object" && !Array.isArray(d) && Array.isArray(d.insider) && Array.isArray(d.nps)
    && typeof d.asOf === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d.asOf) && typeof d.publishedAt === "string" && Number.isFinite(Date.parse(d.publishedAt))),
};

export async function loadAll(now) {
  const [data, corp, macro] = await Promise.all([
    loadJson("./data.json", CHECKS.data),
    loadJson("./corp.json", CHECKS.corp),
    loadJson("./macro.json", CHECKS.macro),
  ]);
  return resolveLoad({ data, corp, macro }, now);
}

// v19.1a: disc.json, only when a company page opens (the live page; app.jsx asks once). -> { ok, data, error }
export function loadDisc() {
  return loadJson("./disc.json", CHECKS.disc);
}

// v19.3a: company logos are our own files on this site (the logos branch, copied in by Deploy; never another site).
// The index is asked for once, by the live page only (main.jsx hands this to logo.jsx); the preview never asks.
export const LOGO_DIR = "./logos/";
export const logoIndexOk = (d) => !!(d && typeof d === "object" && !Array.isArray(d) && d.version === 1
  && d.logos && typeof d.logos === "object" && !Array.isArray(d.logos));
export function loadLogoIndex() {
  return loadJson("./logos/index.json", logoIndexOk);
}

// opts.preview: the fictional example data of app-preview.html. It has a fixed publish date, so the stale check
// (publishedAt more than 4 days old) is switched off there and only there; the page says "예시 데이터" on every screen.
export function resolveLoad({ data, corp, macro }, now, opts = {}) {
  if (!data.ok || !corp.ok) {
    const why = [!data.ok && "data.json: " + data.error, !corp.ok && "corp.json: " + corp.error].filter(Boolean).join(" / ");
    console.warn("[v2] load failed: " + why);
    setDataShape(null);
    return { status: "fail" };
  }
  if (!macro.ok) console.warn("[v2] macro.json not loaded: " + macro.error + " (features that need it stay hidden)");
  const d = data.data, c = corp.data, m = macro.ok ? macro.data : null;
  // v19.1b: data.json with divCheck carries the exact dividend fields and the beta error band (engine.setDataShape). The
  // whole app reads this one file one way; a file without it keeps the earlier behaviour. The console line with the
  // counts is company.jsx logSplitGuard (once per load, in the browser).
  const exact = setDataShape(d);
  const features = detectFeatures(d, c, m);
  const missing = missingForBuild(features);
  if (missing.length) console.warn("[v2] fields not live yet, deck builder hidden: " + missing.join(", "));
  const fresh = opts.preview ? { md: null, days: 0, stale: false } : freshness(d.pxDate, d.publishedAt, "ko", now);
  const byT = new Map(d.stocks.map((s) => [s.t, s]));
  const coByT = new Map(c.companies.map((x) => [x.t, x]));
  return { status: "ok", data: d, corp: c, macro: m, features, missing, fresh, byT, coByT, preview: !!opts.preview,
    cushion: opts.cushion || CUSHION_ASSETS, r2022: opts.r2022 || R2022, exact };
}
