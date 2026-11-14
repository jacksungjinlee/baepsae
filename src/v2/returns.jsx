// ================= 내 수익 (v19.6a, Part A.5, board Returns2): #portfolio/returns/<portfolio id> =================
// One portfolio: 가진 종목 (unrealized) + 판 종목 (realized) + 받은 배당 (after tax), each rounded the way it is shown, and
// the headline is the sum of the rounded rows, so the screen adds up exactly (lots.roundRows). The same for 주가 + 환율
// in 미국 종목 수익, 어디서 왔나. A part that cannot be computed is left out and named (lots.returnsOf), never counted as 0.
// Nothing is computed from stale or failed data (the screen's own stale line or the load-failure message says so); the
// records file (기록 내려받기) works whatever the data. No 뱁이 (the screen shows money). No Korean here: src/copy/v2.js.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, CHART } from "../ui/tokens.js";
import { Amount, priceColor } from "../ui/components.jsx";
import { IconChip, Icon } from "../ui/icons.jsx";
import { C, fill, nf, mdText, todayKst, todayStaleText, unitWon, plus, exactWon } from "./format.js";
import { Page, Card, AppBar, LoadFail, Footer, Note, OwnCloseNote, tx, tap } from "./ui.jsx";
import { ownCloses } from "./stocklist.js";
import { shownName } from "./legacy.js";
import { todayCtx } from "./rules.js";
import { signedPct } from "./deckcalc.js";
import { returnsOf, roundRows, fxSplit, returnsPct } from "./lots.js";
import { missingNames } from "./tracking.jsx";
import { recordsCsv, csvName, downloadCsv } from "./csv.js";

const warned = new Set();
const warnOnce = (m) => { if (!warned.has(m)) { warned.add(m); console.warn(m); } };

// A row of the three: icon chip, name and its second line, the amount (signed, coloured by its sign; "–" when nothing in it
// could be computed).
function Row({ icon, tone, name, sub, value, unit, first, id }) {
  return (
    <div data-ui-v2="ret-row" data-row={id} data-v={value == null ? undefined : value}
      style={{ display: "flex", alignItems: "center", gap: SPACE(3), padding: `${SPACE(2) + 2}px 0`, borderTop: first ? "none" : `1px solid ${COLOR.line}` }}>
      <IconChip name={icon} tone={tone} size={38} />
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.body - 1, WEIGHT.bold, COLOR.ink, { display: "block" })}>{name}</span>
        <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{sub}</span>
      </span>
      <span style={tx(SIZE.body, WEIGHT.heavy, value == null ? COLOR.text2 : priceColor(value), { whiteSpace: "nowrap" })}>
        {value == null ? "–" : <Amount text={plus(unitWon(value, unit), value)} />}
      </span>
    </div>
  );
}

// The records file (one CSV of every portfolio), from the store as it is.
// A download that could not start says so on screen (round-1 review: ret.csvFail), and the console says why.
function CsvRow({ store }) {
  const [failed, setFailed] = useState(false);
  const save = () => {
    const today = todayKst();
    const name = csvName(store.exportPrefix || "baepsae-records", today);
    let ok = false;
    try { ok = downloadCsv(recordsCsv(store.data, C.csv.head, C.csv.kinds, (d) => shownName(d.name)), name); } catch (e) {
      console.warn("[v2] records CSV not made: " + ((e && e.message) || e));
    }
    if (ok) console.info("[v2] records CSV saved: " + name);
    setFailed(!ok);
  };
  return (
    <Card data-ui-v2="ret-csv" style={{ padding: 0 }}>
      <button type="button" onClick={save} style={{ ...tap, width: "100%", minHeight: TOUCH + SPACE(4), display: "flex", alignItems: "center", gap: SPACE(3),
        border: "none", background: "none", padding: `${SPACE(3)}px ${SPACE(4)}px`, textAlign: "left" }}>
        <IconChip name="download-simple" size={38} />
        <span style={tx(SIZE.body - 1, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0, wordBreak: "keep-all" })}>{C.ret.csv}</span>
        <Icon name="chevronRight" size={18} tone="on" />
      </button>
      {failed && <div style={{ padding: `0 ${SPACE(4)}px ${SPACE(3)}px` }}><Note tone="watch" data-ui-v2="ret-csv-fail">{C.ret.csvFail}</Note></div>}
    </Card>
  );
}

// 미국 종목 수익, 어디서 왔나: the US stocks still held whose lots carry a rate.
function FxCard({ fx, today }) {
  if (fx.empty) {
    // every US holding still held is dollar-only (no rate of its own): the card says why there is no split
    return (
      <Card data-ui-v2="ret-fx" data-empty="1">
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
          <IconChip name="currency-dollar" tone="disc" size={36} />
          <h2 style={tx(SIZE.h3 - 1, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0, wordBreak: "keep-all" })}>{C.ret.fxTitle}</h2>
        </div>
        <p data-ui-v2="ret-fx-left" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3), wordBreak: "keep-all" })}>{C.ret.fxLeftOut}</p>
      </Card>
    );
  }
  const r = roundRows([fx.price, fx.rate]);
  const [price, rate] = r.rows;
  const total = r.total;
  const bar = price >= 0 && rate >= 0 && total > 0;
  const rateLine = fx.lotRate != null ? fill(C.ret.rateOne, { a: nf(Math.round(fx.lotRate)), b: nf(Math.round(today)) })
    : fx.avgRate != null ? fill(C.ret.rateAvg, { a: nf(Math.round(fx.avgRate)), b: nf(Math.round(today)) }) : null;
  return (
    <Card data-ui-v2="ret-fx" data-price={price} data-rate={rate} data-total={total}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3), marginBottom: SPACE(3) }}>
        <IconChip name="currency-dollar" tone="disc" size={36} />
        <h2 style={tx(SIZE.h3 - 1, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0, wordBreak: "keep-all" })}>{C.ret.fxTitle}</h2>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap" }}>
        <span style={tx(SIZE.sm, WEIGHT.regular, COLOR.neutral)}>{C.ret.fxHeld}</span>
        <span data-ui-v2="ret-fx-total" style={tx(SIZE.h2, WEIGHT.heavy, priceColor(total), { letterSpacing: "-0.02em" })}><Amount text={plus(unitWon(total, r.unit), total)} /></span>
      </div>
      {bar && (
        <div data-ui-v2="ret-fx-bar" aria-hidden="true" style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", marginTop: SPACE(3), background: COLOR.page }}>
          <span style={{ width: `${(price / total) * 100}%`, background: CHART.mine }} />
          <span style={{ width: `${(rate / total) * 100}%`, background: CHART.compare }} />
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(2), ...tx(SIZE.sm, WEIGHT.regular, COLOR.ink) }}>
        <span data-ui-v2="ret-fx-price"><b>{fill(C.ret.fxPrice, { x: "" }).trim()}</b> <span style={{ color: priceColor(price) }}>{plus(unitWon(price, r.unit), price)}</span></span>
        <span data-ui-v2="ret-fx-rate"><b>{fill(C.ret.fxRate, { y: "" }).trim()}</b> <span style={{ color: priceColor(rate) }}>{plus(unitWon(rate, r.unit), rate)}</span></span>
      </div>
      {rateLine && <p data-ui-v2="ret-fx-line" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{rateLine}</p>}
      {fx.leftOut.length > 0 && <p data-ui-v2="ret-fx-left" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1), wordBreak: "keep-all" })}>{C.ret.fxLeftOut}</p>}
    </Card>
  );
}

export function Returns({ deck, load, store, pad, onBack }) {
  const ctx = useMemo(() => todayCtx(load), [load]);
  const ok = load.status === "ok";
  const live = ok && ctx.state.ok;
  const q = useMemo(() => {
    if (!live) return null;
    const pxOf = (t) => { const s = ctx.byT.get(t); return s && s.price > 0 ? s.price : null; };
    const absent = new Set();
    for (const h of deck.holdings || []) if (h && !ctx.byT.has(h.t)) absent.add(h.t);
    return { pxOf, fx: ctx.fx, absent };
  }, [live, ctx, deck]);
  const r = useMemo(() => (q ? returnsOf(deck, q) : null), [deck, q]);
  const gone = r ? new Set([...r.absent, ...r.noPrice]) : new Set();
  // the stocks the rows leave out for a missing rate (noFx) stay out of the card too (round-2 review); the noFx line names them
  const fx = useMemo(() => (r && q ? fxSplit(r.ledgers.filter((L) => !gone.has(L.t) && !r.noFx.includes(L.t)), q.pxOf, q.fx) : null), [r, q]);
  const holdingOf = (t) => (deck.holdings || []).find((x) => x.t === t) || (deck.history || []).find((x) => x.t === t);
  const names = (ts) => ts.map((t) => { const h = holdingOf(t); return h ? (h.cls === "us" ? t : h.nk) : t; });
  // the rows: a row with records that could all not be computed shows "–" (never 0); a row with nothing in it is 0원
  const heldOpen = r ? r.ledgers.some((L) => L.held > 0) : false;
  const has = (k) => (deck[k] || []).length > 0 || (deck.history || []).some((e) => e && (e[k] || []).length > 0);
  const rowVals = r ? [heldOpen && !r.heldAny ? null : r.held, has("sales") && !r.soldAny ? null : r.sold, has("divs") && !r.divAny ? null : r.divs] : [];
  const rr = r ? roundRows(rowVals) : null;
  if (r) {
    if (r.noAvg.length) warnOnce(`[v2] ${deck.id}: returns leave out ${r.noAvg.join(", ")} (no average price)`);
    if (r.noFx.length) warnOnce(`[v2] ${deck.id}: returns leave out ${r.noFx.join(", ")} (a USD record without a rate): money put in and return not computed`);
    if (r.noPrice.length) warnOnce(`[v2] ${deck.id}: returns leave out ${r.noPrice.join(", ")} (no price today)`);
    if (r.soldOut) warnOnce(`[v2] ${deck.id}: returns leave out ${r.soldOut} sale(s) whose gain could not be computed`);
  }
  const total = rr ? rr.total : 0;
  const none = !!rr && rr.rows.every((v) => v == null);          // every row is "–": the headline too, never "0원"
  // 수익률 and its receipt line, together (CLAUDE.md: a computed ratio shows its inputs), only with the money put in known,
  // from the exact sums (lots.returnsPct). The receipt's {gain} is the headline itself (Jack, 2026-11-13: exact amounts
  // always, so the receipt and the headline agree): the sum of the three rows as shown, each to the 원. The line is
  // ret.receiptFix ("… {cost}으로 …": {cost} always ends in 원), not the Appendix 1 "{cost}로".
  const pct = r ? returnsPct(r) : null;
  const exact = r ? r.held + r.sold + r.divs : 0;
  const md = ok ? mdText(load.data.pxDate) : null;
  // held stocks left out today: missing from today's data (the approved missing-stock line names them); in it without a
  // price: ret.noPrice
  const missing = r ? r.absent : [];
  const usHeld = r ? r.ledgers.filter((L) => L.ccy === "USD" && L.held > 0 && !gone.has(L.t)).map((L) => ctx.byT.get(L.t)).filter(Boolean) : [];
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.app.tabs.portfolio} />
      <div data-ui-v2="returns" data-deck-id={deck.id}>
        {md && <p data-ui-v2="ret-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{fill(C.ret.date, { date: md })}</p>}
        <h2 style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1) })}>{C.ret.title}</h2>
        <p data-ui-v2="ret-deck" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>{shownName(deck.name)}</p>
        {load.status === "fail" && <LoadFail picture={false} />}
        {ok && !ctx.state.ok && <Note tone="watch" data-ui-v2="ret-stale">{todayStaleText(ctx.state.days)}</Note>}
        {r && (
          <>
            <div data-ui-v2="ret-total" data-v={total} data-exact={Math.round(exact)} style={{ marginTop: SPACE(2) }}>
              <span style={tx(34, WEIGHT.heavy, none ? COLOR.text2 : priceColor(total, true), { letterSpacing: "-0.02em", lineHeight: 1.2 })}>
                {none ? "–" : <Amount text={plus(unitWon(total, rr.unit), total)} />}</span>
              {pct != null && <span data-ui-v2="ret-pct" data-pct={Math.round(pct * 1000) / 1000} style={tx(SIZE.sm, WEIGHT.bold, COLOR.text2, { display: "block" })}>{fill(C.ret.ret, { pct: signedPct(pct) })}</span>}
            </div>
            <Card data-ui-v2="ret-rows" style={{ padding: `${SPACE(1) + 2}px ${SPACE(4)}px` }}>
              <Row id="held" icon="deck" tone="earn" name={C.ret.held} sub={C.ret.heldSub} value={rr.rows[0]} unit={rr.unit} first />
              <Row id="sold" icon="receipt" tone="on" name={C.ret.sold} sub={C.ret.soldSub} value={rr.rows[1]} unit={rr.unit} />
              <Row id="divs" icon="coins" tone="div" name={C.ret.divs} sub={C.ret.divsSub} value={rr.rows[2]} unit={rr.unit} />
            </Card>
            {pct != null && (
              <Note data-ui-v2="ret-receipt">{fill(C.ret.receiptFix, { gain: exactWon(rr.unit === 1 ? total : exact), cost: exactWon(r.cost) })}</Note>
            )}
            {r.soldOut > 0 && <Note data-ui-v2="ret-sold-left">{fill(C.ret.soldLeftOut, { n: r.soldOut })}</Note>}
            {r.noFx.length > 0 && C.deck.noFx && <Note data-ui-v2="ret-no-fx">{C.deck.noFx}</Note>}
            {r.noAvg.length > 0 && <Note data-ui-v2="ret-no-avg">{fill(C.ret.noAvg, { n: r.noAvg.length, names: names(r.noAvg).join(", ") })}</Note>}
            {missing.length > 0 && <Note tone="watch" data-ui-v2="ret-missing">{fill(C.missing.line, { n: missing.length, names: missingNames(missing.map((t) => ({ t, nk: names([t])[0], cls: (holdingOf(t) || {}).cls, cost: null }))) })}</Note>}
            {r.noPrice.length > 0 && <Note tone="watch" data-ui-v2="ret-no-price">{C.ret.noPrice}</Note>}
            {r.usdOnly && <Note data-ui-v2="usd-today">{C.pfr.usdToday}</Note>}
            {r.usdOnlySold && <Note data-ui-v2="usd-sold">{C.rec.usdOnly}</Note>}
            {/* v19.1c (#82): a held US stock priced at an earlier close than the US date is named, as everywhere else */}
            <OwnCloseNote groups={ownCloses(load, usHeld)} data-ui-v2="ret-own-close" />
            {fx && (!fx.empty || fx.leftOut.length > 0) && <FxCard fx={fx} today={q.fx} />}
          </>
        )}
        <CsvRow store={store} />
      </div>
      <Footer />
    </Page>
  );
}
