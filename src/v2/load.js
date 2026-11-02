// Data loading for app.html. Same-origin files only, through src/data.js (loadJson: no-store fetch, NaN repair).
// Only the v17.5 format is accepted: data.json and corp.json must carry pxDate and publishedAt, macro.json publishedAt
// (macro.json has no price date in the v17.5 format). Anything else is a load failure, never example data.
// The preview page (app-preview.html) does not fetch anything: it passes its embedded fictional files to resolveLoad.
import { loadJson, freshness } from "../data.js";
import { detectFeatures, missingForBuild, CUSHION_ASSETS } from "./engine.js";
import { R2022 } from "./y2022.js";

// publishedAt must be a time we can read: without it we cannot tell whether the data is fresh, so the file is refused
// like any other format problem (the load-failure message), never treated as fresh.
export const isV175 = (d) => !!(d && typeof d === "object" && !Array.isArray(d) && d.pxDate && d.publishedAt
  && typeof d.publishedAt === "string" && Number.isFinite(Date.parse(d.publishedAt)));

export const CHECKS = {
  data: (d) => isV175(d) && Array.isArray(d.stocks) && d.stocks.length > 0,
  corp: (d) => isV175(d) && Array.isArray(d.companies),
  macro: (d) => !!(d && typeof d === "object" && d.publishedAt),
};

export async function loadAll(now) {
  const [data, corp, macro] = await Promise.all([
    loadJson("./data.json", CHECKS.data),
    loadJson("./corp.json", CHECKS.corp),
    loadJson("./macro.json", CHECKS.macro),
  ]);
  return resolveLoad({ data, corp, macro }, now);
}

// opts.preview: the fictional example data of app-preview.html. It has a fixed publish date, so the stale check
// (publishedAt more than 4 days old) is switched off there and only there; the page says "예시 데이터" on every screen.
export function resolveLoad({ data, corp, macro }, now, opts = {}) {
  if (!data.ok || !corp.ok) {
    const why = [!data.ok && "data.json: " + data.error, !corp.ok && "corp.json: " + corp.error].filter(Boolean).join(" / ");
    console.warn("[v2] load failed: " + why);
    return { status: "fail" };
  }
  if (!macro.ok) console.warn("[v2] macro.json not loaded: " + macro.error + " (features that need it stay hidden)");
  const d = data.data, c = corp.data, m = macro.ok ? macro.data : null;
  const features = detectFeatures(d, c, m);
  const missing = missingForBuild(features);
  if (missing.length) console.warn("[v2] fields not live yet, deck builder hidden: " + missing.join(", "));
  const fresh = opts.preview ? { md: null, days: 0, stale: false } : freshness(d.pxDate, d.publishedAt, "ko", now);
  const byT = new Map(d.stocks.map((s) => [s.t, s]));
  const coByT = new Map(c.companies.map((x) => [x.t, x]));
  return { status: "ok", data: d, corp: c, macro: m, features, missing, fresh, byT, coByT, preview: !!opts.preview,
    cushion: opts.cushion || CUSHION_ASSETS, r2022: opts.r2022 || R2022 };
}
