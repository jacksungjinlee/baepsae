// 2.0 addresses (v19.0c): the four tab routes, 소개, the two sub-screens, and the old app's screens 2.0 links to.
// Pure: no React, no Korean. src/v2/nav.jsx does the history work. Unit tests: tests/test_v2_lists.py.

// The current app (예전 뱁새). Part F: the main address shows 2.0; the old app stays reachable from 2.0.
// The address carries the 2.0 marker (?from=app, src/links.js): baepsae.html without it (and without a #) goes to 2.0.
import { OLD_APP } from "../links.js";
export { OLD_APP };

export const TABS = ["home", "portfolio", "stocks", "market"];
const SUBS = { home: ["why"], portfolio: ["build", "import"] };   // v19.3d: #portfolio/import (가진 종목 넣기)
// v19.3d2: 내 규칙 정하기 of one portfolio, #portfolio/rules/<deck id> (ids as 2.0 makes them: letters, digits, "_" "-")
export const DECK_ID_RX = /^[A-Za-z0-9_-]{1,60}$/;
export const ABOUT_ROUTE = "#about";

// v19.1a company page (#stocks/<code>[/<tab>]): the tabs after 요약, and the 자세히 screens (layer 3).
export const CO_TABS = ["earn", "value", "div", "disc"];
export const CO_MORE = ["value-more", "earn-more"];
// A Korean 6-digit code or a US ticker as data.json writes them (upper case, digits, "." or "-"). Anything else is not a
// company address (the router shows #home for it); whether the company exists is the page's business (it says so).
export const CODE_RX = /^[0-9A-Z][0-9A-Z.-]{0,14}$/;
export const okCode = (t) => typeof t === "string" && CODE_RX.test(t);

// The old app's screens 2.0 opens (src/deeplink.js reads them once on load in the old app, then clears them).
// v19.1a: corp (기업분석) is no longer opened from 2.0: every company opens the 2.0 company page (#stocks/<code>). The
// link stays defined for the old app's own deep link (src/deeplink.js), which 예전 뱁새 보기 still reaches.
export const OLD_LINKS = {
  macro: OLD_APP + "#macro",
  disc: OLD_APP + "#disc",
  glossary: OLD_APP + "#info=glossary",
  sources: OLD_APP + "#info=sources",
  corp: (t) => OLD_APP + "#corp=" + encodeURIComponent(String(t)),
};

// v19.1a 공시 tab (Jack, 2026-11-05): each row links to that one filing in DART's own viewer by its exact receipt number
// (disc.json "rc", rcept_no: 14 digits). A row without an exact number (the pipeline's fallback key "date|name", or
// anything else) gets no link: never a search or a name-based link. This is the only DART address in 2.0, and it is used
// only as <a href target="_blank" rel="noopener"> (tests/test_v2_app.py: no fetch, image or script ever goes there).
export const DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=";
export const RCEPT_RX = /^\d{14}$/;
export const dartFilingUrl = (rc) => (typeof rc === "string" && RCEPT_RX.test(rc) ? DART_VIEWER + rc : null);

// "#portfolio/build" -> { tab: "portfolio", sub: "build", about: false, known: true }. No hash: empty (shown as #home).
// v19.1a: a company page lives under 종목: "#stocks/005930" (요약) and "#stocks/005930/value" (a tab, or a 자세히 screen):
// { tab: "stocks", sub: "005930/value", about: false, known: true, code: "005930", ctab: "value" }. The code must look
// like a data.json code (company.js CODE_RX); whether the company exists is the page's business (it says so).
export function parseHash(hash) {
  const raw = String(hash || "").replace(/^#/, "");
  if (!raw) return { tab: "home", sub: null, about: false, known: false, empty: true };
  if (raw === "about") return { tab: null, sub: null, about: true, known: true };
  const parts = raw.split("/");
  const [tab, sub] = parts;
  if (TABS.includes(tab) && parts.length <= 2 && (sub == null || (SUBS[tab] || []).includes(sub))) {
    return { tab, sub: sub || null, about: false, known: true };
  }
  if (tab === "portfolio" && parts.length === 3 && parts[1] === "rules" && DECK_ID_RX.test(parts[2])) {
    return { tab: "portfolio", sub: "rules/" + parts[2], about: false, known: true, rules: parts[2] };
  }
  // v19.7a: 종목 바꾸기 of one portfolio, #portfolio/edit/<deck id>
  if (tab === "portfolio" && parts.length === 3 && parts[1] === "edit" && DECK_ID_RX.test(parts[2])) {
    return { tab: "portfolio", sub: "edit/" + parts[2], about: false, known: true, edit: parts[2] };
  }
  // v19.6a: 내 수익 of one portfolio, #portfolio/returns/<deck id>
  if (tab === "portfolio" && parts.length === 3 && parts[1] === "returns" && DECK_ID_RX.test(parts[2])) {
    return { tab: "portfolio", sub: "returns/" + parts[2], about: false, known: true, returns: parts[2] };
  }
  if (tab === "stocks" && (parts.length === 2 || parts.length === 3)) {
    let code = null;
    try { code = decodeURIComponent(parts[1]); } catch (e) { code = null; }
    const ctab = parts[2] || null;
    if (okCode(code) && (ctab == null || CO_TABS.includes(ctab) || CO_MORE.includes(ctab))) {
      return { tab: "stocks", sub: companySub(code, ctab), about: false, known: true, code, ctab };
    }
  }
  return { tab: "home", sub: null, about: false, known: false };
}
export const hashOf = (tab, sub) => "#" + tab + (sub ? "/" + sub : "");
// The sub part of a company address (encoded for the hash: US tickers may hold "." or "-", both safe, but stay explicit).
export const companySub = (code, ctab) => encodeURIComponent(String(code)) + (ctab ? "/" + ctab : "");
