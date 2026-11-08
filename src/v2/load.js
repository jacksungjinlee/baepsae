// Data loading for app.html. Same-origin files only, through src/data.js (loadJson: no-store fetch, NaN repair).
// v19.1a: disc.json too, but only when a company page opens (loadDisc).
// 2026-11-08: a page brought back into view with stale data fetches the files once more (refetchNewer, returnWatch).
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

// opts.signal: stops the requests (refetchNewer's timeout, when a page whose first load failed comes back into view).
export async function loadAll(now, opts) {
  const o = opts && opts.signal ? { signal: opts.signal } : undefined;
  const [data, corp, macro] = await Promise.all([
    loadJson("./data.json", CHECKS.data, o),
    loadJson("./corp.json", CHECKS.corp, o),
    loadJson("./macro.json", CHECKS.macro, o),
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
// file has no staleAfter or one that cannot be read, the day count from publishedAt when nextPub is missing, and the US stocks priced at an earlier close (pxd), with counts. A pxd
// that cannot be read is its own warning: that stock shows its price with no date and no change. A readable staleAfter says
// nothing (console.warn only: nothing here writes to stdout, which the Node tests read).
export function logDates(d) {
  const sa = d.staleAfter;
  if (sa == null) console.warn("[v2] data.json staleAfter is missing or null: stale after " + STALE_DAYS + " days from publishedAt");
  else if (staleAfterTime(sa) == null) console.warn("[v2] data.json staleAfter cannot be read (" + JSON.stringify(sa) + "): stale after " + STALE_DAYS + " days from publishedAt");
  // A readable staleAfter without a readable nextPub: the warning still shows when staleAfter passes, but its day count n
  // counts from publishedAt, not from the morning the publish was due (data.js freshness).
  else if (!(typeof d.nextPub === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d.nextPub))) {
    console.warn("[v2] data.json nextPub is " + (d.nextPub == null ? "missing or null" : "not a YYYY-MM-DD date (" + JSON.stringify(d.nextPub) + ")")
      + ": once staleAfter passes, the day count of the warning counts from publishedAt, not from the due day");
  }
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
  const f = freshness(d.pxDate, d.publishedAt, "ko", t, d.staleAfter, d.nextPub);
  const o = load.fresh || {};
  const corpPub = load.corp && load.corp.publishedAt;
  const sameCorp = daysSince(corpPub, load.checkedAt) === daysSince(corpPub, t);
  if (f.stale === o.stale && f.days === o.days && f.md === o.md && !!f.due === !!o.due && sameCorp) return load;
  return { ...load, fresh: f, checkedAt: t };
}
// ms until the stale check can give another answer (data.js nextFreshChange: staleAfter, the next day of either publish
// time, at most an hour), or null (preview, loading, failed: nothing to re-check).
export function nextFreshCheck(load, now) {
  if (!load || load.status !== "ok" || load.preview) return null;
  return nextFreshChange(now, [load.data.publishedAt, load.corp && load.corp.publishedAt], load.data.staleAfter);
}

// ---- An old page brought back into view fetches the files once (Jack, 2026-11-08, Q9) ----
// "Old page brought back into view: yes, fetch once. If that fails, show the existing stale or failed message."
// Before this, a page left open (a home-screen app resumed days later) never fetched again: it said "N일째 갱신이 멈췄어요"
// until a reload, even when a newer publish was already on the site. A page whose first load failed also tries once more.

// Is the data on screen stale by the rule at this moment: data.json's (staleAfter passed, or the 4-day backstop; data.js
// freshness) or corp.json's 4-day rule (rules.js dayState reads it too). Never for the preview, a load in progress or a
// failed load (nothing loaded to be stale).
export function staleNow(load, now) {
  if (!load || load.status !== "ok" || load.preview) return false;
  const t = now == null ? Date.now() : now;
  const d = load.data;
  if (freshness(d.pxDate, d.publishedAt, "ko", t, d.staleAfter, d.nextPub).stale) return true;
  const corpDays = daysSince(load.corp && load.corp.publishedAt, t);
  return corpDays != null && corpDays > STALE_DAYS;
}

// Should a return to view fetch: the data on screen is stale (staleNow), or the first load failed (the load-failure
// message is on screen). Never on the preview page, never while the first load is still under way.
export const dueOnReturn = (load, now) => !!load && !load.preview && (load.status === "fail" || staleNow(load, now));

const pubMs = (j) => Date.parse((j && j.publishedAt) || "");
const nOf = (a) => (Array.isArray(a) ? a.length : 0);
const errText = (e) => String((e && e.message) || e);
// A fetch made when a page comes back into view gives up after this long: one budget for the whole fetch (every file it
// asks for, data.json first and then the others), not per request. A hung connection would otherwise keep every later
// return from fetching. The first load has no such limit.
export const REFETCH_TIMEOUT_MS = 60000;
// After a return's fetch that put nothing on screen (it failed, found no later publish, or found files from different
// publishes), the next return does not fetch for this long: GitHub Pages lets data.json be cached for 10 minutes
// (max-age=600), so a sooner fetch almost always gets the same copy.
export const REFETCH_GAP_MS = 10 * 60000;

// The files fetched again, the way loadAll fetches them (loadJson: no-store, NaN repair, the same CHECKS), all of them
// stopped once REFETCH_TIMEOUT_MS has passed since the fetch began (opts.timeoutMs for tests). now: for the new state's
// fresh (default: when the files arrived; app.jsx works it out again when the state goes on screen).
// cur: the load state on screen. discNow: the disc.json data on screen (the 공시 tab already loaded it), else null.
// - cur failed (the load-failure message): data.json, corp.json and macro.json through loadAll, with all its checks (macro.json
//   may fail, as on a first load). -> { ok: true, load, disc: null } when it loads, else { ok: false, why } and the failure
//   message stays.
// - cur loaded (stale): data.json first; when it fails or is not a later publish, nothing else is fetched (a site that
//   stopped publishing costs one file per return, not four). Otherwise corp.json and macro.json, and disc.json when discNow.
//   All of them or none: every file must load, pass its check and carry the same publishedAt (the pipeline writes one value
//   into all four and the publication gate checks it), later than the publish on screen. Stricter than a first load on
//   purpose: a macro.json that fails here keeps the data on screen (a first load would go on without it). Then
//   -> { ok: true, load, disc } (disc: the new disc.json data or null); anything else -> { ok: false, why } and the data on
//   screen stays as it is, with its stale line (a file that cannot be read never replaces readable data with the
//   load-failure message).
// The new state goes on screen through adoptLoad. Logged either way, with the counts or the reason.
export async function refetchNewer(cur, discNow, now, opts = {}) {
  const ms = opts.timeoutMs == null ? REFETCH_TIMEOUT_MS : opts.timeoutMs;
  const ctrl = typeof AbortController === "function" ? new AbortController() : null;
  const timer = ctrl ? setTimeout(() => ctrl.abort(new Error("no answer in " + Math.round(ms / 1000) + " s")), ms) : null;
  const o = ctrl ? { signal: ctrl.signal } : undefined;
  try {
    return cur && cur.status === "ok" ? await laterPublish(cur, discNow, now, o) : await retryFailed(cur, now, o);
  } finally {
    if (timer != null) clearTimeout(timer);
  }
}

async function retryFailed(cur, now, o) {
  const head = "[v2] back in view after a failed load";
  let next;
  try {
    next = await loadAll(now, o);
  } catch (e) {
    console.warn(head + ": the fetch of data.json, corp.json and macro.json stopped (" + errText(e) + "); the load-failure message stays");
    return { ok: false, why: errText(e) };
  } finally {
    setDataShape(cur && cur.data);                // the failure on screen reads no data: the shape waits for adoptLoad
  }
  if (!next || next.status !== "ok") {
    console.warn(head + ": fetched data.json, corp.json and macro.json once and they still cannot be used (the reason is logged above); the load-failure message stays");
    return { ok: false, why: "the files still cannot be used" };
  }
  const d = next.data;
  console.info(head + ": fetched data.json, corp.json and macro.json once; the publish of " + d.publishedAt + " (prices of " + d.pxDate
    + ") replaces the load-failure message: " + nOf(d.stocks) + " stocks, " + nOf(next.corp.companies) + " companies"
    + (next.macro ? "" : ", no macro.json") + (next.fresh.stale ? " (stale by its own rule: the stale line shows)" : ""));
  return { ok: true, load: next, disc: null };
}

async function laterPublish(cur, discNow, now, o) {
  const head = "[v2] back in view with stale data (published " + cur.data.publishedAt + ")";
  const keep = (fetched, why) => {
    console.warn(head + ": fetched " + fetched.join(", ") + " once and kept the data on screen (its stale line stays): " + why);
    return { ok: false, why };
  };
  // The publish times on screen (normally one: a first load during a deploy can have mixed them). A publish is later when it
  // is later than the oldest of them and not older than any (never a step back for a file already newer).
  const shown = [cur.data, cur.corp, cur.macro, discNow].map(pubMs).filter(Number.isFinite);
  const data = await loadJson("./data.json", CHECKS.data, o);
  if (!data.ok) return keep(["data.json"], "data.json: " + data.error);
  const p0 = pubMs(data.data);
  if (!(p0 > Math.min(...shown) && p0 >= Math.max(...shown))) {
    return keep(["data.json"], "no later publish on the site (data.json published " + data.data.publishedAt + ")");
  }
  const rest = ["corp", "macro"].concat(discNow ? ["disc"] : []);
  const got = await Promise.all(rest.map((n) => loadJson("./" + n + ".json", CHECKS[n], o)));
  const res = { data };
  rest.forEach((n, i) => { res[n] = got[i]; });
  const names = ["data"].concat(rest);
  const files = names.map((n) => n + ".json");
  const bad = names.filter((n) => !res[n].ok);
  if (bad.length) {
    return keep(files, bad.map((n) => n + ".json: " + res[n].error).join(" / ") + " (" + (names.length - bad.length) + " / " + names.length
      + " files loaded; none is used)");
  }
  if (names.some((n) => pubMs(res[n].data) !== p0)) {
    return keep(files, "the files are from different publishes (" + names.map((n) => n + ".json " + res[n].data.publishedAt).join(", ") + "); none is used");
  }
  const t = now == null ? Date.now() : now;
  let next;
  try {
    next = resolveLoad({ data, corp: res.corp, macro: res.macro }, t);
  } catch (e) {
    return keep(files, "the new files could not be read (" + errText(e) + "); none is used");
  } finally {
    // resolveLoad set the engine's data shape from the new data.json: it stays the shape of the data on screen until the
    // new state is put on screen (adoptLoad), so nothing on screen is ever read the other file's way.
    setDataShape(cur.data);
  }
  const d = next.data;
  console.info(head + ": fetched " + files.join(", ") + " once; a later publish, " + d.publishedAt + " (prices of " + d.pxDate
    + "), is ready for every screen: " + nOf(d.stocks) + " stocks, " + nOf(next.corp.companies) + " companies"
    + (res.disc ? ", " + nOf(res.disc.data.insider) + " insider and " + nOf(res.disc.data.nps) + " NPS disclosures" : "")
    + (next.fresh.stale ? " (stale by its own rule too: the stale line stays)" : ""));
  return { ok: true, load: next, disc: res.disc ? res.disc.data : null };
}

// The state refetchNewer returned, as it goes on screen: the engine reads the new data.json its own way from now on
// (engine.setDataShape, as resolveLoad does for a first load). -> the state to show.
export function adoptLoad(next) {
  setDataShape(next.data);
  return next;
}

// A one-line description of a fetched state for the console: "the publish of <time> (<n> stocks, <m> companies)".
export const publishText = (l) => (l && l.status === "ok"
  ? "the publish of " + l.data.publishedAt + " (" + nOf(l.data.stocks) + " stocks, " + nOf(l.corp && l.corp.companies) + " companies)" : "no data");

// One fetch per return to view. A return is visibilitychange to visible after the page was hidden (a page that starts
// hidden counts as hidden), or pageshow from the back-forward cache (persisted; the pagehide before it marks the page
// hidden). The events of one return fetch at most once between them (the first clears the mark), never while an earlier
// fetch is still out, and only when the return is due (dueOnReturn: stale data, or a failed first load). No retries of
// its own; and a return within REFETCH_GAP_MS after a fetch that put nothing on screen does not fetch (logged). Nor does
// one while a later publish already fetched is held back (held(now): its description, or null; app.jsx holds it under a
// draft; a held publish that is stale itself by now is dropped there and the return goes on under the usual rules).
// app.jsx feeds the events in; the preview page never sets this up (it fetches nothing).
//   hidden: the page is hidden now · getLoad(): the load state on screen · getDisc(): the disc.json data on screen or null ·
//   refetch(load, disc): refetchNewer · apply(result, load): what to do with the result (the load it was fetched for) ·
//   now(): the time · held(): see above (optional).
// -> { hide(), show() -> the fetch's promise or null when nothing was fetched, stop() }.
export function returnWatch({ hidden, getLoad, getDisc, refetch, apply, now, held }) {
  let away = !!hidden, busy = false, off = false, emptyAt = null;
  return {
    hide() { away = true; },
    show() {
      if (!away) return null;
      away = false;
      if (busy || off) return null;
      const cur = getLoad();
      const t = now();
      if (!dueOnReturn(cur, t)) return null;
      const what = cur.status === "ok" ? "with stale data" : "after a failed load";
      const waiting = held ? held(t) : null;
      if (waiting) {
        console.info("[v2] back in view " + what + ": nothing fetched; " + waiting + " is already waiting to go on screen");
        return null;
      }
      if (emptyAt != null && t - emptyAt < REFETCH_GAP_MS) {
        console.info("[v2] back in view " + what + ": nothing fetched; the last fetch on a return, " + Math.round((t - emptyAt) / 1000)
          + " s ago, put nothing on screen (the site keeps data.json for up to " + REFETCH_GAP_MS / 60000 + " minutes)");
        return null;
      }
      busy = true;
      return Promise.resolve()
        .then(() => refetch(cur, getDisc()))
        .catch((e) => {
          console.warn("[v2] back in view " + what + ": the fetch stopped (" + errText(e) + "); kept what is on screen");
          return { ok: false, why: errText(e) };
        })
        .then((r) => {
          busy = false;
          if (!r || !r.ok) emptyAt = now();
          if (!off) {
            try { apply(r, cur); } catch (e) { console.warn("[v2] back in view: the fetched files were not applied (" + errText(e) + ")"); }
          }
          return r;
        });
    },
    stop() { off = true; },
  };
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
  // The 4-day rule also stays as a backstop (data.js freshness). The day count n of the warning counts from the morning the
  // publish was due (nextPub; fresh.due), else from the last publish as before.
  const fresh = opts.preview ? { md: null, days: 0, stale: false } : freshness(d.pxDate, d.publishedAt, "ko", now, d.staleAfter, d.nextPub);
  if (!opts.preview) logDates(d);
  const byT = new Map(d.stocks.map((s) => [s.t, s]));
  const coByT = new Map(c.companies.map((x) => [x.t, x]));
  return { status: "ok", data: d, corp: c, macro: m, features, missing, fresh, byT, coByT, preview: !!opts.preview,
    cushion: opts.cushion || CUSHION_ASSETS, r2022: opts.r2022 || R2022, exact, checkedAt: now == null ? Date.now() : now };
}
