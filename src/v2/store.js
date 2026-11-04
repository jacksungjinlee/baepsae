// Browser storage for app.html: one versioned key; every read and write inside try/catch.
// Portfolios ("decks" in the code), rule books, purchase records and the answers to 확인 필요 (confirms) live only on
// this device (no login).
// Export/import is a JSON file. confirms, planFx (deck) and planPx (holding) are optional, so records saved before
// Part C still read the same; when present they must be valid or the whole file is refused.
// v19.1a: two more optional parts, per stock (any stock, held or not): notes (내 메모: { [code]: { text, at } }) and
// assume (가치 자세히 · 이 가정 저장하기: { [code]: { disc, term, at } }). Same rule: absent is fine, present must be valid.
// The preview page (app-preview.html) uses its own key so example records never mix with real ones.
import { okAssume } from "./dcf.js";

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
      // Part E: a US purchase carries the won-per-dollar rate the plan used (for 원금 in won). Optional, so earlier records
      // still read; when present it must be a positive number on a USD purchase.
      if (p.fx != null && !(p.ccy === "USD" && isNum(p.fx) && p.fx > 0)) return false;
      if (!x.holdings.some((h) => h.t === p.t)) return false;
    }
    if (x.confirms != null) {
      if (!Array.isArray(x.confirms)) return false;
      for (const c of x.confirms) if (!validConfirm(c, today) || !x.holdings.some((h) => h.t === c.t)) return false;
    }
  }
  if (d.notes != null && !validPerStock(d.notes, (n) => typeof n.text === "string" && n.text.length > 0 && n.text.length <= NOTE_MAX, today)) return false;
  if (d.assume != null && !validPerStock(d.assume, (a) => okAssume(a), today)) return false;
  return true;
}

// ---------------- per stock: 내 메모 and saved assumptions (v19.1a Part E, Part D) ----------------
export const NOTE_MAX = 500;
const plainObj = (x) => !!x && typeof x === "object" && !Array.isArray(x);
const okStockCode = (t) => isStr(t, 20) && /^[0-9A-Za-z][0-9A-Za-z.-]*$/.test(t);
function validPerStock(m, ok, today) {
  if (!plainObj(m)) return false;
  for (const [t, v] of Object.entries(m)) {
    if (!okStockCode(t) || !plainObj(v) || !isDate(v.at) || (today && v.at > today) || !ok(v)) return false;
  }
  return true;
}
const perStock = (d, key) => (d && plainObj(d[key]) ? d[key] : null);

// The store with this stock's note set (text trimmed; empty text removes the note). Pure: the caller saves it.
// null = nothing valid to save (too long, a bad code or date).
export function withNote(data, t, text, today) {
  if (!okStockCode(t) || !isDate(today) || typeof text !== "string") return null;
  const v = text.trim();
  if (v.length > NOTE_MAX) return null;
  const notes = { ...(perStock(data, "notes") || {}) };
  if (v) notes[t] = { text: v, at: today }; else delete notes[t];
  const { notes: _n, ...rest } = data || {};
  return Object.keys(notes).length ? { ...rest, notes } : rest;
}

// The store with this stock's 가치 자세히 assumption (discount rate and 5년 뒤 성장률, the calculator's own ranges).
export function withAssume(data, t, a, today) {
  if (!okStockCode(t) || !isDate(today) || !okAssume(a)) return null;
  return { ...data, assume: { ...(perStock(data, "assume") || {}), [t]: { disc: a.disc, term: a.term, at: today } } };
}
export const noteOf = (data, t) => { const n = perStock(data, "notes"); return n && plainObj(n[t]) ? n[t] : null; };
export const assumeOf = (data, t) => { const a = perStock(data, "assume"); return a && plainObj(a[t]) && okAssume(a[t]) ? a[t] : null; };
const extras = (d) => ({ ...(perStock(d, "notes") ? { notes: d.notes } : {}), ...(perStock(d, "assume") ? { assume: d.assume } : {}) });

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

// 포트폴리오에서 빼기 (v19.0c): the store without one stock of one portfolio — its holding, its purchases and its
// answers to 확인 필요. Pure: the caller saves it, and only when the user tapped the button (the screen offers it only
// for a stock missing from today's data). The portfolio itself stays, even with no stock left. null = nothing to remove.
export function withoutHolding(data, deckId, t) {
  const deck = data && Array.isArray(data.decks) ? data.decks.find((d) => d && d.id === deckId) : null;
  if (!deck || typeof t !== "string" || !deck.holdings.some((h) => h && h.t === t)) return null;
  const next = { ...deck, holdings: deck.holdings.filter((h) => h.t !== t), purchases: deck.purchases.filter((p) => p.t !== t),
    ...(Array.isArray(deck.confirms) ? { confirms: deck.confirms.filter((c) => c.t !== t) } : {}) };
  return { ...data, decks: data.decks.map((d) => (d.id === deckId ? next : d)) };
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
    return validStore(d, today) ? { v: STORE_VERSION, decks: d.decks, ...extras(d) } : null;
  } catch (e) {
    return null;
  }
}

// Why a file cannot be imported here (null = it can):
//   "preview" = a preview export (example data) opened in the live app -> store.otherKind;
//   "live"    = a live export opened in the preview page -> the plain 기록 불러오기 warning chip (no sentence for it);
//   "bad"     = not a records file, or one bad field -> store.importFail.
export function importProblem(text, today, preview = false) {
  let d;
  try { d = JSON.parse(text); } catch (e) { return "bad"; }
  if (!d || typeof d !== "object" || Array.isArray(d)) return "bad";
  if (!!d.preview !== !!preview) return d.preview ? "preview" : "live";
  return validStore(d, today) ? null : "bad";
}

// Imported decks replace decks with the same id; other decks are kept. Notes and assumptions the same way, per stock.
export function mergeStores(cur, inc) {
  const by = new Map(cur.decks.map((x) => [x.id, x]));
  for (const x of inc.decks) by.set(x.id, x);
  const out = { v: STORE_VERSION, decks: [...by.values()] };
  for (const key of ["notes", "assume"]) {
    const m = { ...(perStock(cur, key) || {}), ...(perStock(inc, key) || {}) };
    if (Object.keys(m).length) out[key] = m;
  }
  return out;
}

export function exportText(d, preview = false) {
  return JSON.stringify(preview ? { v: STORE_VERSION, preview: true, decks: d.decks, ...extras(d) } : { v: STORE_VERSION, decks: d.decks, ...extras(d) }, null, 1);
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
    setTimeout(() => URL.revokeObjectURL(url), 60000);   // early revoke can fail the download on iOS Safari ("WebKitBlobResource error 1")
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

// iPhone Safari itself (v19.0c home-screen hint), never inside the app added to the home screen: on iPhone the records
// live in Safari's storage and the home-screen app has storage of its own, so moving them takes 기록 내보내기 → 기록
// 불러오기. Other iPhone browsers and in-app browsers (KakaoTalk, NAVER …) lack Safari's "Version/… Safari/" pair or
// name themselves; iPad is left out. standalone: the display-mode media query (null = ask the browser).
const NOT_SAFARI = /CriOS|FxiOS|EdgiOS|OPiOS|OPT\/|GSA\/|KAKAOTALK|NAVER|Line\/|FBAN|FBAV|Instagram|DaumApps|Whale|DuckDuckGo/i;
export function iphoneSafari(nav, standalone = null) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  const ua = n.userAgent || "";
  if (!/\((iPhone|iPod)[;\s]/.test(ua) || !/Version\/[\d.]+ .*Safari\//.test(ua) || NOT_SAFARI.test(ua)) return false;
  if (n.standalone === true) return false;
  let sa = standalone;
  if (sa == null) {
    try { sa = typeof window !== "undefined" && !!window.matchMedia && window.matchMedia("(display-mode: standalone)").matches; } catch (e) { sa = false; }
  }
  return !sa;
}
