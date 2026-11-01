// ================= 뱁새 2.0 beta (app.html, v18.3 Parts A + B) =================
// Built by build-app.sh into app.html. The current app (baepsae.html) is untouched.
// Tabs: 오늘 · 내 덱 · 덱 짜기 · 찾기 (찾기 opens the current app until 2.0 has its own search).
import React, { useEffect, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { COLOR } from "../ui/tokens.js";
import { BottomTabBar } from "../ui/components.jsx";
import { C } from "./format.js";
import { loadAll } from "./load.js";
import { readStore, writeStore, askPersist } from "./store.js";
import { Today, MyDeck } from "./home.jsx";
import { Build, newBuilder } from "./build.jsx";
import { TAB_H } from "./ui.jsx";

const OLD_APP = "./baepsae.html";

function App() {
  const [load, setLoad] = useState({ status: "loading" });
  const [tab, setTab] = useState("today");
  const [store, setStore] = useState(() => readStore());
  const [builder, setBuilder] = useState(newBuilder);

  useEffect(() => {
    let live = true;
    loadAll().then((r) => { if (live) setLoad(r); }).catch((e) => {
      console.warn("[v2] load failed: " + ((e && e.message) || e));
      if (live) setLoad({ status: "fail" });
    });
    if (store.writable) askPersist();
    return () => { live = false; };
  }, []);

  // saved = true when the caller already wrote it (the purchase sheet checks the write itself)
  const setStoreData = useCallback((data, saved) => {
    setStore((s) => {
      if (!saved && !(s.writable && writeStore(data))) return { ...s, writable: false };
      return { ...s, data };
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
    <div style={{ minHeight: "100vh", background: COLOR.page }}>
      {tab === "today" && <Today load={load} pad={pad} />}
      {tab === "deck" && <MyDeck load={load} store={store} setStoreData={setStoreData} pad={pad} />}
      {tab === "build" && <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => go("today")} goToday={() => go("today")}
        store={store} setStoreData={setStoreData} />}
      {tab !== "build" && <BottomTabBar fixed tabs={tabs} value={tab} onChange={go} label={C.app.tabsLabel} />}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
