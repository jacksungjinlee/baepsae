// ================= 홈 · 종목 순위 card (v19.5b, docs/tasks/v19.5-home-lists-and-icon.md Part A) =================
// Boards: docs/design/v19.5/reference/HomeMovers2 (시가총액) · 2b (기준별) · 2c (업종별 등락). The lists themselves are pure
// (ranks.js); this file draws them. No Korean here: every word comes from src/copy/v2.js (C.rank and the keys it reuses).
//
// Where: 홈, below the 시장 tiles (phone: after 시장 한눈에; PC from 1024 px: the right column under it, 7 rows in the window),
// and on 홈's first visit (no saved portfolio) after 포트폴리오 만들기. That screen shows numbers now, so it carries no 뱁이
// (the v19.3c welcome screen has the 뱁이; CLAUDE.md: 뱁이 never on a screen with numbers). 전체 보기 opens the 종목 tab with the
// same choice as a still list of 30 (full).
//
// The window (home): the top 10 rows, 58 px each, 5 in view (PC 7) with a soft fade at the top and the bottom. The list is
// drawn twice; the second copy is aria-hidden and its buttons are out of the tab order, so screen readers and the keyboard get
// the list once. It moves upward 32 s per loop, linear, holding #1 at the top for the first 7% (about 2 s), and stops while it
// is touched, hovered or has focus, while it is off screen (IntersectionObserver) and while the page is hidden. It never
// moves under prefers-reduced-motion, on stale data (the app's own stale rule, load.fresh: the date line shows the real
// content date either way) or when the list fits the window: then it is a still list of 5 (PC 7) with 전체 보기.
// Load failure: the screen's own load-failure message (the card is only drawn on loaded data); a market without a readable
// close date shows the same message inside the card, never an empty box.
import React, { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, TOUCH } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { C, fill, nf, p1, mdText } from "./format.js";
import { LoadFail, OwnCloseNote, tx, tap, useLayout, useMode } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { useStockTap } from "./stocks.jsx";
import { ownCloses } from "./stocklist.js";
import { CARD_PICS } from "./pictures.js";
import { eokText, signedPct } from "./deckcalc.js";
import { yieldText } from "./cofmt.js";
import { num, todayD1, sameCompany } from "./engine.js";
import { RANK_TOP, RANK_FULL, CRIT, RANK_CHIPS, rankRows, pointsDeck, chipsFor, shownChip, groupWord, groupList,
  chipState, listReport, oneReportYear, readPick, savePick, RANK_KEY, PREVIEW_RANK_KEY } from "./ranks.js";

export const ROW_H = 58;                 // px per row (board)
export const ROLL_S = 32;                // seconds per loop
export const SHOWN = { phone: 5, pc: 7 };
const DATE = /^\d{4}-\d{2}-\d{2}$/;
// Focus rings: a row inside the clipped window draws its ring inside its own box (the window would cut one drawn outside), and the
// window itself (a stop for the keyboard) gets the app's navy ring (template.html draws it for buttons and links only).
const ROLL_CSS = "@keyframes v2-rank-roll { 0%, 7% { transform: translateY(0); } 100% { transform: translateY(-50%); } }"
  + ' [data-ui-v2="rank-row"] > button:focus-visible { outline: 2px solid #1C2B45; outline-offset: -3px; border-radius: 12px; }'
  + ' [data-ui-v2="rank-window"]:focus-visible { outline: 2px solid #1C2B45; outline-offset: 2px; }'
  + ` [data-ui-v2="rank-track"][data-roll="1"] { animation: v2-rank-roll ${ROLL_S}s linear infinite; will-change: transform; }`
  + " @media (prefers-reduced-motion: reduce) { [data-ui-v2=\"rank-track\"] { animation: none !important; } }";
const CHIP_LINE = "#E3DED6";             // board: the unselected chip's edge
const WIN_LINE = "#ECE8E1";              // board: the window's edge and the switch's background
// Price red · blue from the value as shown (one decimal): a change that reads "0.0%" is neutral, never red or blue.
const changeColor = (v) => { const r = Math.round(v * 10); return r > 0 ? COLOR.up : r < 0 ? COLOR.down : COLOR.text2; };

// ---------------- the choice, shared by 홈 and the 종목 tab and remembered on this device ----------------
const shared = { key: null, pick: null, jump: false, listeners: new Set() };
const pickOf = (key) => {
  if (shared.key !== key) { shared.key = key; shared.pick = readPick(key); }
  return shared.pick;
};
const subscribe = (f) => { shared.listeners.add(f); return () => shared.listeners.delete(f); };
export function usePick() {
  const { preview } = useMode();
  const key = preview ? PREVIEW_RANK_KEY : RANK_KEY;
  const get = useCallback(() => pickOf(key), [key]);
  const pick = useSyncExternalStore(subscribe, get, get);
  const set = useCallback((p) => {
    shared.pick = { ...p };
    savePick(shared.pick, key);
    shared.listeners.forEach((f) => f());
  }, [key]);
  return [pick, set];
}
// 전체 보기: the 종목 tab's card scrolls itself into view once, with focus on its title.
const askJump = () => { shared.jump = true; };
const takeJump = () => { const j = shared.jump; shared.jump = false; return j; };

// ---------------- motion ----------------
function useReducedMotion() {
  const q = "(prefers-reduced-motion: reduce)";
  const get = () => { try { return window.matchMedia(q).matches; } catch (e) { return false; } };
  const [r, setR] = useState(get);
  useEffect(() => {
    let m;
    try { m = window.matchMedia(q); } catch (e) { return undefined; }
    const on = () => setR(m.matches);
    if (m.addEventListener) m.addEventListener("change", on); else m.addListener(on);
    return () => { if (m.removeEventListener) m.removeEventListener("change", on); else m.removeListener(on); };
  }, []);
  return r;
}

// Why a moving window is not moving right now (null: it moves): touch · hover · focus · offscreen · hidden.
// A finger (or pen) press that held the list for longer than HOLD_MS (to read it) and is let go on a row does not open that row:
// only a short tap does (v19.5b review). The browser has already put focus on the pressed row by then, so the swallowed click
// also takes that focus away: the list moves again as soon as the finger is up, not only after a tap elsewhere. A mouse is not
// held to this: hover already stops the list under it, so any mouse click, slow or quick, opens the row. Keyboard focus on a row
// (focus-visible) also lays the rows out still (kb: the animation is off and the focused row is scrolled into view inside the
// window); when focus leaves, the window scrolls back to the top and the loop starts again with #1.
export const HOLD_MS = 400;
function useRoll(on) {
  const [el, ref] = useState(null);                 // the window element (a callback ref: a new window gets observed too)
  const [hover, setHover] = useState(false);
  const [held, setHeld] = useState(null);          // null, or the pointer type that holds it
  const [focus, setFocus] = useState(false);
  const [kb, setKb] = useState(false);             // a row has keyboard focus
  const press = useRef(null);                      // the last press: { at, up } (performance.now), type (pointerType)
  const [seen, setSeen] = useState(() => typeof IntersectionObserver !== "function");
  const [shown, setShown] = useState(() => { try { return document.visibilityState !== "hidden"; } catch (e) { return true; } });
  useEffect(() => {
    if (!on || !el || typeof IntersectionObserver !== "function") return undefined;
    const io = new IntersectionObserver((es) => setSeen(es.some((e) => e.isIntersecting)), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, [on, el]);
  useEffect(() => {
    const vis = () => setShown(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", vis);
    return () => document.removeEventListener("visibilitychange", vis);
  }, []);
  useEffect(() => {
    if (!held) return undefined;
    // The press ends however it ends: let go (pointerup, touchend), or taken over by the browser to scroll the page
    // (pointercancel, touchcancel).
    const ends = ["pointerup", "pointercancel", "touchend", "touchcancel"];
    const up = () => setHeld(null);
    ends.forEach((t) => window.addEventListener(t, up));
    return () => ends.forEach((t) => window.removeEventListener(t, up));
  }, [held]);
  useEffect(() => { if (!on) { setHover(false); setHeld(null); setFocus(false); setKb(false); } }, [on]);
  // A focused row that leaves the page (a tapped 업종 row opens its companies) fires no blur: after every render the focus
  // state follows where focus really is, so the list never stays stopped for a focus that is gone.
  useEffect(() => {
    let inside = false;
    try { inside = !!el && !!document.activeElement && el.contains(document.activeElement); } catch (e) { inside = false; }
    if (focus !== inside) setFocus(inside);
    if (!inside && kb) { setKb(false); if (el) el.scrollTop = 0; }
  });
  const why = !on ? "off" : held ? "touch" : hover ? "hover" : focus ? "focus" : !seen ? "offscreen" : !shown ? "hidden" : null;
  const handlers = {
    onPointerEnter: (e) => { if (e.pointerType === "mouse") setHover(true); },
    onPointerLeave: (e) => { if (e.pointerType === "mouse") setHover(false); },
    onPointerDown: (e) => {
      press.current = { at: performance.now(), up: null, type: e.pointerType || "mouse" };
      setHeld(e.pointerType === "touch" ? "touch" : e.pointerType || "mouse");
    },
    onPointerUp: () => { if (press.current) press.current.up = performance.now(); },
    // the click that follows a long finger or pen press is swallowed before it reaches the row, and the focus that press gave the
    // row is taken away (blur: the window's onBlur below resets it). Keyboard clicks have no press and mouse clicks are never
    // swallowed, so keyboard focus is never touched here.
    onClickCapture: (e) => {
      const p = press.current;
      press.current = null;
      if (p && p.type !== "mouse" && p.up != null && p.up - p.at > HOLD_MS && performance.now() - p.up < 1000) {
        e.preventDefault();
        e.stopPropagation();
        let a = null;
        try { a = document.activeElement; } catch (x) { a = null; }
        if (a && e.currentTarget.contains(a) && typeof a.blur === "function") a.blur();
      }
    },
    onFocus: (e) => {
      setFocus(true);
      let visible = false;
      try { visible = e.target !== e.currentTarget && e.target.matches(":focus-visible"); } catch (x) { visible = false; }
      if (visible) {
        setKb(true);
        const row = e.target;
        requestAnimationFrame(() => { try { row.scrollIntoView({ block: "nearest" }); } catch (x) { /* ignore */ } });
      }
    },
    onBlur: (e) => {
      if (e.currentTarget.contains(e.relatedTarget)) return;
      setFocus(false);
      setKb(false);
      e.currentTarget.scrollTop = 0;
    },
  };
  return { ref, why, kb, handlers };
}

// ---------------- numbers ----------------
const signed = (v) => signedPct(v);
function critNumber(id, s) {
  const N = C.rank.num, P = C.rank.p;
  switch (id) {
    case "value": return fill(N.pbr, { x: nf(s.pbr, 2) });
    case "profit": return fill(N.roe, { x: p1(s.roe) });
    case "stable":
      if (s.cls === "kr") return fill(N.debt, { x: nf(Math.round(s.debt)) });
      return P.debtUs ? fill(P.debtUs, { x: p1(s.debt) }) : `${p1(s.debt)}%`;
    case "lowVol": return fill(N.vol, { x: p1(s.vol) });
    case "trend": return P.trend ? fill(P.trend, { x: signed(s.mom) }) : signed(s.mom);
    case "growth": return P.growth ? fill(P.growth, { x: signed(s.g3) }) : signed(s.g3);
    default: return "";
  }
}
// The number on a stock row: cap and trading value in 억원 · 조원 (the approved units, deckcalc.eokText; cap is 조원 in
// data.json), 거래 급증 "평소의 {x}배", 기준별 the card's own value, 내 기준 "내 기준 상위 {x}%", 배당수익률 the yield.
function rowNumber(chip, crit, r) {
  const s = r.s;
  switch (chip) {
    case "cap": case "group": return eokText(num(s.cap) * 10000) || "";
    case "val": return eokText(r.v) || "";
    case "surge": return fill(C.rank.surgeX, { x: nf(r.v, 1) });
    case "crit": return critNumber(crit, s);
    case "mine": return r.pct != null ? fill(C.rank.mineX, { x: r.pct }) : "";
    case "div": return yieldText(r.v);
    default: return "";
  }
}

// The report year of the rows on screen (KR): only when every row was read from the same 사업보고서 year (ranks.oneReportYear);
// rows from two years, or a row without one, leave the year out (the close date only), and the console says why.
const yearWarned = new Set();
function reportYear(load, rows) {
  const r = oneReportYear(rows, load.coByT);
  const k = r.years.join(",") + ":" + r.missing;
  if (r.year == null && rows.length && !yearWarned.has(k)) {
    yearWarned.add(k);
    console.info(`[v2] rank card: no report year on the date line: the rows are from ${r.years.join(" and ") || "no"} report year(s)`
      + (r.missing ? `, ${r.missing} without one` : ""));
  }
  return r.year;
}

// ---------------- rows ----------------
const rowStyle = { ...tap, display: "flex", alignItems: "center", gap: 11, width: "100%", height: ROW_H, padding: "0 14px", border: "none",
  borderBottom: `1px solid ${COLOR.line}`, background: "none", textAlign: "left", boxSizing: "border-box" };
const rankNo = (i) => <span data-ui-v2="rank-no" style={tx(SIZE.xs, WEIGHT.heavy, COLOR.text3, { width: 18, textAlign: "center", flexShrink: 0 })}>{i + 1}</span>;

// noInd: the companies of one opened group (their industry is the group's, named above the list): US tickers only.
function StockRow({ i, r, number, copy, onTap, noInd = false }) {
  const s = r.s;
  const d1 = todayD1(s);
  const sub = s.cls === "us" ? [s.t, noInd ? null : s.indName].filter(Boolean).join(" · ") : noInd ? "" : s.indName || "";
  return (
    <div data-ui-v2="rank-row" data-t={s.t} data-cls={s.cls} data-rank={i + 1} data-v={r.v != null ? r.v : undefined} role={copy ? undefined : "listitem"}>
      <button type="button" onClick={onTap} tabIndex={copy ? -1 : undefined} style={rowStyle}>
        {rankNo(i)}
        <CoMark t={s.t} name={s.nk} size={34} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span data-ui-v2="rank-name" style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.35 })}>{s.nk}</span>
          <span style={{ display: "flex", alignItems: "center", gap: SPACE(1) + 2, minWidth: 0, marginTop: 1 }}>
            {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.35, minWidth: 0 })}>{sub}</span>}
            {r.warn && (
              <span data-ui-v2="rank-warn" style={tx(SIZE.xs, WEIGHT.bold, COLOR.watch, { background: COLOR.watchBg, borderRadius: 6, padding: "0 6px", lineHeight: 1.4,
                whiteSpace: "nowrap", flexShrink: 0 })}>{C.rank.warn}</span>
            )}
          </span>
        </span>
        <span style={{ textAlign: "right", flexShrink: 0 }}>
          <span data-ui-v2="rank-num" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block", whiteSpace: "nowrap", lineHeight: 1.35 })}>{number}</span>
          {d1 != null && <span data-ui-v2="rank-change" style={tx(SIZE.xs, WEIGHT.bold, changeColor(d1), { display: "block", whiteSpace: "nowrap", lineHeight: 1.35, marginTop: 1 })}>{signed(d1)}</span>}
        </span>
      </button>
    </div>
  );
}

// 업종별 등락: the group's three largest companies overlapped (one mark per company: a second share class of the same company
// is skipped), "{n}개 중 {k}개 오름 / 내림", the average change today (price red · blue). A tap opens its companies.
function GroupRow({ i, g, copy, onOpen }) {
  const w = groupWord(g);
  const marks = [];
  for (const s of g.members) {
    if (marks.length === 3) break;
    if (!marks.some((x) => sameCompany(x, s))) marks.push(s);
  }
  return (
    <div data-ui-v2="rank-row" data-ind={g.ind} data-rank={i + 1} data-n={g.n} data-k={w.k} data-avg={Math.round(g.avg * 1000) / 1000} role={copy ? undefined : "listitem"}>
      <button type="button" onClick={onOpen} tabIndex={copy ? -1 : undefined} style={rowStyle}>
        {rankNo(i)}
        <span aria-hidden="true" style={{ display: "flex", width: 62, flexShrink: 0 }}>
          {marks.map((s, j) => (
            <span key={s.t} style={{ marginLeft: j ? -9 : 0, borderRadius: 9, boxShadow: `0 0 0 2px ${COLOR.surface}`, display: "flex" }}><CoMark t={s.t} name={s.nk} size={26} /></span>
          ))}
        </span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.35 })}>{g.name || g.ind}</span>
          <span data-ui-v2="rank-count" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block", whiteSpace: "nowrap", lineHeight: 1.35, marginTop: 1 })}>
            {fill(w.up ? C.rank.up : C.rank.down, { n: g.n, k: w.k })}</span>
        </span>
        <span data-ui-v2="rank-num" style={tx(SIZE.sm, WEIGHT.heavy, changeColor(g.avg), { flexShrink: 0, whiteSpace: "nowrap" })}>{signed(g.avg)}</span>
      </button>
    </div>
  );
}

// A chip scrolled into view inside its own scrolling row (the page itself never scrolls for it).
function inView(row, el) {
  if (!row || !el) return;
  try {
    const r = row.getBoundingClientRect(), e = el.getBoundingClientRect(), pad = SPACE(4);
    if (e.left < r.left + pad) row.scrollLeft += e.left - r.left - pad;
    else if (e.right > r.right - pad) row.scrollLeft += e.right - r.right + pad;
  } catch (x) { /* ignore */ }
}

// ---------------- the card ----------------
// load · store: the app's. full: the 종목 tab's still list of 30 (no motion, no 전체 보기). go: the app's tab move (홈 only).
// tapper: the 종목 tab's useStockTap (one 최근 본 종목 list for the whole tab).
export function RankCard({ load, store, full = false, go = null, tapper = null }) {
  const { wide } = useLayout();
  const [pick, setPick] = usePick();
  const own = useStockTap();
  const tp = tapper || own;
  const reduced = useReducedMotion();
  const titleId = useId();
  const headRef = useRef(null);
  const boxRef = useRef(null);
  const chipRow = useRef(null);
  const chipRefs = useRef({});
  const critRow = useRef(null);
  const backRef = useRef(null);
  const [group, setGroup] = useState(null);
  const ok = !!load && load.status === "ok";
  const decks = store && store.data ? store.data.decks : null;
  const deck = useMemo(() => pointsDeck(decks), [decks]);
  const mk = pick.mk;
  // which chips have rows: cheap scans (ranks.chipState); only the chosen chip's list is worked out (below)
  const st = useMemo(() => (ok ? chipState(load, mk, deck) : null), [ok, load, mk, deck]);
  const emptyLine = C.rank.p.empty;
  const critShown = st ? CRIT.map((c) => c.id).filter((id) => emptyLine || st.crit[id]) : [];
  // 거래 급증 without today's figures (no stock with both val and val20) is not "none today": like any other empty list, the chip is
  // not offered (or shows the empty-list line once approved), never the approved "오늘은 … 없어요".
  const surgeNoData = !!(st && st.surge && st.surge.state === "nodata");
  const empty = !st ? [] : RANK_CHIPS.filter((c) => !emptyLine && (c === "surge" ? surgeNoData : c === "crit" ? !critShown.length
    : c === "mine" ? st.mine === false : st[c] === false));
  const chips = chipsFor(mk, !!deck, empty);
  const chip = chips.length ? shownChip(pick.chip, chips) : null;
  const crit = critShown.includes(pick.crit) ? pick.crit : critShown[0] || pick.crit;
  useEffect(() => {
    if (!st) return;
    if (surgeNoData) console.warn(`[v2] rank card: no stock of ${st.surge.of} over the floor has both val and val20 today: the surge chip is ${emptyLine ? "shown empty" : "not offered"}`);
    if (empty.length) console.warn(`[v2] rank card (${mk}): no rows today for ${empty.join(", ")}: chip(s) not offered until an empty-list line is approved (rank.p.empty)`);
    if (!chips.length) console.warn(`[v2] rank card (${mk}): no list has a row: the load-failure message stands in for the list`);
  }, [mk, empty.join(","), surgeNoData, chips.length]);
  const cur = useMemo(() => (ok && chip ? rankRows(load, mk, chip, chip === "crit" ? crit : null, deck) : null), [ok, load, mk, chip, crit, deck]);
  const groups = chip === "ind" && cur ? cur.rows : null;
  const opened = group && groups ? groups.find((g) => g.ind === group) || null : null;
  const rows = !cur ? [] : opened ? groupList(load.data.stocks, mk, opened.ind) : cur.rows;
  const kind = opened ? "group" : cur ? (cur.kind === "ind" ? "ind" : chip) : chip;
  const N = full ? RANK_FULL : RANK_TOP;
  const top = rows.slice(0, N);
  const fit = wide ? SHOWN.pc : SHOWN.phone;
  const stale = ok && !!(load.fresh && load.fresh.stale);
  const dateIso = ok ? (mk === "us" ? load.data.usPxDate : load.data.pxDate) : null;
  const dated = DATE.test(dateIso || "");
  const still = full ? "full" : reduced ? "reduced" : stale ? "stale" : top.length <= fit ? "short" : null;
  const roll = useRoll(ok && dated && !still && top.length > 0);
  const moving = roll.why == null;

  // the chosen chip in view inside its row (never the page), and the chosen 기준 in the 기준별 row; only where a row scrolls (the
  // phone). A row's first paint skips its first chip: a new row starts at its left end, so that chip is already in view, and
  // reading the layout there made 홈's longest task longer. After that, every change (a chip, a market whose chip falls back to
  // the first, a 기준) brings the chosen one into view, wherever the row was scrolled to.
  const rowsSeen = useRef(new WeakSet());
  const keepInView = (row, el, i) => {
    if (wide || !row) return;
    const first = !rowsSeen.current.has(row);
    rowsSeen.current.add(row);
    if (!(first && i <= 0)) inView(row, el);
  };
  useEffect(() => { keepInView(chipRow.current, chipRefs.current[chip], chips.indexOf(chip)); }, [chip, mk, chips.length, wide]);
  useEffect(() => { if (chip === "crit") keepInView(critRow.current, chipRefs.current["crit:" + crit], critShown.indexOf(crit)); }, [chip, crit, mk, wide]);
  // 전체 보기 landed here: this card in view, focus on its title
  useEffect(() => {
    if (!full || !ok || !takeJump()) return;
    try {
      if (boxRef.current) boxRef.current.scrollIntoView({ block: "start" });
      if (headRef.current) headRef.current.focus({ preventScroll: true });
    } catch (e) { /* ignore */ }
  }, [full, ok]);
  // a group opened by tapping: focus on its back button (keyboard and screen readers land on the new list)
  const openedId = opened ? opened.ind : null;
  useEffect(() => { if (openedId && backRef.current) { try { backRef.current.focus({ preventScroll: true }); } catch (e) { /* ignore */ } } }, [openedId]);

  if (!ok) return null;
  const choose = (next) => { setGroup(null); setPick({ ...pick, ...next }); };
  // "{year}년 사업보고서 기준" only on lists of 사업보고서 numbers (ranks.listReport: never 가치, whose PBR uses the latest
  // quarter) and only when every row shown is from that one year (reportYear)
  const report = listReport(mk, chip, crit, deck ? deck.settings.points : null);
  const year = report && !opened ? reportYear(load, top) : null;
  const md = dated ? mdText(dateIso) : null;
  const lines = !chip ? [] : opened ? [C.rank.p.groupLine].filter(Boolean)
    : chip === "val" ? [mk === "us" ? C.rank.line.valUs : C.rank.line.val]
      : chip === "crit" ? [fill(C.rank.line.crit, { card: C.build.cards[crit].name, basis: C.build.cards[crit].basis })]
        : chip === "div" ? [C.rank.line.div, mk === "us" ? C.rpt.divUs : null].filter(Boolean)
          : [C.rank.line[chip]].filter(Boolean);
  // the line in place of an empty list: 거래 급증's approved one, or the empty-list line once approved; nothing else (never an
  // empty white box: without a line, the load-failure message stands in, as when the market has no list at all)
  const emptyText = chip === "surge" ? C.rank.surgeNone : C.rank.p.empty;
  const tapOf = (s) => tp.props({ t: s.t, cls: s.cls, s }).onTap;
  const body = (copy) => top.map((r, i) => (kind === "ind"
    ? <GroupRow key={r.ind} i={i} g={r} copy={copy} onOpen={() => setGroup(r.ind)} />
    : <StockRow key={r.s.t} i={i} r={r} copy={copy} number={rowNumber(kind, crit, r)} onTap={tapOf(r.s)} noInd={kind === "group"} />));
  const shownRows = still && still !== "full" && still !== "short" ? top.slice(0, fit) : top;
  const listKey = [mk, chip, crit, openedId || "", top.length].join("|");
  const win = { position: "relative", borderRadius: 16, background: COLOR.surface, boxShadow: `inset 0 0 0 1px ${WIN_LINE}`, overflow: "hidden" };
  const usRows = kind === "ind" ? [] : top.map((r) => r.s);
  // The chip rows: on the phone one row that scrolls sideways and runs to the screen's edges (the board); on PC (no sideways
  // swipe with a mouse wheel) they wrap onto more lines inside the card's column.
  const chipRowStyle = wide ? { display: "flex", flexWrap: "wrap", gap: 6 }
    : { display: "flex", gap: 6, overflowX: "auto", scrollbarWidth: "thin", marginLeft: -SPACE(4), marginRight: -SPACE(4), paddingLeft: SPACE(4), paddingRight: SPACE(4) };
  return (
    <section ref={boxRef} data-ui-v2="rank" data-mk={mk} data-chip={chip} data-crit={chip === "crit" ? crit : undefined} data-full={full ? "1" : undefined}
      data-group={openedId || undefined} aria-labelledby={titleId} style={{ marginTop: SPACE(5), scrollMarginTop: wide ? SPACE(20) : SPACE(3) }}>
      <style>{ROLL_CSS}</style>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", columnGap: SPACE(2), rowGap: 2 }}>
        <h3 id={titleId} ref={headRef} tabIndex={-1} style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { letterSpacing: "-0.02em", outline: "none" })}>{C.rank.title}</h3>
        {md && (
          <span data-ui-v2="rank-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>
            <span>{fill(mk === "us" ? C.rank.dateUs : C.rank.date, { date: md })}</span>
            {year != null && <><span>{" · "}</span><span>{fill(C.app.reportYear, { year })}</span></>}
          </span>
        )}
      </div>
      <MarketSwitch mk={mk} label={titleId} onChange={(m) => choose({ mk: m })} />
      <div ref={chipRow} data-ui-v2="rank-chips" role="group" aria-labelledby={titleId} style={{ ...chipRowStyle, marginTop: SPACE(2) + 2 }}>
        {chips.map((c) => (
          <Chip key={c} id={c} on={c === chip} refOf={(el) => { chipRefs.current[c] = el; }} onClick={() => choose({ chip: c })}>{C.rank.chips[c]}</Chip>
        ))}
      </div>
      {chip === "crit" && (
        <div ref={critRow} data-ui-v2="rank-crit" role="group" aria-label={C.rank.chips.crit} style={{ ...chipRowStyle, marginTop: SPACE(2) }}>
          {critShown.map((id) => (
            <Chip key={id} id={id} on={id === crit} pic={CARD_PICS[id]} refOf={(el) => { chipRefs.current["crit:" + id] = el; }}
              onClick={() => choose({ crit: id })}>{C.build.cards[id].name}</Chip>
          ))}
        </div>
      )}
      {opened && <GroupHead g={opened} backRef={backRef} onBack={() => setGroup(null)} />}
      {lines.length > 0 && (
        <div data-ui-v2="rank-line" style={{ margin: `${SPACE(2) + 2}px 0 ${SPACE(2)}px` }}>
          {lines.map((l, i) => <p key={i} style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { wordBreak: "keep-all" })}>{l}</p>)}
        </div>
      )}
      {!lines.length && <div style={{ height: SPACE(2) }} />}
      {!dated || !chips.length || (!top.length && !emptyText) ? <div data-ui-v2="rank-fail" style={win}><LoadFail picture={false} /></div>
        : !top.length ? (
          <div data-ui-v2="rank-empty" style={{ ...win, padding: `${SPACE(5)}px ${SPACE(4)}px` }}>
            <p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { wordBreak: "keep-all" })}>{emptyText}</p>
          </div>
        ) : still ? (
          <div ref={roll.ref} data-ui-v2="rank-window" data-moving="0" data-still={still} data-rows={shownRows.length} style={win}>
            <div role="list" aria-labelledby={titleId}>{body(false).slice(0, shownRows.length)}</div>
          </div>
        ) : (
          <div ref={roll.ref} data-ui-v2="rank-window" data-moving={moving ? "1" : "0"} data-pause={roll.why || undefined} data-rows={fit}
            data-kb={roll.kb ? "1" : undefined} role="group" aria-label={C.rank.listAria} tabIndex={0} {...roll.handlers}
            style={{ ...win, height: fit * ROW_H, touchAction: "pan-y" }}>
            {/* keyboard focus on a row: the rows lie still at their places (no transform) so the focused one can be scrolled to */}
            <div key={listKey} data-ui-v2="rank-track" data-roll="1" style={{ animationPlayState: moving ? "running" : "paused", ...(roll.kb ? { animation: "none" } : {}) }}>
              <div role="list" aria-labelledby={titleId}>{body(false)}</div>
              <div data-ui-v2="rank-copy" aria-hidden="true">{body(true)}</div>
            </div>
            <span aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, top: 0, height: 22, pointerEvents: "none", zIndex: 2,
              background: "linear-gradient(#FFFFFF, rgba(255,255,255,0))" }} />
            <span aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 22, pointerEvents: "none", zIndex: 2,
              background: "linear-gradient(rgba(255,255,255,0), #FFFFFF)" }} />
          </div>
        )}
      {/* v19.1c: a US stock priced at an earlier close (pxd) among the rows: named once under the list */}
      <OwnCloseNote groups={ownCloses(load, usRows)} data-market={mk} />
      {!full && dated && top.length > 0 && chips.length > 0 && (
        <div data-ui-v2="rank-foot" style={{ marginTop: SPACE(1), display: "flex", justifyContent: "space-between", alignItems: "center", gap: SPACE(2) }}>
          {!still ? <span data-ui-v2="rank-hint" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.rank.hint}</span> : <span />}
          {/* not inside an opened 업종: its back control returns to the groups, and the 종목 tab opens on the groups */}
          {go && !opened && (
            <button type="button" data-ui-v2="rank-all" onClick={() => { askJump(); go("stocks"); }}
              style={{ ...tap, minHeight: TOUCH, border: "none", background: "none", ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { whiteSpace: "nowrap" }) }}>{C.rank.all}</button>
          )}
        </div>
      )}
    </section>
  );
}

function Chip({ id, on, pic, onClick, refOf, children }) {
  return (
    <button ref={refOf} type="button" data-ui-v2="rank-chip" data-chip={id} data-selected={on ? "1" : undefined} aria-pressed={on ? "true" : "false"} onClick={onClick}
      style={{ ...tap, flex: "none", display: "inline-flex", alignItems: "center", gap: 5, height: 40, padding: "0 13px", borderRadius: 20, border: "none",
        background: on ? COLOR.ink : COLOR.surface, boxShadow: on ? "none" : `inset 0 0 0 1px ${CHIP_LINE}`,
        ...tx(13.5, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.surface : COLOR.neutral, { whiteSpace: "nowrap" }) }}>
      {pic && <img src={pic.src} alt="" width={20} height={20} decoding="async" style={{ display: "block", flex: "none", width: 20, height: 20, objectFit: "contain" }} />}
      {children}
    </button>
  );
}

// 한국 · 미국 (board: a warm-grey track with the chosen market on white). Radios: arrow keys move between the two.
function MarketSwitch({ mk, label, onChange }) {
  const refs = useRef({});
  const keys = (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const next = mk === "kr" ? "us" : "kr";
    onChange(next);
    try { refs.current[next].focus(); } catch (x) { /* ignore */ }
  };
  return (
    <div data-ui-v2="rank-market" role="radiogroup" aria-labelledby={label} onKeyDown={keys}
      style={{ marginTop: SPACE(2) + 2, display: "inline-flex", padding: 3, borderRadius: 12, background: WIN_LINE }}>
      {["kr", "us"].map((m) => {
        const on = m === mk;
        return (
          <button key={m} ref={(el) => { refs.current[m] = el; }} type="button" role="radio" aria-checked={on ? "true" : "false"} tabIndex={on ? 0 : -1}
            data-mk={m} data-selected={on ? "1" : undefined} onClick={() => onChange(m)}
            style={{ ...tap, border: "none", minHeight: 38, padding: "0 16px", borderRadius: 9, background: on ? COLOR.surface : "transparent",
              ...tx(13.5, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text2) }}>{C.pick.market[m]}</button>
        );
      })}
    </div>
  );
}

// The opened group: back (to the groups), its name, "{n}개 중 {k}개 오름 / 내림" and its average today.
function GroupHead({ g, backRef, onBack }) {
  const w = groupWord(g);
  const word = C.rank.p.groupBack;
  return (
    <div data-ui-v2="rank-group" data-ind={g.ind} style={{ marginTop: SPACE(2) + 2, display: "flex", alignItems: "center", gap: SPACE(2) }}>
      <button ref={backRef} type="button" data-ui-v2="rank-back" onClick={onBack} aria-label={word ? undefined : C.co.back}
        style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, display: "inline-flex", alignItems: "center", gap: SPACE(1), padding: word ? `0 ${SPACE(3)}px 0 ${SPACE(1)}px` : 0,
          justifyContent: "center", borderRadius: 12, border: "none", background: COLOR.surface, boxShadow: `inset 0 0 0 1px ${CHIP_LINE}`, ...tx(13.5, WEIGHT.semi, COLOR.neutral) }}>
        <Icon name="back" size={18} />{word && <span>{word}</span>}
      </button>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" })}>{g.name || g.ind}</span>
        <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>
          <span>{fill(w.up ? C.rank.up : C.rank.down, { n: g.n, k: w.k })}</span>{" · "}
          <span data-ui-v2="rank-group-avg" style={{ color: Math.round(g.avg * 10) > 0 ? COLOR.upOnPage : Math.round(g.avg * 10) < 0 ? COLOR.down : COLOR.text2,
            fontWeight: WEIGHT.bold }}>{signed(g.avg)}</span>
        </span>
      </span>
    </div>
  );
}
