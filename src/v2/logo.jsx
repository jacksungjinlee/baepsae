// ================= Company marks (v19.1a Part G; logos v19.3a, docs/tasks/v19.3-portfolio-pictures-accounts.md Part J) =====
// Wherever 2.0 lists a company (the company page, 종목, 포트폴리오, 홈, 거래대금 상위, 왜 움직였나) it shows this mark.
// Every company first shows the fallback: a rounded square in one of ten fixed colours (company.js markColor, by the code)
// with the first letter of the name in white. The letter is drawn by CSS from data-initial (src/v2/template.html): a
// decoration, not text (aria-hidden). Never a grey placeholder, never a broken image, never a layout jump.
//
// Logos (v19.3a): our own files, on this site only (logos/, from the logos branch; no other site is ever asked). The live
// page (main.jsx) hands over its loader once (setLogoSource); the preview never does, so it shows letter marks only and
// asks for nothing. The index (logos/index.json) is fetched once, when the first mark is drawn. A company with an entry
// gets its picture lazily (loading="lazy") on top of the mark, in the same box, shown only once it has loaded. There is
// no timer: a picture below the fold simply loads when it is scrolled to. On any failure (no index, no entry, a file
// that does not load) the letter mark stays, and the console counts them.
import React, { useEffect, useState, useSyncExternalStore } from "react";
import { FONT, WEIGHT } from "../ui/tokens.js";
import { markColor, markLetter } from "./company.js";

export const LOGO_FILE_RX = /^[A-Za-z0-9][A-Za-z0-9._-]{0,23}\.(webp|png)$/;   // a plain file name in logos/, nothing else

const store = { load: null, dir: "", status: "off", logos: null, listeners: new Set(), snap: { status: "off", logos: null, dir: "" } };
const stats = { shown: new Set(), none: new Set(), failed: new Set(), timer: null, said: false };

function publish() {
  store.snap = { status: store.status, logos: store.logos, dir: store.dir };
  store.listeners.forEach((f) => f());
}

// load: () => Promise<{ ok, data, error }> (load.js loadLogoIndex); dir: where the files are ("./logos/"). Once.
export function setLogoSource(load, dir) {
  if (store.load || typeof load !== "function") return;
  store.load = load;
  store.dir = dir;
  store.status = "idle";
  publish();
}

function start() {
  if (store.status !== "idle") return;
  store.status = "loading";
  const fail = (why) => {
    store.status = "fail";
    console.warn(`[v2] company logos: logos/index.json not loaded (${why}): every company shows its letter mark`);
    publish();
  };
  Promise.resolve().then(() => store.load()).then((r) => {
    if (!r || !r.ok) return fail(r ? r.error : "no answer");
    store.logos = r.data.logos;
    store.status = "ok";
    console.info(`[v2] company logos: ${Object.keys(store.logos).length} companies have a logo file (logos/index.json)`);
    publish();
    return null;
  }, (e) => fail(String((e && e.message) || e)));
}

function subscribe(f) {
  store.listeners.add(f);
  start();
  return () => store.listeners.delete(f);
}
const snapshot = () => store.snap;

// The address of a company's logo file, or null (no index, no entry, or a file name that is not a plain picture name).
export function logoSrc(logos, dir, code) {
  if (!logos || !code || !Object.prototype.hasOwnProperty.call(logos, code)) return null;
  const e = logos[code];
  return e && typeof e.file === "string" && LOGO_FILE_RX.test(e.file) ? dir + e.file : null;
}

// Console counts: every company once per kind; a short summary after the marks settle.
function note(kind, code) {
  const set = stats[kind];
  if (!code || set.has(code)) return;
  set.add(code);
  if (kind === "failed") console.warn(`[v2] logo file failed for ${code}: letter mark instead · ${stats.failed.size} so far`);
  clearTimeout(stats.timer);
  stats.timer = setTimeout(() => console.info(`[v2] company logos: shown ${stats.shown.size} · letter marks: `
    + `no logo file ${stats.none.size} · file failed ${stats.failed.size}`), 1500);
}
export const logoStats = () => ({ shown: stats.shown.size, none: stats.none.size, failed: stats.failed.size, status: store.status });

function sayOff() {
  if (stats.said) return;
  stats.said = true;
  console.info("[v2] company logos: off on this page, every company shows its letter mark");
}

// s: the stock row (or { t, nk }); name: the name to take the letter from (defaults to s.nk). size in px.
export function CoMark({ s, t, name, size = 36 }) {
  const code = t || (s && s.t) || "";
  const nk = name || (s && s.nk) || code;
  const snap = useSyncExternalStore(subscribe, snapshot, snapshot);
  const src = snap.status === "ok" ? logoSrc(snap.logos, snap.dir, code) : null;
  const [img, setImg] = useState({ src: null, state: "wait" });      // per address: wait · shown · gone
  const state = src && img.src === src ? img.state : "wait";
  useEffect(() => { if (snap.status === "ok" && code && !src) note("none", code); }, [snap.status, src, code]);
  if (snap.status === "off") sayOff();
  const logo = !src ? (snap.status === "ok" ? "none" : snap.status) : state;
  const box = { width: size, height: size, borderRadius: Math.round(size * 0.28), flexShrink: 0, position: "relative", overflow: "hidden" };
  return (
    <span data-ui-v2="co-mark" data-t={code} data-logo={logo} aria-hidden="true" style={box}>
      <span data-initial={markLetter(nk, code)} style={{ position: "absolute", inset: 0, background: markColor(code), color: "#FFFFFF",
        display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT, fontWeight: WEIGHT.heavy,
        fontSize: Math.round(size * 0.44), lineHeight: 1, letterSpacing: 0 }} />
      {src && state !== "gone" && (
        <img key={src} src={src} alt="" loading="lazy" decoding="async" width={size} height={size}
          onLoad={() => { note("shown", code); setImg({ src, state: "shown" }); }}
          onError={() => { note("failed", code); setImg({ src, state: "gone" }); }}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", background: "#FFFFFF", opacity: state === "shown" ? 1 : 0 }} />
      )}
    </span>
  );
}
