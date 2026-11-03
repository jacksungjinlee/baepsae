// 2.0 addresses (v19.0c): the four tab routes, 소개, the two sub-screens, and the old app's screens 2.0 links to.
// Pure: no React, no Korean. src/v2/nav.jsx does the history work. Unit tests: tests/test_v2_nav.py.

// The current app (예전 뱁새). Part F: the main address shows 2.0; the old app stays reachable from 2.0.
export const OLD_APP = "./baepsae.html";

export const TABS = ["home", "portfolio", "stocks", "market"];
const SUBS = { home: ["why"], portfolio: ["build"] };
export const ABOUT_ROUTE = "#about";

// The old app's screens 2.0 opens (src/deeplink.js reads them once on load in the old app, then clears them).
export const OLD_LINKS = {
  macro: OLD_APP + "#macro",
  disc: OLD_APP + "#disc",
  glossary: OLD_APP + "#info=glossary",
  sources: OLD_APP + "#info=sources",
  corp: (t) => OLD_APP + "#corp=" + encodeURIComponent(String(t)),
};

// "#portfolio/build" -> { tab: "portfolio", sub: "build", about: false, known: true }. No hash: empty (shown as #home).
export function parseHash(hash) {
  const raw = String(hash || "").replace(/^#/, "");
  if (!raw) return { tab: "home", sub: null, about: false, known: false, empty: true };
  if (raw === "about") return { tab: null, sub: null, about: true, known: true };
  const parts = raw.split("/");
  const [tab, sub] = parts;
  if (TABS.includes(tab) && parts.length <= 2 && (sub == null || (SUBS[tab] || []).includes(sub))) {
    return { tab, sub: sub || null, about: false, known: true };
  }
  return { tab: "home", sub: null, about: false, known: false };
}
export const hashOf = (tab, sub) => "#" + tab + (sub ? "/" + sub : "");
