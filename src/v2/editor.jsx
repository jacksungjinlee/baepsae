// ================= 종목 바꾸기 (v19.7a Part A, board PfEdit3) · 빼기 (Part B, PfRemove3) · 이름으로 찾기 · 담기 (Part C) =================
// #portfolio/edit/<portfolio id>, for a portfolio made with 포트폴리오 만들기 (targets and per-stock rules). The screen edits a
// draft (edit.js: the maths and the store edits); nothing is saved until 바꾼 내용 저장, except 팔고 빼기, which records money
// and so saves at once with the removal it belongs to ([B4]: v19.6a's 팔았어요 sheet, prefilled with every held share).
// The draft lives in the app (app.jsx editor), so moving to another tab and back keeps it; the screen's back button asks
// "바꾼 내용을 저장하지 않고 나갈까요?" when anything is waiting. Stale data: everything still works, with the date line's stale
// words (the 규칙 깨짐 lines need fresh data and are left out then). Failed data: the load-failure message instead of the
// list. No 뱁이 (the screen shows weights and scores). No Korean here: src/copy/v2.js.
import React, { useEffect, useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, holdingShades, HOLDING_SHADES } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Button, BottomSheet, StatusChip } from "../ui/components.jsx";
import { C, fill, nf, todayKst, recDate } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, tx, tap, useLayout, useMode, SIDE_W, SampleLabel } from "./ui.jsx";
import { priceDate } from "./cofmt.js";
import { CoMark } from "./logo.jsx";
import { writeStore } from "./store.js";
import { evaluateDeck, todayCtx } from "./rules.js";
import { objectParticle } from "./track.js";
import { searchStocks } from "./stocklist.js";
import { warnings } from "./warn.js";
import { icrOffShown } from "./fix.js";
import { warnKind, uncheckedCount } from "./company.js";
import { activeCards } from "./engine.js";
import { criteriaPct } from "./fitpct.js";
import { RecordFlow } from "./records.jsx";
import { stockState } from "./records.js";
import * as E from "./edit.js";

const qtyText = (q) => Number(q).toLocaleString("ko-KR", { maximumFractionDigits: 4 });
const ownMoney = (v, ccy) => (ccy === "USD" ? "$" + nf(v, 2) : fill(C.app.won, { n: nf(Math.round(v)) }));
const pctText = (p) => { const x = E.pctShown(p); return nf(x.n, x.d); };
const won = (v) => nf(Math.round(v));
// "왜 빼나요? (선택)": the question, and its "(선택)" in the board's lighter weight
const splitWhy = (t) => { const m = /^(.*?)\s*(\([^)]*\))$/.exec(String(t || "")); return m ? [m[1], m[2]] : [t, ""]; };
// the accessible names of − and + (Jack, 2026-11-13)
const downLabel = (name) => fill(C.edit.down, { name });
const upLabel = (name) => fill(C.edit.up, { name });

// The 규칙 깨짐 line of a holding whose sell condition fired today: the words the 포트폴리오 screen uses for that rule. A sold-out
// kept holding failing a rule at that level gets the same line, box and pre-picked reason as a held stock (E.brokenReason).
function brokenPieces(x) {
  const r = E.brokenReason(x);
  if (!r) return null;
  if (r.code === "divCut") return [C.plan.rules.divCut, fill(C.plan.rules.dpsChange, { a: won(r.a), b: won(r.b) })];
  return [];
}
function BrokenLine({ x, boxed = false }) {
  const pieces = brokenPieces(x);
  if (!pieces) return null;
  return (
    <div data-ui-v2="edit-broken" style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(2),
      ...(boxed ? { background: COLOR.watchBg, borderRadius: RADIUS.md, padding: `${SPACE(2) + 2}px ${SPACE(3)}px` } : { marginLeft: SPACE(11) + 2 }) }}>
      <Icon name="warning" size={boxed ? 18 : 16} tone="on" />
      <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.watch, { wordBreak: "keep-all" })}><b>{C.daily.broken}</b>{pieces.map((p, i) => <span key={i}>{" · "}{p}</span>)}</span>
    </div>
  );
}

// The stacked bar of target weights by industry group, with its legend (navy shades by weight, never logo colours).
function IndBar({ parts }) {
  const shades = holdingShades(parts.map((p) => p.pct));
  const total = parts.reduce((a, p) => a + p.pct, 0) || 1;
  return (
    <div data-ui-v2="edit-ind-bar">
      <div aria-hidden="true" style={{ display: "flex", gap: 2, borderRadius: 7, overflow: "hidden", height: 14, background: COLOR.page }}>
        {parts.map((p, i) => <span key={p.key || "none"} style={{ width: `${(p.pct / total) * 100}%`, background: shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1] }} />)}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap" }}>
        {parts.map((p, i) => (
          <span key={p.key || "none"} data-ui-v2="edit-ind-part" data-ind={p.key} data-pct={Math.round(p.pct * 100) / 100}
            style={{ ...tx(SIZE.xs, WEIGHT.regular, COLOR.neutral), display: "inline-flex", alignItems: "center", gap: 5, margin: `${SPACE(2)}px ${SPACE(3)}px 0 0` }}>
            <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 3, background: shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1], flexShrink: 0 }} />
            {p.cushion ? C.build.s4.cushionLabel : p.name || C.rpt.noInd} <b style={{ color: COLOR.ink }}>{pctText(p.pct)}%</b>
          </span>
        ))}
      </div>
    </div>
  );
}

// − 25% +: 44 px each way. + at its limit is aria-disabled and dimmed but still answers a tap: at the cap, the row then says
// why it cannot go higher (spec [C2]); the value and that line are read out when they change (aria-live).
function Stepper({ name, pct, onDown, onUp, downOff, upOff }) {
  const btn = (off) => ({ ...tap, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center",
    opacity: off ? 0.4 : 1, cursor: off ? "default" : "pointer", flexShrink: 0, ...tx(SIZE.h3, WEIGHT.semi, COLOR.text2, { lineHeight: 1 }) });
  return (
    <span data-ui-v2="edit-stepper" style={{ display: "inline-flex", alignItems: "center", background: COLOR.page, borderRadius: RADIUS.sm, flexShrink: 0 }}>
      <button type="button" data-ui-v2="edit-down" aria-label={downLabel(name)} disabled={downOff} onClick={onDown} style={btn(downOff)}><span aria-hidden="true">{"\u2212"}</span></button>
      <b data-ui-v2="edit-pct" aria-live="polite" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { minWidth: SPACE(11), textAlign: "center" })}>{pctText(pct)}%</b>
      <button type="button" data-ui-v2="edit-up" aria-label={upLabel(name)} aria-disabled={upOff ? "true" : undefined} onClick={onUp} style={btn(upOff)}><span aria-hidden="true">+</span></button>
    </span>
  );
}

// One holding of the edited list: logo, name, "지금 {qty}주 · {industry}", the stepper and 빼기 (on a phone the two go on a
// line of their own under the name, so a 320 px screen keeps every target 44 px wide and the name readable).
function Row({ r, qty, ind, x, cap, rows, onStep, onRemove, capHit, only }) {
  const limits = E.stepLimits(rows, r.t, cap, E.storedPct(r));
  const downOff = E.stepped(rows, r.t, -1, cap, E.storedPct(r)) == null;
  const upOff = E.stepped(rows, r.t, 1, cap, E.storedPct(r)) == null;
  const atCap = cap != null && upOff && limits.byCap && r.pct >= limits.hi - 1e-9;
  const controls = (
    <div style={{ display: "flex", alignItems: "center", gap: SPACE(1), flexShrink: 0, marginLeft: "auto" }}>
      <Stepper name={r.nk} pct={r.pct} downOff={downOff} upOff={upOff} onDown={() => onStep(r.t, -1)} onUp={() => onStep(r.t, 1)} />
      <button type="button" data-ui-v2="edit-remove" aria-label={fill(C.build.s4.removeAria, { name: r.nk })} disabled={only} onClick={() => onRemove(r.t)}
        style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: "none", background: "none", opacity: only ? 0.4 : 1, cursor: only ? "default" : "pointer",
          ...tx(SIZE.xs, WEIGHT.bold, COLOR.neutral) }}>{C.build.s4.remove}</button>
    </div>
  );
  return (
    <div data-edit-row={r.t} data-pct={Math.round(r.pct * 1000) / 1000} data-added={r.add ? "1" : undefined}
      style={{ padding: `${SPACE(2) + 2}px 0`, borderTop: `1px solid ${COLOR.line}` }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", columnGap: SPACE(2) + 2, rowGap: SPACE(1) }}>
        <CoMark t={r.t} name={r.nk} s={r.add ? r.add.s : undefined} size={SPACE(9)} />
        <div style={{ flex: "1 1 120px", minWidth: 0 }}>
          <div style={tx(SIZE.body - 1, WEIGHT.bold, COLOR.ink, { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" })}>{r.nk}</div>
          <div data-ui-v2="edit-row-sub" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2, wordBreak: "keep-all" })}>
            {fill(C.edit.row, { qty: qtyText(qty), industry: ind === E.CUSHION ? C.build.s4.cushionLabel : ind || C.rpt.noInd })}</div>
        </div>
        {controls}
      </div>
      <BrokenLine x={x} />
      <div aria-live="polite">{capHit === r.t && atCap && <Note data-ui-v2="edit-max">{fill(C.edit.max, { x: cap })}</Note>}</div>
      {only && <Note data-ui-v2="edit-last">{C.rm.last}</Note>}
    </div>
  );
}

// deck: the stored portfolio (the app's view of it); draft / setDraft: the edits waiting (app.jsx). onLeave: back to
// 포트폴리오 (the draft dropped); onSaved: after 바꾼 내용 저장.
// startRemove (Jack 2026-11-13, J4): a stock whose 빼기 sheet opens with the screen (the "다 판 종목이에요. …" line on 포트폴리오
// and on the company page); onStarted: called once it has opened.
export function Editor({ deck, load, store, setStoreData, draft: raw, setDraft, pad, onLeave, onSaved, startRemove = null, onStarted = null }) {
  const { wide } = useLayout();
  const ok = load.status === "ok";
  const draft = useMemo(() => E.rebaseDraft(deck, raw), [deck, raw]);
  const [sheet, setSheet] = useState(() => (startRemove ? { kind: "remove", t: startRemove } : null));   // { kind: "remove", t } | { kind: "find" } | { kind: "add", s } | { kind: "leave" }
  useEffect(() => { if (startRemove && onStarted) onStarted(); }, []);
  const [flow, setFlow] = useState(null);                // 팔고 빼기: v19.6a's 팔았어요 sheet (records.jsx RecordFlow)
  const [capHit, setCapHit] = useState(null);
  const [fail, setFail] = useState(null);                // "storage" | "refused"
  const ctx = useMemo(() => todayCtx(load), [load]);
  const de = useMemo(() => (ctx.state.ok ? evaluateDeck(deck, ctx) : null), [deck, ctx]);
  const xOf = (t) => (de && de.ok ? de.holdings.find((y) => y.t === t) || null : null);
  const names = useMemo(() => (ok ? E.indNames(load.data.stocks) : new Map()), [load, ok]);
  const back = () => (E.pending(deck, draft) ? setSheet({ kind: "leave" }) : onLeave());
  const writable = store.writable && !store.locked;
  const shift = wide ? SIDE_W : 0;
  // "바꾼 내용을 저장하지 않고 나갈까요?": staying (닫기) is the main button and leaving (나가기, edit.leaveGo: Jack 2026-11-13) the
  // second one (round-1 S5: nothing is dropped by the button under the thumb)
  const leaveSheet = sheet && sheet.kind === "leave" && (
    <BottomSheet open title={C.edit.leave} onClose={() => setSheet(null)} closeLabel={C.app.close} shift={shift}>
      <div data-ui-v2="edit-leave" style={{ display: "flex", gap: SPACE(2), marginTop: SPACE(2) }}>
        <Button onClick={() => setSheet(null)} style={{ flex: 1 }}>{C.app.close}</Button>
        <Button kind="secondary" data-go="leave" onClick={() => { setSheet(null); onLeave(); }} style={{ flex: 1 }}>{C.edit.leaveGo}</Button>
      </div>
    </BottomSheet>
  );
  if (!ok) {
    // the load-failure screen: its back button asks too before a waiting edit is dropped (round-1 nit)
    return (
      <>
        <Page pad={pad}>
          <AppBar onBack={back} backLabel={C.app.tabs.portfolio} />
          <ScreenTitle sub={C.edit.sub}>{C.edit.title}</ScreenTitle>
          {load.status === "fail" && <LoadFail picture={false} />}
          <Footer />
        </Page>
        {leaveSheet}
      </>
    );
  }
  const rows = E.editRows(deck, draft);
  const cap = E.capOf(deck, draft);
  const sum = E.sumPct(rows);
  const good = E.sumOk(sum);
  const shown = E.sumShown(sum);
  const d2 = E.d2Of(rows, cap);
  const bar = E.indBar(rows, load.byT, names);
  const held = (t) => E.heldShares(deck, t);
  const set = (f) => { setFail(null); setCapHit(null); setDraft(f); };
  const onStep = (t, dir) => {
    const p = E.stepped(rows, t, dir, cap, E.storedPct(rows.find((r) => r.t === t)));
    if (p == null) { if (dir > 0) setCapHit(t); return; }
    set((d) => E.stepDraft(E.rebaseDraft(deck, d), t, p));
  };
  const canSave = good && !d2.low && rows.length > 0 && writable;
  const save = () => {
    if (!canSave) return;
    if (!E.pending(deck, draft)) { onSaved(); return; }
    const today = todayKst();
    const r = E.applyEdit(store.data, deck.id, draft, { load, today, ts: Date.now() });
    if (!r.ok) { console.warn("[v2] portfolio edit not saved: " + r.why); setFail("refused"); return; }
    if (!writeStore(r.data, store.key, today)) { setFail("storage"); return; }
    setStoreData(r.data, true);
    console.info(`[v2] ${deck.id}: portfolio edit saved (${(draft.adds || []).length} added, ${(draft.removed || []).length} taken out)`);
    onSaved();
  };
  // 팔고 빼기: the sale sheet; its save takes the stock out with the reason in the same write, its stored target shared out
  // under this portfolio's cap as edited (the sheet's D2 button, or a raise already waiting in the draft, saved with it). The
  // draft then follows the saved portfolio (edit.draftAfterSale): with nothing else waiting it is what was stored.
  const sellOut = (t, nk, reason, raise) => {
    setSheet(null);
    const up = raise != null ? raise : E.sellCheck(deck, draft, t).up;
    const before = deck;
    // every held share, locked (round-1 B2: a smaller sale would drop the unsold shares from 내 수익; that is 팔았어요's job)
    setFlow({ stage: "sell", deckId: deck.id, t, nk, prefill: { qty: held(t) }, lockQty: true,
      finish: (next) => E.sellAndRemove(next, deck.id, t, { reason, raise: up, load, today: todayKst(), ts: Date.now() }),
      after: (next) => {
        setFail(null);
        // round 3: what still waits, rebased onto the portfolio as the sale saved it (edit.draftAfterSale)
        const saved = next && Array.isArray(next.decks) ? next.decks.find((d) => d && d.id === before.id) || null : null;
        setDraft((d) => E.draftAfterSale(before, saved, E.rebaseDraft(before, d), t));
      } });
  };
  const removeNow = (t, reason) => { setSheet(null); set((d) => E.removeDraft(deck, E.rebaseDraft(deck, d), t, reason)); };
  const logs = E.changeList(deck);                       // 바꾼 기록, at the bottom of this screen (Jack, 2026-11-13)
  const nameOf = (c) => c.nk || ((deck.holdings || []).find((h) => h.t === c.t) || {}).nk || c.t;
  const cur = sheet && sheet.kind === "remove" ? rows.find((r) => r.t === sheet.t) || null : null;
  return (
    <>
      <Page pad={pad}>
        <AppBar onBack={back} backLabel={C.app.tabs.portfolio} />
        <DateLine date={load.data.pxDate} fresh={load.fresh} />
        <div data-ui-v2="edit" data-deck-id={deck.id}>
          <ScreenTitle sub={C.edit.sub}>{C.edit.title}</ScreenTitle>
          {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
          {store.locked && <Note tone="watch">{C.store.locked}</Note>}
          <Card data-ui-v2="edit-ind" style={{ padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
            <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginBottom: SPACE(2) })}>{C.edit.ind}</h3>
            <IndBar parts={bar} />
          </Card>
          <Card data-ui-v2="edit-list" style={{ padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), marginBottom: SPACE(2) }}>
              <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{C.edit.targets}</h3>
              <span data-ui-v2="edit-sum" data-sum={Math.round(sum * 1000) / 1000} data-ok={good ? "1" : "0"}
                style={tx(SIZE.xs, WEIGHT.bold, good ? COLOR.ink : COLOR.watch)}>{fill(C.edit.sum, { x: nf(shown.n, shown.d) })}</span>
            </div>
            {rows.map((r) => (
              <Row key={r.t} r={r} qty={held(r.t)} ind={E.indOf(r, load.byT, names)} x={xOf(r.t)} cap={cap} rows={rows} capHit={capHit}
                only={rows.length === 1} onStep={onStep} onRemove={(t) => setSheet({ kind: "remove", t })} />
            ))}
            {d2.low && (
              <div data-ui-v2="edit-cap-low" style={{ marginTop: SPACE(3) }}>
                <Note tone="watch">{fill(C.edit.capLow, { n: rows.length, x: cap })}</Note>
                <div style={{ marginTop: SPACE(2) }}><Button kind="secondary" onClick={() => { setCapHit(null); set((d) => E.raiseDraft(deck, E.rebaseDraft(deck, d))); }}>
                  {fill(C.edit.capRaise, { y: d2.y })}</Button></div>
              </div>
            )}
            {!d2.low && !good && rows.length > 0 && (
              <div data-ui-v2="edit-fix" style={{ marginTop: SPACE(3) }}>
                <Button kind="secondary" onClick={() => { setCapHit(null); set((d) => E.fixDraft(deck, E.rebaseDraft(deck, d))); }}>{C.edit.fix}</Button>
              </div>
            )}
          </Card>
          <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { margin: `${SPACE(4)}px ${SPACE(1)}px 0` })}>{C.edit.addTitle}</h3>
          <div style={{ display: "grid", gridTemplateColumns: wide ? "repeat(2, minmax(0, 1fr))" : "minmax(0, 1fr)", gap: SPACE(2), marginTop: SPACE(2) }}>
            <button type="button" data-ui-v2="edit-by-name" onClick={() => setSheet({ kind: "find" })}
              style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(2) + 2, padding: SPACE(3), borderRadius: RADIUS.md, background: COLOR.surface,
                border: "none", textAlign: "left", minHeight: TOUCH + SPACE(4) }}>
              <span style={{ width: 34, height: 34, borderRadius: 10, background: COLOR.select, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Icon name="magnifying-glass" size={21} tone="on" />
              </span>
              <span style={{ minWidth: 0 }}>
                <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{C.edit.byName}</span>
                <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{C.edit.byNameSub}</span>
              </span>
            </button>
          </div>
          <div style={{ marginTop: SPACE(4) }}>
            <Button onClick={save} disabled={!canSave}>{C.edit.save}</Button>
          </div>
          <p data-ui-v2="edit-save-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(2)}px ${SPACE(1)}px 0`, wordBreak: "keep-all" })}>{C.edit.saveNote}</p>
          {fail === "storage" && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
          {fail === "refused" && <Note tone="watch" data-ui-v2="edit-save-fail">{C.edit.saveFail}</Note>}
          {logs.length > 0 && (
            <Card data-ui-v2="edit-log">
              <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.edit.log}</h3>
              <ul style={{ listStyle: "none", margin: `${SPACE(2)}px 0 0`, padding: 0 }}>
                {logs.map((c) => {
                  const date = recDate(c.at, todayKst());
                  const reason = c.reason && C.rm.reasons[c.reason];
                  const text = c.kind === "add" ? fill(C.edit.logAdd, { date, name: nameOf(c) }) : c.kind === "targets" ? fill(C.edit.logTargets, { date })
                    : reason ? fill(C.edit.logRemove, { date, name: nameOf(c), reason }) : fill(C.edit.logRemove.replace(/ · \{reason\}$/, ""), { date, name: nameOf(c) });
                  return <li key={c.i} data-change={c.kind} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { padding: `${SPACE(1)}px 0`, borderTop: `1px solid ${COLOR.line}` })}>{text}</li>;
                })}
              </ul>
            </Card>
          )}
        </div>
        <Footer />
      </Page>
      {/* the sheets sit outside Page: Page's wrapper changes at the PC width (1024 px), and what is typed must survive it */}
      {cur && <RemoveSheet key={cur.t} deck={deck} draft={draft} row={cur} x={xOf(cur.t)} shift={shift} writable={writable} onClose={() => setSheet(null)}
        onSell={sellOut} onRemove={removeNow} />}
      {sheet && sheet.kind === "find" && <FindSheet load={load} rows={rows} draft={draft} shift={shift} onClose={() => setSheet(null)}
        onPick={(s) => setSheet({ kind: "add", s })} />}
      {sheet && sheet.kind === "add" && <AddSheet deck={deck} draft={draft} s={sheet.s} load={load} cap={cap} shift={shift} onClose={() => setSheet(null)}
        onAdd={(add, pct) => { setSheet(null); setCapHit(null); set((d) => E.addDraft(deck, E.rebaseDraft(deck, d), add, pct)); }} />}
      {leaveSheet}
      <RecordFlow flow={flow} setFlow={setFlow} load={load} store={store} setStoreData={setStoreData} />
    </>
  );
}

// 왜 빼나요? (선택): four chips, one choice or none. A radio group the keyboard can use: arrows move and choose, Space or Enter
// on the chosen one clears it (the choice is optional); one chip is in the tab order.
function Reasons({ value, onChange, q, opt }) {
  const refs = React.useRef([]);
  const at = Math.max(0, E.REASONS.indexOf(value));
  const key = (e, i) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const j = (i + step + E.REASONS.length) % E.REASONS.length;
    onChange(E.REASONS[j]);
    const el = refs.current[j];
    if (el) el.focus();
  };
  return (
    <>
      <p style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { margin: `${SPACE(4)}px 0 ${SPACE(2)}px` })}>
        {q}{opt && <span style={{ fontWeight: WEIGHT.regular, color: COLOR.text3 }}>{" "}{opt}</span>}
      </p>
      <div role="radiogroup" aria-label={C.rm.why} data-ui-v2="rm-reasons" style={{ display: "flex", flexWrap: "wrap", gap: SPACE(2) }}>
        {E.REASONS.map((k, i) => {
          const on = value === k;
          return (
            <button key={k} ref={(el) => { refs.current[i] = el; }} type="button" role="radio" aria-checked={on ? "true" : "false"} data-reason={k}
              tabIndex={i === at ? 0 : -1} onKeyDown={(e) => key(e, i)} onClick={() => onChange(on ? null : k)}
              style={{ ...tap, minHeight: TOUCH, padding: `0 ${SPACE(3) + 2}px`, borderRadius: TOUCH / 2, border: on ? `1.5px solid ${COLOR.ink}` : `1.5px solid ${COLOR.border}`,
                background: on ? COLOR.ink : COLOR.surface, ...tx(SIZE.xs, WEIGHT.bold, on ? COLOR.surface : COLOR.ink, { wordBreak: "keep-all" }) }}>{C.rm.reasons[k]}</button>
          );
        })}
      </div>
    </>
  );
}

// ---------------- 빼기 (Part B) ----------------
function RemoveSheet({ deck, draft, row, x, shift, writable, onClose, onSell, onRemove }) {
  const { preview } = useMode();
  const st = row.h ? stockState(deck, row.t) : null;
  const held = !!st && st.held > 0;
  const broken = !!brokenPieces(x);
  const [reason, setReason] = useState(broken ? "rule" : null);
  const [raise, setRaise] = useState(null);
  // 팔고 빼기 saves to the stored portfolio at once: its last-holding rule and D2 read the stored holdings left (round-1 B1)
  const sc = E.sellCheck(deck, draft, row.t);
  const chk = { low: sc.low, y: sc.y };
  const n = sc.n, cap = sc.cap;
  const pendingRows = (draft.adds || []).length > 0 || (draft.removed || []).length > 0;
  const blocked = held && (sc.last || !writable || (chk.low && raise == null));
  const title = fill(objectParticle(row.nk) === "eul" ? C.rm.title : C.rm.titleReul, { name: row.nk });
  const head = held ? (st.avg ? fill(C.rec.head, { qty: qtyText(st.qty), price: ownMoney(st.avg.avg, st.avg.ccy) }) : fill(C.rec.heldQty, { qty: qtyText(st.qty) })) : null;
  const records = !!row.h && ["sales", "divs"].some((k) => (deck[k] || []).some((r) => r && r.t === row.t));
  const [q, opt] = splitWhy(C.rm.why);
  const kept = String(C.rec.fullSale || "").replace(/^.+?\?\s*/, "");      // 판 기록과 배당 기록은 내 수익에 남아요.
  return (
    <BottomSheet open title={title} onClose={onClose} closeLabel={C.app.close} shift={shift}>
      {preview && <div style={{ marginBottom: SPACE(2) }}><SampleLabel /></div>}
      <div data-ui-v2="rm-sheet" data-t={row.t} data-held={held ? "1" : "0"}>
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
          <CoMark t={row.t} name={row.nk} s={row.add ? row.add.s : undefined} size={SPACE(11)} />
          <div style={{ minWidth: 0 }}>
            <div style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{row.nk}</div>
            {head && <div data-ui-v2="rm-head" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { wordBreak: "keep-all" })}>{head}</div>}
          </div>
        </div>
        <BrokenLine x={x} boxed />
        {/* a 담기 row waiting to be saved has no reason to give (it was never held): no chips (round-1 nit) */}
        {!row.add && <Reasons value={reason} onChange={setReason} q={q} opt={opt} />}
        {held && sc.last && <Note data-ui-v2="rm-last">{C.rm.last}</Note>}
        {held && !sc.last && chk.low && raise == null && (
          <div data-ui-v2="rm-cap-low" style={{ marginTop: SPACE(3) }}>
            <Note tone="watch">{fill(C.edit.capLow, { n, x: cap })}</Note>
            {/* round-2: the line counts the SAVED stocks left (팔고 빼기 saves at once); while 담기 or 빼기 wait, the list above shows
                others, so the {n} stocks it means are named (their names, no new words) */}
            {pendingRows && <p data-ui-v2="rm-stored" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(1)}px ${SPACE(1)}px 0`, wordBreak: "keep-all" })}>{sc.names.join(" · ")}</p>}
            <div style={{ marginTop: SPACE(2) }}><Button kind="secondary" onClick={() => setRaise(chk.y)}>{fill(C.edit.capRaise, { y: chk.y })}</Button></div>
          </div>
        )}
        <div style={{ display: "grid", gap: SPACE(2), marginTop: SPACE(4) }}>
          {held ? (
            <>
              <Button disabled={blocked} onClick={() => !blocked && onSell(row.t, row.nk, reason, raise)}>{C.rm.sell}</Button>
              <Button kind="secondary" onClick={() => onRemove(row.t, reason)}>{C.rm.noRecord}</Button>
            </>
          ) : <Button onClick={() => onRemove(row.t, reason)}>{C.rec.remove}</Button>}
        </div>
        {held && <p data-ui-v2="rm-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3), lineHeight: 1.5, wordBreak: "keep-all" })}>{fill(C.rm.note, { qty: qtyText(st.qty) })}</p>}
        {!held && records && kept && <p data-ui-v2="rm-kept" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3), wordBreak: "keep-all" })}>{kept}</p>}
      </div>
    </BottomSheet>
  );
}

// ---------------- 이름으로 찾기 (Part C): the 종목 tab's own search, without the stocks already in this portfolio ----------------
function FindSheet({ load, rows, draft, shift, onClose, onPick }) {
  const [q, setQ] = useState("");
  const out = new Set([...rows.map((r) => r.t), ...(draft.removed || []).map((r) => r.t)]);
  const results = useMemo(() => searchStocks(load, q, 30).filter((s) => !out.has(s.t)).slice(0, 20), [load, q, rows, draft]);
  const typing = q.trim().length > 0;
  return (
    <BottomSheet open title={C.edit.byName} onClose={onClose} closeLabel={C.app.close} shift={shift}>
      <div data-ui-v2="find-sheet">
        <label style={{ display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH + SPACE(1), background: COLOR.surface,
          border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.md, padding: `0 ${SPACE(3)}px` }}>
          <Icon name="search" size={20} tone="off" />
          {/* type text, not search: no browser-drawn clear button (its own colour, under 44 px; round-1 nit) */}
          <input type="text" value={q} onChange={(e) => setQ(e.target.value.slice(0, 40))} aria-label={C.stocks.search} placeholder={C.stocks.search}
            enterKeyHint="search" autoComplete="off" data-ui-v2="find-input"
            style={{ flex: 1, minWidth: 0, border: "none", outline: "none", background: "none", minHeight: TOUCH, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
        </label>
        {typing && !results.length && <Note data-ui-v2="find-none">{C.stocks.noResult}</Note>}
        {results.length > 0 && (
          <ul data-ui-v2="find-results" style={{ listStyle: "none", margin: `${SPACE(2)}px 0 0`, padding: 0 }}>
            {results.map((s) => (
              <li key={s.t} style={{ borderBottom: `1px solid ${COLOR.line}` }}>
                <button type="button" data-find={s.t} aria-label={fill(C.build.s4.addAria, { name: s.nk })} onClick={() => onPick(s)}
                  style={{ ...tap, width: "100%", minHeight: TOUCH + SPACE(2), display: "flex", alignItems: "center", gap: SPACE(3), border: "none", background: "none",
                    padding: `${SPACE(1)}px 0`, textAlign: "left" }}>
                  <CoMark s={s} t={s.t} name={s.nk} size={SPACE(9)} />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{s.nk}</span>
                    <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{s.t} · {C.pick.market[s.ccy === "USD" ? "us" : "kr"]}</span>
                  </span>
                  <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { flexShrink: 0, padding: `0 ${SPACE(1)}px` })}>{C.build.s4.add}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </BottomSheet>
  );
}

// ---------------- 담기 (Part C) ----------------
// The stock's logo, name and industry, its 내 기준 상위 {x}% for this portfolio (fitpct.criteriaPct; a stock it cannot score
// is 직접 추가, with the build step's note), its 재무 경고 count (the company page's rule), and a 목표 비중 stepper from an
// equal share, with the others scaled in proportion and the 업종 비중 bar after the change. Nothing is saved here.
function AddSheet({ deck, draft, s, load, cap, shift, onClose, onAdd }) {
  const { preview } = useMode();
  const points = (deck.settings && deck.settings.points) || {};
  const hasPoints = activeCards(points).length > 0;
  const mk = s.cls === "us" ? "us" : "kr";
  const fit = hasPoints ? criteriaPct(load.data.stocks, mk, points).get(s.t) : undefined;
  const scored = typeof fit === "number";
  // by name, as the build step's 꼭 담을 종목: kind "pinned" (its rules and reasons, edit.newHolding); the chip says 직접 추가 only
  // when the portfolio's 기준 cannot score it (spec Part C)
  const add = { t: s.t, nk: s.nk, cls: s.cls === "us" || s.cls === "kr" ? s.cls : null, ind: s.ind || null, kind: "pinned", s };
  const rows = E.editRows(deck, draft);
  const n = rows.length;
  const [pct, setPct] = useState(() => E.addDefault(n, cap));
  const hi = Math.min(cap != null ? cap : 100, 100 - n * E.MIN_PCT);
  const after = E.addPreview(deck, draft, add, Math.min(pct, hi));
  const names = useMemo(() => E.indNames(load.data.stocks), [load]);
  const bar = E.indBar(after, load.byT, names);
  const indName = E.indOf({ t: s.t, add }, load.byT, names);
  const ind = s.cls === "us" && indName ? fill(C.pick.usInd, { ind: indName }) : indName;
  const w = s.cls === "kr" ? warnings(s, load.coByT.get(s.t) || null) : null;
  const W = C.co.warn;
  // The company page's rule (company.js warnKind, Jack 2026-11-14): a count when a check fired, "…없어요" only when every check
  // ran, "확인한 …" when only some did (PR #68's case and the new "some" case), "재무 경고" when none could
  // run. A short line here: no ✓ chips in this sheet (as for "없어요"); under the row the company page's reason lines (Jack,
  // 2026-11-14): the 이자보상배율 one (warn.js icrIe), "4가지 중 {k}가지는 …" for the other checks that could not run, and
  // "필요한 자료가 없어서 확인하지 못했어요." when none could.
  const kind = warnKind(s, w);
  const warnLine = kind === "flags" ? fill(W.count, { n: w.flags.length }) : kind === "partial" || kind === "some" ? W.nonePartial : kind === "none" ? W.none : null;
  const unchecked = kind === "unchecked" && !!C.rank.warn && !!W.noData;      // "재무 경고" in the row, Jack's reason line under it
  const noIcr = w && w.icrIe && W.noneSubNoIcr ? W.noneSubNoIcr : null;
  const k = (kind === "flags" || kind === "some") ? uncheckedCount(w, icrOffShown(load.coByT.get(s.t) || null)) : 0;
  const why = noIcr || (k && W.uncheckedN ? fill(W.uncheckedN, { k }) : null) || (unchecked && W.noData ? W.noData : null);
  const step = (dir) => setPct((p) => { const x = Math.min(p, hi) + dir; return x < E.MIN_PCT || x > hi ? p : x; });
  const p = Math.min(pct, hi);
  const [capHit, setCapHit] = useState(false);
  return (
    <BottomSheet open title={C.build.s4.add} onClose={onClose} closeLabel={C.app.close} shift={shift}>
      {preview && <div style={{ marginBottom: SPACE(2) }}><SampleLabel /></div>}
      <div data-ui-v2="add-sheet" data-t={s.t} data-kind={add.kind} data-scored={scored ? "1" : "0"}>
        {/* the stock's own close date (a US stock: its US close, as on its company page; round-1 nit) */}
        <DateLine date={priceDate(load, s)} fresh={load.fresh} style={{ marginTop: 0 }} />
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(3), marginTop: SPACE(2) }}>
          <CoMark s={s} t={s.t} name={s.nk} size={SPACE(11)} />
          <div style={{ minWidth: 0 }}>
            <div style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{s.nk}</div>
            <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{ind || C.rpt.noInd}</div>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: SPACE(2), marginTop: SPACE(3) }}>
          {scored && <span data-ui-v2="add-fit" data-fit={fit}><StatusChip tone="neutral">{`${C.rpt.mine} ${fill(C.build.s1.topPct, { pct: fit })}`}</StatusChip></span>}
          {!scored && <span data-ui-v2="add-manual"><StatusChip tone="neutral">{C.pick.manual}</StatusChip></span>}
          {warnLine && <span data-ui-v2="add-warn" data-n={w.flags.length} data-kind={kind} style={tx(SIZE.xs, WEIGHT.bold, w.flags.length ? COLOR.watch : COLOR.text2)}>{warnLine}</span>}
          {unchecked && <span data-ui-v2="add-warn" data-kind="unchecked" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.rank.warn}</span>}
        </div>
        {why && <p data-ui-v2="add-warn-why" data-why={noIcr ? "noIcr" : k ? "count" : "noData"} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{why}</p>}
        {!scored && <p data-ui-v2="add-manual-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{C.pick.manualNote}</p>}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(2), marginTop: SPACE(4), flexWrap: "wrap" }}>
          <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.edit.targets}</span>
          <Stepper name={s.nk} pct={p} downOff={p <= E.MIN_PCT} upOff={p >= hi} onDown={() => { setCapHit(false); step(-1); }}
            onUp={() => { if (p >= hi) { setCapHit(cap != null && hi === cap); return; } step(1); }} />
        </div>
        {capHit && <Note data-ui-v2="edit-max">{fill(C.edit.max, { x: cap })}</Note>}
        <div style={{ marginTop: SPACE(4) }}>
          <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink, { marginBottom: SPACE(2) })}>{C.edit.ind}</div>
          <IndBar parts={bar} />
        </div>
        <div style={{ marginTop: SPACE(4) }}><Button onClick={() => onAdd(add, p)}>{C.build.s4.add}</Button></div>
      </div>
    </BottomSheet>
  );
}
