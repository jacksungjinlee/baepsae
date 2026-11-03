// ================= 뱁새 2.0 app shell (v18.3 Parts A + B, Part E: 오늘 · 왜 움직였나) =================
// Shared by app.html (main.jsx: live data) and app-preview.html (main-preview.jsx: embedded fictional data).
// Tabs: 오늘 · 내 덱 · 덱 짜기 · 찾기 (찾기 opens the current app until 2.0 has its own search).
// 소개 (v19.0 Part D): the hash #about opens the 소개 page over the current screen, on load and on every hash change (the
// footer's 소개 link, the old app's footers). Its back button returns to the screen before and clears the hash: one step
// back in the browser when a link here or a page of this site opened it, otherwise the hash is cleared in place.
// 소개 and the screens behind it have their own error boundaries, so a crash in the hidden screen never replaces 소개.
import React, { useEffect, useState, useCallback, useRef } from "react";
import { COLOR } from "../ui/tokens.js";
import { BottomTabBar } from "../ui/components.jsx";
import { C, todayKst } from "./format.js";
import { readStore, writeStore, askPersist } from "./store.js";
import { MyDeck } from "./home.jsx";
import { Today } from "./today.jsx";
import { Why } from "./why.jsx";
import { Build, newBuilder } from "./build.jsx";
import { About } from "./about.jsx";
import { ABOUT_HASH } from "../links.js";
import { TAB_H, ModeContext, Page, AppBar, LoadFail, Footer, OLD_APP } from "./ui.jsx";


const atAbout = () => {
  try { return window.location.hash === ABOUT_HASH; } catch (e) { return false; }
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

// A rendering error never leaves a blank page: the approved load-failure message is shown instead.
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(err) {
    console.warn("[v2] screen error: " + ((err && err.message) || err));
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <Page><AppBar onBack={this.props.onBack} backLabel={this.props.backLabel} /><LoadFail /><Footer /></Page>;
  }
}

// source: { preview, storeKey, exportPrefix, load: () => Promise<load state> }
export function App({ source }) {
  const [load, setLoad] = useState({ status: "loading" });
  const [store, setStore] = useState(() => ({ ...readStore(source.storeKey, todayKst()), key: source.storeKey, exportPrefix: source.exportPrefix,
    preview: !!source.preview }));
  // First screen: a visitor with a saved deck lands on 오늘; everyone else (first visit, recruiters) on 덱 짜기.
  const [tab, setTab] = useState(() => (store.data.decks.length ? "today" : "build"));
  const [builder, setBuilder] = useState(newBuilder);
  const [why, setWhy] = useState(null);                  // 왜 움직였나: { deckId, t } opened from 오늘 (Part E)
  const [about, setAbout] = useState(atAbout);           // 소개 (#about), over whatever screen was open
  const aboutRef = useRef(about);
  const aboutPushed = useRef(false);                     // opened by a link inside this page: the screen before is one step back
  const lastFocus = useRef(null);                        // what had focus before 소개 opened (the footer's 소개 link), restored on close

  useEffect(() => {
    const onHash = () => {
      const a = atAbout();
      if (a === aboutRef.current) return;
      if (a) lastFocus.current = document.activeElement;
      aboutPushed.current = a;
      aboutRef.current = a;
      setAbout(a);
      toTop();
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Back from 소개, three ways:
  //   opened by a link inside this page -> one step back (the hash change closes it, focus returns to the link);
  //   opened straight at app.html#about from another page of this site (the old app) -> one step back to that page;
  //   otherwise (a shared link, a bookmark) -> clear the hash in place and show this page's first screen.
  // If a step back does not leave 소개 (nothing to go back to), the hash is cleared in place after a moment.
  const clearInPlace = () => {
    try { window.history.replaceState(null, "", window.location.pathname + window.location.search); } catch (e) { /* ignore */ }
    aboutRef.current = false;
    setAbout(false);
    toTop();
  };
  const closeAbout = () => {
    if (aboutPushed.current || cameFromThisSite()) {
      aboutPushed.current = false;
      let left = false;
      const onHide = () => { left = true; };
      try {
        window.addEventListener("pagehide", onHide, { once: true });
        window.history.back();
        window.setTimeout(() => {
          window.removeEventListener("pagehide", onHide);
          if (!left && aboutRef.current) clearInPlace();
        }, 600);
        return;
      } catch (e) { /* fall through */ }
    }
    clearInPlace();
  };

  // Closing 소개: focus goes back to what opened it (the footer's 소개 link), when it is still on the page.
  useEffect(() => {
    if (about) return;
    const el = lastFocus.current;
    lastFocus.current = null;
    if (el && el.isConnected && typeof el.focus === "function") {
      try { el.focus(); } catch (e) { /* ignore */ }
    }
  }, [about]);

  useEffect(() => {
    let live = true;
    source.load().then((r) => { if (live) setLoad(r); }).catch((e) => {
      console.warn("[v2] load failed: " + ((e && e.message) || e));
      if (live) setLoad({ status: "fail" });
    });
    if (store.writable) askPersist();
    return () => { live = false; };
  }, []);

  // saved = true when the caller already wrote it (the purchase sheet checks the write itself)
  const setStoreData = useCallback((data, saved) => {
    setStore((s) => {
      if (!saved && !(s.writable && writeStore(data, s.key, todayKst()))) return { ...s, writable: false };
      return { ...s, data, locked: false };
    });
  }, []);

  const go = (id) => {
    if (id === "search") { try { window.location.href = OLD_APP; } catch (e) { /* ignore */ } return; }
    setWhy(null);
    setTab(id);
    try { window.scrollTo(0, 0); } catch (e) { /* ignore */ }
  };
  const tabs = [
    { id: "today", label: C.app.tabs.today, icon: "today" },
    { id: "deck", label: C.app.tabs.deck, icon: "deck" },
    { id: "build", label: C.app.tabs.build, icon: "build" },
    { id: "search", label: C.app.tabs.search, icon: "search" },
  ];
  const pad = TAB_H + 32;
  return (
    <ModeContext.Provider value={{ preview: !!source.preview }}>
      {about && (
        <ErrorBoundary onBack={closeAbout} backLabel={C.app.close}>
          <div style={{ minHeight: "100vh", background: COLOR.page }}><About load={load} onBack={closeAbout} /></div>
        </ErrorBoundary>
      )}
      <div style={{ minHeight: "100vh", background: COLOR.page, ...(about ? { display: "none" } : {}) }} aria-hidden={about ? true : undefined}>
        <ErrorBoundary>
          {tab === "today" && !why && <Today load={load} store={store} setStoreData={setStoreData} pad={pad} go={go}
            onWhy={(deckId, t) => { setWhy({ deckId, t }); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } }} />}
          {tab === "today" && why && <Why load={load} store={store} setStoreData={setStoreData} pad={pad} target={why}
            onBack={() => { setWhy(null); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } }} />}
          {tab === "deck" && <MyDeck load={load} store={store} setStoreData={setStoreData} pad={pad} />}
          {tab === "build" && <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => go("today")} goToday={() => go("today")}
            store={store} setStoreData={setStoreData} />}
          {tab !== "build" && <BottomTabBar fixed tabs={tabs} value={tab} onChange={go} label={C.app.tabsLabel} />}
        </ErrorBoundary>
      </div>
    </ModeContext.Provider>
  );
}
