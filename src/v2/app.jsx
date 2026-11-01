// ================= 뱁새 2.0 app shell (v18.3 Parts A + B) =================
// Shared by app.html (main.jsx: live data) and app-preview.html (main-preview.jsx: embedded fictional data).
// Tabs: 오늘 · 내 덱 · 덱 짜기 · 찾기 (찾기 opens the current app until 2.0 has its own search).
import React, { useEffect, useState, useCallback } from "react";
import { COLOR } from "../ui/tokens.js";
import { BottomTabBar } from "../ui/components.jsx";
import { C, todayKst } from "./format.js";
import { readStore, writeStore, askPersist } from "./store.js";
import { Today, MyDeck } from "./home.jsx";
import { Build, newBuilder } from "./build.jsx";
import { TAB_H, ModeContext, Page, AppBar, LoadFail, Footer } from "./ui.jsx";

const OLD_APP = "./baepsae.html";

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
  const [tab, setTab] = useState("today");
  const [store, setStore] = useState(() => ({ ...readStore(source.storeKey, todayKst()), key: source.storeKey, exportPrefix: source.exportPrefix }));
  const [builder, setBuilder] = useState(newBuilder);

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
      if (!saved && !(s.writable && writeStore(data, s.key))) return { ...s, writable: false };
      return { ...s, data, locked: false };
    });
  }, []);

  const go = (id) => {
    if (id === "search") { try { window.location.href = OLD_APP; } catch (e) { /* ignore */ } return; }
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
          {tab === "today" && <Today load={load} pad={pad} />}
          {tab === "deck" && <MyDeck load={load} store={store} setStoreData={setStoreData} pad={pad} />}
          {tab === "build" && <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => go("today")} goToday={() => go("today")}
            store={store} setStoreData={setStoreData} />}
          {tab !== "build" && <BottomTabBar fixed tabs={tabs} value={tab} onChange={go} label={C.app.tabsLabel} />}
        </div>
      </ErrorBoundary>
    </ModeContext.Provider>
  );
}
