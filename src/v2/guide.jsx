// ================= 처음 안내: 직접 해 보기 (v19.3c Part E, boards Guide2a-Guide2d) =================
// One real action at a time on the real screen, no text walls (Plants vs. Zombies).
//   welcome  (Guide2a) on 홈: the 뱁이 carrying twigs (no numbers on this screen: CLAUDE.md), the title and line, the
//            three-step strip (기준 고르기 › 점수 나누기 › 종목과 비중, no digits), 직접 해 보기 and 그냥 둘러볼게요. The
//            data date line, the iPhone home-screen hint and the load-failure message stay as on today's first visit.
//            The second button 가진 종목 넣기 opens 가진 종목 넣기 (Part F, v19.3d).
//   1/3–3/3  (Guide2b-d) on the real 기준 카드 step (build.jsx StepCards): a dark overlay over everything but the target.
//            1: the 배당 card and its + are lit (a pulsing ring and a hand); the user taps the real +. 2: the meter is
//            lit and shows the pool struck through → the new count, both the engine's own numbers; it moves on after
//            2.5 s or a tap. 3: "남은 {n}점도 …" and 알겠어요, which closes the overlay; the point given stays.
//   건너뛰기 on every step (and Esc) ends the guide and remembers it was seen. Focus moves into the bubble on every step,
//   its text is read out (aria-live), and the counter reads "1/3". No 뱁이 on the steps: they show counts and points.
// When it shows: GUIDE_FIRST_VISIT (below) — the first visit to 2.0 whose first screen is 홈, with no saved portfolio and
// the guide not yet seen, in place of today's first-visit landing. The ☰ menu's (PC: the left menu's) 처음 안내 다시 보기
// replays it at any time, whatever the switch says.
// "Seen" is the store's guideSeen (v19.3d, Part E; app.html and the preview page each keep their own store), written with
// the store: a browser that cannot store anything simply shows the welcome again on the next first visit.
// v19.3d: the welcome's second button 가진 종목 넣기 opens 가진 종목 넣기 (Part F).
// No Korean here: the words come from src/copy/v2.js.
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, TOPIC_CHIP, ICON_CHIP } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Button } from "../ui/components.jsx";
import { C } from "./format.js";
import { Card, DateLine, LoadFail, Mascot, IMG, SIDE_W, useLayout, tx, tap } from "./ui.jsx";
import { IosHint } from "./hint.jsx";
import { CARD_PICS, TOPIC_DOT, DOT_EMPTY } from "./pictures.js";
import { guideSeenIn } from "./store.js";

// On since Jack's yes (2026-11-08): a first visit to 홈 shows the welcome instead of the first-visit landing (the smoke
// tests' other scenes run as a visitor who has seen it). 처음 안내 다시 보기 replays it at any time.
export const GUIDE_FIRST_VISIT = true;

// v19.3d (Part E: "Store the flag in the 2.0 store"): "seen" is the store's guideSeen (store.js), written with the store
// (app.jsx endGuide). The flag of v19.3c's own key (storeKey + ".guideSeen") is read into the store once (store.js
// readStore) and never written again.
export const guideSeen = (store) => guideSeenIn(store && store.data);

// Shown at start: GUIDE_FIRST_VISIT, the page opened on 홈 (no sub-screen, not 소개), nothing saved and nothing
// unreadable in the store, and the guide not seen yet.
export function firstVisitGuide(loc, store, on = GUIDE_FIRST_VISIT) {
  return !!(on && loc && loc.tab === "home" && !loc.sub && !loc.about && store && !store.locked && store.data && store.data.decks.length === 0
    && !guideSeen(store));
}

// ---------------- the welcome (Guide2a) ----------------
function Arrow() {
  return <span aria-hidden="true" style={{ marginTop: SPACE(3), flexShrink: 0 }}><Icon name="chevronRight" size={16} tone="off" /></span>;
}
function StepItem({ children, label }) {
  return (
    <div role="listitem" style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: SPACE(1) + 2 }}>
      <span aria-hidden="true" style={{ height: SPACE(10), display: "flex", alignItems: "center" }}>{children}</span>
      <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.neutral, { textAlign: "center" })}>{label}</span>
    </div>
  );
}
const tile = (id, style) => (
  <span style={{ width: SPACE(10), height: SPACE(10), borderRadius: ICON_CHIP.radius, background: TOPIC_CHIP[CARD_PICS[id].topic], display: "flex",
    alignItems: "center", justifyContent: "center", flexShrink: 0, ...style }}>
    <img src={CARD_PICS[id].src} alt="" width={28} height={28} decoding="async" style={{ display: "block", width: 28, height: 28, objectFit: "contain" }} />
  </span>
);

// The three-step strip: 기준 (two 기준 pictures) › 점수 (four of five dots) › 종목과 비중 (the portfolio icon). No digits.
function StepStrip() {
  const [a, b, c] = C.guide.steps;
  return (
    <div role="list" data-ui-v2="guide-steps" style={{ margin: `${SPACE(4)}px 0 0`, padding: `${SPACE(3) + 2}px ${SPACE(2)}px`, borderRadius: RADIUS.lg - 2,
      background: COLOR.page, display: "flex", alignItems: "flex-start", gap: SPACE(1) }}>
      <StepItem label={a}>{tile("value")}{tile("div", { marginLeft: -SPACE(3) })}</StepItem>
      <Arrow />
      <StepItem label={b}>
        <span style={{ display: "inline-flex", gap: SPACE(1) }}>
          {[0, 1, 2, 3, 4].map((i) => <span key={i} style={{ width: 10, height: 10, borderRadius: "50%", background: i < 4 ? TOPIC_DOT.div : DOT_EMPTY }} />)}
        </span>
      </StepItem>
      <Arrow />
      <StepItem label={c}>
        <span style={{ width: SPACE(10), height: SPACE(10), borderRadius: ICON_CHIP.radius, background: ICON_CHIP.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon name="chart-pie-slice" size={24} tone="on" />
        </span>
      </StepItem>
    </div>
  );
}

// first: no portfolio saved (the iPhone hint is the first-visit one, as on today's landing). A replay from the menu by
// someone with portfolios shows the same welcome without it. Without data the welcome is never kept on screen (app.jsx
// closes it, so 홈 shows its load-failure message as without the guide).
// onImport (v19.3d): the second button, 가진 종목 넣기 (Part F); left out when there is nowhere to go (no data).
export function Welcome({ load, first, onTry, onBrowse, onImport = null }) {
  const { wide } = useLayout();
  return (
    <>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      <Card data-ui-v2="guide-welcome" style={{ textAlign: "center", marginTop: SPACE(4), padding: `${SPACE(6)}px ${SPACE(5)}px ${SPACE(5)}px`,
        ...(wide ? { maxWidth: 520 } : {}) }}>
        <Mascot src={IMG.build} alt={C.build.s0.imgAlt} size={132} style={{ display: "block", margin: "0 auto" }} />
        <h2 style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3), lineHeight: 1.35, textWrap: "balance" })}>{C.guide.title}</h2>
        <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(2) })}>{C.guide.body}</p>
        <StepStrip />
        <div data-ui-v2="guide-try" style={{ marginTop: SPACE(5) }}><Button onClick={onTry} style={{ minHeight: TOUCH + SPACE(1) + 2 }}>{C.guide.try}</Button></div>
        {onImport && <div data-ui-v2="guide-holdings" style={{ marginTop: SPACE(2) }}><Button kind="secondary" onClick={onImport} style={{ minHeight: TOUCH + SPACE(1) + 2 }}>{C.guide.holdings}</Button></div>}
        <button type="button" data-ui-v2="guide-browse" onClick={onBrowse}
          style={{ ...tap, marginTop: SPACE(2), minHeight: TOUCH, width: "100%", border: "none", background: "none", ...tx(SIZE.sm, WEIGHT.bold, COLOR.text2) }}>{C.guide.browse}</button>
      </Card>
      {first && <IosHint kind="first" />}
      {load.status === "fail" && <LoadFail picture={false} />}
    </>
  );
}

// ---------------- the steps (Guide2b-d) ----------------
const SHADE = "rgba(28, 43, 69, 0.55)";                 // the board's overlay: navy at 55%
const LIGHT = "#FFE2A8";                                // the board's light ring around what to look at (not apricot)
const HOLE_PAD = SPACE(1) + 2;
const STEPS_N = 3;

const sameRect = (a, b) => !!a && !!b && a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
function rectOf(el) {
  if (!el || !el.isConnected) return null;
  const r = el.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return null;
  return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
}

// The target's place on screen, every frame (the page may scroll under the overlay, or the meter stick to the top).
function useTrack(sel, on) {
  const [rect, setRect] = useState(null);
  const last = useRef(null);
  useLayoutEffect(() => {
    if (!on) return undefined;
    let raf = 0;
    const tick = () => {
      const r = rectOf(document.querySelector(sel));
      if (!sameRect(r, last.current)) { last.current = r; setRect(r); }
      raf = window.requestAnimationFrame(tick);
    };
    tick();
    return () => window.cancelAnimationFrame(raf);
  }, [sel, on]);
  return rect;
}

const PULSE_CSS = "@keyframes v2-guide-pulse { 0%, 100% { box-shadow: 0 0 0 4px #FFE2A8, 0 0 0 9px rgba(255, 226, 168, 0.45); } 50% { box-shadow: 0 0 0 6px #FFE2A8, 0 0 0 14px rgba(255, 226, 168, 0.25); } }"
  + " @media (prefers-reduced-motion: reduce) { [data-ui-v2=\"guide-ring\"] { animation: none !important; } }";

// stage: 1 · 2 · 3. hole: what stays lit (a CSS selector); ring: the button to tap (stage 1); title / body: the bubble;
// action: { label, onClick } (stage 3's 알겠어요); onBackdrop: a tap on the dark part (stage 2 moves on); onSkip: 건너뛰기 and Esc.
// onLost: the target never appeared (e.g. the screen changed): the guide ends without a word.
// focusAfter: where focus goes when the bubble is gone (the first of these selectors still on the page), so it never
// drops to the page itself; nothing is moved when focus is already somewhere else on the page.
// keepClear (step 1): { top, bottom } selectors of what covers the page there (the sticky meter above, the action bar
// below). The button to tap must sit in the gap between them and the bubble, and the lit part stops at their edges.
// On a short screen (a phone held sideways) where that gap is under a tap's height, the bubble moves to the top; if it
// still does not fit, the guide ends quietly, as seen.
export function Coach({ stage, hole, ring, title, body, action, onBackdrop, onSkip, onLost, focusAfter = [], keepClear = null }) {
  const { wide } = useLayout();
  const box = useTrack(hole, true);
  const btn = useTrack(ring || "", !!ring);
  const bubble = useRef(null);
  const clear = stage === 1 && ring && keepClear ? keepClear : null;
  const [atTop, setAtTop] = useState(false);
  const capTop = useTrack(clear ? clear.top : "", !!clear);
  const capBottom = useTrack(clear ? clear.bottom : "", !!clear);
  const bub = useTrack('[data-ui-v2="guide-bubble"]', !!clear);
  const after = useRef(focusAfter);
  after.current = focusAfter;

  useEffect(() => () => {
    window.setTimeout(() => {
      const a = document.activeElement;
      if (a && a !== document.body && a.isConnected) return;
      for (const sel of after.current) {
        const el = document.querySelector(sel);
        if (el) { try { el.focus({ preventScroll: true }); } catch (e) { /* ignore */ } return; }
      }
    }, 0);
  }, []);

  // The target must show up within about a second, or the guide gives up quietly (never a dark screen with nothing lit).
  useEffect(() => {
    if (box) return undefined;
    const id = window.setTimeout(() => { if (!rectOf(document.querySelector(hole)) && onLost) onLost(); }, 1200);
    return () => window.clearTimeout(id);
  }, [!!box, hole]);

  // The free band for the button to tap: below the sticky meter (and the bubble, when it is at the top), above the action
  // bar (and the bubble, when it is at the bottom).
  const band = (top) => {
    const rect = (sel) => { const e = sel ? document.querySelector(sel) : null; return e ? e.getBoundingClientRect() : null; };
    const a = rect(clear && clear.top), z = rect(clear && clear.bottom);
    const b = bubble.current ? bubble.current.getBoundingClientRect() : null;
    let lo = a ? Math.max(0, a.bottom) : 0;
    let hi = z ? Math.min(window.innerHeight, z.top) : window.innerHeight;
    if (b) { if (top) lo = Math.max(lo, b.bottom); else hi = Math.min(hi, b.top); }
    return { lo, hi };
  };
  // Scrolls the button to tap into the middle of the band if it is not inside it already. false: the band is too short.
  const fitRing = (top) => {
    const el = ring ? document.querySelector(ring) : null;
    if (!el) return true;
    const { lo, hi } = band(top);
    if (hi - lo < TOUCH + SPACE(2)) return false;
    const r = el.getBoundingClientRect();
    if (r.top < lo + SPACE(1) || r.bottom > hi - SPACE(1)) { try { window.scrollBy(0, (r.top + r.bottom) / 2 - (lo + hi) / 2); } catch (e) { /* ignore */ } }
    return true;
  };

  // Each step: bring the target into view above the bubble, then move focus into the bubble (its text is read out).
  // Step 1 then makes sure the button to tap is clear of the meter, the bubble and the action bar (see keepClear).
  useEffect(() => {
    const el = document.querySelector(hole);
    if (el) {
      const r = el.getBoundingClientRect();
      const under = bubble.current ? bubble.current.getBoundingClientRect().top : window.innerHeight;
      if (r.top < 0 || r.bottom > under - SPACE(3)) { try { el.scrollIntoView({ block: "center" }); } catch (e) { /* ignore */ } }
    }
    if (clear && !atTop && !fitRing(false)) setAtTop(true);
    const b = bubble.current;
    if (b) { try { b.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
  }, [stage]);
  useEffect(() => {
    if (!clear || !atTop) return;
    if (!fitRing(true)) onSkip();                         // nothing fits on this screen: end the guide quietly, as seen
  }, [atTop]);

  // Esc = 건너뛰기. Tab stays between the bubble's buttons and the button to tap (nothing under the dark part).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onSkip(); return; }
      if (e.key !== "Tab") return;
      const list = [...(bubble.current ? bubble.current.querySelectorAll("button") : []), ...(ring ? [document.querySelector(ring)] : [])]
        .filter((x) => x && !x.disabled);
      if (!list.length) return;
      const i = list.indexOf(document.activeElement);
      const next = e.shiftKey ? (i <= 0 ? list.length - 1 : i - 1) : (i < 0 || i === list.length - 1 ? 0 : i + 1);
      e.preventDefault();
      try { list[next].focus(); } catch (err) { /* ignore */ }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [onSkip, ring]);

  let h = box ? { x: box.x - HOLE_PAD, y: box.y - HOLE_PAD, w: box.w + 2 * HOLE_PAD, h: box.h + 2 * HOLE_PAD } : null;
  if (h && clear) {                                       // step 1: the lit part stops at the meter, the bubble and the action bar
    let lo = capTop ? Math.max(0, capTop.y + capTop.h) : 0;
    let hi = capBottom ? capBottom.y : Infinity;
    if (bub) { if (atTop && clear) lo = Math.max(lo, bub.y + bub.h); else hi = Math.min(hi, bub.y); }
    const y1 = Math.max(h.y, lo), y2 = Math.min(h.y + h.h, hi);
    h = { ...h, y: y1, h: Math.max(0, y2 - y1) };
  }
  // Four clear blocks around the lit part catch every tap outside it (nothing under the dark part can be pressed); the
  // dark itself is the lit part's own shadow, so its corners stay round. The blocks reach the window's edges (right /
  // bottom 0), so a window that changes size never leaves a dark strip that can be tapped.
  const block = (style) => <div data-ui-v2="guide-shade" onClick={onBackdrop} style={{ position: "fixed", zIndex: 90, ...style }} />;
  return (
    <>
      <style>{PULSE_CSS}</style>
      {h ? (
        <>
          {block({ left: 0, right: 0, top: 0, height: Math.max(0, h.y) })}
          {block({ left: 0, right: 0, top: h.y + h.h, bottom: 0 })}
          {block({ left: 0, top: h.y, width: Math.max(0, h.x), height: h.h })}
          {block({ left: h.x + h.w, right: 0, top: h.y, height: h.h })}
          <div data-ui-v2="guide-hole" aria-hidden="true" onClick={stage === 2 ? onBackdrop : undefined}
            style={{ position: "fixed", zIndex: 89, left: h.x, top: h.y, width: h.w, height: h.h, borderRadius: RADIUS.lg + 2,
              boxShadow: `${stage === 1 ? "" : `0 0 0 4px ${LIGHT}, `}0 0 0 200vmax ${SHADE}`, pointerEvents: stage === 2 ? "auto" : "none" }} />
        </>
      ) : <div data-ui-v2="guide-shade" style={{ position: "fixed", zIndex: 90, inset: 0, background: SHADE }} />}
      {ring && btn && (
        <>
          <span data-ui-v2="guide-ring" aria-hidden="true" style={{ position: "fixed", zIndex: 92, pointerEvents: "none", left: btn.x + btn.w / 2 - 17, top: btn.y + btn.h / 2 - 17,
            width: 34, height: 34, borderRadius: "50%", animation: "v2-guide-pulse 1.4s ease-in-out infinite", boxShadow: `0 0 0 4px ${LIGHT}` }} />
          <span data-ui-v2="guide-hand" aria-hidden="true" style={{ position: "fixed", zIndex: 92, pointerEvents: "none", left: btn.x + btn.w / 2 - 8, top: btn.y + btn.h - 4 }}>
            <Icon name="hand-pointing" size={36} tone="on" />
          </span>
        </>
      )}
      <div style={{ position: "fixed", zIndex: 93, left: wide ? SIDE_W : 0, right: 0, pointerEvents: "none",
        ...(atTop && clear ? { top: 0, padding: `calc(${SPACE(3)}px + env(safe-area-inset-top)) ${SPACE(3)}px 0` }
          : { bottom: 0, padding: `0 ${SPACE(3)}px calc(${SPACE(3) + 2}px + env(safe-area-inset-bottom))` }) }}>
        <div ref={bubble} data-ui-v2="guide-bubble" data-step={stage} data-at={atTop && clear ? "top" : "bottom"} role="dialog" aria-modal="false" aria-labelledby="v2-guide-title" aria-describedby="v2-guide-body"
          tabIndex={-1} onClick={stage === 2 ? onBackdrop : undefined}
          style={{ maxWidth: 520, margin: "0 auto", pointerEvents: "auto", background: COLOR.surface, borderRadius: RADIUS.lg, padding: `${SPACE(4)}px ${SPACE(4)}px ${SPACE(3) + 2}px`,
            boxShadow: "0 8px 28px rgba(28, 43, 69, 0.35)", outline: "none" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(2) }}>
            <span style={{ display: "flex", alignItems: "center", gap: SPACE(1) }}>
              {Array.from({ length: STEPS_N }, (_, i) => (
                <span key={i} aria-hidden="true" style={{ width: i + 1 === stage ? 18 : 6, height: 6, borderRadius: 3, background: i + 1 === stage ? COLOR.ink : "#D9D4CC" }} />
              ))}
              <span data-ui-v2="guide-count" style={tx(SIZE.xs, WEIGHT.heavy, COLOR.text2, { marginLeft: SPACE(1) + 2 })}>{`${stage}/${STEPS_N}`}</span>
            </span>
            <button type="button" data-ui-v2="guide-skip" onClick={(e) => { e.stopPropagation(); onSkip(); }}
              style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: "none", background: "none", marginRight: -SPACE(2), padding: `0 ${SPACE(2)}px`, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.guide.skip}</button>
          </div>
          <div aria-live="polite">
            <p id="v2-guide-title" style={tx(SIZE.h3 - 1, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1), lineHeight: 1.4, letterSpacing: "-0.02em" })}>{title}</p>
            <p id="v2-guide-body" style={tx(SIZE.sm - 1, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1) })}>{body}</p>
          </div>
          {action && (
            <div style={{ marginTop: SPACE(3) }}><Button onClick={action.onClick} style={{ minHeight: TOUCH }}>{action.label}</Button></div>
          )}
        </div>
      </div>
    </>
  );
}
