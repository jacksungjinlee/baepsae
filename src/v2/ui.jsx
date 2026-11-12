// Shared pieces for the 2.0 screens, built on the v18.1 tokens and components. No Korean here: text comes in props
// or from src/copy/v2.js.
import React, { createContext, useContext, useEffect, useState } from "react";
import { COLOR, FONT, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, SELECTED, TOPIC_CHIP, ICON_CHIP } from "../ui/tokens.js";
import { CARD_PICS, DECK_PICS, PIC_SIZES } from "./pictures.js";
import { Icon } from "../ui/icons.jsx";
import { StatusChip, Button } from "../ui/components.jsx";
import { C, fill, mdText, staleText, ownCloseText } from "./format.js";
import { hasOldAppRecords } from "./store.js";
import { ABOUT_HASH } from "../links.js";

export const tx = (size, weight, color, extra) => ({ fontFamily: FONT, fontSize: size, fontWeight: weight, color, lineHeight: 1.5,
  letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums", margin: 0, ...extra });
const tap = { WebkitTapHighlightColor: "transparent", cursor: "pointer", fontFamily: FONT, padding: 0 };
export const TAB_H = TOUCH + SPACE(3);

// The current app (예전 뱁새, src/v2/routes.js). The ☰ menu's 예전 뱁새 보기, 용어 사전 and 데이터 출처 and 시장's two buttons
// open it (v19.0c deep links: routes.js OLD_LINKS). Part F: the main address shows 2.0. v19.1a: companies open the 2.0
// company page instead of the old app's 기업분석.
export { OLD_APP } from "./routes.js";

// Which page this is: the live app or the preview with fictional example data (app-preview.html).
export const ModeContext = createContext({ preview: false });
export const useMode = () => useContext(ModeContext);

// The ☰ button's action (v19.0c, src/v2/app.jsx): openMenu, and whether the menu is open. Without it no ☰ is drawn.
// openStock(t) (v19.1a): open the 2.0 company page of a stock (null outside the app shell: rows are then not tappable).
// goHome() (v19.5a): the 뱁새 logo's action (null outside the app shell: the link's own #home then does it).
export const NavContext = createContext({ openMenu: null, menuOpen: false, openStock: null, goHome: null });
export const useNav = () => useContext(NavContext);

// A later publish waits under the draft on screen (Jack, 2026-11-08; app.jsx, hold.js heldOn): true only while 후보 고르기,
// 매수 계획 or 가진 종목 넣기 is on screen and a newer publish is held for it (and saving or leaving would let it in). The
// screen's date line (and 점검's stale note) then say "새 데이터가 들어왔어요. 이 화면을 저장하거나 나가면 새 데이터로
// 바뀌어요." instead of the stale words. app.jsx provides it around the screen only: the ☰ menu and the PC left menu keep
// their date line as before. False everywhere else and when nothing is held.
export const HeldContext = createContext(false);
export const useHeld = () => useContext(HeldContext);

// PC layout (v19.0d, Layout C PC step 1). From 1024 px wide: a 240 px left menu (nav.jsx SideMenu) with the four tabs,
// the menu links and the data-date box, and a top bar with the search field (nav.jsx TopBar); no bottom tab bar, no ☰.
// 홈 and 시장 use two columns (content up to 1000 px), every other screen one column (up to 720 px). Fixed bars (the
// action bar, sheets) sit right of the left menu. Below 1024 px everything is the phone layout, unchanged.
export const WIDE_MIN = 1024;
export const SIDE_W = 240;
export const PC_MAX = { one: 720, two: 1000 };    // content width on PC (the page's side padding comes on top)
export const PC_PAD = SPACE(8);
const WIDE_QUERY = `(min-width: ${WIDE_MIN}px)`;
function wideNow() {
  try {
    if (window.matchMedia) return window.matchMedia(WIDE_QUERY).matches;
    return window.innerWidth >= WIDE_MIN;
  } catch (e) { return false; }
}
// true from 1024 px wide (follows the window as it is resized). Used once, by the app shell: screens read LayoutContext.
export function useWide() {
  const [wide, setWide] = useState(wideNow);
  useEffect(() => {
    const on = () => setWide(wideNow());
    let mq = null;
    try { mq = window.matchMedia ? window.matchMedia(WIDE_QUERY) : null; } catch (e) { mq = null; }
    if (mq && mq.addEventListener) mq.addEventListener("change", on);
    else if (mq && mq.addListener) mq.addListener(on);
    else window.addEventListener("resize", on);
    on();
    return () => {
      if (mq && mq.removeEventListener) mq.removeEventListener("change", on);
      else if (mq && mq.removeListener) mq.removeListener(on);
      else window.removeEventListener("resize", on);
    };
  }, []);
  return wide;
}
// true from ROOMY_MIN (1200 px) wide: room for 종목 순위 in 홈's right column (Jack, 2026-11-12: from 1024 to 1199 px it sits at the
// end of the main column instead). Follows the window as it is resized.
export const ROOMY_MIN = 1200;
export function useRoomy() {
  const q = `(min-width: ${ROOMY_MIN}px)`;
  const now = () => { try { return window.matchMedia ? window.matchMedia(q).matches : window.innerWidth >= ROOMY_MIN; } catch (e) { return false; } };
  const [roomy, setRoomy] = useState(now);
  useEffect(() => {
    const on = () => setRoomy(now());
    let mq = null;
    try { mq = window.matchMedia ? window.matchMedia(q) : null; } catch (e) { mq = null; }
    if (mq && mq.addEventListener) mq.addEventListener("change", on);
    else if (mq && mq.addListener) mq.addListener(on);
    else window.addEventListener("resize", on);
    on();
    return () => {
      if (mq && mq.removeEventListener) mq.removeEventListener("change", on);
      else if (mq && mq.removeListener) mq.removeListener(on);
      else window.removeEventListener("resize", on);
    };
  }, []);
  return roomy;
}
export const LayoutContext = createContext({ wide: false });
export const useLayout = () => useContext(LayoutContext);
// Which column of Cols a piece sits in on PC: "main", "side" (the narrow one) or "full" (it stands alone). null elsewhere.
const ColContext = createContext(null);
export const useCol = () => useContext(ColContext);
// The page width on PC: content + side padding (box-sizing is border-box). Every screen, the top bar and the action bar
// sit in one frame as wide as the two-column page (centred right of the left menu), and a one-column page keeps to the
// frame's left edge: the search field and the first card start at the same place on every tab.
export const pcWidth = (cols) => (cols === 2 ? PC_MAX.two : PC_MAX.one) + 2 * PC_PAD;
export function PcFrame({ children, style, ...rest }) {
  return <div {...rest} style={{ maxWidth: pcWidth(2), margin: "0 auto", ...style }}>{children}</div>;
}

// "예시 데이터" label: on every screen of the preview page, right in the app bar.
export function SampleLabel() {
  return <span data-ui-v2="sample-label"><StatusChip tone="neutral">{C.app.sample}</StatusChip></span>;
}

// cols: 2 on 홈 and 시장 (two columns on PC: see Cols). On the phone every page is one column, up to 520 px.
export function Page({ children, pad = SPACE(6), cols = 1 }) {
  const { wide } = useLayout();
  if (wide) {
    return (
      <PcFrame>
        <main data-ui-v2="page" data-cols={cols} style={{ maxWidth: pcWidth(cols), padding: `${SPACE(2)}px ${PC_PAD}px ${pad}px` }}>{children}</main>
      </PcFrame>
    );
  }
  return <main style={{ maxWidth: 520, margin: "0 auto", padding: `${SPACE(4)}px ${SPACE(4)}px ${pad}px` }}>{children}</main>;
}

// Two columns on PC (홈 and 시장: the wider main column on the left, the side column on the right, as on the boards
// PcHome · PcMarket); on the phone the same pieces one after the other, as before. When only one of the two has
// anything to show, it takes the whole width.
export function Cols({ main, side }) {
  const { wide } = useLayout();
  const has = (x) => (Array.isArray(x) ? x.some(Boolean) : !!x);
  if (!wide) return <>{main}{side}</>;
  if (!has(main) || !has(side)) return <ColContext.Provider value="full"><div data-ui-v2="cols" data-n="1">{main}{side}</div></ColContext.Provider>;
  return (
    <div data-ui-v2="cols" data-n="2" style={{ display: "grid", gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)", columnGap: SPACE(5), alignItems: "start" }}>
      <ColContext.Provider value="main"><div data-ui-v2="col-main" style={{ minWidth: 0 }}>{main}</div></ColContext.Provider>
      <ColContext.Provider value="side"><div data-ui-v2="col-side" style={{ minWidth: 0 }}>{side}</div></ColContext.Provider>
    </div>
  );
}

export function Card({ children, style, ...rest }) {
  return <section {...rest} style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(5), marginTop: SPACE(3), ...style }}>{children}</section>;
}

// v19.5 Part B: the 뱁새 logo (the 뱁이 mark and the 뱁새 wordmark) opens 홈 wherever it shows — the phone header, the PC
// left menu and the ☰ menu sheet; on 홈 it scrolls to the top (router.go). A real link (#home) named "뱁새, 홈으로" (C.app.homeLink)
// for screen readers; a plain click goes through the router (one history entry, the menu closes), a modified click is left to the
// browser (new tab). The wordmark stays the page's <h1> inside the link.
export function HomeLink({ onHome, children, style }) {
  const click = (e) => {
    if (!onHome || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    onHome();
  };
  return (
    <a href="#home" data-ui-v2="home-link" aria-label={C.app.homeLink} onClick={click}
      style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH, minWidth: TOUCH, color: "inherit", textDecoration: "none", ...style }}>
      {children}
    </a>
  );
}

// App bar: the name 뱁새 on every screen (v19.0: the page title is now the long "뱁새 — 내 기준으로 …", so the header shows
// only C.app.brand), the preview label, optional back button, and the ☰ menu button on the right (v19.0c, board NavC:
// the Phosphor "list" icon, never the ☰ character). 예전 뱁새 보기 and 찾기 moved from here into the menu and the 종목 tab.
// Logo (v19.0b, Part B): Jack's mark (baepi-mark, 28 px on phone) + the "뱁새" wordmark at 22 px / 800. The mark is
// decorative (alt ""): the wordmark next to it says the name. A back button takes the mark's place.
// menu = false: no ☰ (소개 is a page of its own, closed with its back button).
// PC (v19.0d): the left menu carries the logo, the name and the menu links, and the top bar the preview label, so the app
// bar keeps only a back button (and nothing at all on a screen without one).
export function AppBar({ onBack, backLabel, right, menu = true }) {
  const { preview } = useMode();
  const nav = useContext(NavContext);
  const { wide } = useLayout();
  if (wide) {
    if (!onBack && !right) return null;
    return (
      <header data-ui-v2="app-bar" data-wide="1" style={{ display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH }}>
        {onBack && (
          <button type="button" aria-label={backLabel} onClick={onBack}
            style={{ ...tap, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center", marginLeft: -SPACE(3) }}>
            <Icon name="back" tone="on" />
          </button>
        )}
        <span style={{ flex: 1 }} />
        {right}
      </header>
    );
  }
  return (
    <header data-ui-v2="app-bar" style={{ display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH,
      ...(preview ? { position: "sticky", top: 0, zIndex: 40, background: COLOR.page, margin: `0 -${SPACE(4)}px`, padding: `0 ${SPACE(4)}px` } : {}) }}>
      {onBack && (
        <button type="button" aria-label={backLabel} onClick={onBack}
          style={{ ...tap, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center", marginLeft: -SPACE(3) }}>
          <Icon name="back" tone="on" />
        </button>
      )}
      <HomeLink onHome={nav.goHome}>
        {!onBack && <img data-ui-v2="logo-mark" src={IMG.mark} alt="" width={28} height={28} style={{ objectFit: "contain", flexShrink: 0, marginRight: -SPACE(1) }} />}
        <h1 data-ui-v2="wordmark" style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { minWidth: 0, lineHeight: 1.2, letterSpacing: "-0.04em" })}>{C.app.brand}</h1>
      </HomeLink>
      <span style={{ flex: 1 }} />
      {preview && <SampleLabel />}
      {right}
      {menu && nav.openMenu && (
        <button type="button" data-ui-v2="menu-button" aria-label={C.menu.label || C.app.tabsLabel} aria-haspopup="dialog" aria-expanded={nav.menuOpen ? "true" : "false"}
          onClick={nav.openMenu}
          style={{ ...tap, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center", marginRight: -SPACE(2), flexShrink: 0 }}>
          <Icon name="list" tone="on" />
        </button>
      )}
    </header>
  );
}

export function ScreenTitle({ children, sub }) {
  return (
    <div style={{ marginTop: SPACE(2) }}>
      <h2 style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3, whiteSpace: "pre-line" })}>{children}</h2>
      {sub && <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{sub}</p>}
    </div>
  );
}

// "10월 30일 기준" — the content date. Publication late (data.js freshness: staleAfter passed, or more than 4 days since
// the publish): in warning colour "· 갱신이 늦어지고 있어요" when n <= 1, "· N일째 갱신이 멈췄어요" from n = 2 (format.staleText,
// Jack 2026-11-07; n counts from the morning the publish was due when data.json has nextPub, else from the last publish).
// While a later publish waits under the draft on screen (HeldContext, Jack 2026-11-08), the stale words are not true: the
// date stays and, on its own line in the same warning colour, "새 데이터가 들어왔어요. 이 화면을 저장하거나 나가면 새
// 데이터로 바뀌어요." (data-held; data-stale still says whether the data on screen is stale).
export function DateLine({ date, fresh, style }) {
  const wait = useHeld();
  const md = mdText(date);
  if (!md) return null;
  const stale = !!(fresh && fresh.stale);
  const warn = stale || wait;
  return (
    <div data-ui-v2="date-line" data-stale={stale ? "1" : "0"} data-held={wait ? "1" : undefined}
      style={tx(SIZE.xs, warn ? WEIGHT.bold : WEIGHT.regular, warn ? COLOR.watch : COLOR.text2, { marginTop: SPACE(1), ...style })}>
      <span>{fill(C.app.asOf, { md })}</span>
      {stale && !wait && <span>{" · "}</span>}
      {stale && !wait && <span>{staleText(fresh.days)}</span>}
      {wait && <span data-ui-v2="held-line" style={{ display: "block", marginTop: SPACE(1), lineHeight: 1.45, wordBreak: "keep-all" }}>{C.app.heldNew}</span>}
    </div>
  );
}

// 뱁이 pictures 2.0 may show (v19.0 Part C, CLAUDE.md): only on the first visit, empty states, the load-failure screen,
// 준비 중 blocks, learning cards, the share card, the 소개 page and the link preview, never on a card that shows numbers
// and never beside a verdict (verdicts carry a state icon: src/ui/components.jsx StateIcon). Numbers means money, prices,
// returns, weights and scores; a date label or a count of stocks is not one (Jack, 2026-11-04). The v19 files are Jack's
// art scaled to twice their largest display size by tools/resize_assets.py (originals in docs/design/v19/assets).
// Alt texts: src/copy/v2.js (Jack, 2026-11-04).
export const IMG = {
  mark: "baepi-mark.webp",            // logo, 28 px
  build: "baepi-16-build.webp",       // 포트폴리오 만들기 start and the first-visit 홈 (screens without numbers), 92 px
  empty: "baepi-15-portfolio.webp",   // empty 포트폴리오, 112 px
  error: "baepi-20-error.webp",       // load failure, 120 px
  wip: "baepi-21-wip.webp",           // a whole block that is 준비 중, 64 px
  happy: "baepi-5.png",               // 기록했어요 sheet (a count of stocks only, no money), 64 px — Jack's original, as before
};

export function Mascot({ src, alt, size, style }) {
  return <img data-ui-v2="mascot" src={src} alt={alt || ""} width={size} height={size} style={{ objectFit: "contain", flexShrink: 0, ...style }} />;
}

// v19.3b Part A: a 기준 or template picture on its tint chip (src/v2/pictures.js). It always sits next to a visible name,
// so the picture is decorative (alt ""). dim: a 기준 that is 준비 중 (its data does not exist yet). The picture is never
// recoloured or filtered: dimming is the chip's opacity only.
export function PicChip({ pic, size = "row", dim = false, style, ...rest }) {
  if (!pic) return null;
  const z = PIC_SIZES[size] || PIC_SIZES.row;
  return (
    <span {...rest} data-ui-v2="pic-chip" data-topic={pic.topic || "none"} data-dim={dim ? "1" : undefined}
      style={{ width: z.chip, height: z.chip, borderRadius: ICON_CHIP.radius, background: (pic.topic && TOPIC_CHIP[pic.topic]) || ICON_CHIP.bg,
        display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0, opacity: dim ? 0.45 : 1, ...style }}>
      <img src={pic.src} alt="" width={z.pic} height={z.pic} decoding="async" style={{ display: "block", width: z.pic, height: z.pic, objectFit: "contain" }} />
    </span>
  );
}
export const CardPic = ({ id, ...rest }) => <PicChip pic={CARD_PICS[id]} data-card-pic={id} {...rest} />;
export const DeckPic = ({ id, ...rest }) => <PicChip pic={DECK_PICS[id]} data-deck-pic={id} {...rest} />;

// "가치 82점 · 배당 70점" (포트폴리오 만들기의 미리 보기 · 후보 고르기 · 매수 계획): each 기준 with its picture in front.
// list: [[card id, score], …]. Inline, so the words, their order and the text read out are the same as before; a piece
// (picture, name, score) never breaks inside, the line wraps between pieces on a narrow screen; the " · " goes with the
// next piece, so no line ends with a dangling dot (320 px).
export function CardScores({ list, style }) {
  return (
    <span data-ui-v2="card-scores" style={style}>
      {list.map(([id, v], i) => (
        <React.Fragment key={id}>
          {i ? " " : ""}
          <span style={{ whiteSpace: "nowrap" }}>
            {i ? "· " : ""}
            <CardPic id={id} style={{ verticalAlign: "middle", marginRight: SPACE(1) }} />
            <span>{C.build.cards[id].name}</span>{" "}<span>{fill(C.build.s1.score, { score: Math.round(v) })}</span>
          </span>
        </React.Fragment>
      ))}
    </span>
  );
}

// picture = false: the screen also shows figures (포트폴리오 with saved records, 시장), so the 뱁이 stays off (CLAUDE.md: never on
// a screen that shows numbers). The message is the same either way.
// inline (v19.3e, 홈's 오늘 볼 것): the same message as a line in a row (left-aligned, no padding, no picture), beside the
// icon chip that says what failed to load.
export function LoadFail({ picture = true, inline = false }) {
  if (inline) {
    return (
      <div data-ui-v2="load-fail" data-picture="0" data-inline="1" role="alert">
        <p style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { wordBreak: "keep-all" })}>{C.app.loadFail}</p>
      </div>
    );
  }
  return (
    <div data-ui-v2="load-fail" data-picture={picture ? "1" : "0"} role="alert" style={{ textAlign: "center", padding: `${picture ? SPACE(10) : SPACE(6)}px ${SPACE(4)}px` }}>
      {picture && <Mascot src={IMG.error} alt={C.app.loadFailAlt} size={120} style={{ display: "inline-block" }} />}
      <p style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { marginTop: picture ? SPACE(3) : 0 })}>{C.app.loadFail}</p>
    </div>
  );
}

export function PendingChip() {
  return <span data-ui-v2="pending"><StatusChip tone="neutral">{C.app.pending}</StatusChip></span>;
}

// A whole block that is 준비 중 (not one line of it): the hard-hat 뱁이 next to the 준비 중 chip, nothing else.
export function PendingBlock(props) {
  return (
    <Card {...props}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <Mascot src={IMG.wip} alt={C.app.pendingAlt} size={64} />
        <PendingChip />
      </div>
    </Card>
  );
}

// The disclaimer and a 소개 link (v19.0 Part D, Jack 2026-11-03): the maker's credit moved to the 소개 page (#about).
// The link's tap area is padded out to the 44px touch size without moving the text around it.
export function Footer() {
  return (
    <footer data-ui-v2="footer" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(8) })}>
      <div>
        {C.app.footer}{" · "}
        <a data-ui-v2="about-link" href={ABOUT_HASH} style={{ color: "inherit", textDecoration: "underline", textUnderlineOffset: 3,
          display: "inline-block", padding: `${SPACE(4)}px ${SPACE(2)}px`, margin: `-${SPACE(4)}px -${SPACE(2)}px`, WebkitTapHighlightColor: "transparent" }}>{C.app.aboutLink}</a>
      </div>
    </footer>
  );
}

// v19.1c (Jack, 2026-11-07): the note under a list or a total that includes a US stock priced at an earlier close (data.json
// pxd): "AAPL 가격은 11월 4일 종가예요." (format.ownCloseText). groups: stocklist.js ownCloseGroups. Nothing when none is there.
export function OwnCloseNote({ groups, style, ...rest }) {
  const text = groups && groups.length ? ownCloseText(groups) : null;
  if (!text) return null;
  return <Note data-ui-v2="own-close" data-ts={groups.flatMap((g) => g.ts).join(",")} style={style} {...rest}>{text}</Note>;
}

export function Note({ children, tone, style, ...rest }) {
  const t = tone === "watch" ? { color: COLOR.watch, bg: COLOR.watchBg } : null;
  return (
    <div {...rest} role={tone ? "status" : undefined} style={tx(SIZE.xs, t ? WEIGHT.semi : WEIGHT.regular, t ? t.color : COLOR.text2, {
      marginTop: SPACE(2), ...(t ? { background: t.bg, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px` } : {}), ...style })}>{children}</div>
  );
}

// For visitors who made portfolios in the current app: they are still there, behind the menu's "예전 뱁새 보기".
// Live page only (the preview has no such link). Shown on 포트폴리오 만들기's first screen and on 포트폴리오.
export function OldAppNote() {
  const { preview } = useMode();
  const [has] = useState(() => !preview && hasOldAppRecords());
  return has ? <Note data-ui-v2="old-app-note">{C.app.oldAppNote}</Note> : null;
}

export function Label({ children, style }) {
  return <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { marginBottom: SPACE(2), ...style })}>{children}</div>;
}

// On/off switch row (the v18.1 set has no switch): label, second line, count on the right.
export function Toggle({ on, onChange, label, sub, side, disabled, chip }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => !disabled && onChange(!on)}
      style={{ ...tap, width: "100%", minHeight: TOUCH + SPACE(3), border: "none", borderBottom: `1px solid ${COLOR.line}`, background: "none",
        display: "flex", alignItems: "center", gap: SPACE(3), textAlign: "left", padding: `${SPACE(2)}px 0`, cursor: disabled ? "default" : "pointer" }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, disabled ? COLOR.text2 : COLOR.ink, { display: "block" })}>{label}</span>
        <span style={{ display: "flex", flexWrap: "wrap", gap: SPACE(2), alignItems: "center" }}>
          {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{sub}</span>}
          {chip}
        </span>
      </span>
      {side != null && <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{side}</span>}
      <span aria-hidden="true" style={{ width: SPACE(11), height: SPACE(6) + 2, borderRadius: 999, background: on ? COLOR.ink : COLOR.border, position: "relative", flexShrink: 0, opacity: disabled ? 0.5 : 1 }}>
        <span style={{ position: "absolute", top: 3, left: on ? SPACE(5) + 3 : 3, width: SPACE(5), height: SPACE(5), borderRadius: 999, background: COLOR.surface, transition: "left .15s" }} />
      </span>
    </button>
  );
}

// Fixed bar above the bottom edge: summary on the left, one main button. PC: right of the left menu, lined up with the
// one-column page above it.
export function ActionBar({ summary, action, onAction, disabled }) {
  const { wide } = useLayout();
  const row = (
    <div style={{ maxWidth: wide ? PC_MAX.one : 520, margin: wide ? 0 : "0 auto", display: "flex", alignItems: "center", gap: SPACE(3) }}>
      <div style={{ flex: 1, minWidth: 0, ...tx(SIZE.xs, WEIGHT.semi, COLOR.text2) }}>{summary}</div>
      <div style={{ flexShrink: 0, minWidth: SPACE(30), maxWidth: "60%" }}>
        <Button onClick={onAction} disabled={disabled} style={{ padding: `0 ${SPACE(3)}px` }}>{action}</Button>
      </div>
    </div>
  );
  return (
    <div data-ui-v2="action-bar" style={{ position: "fixed", left: wide ? SIDE_W : 0, right: 0, bottom: 0, zIndex: 50, background: COLOR.surface, borderTop: `1px solid ${COLOR.line}`,
      padding: `${SPACE(3)}px ${wide ? 0 : SPACE(4)}px calc(${SPACE(3)}px + env(safe-area-inset-bottom))` }}>
      {wide ? <PcFrame style={{ padding: `0 ${PC_PAD}px` }}>{row}</PcFrame> : row}
    </div>
  );
}

// One rule line in 내 투자 규칙. 매수 계획 (before purchase) evaluates nothing, so no rule gets a green check there: a
// rule we can check shows the rule icon with its number and report; a rule we cannot check yet shows a dot and 준비 중.
// 포트폴리오 (Part C) passes today's result as state: "ok" (check icon), "watch" (alert), "broken" (cross), or nothing
// (the rule icon: in place, nothing new since the purchase report), plus an optional chip label.
// Icon colours only from the v19.0b table (ICON_TONE): the state shows in the circle behind the icon.
const STATE_ICON = { ok: { name: "check", tone: "ok", bg: COLOR.okBg }, watch: { name: "alert", tone: "on", bg: COLOR.watchBg },
  broken: { name: "close", tone: "onNavy", bg: COLOR.brokenBg } };
export function RuleLine({ name, now, limit, source, pending, note, state, stateLabel }) {
  const ic = pending ? { name: "dot", tone: "off", bg: COLOR.neutralBg } : STATE_ICON[state] || { name: "rule", tone: "on", bg: COLOR.neutralBg };
  return (
    <div data-ui-v2="rule-line" data-check={pending ? "pending" : "checked"} data-icon={ic.name} data-state={pending ? undefined : state || undefined}
      style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start", padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <span style={{ width: SPACE(7), height: SPACE(7), borderRadius: 999, background: ic.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={ic.name} size={16} tone={ic.tone} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{name}</div>
        {pending ? <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.app.notChecked}</div>
          : <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{[now, limit].filter(Boolean).map((x, i) => <span key={i}>{i ? " · " : ""}{x}</span>)}</div>}
        {note && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.watch)}>{note}</div>}
        {source && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{source}</div>}
      </div>
      {pending && <PendingChip />}
      {!pending && stateLabel && <StatusChip tone={state === "broken" ? "broken" : state === "watch" ? "watch" : "ok"}>{stateLabel}</StatusChip>}
    </div>
  );
}

// Radio choices that wrap onto more rows on narrow screens (the 5 Korea:US options would wrap inside a segmented bar).
// v19.0b: the chosen one has the warm-grey selection background and a 2 px navy border (never apricot).
export function ChoiceGrid({ options, value, onChange, label, min = 96 }) {
  return (
    <div data-ui-v2="choice-grid" role="radiogroup" aria-label={label}
      style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))`, gap: SPACE(2) }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)} data-selected={on ? "1" : undefined}
            style={{ ...tap, minHeight: TOUCH, borderRadius: RADIUS.sm, padding: `0 ${SPACE(2)}px`, whiteSpace: "nowrap",
              border: on ? `2px solid ${COLOR.ink}` : `1px solid ${COLOR.border}`, background: on ? SELECTED.background : COLOR.surface,
              ...tx(SIZE.xs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text2) }}>{o.label}</button>
        );
      })}
    </div>
  );
}

export function TextInput({ label, value, onChange, inputMode, placeholder, type = "text", ariaLabel, invalid, max }) {
  return (
    <label style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", marginTop: SPACE(3) })}>
      {label}
      <input type={type} value={value} inputMode={inputMode} placeholder={placeholder} aria-label={ariaLabel} onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid ? "true" : undefined} max={max}
        style={{ display: "block", width: "100%", marginTop: SPACE(1), minHeight: TOUCH, border: invalid ? `2px solid ${COLOR.watch}` : `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm,
          padding: `0 ${SPACE(3)}px`, background: COLOR.surface, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
    </label>
  );
}

export { tap };
