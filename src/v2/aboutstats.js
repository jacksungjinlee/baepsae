// 소개 page figures (v19.0 Part D, rule in docs/design/v19/copy/about.md): computed from the loaded data.json, never typed in.
//   stocks covered = stocks whose cls is "kr" or "us" (ETFs included, as about.md says);
//   industry groups = distinct `ind` values among them, leaving out blank and the catch-all ids (engine.js hasGroup);
//   n = stocks covered rounded down to the hundred, for the sentence "{n}개가 넘는" (3,256 -> 3,200).
import { hasGroup } from "./engine.js";

// data: the data.json object. Returns null when there is no stock to count; n is null below 100 (the sentence would say
// "more than 0").
export function aboutStats(data) {
  const stocks = data && Array.isArray(data.stocks) ? data.stocks : null;
  if (!stocks) return null;
  const covered = stocks.filter((s) => s && (s.cls === "kr" || s.cls === "us"));
  if (!covered.length) return null;
  const groups = new Set(covered.filter(hasGroup).map((s) => s.ind));
  const n = Math.floor(covered.length / 100) * 100;
  return { count: covered.length, groups: groups.size, n: n > 0 ? n : null };
}

// What the 소개 page shows, from the app's load state (src/v2/load.js):
//   live data, fresh -> the figures row, and the sentence with n;
//   live data, stale (the same check as the date line: publication stopped for more than 4 days) -> no figures row (its
//     "every trading day" would not be true), the sentence keeps n (a count of stocks does not go out of date);
//   loading, failed, or the preview's fictional data -> no figures row and no sentence with a number.
export function aboutView(load) {
  const none = { figures: null, n: null };
  if (!load || load.status !== "ok" || load.preview) return none;
  const st = aboutStats(load.data);
  if (!st) return none;
  const stale = !!(load.fresh && load.fresh.stale);
  return { figures: stale ? null : st, n: st.n };
}
