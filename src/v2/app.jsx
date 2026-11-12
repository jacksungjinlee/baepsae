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
import { refreshFresh, nextFreshCheck, returnWatch, adoptLoad } from "./load.js";
import { publishGate, discAfter, discFits, discRetryDue, heldOn, discBehind } from "./hold.js";
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
import { Limits } from "./limits.jsx";
import { Returns } from "./returns.jsx";
import { dataSplits, withDataSplits, storedNotInData, withStoredSplits } from "./lots.js";
import { companySub, CO_MORE } from "./routes.js";
import { holdsKorean } from "./home.js";
import { TAB_H, SIDE_W, ModeContext, NavContext, LayoutContext, HeldContext, useWide, Page, AppBar, LoadFail, Footer } from "./ui.jsx";
import { useRouter, TabBar, MenuSheet, SideMenu, TopBar, useSlashFocus, typingIn, useThemeMode } from "./nav.jsx";

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

// source: { preview, storeKey, exportPrefix, load: () => Promise<load state>, loadDisc?: () => Promise<{ ok, data, error }>,
//   refetch?: (load, disc) => Promise<{ ok, load?, disc?, why? }> }
// loadDisc (v19.1a, live page only): disc.json for a Korean company's 공시 tab and 홈's 오늘 볼 것 (v19.3e), fetched once,
// the first time a company page opens or 홈 opens with a Korean stock held. The preview page has none (it fetches nothing):
// its company pages have no 공시 tab and its 홈 no filings rows.
// refetch (2026-11-08, live page only): load.js refetchNewer, for a page brought back into view with stale data.
export function App({ source }) {
  const [load, setLoad] = useState({ status: "loading" });
  const [store, setStore] = useState(() => ({ ...readStore(source.storeKey, todayKst()), key: source.storeKey, exportPrefix: source.exportPrefix,
    preview: !!source.preview }));
  const [builder, setBuilder] = useState(newBuilder);
  const [importer, setImporter] = useState(newImporter);   // v19.3d 가진 종목 넣기 (#portfolio/import): kept while the user moves around
  const [why, setWhy] = useState(null);                  // 왜 움직였나: { deckId, t } opened from 홈 (Part E)
  const [disc, setDisc] = useState(() => ({ status: source.loadDisc ? "idle" : "none" }));   // v19.1a 공시 tab (disc.json)
  // 2026-11-08 (Jack): the later publish held under a draft (hold.js publishGate onHold), or null: the draft's screen says
  // "새 데이터가 들어왔어요. …" instead of its stale line while it waits (heldOn, below).
  const [heldNext, setHeldNext] = useState(null);
  const [heldTick, setHeldTick] = useState(0);            // bumped when the held publish's own stale check can change
  const router = useRouter();
  const { loc } = router;
  const theme = useThemeMode();                          // v19.6d 화면 모드: applied here, chosen in the menus
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
  // that fires just after staleAfter or the next day of a publish (at most an hour apart). Nothing is fetched here: only
  // fresh (and what reads it: the date lines, the 홈 stale band, the daily check) can change. Not on the preview page.
  // (A page brought back into view with stale data fetches the files once: the effect after this one.) The timer is set
  // again for each publish on screen (livePub, round-2 review): one fetched on a return brings its own staleAfter.
  const liveData = load.status === "ok" && !load.preview;
  const livePub = liveData ? load.data.publishedAt : null;
  const loadRef = useRef(load);
  loadRef.current = load;
  const discRef = useRef(disc);
  discRef.current = disc;
  const discGen = useRef(0);                              // bumped when a newer publish goes on screen (the disc effect below)
  const discPub = useRef(null);                           // the publishedAt of the data put on screen by a return's fetch
  const discRetried = useRef(false);                      // the one more try of an older disc.json used (hold.js discRetryDue)
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
  }, [liveData, livePub]);

  // 2026-11-08 (Jack, Q9: "Old page brought back into view: yes, fetch once. If that fails, show the existing stale or
  // failed message."): a page brought back into view (visibilitychange to visible after it was hidden, or pageshow from the
  // back-forward cache) whose data is stale at that moment, or whose first load failed, fetches the files once (load.js
  // returnWatch · refetchNewer: a timeout, and no new fetch within 10 minutes of one that put nothing on screen).
  // A later publish, every file from it, replaces the data on every screen at once (and the 공시 tab's disc.json when it is
  // already shown); a failed first load is replaced only by a load that works. Anything else leaves the screens as they are,
  // with their stale line or the load-failure message, and says why in the console. The loading screen never shows again.
  // Review (2026-11-08): never under a draft the new data could change (hold.js publishGate · holdReason): the result
  // waits, and goes on screen when nothing holds it any more (the effect after inBuild and inImport below).
  // Focus alone is not a return. Live page only (the preview has no refetch).
  const watchable = !!source.refetch && !load.preview && (load.status === "ok" || load.status === "fail");
  const holdCtxRef = useRef({});
  const gateRef = useRef(null);
  if (!gateRef.current) {
    gateRef.current = publishGate({
      getLoad: () => loadRef.current,
      ctx: () => holdCtxRef.current,
      onHold: (l) => setHeldNext(l),
      put: (r) => {
        // its stale check as of now, not as of the fetch (a publish held for days must not show as fresh: round-2 review)
        setLoad(refreshFresh(adoptLoad(r.load), Date.now()));
        // disc.json goes with it (hold.js discAfter): the one fetched with this publish, or the one on screen when it is
        // already this publish's; else it loads again (and an answer still out from before is not used: discGen).
        const pub = r.load.data.publishedAt;
        discGen.current += 1;
        discPub.current = pub;
        discRetried.current = false;
        setDisc((d) => discAfter(d, r.disc, pub));
      },
    });
  }
  useEffect(() => {
    if (!watchable) return undefined;
    const gate = gateRef.current;
    const w = returnWatch({
      hidden: document.visibilityState === "hidden",
      getLoad: () => loadRef.current,
      getDisc: () => (discRef.current && discRef.current.status === "ok" ? discRef.current.data : null),
      refetch: source.refetch,
      now: () => Date.now(),
      apply: (r, cur) => gate.apply(r, cur),
      held: (now) => gate.held(now),
      // a disc.json that was older than the data on screen: one more try, 10 minutes on (hold.js discRetryDue)
      onReturn: (now) => {
        const d = discRef.current;
        if (!discRetryDue(d, now, discRetried.current)) return;
        discRetried.current = true;
        console.info("[v2] back in view: disc.json was older than the data on screen " + Math.round((now - d.older) / 60000)
          + " minutes ago: it loads once more");
        setDisc((x) => (x === d ? { status: "idle" } : x));
      },
    });
    const onVis = () => { if (document.visibilityState === "hidden") w.hide(); else w.show(); };
    const onHide = () => w.hide();
    const onBack = (e) => { if (e && e.persisted) w.show(); };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("pagehide", onHide);
    window.addEventListener("pageshow", onBack);
    return () => {
      w.stop();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("pagehide", onHide);
      window.removeEventListener("pageshow", onBack);
    };
  }, [watchable]);

  // #90 review follow-up (2026-11-08): on every load, not only after a return's fetch, a disc.json from an older publish
  // than the data on screen that would read as current (hold.js discBehind: the site's CDN just after a deploy, or the
  // phone's offline copy) is not shown: the screens get the load-failure message at once (discView), and the state becomes
  // the failure with its one more try 10 minutes on (discRetryDue), as after a fetch. Also when the data arrives after it
  // (a company page opened by its address loads disc.json while the data is still loading).
  const discOld = disc.status === "ok" && discBehind(disc.data, load);
  const discView = useMemo(() => (discOld ? { status: "fail" } : disc), [discOld, disc]);
  useEffect(() => {
    if (!discOld) return;
    console.warn("[v2] disc.json not shown: it is from " + disc.data.publishedAt + ", older than the data on screen (" + load.data.publishedAt
      + "); the disclosures show the load-failure message" + (discRetried.current ? " (it was the one more try: no more)"
        : "; it is tried once more on a return to view at least 10 minutes from now"));
    setDisc((d) => (d === disc ? { status: "fail", older: Date.now() } : d));
  }, [discOld, disc]);

  // The held publish can go stale itself while it waits (review, 2026-11-08): heldHere is worked out again then.
  useEffect(() => {
    if (!heldNext) return undefined;
    const wait = nextFreshCheck(heldNext, Date.now());
    if (wait == null) return undefined;
    const id = setTimeout(() => setHeldTick((n) => n + 1), wait);
    return () => clearTimeout(id);
  }, [heldNext, heldTick]);

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
  const homeKr = useMemo(() => holdsKorean(store.data.decks, load.status === "ok" ? load.byT : null), [store.data.decks, load]);
  const wantDisc = !!loc.code || (loc.tab === "home" && homeKr);
  // 2026-11-08 (the stale re-fetch): a load still out when a newer publish goes on screen is not used (discGen: it loads
  // again with that publish, hold.js discAfter), and one loaded again then is shown only if it is not older than that
  // publish (discPub, hold.js discFits; else the load-failure message), so an older disc.json never sits beside newer data.
  useEffect(() => {
    if (!wantDisc || disc.status !== "idle") return;
    setDisc({ status: "loading" });
    const gen = discGen.current, pub = discPub.current;
    const mine = () => {
      if (gen === discGen.current) return true;
      console.info("[v2] disc.json loaded for data that is no longer on screen: not used (it loads again with the new publish)");
      return false;
    };
    source.loadDisc().then((r) => {
      if (!mine()) return;
      if (r && r.ok && !discFits(r.data, pub)) {
        console.warn("[v2] disc.json not shown: it is from " + r.data.publishedAt + ", older than the data on screen (" + pub
          + "); the disclosures show the load-failure message" + (discRetried.current ? " (it was the one more try: no more)"
            : "; it is tried once more on a return to view at least 10 minutes from now"));
        setDisc({ status: "fail", older: Date.now() });
      } else if (r && r.ok) setDisc({ status: "ok", data: r.data });
      else { console.warn("[v2] disc.json not loaded: " + ((r && r.error) || "unknown") + " (the disclosures tab shows the load-failure message)"); setDisc({ status: "fail" }); }
    }).catch((e) => { if (mine()) { console.warn("[v2] disc.json not loaded: " + ((e && e.message) || e)); setDisc({ status: "fail" }); } });
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
    // #87 (hotfix of #83): the records in memory carry the version tag writeStore gives them (a portfolio made with 가진
    // 종목 넣기 makes them version 2). Before, they kept the tag they had (1), so every later change in the same visit (a 메모,
    // an answer, 빼기, 내 규칙) failed the check below and was refused. A store already tagged is kept as it is (the same
    // object: a records file taken in keeps its mergeStores mark).
    const data = given && Array.isArray(given.decks) && given.v !== versionFor(given) ? { ...given, v: versionFor(given) } : given;
    setStore((s) => {
      if (!saved && !validStore(data, todayKst())) { console.warn("[v2] change not saved: the records would not read back"); return { ...s, refused: true }; }
      if (!saved && !(s.writable && writeStore(data, s.key, todayKst()))) return { ...s, writable: false };
      return { ...s, data, locked: false, refused: false };
    });
  }, []);

  // go(id): a tab ("home" · "portfolio" · "stocks" · "market") or "build" (포트폴리오 만들기, under 포트폴리오)
  const go = useCallback((id) => {
    // Jack, 11월 10일: 포트폴리오 만들기 after a recorded plan starts fresh (also when it is already open under 기록했어요).
    if (id === "build") { setBuilder((b) => (b.recorded ? newBuilder() : b)); router.go("portfolio", "build"); return; }
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
  // Jack, 11월 10일: 기록했어요 closed -> 포트폴리오 (the new portfolio); the finished build is replaced the same way as for 홈.
  const doneToPortfolio = useCallback(() => { setBuilder(newBuilder()); router.replaceRoute("portfolio"); }, [router.replaceRoute]);

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
  // Jack, 11월 10일: leaving 포트폴리오 만들기 any way after a recorded plan (left menu, tabs, back, 소개) ends it: the next visit
  // starts fresh, so the same plan can't be recorded twice.
  useEffect(() => { if (!inBuild && builder.recorded) setBuilder(newBuilder()); }, [inBuild, builder.recorded]);
  // A later publish held under a draft (hold.js) goes on screen once the user leaves it or the draft no longer needs it.
  holdCtxRef.current = { onBuild: inBuild, onImport: inImport, builder, importer };
  useEffect(() => { gateRef.current.check(); }, [inBuild, inImport, builder, importer]);
  // The held publish's line (hold.js heldOn): on 후보 고르기 · 매수 계획 or 가진 종목 넣기 while a later publish waits for this
  // screen's work, and only when saving or leaving would let it in and it is not stale itself. Never with nothing held;
  // gone once it is on screen (onHold(null)). Not while 소개 covers the screen. Worked out when the screen, a draft or the
  // held publish changes (review: not on every render: heldOn can read the whole new data.json), and again when the held
  // publish's own stale check can change (heldTick, from load.js nextFreshCheck on it).
  const heldHere = useMemo(() => !!heldNext && !loc.about
    && !!heldOn({ onBuild: inBuild, onImport: inImport, builder, importer }, heldNext, Date.now()),
  [heldNext, heldTick, inBuild, inImport, builder, importer, loc.about]);
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
  // No data (Part E: "if … data load failed, skip the guide silently and show the normal screen"): the welcome closes
  // without a word and is not marked seen, whether it opened on its own or from 처음 안내 다시 보기, so 홈 shows its
  // load-failure message exactly as without the guide (the first-visit landing on a first visit).
  useEffect(() => {
    if (onWelcome && load.status === "fail") setGuide(null);
  }, [onWelcome, load.status]);
  const inWhy = tab === "home" && loc.sub === "why" && !!why;
  // v19.3d2: 내 규칙 정하기 of a 가진 종목 portfolio that exists (else 포트폴리오, where the portfolio would be)
  const rulesDeck = tab === "portfolio" && loc.rules ? store.data.decks.find((d) => d.id === loc.rules && d.kind === "imported") || null : null;
  // entering 내 규칙 정하기: a refusal left from another screen does not show there (only a refused 저장 of this screen)
  const rulesId = rulesDeck ? rulesDeck.id : null;
  useEffect(() => { if (rulesId) setStore((s) => (s.refused ? { ...s, refused: false } : s)); }, [rulesId]);
  // v19.6a (A.6): data.json's stock splits, put on an in-memory copy of each portfolio that has records of a split stock
  // (held.js VIEW_SPLITS: never written), so every screen reads its records at today's share basis. A record saved for
  // that stock stores the split with it (records.js withRecord), so the stored records read back the same.
  const splitList = useMemo(() => {
    if (load.status !== "ok") return [];
    const r = dataSplits(load.data);
    if (r.bad) console.warn(`[v2] data.json splits: ${r.bad} entr${r.bad === 1 ? "y" : "ies"} not read (not [code, date, ratio]); left out`);
    return r.list;
  }, [load]);
  const view = useMemo(() => {
    const data = withDataSplits(store.data, splitList, todayKst());
    return data === store.data ? store : { ...store, data };
  }, [store, splitList]);
  // a split the records keep (store.js splits) that today's data.json does not list: said loudly, once each (it stays in use:
  // the records were saved with it). data.json lists the last 3 years of splits, so an older one is expected to be missing.
  const splitsSaid = useRef(new Set());
  useEffect(() => {
    if (load.status !== "ok") return;
    for (const x of storedNotInData(store.data, splitList)) {
      const k = `${x.id}|${x.t}|${x.date}|${x.r}`;
      if (splitsSaid.current.has(k)) continue;
      splitsSaid.current.add(k);
      console.warn(`[v2] ${x.id}: the stored split of ${x.t} on ${x.date} (x${x.r}) is not in today's data.json splits (it lists the last 3 years); the records still read with it`);
    }
  }, [store.data, splitList, load.status]);
  // round-2 review: a data.json split that a saved record already lies before is stored with the records at once (not only
  // with the next record), so a buy-and-hold portfolio keeps it even after data.json stops listing it. Nothing a user sees
  // changes (the screens already read the records with it); only when the records can be written, and said once.
  useEffect(() => {
    if (load.status !== "ok" || !store.writable || store.locked) return;
    const r = withStoredSplits(view.data);
    if (!r.added.length) return;
    console.info("[v2] stock splits stored with the records they apply to: " + r.added.map((x) => `${x.id} ${x.t} ${x.date} x${x.r}`).join(", "));
    setStoreData(r.data);
  }, [view, load.status]);
  // v19.6a: 내 수익 of a portfolio that exists (else 포트폴리오)
  const returnsDeck = tab === "portfolio" && loc.returns ? view.data.decks.find((d) => d.id === loc.returns) || null : null;
  const pad = wide ? SPACE(10) : TAB_H + 32;
  const screen = (() => {
    const store = view;
    if (inBuild) {
      return <Build load={load} builder={builder} setBuilder={setBuilder} onExit={() => router.back("portfolio")} goToday={doneToHome} goPortfolio={doneToPortfolio}
        store={store} setStoreData={setStoreData} coach={builder.step === 1 && builder.stage === "steps" ? coach : null} onImport={openImport} />;
    }
    if (inImport) {
      return <Import load={load} store={store} setStoreData={setStoreData} importer={importer} setImporter={setImporter} onExit={() => router.back("portfolio")}
        onSaved={importSaved} />;
    }
    if (inWhy) return <Why load={load} store={store} setStoreData={setStoreData} pad={pad} target={why} onBack={() => router.back("home")} />;
    if (rulesDeck) return <Limits key={rulesDeck.id} deck={rulesDeck} store={store} setStoreData={setStoreData} pad={pad} onBack={() => router.back("portfolio")} />;
    if (returnsDeck) return <Returns key={returnsDeck.id} deck={returnsDeck} load={load} store={store} pad={pad} onBack={() => router.back("portfolio")} />;
    if (tab === "portfolio") {
      return <Portfolio load={load} store={store} setStoreData={setStoreData} pad={pad} go={go} onImport={openImport}
        onRules={(id) => router.go("portfolio", "rules/" + id)} onReturns={(id) => router.go("portfolio", "returns/" + id)} />;
    }
    if (tab === "stocks" && loc.code && !loc.about) {
      return <Company load={load} store={store} setStoreData={setStoreData} pad={pad} code={loc.code} ctab={loc.ctab} disc={discView} nav={coNav} />;
    }
    if (tab === "stocks") return <Stocks load={load} store={store} pad={pad} q={wide ? stockQ : null} ownQ={phoneQ} setOwnQ={setPhoneQ} />;
    if (tab === "market") return <Market load={load} pad={pad} />;
    return <Home load={load} store={store} setStoreData={setStoreData} pad={pad} go={go} onWhy={openWhy} welcome={welcome} disc={discView} />;
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
          {wide && <SideMenu tab={tab} about={loc.about} load={load} go={go} onAbout={router.openAbout} onGuide={replayGuide} theme={theme} />}
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
                {/* The held publish's line (HeldContext) is for the screen only: the ☰ menu and the PC left menu keep their date
                    line as it is (Jack has not decided on them, review 2026-11-08). */}
                <HeldContext.Provider value={heldHere}>
                  <ErrorBoundary key={screenKey} name={tab} pad={ownBar ? undefined : pad}>{screen}</ErrorBoundary>
                </HeldContext.Provider>
                {!wide && <MenuSheet open={loc.menu && !loc.about} load={load} onClose={router.closeMenu} onAbout={router.openAbout} onHome={goHome} onGuide={replayGuide}
                  tabH={ownBar ? 0 : TAB_H} theme={theme} />}
                {!wide && !ownBar && <TabBar value={tab} onChange={go} />}
              </ErrorBoundary>
            </div>
          </div>
        </LayoutContext.Provider>
      </NavContext.Provider>
    </ModeContext.Provider>
  );
}
