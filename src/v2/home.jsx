// 오늘 and 내 덱 for the first PR (v18.3 A+B). The daily rule check (Part C) and the tracking sheet (Part E) come later,
// so these screens show only real states: load failure, stale data, the content date, "준비 중", and the user's own
// purchase records. No verdict and no example data.
import React, { useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE } from "../ui/tokens.js";
import { HeroBand, Button, ListRow, StatusChip } from "../ui/components.jsx";
import { C, fill, nf, todayKst } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, PendingChip, Footer, Note, tx } from "./ui.jsx";
import { parseImport, mergeStores, downloadRecords, isSafariLike } from "./store.js";

export function Today({ load, pad }) {
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.today.title}</ScreenTitle>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {load.status === "fail" && <LoadFail />}
      {load.status === "ok" && load.fresh.stale && (
        <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-stale">
          <HeroBand tone="alert" title={fill(C.today.stale, { n: load.fresh.days })} />
        </div>
      )}
      {load.status === "ok" && !load.fresh.stale && <Card><PendingChip /></Card>}
      <Footer />
    </Page>
  );
}

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
  const onImport = async (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!f) return;
    let text = null;
    try { text = await f.text(); } catch (err) { text = null; }
    const inc = text != null ? parseImport(text, todayKst()) : null;          // any bad field rejects the whole file
    if (!inc) { console.warn("[v2] import: not a records file"); setImportBad(true); return; }
    setImportBad(false);
    setStoreData(mergeStores(store.data, inc));
  };
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.deck.title}</ScreenTitle>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {decks.map((d) => {
        const ts = [...new Set(d.purchases.filter((p) => p.qty > 0).map((p) => p.t))];
        return (
          <Card key={d.id} data-deck-id={d.id}>
            <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}>{d.name}</h3>
            <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>{fill(C.deck.mine, { n: ts.length })}</div>
            {ts.map((t) => {
              const h = d.holdings.find((x) => x.t === t) || { nk: t };
              const a = avgCost(d.purchases, t);
              return <ListRow key={t} title={h.nk} sub={a ? fill(C.deck.holding, { qty: nf(a.qty), price: money(a.avg, a.ccy) }) : null} />;
            })}
          </Card>
        );
      })}
      <Card><PendingChip /></Card>
      <Card data-ui-v2="records">
        {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
        <div style={{ display: "flex", flexDirection: "column", gap: SPACE(2), marginTop: store.writable ? 0 : SPACE(3) }}>
          <Button kind="secondary" onClick={() => downloadRecords(store.data, todayKst(), store.exportPrefix)}>{C.store.export}</Button>
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

