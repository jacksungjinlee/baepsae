// ================= 뱁새 2.0 app shell (v18.3 Parts A + B + E, v19.0 Part D 소개, v19.0c Layout C phone) =================
// Shared by app.html (main.jsx: live data) and app-preview.html (main-preview.jsx: embedded fictional data).
// v19.0c: four tabs 홈 · 포트폴리오 · 종목 · 시장 with hash routes, the ☰ menu and 소개 (#about); the routing and the menu
// live in nav.jsx. Sub-screens: 포트폴리오 만들기 (#portfolio/build, no tab bar: it has its own bottom bar) and 왜 움직였나
// (#home/why, opened from 홈). 소개 covers the screen behind it (kept mounted, so a half-made portfolio or a scroll
// position survive), and that screen and 소개 have their own error boundaries; each tab has its own too, so a crash in
// one tab never stays on screen after moving to another.
// v19.0d (PC, from 1024 px wide): the left menu and the top bar with the search field (nav.jsx SideMenu · TopBar) take the
// place of the bottom tab bar and the ☰ menu; screens read the width from LayoutContext (ui.jsx). The search field's
// words live here: typing opens 종목 with the results, and leaving 종목 empties the field. Below 1024 px: the phone layout.
import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { COLOR, SPACE } from "../ui/tokens.js";
import { C, todayKst } from "./format.js";
import { readStore, writeStore, askPersist } from "./store.js";
import { Portfolio } from "./portfolio.jsx";
import { Home } from "./today.jsx";
import { Why } from "./why.jsx";
import { Build, newBuilder } from "./build.jsx";
import { Stocks } from "./stocks.jsx";
import { Market } from "./market.jsx";
import { About } from "./about.jsx";
import { TAB_H, SIDE_W, ModeContext, NavContext, LayoutContext, useWide, Page, AppBar, LoadFail, Footer } from "./ui.jsx";
import { useRouter, TabBar, MenuSheet, SideMenu, TopBar, useSlashFocus } from "./nav.jsx";

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
    console.warn("[v2] screen error" + (this.props.name ? " (" + this.props.name + ")" : "") + ": " + ((err && err.message) || err));
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <Page pad={this.props.pad}><AppBar onBack={this.props.onBack} backLabel={this.props.backLabel} /><LoadFail /><Footer /></Page>;
  }
}

// source: { preview, storeKey, exportPrefix, load: () => Promise<load state> }
export function App({ source }) {
  const [load, setLoad] = useState({ status: "loading" });
  const [store, setStore] = useState(() => ({ ...readStore(source.storeKey, todayKst()), key: source.storeKey, exportPrefix: source.exportPrefix,
    preview: !!source.preview }));
  const [builder, setBuilder] = useState(newBuilder);
  const [why, setWhy] = useState(null);                  // 왜 움직였나: { deckId, t } opened from 홈 (Part E)
  const router = useRouter();
  const { loc } = router;
  const wasAbout = useRef(loc.about);
  const wide = useWide();
  const layout = useMemo(() => ({ wide }), [wide]);
  const [stockQ, setStockQ] = useState("");             // PC: the top bar's search words (the phone's 종목 keeps its own)
  const searchRef = useRef(null);
  useSlashFocus(searchRef, wide);

  useEffect(() => {
    let live = true;
    source.load().then((r) => { if (live) setLoad(r); }).catch((e) => {
      console.warn("[v2] load failed: " + ((e && e.message) || e));
      if (live) setLoad({ status: "fail" });
    });
    if (store.writable) askPersist();
    return () => { live = false; };
  }, []);

  // 왜 움직였나 needs its target: loaded on its own (a reload, a shared address) it shows 홈 instead.
  useEffect(() => {
    if (loc.tab === "home" && loc.sub === "why" && !why) router.replaceRoute("home");
  }, [loc.tab, loc.sub, why]);

  // Closing 소개: focus goes back to what opened it (the footer's 소개 link, noted by the router when 소개 opened), when it
  // is still on the page.
  useEffect(() => {
    if (!loc.about && wasAbout.current) {
      const el = router.focusBefore.current;
      router.focusBefore.current = null;
      if (el && el.isConnected && typeof el.focus === "function") {
        try { el.focus(); } catch (e) { /* ignore */ }
      }
    }
    wasAbout.current = loc.about;
  }, [loc.about]);

  // PC has no ☰ menu: a menu left open on a narrower window (its own history entry) closes when the window gets wide.
  useEffect(() => {
    if (wide && loc.menu) router.closeMenu();
  }, [wide, loc.menu]);

  // PC search: the field shows what 종목 lists, so leaving 종목 (another tab, 소개, back) empties it.
  const onStocks = !loc.about && loc.tab === "stocks";
  useEffect(() => {
    if (!onStocks && stockQ) setStockQ("");
  }, [onStocks]);

  // saved = true when the caller already wrote it (the purchase sheet checks the write itself)
  const setStoreData = useCallback((data, saved) => {
    setStore((s) => {
      if (!saved && !(s.writable && writeStore(data, s.key, todayKst()))) return { ...s, writable: false };
      return { ...s, data, locked: false };
    });
  }, []);

  // go(id): a tab ("home" · "portfolio" · "stocks" · "market") or "build" (포트폴리오 만들기, under 포트폴리오)
  const go = useCallback((id) => {
    if (id === "build") { router.go("portfolio", "build"); return; }
    router.go(id);
  }, [router.go]);
  // Typing in the top bar opens 종목 (one history entry), where the results show; the field keeps focus.
  const onSearch = useCallback((v) => {
    setStockQ(v);
    const cur = router.loc;
    if (v.trim() && (cur.about || cur.tab !== "stocks" || cur.sub)) router.go("stocks");
  }, [router.go, router.loc]);
  const openWhy = useCallback((deckId, t) => { setWhy({ deckId, t }); router.go("home", "why"); }, [router.go]);
  // 기록했어요 -> 홈: the finished build is replaced by 홈, and the next 포트폴리오 만들기 starts fresh.
  const doneToHome = useCallback(() => { setBuilder(newBuilder()); router.replaceRoute("home"); }, [router.replaceRoute]);

  const tab = loc.about ? router.lastTab : loc.tab;
  const inBuild = tab === "portfolio" && loc.sub === "build";
  const inWhy = tab === "home" && loc.sub === "why" && !!why;
  const pad = wide ? SPACE(10) : TAB_H + 32;
  const screen = (() => {
    if (inBuild) {
      return <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => router.back("portfolio")} goToday={doneToHome}
        store={store} setStoreData={setStoreData} />;
    }
    if (inWhy) return <Why load={load} store={store} setStoreData={setStoreData} pad={pad} target={why} onBack={() => router.back("home")} />;
    if (tab === "portfolio") return <Portfolio load={load} store={store} setStoreData={setStoreData} pad={pad} go={go} />;
    if (tab === "stocks") return <Stocks load={load} store={store} pad={pad} q={wide ? stockQ : null} />;
    if (tab === "market") return <Market load={load} pad={pad} />;
    return <Home load={load} store={store} setStoreData={setStoreData} pad={pad} go={go} onWhy={openWhy} />;
  })();
  const nav = { openMenu: wide ? null : router.openMenu, menuOpen: !wide && loc.menu };
  const tall = wide ? {} : { minHeight: "100vh" };
  return (
    <ModeContext.Provider value={{ preview: !!source.preview }}>
      <NavContext.Provider value={nav}>
        <LayoutContext.Provider value={layout}>
          {wide && <SideMenu tab={tab} about={loc.about} load={load} go={go} onAbout={router.openAbout} />}
          <div data-ui-v2="main-area" style={wide ? { marginLeft: SIDE_W, minWidth: 0 } : undefined}>
            {wide && <TopBar q={stockQ} onSearch={onSearch} inputRef={searchRef} load={load} />}
            {loc.about && (
              <ErrorBoundary name="about" onBack={() => router.back("home")} backLabel={C.app.close}>
                <div style={{ ...tall, background: COLOR.page }}><About load={load} onBack={() => router.back("home")} /></div>
              </ErrorBoundary>
            )}
            <div data-ui-v2="screen" data-route={tab + (loc.sub ? "/" + loc.sub : "")} style={{ ...tall, background: COLOR.page, ...(loc.about ? { display: "none" } : {}) }}
              aria-hidden={loc.about ? true : undefined}>
              <ErrorBoundary name="app">
                <ErrorBoundary key={tab + (loc.sub || "")} name={tab} pad={inBuild ? undefined : pad}>{screen}</ErrorBoundary>
                {!wide && <MenuSheet open={loc.menu && !loc.about} load={load} onClose={router.closeMenu} onAbout={router.openAbout} tabH={inBuild ? 0 : TAB_H} />}
                {!wide && !inBuild && <TabBar value={tab} onChange={go} />}
              </ErrorBoundary>
            </div>
          </div>
        </LayoutContext.Provider>
      </NavContext.Provider>
    </ModeContext.Provider>
  );
}
