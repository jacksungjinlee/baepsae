// Data loading for app.html. Same-origin files only, through src/data.js (loadJson: no-store fetch, NaN repair).
// Only the v17.5 format is accepted: data.json and corp.json must carry pxDate and publishedAt, macro.json publishedAt
// (macro.json has no price date in the v17.5 format). Anything else is a load failure, never example data.
import { loadJson, freshness } from "../data.js";
import { detectFeatures, missingForBuild } from "./engine.js";

export const isV175 = (d) => !!(d && typeof d === "object" && !Array.isArray(d) && d.pxDate && d.publishedAt);

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

export function resolveLoad({ data, corp, macro }, now) {
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
  const fresh = freshness(d.pxDate, d.publishedAt, "ko", now);
  const byT = new Map(d.stocks.map((s) => [s.t, s]));
  const coByT = new Map(c.companies.map((x) => [x.t, x]));
  return { status: "ok", data: d, corp: c, macro: m, features, missing, fresh, byT, coByT };
}
