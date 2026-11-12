// ================= 홈 · 종목 순위 card (v19.5b, docs/tasks/v19.5-home-lists-and-icon.md Part A) =================
// Boards: docs/design/v19.5/reference/HomeMovers2 (시가총액) · 2b (기준별) · 2c (업종별 등락). The lists themselves are pure
// (ranks.js); this file draws them. No Korean here: every word comes from src/copy/v2.js (C.rank and the keys it reuses).
//
// Where: 홈, below the 시장 tiles (phone: after 시장 한눈에; PC from 1200 px: the right column under it, 7 rows in the window;
// PC from 1024 to 1199 px: the end of the main column, today.jsx · home2.jsx), and on 홈's first visit (no saved portfolio)
// after 포트폴리오 만들기. That screen shows numbers now, so it carries no 뱁이 (the v19.3c welcome screen has the 뱁이;
// CLAUDE.md: 뱁이 never on a screen with numbers). 전체 보기 opens the 종목 tab with the same choice as a still list of 30
// (업종별 등락: every group).
//
// The window (home): the top 10 rows, 58 px each, 5 in view (PC 7) with a soft fade at the top and the bottom; 업종별 등락
// shows two labelled parts, 많이 오른 업종 and 많이 내린 업종 (five each). The list is drawn twice; the second copy is
// aria-hidden and its buttons are out of the tab order, so screen readers and the keyboard get the list once. It moves upward
// 32 s per loop, linear, holding #1 at the top for the first 7% (about 2 s), and stops while it is touched, hovered or has
// focus, while it is off screen (IntersectionObserver) and while the page is hidden ("누르고 있으면 멈춰요" under it, on phones
// only). It never moves under prefers-reduced-motion, on stale data (the app's own stale rule, load.fresh: the date line shows
// the real content date either way) or when the list fits the window: then it is a still list of 5 (PC 7) with 전체 보기.
// Every chip that applies is offered; a list with no row says why in its place (Jack, 2026-11-12): "필요한 데이터가 아직 없어
// 이 순위를 보여 드릴 수 없어요." or "지금은 이 순위에 들어갈 종목이 없어요." (거래 급증: its own approved line).
// Load failure: the screen's own load-failure message (the card is only drawn on loaded data); a market with no stock over the
// trading-value floor or without a readable close date shows the same message inside the card, never an empty box.
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
import { RANK_TOP, RANK_FULL, CRIT, rankRows, pointsDeck, chipsFor, shownChip, groupWord, groupList, indParts,
  chipState, dateBasis, oneReportYear, quarterBasis, readPick, savePick, RANK_KEY, PREVIEW_RANK_KEY } from "./ranks.js";

export const ROW_H = 58;                 // px per row (board)
const PART_H = 34;                       // px: the label over each part of 업종별 등락 (많이 오른 업종 · 많이 내린 업종)
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
// 기준별 row numbers (Jack, 2026-11-12): PBR to two decimals as on the company page; Korea 부채비율, US 차입금비율 (Yahoo
// debtToEquity: total debt ÷ equity × 100); 추세 "1년 {x}"; 성장 one measure per market (KR the 2-year average, US the latest
// quarter against the same quarter a year before).
// A row number in two parts (v19.5b review 3): the label (the words before {x}) on its own small line above the value, so a
// long label ("매출 연평균", "차입금비율") never squeezes the company name. -> { label, value }; label null for a bare number.
function labelled(tpl, x) {
  const i = tpl.indexOf("{x}");
  const label = i > 0 ? tpl.slice(0, i).trim() : "";
  return { label: label || null, value: fill(label ? tpl.slice(i) : tpl, { x }) };
}
function critNumber(id, s) {
  const N = C.rank.num;
  switch (id) {
    case "value": return labelled(N.pbr, nf(s.pbr, 2));
    case "profit": return labelled(N.roe, p1(s.roe));
    case "stable": return s.cls === "kr" ? labelled(N.debt, nf(Math.round(s.debt))) : labelled(N.debtUs, p1(s.debt));
    case "lowVol": return labelled(N.vol, p1(s.vol));
    case "trend": return labelled(N.trend, signed(s.mom));
    case "growth": return labelled(s.cls === "kr" ? N.g3Kr : N.g3Us, signed(s.g3));
    default: return { label: null, value: "" };
  }
}
// The {basis} of the 기준별 line: the card's basis line (build.cards), 성장 the market's own measure, and on the Korean 성장 and
// 수익성 lists the minimum size they keep (" · 매출 100억원 이상" / " · 자본 100억원 이상": ranks.MIN_EOK). The US lists have
// no minimum yet (no US revenue or equity figure in the data), so their line names none.
function critBasis(id, mk) {
  // US 성장: the approved basis until the owner approves the proposal without nested brackets (rank.p.basisG3Us, pending doc)
  const b = id === "growth" ? (mk === "kr" ? C.rank.basis.g3Kr : C.rank.p.basisG3Us || C.rank.basis.g3Us) : C.build.cards[id].basis;
  const f = mk === "kr" && (id === "growth" || id === "profit") ? C.rank.floor[id] : null;
  return f ? `${b} · ${f}` : b;
}
// The number on a stock row: cap and trading value in 억원 · 조원 (the approved units, deckcalc.eokText; cap is 조원 in
// data.json), 거래 급증 "평소의 {x}배", 기준별 the card's own value, 내 기준 "상위 {x}%", 배당수익률 the yield.
function rowNumber(chip, crit, r) {
  const s = r.s;
  const bare = (v) => ({ label: null, value: v || "" });
  switch (chip) {
    case "cap": case "group": return bare(eokText(num(s.cap) * 10000));
    case "val": return bare(eokText(r.v));
    case "surge": return labelled(C.rank.surgeX, nf(r.v, 1));
    case "crit": return critNumber(crit, s);
    case "mine": return r.pct != null ? labelled(C.rank.mineX, r.pct) : bare("");
    case "div": return bare(yieldText(r.v));
    default: return bare("");
  }
}

// The quarter line left out (ranks.quarterBasis): the console says why, once per market, chip and reason.
const quarterWarned = new Set();
function noteQuarter(mk, chip, qb) {
  const k = `${mk}:${chip}:${qb.fy}:${qb.missing}`;
  if (quarterWarned.has(k)) return;
  quarterWarned.add(k);
  console.info(`[v2] rank card (${mk} ${chip}): no quarter line on the date line: ${qb.fy} row(s) with a year-end PBR (bpsIn p fy), ${qb.missing} without bpsIn`);
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
// tight: under 360 px wide (v19.5b review 3) the row's gaps, side padding, number column and logo are a little smaller, so the
// company name keeps room at 320 px (the smoke test holds every row's name at least NAME_MIN_320 wide there).
const rowStyle = (tight) => ({ ...tap, display: "flex", alignItems: "center", gap: tight ? 8 : 11, width: "100%", height: ROW_H,
  padding: tight ? "0 10px" : "0 14px", border: "none", borderBottom: `1px solid ${COLOR.line}`, background: "none", textAlign: "left",
  boxSizing: "border-box" });
const rankNo = (i, tight) => <span data-ui-v2="rank-no" style={tx(SIZE.xs, WEIGHT.heavy, COLOR.text3, { width: tight ? 15 : 18, textAlign: "center", flexShrink: 0 })}>{i + 1}</span>;
function useTight() {
  const q = "(max-width: 359px)";
  const get = () => { try { return window.matchMedia(q).matches; } catch (e) { return false; } };
  const [t, setT] = useState(get);
  useEffect(() => {
    let m;
    try { m = window.matchMedia(q); } catch (e) { return undefined; }
    const on = () => setT(m.matches);
    if (m.addEventListener) m.addEventListener("change", on); else m.addListener(on);
    return () => { if (m.removeEventListener) m.removeEventListener("change", on); else m.removeListener(on); };
  }, []);
  return t;
}

// noInd: the companies of one opened group (their industry is the group's, named above the list): US tickers only.
function StockRow({ i, r, number, copy, onTap, noInd = false, tight = false }) {
  const s = r.s;
  const d1 = todayD1(s);
  const sub = s.cls === "us" ? [s.t, noInd ? null : s.indName].filter(Boolean).join(" · ") : noInd ? "" : s.indName || "";
  return (
    <div data-ui-v2="rank-row" data-t={s.t} data-cls={s.cls} data-rank={i + 1} data-v={r.v != null ? r.v : undefined} role={copy ? undefined : "listitem"}>
      <button type="button" onClick={onTap} tabIndex={copy ? -1 : undefined} style={rowStyle(tight)}>
        {rankNo(i, tight)}
        <CoMark t={s.t} name={s.nk} size={tight ? 30 : 34} />
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
          {/* a labelled number stays one approved string ("매출 연평균 +346.1%"): the label drawn as a small line above the value,
              the space between them kept (data-ui="amount": read as one piece, as build.jsx does for its bold numbers) */}
          <span data-ui-v2="rank-num" data-ui={number.label ? "amount" : undefined} style={tx(tight ? 13 : SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block", whiteSpace: "nowrap", lineHeight: 1.35 })}>
            {number.label && <span data-ui-v2="rank-num-label" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { display: "block", lineHeight: 1.2 })}>{number.label}</span>}
            {number.label ? " " : null}{number.value}
          </span>
          {d1 != null && <span data-ui-v2="rank-change" style={tx(SIZE.xs, WEIGHT.bold, changeColor(d1), { display: "block", whiteSpace: "nowrap", lineHeight: 1.35, marginTop: 1 })}>{signed(d1)}</span>}
        </span>
      </button>
    </div>
  );
}

// 업종별 등락: the group's three largest companies overlapped (one mark per company: a second share class of the same company
// is skipped), "{n}개 중 {k}개 오름 / 내림", the average change today (price red · blue). A tap opens its companies.
function GroupRow({ i, g, copy, onOpen, tight = false }) {
  const w = groupWord(g);
  const marks = [];
  for (const s of g.members) {
    if (marks.length === 3) break;
    if (!marks.some((x) => sameCompany(x, s))) marks.push(s);
  }
  return (
    <div data-ui-v2="rank-row" data-ind={g.ind} data-rank={i + 1} data-n={g.n} data-k={w.k} data-avg={Math.round(g.avg * 1000) / 1000} role={copy ? undefined : "listitem"}>
      <button type="button" onClick={onOpen} tabIndex={copy ? -1 : undefined} style={rowStyle(tight)}>
        {rankNo(i, tight)}
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
  const tight = useTight();
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
  // what each chip has: cheap scans (ranks.chipState); only the chosen chip's list is worked out (below)
  const st = useMemo(() => (ok ? chipState(load, mk, deck) : null), [ok, load, mk, deck]);
  // Every chip that applies is offered, and an empty one says why in place of the list (Jack, 2026-11-12: the data is missing, or
  // nothing qualifies). Only a market with no stock at all has no chip: the load-failure message stands in (v19.5b review 3).
  const chips = st && (st.base > 0 || st.uni > 0) ? chipsFor(mk, !!deck) : [];
  const critShown = CRIT.map((c) => c.id);
  const chip = chips.length ? shownChip(pick.chip, chips) : null;
  const crit = critShown.includes(pick.crit) ? pick.crit : critShown[0];
  const state = !st || !chip ? null : chip === "crit" ? st.crit[crit] : st[chip];
  useEffect(() => {
    if (!st) return;
    if (!st.base && !st.uni) console.warn(`[v2] rank card (${mk}): no stock in the data: the load-failure message stands in for the list`);
    else if (!st.base) console.warn(`[v2] rank card (${mk}): ${st.uni} stocks but none over the trading-value floor (${state === "none" ? "all under 5 eok won" : "no floor value"})`);
    else if (state === "nodata") console.warn(`[v2] rank card (${mk}): ${chip}${chip === "crit" ? " " + crit : ""}: the data this list needs is missing`
      + (chip === "surge" && st.surgeOf ? ` (no stock of ${st.surgeOf.of} over the floor has both val and val20)` : ""));
    else if (state === "none") console.info(`[v2] rank card (${mk}): ${chip}${chip === "crit" ? " " + crit : ""}: no stock qualifies today`);
  }, [mk, chip, crit, state, st ? st.base : -1, st ? st.uni : -1]);
  const cur = useMemo(() => (ok && chip && state === "rows" ? rankRows(load, mk, chip, chip === "crit" ? crit : null, deck) : null),
    [ok, load, mk, chip, crit, deck, state]);
  const groups = chip === "ind" && cur ? cur.rows : null;
  const opened = group && groups ? groups.find((g) => g.ind === group) || null : null;
  const rows = !cur ? [] : opened ? groupList(load.data.stocks, mk, opened.ind) : cur.rows;
  const kind = opened ? "group" : cur ? (cur.kind === "ind" ? "ind" : chip) : chip;
  // 업종별 등락 on 홈: two parts, 많이 오른 업종 and 많이 내린 업종 (five each, ranks.indParts); the 종목 tab's 전체 보기 lists every
  // group, highest first (Jack, 2026-11-12)
  const parts = kind === "ind" && !full ? indParts(rows, 5) : null;
  const partList = parts ? [["up", parts.up, C.rank.indUp], ["down", parts.down, C.rank.indDown]].filter((x) => x[1].length) : null;
  const N = full ? (kind === "ind" ? rows.length : RANK_FULL) : RANK_TOP;
  const top = parts ? [...parts.up, ...parts.down] : rows.slice(0, N);
  const fit = wide ? SHOWN.pc : SHOWN.phone;
  const stale = ok && !!(load.fresh && load.fresh.stale);
  const dateIso = ok ? (mk === "us" ? load.data.usPxDate : load.data.pxDate) : null;
  const dated = DATE.test(dateIso || "");
  const still = full ? "full" : reduced ? "reduced" : stale ? "stale" : top.length + (partList ? partList.length : 0) <= fit ? "short" : null;
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
  // What the Korean date line adds after "{date} 종가" (ranks.dateBasis): "{year}년 사업보고서 기준" on lists of 사업보고서 numbers,
  // only when every row shown is from that one year (reportYear); "각 회사의 최근 분기 재무제표 기준" on 가치 (PBR = today's close ÷
  // the latest quarter's equity) and on a 내 기준 whose only statement card with points is 가치; else nothing.
  const basis = dateBasis(mk, chip, crit, deck ? deck.settings.points : null);
  const year = basis === "report" && !opened && top.length ? reportYear(load, top) : null;
  // the quarter line only when every row shown has its PBR on the latest quarter's equity (ranks.quarterBasis), else the close
  // date only, and the console says why
  const qb = basis === "quarter" && !opened && top.length > 0 ? quarterBasis(top, load.coByT) : null;
  const quarter = !!(qb && qb.quarter);
  if (qb && !qb.quarter) noteQuarter(mk, chip, qb);
  const md = dated ? mdText(dateIso) : null;
  const lines = !chip ? [] : opened ? [C.rank.groupLine]
    : chip === "val" ? [mk === "us" ? C.rank.line.valUs : C.rank.line.val]
      : chip === "crit" ? [fill(C.rank.line.crit, { card: C.build.cards[crit].name, basis: critBasis(crit, mk) })]
        : chip === "div" ? [C.rank.line.div, mk === "us" ? C.rpt.divUs : null].filter(Boolean)
          : [C.rank.line[chip]].filter(Boolean);
  // the line in place of an empty list (Jack, 2026-11-12): the data is missing, or nothing qualifies (거래 급증: its own approved
  // line). Never an empty white box: a list that should have rows and has none falls to the load-failure message.
  // 업종별 등락 on 홈 with groups but none above or below 0.0% (both parts empty): nothing qualifies
  const emptyText = state === "nodata" ? C.rank.emptyData : state === "none" ? (chip === "surge" ? C.rank.surgeNone : C.rank.emptyNone)
    : parts && !top.length ? C.rank.emptyNone : null;
  const tapOf = (s) => tp.props({ t: s.t, cls: s.cls, s }).onTap;
  // cut: a still window shows its first `fit` rows (both parts of 업종별 등락 stay whole)
  const cut = !parts && (still === "reduced" || still === "stale");
  const shownRows = cut ? top.slice(0, fit) : top;
  const stockList = (copy) => shownRows.map((r, i) => (kind === "ind"
    ? <GroupRow key={r.ind} i={i} g={r} copy={copy} tight={tight} onOpen={() => setGroup(r.ind)} />
    : <StockRow key={r.s.t} i={i} r={r} copy={copy} tight={tight} number={rowNumber(kind, crit, r)} onTap={tapOf(r.s)} noInd={kind === "group"} />));
  // the list(s): one list, or the two labelled parts of 업종별 등락 (each its own list, named by its visible label through
  // aria-labelledby, so a screen reader hears the name once: v19.5b review 3)
  const lists = (copy) => (partList ? partList.map(([k, gs, label]) => (
    <div key={k} data-ui-v2="rank-part" data-part={k}>
      <p data-ui-v2="rank-part-label" id={copy ? undefined : `${titleId}-${k}`}
        style={tx(SIZE.xs, WEIGHT.heavy, COLOR.text2, { height: PART_H, display: "flex", alignItems: "flex-end", padding: tight ? "0 10px 6px" : "0 14px 6px",
          boxSizing: "border-box", borderBottom: `1px solid ${COLOR.line}` })}>{label}</p>
      <div role={copy ? undefined : "list"} aria-labelledby={copy ? undefined : `${titleId}-${k}`}>
        {gs.map((g, i) => <GroupRow key={g.ind} i={i} g={g} copy={copy} tight={tight} onOpen={() => setGroup(g.ind)} />)}
      </div>
    </div>
  )) : <div role={copy ? undefined : "list"} aria-labelledby={copy ? undefined : titleId}>{stockList(copy)}</div>);
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
            {quarter && <><span>{" · "}</span><span data-ui-v2="rank-quarter">{C.rank.quarter}</span></>}
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
            {lists(false)}
          </div>
        ) : (
          <div ref={roll.ref} data-ui-v2="rank-window" data-moving={moving ? "1" : "0"} data-pause={roll.why || undefined} data-rows={fit}
            data-kb={roll.kb ? "1" : undefined} role="group" aria-label={C.rank.listAria} tabIndex={0} {...roll.handlers}
            style={{ ...win, height: fit * ROW_H, touchAction: "pan-y" }}>
            {/* keyboard focus on a row: the rows lie still at their places (no transform) so the focused one can be scrolled to */}
            <div key={listKey} data-ui-v2="rank-track" data-roll="1" style={{ animationPlayState: moving ? "running" : "paused", ...(roll.kb ? { animation: "none" } : {}) }}>
              {lists(false)}
              <div data-ui-v2="rank-copy" aria-hidden="true">{lists(true)}</div>
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
          {/* phones only: on PC the mouse over the list already stops it (Jack, 2026-11-12) */}
          {!still && !wide ? <span data-ui-v2="rank-hint" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.rank.hint}</span> : <span />}
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
      style={{ ...tap, flex: "none", display: "inline-flex", alignItems: "center", gap: 5, height: TOUCH, padding: "0 13px", borderRadius: TOUCH / 2, border: "none",
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
            style={{ ...tap, border: "none", minHeight: TOUCH, padding: "0 16px", borderRadius: 9, background: on ? COLOR.surface : "transparent",
              ...tx(13.5, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text2) }}>{C.pick.market[m]}</button>
        );
      })}
    </div>
  );
}

// The opened group: back (to the groups), its name, "{n}개 중 {k}개 오름 / 내림" and its average today.
function GroupHead({ g, backRef, onBack }) {
  const w = groupWord(g);
  const word = C.rank.groupBack;
  return (
    <div data-ui-v2="rank-group" data-ind={g.ind} style={{ marginTop: SPACE(2) + 2, display: "flex", alignItems: "center", gap: SPACE(2) }}>
      <button ref={backRef} type="button" data-ui-v2="rank-back" onClick={onBack}
        style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, display: "inline-flex", alignItems: "center", gap: SPACE(1), padding: `0 ${SPACE(3)}px 0 ${SPACE(1)}px`,
          justifyContent: "center", borderRadius: 12, border: "none", background: COLOR.surface, boxShadow: `inset 0 0 0 1px ${CHIP_LINE}`, ...tx(13.5, WEIGHT.semi, COLOR.neutral) }}>
        <Icon name="back" size={18} /><span>{word}</span>
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
