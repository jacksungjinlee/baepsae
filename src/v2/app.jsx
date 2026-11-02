// ================= 뱁새 2.0 app shell (v18.3 Parts A + B, Part E: 오늘 · 왜 움직였나) =================
// Shared by app.html (main.jsx: live data) and app-preview.html (main-preview.jsx: embedded fictional data).
// Tabs: 오늘 · 내 덱 · 덱 짜기 · 찾기 (찾기 opens the current app until 2.0 has its own search).
import React, { useEffect, useState, useCallback } from "react";
import { COLOR } from "../ui/tokens.js";
import { BottomTabBar } from "../ui/components.jsx";
import { C, todayKst } from "./format.js";
import { readStore, writeStore, askPersist } from "./store.js";
import { MyDeck } from "./home.jsx";
import { Today } from "./today.jsx";
import { Why } from "./why.jsx";
import { Build, newBuilder } from "./build.jsx";
import { TAB_H, ModeContext, Page, AppBar, LoadFail, Footer, OLD_APP } from "./ui.jsx";


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
    return <Page><AppBar /><LoadFail /><Footer /></Page>;
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
      <ErrorBoundary>
        <div style={{ minHeight: "100vh", background: COLOR.page }}>
          {tab === "today" && !why && <Today load={load} store={store} setStoreData={setStoreData} pad={pad} go={go}
            onWhy={(deckId, t) => { setWhy({ deckId, t }); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } }} />}
          {tab === "today" && why && <Why load={load} store={store} setStoreData={setStoreData} pad={pad} target={why}
            onBack={() => { setWhy(null); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } }} />}
          {tab === "deck" && <MyDeck load={load} store={store} setStoreData={setStoreData} pad={pad} />}
          {tab === "build" && <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => go("today")} goToday={() => go("today")}
            store={store} setStoreData={setStoreData} />}
          {tab !== "build" && <BottomTabBar fixed tabs={tabs} value={tab} onChange={go} label={C.app.tabsLabel} />}
        </div>
      </ErrorBoundary>
    </ModeContext.Provider>
  );
}
