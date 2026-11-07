// 포트폴리오 만들기: 시작 · 기준 · 빼기 · 조건 (테마 is hidden in the beta; 꼭 담을 종목 lives in 조건), then 후보 고르기 and
// 매수 계획 · 샀어요. A live count of candidates sits in the bottom bar.
// v19.0b: the start card shows the 뱁이 carrying twigs (baepi-16-build) next to the title and question only: no numbers on
// that screen besides the data-date line. The whole-block 준비 중 (data fields missing) shows the hard-hat 뱁이.
// v19.3c Part D (boards BuildCards2 · BuildStart2 · PcStart2): the 기준 step is two columns of 기준 cards (picture chip,
// the card's small picture, name, basis, one plain line, − / five dots + "{n}점" / +) under a sticky 내 점수 meter: ten
// slots filled with the chosen 기준 pictures, "{n}점 남았어요", and "지금 기준이면 회사 {n}개가 남아요" with the top three
// companies' marks. The count is the engine's own (engine.meterCount: the length of screen()'s result list, or the pool
// before any 기준 while no card has points), recomputed on every change, never an estimate. The strictness control stays,
// under the meter. The first-visit guide (guide.jsx) runs its three steps on this screen.
// The new start screen (dark 처음부터 card, 가진 종목 card, templates as recipe cards, no 뱁이) waits behind RECIPE_START.
import React, { useEffect, useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, SELECTED, TOPIC_CHIP, ICON_CHIP } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { Segmented, Stepper, MoneyInput, StatusChip } from "../ui/components.jsx";
import {
  CARDS, DECKS, STRICT, MIX, METHODS, MAX_PCTS, CUSHIONS, EXCLUDE_LIVE, EXCLUDE_PENDING, POINTS_TOTAL, POINTS_MAX, COUNT_RANGE,
  MIN_PER_STOCK_MAN, applyDeck, defaultSettings, activeCards, pointsUsed, strictTop, topOverall, bestCard,
  marketsOf, canPin, PINNED_MAX, meterCount, mixKr,
} from "./engine.js";
import { C, fill, nf, manText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, PendingChip, PendingBlock, Footer, Note, Label, Toggle, ActionBar, TextInput, ChoiceGrid, OldAppNote, Mascot, IMG, PicChip, CardPic, DeckPic, CardScores, PC_PAD, useLayout, useMode, tx, tap } from "./ui.jsx";
import { CARD_PICS, START_PICS, FAN_CARDS, DOT_EMPTY, dotColor } from "./pictures.js";
import { CARD_ART } from "./cardart.js";
import { CoMark } from "./logo.jsx";
import { Coach } from "./guide.jsx";
import { deckState, defaultPicks, pickItems, computePlan, pinnable, aboutWon, cushionStocks, clashView, y2022View } from "./deckcalc.js";
import { Pick } from "./pick.jsx";
import { Plan, Y2022Amount } from "./plan.jsx";

// Off until Jack says yes to the smoke-test edits it needs (v19.3c PR): today's tests check the start screen's 뱁이 and a
// one-column PC page, and the new start screen has neither (its recipe cards show points and percentages, so the 뱁이 must
// go: CLAUDE.md). Off, the start screen is exactly as before.
export const RECIPE_START = false;

export const STEPS = ["start", "cards", "exclude", "terms"];
// The first step's back button leaves 포트폴리오 만들기 (to the screen before it). Its name waits for Jack (build.backToday):
// meanwhile it is the tab name 홈.
export const backLabel = () => C.build.backToday || C.app.tabs.home;
export const newBuilder = () => ({ step: 0, stage: "steps", settings: defaultSettings(), picks: null });
// A half-made portfolio (v19.3c): points given (a template or the user's own), or 후보 고르기 / 매수 계획 open. The guide's
// 직접 해 보기 then resumes it instead of starting over, so nothing unsaved is ever thrown away. Without points nothing
// past the 기준 step can be reached, so an empty 기준 step is not a draft.
export const buildInProgress = (b) => !!b && (b.stage !== "steps" || pointsUsed((b.settings && b.settings.points) || {}) > 0);

// coach (v19.3c Part E): the first-visit guide's step while it runs ({ stage: 1 · 2 · 3, go, done, skip, lost }), else null.
export function Build({ load, builder, setBuilder, onExit, store, setStoreData, goToday, coach = null }) {
  if (load.status !== "ok" || load.missing.length) {
    return (
      <Page>
        <AppBar onBack={onExit} backLabel={backLabel()} />
        <ScreenTitle>{C.build.title}</ScreenTitle>
        {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        {load.status === "fail" && <LoadFail />}
        {load.status === "ok" && <PendingBlock data-ui-v2="build-not-ready" />}
        <Footer />
      </Page>
    );
  }
  if (builder.stage === "pick") return <Pick load={load} builder={builder} setBuilder={setBuilder} />;
  if (builder.stage === "plan") return <Plan load={load} builder={builder} setBuilder={setBuilder} store={store} setStoreData={setStoreData} goToday={goToday} />;
  return <Steps load={load} builder={builder} setBuilder={setBuilder} onExit={onExit} coach={coach} />;
}

function StepDots({ step }) {
  return (
    <ol aria-label={C.build.stepsAria} style={{ listStyle: "none", display: "flex", gap: SPACE(2), padding: 0, margin: `${SPACE(3)}px 0 0` }}>
      {STEPS.map((k, i) => (
        <li key={k} aria-current={i === step ? "step" : undefined} style={{ flex: 1 }}>
          <div style={{ height: SPACE(1), borderRadius: 2, background: i <= step ? COLOR.ink : COLOR.border }} />
          <div style={tx(SIZE.xs, i === step ? WEIGHT.heavy : WEIGHT.semi, i === step ? COLOR.ink : COLOR.text2, { marginTop: SPACE(1) })}>{C.build.steps[k]}</div>
        </li>
      ))}
    </ol>
  );
}

// v19.3b Part A: a template shows its picture on its tint chip (src/v2/pictures.js); 처음부터 (blank) has none until v19.3c.
function Option({ title, sub, onClick, id, pic }) {
  return (
    <button type="button" data-deck={id} onClick={onClick}
      style={{ ...tap, width: "100%", textAlign: "left", border: `1px solid ${COLOR.border}`, background: COLOR.surface, borderRadius: RADIUS.md,
        padding: `${SPACE(3)}px ${SPACE(4)}px`, marginTop: SPACE(2), display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(4) }}>
      {pic && <DeckPic id={id} size="deck" />}
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.body, WEIGHT.bold, COLOR.ink, { display: "block" })}>{title}</span>
        {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{sub}</span>}
      </span>
      <Icon name="chevronRight" size={20} tone="off" />
    </button>
  );
}

function Steps({ load, builder, setBuilder, onExit, coach }) {
  const { wide } = useLayout();
  const st = builder.settings;
  const step = builder.step;
  const set = (patch) => setBuilder((b) => ({ ...b, settings: { ...b.settings, ...patch }, picks: null }));
  const go = (n) => { setBuilder((b) => ({ ...b, step: n })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const ds = useMemo(() => deckState(load, st), [load, st]);
  const active = activeCards(st.points);
  const noCards = !active.length;
  const last = step === STEPS.length - 1;
  // Steps 기준 and 빼기 stop only when nothing passes at all, so 종목 수 and 한국 : 미국 in 조건 stay reachable.
  // 조건 stops whenever 후보 고르기 could not be filled (a market short of survivors, or the industry limits).
  const lower = last ? ds.blocked : ds.res.survivors === 0;
  const blocked = noCards || lower;
  const restart = () => setBuilder(newBuilder());
  const start = (id) => { setBuilder((b) => ({ ...b, settings: applyDeck(b.settings, id), picks: null, step: 1 })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const toPick = () => {
    setBuilder((b) => ({ ...b, stage: "pick", picks: defaultPicks(ds) }));
    try { window.scrollTo(0, 0); } catch (e) { /* ignore */ }
  };
  // A settings clash (e.g. 5 stocks x max 10%) is not fixed by lowering the criteria: the button stays "후보 n개 보기"
  // (off) and the clash line above names the limits. "기준을 낮춰 주세요" is only for too few survivors.
  const tooFew = last ? ds.check.block || ds.pre.short : ds.res.survivors === 0;
  const action = noCards ? C.build.pickCardsBtn : tooFew ? C.build.lowerBtn : last ? fill(C.build.seeCands, { shortN: ds.shortN }) : C.build.next;
  const summary = (
    <span data-ui-v2="match-count"><span>{C.build.matchSummary}</span>{" "}
      <b style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{fill(C.app.count, { count: nf(ds.res.survivors) })}</b></span>
  );
  return (
    <Page pad={SPACE(30)} cols={RECIPE_START && wide && step === 0 ? 2 : 1}>
      <AppBar onBack={step === 0 ? onExit : () => go(step - 1)} backLabel={step === 0 ? backLabel() : C.build.prevStep} />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(2), marginTop: SPACE(1) }}>
        <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.build.title}</div>
        {step > 0 && <button type="button" onClick={restart} style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.build.restart}</button>}
      </div>
      <DateLine date={load.data.pxDate} fresh={load.fresh} />
      <StepDots step={step} />
      {step === 0 && (RECIPE_START ? <StepStart2 start={start} /> : <StepStart start={start} />)}
      {step === 1 && <StepCards st={st} set={set} ds={ds} load={load} coach={coach} />}
      {step === 2 && <StepExclude st={st} set={set} ds={ds} />}
      {step === 3 && <StepTerms st={st} set={set} ds={ds} load={load} />}
      {step > 0 && !noCards && <SurvivorNotes ds={ds} two={marketsOf(st).length === 2} />}
      <Footer />
      {step > 0 && <ActionBar summary={summary} action={action} disabled={blocked} onAction={() => (last ? toPick() : go(step + 1))} />}
    </Page>
  );
}

// Per market: the market's own survivor count (a two-market deck names the market first).
function SurvivorNotes({ ds, two }) {
  return (
    <div data-ui-v2="survivor-notes">
      {ds.res.blanks > 0 && <Note data-ui-v2="blanks">{fill(C.build.s1.blanks, { n: nf(ds.res.blanks) })}</Note>}
      {ds.check.markets.map((m) => (
        <Note key={m.mk} tone="watch" data-ui-v2={m.state} data-market={m.mk}>
          {two && <span>{C.pick.market[m.mk]}{" · "}</span>}
          <span>{m.state === "zero" ? C.build.zero : m.state === "short" ? fill(C.build.short, { n: nf(m.have), need: m.need })
            : fill(C.build.few, { n: nf(m.have) })}</span>
        </Note>
      ))}
      {!ds.check.block && ds.pre.short && (
        <Note tone="watch" data-ui-v2="ind-block">
          {[...new Set(ds.pre.blocked.map((b) => (b.code === "indCap" && b.indName ? fill(C.plan.clashParts.ind, { ind: b.indName }) : C.pick.limitInd)))].map((t, i) => (
            <span key={i}>{i ? " · " : ""}{t}</span>
          ))}
          {" "}<span>{C.build.indFix}</span>
        </Note>
      )}
      {ds.clash && (() => {
        const v = clashView(ds.clash);
        return (
          <Note tone="watch" data-ui-v2="clash">
            {v.sentence && <div data-ui-v2="clash-text">{v.sentence}</div>}
            <div data-ui-v2="clash-list">{v.pieces.map((p, i) => <span key={i}>{i ? " · " : ""}{p.map((x, j) => <span key={j}>{j ? " " : ""}{x}</span>)}</span>)}</div>
          </Note>
        );
      })()}
    </div>
  );
}

function StepStart({ start }) {
  const s0 = C.build.s0;
  const { wide } = useLayout();                          // the 뱁이: 92 px on the phone, 176 px on PC (Part C)
  return (
    <div>
      <section data-ui-v2="build-start" style={{ display: "flex", gap: SPACE(3), alignItems: "center" }}>
        <div style={{ flex: 1, minWidth: 0 }}><ScreenTitle sub={s0.body}>{s0.title}</ScreenTitle></div>
        <Mascot src={IMG.build} alt={s0.imgAlt} size={wide ? 176 : 92} style={{ marginTop: SPACE(2) }} />
      </section>
      <OldAppNote />
      <div style={{ marginTop: SPACE(3) }}>
        <Option id="blank" title={s0.blank} sub={s0.blankSub} onClick={() => start(null)} />
        {DECKS.filter((d) => !d.hidden).map((d) => (
          <Option key={d.id} id={d.id} pic title={C.build.decks[d.id].name} sub={C.build.decks[d.id].sub} onClick={() => start(d.id)} />
        ))}
      </div>
    </div>
  );
}

// ---------------- v19.3c Part D: the new start screen (boards BuildStart2 · PcStart2), behind RECIPE_START ----------------
// Five dots for a 기준's points (one dot = one point), in the 기준's topic shade. label: what a screen reader says instead.
function Dots({ id, n, size = 7, gap = 3, label }) {
  return (
    <span role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} style={{ display: "inline-flex", gap, flexShrink: 0 }}>
      {Array.from({ length: POINTS_MAX }, (_, i) => (
        <span key={i} style={{ width: size, height: size, borderRadius: "50%", background: i < n ? dotColor(id) : DOT_EMPTY }} />
      ))}
    </span>
  );
}

// The 처음부터 card's fan of five 기준 pictures (white tiles tinted at the foot, as on the board).
function Fan() {
  const tilt = [-18, -9, 0, 9, 18];
  const lift = [12, 6, 0, 6, 12];
  return (
    <span aria-hidden="true" style={{ display: "block", position: "relative", height: SPACE(18), width: SPACE(42), marginBottom: SPACE(2) + 2 }}>
      {FAN_CARDS.map((id, i) => (
        <span key={id} style={{ position: "absolute", left: i * 28, top: lift[i], transform: `rotate(${tilt[i]}deg)`, width: 50, height: 64, borderRadius: 11,
          background: COLOR.surface, boxShadow: `0 2px 8px rgba(0, 0, 0, 0.25), inset 0 -14px 0 ${TOPIC_CHIP[CARD_PICS[id].topic]}`,
          display: "flex", alignItems: "center", justifyContent: "center" }}>
          <img src={CARD_PICS[id].src} alt="" width={34} height={34} decoding="async" style={{ display: "block", width: 34, height: 34, objectFit: "contain" }} />
        </span>
      ))}
    </span>
  );
}

// The badge under a recipe: 깐깐한 기준's cut (its own strictness) and 한미 반반's mix (its own Korea:US), from the engine.
function recipeBadge(d, n) {
  const s0 = C.build.s0;
  if (d.strict && strictTop(d.strict) != null && n === 3) return fill(s0.badgeStrict, { top: strictTop(d.strict) });
  if (d.mix) { const kr = Math.round(mixKr(d.mix) * 100); return fill(s0.badgeMix, { kr, us: 100 - kr }); }
  return null;
}

// A template as a recipe card: its picture, name, one line, then up to three ingredient rows (기준 picture, name, five
// dots, largest first; ties keep the engine's card order) and "+ {n}개 더" for the rest.
function Recipe({ d, start }) {
  const s0 = C.build.s0;
  const cc = C.build.decks[d.id];
  const ing = CARDS.filter((c) => !c.pending && (d.points[c.id] || 0) > 0).sort((a, b) => d.points[b.id] - d.points[a.id]);
  const shown = ing.slice(0, 3);
  const badge = recipeBadge(d, ing.length);
  return (
    <button type="button" data-deck={d.id} onClick={() => start(d.id)}
      style={{ ...tap, display: "flex", flexDirection: "column", alignItems: "stretch", gap: SPACE(2), textAlign: "left", border: "none", background: COLOR.surface,
        borderRadius: RADIUS.lg - 2, padding: SPACE(3) + 2, minWidth: 0 }}>
      <DeckPic id={d.id} size="deck" />
      <span style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { letterSpacing: "-0.02em" })}>{cc.name}</span>
      <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { lineHeight: 1.4, minHeight: 36 })}>{cc.sub}</span>
      <span aria-hidden="true" style={{ height: 1, background: COLOR.line }} />
      <span style={{ display: "flex", flexDirection: "column", gap: SPACE(1) }}>
        {shown.map((c) => (
          <span key={c.id} data-ingredient={c.id} style={{ display: "flex", alignItems: "center", gap: SPACE(1) + 2 }}>
            <CardPic id={c.id} />
            <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0, lineHeight: 1.3 })}>{C.build.cards[c.id].name}</span>
            <Dots id={c.id} n={d.points[c.id]} label={fill(C.build.s1.score, { score: d.points[c.id] })} />
          </span>
        ))}
        {ing.length > shown.length && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{fill(s0.more, { n: ing.length - shown.length })}</span>}
      </span>
      {badge && (
        <span data-ui-v2="recipe-badge" style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { alignSelf: "flex-start", background: COLOR.select, borderRadius: SPACE(2),
          padding: `${SPACE(1)}px ${SPACE(2)}px`, lineHeight: 1.35, textWrap: "balance" })}>{badge}</span>
      )}
    </button>
  );
}

function StepStart2({ start }) {
  const s0 = C.build.s0;
  const { wide } = useLayout();
  const ways = (
    <div data-ui-v2="start-ways" style={{ minWidth: 0 }}>
      <ScreenTitle>{s0.title}</ScreenTitle>
      <section data-ui-v2="start-blank" style={{ marginTop: SPACE(3), background: COLOR.ink, borderRadius: RADIUS.lg + 2, padding: `${SPACE(5)}px ${SPACE(5)}px ${SPACE(4) + 2}px`, overflow: "hidden" }}>
        <Fan />
        <h3 style={tx(SIZE.h2, WEIGHT.heavy, COLOR.surface, { letterSpacing: "-0.03em" })}>{s0.blank}</h3>
        <p style={tx(SIZE.sm - 1, WEIGHT.regular, "#CBD3DF", { marginTop: SPACE(1) })}>{s0.blankBody}</p>
        <button type="button" data-deck="blank" onClick={() => start(null)}
          style={{ ...tap, marginTop: SPACE(3) + 2, display: "inline-flex", alignItems: "center", gap: SPACE(1) + 2, minHeight: TOUCH, padding: `0 ${SPACE(4)}px`,
            border: "none", borderRadius: RADIUS.sm, background: COLOR.surface, ...tx(SIZE.sm, WEIGHT.heavy, COLOR.ink) }}>
          <span>{s0.pickCards}</span><Icon name="chevronRight" size={16} tone="on" />
        </button>
      </section>
      {/* 가진 종목 넣기 (Part F) comes in v19.3d: until then the card is shown, dimmed, as 준비 중이에요 (no button). */}
      <section data-ui-v2="start-holdings" data-pending="1" style={{ marginTop: SPACE(2) + 2, display: "flex", alignItems: "center", gap: SPACE(3) + 2, background: COLOR.surface,
        borderRadius: RADIUS.lg, padding: SPACE(4), opacity: 0.6 }}>
        <PicChip pic={START_PICS.holdings} size="deck" />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={tx(SIZE.h3 - 1, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{s0.holdings}</span>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, lineHeight: 1.45 })}>{s0.holdingsSub}</span>
          <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { display: "flex", alignItems: "center", gap: SPACE(1), marginTop: SPACE(1) })}>
            <Icon name="calendar" size={16} tone="off" /><span>{C.build.s1.pendingCard}</span>
          </span>
        </span>
      </section>
      <OldAppNote />
    </div>
  );
  const recipes = (
    <div data-ui-v2="start-recipes" style={{ minWidth: 0 }}>
      <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginTop: wide ? SPACE(3) : SPACE(6) })}>{s0.recipes}</h3>
      <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "flex", alignItems: "center", gap: SPACE(1) + 2, marginTop: SPACE(1) })}>
        <span aria-hidden="true" style={{ display: "inline-flex", gap: 3, flexShrink: 0 }}>
          {[0, 1, 2, 3, 4].map((i) => <span key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: i < 3 ? "#7C889C" : DOT_EMPTY }} />)}
        </span>
        <span>{s0.dotsNote}</span>
      </p>
      <div data-ui-v2="recipe-grid" style={{ marginTop: SPACE(2) + 2, display: "grid", gap: SPACE(2),
        gridTemplateColumns: wide ? "repeat(3, minmax(0, 1fr))" : "repeat(auto-fill, minmax(156px, 1fr))" }}>
        {DECKS.filter((d) => !d.hidden).map((d) => <Recipe key={d.id} d={d} start={start} />)}
      </div>
    </div>
  );
  if (!wide) return <div data-ui-v2="build-start2">{ways}{recipes}</div>;
  return (
    <div data-ui-v2="build-start2" style={{ display: "grid", gridTemplateColumns: "340px minmax(0, 1fr)", columnGap: SPACE(6), alignItems: "start" }}>{ways}{recipes}</div>
  );
}

// ---------------- the 기준 step (board BuildCards2) ----------------
// A copy line split at one {slot}: [before, after] (so a number in it can be bold or struck through), or null if absent.
function around(tpl, slot) {
  const i = typeof tpl === "string" ? tpl.indexOf(`{${slot}}`) : -1;
  return i < 0 ? null : [tpl.slice(0, i), tpl.slice(i + slot.length + 2)];
}

// The card's own small picture (copied from the board, src/v2/cardart.js). Decorative.
function CardArt({ id, dim = false }) {
  const art = CARD_ART[id];
  if (!art) return null;
  return (
    <svg data-ui-v2="card-art" width={64} height={40} viewBox="0 0 64 40" aria-hidden="true" style={{ display: "block", flexShrink: 0, opacity: dim ? 0.45 : 1 }}>
      {art.map(([tag, a], i) => React.createElement(tag, { key: i, ...a }))}
    </svg>
  );
}

// One of the meter's ten slots: a chosen 기준's picture on its tint, or an empty outlined slot. The first slot of each
// 기준 carries the screen-reader name for all of them ("가치 4점"); the others and the empty ones are hidden from it.
function Slot({ slot }) {
  const base = { width: "100%", aspectRatio: "1 / 1", borderRadius: ICON_CHIP.radius, display: "flex", alignItems: "center", justifyContent: "center" };
  if (!slot) return <span data-ui-v2="meter-slot" data-empty="1" aria-hidden="true" style={{ ...base, boxShadow: "inset 0 0 0 1.5px #D9D4CC" }} />;
  const pic = CARD_PICS[slot.id];
  const name = slot.first ? fill(C.build.s1.slot, { card: C.build.cards[slot.id].name, n: slot.n }) : undefined;
  return (
    <span data-ui-v2="meter-slot" data-slot={slot.id} role={name ? "img" : undefined} aria-label={name} aria-hidden={name ? undefined : true}
      style={{ ...base, background: TOPIC_CHIP[pic.topic] }}>
      <img src={pic.src} alt="" decoding="async" style={{ display: "block", width: "74%", height: "74%", objectFit: "contain" }} />
    </span>
  );
}

// 내 점수 (sticky): "{n}점 남았어요", ten slots in the engine's card order, and the live count with the top three
// companies' marks. strike: the guide's step 2 shows the pool struck through → the line with the new count.
// The two lines keep each approved sentence whole: only the number is bold, inside a data-ui="amount" span (like
// "1,073만원": a figure with its words, one piece of text for the copy check and for screen readers).
const TOP_BAR = TOUCH + SPACE(6);                          // the PC top bar's height (nav.jsx TopBar): the meter sticks under it
function Meter({ st, ds, left, strike }) {
  const s1 = C.build.s1;
  const { wide } = useLayout();
  const { preview } = useMode();
  const m = meterCount(ds.res);
  const slots = CARDS.filter((c) => !c.pending).flatMap((c) => {
    const n = st.points[c.id] || 0;
    return Array.from({ length: n }, (_, i) => ({ id: c.id, n, first: i === 0 }));
  });
  const top3 = m.pool ? [] : topOverall(ds.res, 3);
  const lp = around(s1.left, "n");
  const rp = around(s1.remain, "n");
  const pad = wide ? PC_PAD : SPACE(4);
  return (
    <div data-ui-v2="meter-bar" style={{ position: "sticky", top: wide ? TOP_BAR : preview ? TOUCH : 0, zIndex: 30, background: COLOR.page,
      margin: `${SPACE(2)}px -${pad}px 0`, padding: `${SPACE(2)}px ${pad}px` }}>
      <section data-ui-v2="meter" tabIndex={-1} style={{ outline: "none", background: COLOR.surface, borderRadius: RADIUS.lg - 4, padding: `${SPACE(3)}px ${SPACE(3) + 2}px` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), marginBottom: SPACE(2) }}>
          <span style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{s1.meter}</span>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>
            {lp ? <span data-ui="amount">{lp[0]}<b data-ui-v2="points-left" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{left}</b>{lp[1]}</span>
              : <b data-ui-v2="points-left">{left}</b>}
          </span>
        </div>
        <div role="group" aria-label={s1.meter} style={{ display: "grid", gridTemplateColumns: `repeat(${POINTS_TOTAL}, minmax(0, 32px))`,
          justifyContent: wide ? "start" : "space-between", columnGap: wide ? SPACE(2) : SPACE(1) }}>
          {Array.from({ length: POINTS_TOTAL }, (_, i) => <Slot key={i} slot={slots[i]} />)}
        </div>
        <p data-ui-v2="meter-count" data-pool={m.pool ? "1" : "0"} data-n={m.n}
          style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(2) + 2, minHeight: SPACE(6) })}>
          {top3.length > 0 && (
            <span data-ui-v2="meter-marks" style={{ display: "flex", flexShrink: 0 }}>
              {top3.map((x, i) => (
                <span key={x.t} style={{ marginLeft: i ? -SPACE(1) - 2 : 0, borderRadius: 8, boxShadow: `0 0 0 2px ${COLOR.surface}`, display: "flex" }}>
                  <CoMark s={x.s} size={24} />
                </span>
              ))}
            </span>
          )}
          <span aria-live="polite">
            {strike && <><s data-ui-v2="meter-pool" style={{ color: COLOR.text2 }}>{fill(C.app.count, { count: nf(ds.res.pool) })}</s>{" → "}</>}
            {m.n === 0 ? s1.remainNone : rp ? (
              <span data-ui="amount">{rp[0]}<b data-ui-v2="meter-n" style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{nf(m.n)}</b>{rp[1]}</span>
            ) : fill(s1.remain, { n: nf(m.n) })}
          </span>
        </p>
      </section>
    </div>
  );
}

// − and + around the dots: a 32 px circle inside a 44 px tap area, the sign drawn as type (as on the board: the Phosphor
// duotone plus and minus carry a square fill layer that reads as a box inside a circle). inc on an empty card is navy.
const SIGN = { inc: "+", dec: "−" };
function RoundBtn({ kind, filled, disabled, label, onClick }) {
  return (
    <button type="button" data-ui-v2={kind === "inc" ? "card-inc" : "card-dec"} aria-label={label} disabled={disabled} onClick={onClick}
      style={{ ...tap, width: TOUCH, height: TOUCH, margin: `0 -${SPACE(1) + 2}px`, border: "none", background: "none", display: "flex", alignItems: "center",
        justifyContent: "center", opacity: disabled ? 0.4 : 1, cursor: disabled ? "default" : "pointer", flexShrink: 0 }}>
      <span aria-hidden="true" style={{ width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
        background: filled ? COLOR.ink : COLOR.surface, boxShadow: filled ? "none" : "inset 0 0 0 1.5px #C9C2B8",
        ...tx(SIZE.h3 + 2, WEIGHT.bold, filled ? COLOR.surface : COLOR.ink, { lineHeight: 1 }) }}>{SIGN[kind]}</span>
    </button>
  );
}

// One 기준 card. Chosen (points > 0): navy outline on the warm selection background. 준비 중 (no data yet): dimmed, no buttons.
function CriterionCard({ c, pts, left, top, onSet }) {
  const s1 = C.build.s1;
  const cc = C.build.cards[c.id];
  const on = !c.pending && pts > 0;
  const max = Math.min(POINTS_MAX, pts + left);
  return (
    <div data-card={c.id} data-points={c.pending ? undefined : pts}
      style={{ background: on ? SELECTED.background : COLOR.surface, boxShadow: on ? `inset 0 0 0 2px ${COLOR.ink}` : "none", borderRadius: RADIUS.lg - 2,
        padding: SPACE(3), minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: SPACE(1) }}>
        {/* 준비 중: only the two pictures are dimmed; the words keep their full contrast (as before v19.3c). */}
        <CardPic id={c.id} size="fit" dim={!!c.pending} />
        <CardArt id={c.id} dim={!!c.pending} />
      </div>
      <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(2) + 2, letterSpacing: "-0.02em" })}>{cc.name}</h3>
      {cc.basis && <p style={tx(SIZE.xs, WEIGHT.regular, on ? COLOR.text2 : COLOR.text3, { textWrap: "balance" })}>{cc.basis}</p>}
      {cc.plain && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1) + 2, lineHeight: 1.4, textWrap: "balance" })}>{cc.plain}</p>}
      {on && top != null && <span style={{ marginTop: SPACE(2) }}><StatusChip tone="neutral">{fill(s1.topPct, { pct: top })}</StatusChip></span>}
      {c.id === "stable" && on && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{s1.finNA}</p>}
      {c.pending ? (
        <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: "auto", paddingTop: SPACE(3), display: "flex", alignItems: "center", gap: SPACE(1) + 2 })}>
          <Icon name="calendar" size={16} tone="off" /><span>{s1.pendingCard}</span>
        </div>
      ) : (
        <div style={{ marginTop: "auto", paddingTop: SPACE(2), display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <RoundBtn kind="dec" disabled={pts <= 0} label={fill(s1.dec, { card: cc.name })} onClick={() => onSet(Math.max(0, pts - 1))} />
          <span style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: SPACE(1) }}>
            <Dots id={c.id} n={pts} size={8} gap={2} />
            <span data-ui-v2="card-points" aria-live="polite" style={tx(SIZE.xs, WEIGHT.heavy, on ? COLOR.ink : COLOR.text2)}>{fill(s1.score, { score: pts })}</span>
          </span>
          <RoundBtn kind="inc" filled={!on && left > 0} disabled={pts >= max} label={fill(s1.inc, { card: cc.name, n: pts })} onClick={() => onSet(Math.min(max, pts + 1))} />
        </div>
      )}
    </div>
  );
}

// The guide (v19.3c Part E) on this screen: 1 · the 배당 card and its +, 2 · the meter with the pool struck through → the
// count (2.5 s or a tap), 3 · the meter and 알겠어요.
const GUIDE_HOLE = { 1: '[data-card="div"]', 2: '[data-ui-v2="meter"]', 3: '[data-ui-v2="meter"]' };
const GUIDE_RING = '[data-card="div"] [data-ui-v2="card-inc"]';
// When the bubble goes (알겠어요 · 건너뛰기 · Esc), focus lands on the 배당 card's + (where the user goes on), or the meter.
const GUIDE_FOCUS_AFTER = [`${GUIDE_RING}:not(:disabled)`, '[data-ui-v2="meter"]'];
// Step 1 keeps the + clear of the sticky meter above and the action bar below (a phone held sideways: guide.jsx keepClear).
const GUIDE_KEEP_CLEAR = { top: '[data-ui-v2="meter-bar"]', bottom: '[data-ui-v2="action-bar"]' };

function StepCards({ st, set, ds, coach }) {
  const s1 = C.build.s1;
  const g = C.guide;
  const used = pointsUsed(st.points);
  const left = POINTS_TOTAL - used;
  const top = strictTop(st.strict);
  const setPts = (id, v) => set({ points: { ...st.points, [id]: v } });
  const preview = topOverall(ds.res, 3);
  const stage = coach ? coach.stage : null;
  const divPts = st.points.div || 0;
  useEffect(() => { if (stage === 1 && divPts >= 1) coach.go(2); }, [stage, divPts]);      // the user gave 배당 its first point
  useEffect(() => {
    if (stage !== 2) return undefined;
    const id = window.setTimeout(() => coach.go(3), 2500);
    return () => window.clearTimeout(id);
  }, [stage]);
  const n = meterCount(ds.res).n;
  const bubble = stage === 1 ? { title: g.s1[0], body: g.s1[1] }
    : stage === 2 ? { title: fill(g.s2[0], { n: nf(n) }), body: top == null ? g.s2Loose : fill(g.s2[1], { top }) }
      : stage === 3 ? { title: fill(g.s3[0], { n: left }), body: g.s3[1] } : null;
  return (
    <div>
      <ScreenTitle sub={s1.body}>{s1.title}</ScreenTitle>
      <Meter st={st} ds={ds} left={left} strike={stage === 2} />
      <Card style={{ marginTop: SPACE(1) }}>
        <Label>{s1.strictLabel}</Label>
        <Segmented label={s1.strictAria} value={st.strict} onChange={(v) => set({ strict: v })}
          options={STRICT.map((x) => ({ value: x.id, label: s1.strict[x.id] }))} />
        <Note>{top == null ? s1.looseNote : fill(s1.strictNote, { pct: top })}</Note>
      </Card>
      <div data-ui-v2="card-grid" style={{ marginTop: SPACE(3), display: "grid", gap: SPACE(2),
        gridTemplateColumns: "repeat(auto-fill, minmax(max(136px, calc((100% - 16px) / 3)), 1fr))" }}>
        {CARDS.map((c) => <CriterionCard key={c.id} c={c} pts={st.points[c.id] || 0} left={left} top={top} onSet={(v) => setPts(c.id, v)} />)}
      </div>
      {activeCards(st.points).length > 0 && (
        <Card data-ui-v2="preview">
          <Label>{s1.preview}</Label>
          {!preview.length && <Note>{s1.previewNone}</Note>}
          {preview.map((x) => {
            const b = bestCard(x, st.points);
            return (
              <div key={x.t} style={{ display: "flex", justifyContent: "space-between", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderTop: `1px solid ${COLOR.line}` }}>
                <span style={{ minWidth: 0 }}>
                  <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{x.s.nk}</span>
                  {b && <CardScores list={[[b.id, b.score]]} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block", marginTop: SPACE(1) })} />}
                </span>
                <span data-ui-v2="preview-score" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { flexShrink: 0 })}>{fill(s1.score, { score: Math.round(x.total) })}</span>
              </div>
            );
          })}
        </Card>
      )}
      {bubble && (
        <Coach stage={stage} hole={GUIDE_HOLE[stage]} ring={stage === 1 ? GUIDE_RING : null} title={bubble.title} body={bubble.body}
          action={stage === 3 ? { label: g.done, onClick: coach.done } : null} onBackdrop={stage === 2 ? () => coach.go(3) : undefined}
          onSkip={coach.skip} onLost={coach.lost} focusAfter={GUIDE_FOCUS_AFTER} keepClear={GUIDE_KEEP_CLEAR} />
      )}
    </div>
  );
}

function StepExclude({ st, set, ds }) {
  const s3 = C.build.s3;
  const order = ["warned", "loss", "young", "debt", "noDiv", "china", "sin", "holding"];
  return (
    <div>
      <ScreenTitle sub={s3.body}>{s3.title}</ScreenTitle>
      <Card style={{ paddingTop: SPACE(2), paddingBottom: SPACE(2) }}>
        {order.map((k) => {
          const sw = s3.switches[k];
          if (EXCLUDE_PENDING.includes(k)) return <Toggle key={k} on={false} disabled label={sw.name} sub={sw.sub} chip={<PendingChip />} onChange={() => {}} />;
          if (!EXCLUDE_LIVE.includes(k)) return null;
          return <Toggle key={k} on={!!st.exclude[k]} label={sw.name} sub={sw.sub} side={fill(C.app.count, { count: nf(ds.res.excludeCounts[k]) })}
            onChange={(v) => set({ exclude: { ...st.exclude, [k]: v } })} />;
        })}
      </Card>
      <Note>{s3.liquidity}</Note>
    </div>
  );
}

function StepTerms({ st, set, ds, load }) {
  const s4 = C.build.s4;
  const amt = st.amountMan;
  const warning = !amt ? s4.amountEmpty : amt < 50 ? s4.under50 : amt > 100000 ? s4.over10 : null;
  const maxN = Math.floor(amt / MIN_PER_STOCK_MAN);
  const mk = marketsOf(st);
  const [q, setQ] = useState("");
  const results = pinnable(load, q, st.pinned);
  const [pinMsg, setPinMsg] = useState(null);
  const cushionOk = cushionStocks(load).length > 0;
  const pin = (s) => {
    const why = canPin(s, ds.pinned);
    if (why === "industry") { setPinMsg(C.pick.limitInd); return; }
    if (why) return;
    setPinMsg(null);
    set({ pinned: [...st.pinned, s.t] });
    setQ("");
  };
  // 2022 line per sizing choice, from the list that 후보 고르기 would pre-select. v19.1b data (Part O.1): each a range from the
  // beta band (deckcalc.y2022View). A choice whose smaller end is not a fall shows plan.y2022Wide in its own cell, the others
  // keep their ranges; when all three are, the line once instead of the three cells.
  const y2022 = useMemo(() => {
    if (!(amt > 0)) return null;
    const picks = pickItems(ds, defaultPicks(ds));
    const out = {};
    for (const m of METHODS) {
      const r = computePlan(load, { ...st, method: m }, picks, ds.pinned);
      out[m] = r.ok && r.y2022.ok ? { won: r.y2022.won, view: y2022View(r.y2022, true) } : null;
    }
    return Object.values(out).every((v) => v != null) ? out : "hide";
  }, [ds, st, load, amt]);
  const wideOf = (m) => !!(y2022 && y2022 !== "hide" && y2022[m].view && y2022[m].view.wide);
  const yWide = METHODS.every(wideOf);
  const yRange = y2022 && y2022 !== "hide" && METHODS.some((m) => !wideOf(m) && y2022[m].view && y2022[m].view.parts.length > 1);
  return (
    <div>
      <ScreenTitle>{s4.title}</ScreenTitle>
      <Card>
        <MoneyInput label={s4.amountLabel} unit={C.app.manUnit} value={amt} onChange={(v) => set({ amountMan: v })}
          quick={[{ label: s4.quick[0], add: 10 }, { label: s4.quick[1], add: 100 }, { label: s4.quick[2], add: 1000 }]} clearLabel={s4.clear} warning={warning} />
        {amt >= 50 && amt <= 100000 && <Note>{fill(s4.perStock, { x: manText(nf(Math.round(amt / st.count))) })}</Note>}
      </Card>
      <Card>
        <Label>{s4.mixLabel}</Label>
        <ChoiceGrid label={s4.mixAria} value={st.mix} onChange={(v) => set({ mix: v })} options={MIX.map((x) => ({ value: x.id, label: s4.mix[x.id] }))} />
        {mk.includes("us") && <Note>{s4.usWhole}</Note>}
      </Card>
      <Card>
        <Stepper value={st.count} min={Math.max(COUNT_RANGE[0], st.pinned.length + 1)} max={COUNT_RANGE[1]} onChange={(v) => set({ count: v })}
          label={s4.countLabel} format={C.app.count} decLabel={s4.countDec} incLabel={s4.countInc} />
        <Note>{s4.countNote}</Note>
        {amt > 0 && st.count > maxN && <Note tone="watch" data-ui-v2="too-many">{fill(s4.tooMany, { amount: manText(nf(amt)), n: Math.max(0, maxN) })}</Note>}
      </Card>
      <Card data-ui-v2="pinned">
        <Label style={{ marginBottom: 0 }}>{s4.pinnedTitle}</Label>
        <Note style={{ marginTop: SPACE(1) }}>{s4.pinnedBody}</Note>
        {st.pinned.map((t) => {
          const s = load.byT.get(t);
          if (!s) return null;
          return (
            <div key={t} style={{ display: "flex", alignItems: "center", gap: SPACE(2), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0 })}>{s.nk}</span>
              <span data-ui-v2="manual-chip"><StatusChip tone="neutral">{C.pick.manual}</StatusChip></span>
              <button type="button" aria-label={fill(s4.removeAria, { name: s.nk })} onClick={() => set({ pinned: st.pinned.filter((x) => x !== t) })}
                style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: "none", background: "none", ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{s4.remove}</button>
            </div>
          );
        })}
        {pinMsg && <Note tone="watch" data-ui-v2="pin-limit">{pinMsg}</Note>}
        {st.pinned.length < PINNED_MAX && (
          <>
            <TextInput label={null} ariaLabel={s4.pinnedTitle} value={q} onChange={setQ} />
            {results.map((s) => (
              <div key={s.t} style={{ display: "flex", alignItems: "center", gap: SPACE(2), padding: `${SPACE(1)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block" })}>{s.nk}</span>
                  <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{s.t}</span>
                </span>
                <button type="button" aria-label={fill(s4.addAria, { name: s.nk })} disabled={st.count <= st.pinned.length + 1}
                  onClick={() => pin(s)}
                  style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, background: COLOR.surface, padding: `0 ${SPACE(3)}px`, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{s4.add}</button>
              </div>
            ))}
          </>
        )}
      </Card>
      <Card>
        <Label>{s4.methodLabel}</Label>
        <Segmented label={s4.methodLabel} value={st.method} onChange={(v) => set({ method: v })} options={METHODS.map((m) => ({ value: m, label: s4.method[m] }))} />
        <Note>{s4.methodNote[st.method]}</Note>
        {y2022 !== "hide" && (
          <div data-ui-v2="y2022-methods" style={{ marginTop: SPACE(3) }}>
            <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink)}>{s4.y2022Label}</div>
            {!y2022 ? <Note>{s4.y2022Empty}</Note> : yWide ? <Note data-ui-v2="y2022-wide">{C.plan.y2022Wide}</Note> : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: SPACE(1), marginTop: SPACE(1) }}>
                {METHODS.map((m) => (
                  <div key={m} data-method={m} style={tx(SIZE.xs, m === st.method ? WEIGHT.heavy : WEIGHT.regular, m === st.method ? COLOR.ink : COLOR.text2, { textAlign: "center", minWidth: 0 })}>
                    {wideOf(m) ? <span data-ui-v2="y2022-wide">{C.plan.y2022Wide}</span>
                      : y2022[m].view ? <Y2022Amount v={y2022[m].view} /> : aboutWon(y2022[m].won)}
                  </div>
                ))}
              </div>
            )}
            {yRange && C.plan.y2022Range && <div data-ui-v2="y2022-range-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{C.plan.y2022Range}</div>}
            {y2022 && <div data-ui-v2="y2022-source" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{C.plan.y2022Source}</div>}
          </div>
        )}
        <div style={{ display: "flex", gap: SPACE(2), alignItems: "flex-start", marginTop: SPACE(3) }}>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { flex: 1 })}>{s4.eventNote}</span>
          <PendingChip />
        </div>
      </Card>
      <Card>
        <Label>{s4.maxLabel}</Label>
        <Segmented label={s4.maxLabel} value={st.maxPct} onChange={(v) => set({ maxPct: v })} options={MAX_PCTS.map((p) => ({ value: p, label: `${p}%` }))} />
      </Card>
      {cushionOk && (
        <Card>
          <Label style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}><IconChip name="umbrella" size={32} /><span>{s4.cushionLabel}</span></Label>
          <Segmented label={s4.cushionAria} value={st.cushion} onChange={(v) => set({ cushion: v })}
            options={CUSHIONS.map((p) => ({ value: p, label: p === 0 ? C.app.none : `${p}%` }))} />
          <Note>{s4.cushionNote}</Note>
        </Card>
      )}
      <Card>
        <TextInput label={s4.nameLabel || C.deck.title} value={st.name} onChange={(v) => set({ name: v.slice(0, 30) })} />
      </Card>
    </div>
  );
}

