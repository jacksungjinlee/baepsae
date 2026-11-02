// 내 덱 (v18.3 A+B, the Part C daily check, and the Part E tracking sheet). It shows the user's own purchase records
// and, when today's data is fresh, each held stock's rule check (daily.jsx), the deck's value · 원금 · return against
// KOSPI, weight bars with target marks and 추가로 넣을 돈 (tracking.jsx). No example data. 오늘 is in today.jsx.
import React, { useMemo, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE } from "../ui/tokens.js";
import { Button, StatusChip } from "../ui/components.jsx";
import { C, fill, nf, mdText, todayKst } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, Footer, Note, OldAppNote, tx } from "./ui.jsx";
import { parseImport, mergeStores, downloadRecords, isSafariLike, withConfirm } from "./store.js";
import { evaluateAll, todayCtx } from "./rules.js";
import { HoldingRow } from "./daily.jsx";
import { deckMoney } from "./track.js";
import { DeckSummary, ByStockHead, WeightLine, AddMoney } from "./tracking.jsx";

function avgCost(purchases, t) {
  const ps = purchases.filter((p) => p.t === t && p.qty > 0);
  const q = ps.reduce((a, p) => a + p.qty, 0);
  return q > 0 ? { qty: q, avg: ps.reduce((a, p) => a + p.qty * p.price, 0) / q, ccy: ps[0].ccy } : null;
}

const money = (v, ccy) => (ccy === "USD" ? "$" + nf(v, 2) : fill(C.app.won, { n: nf(Math.round(v)) }));

export function MyDeck({ load, store, setStoreData, pad }) {
  const fileRef = useRef(null);
  const [importBad, setImportBad] = useState(false);
  const decks = store.data.decks;
  // The daily rule check: nothing is computed from stale or failed data (ev.ok false, ev.why says why).
  const ev = useMemo(() => evaluateAll(decks, todayCtx(load)), [decks, load]);
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
    if (!inc) { console.warn("[v2] import: not a records file"); setImportBad(true); return; }
    setImportBad(false);
    setStoreData(mergeStores(store.data, inc));
  };
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.deck.title}</ScreenTitle>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      <OldAppNote />
      {decks.length > 0 && !ev.ok && ev.why === "stale" && (
        <Note tone="watch" data-ui-v2="deck-stale">{fill(C.today.stale, { n: ev.days })}</Note>
      )}
      {decks.map((d) => {
        const ts = [...new Set(d.purchases.filter((p) => p.qty > 0).map((p) => p.t))];
        const de = ev.ok ? ev.decks.find((x) => x.id === d.id) : null;
        const names = new Map(d.holdings.map((h) => [h.t, h.nk]));
        const m = de && de.ok ? deckMoney(d, de) : { ok: false };      // Part E: value · 원금 · return (fresh data only)
        const start = d.purchases.reduce((a, p) => (p.qty > 0 && (a == null || p.date < a) ? p.date : a), null);
        return (
          <Card key={d.id} data-deck-id={d.id}>
            <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}>{d.name}</h3>
            <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>
              <span>{fill(C.deck.mine, { n: ts.length })}</span>
              {start && mdText(start) && <><span>{" · "}</span><span data-ui-v2="deck-start">{fill(C.deck.start, { md: mdText(start) })}</span></>}
            </div>
            {m.ok && <DeckSummary deck={d} m={m} load={load} />}
            {m.ok && <ByStockHead />}
            {ts.map((t) => {
              const h = d.holdings.find((x) => x.t === t) || { nk: t };
              const a = avgCost(d.purchases, t);
              const x = de && de.ok ? de.holdings.find((y) => y.t === t) || null : null;
              const ret = m.ok && m.per[t] && m.per[t].ret != null ? m.per[t].ret * 100 : null;
              return <HoldingRow key={t} title={h.nk} sub={a ? fill(C.deck.holding, { qty: nf(a.qty), price: money(a.avg, a.ccy) }) : null}
                x={x} names={names} onConfirm={(item, answer) => onConfirm(d.id, item, answer)} change={ret}
                extra={m.ok && x ? <WeightLine x={x} /> : null} />;
            })}
            {de && de.ok && de.notChecked > 0 && <Note data-ui-v2="not-checked">{fill(C.daily.notChecked, { n: de.notChecked })}</Note>}
            {m.ok && <AddMoney de={de} />}
          </Card>
        );
      })}
      <Card data-ui-v2="records">
        {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
        {store.locked && C.store.locked && <Note tone="watch" data-ui-v2="store-locked">{C.store.locked}</Note>}
        <div style={{ display: "flex", flexDirection: "column", gap: SPACE(2), marginTop: store.writable ? 0 : SPACE(3) }}>
          <Button kind="secondary" onClick={() => downloadRecords(store.data, todayKst(), store.exportPrefix, store.preview)}>{C.store.export}</Button>
          <Button kind="secondary" disabled={!store.writable} onClick={() => fileRef.current && fileRef.current.click()}>{C.store.import}</Button>
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={onImport} style={{ display: "none" }} data-ui-v2="import-file" />
        </div>
        {importBad && (
          <div data-ui-v2="import-bad" style={{ marginTop: SPACE(2) }}>
            {C.store.importFail ? <Note tone="watch">{C.store.importFail}</Note>
              : <StatusChip tone="watch" icon="alert">{C.store.import}</StatusChip>}
          </div>
        )}
        {isSafariLike() && <Note>{C.store.safari}</Note>}
      </Card>
      <Footer />
    </Page>
  );
}

