// 포트폴리오 tab (v19.0c; the screen was called by the old name before: v18.3 A+B, the Part C daily check, and the
// Part E tracking sheet). It shows the user's own purchase records and, when today's data is fresh, each held stock's
// rule check (daily.jsx), the portfolio's value · 원금 · return against KOSPI, weight bars with target marks and
// 추가로 넣을 돈 (tracking.jsx). No example data. 홈 is in today.jsx. 포트폴리오 만들기 starts here (and on 홈's first visit).
// v19.0b: with no saved portfolio (and data that did not fail, and records that could be read), an empty-state card shows
// the 뱁이 in its nest (baepi-15-portfolio) and the way to 포트폴리오 만들기. No numbers on that screen.
// With saved portfolios the screen shows their figures, so a load failure here shows its message without the 뱁이 picture.
// v19.0c, a saved stock missing from today's data (Jack's design): its row stays with its line and 확인 필요 chip and a
// 포트폴리오에서 빼기 button (removes that stock from that portfolio, only when tapped); the totals leave it out with the
// line "오늘 데이터에 없는 종목 {n}개({names})는 빼고 계산했어요."; the weight bars, bands and 추가로 넣을 돈 pause with
// "빠진 종목이 다시 들어오거나 직접 뺄 때까지 비중은 점검하지 않아요." Names saved before v19.0c show their new form
// (legacy.js); the saved record keeps its name. iPhone Safari (not the home-screen app): a note on moving the records.
import React, { useMemo, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, TOUCH } from "../ui/tokens.js";
import { Button, StatusChip } from "../ui/components.jsx";
import { C, fill, nf, mdText, todayKst, todayStaleText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, OwnCloseNote, OldAppNote, Mascot, IMG, tx, tap, useNav } from "./ui.jsx";
import { parseImport, importProblem, importIssues, mergeStores, storedStores, downloadRecords, isSafariLike, withConfirm, withoutHolding } from "./store.js";
import { evaluateAll, todayCtx } from "./rules.js";
import { HoldingRow } from "./daily.jsx";
import { deckMoney } from "./track.js";
import { DeckSummary, ByStockHead, WeightLine, AddMoney, MissingNote, PausedNote, plainEdges } from "./tracking.jsx";
import { shownName } from "./legacy.js";
import { IosHint } from "./hint.jsx";
import { isCompany, ownCloses } from "./stocklist.js";
import { heldQty } from "./held.js";
import { pfState, isImported, usHeld, avgOf } from "./pf.js";
import { ImportedDeck } from "./pfview.jsx";
import { EpsOwnersNote } from "./fixnote.jsx";
import { RecordButton, RecordFlow, startFlow } from "./records.jsx";
import { Icon } from "../ui/icons.jsx";

// The held quantity (held.js: the one rule every screen uses) and the 평균 단가 (v19.6a: the moving average of the lots,
// pf.avgOf, so a sale never changes it and a purchase after a sale averages with what is left).
function avgCost(deck, t) {
  const held = heldQty(deck).get(t) || 0;
  const a = held > 0 ? avgOf(deck, t) : null;
  return a ? { qty: held, avg: a.avg, ccy: a.ccy } : null;
}
// v19.6a: a portfolio with any record (a purchase, a sale, a dividend, an imported row, a stock taken out) has a 내 수익.
export const hasRecords = (d) => !!d && ["purchases", "sales", "divs", "imported", "history"].some((k) => Array.isArray(d[k]) && d[k].length > 0);
// "내 수익 ›": the link to that portfolio's 내 수익 (#portfolio/returns/<id>), the board's chevron row.
export function ReturnsLink({ onClick }) {
  return (
    <button type="button" data-ui-v2="returns-link" onClick={onClick}
      style={{ ...tap, width: "100%", minHeight: TOUCH, marginTop: SPACE(3), display: "flex", alignItems: "center", gap: SPACE(2), border: "none", borderTop: `1px solid ${COLOR.line}`,
        background: "none", padding: `${SPACE(2)}px 0 0`, textAlign: "left" }}>
      <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flex: 1 })}>{C.ret.title}</span>
      <Icon name="chevronRight" size={18} tone="on" />
    </button>
  );
}

// 포트폴리오에서 빼기 (the old app's label): a small secondary button under the missing stock's row.
function RemoveButton({ onClick }) {
  return (
    <div data-ui-v2="missing-remove" style={{ padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>
      <Button kind="secondary" onClick={onClick} style={{ width: "auto", padding: `0 ${SPACE(4)}px` }}>{C.missing.remove}</Button>
    </div>
  );
}

const money = (v, ccy) => (ccy === "USD" ? "$" + nf(v, 2) : fill(C.app.won, { n: nf(Math.round(v)) }));

// onImport (v19.3d): opens 가진 종목 넣기.
export function Portfolio({ load, store, setStoreData, pad, go, onImport: openImport = null, onRules = null, onReturns = null }) {
  const { openStock } = useNav();
  const [flow, setFlow] = useState(null);                // v19.6a: the record sheet (records.jsx)
  const canRecord = load.status === "ok" && store.writable && !store.locked;
  const record = (deckId, t, nk) => (canRecord ? () => setFlow(startFlow([deckId], t, nk)) : null);
  const fileRef = useRef(null);
  const [importBad, setImportBad] = useState(false);
  const decks = store.data.decks;
  // The daily rule check: nothing is computed from stale or failed data (ev.ok false, ev.why says why). Then the screen
  // says so (the stale line, or the load-failure message), so a held stock without a chip never reads as "fine".
  const ctx = useMemo(() => todayCtx(load), [load]);
  const ev = useMemo(() => evaluateAll(decks, ctx), [decks, ctx]);
  // Part E: values use US prices at their own close date; say so when it differs from the Korean one.
  // v19.3d: a 가진 종목 portfolio has no per-stock rows in the daily check, so its dollar holdings are looked up here
  const us = ev.ok && (ev.decks.some((de) => de.ok && de.holdings.some((x) => x.cls === "us")) || decks.some((d) => usHeld(d, load)));
  const usDate = us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  // 포트폴리오에서 빼기: only the stock missing from today's data, only from this portfolio, only when tapped.
  const onRemove = (deckId, t) => {
    const next = withoutHolding(store.data, deckId, t, todayKst(), Date.now());   // with a removal mark (two tabs)
    if (next) { console.warn(`[v2] ${deckId}: ${t} removed from the portfolio (user tapped remove; it was not in today's data)`); setStoreData(next); }
    else console.warn("[v2] remove refused: " + JSON.stringify({ deckId, t }));
  };
  const onConfirm = (deckId, item, answer) => {
    const next = withConfirm(store.data, deckId, item, answer, todayKst(), Date.now());
    if (next) setStoreData(next);
    else console.warn("[v2] answer not recorded: " + JSON.stringify(item));
  };
  const onImport = async (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!f) return;
    let text = null;
    try { text = await f.text(); } catch (err) { text = null; }
    const inc = text != null ? parseImport(text, todayKst(), store.preview) : null;  // any bad field, or the other page's file, rejects it
    if (!inc) {
      const why = text == null ? "bad" : importProblem(text, todayKst(), store.preview) || "bad";
      // v19.3 F.1: name what is wrong (the portfolio, the part, the row, the stock), not only that it is
      const issues = text == null ? [] : importIssues(text, todayKst());
      console.warn("[v2] import refused: " + why + (issues.length ? " · " + issues.join("; ") : ""));
      setImportBad(why);
      return;
    }
    setImportBad(false);
    setStoreData(mergeStores(store.data, inc, Date.now(), storedStores(store.key, todayKst()), todayKst()));   // what the file brings back is an edit made now
  };
  // The record sheet sits outside Page: Page's wrapper changes at the PC width (1024 px), and a half-typed record must
  // survive a window resized or a tablet turned across it.
  return (
    <>
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.deck.title}</ScreenTitle>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
      {/* the week after the DART re-read (src/repair.js epsNoticeOn): one quiet line near the top */}
      <EpsOwnersNote load={load} />
      {!ev.ok && (ev.why === "fail" || ev.why === "undated") && <LoadFail picture={decks.length === 0} />}
      <OldAppNote />
      {decks.length === 0 && !store.locked && ev.why !== "fail" && ev.why !== "undated" && (
        <Card data-ui-v2="deck-empty" style={{ textAlign: "center" }}>
          <Mascot src={IMG.empty} alt={C.deck.emptyAlt} size={112} style={{ display: "inline-block" }} />
          {go && <div style={{ marginTop: SPACE(3) }}><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></div>}
        </Card>
      )}
      {decks.length === 0 && !store.locked && <IosHint kind="first" />}
      {decks.length > 0 && !ev.ok && ev.why === "stale" && (
        <Note tone="watch" data-ui-v2="deck-stale">{todayStaleText(ev.days)}</Note>
      )}
      {decks.map((d) => {
        if (isImported(d)) return <ImportedCard key={d.id} deck={d} ev={ev} ctx={ctx} load={load} openStock={openStock} onRemove={(t) => onRemove(d.id, t)} onRules={onRules ? () => onRules(d.id) : null}
          onRecord={canRecord ? (t, nk) => setFlow(startFlow([d.id], t, nk)) : null} onReturns={onReturns && hasRecords(d) ? () => onReturns(d.id) : null} />;
        const ts = [...heldQty(d).keys()];
        const de = ev.ok ? ev.decks.find((x) => x.id === d.id) : null;
        const names = new Map(d.holdings.map((h) => [h.t, h.nk]));
        const m = de && de.ok ? deckMoney(d, de, ctx) : { ok: false };   // Part E: value · 원금 · return (fresh data only)
        const paused = !!(de && de.ok && de.weights && de.weights.paused);    // v19.0c: a held stock is missing from today's data
        const start = d.purchases.reduce((a, p) => (p.qty > 0 && (a == null || p.date < a) ? p.date : a), null);
        return (
          <Card key={d.id} data-deck-id={d.id}>
            <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}>{shownName(d.name)}</h3>
            <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>
              <span>{fill(C.deck.mine, { n: ts.length })}</span>
              {start && mdText(start) && <><span>{" · "}</span><span data-ui-v2="deck-start">{fill(C.deck.start, { md: mdText(start) })}</span></>}
            </div>
            {m.ok && <DeckSummary deck={d} de={de} m={m} load={load} />}
            {m.absent && m.absent.length > 0 && <MissingNote absent={m.absent} deckId={d.id} />}
            {/* v19.1c: the totals and rows include a US stock priced at an earlier close (pxd): named here, beside the missing line */}
            {de && de.ok && <OwnCloseNote groups={ownCloses(load, de.holdings.filter((x) => !x.absent).map((x) => ctx.byT.get(x.t)))} data-deck-id={d.id} />}
            {m.ok && <ByStockHead plain={plainEdges(de)} paused={paused} />}
            {paused && <PausedNote />}
            {ts.map((t) => {
              const h = d.holdings.find((x) => x.t === t) || { nk: t };
              const a = avgCost(d, t);
              const x = de && de.ok ? de.holdings.find((y) => y.t === t) || null : null;
              const ret = m.ok && m.per[t] && m.per[t].ret != null ? m.per[t].ret * 100 : null;
              const gone = !!(x && x.absent);
              const rec = record(d.id, t, h.nk);
              return <HoldingRow key={t} t={t} title={h.nk} sub={a ? fill(C.deck.holding, { qty: nf(a.qty), price: money(a.avg, a.ccy) }) : null}
                onOpen={!gone && openStock && load.status === "ok" && isCompany(load.byT.get(t)) ? () => openStock(t) : undefined}
                x={x} names={names} onConfirm={(item, answer) => onConfirm(d.id, item, answer)} change={ret}
                extra={!gone && m.ok && x ? <WeightLine x={x} /> : null}
                action={gone || rec ? (
                  <div data-ui-v2="row-actions" style={{ display: "flex", gap: SPACE(2), flexWrap: "wrap", padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>
                    {rec && <RecordButton name={h.nk} onClick={rec} />}
                    {gone && <RemoveButton onClick={() => onRemove(d.id, t)} />}
                  </div>
                ) : null} />;
            })}
            {de && de.ok && (de.soldOut || []).map((t) => {
              const nk = (d.holdings.find((x) => x.t === t) || { nk: t }).nk;
              const rec = record(d.id, t, nk);
              return (
                <div key={t} data-sold-out={t}>
                  <HoldingRow t={t} title={nk} sub={C.daily.soldOut} x={null} names={names}
                    action={rec ? <div data-ui-v2="row-actions" style={{ padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}><RecordButton name={nk} onClick={rec} /></div> : null} />
                </div>
              );
            })}
            {de && de.ok && de.rebased && C.daily.rebasedNote && (
              <Note data-ui-v2="rebased-note">{fill(C.daily.rebasedNote, { n: de.bandPlanned, m: de.bandHeld })}</Note>
            )}
            {de && de.ok && de.notChecked > 0 && <Note data-ui-v2="not-checked">{fill(C.daily.notChecked, { n: de.notChecked })}</Note>}
            {m.ok && <AddMoney de={de} />}
            {onReturns && hasRecords(d) && <ReturnsLink onClick={() => onReturns(d.id)} />}
          </Card>
        );
      })}
      {decks.length > 0 && go && (
        <Card data-ui-v2="build-more"><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></Card>
      )}
      {decks.length > 0 && openImport && (
        <Card data-ui-v2="import-more"><Button kind="secondary" onClick={openImport}>{C.build.s0.holdings}</Button></Card>
      )}
      <Card data-ui-v2="records">
        {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
        {store.locked && C.store.locked && <Note tone="watch" data-ui-v2="store-locked">{C.store.locked}</Note>}
        {store.restored && <Note tone="watch" data-ui-v2="store-merged">{C.store.merged}</Note>}
        {store.unmerged && !store.locked && C.store.locked && <Note tone="watch" data-ui-v2="store-unmerged">{C.store.locked}</Note>}
        {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
        <div style={{ display: "flex", flexDirection: "column", gap: SPACE(2), marginTop: store.writable ? 0 : SPACE(3) }}>
          <Button kind="secondary" onClick={() => downloadRecords(store.data, todayKst(), store.exportPrefix, store.preview, store.key)}>{C.store.export}</Button>
          <Button kind="secondary" disabled={!store.writable} onClick={() => fileRef.current && fileRef.current.click()}>{C.store.import}</Button>
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={onImport} style={{ display: "none" }} data-ui-v2="import-file" />
        </div>
        {importBad && (
          // a preview file in the live app: otherKind · a live file in the preview: the plain chip · anything else: importFail
          <div data-ui-v2="import-bad" data-why={importBad} style={{ marginTop: SPACE(2) }}>
            {importBad === "preview" && !store.preview ? <Note tone="watch">{C.store.otherKind}</Note>
              : importBad === "live" && store.preview ? <StatusChip tone="watch" icon="alert">{C.store.import}</StatusChip>
              : <Note tone="watch">{C.store.importFail}</Note>}
          </div>
        )}
        {/* v19.0c: only with records to lose (an empty 포트폴리오 shows the 뱁이, and "7일" there would be the only number) */}
        {isSafariLike() && decks.length > 0 && <Note>{C.store.safari}</Note>}
        {decks.length > 0 && <IosHint kind="move" />}
      </Card>
      <Footer />
    </Page>
    <RecordFlow flow={flow} setFlow={setFlow} load={load} store={store} setStoreData={setStoreData} />
    </>
  );
}

// v19.3d (v19.3 F.1): a portfolio made with 가진 종목 넣기. Its four portfolio rules instead of 확인 필요 for every stock;
// on stale or failed data no number and no rule (the screen's own line says why).
function ImportedCard({ deck, ev, ctx, load, openStock, onRemove, onRules, onRecord, onReturns }) {
  const de = ev.ok ? ev.decks.find((x) => x.id === deck.id) : null;
  const st = useMemo(() => pfState(deck, ctx, load.status === "ok" ? load.data.stocks : []), [deck, ctx, load]);
  const m = de && de.ok ? deckMoney(deck, de, ctx) : { ok: false };
  return <ImportedDeck deck={deck} st={st} m={m} openStock={openStock} byT={ctx.byT} onRemove={onRemove} onRules={onRules} onRecord={onRecord}
    footer={onReturns ? <ReturnsLink onClick={onReturns} /> : null} />;
}
