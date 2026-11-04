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
import { COLOR, SIZE, WEIGHT, SPACE } from "../ui/tokens.js";
import { Button, StatusChip } from "../ui/components.jsx";
import { C, fill, nf, mdText, todayKst } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, OldAppNote, Mascot, IMG, tx, useNav } from "./ui.jsx";
import { parseImport, importProblem, mergeStores, downloadRecords, isSafariLike, withConfirm, withoutHolding } from "./store.js";
import { evaluateAll, todayCtx } from "./rules.js";
import { HoldingRow } from "./daily.jsx";
import { deckMoney } from "./track.js";
import { DeckSummary, ByStockHead, WeightLine, AddMoney, MissingNote, PausedNote, plainEdges } from "./tracking.jsx";
import { shownName } from "./legacy.js";
import { IosHint } from "./hint.jsx";

function avgCost(purchases, t) {
  const ps = purchases.filter((p) => p.t === t && p.qty > 0);
  const q = ps.reduce((a, p) => a + p.qty, 0);
  return q > 0 ? { qty: q, avg: ps.reduce((a, p) => a + p.qty * p.price, 0) / q, ccy: ps[0].ccy } : null;
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

export function Portfolio({ load, store, setStoreData, pad, go }) {
  const { openStock } = useNav();
  const fileRef = useRef(null);
  const [importBad, setImportBad] = useState(false);
  const decks = store.data.decks;
  // The daily rule check: nothing is computed from stale or failed data (ev.ok false, ev.why says why). Then the screen
  // says so (the stale line, or the load-failure message), so a held stock without a chip never reads as "fine".
  const ctx = useMemo(() => todayCtx(load), [load]);
  const ev = useMemo(() => evaluateAll(decks, ctx), [decks, ctx]);
  // Part E: values use US prices at their own close date; say so when it differs from the Korean one.
  const us = ev.ok && ev.decks.some((de) => de.ok && de.holdings.some((x) => x.cls === "us"));
  const usDate = us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  // 포트폴리오에서 빼기: only the stock missing from today's data, only from this portfolio, only when tapped.
  const onRemove = (deckId, t) => {
    const next = withoutHolding(store.data, deckId, t);
    if (next) { console.warn(`[v2] ${deckId}: ${t} removed from the portfolio (user tapped remove; it was not in today's data)`); setStoreData(next); }
    else console.warn("[v2] remove refused: " + JSON.stringify({ deckId, t }));
  };
  const onConfirm = (deckId, item, answer) => {
    const next = withConfirm(store.data, deckId, item, answer, todayKst());
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
      console.warn("[v2] import refused: " + why);
      setImportBad(why);
      return;
    }
    setImportBad(false);
    setStoreData(mergeStores(store.data, inc));
  };
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.deck.title}</ScreenTitle>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
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
        <Note tone="watch" data-ui-v2="deck-stale">{fill(C.today.stale, { n: ev.days })}</Note>
      )}
      {decks.map((d) => {
        const ts = [...new Set(d.purchases.filter((p) => p.qty > 0).map((p) => p.t))];
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
            {m.ok && <ByStockHead plain={plainEdges(de)} paused={paused} />}
            {paused && <PausedNote />}
            {ts.map((t) => {
              const h = d.holdings.find((x) => x.t === t) || { nk: t };
              const a = avgCost(d.purchases, t);
              const x = de && de.ok ? de.holdings.find((y) => y.t === t) || null : null;
              const ret = m.ok && m.per[t] && m.per[t].ret != null ? m.per[t].ret * 100 : null;
              const gone = !!(x && x.absent);
              return <HoldingRow key={t} t={t} title={h.nk} sub={a ? fill(C.deck.holding, { qty: nf(a.qty), price: money(a.avg, a.ccy) }) : null}
                onOpen={!gone && openStock && load.status === "ok" && load.byT.has(t) ? () => openStock(t) : undefined}
                x={x} names={names} onConfirm={(item, answer) => onConfirm(d.id, item, answer)} change={ret}
                extra={!gone && m.ok && x ? <WeightLine x={x} /> : null} action={gone ? <RemoveButton onClick={() => onRemove(d.id, t)} /> : null} />;
            })}
            {de && de.ok && de.rebased && C.daily.rebasedNote && (
              <Note data-ui-v2="rebased-note">{fill(C.daily.rebasedNote, { n: de.bandPlanned, m: de.bandHeld })}</Note>
            )}
            {de && de.ok && de.notChecked > 0 && <Note data-ui-v2="not-checked">{fill(C.daily.notChecked, { n: de.notChecked })}</Note>}
            {m.ok && <AddMoney de={de} />}
          </Card>
        );
      })}
      {decks.length > 0 && go && (
        <Card data-ui-v2="build-more"><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></Card>
      )}
      <Card data-ui-v2="records">
        {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
        {store.locked && C.store.locked && <Note tone="watch" data-ui-v2="store-locked">{C.store.locked}</Note>}
        <div style={{ display: "flex", flexDirection: "column", gap: SPACE(2), marginTop: store.writable ? 0 : SPACE(3) }}>
          <Button kind="secondary" onClick={() => downloadRecords(store.data, todayKst(), store.exportPrefix, store.preview)}>{C.store.export}</Button>
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
  );
}

