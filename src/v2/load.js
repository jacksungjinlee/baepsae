// Data loading for app.html. Same-origin files only, through src/data.js (loadJson: no-store fetch, NaN repair).
// v19.1a: disc.json too, but only when a company page opens (loadDisc).
// Only the v17.5 format is accepted: data.json and corp.json must carry pxDate and publishedAt, macro.json publishedAt
// (macro.json has no price date in the v17.5 format). Anything else is a load failure, never example data.
// The preview page (app-preview.html) does not fetch anything: it passes its embedded fictional files to resolveLoad.
import { loadJson, freshness, staleAfterTime, ownCloseReport, STALE_DAYS, daysSince, nextFreshChange } from "../data.js";
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

// v19.1c: console warnings at load about the dates the screens use (never silent): the fallback to the 4-day rule when the
// file has no staleAfter or one that cannot be read, and the US stocks priced at an earlier close (pxd), with counts. A pxd
// that cannot be read is its own warning: that stock shows its price with no date and no change. A readable staleAfter says
// nothing (console.warn only: nothing here writes to stdout, which the Node tests read).
export function logDates(d) {
  const sa = d.staleAfter;
  if (sa == null) console.warn("[v2] data.json staleAfter is missing or null: stale after " + STALE_DAYS + " days from publishedAt");
  else if (staleAfterTime(sa) == null) console.warn("[v2] data.json staleAfter cannot be read (" + JSON.stringify(sa) + "): stale after " + STALE_DAYS + " days from publishedAt");
  const r = ownCloseReport(d.stocks, d.usPxDate);
  const us = d.stocks.filter((s) => s && s.cls === "us").length;
  if (r.own.length) {
    console.warn(`[v2] ${r.own.length} of ${us} US stocks at an earlier close than ${d.usPxDate} (pxd, no daily change): `
      + r.own.slice(0, 30).map(([t, x]) => `${t} ${x}`).join(", ") + (r.own.length > 30 ? ` and ${r.own.length - 30} more` : ""));
  }
  // pxd equal to usPxDate: the pipeline never writes it (the field is left out then) and the publication gate refuses it. If it
  // ever comes, the price is at the US date anyway, so the stock is shown like any other (its d1 is still not read).
  if (r.same.length) console.warn(`[v2] ${r.same.length} US stocks carry pxd equal to usPxDate (not expected; shown at the US date, no daily change): ${r.same.slice(0, 30).join(", ")}`);
  if (r.bad.length) console.warn(`[v2] ${r.bad.length} US stocks with a pxd that cannot be read (price shown with no date and no daily change): ${r.bad.slice(0, 30).join(", ")}`);
  return r;
}

// v19.1c: the stale check again, without fetching or changing any data: an app opened in the morning and left open must
// show the warning once staleAfter passes (16:47 on the due day), and the day count n moves at midnight-of-publish. App
// (app.jsx) calls this when the page is shown again (visibilitychange, focus) and from a timer (nextFreshCheck).
// -> the same load object when nothing a screen reads changed (no re-render), else a copy with the new fresh and checkedAt
// (todayCtx / rules.js dayState then run again: the 홈 stale band and the daily check follow, including corp.json's 4-day rule).
export function refreshFresh(load, now) {
  if (!load || load.status !== "ok" || load.preview) return load;
  const t = now == null ? Date.now() : now;
  const d = load.data;
  const f = freshness(d.pxDate, d.publishedAt, "ko", t, d.staleAfter);
  const o = load.fresh || {};
  const corpPub = load.corp && load.corp.publishedAt;
  const sameCorp = daysSince(corpPub, load.checkedAt) === daysSince(corpPub, t);
  if (f.stale === o.stale && f.days === o.days && f.md === o.md && sameCorp) return load;
  return { ...load, fresh: f, checkedAt: t };
}
// ms until the stale check can give another answer (data.js nextFreshChange: staleAfter, the next day of either publish
// time, at most an hour), or null (preview, loading, failed: nothing to re-check).
export function nextFreshCheck(load, now) {
  if (!load || load.status !== "ok" || load.preview) return null;
  return nextFreshChange(now, [load.data.publishedAt, load.corp && load.corp.publishedAt], load.data.staleAfter);
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
  // v19.1c (Jack, 2026-11-07): stale once data.json's staleAfter has passed (the time the next publish is due, weekends and
  // market holidays counted by the pipeline); a file without one, or with one that cannot be read, keeps the 4-day rule.
  // The 4-day rule also stays as a backstop (data.js freshness).
  const fresh = opts.preview ? { md: null, days: 0, stale: false } : freshness(d.pxDate, d.publishedAt, "ko", now, d.staleAfter);
  if (!opts.preview) logDates(d);
  const byT = new Map(d.stocks.map((s) => [s.t, s]));
  const coByT = new Map(c.companies.map((x) => [x.t, x]));
  return { status: "ok", data: d, corp: c, macro: m, features, missing, fresh, byT, coByT, preview: !!opts.preview,
    cushion: opts.cushion || CUSHION_ASSETS, r2022: opts.r2022 || R2022, exact, checkedAt: now == null ? Date.now() : now };
}
