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
// v19.1a: the company page (#stocks/<code>[/<tab>], company.jsx) sits under the 종목 tab; every company tapped anywhere in
// 2.0 opens it (NavContext.openStock), never the old app's 기업분석.
import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { COLOR, SPACE } from "../ui/tokens.js";
import { C, todayKst } from "./format.js";
import { readStore, writeStore, validStore, askPersist, guideSeenIn, withGuideSeen, keepOwnText, keepMine, versionFor } from "./store.js";
import { refreshFresh, nextFreshCheck } from "./load.js";
import { Portfolio } from "./portfolio.jsx";
import { Home } from "./today.jsx";
import { Why } from "./why.jsx";
import { Build, newBuilder, buildInProgress } from "./build.jsx";
import { Stocks } from "./stocks.jsx";
import { Market } from "./market.jsx";
import { About } from "./about.jsx";
import { Company, logSplitGuard } from "./company.jsx";
import { firstVisitGuide } from "./guide.jsx";
import { Import, newImporter } from "./import.jsx";
import { companySub, CO_MORE } from "./routes.js";
import { holdsKorean } from "./home.js";
import { TAB_H, SIDE_W, ModeContext, NavContext, LayoutContext, useWide, Page, AppBar, LoadFail, Footer } from "./ui.jsx";
import { useRouter, TabBar, MenuSheet, SideMenu, TopBar, useSlashFocus, typingIn } from "./nav.jsx";

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

// source: { preview, storeKey, exportPrefix, load: () => Promise<load state>, loadDisc?: () => Promise<{ ok, data, error }> }
// loadDisc (v19.1a, live page only): disc.json for a Korean company's 공시 tab and 홈's 오늘 볼 것 (v19.3e), fetched once,
// the first time a company page opens or 홈 opens with a Korean stock held. The preview page has none (it fetches nothing):
// its company pages have no 공시 tab and its 홈 no filings rows.
export function App({ source }) {
  const [load, setLoad] = useState({ status: "loading" });
  const [store, setStore] = useState(() => ({ ...readStore(source.storeKey, todayKst()), key: source.storeKey, exportPrefix: source.exportPrefix,
    preview: !!source.preview }));
  const [builder, setBuilder] = useState(newBuilder);
  const [importer, setImporter] = useState(newImporter);   // v19.3d 가진 종목 넣기 (#portfolio/import): kept while the user moves around
  const [why, setWhy] = useState(null);                  // 왜 움직였나: { deckId, t } opened from 홈 (Part E)
  const [disc, setDisc] = useState(() => ({ status: source.loadDisc ? "idle" : "none" }));   // v19.1a 공시 tab (disc.json)
  const router = useRouter();
  const { loc } = router;
  // v19.3c Part E: the first-visit guide — null, { stage: "welcome" } on 홈, or { stage: 1 · 2 · 3 } on 포트폴리오 만들기's
  // 기준 step (guide.jsx). It starts on its own only behind GUIDE_FIRST_VISIT; the menu's 처음 안내 다시 보기 always replays it.
  const [guide, setGuide] = useState(() => (firstVisitGuide(loc, store) ? { stage: "welcome" } : null));
  const wasAbout = useRef(loc.about);
  const wide = useWide();
  const layout = useMemo(() => ({ wide }), [wide]);
  const [stockQ, setStockQ] = useState("");             // PC: the top bar's search words
  const [phoneQ, setPhoneQ] = useState("");             // phone: 종목's own field (kept here so a company page and back keep it)
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

  // v19.1c: the stale check again while the page stays open (load.js refreshFresh): when it is shown again and from a timer
  // that fires just after staleAfter or the next day of a publish (at most an hour apart). Nothing is fetched again: only
  // fresh (and what reads it: the date lines, the 홈 stale band, the daily check) can change. Not on the preview page.
  const liveData = load.status === "ok" && !load.preview;
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    if (!liveData) return undefined;
    let on = true, timer = null;
    const check = () => { if (on) setLoad((l) => refreshFresh(l, Date.now())); };
    const arm = () => {
      const wait = nextFreshCheck(loadRef.current, Date.now());
      if (on && wait != null) timer = setTimeout(() => { check(); arm(); }, wait);
    };
    const onShow = () => { if (document.visibilityState !== "hidden") check(); };
    arm();
    document.addEventListener("visibilitychange", onShow);
    window.addEventListener("focus", check);
    return () => {
      on = false;
      if (timer != null) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onShow);
      window.removeEventListener("focus", check);
    };
  }, [liveData]);

  // v19.1a: the interim dividend split guard's count, once the data is in (company.jsx logSplitGuard; no silent hiding).
  useEffect(() => { logSplitGuard(load); }, [load]);

  // v19.3d review: another tab writing the records (a tab of the earlier app writes over them without looking) never
  // drops what this tab saved: store.js keeps this tab's text as a copy, merged back on the next start.
  useEffect(() => {
    const on = (e) => { if (e.key === store.key && e.storageArea === window.localStorage) keepOwnText(store.key, e.newValue, todayKst()); };
    // leaving the page: the first records this tab wrote get their .mine copy now (store.js keepMine)
    const hide = () => keepMine(store.key);
    const vis = () => { if (document.visibilityState === "hidden") keepMine(store.key); };
    window.addEventListener("storage", on);
    window.addEventListener("pagehide", hide);
    document.addEventListener("visibilitychange", vis);
    return () => { window.removeEventListener("storage", on); window.removeEventListener("pagehide", hide); document.removeEventListener("visibilitychange", vis); };
  }, [store.key]);

  // v19.1a: disc.json, once, when the first company page opens (a failure shows the load-failure message on 공시).
  // v19.3e (Jack, 2026-11-08): also when 홈 opens and a saved portfolio holds a Korean stock (오늘 볼 것's filings rows; a
  // failure shows the same message there). After the first paint (an effect), once per visit for both.
  const homeKr = useMemo(() => holdsKorean(store.data.decks), [store.data.decks]);
  const wantDisc = !!loc.code || (loc.tab === "home" && homeKr);
  useEffect(() => {
    if (!wantDisc || disc.status !== "idle") return;
    setDisc({ status: "loading" });
    source.loadDisc().then((r) => {
      if (r && r.ok) setDisc({ status: "ok", data: r.data });
      else { console.warn("[v2] disc.json not loaded: " + ((r && r.error) || "unknown") + " (the disclosures tab shows the load-failure message)"); setDisc({ status: "fail" }); }
    }).catch((e) => { console.warn("[v2] disc.json not loaded: " + ((e && e.message) || e)); setDisc({ status: "fail" }); });
  }, [wantDisc, disc.status]);

  // 왜 움직였나 needs its target: loaded on its own (a reload, a shared address) it shows 홈 instead.
  useEffect(() => {
    if (loc.tab === "home" && loc.sub === "why" && !why) router.replaceRoute("home");
  }, [loc.tab, loc.sub, why]);

  // Closing 소개 (its back button, the phone's back): focus goes back to what opened it (the footer's 소개 link, noted by
  // the router when 소개 opened), when it is still on the page. Leaving it by a move (router.go clears the note) or while
  // the user is typing in a field (the PC search) leaves focus alone.
  useEffect(() => {
    if (!loc.about && wasAbout.current) {
      const el = router.focusBefore.current;
      router.focusBefore.current = null;
      if (el && el.isConnected && typeof el.focus === "function" && !typingIn(document.activeElement)) {
        try { el.focus(); } catch (e) { /* ignore */ }
      }
    }
    wasAbout.current = loc.about;
  }, [loc.about]);

  // PC has no ☰ menu: a menu left open on a narrower window (its own history entry) closes when the window gets wide.
  useEffect(() => {
    if (wide && loc.menu) router.closeMenu();
  }, [wide, loc.menu]);

  // PC search: the field shows what 종목 lists, so leaving 종목 (another tab, 소개, back) empties it. A company page is part
// of 종목 (v19.1a): the words stay, so back from a company shows the same results (the phone's field too).
  const onStocks = !loc.about && loc.tab === "stocks";
  useEffect(() => {
    if (!onStocks && stockQ) setStockQ("");
    if (!onStocks && phoneQ) setPhoneQ("");
  }, [onStocks]);

  // saved = true when the caller already wrote it (the purchase sheet checks the write itself)
  // v19.3d: records that would not read back are never written or shown (store.js names the reason in the console); that is
  // not a storage failure, so the "can't save on this device" line stays off and refused says so instead (plan.badInput on
  // the screens, until the next change that saves).
  const setStoreData = useCallback((given, saved) => {
    // the records in memory carry the version tag writeStore gives them (a 가진 종목 portfolio makes them version 2). Kept
    // at the old tag (1), every later change in the same visit failed the check below and was refused.
    const data = given && Array.isArray(given.decks) && given.v !== versionFor(given) ? { ...given, v: versionFor(given) } : given;
    setStore((s) => {
      if (!saved && !validStore(data, todayKst())) { console.warn("[v2] change not saved: the records would not read back"); return { ...s, refused: true }; }
      if (!saved && !(s.writable && writeStore(data, s.key, todayKst()))) return { ...s, writable: false };
      return { ...s, data, locked: false, refused: false };
    });
  }, []);

  // go(id): a tab ("home" · "portfolio" · "stocks" · "market") or "build" (포트폴리오 만들기, under 포트폴리오)
  const go = useCallback((id) => {
    if (id === "build") { router.go("portfolio", "build"); return; }
    router.go(id);
  }, [router.go]);
  const goHome = useCallback(() => go("home"), [go]);            // v19.5 Part B: the 뱁새 logo opens 홈 (or scrolls it to the top)
  // Typing in the top bar opens 종목 (one history entry), where the results show; the field keeps focus.
  const onSearch = useCallback((v) => {
    setStockQ(v);
    const cur = router.loc;
    if (v.trim() && (cur.about || cur.tab !== "stocks" || cur.sub)) router.go("stocks");
  }, [router.go, router.loc]);
  const openWhy = useCallback((deckId, t) => { setWhy({ deckId, t }); router.go("home", "why"); }, [router.go]);
  // v19.1a: any company tapped anywhere in 2.0 opens its company page (#stocks/<code>, one history entry).
  const openStock = useCallback((t) => router.go("stocks", companySub(t)), [router.go]);
  const coNav = useMemo(() => ({
    back: () => (loc.ctab === "value-more" || loc.ctab === "earn-more" ? router.back("stocks", companySub(loc.code, loc.ctab.replace("-more", ""))) : router.back("stocks")),
    setTab: (ctab) => router.replaceRoute("stocks", companySub(loc.code, ctab)),
    more: (ctab) => router.go("stocks", companySub(loc.code, ctab)),
    onWhy: openWhy,
  }), [loc.code, loc.ctab, router.back, router.replaceRoute, router.go, openWhy]);
  // 기록했어요 -> 홈: the finished build is replaced by 홈, and the next 포트폴리오 만들기 starts fresh.
  const doneToHome = useCallback(() => { setBuilder(newBuilder()); router.replaceRoute("home"); }, [router.replaceRoute]);

  // v19.3c Part E. seen = remember it (건너뛰기, Esc, 알겠어요, 그냥 둘러볼게요, leaving the steps); a guide that could not run
  // (no data) ends without it.
  // v19.3d: "seen" is the store's guideSeen, written with the store. Records that could not be read are never moved aside
  // for it (a locked store keeps the flag in memory only), and a device that cannot store anything shows the welcome again
  // on the next first visit, as before.
  const markSeen = useCallback(() => {
    setStore((s) => {
      if (guideSeenIn(s.data)) return s;
      const next = withGuideSeen(s.data, todayKst());
      if (!next) return s;
      if (s.locked || !s.writable || !writeStore(next, s.key, todayKst())) {
        console.warn("[v2] the first-visit guide is remembered for this visit only (records not writable or not readable)");
        return { ...s, data: next };
      }
      return { ...s, data: next, locked: false };
    });
  }, []);
  const endGuide = useCallback((seen) => { setGuide(null); if (seen) markSeen(); }, [markSeen]);
  // ☰ (PC: the left menu) 처음 안내 다시 보기: the welcome on 홈, whatever was on screen.
  const replayGuide = useCallback(() => { setGuide({ stage: "welcome" }); router.go("home"); }, [router.go]);
  // 직접 해 보기: a fresh 포트폴리오 만들기 at its 기준 step, the guide's step 1 over it. Without the data (it failed to load)
  // there is no 배당 card to light: the screen opens as usual, with no guide. A half-made portfolio is never thrown away:
  // 포트폴리오 만들기 opens where the user left off, without the guide (it needs an untouched 기준 step).
  const tryGuide = useCallback(() => {
    if (buildInProgress(builder)) {
      setGuide(null);
      router.go("portfolio", "build");
      return;
    }
    setBuilder({ ...newBuilder(), step: 1 });
    setGuide(load.status === "fail" ? null : { stage: 1 });
    router.go("portfolio", "build");
  }, [builder, load.status, router.go]);
  const browseGuide = useCallback(() => { endGuide(true); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } }, [endGuide]);
  const stepNo = guide && typeof guide.stage === "number" ? guide.stage : null;
  const coach = useMemo(() => (stepNo == null ? null : {
    stage: stepNo, go: (n) => setGuide({ stage: n }), done: () => endGuide(true), skip: () => endGuide(true), lost: () => endGuide(false),
  }), [stepNo, endGuide]);
  // v19.3d: 가진 종목 넣기 (Part F), from the start step, the welcome's second button and 포트폴리오.
  const openImport = useCallback(() => router.go("portfolio", "import"), [router.go]);
  const welcome = useMemo(() => (guide && guide.stage === "welcome" ? { onTry: tryGuide, onBrowse: browseGuide, onImport: load.status === "fail" ? null : openImport } : null),
    [guide, tryGuide, browseGuide, openImport, load.status]);
  // 매일 점검 시작하기 saved the portfolio: 포트폴리오 shows it, and the next 가진 종목 넣기 starts fresh.
  const importSaved = useCallback(() => { setImporter(newImporter()); router.replaceRoute("portfolio"); }, [router.replaceRoute]);

  const tab = loc.about ? router.lastTab : loc.tab;
  const inBuild = tab === "portfolio" && loc.sub === "build";
  const inImport = tab === "portfolio" && loc.sub === "import";
  const ownBar = inBuild || inImport;                     // screens with their own bottom bar: no tab bar
  // The steps live on the 기준 step: leaving 포트폴리오 만들기 (the phone's back, a tab, 소개) ends the guide as seen. With no
  // 배당 card to light (the data failed to load, or 포트폴리오 만들기 is not ready) it ends quietly.
  // The same when 포트폴리오 만들기 leaves its 기준 step by a way the overlay does not cover (a screen reader's 다음,
  // 이전 단계 or 다시 시작): the guide ends as seen, so it never comes back over another step or a changed draft.
  const offStep = builder.step !== 1 || builder.stage !== "steps";
  useEffect(() => {
    if (stepNo == null) return;
    if (!inBuild || loc.about || offStep) endGuide(true);
    else if (load.status === "fail" || (load.status === "ok" && load.missing.length)) endGuide(false);
  }, [stepNo, inBuild, loc.about, offStep, load, endGuide]);
  // The welcome lives on 홈: leaving 홈 (another tab, 포트폴리오 만들기, a sub-screen) ends it as seen, so it never comes
  // back over 홈 later (e.g. after 기록했어요). 소개 opens over 홈 and keeps it.
  const onWelcome = !!(guide && guide.stage === "welcome");
  useEffect(() => {
    if (onWelcome && (tab !== "home" || loc.sub)) endGuide(true);
  }, [onWelcome, tab, loc.sub, endGuide]);
  const inWhy = tab === "home" && loc.sub === "why" && !!why;
  const pad = wide ? SPACE(10) : TAB_H + 32;
  const screen = (() => {
    if (inBuild) {
      return <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => router.back("portfolio")} goToday={doneToHome}
        store={store} setStoreData={setStoreData} coach={builder.step === 1 && builder.stage === "steps" ? coach : null} onImport={openImport} />;
    }
    if (inImport) {
      return <Import load={load} store={store} setStoreData={setStoreData} importer={importer} setImporter={setImporter} onExit={() => router.back("portfolio")}
        onSaved={importSaved} />;
    }
    if (inWhy) return <Why load={load} store={store} setStoreData={setStoreData} pad={pad} target={why} onBack={() => router.back("home")} />;
    if (tab === "portfolio") return <Portfolio load={load} store={store} setStoreData={setStoreData} pad={pad} go={go} onImport={openImport} />;
    if (tab === "stocks" && loc.code && !loc.about) {
      return <Company load={load} store={store} setStoreData={setStoreData} pad={pad} code={loc.code} ctab={loc.ctab} disc={disc} nav={coNav} />;
    }
    if (tab === "stocks") return <Stocks load={load} store={store} pad={pad} q={wide ? stockQ : null} ownQ={phoneQ} setOwnQ={setPhoneQ} />;
    if (tab === "market") return <Market load={load} pad={pad} />;
    return <Home load={load} store={store} setStoreData={setStoreData} pad={pad} go={go} onWhy={openWhy} welcome={welcome} disc={disc} />;
  })();
  const nav = { openMenu: wide ? null : router.openMenu, menuOpen: !wide && loc.menu, openStock, goHome };
  // One boundary per screen. A company's tabs are one screen (company.jsx keeps its own boundary per tab), so switching
  // tabs keeps the page mounted; its 자세히 screens are screens of their own.
  const screenKey = !loc.about && tab === "stocks" && loc.code ? "stocks/" + loc.code + (CO_MORE.includes(loc.ctab) ? "/" + loc.ctab : "") : tab + (loc.sub || "");
  const tall = wide ? {} : { minHeight: "100vh" };
  return (
    <ModeContext.Provider value={{ preview: !!source.preview }}>
      <NavContext.Provider value={nav}>
        <LayoutContext.Provider value={layout}>
          {wide && <SideMenu tab={tab} about={loc.about} load={load} go={go} onAbout={router.openAbout} onGuide={replayGuide} />}
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
                <ErrorBoundary key={screenKey} name={tab} pad={ownBar ? undefined : pad}>{screen}</ErrorBoundary>
                {!wide && <MenuSheet open={loc.menu && !loc.about} load={load} onClose={router.closeMenu} onAbout={router.openAbout} onHome={goHome} onGuide={replayGuide}
                  tabH={ownBar ? 0 : TAB_H} />}
                {!wide && !ownBar && <TabBar value={tab} onChange={go} />}
              </ErrorBoundary>
            </div>
          </div>
        </LayoutContext.Provider>
      </NavContext.Provider>
    </ModeContext.Provider>
  );
}
