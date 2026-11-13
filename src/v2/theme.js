// ================= 화면 모드 (v19.6d, docs/tasks/v19.6-records-alerts-dark.md Part D) =================
// ☰ menu (and the PC left menu) → 화면 모드: 자동 · 밝게 · 어둡게. 자동 (the default) follows the device
// (prefers-color-scheme) and follows it live when the device switches. The choice is a per-device convenience: it lives in
// localStorage under its own key (never in the records, never in the export file, never synced), read and written inside
// try/catch. Storage that is blocked or holds anything else reads as 자동, without an error.
//
// One function applies a mode: bootTheme. build-app.sh puts its source text, called with the key and the two page
// colours, in app.html's <head> (themeHeadScript), so the first paint already has the right colours; the app calls the same
// function whenever the mode changes. It sets <html data-theme="light|dark"> (the colour sheet in tokens.js themeCss
// switches every token on it, color-scheme included), <html data-theme-mode="auto|light|dark"> and the theme-color meta
// (the browser bar's colour: the page colour of the theme in use). It is written in old-style JavaScript on purpose: it runs
// in the head as esbuild prints it (whitespace removed, nothing renamed).
// The head script's hash goes into the page's Content-Security-Policy when v19.4 adds one (v19.3 Part O): build-app.sh
// prints it, and tests/test_v196d_dark.py checks that any CSP on app.html lists it.
import { THEME_COLOR } from "../ui/tokens.js";

export { themeCss } from "../ui/tokens.js";      // for build-app.sh (the colour sheet in app.html's <style>)

export const THEME_KEY = "baepsae-theme";
export const MODES = ["auto", "light", "dark"];

/* eslint-disable no-var */
export function bootTheme(key, light, dark, pick) {
  var mode = pick, theme = "light", root = document.documentElement, meta;
  if (mode === undefined) { try { mode = window.localStorage.getItem(key); } catch (e) { mode = null; } }
  if (mode !== "light" && mode !== "dark") {
    mode = "auto";
    try { theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch (e) { theme = "light"; }
  } else {
    theme = mode;
  }
  root.setAttribute("data-theme", theme);
  root.setAttribute("data-theme-mode", mode);
  meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? dark : light);
  return theme;
}
/* eslint-enable no-var */

// The <script> body for the page head (build-app.sh): the function above, called once with the stored choice.
export function themeHeadScript() {
  return `(${bootTheme.toString()})(${JSON.stringify(THEME_KEY)},${JSON.stringify(THEME_COLOR.light)},${JSON.stringify(THEME_COLOR.dark)});`;
}

// The stored choice ("auto" when there is none, storage is blocked, or it holds something else).
export function readMode() {
  let v = null;
  try { v = window.localStorage.getItem(THEME_KEY); } catch (e) { v = null; }
  return MODES.includes(v) ? v : "auto";
}

// Keep the choice on this device. 자동 removes the key (the default needs no record). Blocked storage: the choice holds
// for this visit only, quietly (it is a convenience, not a record).
export function saveMode(mode) {
  try {
    if (mode === "auto") window.localStorage.removeItem(THEME_KEY);
    else window.localStorage.setItem(THEME_KEY, mode);
    return true;
  } catch (e) { return false; }
}

export function applyMode(mode) {
  try { return bootTheme(THEME_KEY, THEME_COLOR.light, THEME_COLOR.dark, MODES.includes(mode) ? mode : "auto"); } catch (e) { return "light"; }
}

// Under 자동: call back whenever the device switches between light and dark. Returns the function that stops it.
export function onDeviceChange(cb) {
  let mq = null;
  try { mq = window.matchMedia("(prefers-color-scheme: dark)"); } catch (e) { mq = null; }
  if (!mq) return () => {};
  if (mq.addEventListener) { mq.addEventListener("change", cb); return () => mq.removeEventListener("change", cb); }
  if (mq.addListener) { mq.addListener(cb); return () => mq.removeListener(cb); }
  return () => {};
}
