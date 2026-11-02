// Browser storage for app.html: one versioned key; every read and write inside try/catch.
// Decks, rule books, purchase records and the answers to 확인 필요 (confirms) live only on this device (no login).
// Export/import is a JSON file. confirms, planFx (deck) and planPx (holding) are optional, so records saved before
// Part C still read the same; when present they must be valid or the whole file is refused.
// The preview page (app-preview.html) uses its own key so example records never mix with real ones.
export const STORE_KEY = "baepsae2.v1";
export const PREVIEW_STORE_KEY = "baepsae2.preview.v1";
export const STORE_VERSION = 1;

export const emptyStore = () => ({ v: STORE_VERSION, decks: [] });

// The current app (baepsae.html) keeps its portfolios under this key. 2.0 never reads their contents or changes them:
// it only checks whether any exist, to tell a returning visitor where to find them (Part F, Jack 2026-11-01).
export const OLD_APP_SLOTS_KEY = "baepsae_v10_slots";
export function hasOldAppRecords(get = (k) => localStorage.getItem(k)) {
  try {
    const a = JSON.parse(get(OLD_APP_SLOTS_KEY) || "[]");
    return Array.isArray(a) && a.length > 0;
  } catch (e) { return false; }
}

const isStr = (x, max = 200) => typeof x === "string" && x.length > 0 && x.length <= max;
const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const isDate = (x) => typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x) && !Number.isNaN(Date.parse(x + "T00:00:00Z"))
  && new Date(x + "T00:00:00Z").toISOString().slice(0, 10) === x;

// Every field the app reads back is checked. One bad field rejects the whole file (nothing is stored).
export function validStore(d, today) {
  if (!d || typeof d !== "object" || Array.isArray(d) || d.v !== STORE_VERSION || !Array.isArray(d.decks)) return false;
  const ids = new Set();
  for (const x of d.decks) {
    if (!x || typeof x !== "object" || !isStr(x.id, 60) || ids.has(x.id) || !isStr(x.name, 60)) return false;
    ids.add(x.id);
    if (x.createdAt != null && !isDate(x.createdAt)) return false;
    if (x.planFx != null && !(isNum(x.planFx) && x.planFx > 0)) return false;           // the USD/KRW rate the plan used
    if (!Array.isArray(x.holdings) || !Array.isArray(x.purchases)) return false;
    for (const h of x.holdings) {
      if (!h || typeof h !== "object" || !isStr(h.t, 20) || !isStr(h.nk, 120)) return false;
      if (h.target != null && !(isNum(h.target) && h.target >= 0 && h.target <= 1)) return false;
      if (h.plannedQty != null && !(Number.isInteger(h.plannedQty) && h.plannedQty >= 0)) return false;
      if (h.planPx != null && !(isNum(h.planPx) && h.planPx > 0)) return false;          // the price the plan used
      if (h.rules != null && !Array.isArray(h.rules)) return false;
    }
    for (const p of x.purchases) {
      if (!p || typeof p !== "object" || !isStr(p.t, 20)) return false;
      if (!(Number.isInteger(p.qty) && p.qty > 0)) return false;
      if (!(isNum(p.price) && p.price > 0)) return false;
      if (!isDate(p.date) || (today && p.date > today)) return false;
      if (p.ccy !== "KRW" && p.ccy !== "USD") return false;
      if (!x.holdings.some((h) => h.t === p.t)) return false;
    }
    if (x.confirms != null) {
      if (!Array.isArray(x.confirms)) return false;
      for (const c of x.confirms) if (!validConfirm(c, today) || !x.holdings.some((h) => h.t === c.t)) return false;
    }
  }
  return true;
}

// ---------------- 확인 필요: the user's answers (v18.3 Part C) ----------------
// A dividend drop is never 규칙 깨짐 on its own: the user answers 실제로 줄였어요 ("cut": the sell condition fired) or
// 줄인 게 아니에요 ("notCut": cleared). The answer is stored in the deck record as { t, rule, fy, a, b, answer, at }:
// it covers only that report year and those two numbers (주당 a원 -> b원), so a later, newer cut is asked about again,
// and so is the same report if its numbers change.
export const CONFIRM_ANSWERS = ["cut", "notCut"];
export const sameConfirm = (x, y) => !!(x && y && x.t === y.t && x.rule === y.rule && x.fy === y.fy && x.a === y.a && x.b === y.b);

function validConfirm(c, today) {
  return !!(c && typeof c === "object" && !Array.isArray(c) && isStr(c.t, 20) && c.rule === "divCut" && Number.isInteger(c.fy)
    && isNum(c.a) && isNum(c.b) && c.b >= 0 && c.b < c.a && CONFIRM_ANSWERS.includes(c.answer) && isDate(c.at) && !(today && c.at > today));
}

// The store with one answer recorded (it replaces an earlier answer for the same item). Pure: the caller saves it.
// Returns null when the item, the answer or the deck is not valid (nothing to save).
export function withConfirm(data, deckId, item, answer, today) {
  const c = { t: item && item.t, rule: item && item.rule, fy: item && item.fy, a: item && item.a, b: item && item.b, answer, at: today };
  if (!validConfirm(c, today)) return null;
  const deck = data.decks.find((d) => d.id === deckId);
  if (!deck || !deck.holdings.some((h) => h.t === c.t)) return null;
  const confirms = [...(deck.confirms || []).filter((x) => !sameConfirm(x, c)), c];
  return { ...data, decks: data.decks.map((d) => (d.id === deckId ? { ...d, confirms } : d)) };
}

// { data, writable, locked }: locked = something unreadable is stored under the key. It stays untouched; the first
// write moves it to a backup key first (see writeStore), so 기록 불러오기 and 샀어요 still work.
export function readStore(key = STORE_KEY, today) {
  let writable = false;
  try {
    const k = key + ".probe";
    localStorage.setItem(k, "1");
    localStorage.removeItem(k);
    writable = true;
  } catch (e) { writable = false; }
  let raw = null;
  try { raw = localStorage.getItem(key); } catch (e) { return { data: emptyStore(), writable: false, locked: false }; }
  if (raw == null) return { data: emptyStore(), writable, locked: false };
  try {
    const d = JSON.parse(raw);
    if (validStore(d, today)) return { data: d, writable, locked: false };
  } catch (e) { /* unreadable */ }
  console.warn("[v2] stored records are in an unknown format; kept as they are");
  return { data: emptyStore(), writable, locked: true };
}

// Before overwriting, the stored blob is checked exactly like readStore does (with today's date); anything it would
// reject on read is first copied to a backup key, so nothing unreadable is ever lost.
export function writeStore(d, key = STORE_KEY, today) {
  try {
    const cur = localStorage.getItem(key);
    if (cur != null) {
      let ok = false;
      try { ok = validStore(JSON.parse(cur), today); } catch (e) { ok = false; }
      if (!ok) localStorage.setItem(`${key}.unreadable.${Date.now()}`, cur);   // keep what we could not read
    }
    localStorage.setItem(key, JSON.stringify(d));
    return true;
  } catch (e) {
    console.warn("[v2] could not save records: " + ((e && e.message) || e));
    return false;
  }
}

export function askPersist() {
  try {
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
  } catch (e) { /* not supported */ }
}

// preview: the page importing. A preview export (example data) never goes into the live app, and a live export never
// goes into the preview: the file's own "preview" flag must match.
export function parseImport(text, today, preview = false) {
  try {
    const d = JSON.parse(text);
    if (!!(d && d.preview) !== !!preview) return null;
    return validStore(d, today) ? { v: STORE_VERSION, decks: d.decks } : null;
  } catch (e) {
    return null;
  }
}

// Imported decks replace decks with the same id; other decks are kept.
export function mergeStores(cur, inc) {
  const by = new Map(cur.decks.map((x) => [x.id, x]));
  for (const x of inc.decks) by.set(x.id, x);
  return { v: STORE_VERSION, decks: [...by.values()] };
}

export function exportText(d, preview = false) {
  return JSON.stringify(preview ? { v: STORE_VERSION, preview: true, decks: d.decks } : { v: STORE_VERSION, decks: d.decks }, null, 1);
}

export function downloadRecords(d, today, prefix = "baepsae-records", preview = false) {
  try {
    const blob = new Blob([exportText(d, preview)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${prefix}-${today}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  } catch (e) {
    console.warn("[v2] export failed: " + ((e && e.message) || e));
    return false;
  }
}

// Safari (and every iOS browser, all WebKit) may clear site storage after 7 days without a visit.
export function isSafariLike(nav) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  const ua = n.userAgent || "";
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && (n.maxTouchPoints || 0) > 1);
  const safari = /Safari\//.test(ua) && !/Chrome|Chromium|CriOS|FxiOS|EdgiOS|Edg\/|Android/.test(ua);
  return ios || safari;
}
