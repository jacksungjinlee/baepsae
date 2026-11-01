// Browser storage for app.html: one versioned key; every read and write inside try/catch.
// Decks, rule books and purchase records live only on this device (no login). Export/import is a JSON file.
export const STORE_KEY = "baepsae2.v1";
export const STORE_VERSION = 1;

export const emptyStore = () => ({ v: STORE_VERSION, decks: [] });

export function validStore(d) {
  return !!(d && typeof d === "object" && d.v === STORE_VERSION && Array.isArray(d.decks)
    && d.decks.every((x) => x && typeof x.id === "string" && Array.isArray(x.holdings) && Array.isArray(x.purchases)));
}

// { data, writable, locked }: locked = something unreadable is stored under the key; we never overwrite it.
export function readStore() {
  let writable = false;
  try {
    const k = STORE_KEY + ".probe";
    localStorage.setItem(k, "1");
    localStorage.removeItem(k);
    writable = true;
  } catch (e) { writable = false; }
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw == null) return { data: emptyStore(), writable, locked: false };
    const d = JSON.parse(raw);
    if (validStore(d)) return { data: d, writable, locked: false };
    console.warn("[v2] stored records are in an unknown format; left untouched");
    return { data: emptyStore(), writable: false, locked: true };
  } catch (e) {
    return { data: emptyStore(), writable: false, locked: writable };
  }
}

export function writeStore(d) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(d));
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

export function parseImport(text) {
  try {
    const d = JSON.parse(text);
    return validStore(d) ? { v: STORE_VERSION, decks: d.decks } : null;
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

export function exportText(d) {
  return JSON.stringify({ v: STORE_VERSION, decks: d.decks }, null, 1);
}

export function downloadRecords(d, today) {
  try {
    const blob = new Blob([exportText(d)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `baepsae-records-${today}.json`;
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
