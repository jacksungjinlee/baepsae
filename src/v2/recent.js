// 최근 본 종목 (v19.0c, 종목 tab): the stocks tapped last, newest first, up to 8, kept in this browser only (a per-viewer
// convenience: losing it loses nothing). Its own key per page (the preview keeps its own); every read and write inside
// try/catch, and anything that is not a short list of codes reads as empty.
export const RECENT_KEY = "baepsae2.recent.v1";
export const PREVIEW_RECENT_KEY = "baepsae2.preview.recent.v1";
export const RECENT_MAX = 8;

const okCode = (t) => typeof t === "string" && t.length > 0 && t.length <= 20;

export function readRecent(key = RECENT_KEY) {
  try {
    const a = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(a) ? a.filter(okCode).slice(0, RECENT_MAX) : [];
  } catch (e) { return []; }
}

// -> the new list (also when it could not be saved)
export function addRecent(t, key = RECENT_KEY) {
  const next = [t, ...readRecent(key).filter((x) => x !== t)].filter(okCode).slice(0, RECENT_MAX);
  try { localStorage.setItem(key, JSON.stringify(next)); } catch (e) { console.warn("[v2] recently viewed not saved: " + ((e && e.message) || e)); }
  return next;
}
