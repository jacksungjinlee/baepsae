// ================= 뱁새 2.0 navigation (v19.0c, Layout C phone) =================
// Four tabs 홈 · 포트폴리오 · 종목 · 시장 with hash routes #home #portfolio #stocks #market, plus #about (소개) and two
// sub-screens: 포트폴리오 만들기 (#portfolio/build) and 왜 움직였나 (#home/why, which needs its target in memory: loaded on
// its own it falls back to #home). No hash (or a hash this page does not know) -> #home, in place (no new history entry).
//
// History: every in-page move pushes one entry (history.pushState) and every entry this page made carries its depth
// ({ v2: n }), so the phone's back button walks back through tabs, 소개 and sub-screens (popstate · hashchange). A link
// inside the page (the footer's 소개 link) makes an entry without a depth: the next event gives it one. The ☰ menu is an
// entry of its own on top of the screen it covers ({ v2: n, v2menu: 1 }, same address), so back closes it; a choice in
// the menu replaces that entry, so back from the chosen screen returns to the screen under the menu.
// Leaving a sub-screen or 소개 ("back"): one step back when the entry before is this page's own (depth > 0); 소개 opened
// straight from another page of this site (the old app's footer) also goes one step back to that page; otherwise (a
// shared link, a bookmark) the fallback route replaces the current entry.
// The menu links into the old app (예전 뱁새, baepsae.html) open its screens through the deep links it reads once on load
// and then clears (src/deeplink.js, src/shell.jsx: #macro · #disc · #corp=CODE · #info=glossary|sources; routes.js
// OLD_LINKS). The preview page (fictional data) has no link into the old app: its menu shows 소개 and the data date only.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, SELECTED } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { BottomTabBar } from "../ui/components.jsx";
import { C, fill, mdText } from "./format.js";
import { DateLine, Note, IMG, SampleLabel, SIDE_W, PC_PAD, PcFrame, tx, tap, useMode } from "./ui.jsx";
import { TABS, OLD_APP, OLD_LINKS, ABOUT_ROUTE, parseHash, hashOf } from "./routes.js";

export { TABS, OLD_LINKS, parseHash, hashOf };
export const TAB_ICON = { home: "house", portfolio: "chart-pie-slice", stocks: "buildings", market: "chart-line-up" };

const stateNow = () => {
  try { const s = window.history.state; return s && typeof s === "object" ? s : null; } catch (e) { return null; }
};
const depthOf = (s) => (s && Number.isInteger(s.v2) && s.v2 >= 0 ? s.v2 : null);
const here = () => {
  try { return window.location.pathname + window.location.search; } catch (e) { return ""; }
};
const replace = (state, hash) => {
  try { window.history.replaceState(state, "", hash != null ? here() + hash : undefined); return true; } catch (e) { return false; }
};
const push = (state, hash) => {
  try { window.history.pushState(state, "", hash != null ? here() + hash : undefined); return true; } catch (e) { return false; }
};
const toTop = () => {
  try { window.scrollTo(0, 0); } catch (e) { /* ignore */ }
};
// Opened straight at app.html#about from another page of this site (the old app's footer): that page is one step back.
const cameFromThisSite = () => {
  try {
    return !!document.referrer && new URL(document.referrer).origin === window.location.origin && window.history.length > 1;
  } catch (e) { return false; }
};

function readLocation() {
  let hash = "";
  try { hash = window.location.hash; } catch (e) { hash = ""; }
  const r = parseHash(hash);
  const s = stateNow();
  return { ...r, menu: !!(s && s.v2menu), depth: depthOf(s) || 0 };
}

// First load: give this entry depth 0, put #home in place of a missing or unknown hash, and close a menu that was open
// when the page was reloaded (its entry keeps its depth).
function startLocation() {
  let hash = "";
  try { hash = window.location.hash; } catch (e) { hash = ""; }
  const r = parseHash(hash);
  const s = stateNow();
  const d = depthOf(s);
  if (!r.known) {
    if (!r.empty) console.warn("[v2] unknown address " + JSON.stringify(hash) + ": showing #home");
    replace({ v2: d || 0 }, hashOf("home"));
  } else if (d == null || (s && s.v2menu)) {
    replace({ v2: d || 0 });
  }
  return readLocation();
}

// The router: { loc, lastTab, focusBefore, go, openAbout, replaceRoute, back, openMenu, closeMenu }
//   loc: { tab, sub, about, menu, depth } (tab is null on 소개: the screen behind it is lastTab)
export function useRouter() {
  const [loc, setLoc] = useState(startLocation);
  const locRef = useRef(loc);
  const moves = useRef(0);                               // every history event this page saw (for back's "did it move?")
  const focusBefore = useRef(null);                      // what had focus when 소개 opened (the footer's 소개 link)
  locRef.current = loc;
  const lastTab = useRef(loc.tab || "home");
  if (loc.tab) lastTab.current = loc.tab;

  const sync = useCallback(() => {
    moves.current += 1;
    const s = stateNow();
    if (depthOf(s) == null) replace({ v2: (locRef.current.depth || 0) + 1 });   // a link inside the page made this entry
    let next = readLocation();
    if (!next.known) {
      console.warn("[v2] unknown address: showing #home");
      replace({ v2: next.depth }, hashOf("home"));
      next = readLocation();
    }
    const cur = locRef.current;
    const moved = next.tab !== cur.tab || next.sub !== cur.sub || next.about !== cur.about;
    if (next.about && !cur.about) { try { focusBefore.current = document.activeElement; } catch (e) { focusBefore.current = null; } }
    locRef.current = next;
    setLoc(next);
    if (moved) toTop();
  }, []);

  useEffect(() => {
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
    };
  }, [sync]);

  // A move inside the page. From the open menu the menu's entry is replaced (back returns to the screen under it).
  const go = useCallback((tab, sub = null) => {
    const cur = locRef.current;
    if (!cur.menu && !cur.about && cur.tab === tab && cur.sub === sub) { toTop(); return; }
    const hash = hashOf(tab, sub);
    if (cur.menu) replace({ v2: cur.depth }, hash);
    else push({ v2: cur.depth + 1 }, hash);
    sync();
  }, [sync]);
  const openAbout = useCallback(() => {
    const cur = locRef.current;
    if (cur.menu) replace({ v2: cur.depth }, ABOUT_ROUTE);
    else if (!cur.about) push({ v2: cur.depth + 1 }, ABOUT_ROUTE);
    sync();
  }, [sync]);
  const replaceRoute = useCallback((tab, sub = null) => {
    replace({ v2: locRef.current.depth }, hashOf(tab, sub));
    sync();
  }, [sync]);
  // Leave a sub-screen or 소개 (see the top of this file). fallback: the route that replaces it when there is no step back.
  const back = useCallback((fallbackTab = "home") => {
    const cur = locRef.current;
    const viaSite = cur.about && cur.depth === 0 && cameFromThisSite();
    if (cur.depth > 0 || viaSite) {
      // If the step back did not happen at all (no history event, the page did not leave), the fallback replaces this
      // entry after a moment. Any move in between (the step back itself, or a later tap) cancels it.
      let left = false;
      const seen = moves.current;
      const onHide = () => { left = true; };
      try {
        window.addEventListener("pagehide", onHide, { once: true });
        window.history.back();
        window.setTimeout(() => {
          window.removeEventListener("pagehide", onHide);
          if (!left && moves.current === seen) replaceRoute(fallbackTab);
        }, 600);
        return;
      } catch (e) { /* fall through */ }
    }
    replaceRoute(fallbackTab);
  }, [replaceRoute]);
  const openMenu = useCallback(() => {
    const cur = locRef.current;
    if (cur.menu) return;
    push({ v2: cur.depth + 1, v2menu: 1 });
    sync();
  }, [sync]);
  const closeMenu = useCallback(() => {
    const s = stateNow();
    if (s && s.v2menu) {
      try { window.history.back(); return; } catch (e) { /* fall through */ }
      replace({ v2: depthOf(s) || 0 });
      sync();
    }
  }, [sync]);
  return { loc, lastTab: lastTab.current, focusBefore, go, openAbout, replaceRoute, back, openMenu, closeMenu };
}

// The bottom tab bar: icon + label for the four tabs (board NavC).
export function TabBar({ value, onChange }) {
  const tabs = TABS.map((id) => ({ id, label: C.app.tabs[id], icon: TAB_ICON[id] }));
  return <BottomTabBar fixed tabs={tabs} value={value} onChange={onChange} label={C.app.tabsLabel} />;
}

// One menu line: icon chip, label, chevron. href: a link (into the old app); onClick: a move inside the page.
function MenuRow({ icon, label, href, onClick, id, first }) {
  const body = (
    <>
      <IconChip name={icon} size={40} />
      <span style={tx(SIZE.body, WEIGHT.semi, COLOR.ink, { flex: 1, minWidth: 0 })}>{label}</span>
      <Icon name="chevronRight" size={20} tone="off" />
    </>
  );
  const style = { ...tap, display: "flex", alignItems: "center", gap: SPACE(3) + 2, minHeight: SPACE(15), padding: `0 ${SPACE(1)}px`, width: "100%",
    border: "none", borderTop: first ? "none" : `1px solid ${COLOR.line}`, background: "none", textDecoration: "none", textAlign: "left" };
  return href
    ? <a data-ui-v2="menu-item" data-item={id} href={href} style={style}>{body}</a>
    : <button data-ui-v2="menu-item" data-item={id} type="button" onClick={onClick} style={style}>{body}</button>;
}

// ☰ menu (board Menu): a screen over the current one, above the tab bar. 소개 · 용어 사전 · 데이터 출처 · 예전 뱁새 보기, then
// the data-date box ("{md} 기준", the US close date when it differs). Escape and the close button close it; focus moves
// into it on open and back to the ☰ button on close. The preview page shows 소개 and the data date only.
export function MenuSheet({ open, load, onClose, onAbout, tabH }) {
  const { preview } = useMode();
  const panel = useRef(null);
  const opener = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    opener.current = document.activeElement;
    const first = panel.current && panel.current.querySelector("button, a");
    if (first) { try { first.focus(); } catch (e) { /* ignore */ } }
    const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); onClose(); } };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      const el = opener.current;
      if (el && el.isConnected && typeof el.focus === "function") { try { el.focus(); } catch (e) { /* ignore */ } }
    };
  }, [open]);
  if (!open) return null;
  const ok = load.status === "ok";
  const us = ok && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  const label = C.menu.label || C.app.tabsLabel;
  return (
    <div ref={panel} data-ui-v2="menu" role="dialog" aria-modal="true" aria-label={label}
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: tabH, zIndex: 80, background: COLOR.page, overflowY: "auto", overscrollBehavior: "contain" }}>
      <div style={{ maxWidth: 520, margin: "0 auto", padding: `${SPACE(4)}px ${SPACE(4)}px ${SPACE(6)}px` }}>
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH }}>
          <img src={IMG.mark} alt="" width={28} height={28} style={{ objectFit: "contain", flexShrink: 0, marginRight: -SPACE(1) }} />
          <div style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0, lineHeight: 1.2, letterSpacing: "-0.04em" })}>{C.app.brand}</div>
          <button type="button" data-ui-v2="menu-close" aria-label={C.app.close} onClick={onClose}
            style={{ ...tap, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center", marginRight: -SPACE(2) }}>
            <Icon name="close" tone="on" />
          </button>
        </div>
        <section style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: `${SPACE(1)}px ${SPACE(4)}px`, marginTop: SPACE(2) }}>
          <MenuRow id="about" icon="info" label={C.app.aboutLink} onClick={onAbout} first />
          {!preview && <MenuRow id="glossary" icon="book-open-text" label={C.menu.glossary} href={OLD_LINKS.glossary} />}
          {!preview && <MenuRow id="sources" icon="database" label={C.menu.sources} href={OLD_LINKS.sources} />}
          {!preview && <MenuRow id="old-app" icon="clock-counter-clockwise" label={C.app.oldApp} href={OLD_APP} />}
        </section>
        {ok && (
          <section data-ui-v2="menu-date" style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: `${SPACE(4)}px ${SPACE(4)}px`, marginTop: SPACE(3) }}>
            <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
              <Icon name="calendar" size={20} tone="on" />
              <DateLine date={load.data.pxDate} fresh={load.fresh} />
            </div>
            {us && <Note>{fill(C.app.usClose, { md: us })}</Note>}
          </section>
        )}
      </div>
    </div>
  );
}

// ================= PC (v19.0d, boards PcHome · PcHomeNew · PcMarket) =================
// From 1024 px wide the bottom tab bar and the ☰ menu give way to a 240 px left menu: Jack's mark + 뱁새 (24 px) with the
// catchphrase under it, the four tabs (icon + label, the chosen one on the warm-grey selection background, never apricot),
// 포트폴리오 만들기, then at the bottom the data-date box and the menu links (소개 · 용어 사전 · 데이터 출처 · 예전 뱁새 보기;
// the preview page: 소개 only, as in the ☰ menu). The board's 내 포트폴리오 list waits for its heading to be approved.
// Above each screen a top bar holds the search field (up to 520 px), which searches like the 종목 tab: typing there opens
// 종목 with the results. "/" focuses it, unless the user is typing in another field (input, textarea, select or
// contenteditable) or a dialog is open. The preview page shows its 예시 데이터 label at the right of the top bar.

function SideTab({ id, on, onClick }) {
  return (
    <button type="button" data-ui-v2="side-tab" data-tab={id} aria-current={on ? "page" : undefined} onClick={onClick}
      style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + 2, padding: `0 ${SPACE(3)}px`, width: "100%", border: "none",
        borderRadius: RADIUS.sm, background: on ? SELECTED.background : "transparent", textAlign: "left" }}>
      <Icon name={TAB_ICON[id]} size={24} tone="on" />
      <span style={tx(SIZE.sm, on ? WEIGHT.bold : WEIGHT.regular, COLOR.ink)}>{C.app.tabs[id]}</span>
    </button>
  );
}

// A small line at the bottom of the left menu: icon and label. href: a link (into the old app); onClick: a move inside.
function SideLink({ id, icon, label, href, onClick, on }) {
  const body = (
    <>
      <Icon name={icon} size={18} tone="off" />
      <span style={tx(SIZE.xs, on ? WEIGHT.bold : WEIGHT.semi, on ? COLOR.ink : COLOR.text2)}>{label}</span>
    </>
  );
  const style = { ...tap, display: "flex", alignItems: "center", gap: SPACE(2), minHeight: SPACE(8), padding: `0 ${SPACE(2)}px`, width: "100%", border: "none",
    borderRadius: RADIUS.sm, background: on ? SELECTED.background : "none", textDecoration: "none", textAlign: "left" };
  return href
    ? <a data-ui-v2="side-link" data-item={id} href={href} style={style}>{body}</a>
    : <button data-ui-v2="side-link" data-item={id} type="button" onClick={onClick} aria-current={on ? "page" : undefined} style={style}>{body}</button>;
}

// tab: the tab on screen (none while 소개 is open); about: 소개 is open; go(id): a tab or "build"; onAbout: open 소개.
export function SideMenu({ tab, about, load, go, onAbout }) {
  const { preview } = useMode();
  const ok = load.status === "ok";
  const us = ok && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  return (
    <aside data-ui-v2="side-menu" style={{ position: "fixed", top: 0, bottom: 0, left: 0, width: SIDE_W, zIndex: 60, background: COLOR.surface,
      borderRight: `1px solid ${COLOR.border}`, display: "flex", flexDirection: "column", padding: `${SPACE(5)}px ${SPACE(3)}px ${SPACE(4)}px`,
      overflowY: "auto", overscrollBehavior: "contain" }}>
      <div data-ui-v2="side-brand" style={{ display: "flex", alignItems: "center", gap: SPACE(2) + 2, padding: `0 ${SPACE(2)}px` }}>
        <img data-ui-v2="logo-mark" src={IMG.mark} alt="" width={38} height={38} style={{ objectFit: "contain", flexShrink: 0 }} />
        <div style={{ minWidth: 0 }}>
          <h1 data-ui-v2="wordmark" style={tx(24, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.1, letterSpacing: "-0.04em" })}>{C.app.brand}</h1>
          <p data-ui-v2="side-catch" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2, { marginTop: 2, lineHeight: 1.35 })}>{C.about.ko.hero.catch}</p>
        </div>
      </div>
      <nav aria-label={C.app.tabsLabel} data-ui-v2="side-tabs" style={{ display: "flex", flexDirection: "column", gap: SPACE(1), marginTop: SPACE(6) }}>
        {TABS.map((id) => <SideTab key={id} id={id} on={!about && tab === id} onClick={() => go(id)} />)}
      </nav>
      <div style={{ height: 1, background: COLOR.line, margin: `${SPACE(4)}px ${SPACE(3)}px ${SPACE(2)}px` }} />
      <button type="button" data-ui-v2="side-build" onClick={() => go("build")}
        style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(2) + 2, minHeight: SPACE(10), padding: `0 ${SPACE(3)}px`, width: "100%", border: "none",
          borderRadius: RADIUS.sm, background: "none", textAlign: "left" }}>
        <Icon name="build" size={20} tone="on" />
        <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.neutral)}>{C.build.title}</span>
      </button>
      <div style={{ flex: 1, minHeight: SPACE(4) }} />
      {ok && (
        <section data-ui-v2="side-date" style={{ background: COLOR.page, borderRadius: RADIUS.md, padding: `${SPACE(3)}px ${SPACE(3)}px` }}>
          <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
            <Icon name="calendar" size={18} tone="on" />
            <DateLine date={load.data.pxDate} fresh={load.fresh} style={{ marginTop: 0 }} />
          </div>
          {us && <Note style={{ marginTop: SPACE(1) }}>{fill(C.app.usClose, { md: us })}</Note>}
        </section>
      )}
      <div data-ui-v2="side-links" style={{ marginTop: SPACE(3), display: "flex", flexDirection: "column" }}>
        <SideLink id="about" icon="info" label={C.app.aboutLink} onClick={onAbout} on={about} />
        {!preview && <SideLink id="glossary" icon="book-open-text" label={C.menu.glossary} href={OLD_LINKS.glossary} />}
        {!preview && <SideLink id="sources" icon="database" label={C.menu.sources} href={OLD_LINKS.sources} />}
        {!preview && <SideLink id="old-app" icon="clock-counter-clockwise" label={C.app.oldApp} href={OLD_APP} />}
      </div>
    </aside>
  );
}

// Typing somewhere already: "/" is that field's letter, not the search shortcut.
export function typingIn(el) {
  if (!el || el.nodeType !== 1) return false;
  if (el.isContentEditable) return true;
  const tag = String(el.tagName || "").toUpperCase();
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  try { return !!el.closest('[contenteditable]:not([contenteditable="false"])'); } catch (e) { return false; }
}

// "/" focuses the search field (PC only). Not while typing in a field, not with Ctrl / Alt / Cmd, not during IME
// composition, and not while a dialog (a sheet) is open: focus stays where the dialog keeps it.
export function useSlashFocus(ref, on) {
  useEffect(() => {
    if (!on) return undefined;
    const onKey = (e) => {
      if (e.key !== "/" || e.defaultPrevented || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (typingIn(e.target) || typingIn(document.activeElement)) return;
      if (document.querySelector('[aria-modal="true"]')) return;
      const el = ref.current;
      if (!el || !el.isConnected) return;
      e.preventDefault();
      try { el.focus(); el.select(); } catch (err) { /* ignore */ }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [on]);
}

// The top bar on PC: the search field (shown once the data has loaded, as on the 종목 tab) and the preview label, in the
// same frame as the page under it (ui.jsx PcFrame).
export function TopBar({ q, onSearch, inputRef, load }) {
  const { preview } = useMode();
  const ok = load.status === "ok";
  const label = C.stocks.search || C.app.tabs.stocks;
  return (
    <div data-ui-v2="top-bar" style={{ position: "sticky", top: 0, zIndex: 40, background: COLOR.page }}>
      <PcFrame style={{ padding: `${SPACE(3)}px ${PC_PAD}px`, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(6) }}>
        {ok && (
          <label data-ui-v2="top-search" style={{ flex: 1, maxWidth: 520, minWidth: 0, display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH,
            background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.md, padding: `0 ${SPACE(3)}px` }}>
            <Icon name="search" size={20} tone="off" />
            <input ref={inputRef} type="search" value={q} onChange={(e) => onSearch(e.target.value.slice(0, 40))} aria-label={label}
              placeholder={C.stocks.search || undefined} enterKeyHint="search" autoComplete="off" aria-keyshortcuts="/"
              style={{ flex: 1, minWidth: 0, border: "none", outline: "none", background: "transparent", minHeight: TOUCH - 2, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
            <kbd aria-hidden="true" style={{ flexShrink: 0, minWidth: SPACE(6), height: SPACE(6), display: "inline-flex", alignItems: "center", justifyContent: "center",
              border: `1px solid ${COLOR.border}`, borderRadius: SPACE(1) + 2, background: COLOR.surface, ...tx(SIZE.xxs, WEIGHT.bold, COLOR.text2, { lineHeight: 1 }) }}>/</kbd>
          </label>
        )}
        <span style={{ flex: 1 }} />
        {preview && <SampleLabel />}
      </PcFrame>
    </div>
  );
}
