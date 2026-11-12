// ================= 기록: 샀어요 · 팔았어요 · 배당 받았어요 on an existing portfolio (v19.6a, Part A.2, board Records2) =================
// A 기록 button on each holding row of 포트폴리오 (and on the company page when a portfolio has the stock) opens the
// "{name} 기록" sheet: three actions above that stock's record list. When the stock is in two or more portfolios, the
// company page asks which one first. The forms keep the live 샀어요 sheet's shape (a bottom sheet, the same fields and
// button), with the board's head line and result card. Every number is the lot maths' (lots.js); every refusal is an
// approved line (records.js says which). No 뱁이 here (the forms show money). No Korean in this file: src/copy/v2.js.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Button, BottomSheet, priceColor } from "../ui/components.jsx";
import { C, fill, nf, mdText, todayKst, exactWon, plus, recDate } from "./format.js";
import { Note, TextInput, SampleLabel, tx, useMode, useLayout, SIDE_W } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { shownName } from "./legacy.js";
import { writeStore } from "./store.js";
import { withRemoval } from "./edit.js";
import { priceDate } from "./cofmt.js";
import { signedPct } from "./deckcalc.js";
import { splitsFor } from "./lots.js";
import {
  stockState, checkSale, checkPurchase, checkDiv, withRecord, withoutRecord, recordsOf, salePreview, soldOutNow, rateEnv, typed, decksFor, recordCcy,
  closeIsDefault, rateRefusal,
} from "./records.js";

const usdText = (v) => "$" + nf(v, 2);
// Shares: whole numbers as they are, a fraction (US, or derived from an amount) with up to 4 decimals (as pfview.qtyText).
const qtyText = (q) => Number(q).toLocaleString("ko-KR", { maximumFractionDigits: 4 });
// A split's ratio as the approved line writes it: "2", "1.5" (no trailing zeros), "0.25" -> shown as 1 / r for a 병합.
const ratioText = (r) => Number(r).toLocaleString("ko-KR", { maximumFractionDigits: 2 });
const ownMoney = (v, ccy) => (ccy === "USD" ? usdText(v) : fill(C.app.won, { n: nf(Math.round(v)) }));
// "포트폴리오에서도 뺄까요?" and "판 기록과 배당 기록은 내 수익에 남아요." (one approved line: the question titles the sheet)
const firstSentence = (t) => { const m = /^(.+?\?)\s*(.*)$/.exec(String(t || "")); return m ? [m[1], m[2]] : [t, ""]; };

// The 기록 button: a small secondary button under a holding row (the same place and look as 포트폴리오에서 빼기).
export function RecordButton({ name, onClick, style }) {
  return (
    <Button kind="secondary" onClick={onClick} style={{ width: "auto", padding: `0 ${SPACE(4)}px`, minHeight: TOUCH, position: "relative", ...style }}>
      <span aria-hidden="true">{C.rec.button}</span>
      <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap" }}>{fill(C.rec.title, { name })}</span>
    </Button>
  );
}

// What opens the flow: { decks: [deck id], t, nk } — one portfolio opens its sheet, two or more ask which first.
export const startFlow = (deckIds, t, nk) => (deckIds.length > 1 ? { stage: "which", deckIds, t, nk } : deckIds.length === 1 ? { stage: "list", deckId: deckIds[0], t, nk } : null);
// The company page's 기록: the portfolios that have the stock (held, sold out, planned, or taken out: 배당 only).
export const companyFlow = (data, t, nk) => startFlow(decksFor(data, t).map((d) => d.id), t, nk);

// flow: null | { stage: "which" | "list" | "buy" | "sell" | "div" | "full", deckIds?, deckId?, t, nk, saved? }
export function RecordFlow({ flow, setFlow, load, store, setStoreData }) {
  const { preview } = useMode();
  const { wide } = useLayout();
  if (!flow) return null;
  const close = () => setFlow(null);
  const shift = wide ? SIDE_W : 0;
  const sample = preview ? <div style={{ marginBottom: SPACE(2) }}><SampleLabel /></div> : null;
  if (flow.stage === "which") {
    const decks = flow.deckIds.map((id) => store.data.decks.find((d) => d.id === id)).filter(Boolean);
    return (
      <BottomSheet open title={C.rec.which} onClose={close} closeLabel={C.app.close} shift={shift}>
        {sample}
        <div data-ui-v2="rec-which" style={{ display: "flex", flexDirection: "column", gap: SPACE(2) }}>
          {decks.map((d) => (
            <Button key={d.id} kind="secondary" onClick={() => setFlow({ stage: "list", deckId: d.id, t: flow.t, nk: flow.nk })}>{shownName(d.name)}</Button>
          ))}
        </div>
      </BottomSheet>
    );
  }
  const deck = store.data.decks.find((d) => d.id === flow.deckId);
  if (!deck) return null;
  const props = { flow, setFlow, load, store, setStoreData, deck, close, shift, sample };
  if (flow.stage === "buy" || flow.stage === "sell" || flow.stage === "div") return <RecordForm key={flow.stage} {...props} />;
  if (flow.stage === "full") return <FullSale {...props} />;
  return <RecordList {...props} />;
}

// Save the store (the same way 샀어요 does: writeStore checks it, then the app takes it as saved). -> true when saved.
function save(store, setStoreData, next) {
  const today = todayKst();
  if (!next || !store.writable || !writeStore(next, store.key, today)) return false;
  setStoreData(next, true);
  return true;
}

// ---------------- the sheet: three actions above the stock's records ----------------
function RecordList({ flow, setFlow, store, setStoreData, deck, close, shift, sample }) {
  const t = flow.t;
  const today = todayKst();
  const st = stockState(deck, t);
  const items = recordsOf(deck, t);
  const [ask, setAsk] = useState(null);          // the record whose 지우기 was tapped (key)
  const [refused, setRefused] = useState(null);  // { key, why }
  const [fail, setFail] = useState(false);
  const go = (stage) => setFlow({ ...flow, stage, saved: false });
  const splits = splitsFor(deck, t);
  const del = (it) => {
    const r = withoutRecord(store.data, deck.id, it, today);
    if (!r.ok) { setRefused({ key: it.key, why: r.why }); setAsk(null); return; }
    if (!save(store, setStoreData, r.data)) { setFail(true); return; }
    setAsk(null); setRefused(null); setFail(false);
    setFlow({ ...flow, saved: false });
  };
  const kindText = (k) => C.csv.kinds[{ buy: "buy", sell: "sell", div: "div", imp: "imp" }[k]];
  return (
    <BottomSheet open title={fill(C.rec.title, { name: flow.nk })} onClose={close} closeLabel={C.app.close} shift={shift}>
      {sample}
      <div data-ui-v2="rec-sheet" data-t={t} data-deck-id={deck.id}>
        {/* three buttons fit one row only from about 420 px of sheet width; below that 2 + 1, so none wraps inside (320 px phones) */}
        <div data-ui-v2="rec-actions" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(132px, 1fr))", gap: SPACE(2) }}>
          {st.inHoldings && <Button kind="secondary" onClick={() => go("buy")} style={{ padding: `0 ${SPACE(2)}px`, wordBreak: "keep-all" }}>{C.plan.bought}</Button>}
          {st.inHoldings && st.held > 0 && <Button kind="secondary" onClick={() => go("sell")} style={{ padding: `0 ${SPACE(2)}px`, wordBreak: "keep-all" }}>{C.rec.sell}</Button>}
          {(st.inHoldings || st.inHistory) && <Button kind="secondary" onClick={() => go("div")} style={{ padding: `0 ${SPACE(2)}px`, wordBreak: "keep-all" }}>{C.rec.div}</Button>}
        </div>
        {flow.saved && <Note data-ui-v2="rec-saved">{C.plan.done}</Note>}
        {fail && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
        {/* a split correction in data.json changed this stock's share count during this visit (app.jsx: an "out" row took a
            stored split out or moved it to the corrected date) */}
        {store.splitFixed && store.splitFixed.has(`${deck.id}|${t}`) && <Note data-ui-v2="rec-split-fixed">{C.rec.splitFixed}</Note>}
        {splits.map((s) => (
          <Note key={s.date} data-ui-v2="rec-split">{s.r >= 1 ? fill(C.rec.split, { date: recDate(s.date, today), r: ratioText(s.r) })
            : fill(C.rec.merge, { date: recDate(s.date, today), r: ratioText(1 / s.r) })}</Note>
        ))}
        {items.length > 0 && (
          <ul data-ui-v2="rec-list" style={{ listStyle: "none", margin: `${SPACE(3)}px 0 0`, padding: 0 }}>
            {items.map((it) => {
              const date = it.date ? recDate(it.date, today) : null;
              const what = it.qty != null ? fill(C.plan.shares, { n: qtyText(it.qty) })
                : it.amount != null ? (it.ccy === "USD" && it.kind === "div" ? usdText(it.amount) : exactWon(it.amount)) : null;
              const canDel = it.kind !== "imp";
              return (
                <li key={it.key} data-rec={it.kind} data-rec-key={it.key} style={{ borderTop: `1px solid ${COLOR.line}`, padding: `${SPACE(2)}px 0` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH }}>
                    <span style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { minWidth: 0, flex: 1, wordBreak: "keep-all" })}>
                      {[date, kindText(it.kind), what].filter(Boolean).join(" · ")}
                    </span>
                    {canDel && (
                      <Button kind="quiet" onClick={() => { setAsk(it.key); setRefused(null); }} style={{ width: "auto", padding: `0 ${SPACE(2)}px`, position: "relative", ...tx(SIZE.sm, WEIGHT.bold, COLOR.text2) }}>
                        <span aria-hidden="true">{C.rec.del}</span>
                        <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap" }}>
                          {fill(C.rec.delAriaNew, { date: date || "", kind: kindText(it.kind) }).trim()}</span>
                      </Button>
                    )}
                  </div>
                  {ask === it.key && (
                    <div data-ui-v2="rec-del-ask" style={{ background: COLOR.page, borderRadius: RADIUS.sm, padding: SPACE(3), marginTop: SPACE(1) }}>
                      <p style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink, { wordBreak: "keep-all" })}>{C.rec.delAsk}</p>
                      <div style={{ display: "flex", gap: SPACE(2), marginTop: SPACE(2) }}>
                        <Button onClick={() => del(it)} style={{ flex: 1 }}>{C.rec.del}</Button>
                        <Button kind="secondary" onClick={() => setAsk(null)} style={{ flex: 1 }}>{C.rec.cancel}</Button>
                      </div>
                    </div>
                  )}
                  {/* below: the approved refusal. gone (the record changed meanwhile) or store (it would not read back):
                      rec.delFail (never the 날짜·수량·가격 line, which is about typing) */}
                  {refused && refused.key === it.key && (
                    <Note tone="watch" data-ui-v2="rec-del-refused" data-why={refused.why}>{refused.why === "below" ? C.rec.delRefused : C.rec.delFail}</Note>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </BottomSheet>
  );
}

// ---------------- the forms ----------------
function RecordForm({ flow, setFlow, load, store, setStoreData, deck, close, shift, sample }) {
  const kind = flow.stage;
  const t = flow.t;
  const today = todayKst();
  const ok = load.status === "ok";
  const s = ok ? load.byT.get(t) || null : null;
  const st = stockState(deck, t);
  const usd = recordCcy(deck, t, s) === "USD";              // the same source the saved record's currency comes from
  const env = rateEnv(load, today);
  // v19.7a 팔고 빼기: the sale form opens with every held share filled in (flow.prefill.qty)
  const [v, setV] = useState({ qty: flow.prefill && flow.prefill.qty != null ? String(flow.prefill.qty) : "", price: "", date: today, amount: "" });
  const [tried, setTried] = useState(false);
  const [fail, setFail] = useState(false);
  const set = (k) => (x) => setV((o) => ({ ...o, [k]: x }));
  const byAmount = kind === "sell" && st.byAmount;
  const closeOk = kind === "div" || closeIsDefault(deck, t, v.date, today);   // today's close can stand in for an empty price
  const check = useMemo(() => {
    if (kind === "sell") return checkSale(deck, t, { qty: v.qty, price: v.price, date: v.date, amountWon: v.amount }, s, env);
    if (kind === "buy") return checkPurchase(deck, t, v, s, env);
    return checkDiv(deck, t, v, s, env);
  }, [kind, deck, t, v, s, env.fx, env.fxHist, env.stale]);
  // the result card (팔았어요): live from what is typed, before anything is saved
  const prev = kind === "sell" && check.ok ? salePreview(deck, check.rec) : null;
  const md = s ? mdText(priceDate(load, s)) : null;
  const submit = () => {
    setTried(true);
    if (!check.ok) return;
    const list = kind === "buy" ? "purchases" : kind === "sell" ? "sales" : "divs";
    let next = withRecord(store.data, deck.id, list, check.rec, today);
    // v19.7a 팔고 빼기 [B4]: what the sale belongs to (the stock taken out, its target shared out) is saved with it, in one
    // write (flow.finish: edit.sellAndRemove). Refused -> nothing is saved (the proposed edit.saveFail, else the console).
    if (next && flow.finish) {
      const r = flow.finish(next);
      if (!r || !r.ok) { setFail("refused"); return; }
      next = r.data;
    }
    if (!save(store, setStoreData, next)) { setFail(true); return; }
    setFail(false);
    if (flow.finish) { if (flow.after) flow.after(next); setFlow(null); return; }
    const nd = next.decks.find((d) => d.id === deck.id);
    if (kind === "sell" && soldOutNow(nd, t)) setFlow({ ...flow, stage: "full" });
    else setFlow({ ...flow, stage: "list", saved: true });
  };
  const title = kind === "sell" ? C.rec.sellTitle : kind === "buy" ? C.plan.sheetTitle : C.rec.divTitle;
  const why = tried && !check.ok ? check.why : null;
  const bad = (f) => !!why && check.field === f;            // only the field the refusal is about turns amber
  // a US record without the rate of its date: said as soon as the date is typed (the record can't be saved yet). A past date:
  // the approved "환율 정보를 불러오지 못해 … 지난 날짜의 …" line. Today (stale data: its rate is an older day's): rec.noTodayRate.
  // A past date after the published history's last day (last night's US date before the morning publish): rec.rateNotYet.
  // The form keeps what was typed (nothing is cleared on a refusal).
  const rateNo = !check.ok && check.why === "rate" ? rateRefusal(check.rate) : null;
  const rateLine = rateNo === "past" ? C.rec.noPastRate : rateNo === "today" ? C.rec.noTodayRate : rateNo === "notYet" ? C.rec.rateNotYet : null;
  // a holding put in by amount has no share count of its own: no "지금 N주 …" head line (the by-amount line explains the form)
  const head = kind === "sell" && !byAmount ? (st.avg ? fill(C.rec.head, { qty: qtyText(st.qty), price: ownMoney(st.avg.avg, st.avg.ccy) }) : fill(C.rec.heldQty, { qty: qtyText(st.qty) })) : null;
  // the dividend and by-amount forms have no 수량 · 가격: their own line (rec.badAmount), never "날짜·수량·가격을 다시 확인해
  // 주세요" (round-2 review)
  const badLine = kind === "div" || byAmount ? C.rec.badAmount : C.plan.badInput;
  return (
    <BottomSheet open title={title} onClose={close} closeLabel={C.app.close} shift={shift}>
      {sample}
      <div data-ui-v2="rec-form" data-kind={kind} data-t={t}>
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
          <CoMark t={t} name={flow.nk} size={SPACE(11)} />
          <div style={{ minWidth: 0 }}>
            <div style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{flow.nk}</div>
            {head && <div data-ui-v2="rec-head" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { wordBreak: "keep-all" })}>{head}</div>}
          </div>
        </div>
        {/* round-3: with a split between the chosen date and today, today's close is on another share basis: no default price
            (the price is required, records.closeIsDefault), so neither this line nor the close as the placeholder */}
        {kind !== "div" && !byAmount && md && closeOk && <p data-ui-v2="rec-close-line" style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3), wordBreak: "keep-all" })}>{fill(C.rec.buyBody, { md })}</p>}
        {byAmount && <p data-ui-v2="rec-by-amount" style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3), wordBreak: "keep-all" })}>{C.rec.byAmount}</p>}
        {kind === "div" ? (
          <>
            <TextInput label={usd ? C.rec.divUsd : C.rec.divWon} inputMode={usd ? "decimal" : "numeric"} value={v.amount} onChange={set("amount")} invalid={bad("amount")} />
            <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{C.rec.divHint}</p>
          </>
        ) : byAmount ? (
          <TextInput label={C.rec.sellAmount} inputMode="numeric" value={v.amount} onChange={set("amount")} invalid={bad("amount")} />
        ) : (
          <>
            <TextInput label={C.plan.qty} inputMode={usd && kind === "sell" ? "decimal" : "numeric"} value={v.qty} onChange={set("qty")}
              invalid={bad("qty")} />
            <TextInput label={kind === "sell" ? (usd ? C.rec.sellPriceUsd : C.rec.sellPriceWon) : (usd ? C.plan.priceUsd : C.plan.priceWon)} inputMode="decimal"
              placeholder={s && s.price > 0 && closeOk ? (usd ? nf(s.price, 2) : nf(s.price)) : undefined} value={v.price} onChange={set("price")} invalid={bad("price")} />
          </>
        )}
        <TextInput label={kind === "sell" ? C.rec.sellDate : kind === "buy" ? C.plan.date : C.rec.divDate} type="date" value={v.date} onChange={set("date")} max={today}
          invalid={bad("date") || (!!rateNo && !!rateLine)} />
        {/* a US record's date is the US trading date (#117 RUNBOOK), which can be the day before the Korean date */}
        {usd && <p data-ui-v2="rec-us-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1), wordBreak: "keep-all" })}>{C.rec.usDateHint}</p>}
        {kind === "sell" && prev && <SaleResult prev={prev} usd={usd} />}
        {rateLine && <Note tone="watch" data-ui-v2="rec-no-rate" data-why={rateNo}>{rateLine}</Note>}
        {why === "tooMany" && <Note tone="watch" data-ui-v2="rec-too-many">{C.rec.tooMany}</Note>}
        {why === "tooEarly" && <Note tone="watch" data-ui-v2="rec-too-early">{C.rec.tooEarly}</Note>}
        {(why === "input" || why === "noPrice") && badLine && <Note tone="watch" data-ui-v2="bad-input">{badLine}</Note>}
        {fail === true && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
        {fail === "refused" && C.edit.saveFail && <Note tone="watch" data-ui-v2="edit-save-fail">{C.edit.saveFail}</Note>}
        <div style={{ marginTop: SPACE(4) }}><Button onClick={submit}>{C.plan.save}</Button></div>
      </div>
    </BottomSheet>
  );
}

// 판 금액 · 산 가격보다 (won first: a US sale shows its dollars small under the won amount), then the note or why the gain
// could not be computed (the sale is still recorded).
function SaleResult({ prev, usd }) {
  const gainText = prev.gain != null ? plus(exactWon(prev.gain), Math.round(prev.gain)) + (prev.pct != null ? ` (${signedPct(prev.pct)})` : "") : null;
  return (
    <section data-ui-v2="rec-result" style={{ marginTop: SPACE(3), background: COLOR.page, borderRadius: RADIUS.md, padding: `${SPACE(3)}px ${SPACE(4)}px` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap" }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.text2)}>{C.rec.proceeds}</span>
        <span style={{ textAlign: "right" }}>
          {prev.proceedsWon != null && <span data-ui-v2="rec-proceeds" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{exactWon(prev.proceedsWon)}</span>}
          {usd && <span data-ui-v2="rec-proceeds-usd" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { display: "block" })}>{usdText(prev.proceedsOwn)}</span>}
        </span>
      </div>
      {gainText && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), marginTop: SPACE(1), flexWrap: "wrap" }}>
          <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.text2)}>{C.rec.vsCost}</span>
          <span data-ui-v2="rec-gain" data-gain={Math.round(prev.gain)} style={tx(SIZE.body, WEIGHT.heavy, priceColor(Math.round(prev.gain), true))}>{gainText}</span>
        </div>
      )}
      <p data-ui-v2="rec-result-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2), wordBreak: "keep-all" })}>
        {prev.gain == null ? (prev.why === "noRate" ? C.rec.noRate : C.rec.noCost) : C.rec.note}
      </p>
      {prev.gain != null && prev.usdOnly && <p data-ui-v2="rec-usd-only" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1), wordBreak: "keep-all" })}>{C.rec.usdOnly}</p>}
    </section>
  );
}

// ---------------- after a sale that left 0 shares: 포트폴리오에서도 뺄까요? ----------------
function FullSale({ flow, setFlow, store, setStoreData, deck, close, shift, sample }) {
  const [q, body] = firstSentence(C.rec.fullSale);
  const [fail, setFail] = useState(false);
  const remove = () => {
    // the sale and dividend records move to history (A.3); v19.7a: logged in the portfolio's change log
    const next = withRemoval(store.data, deck.id, flow.t, todayKst(), Date.now());
    if (!save(store, setStoreData, next)) { setFail(true); return; }
    console.info(`[v2] ${deck.id}: ${flow.t} taken out after a full sale (its sale and dividend records stay in the returns)`);
    close();
  };
  return (
    <BottomSheet open title={q} onClose={() => setFlow({ ...flow, stage: "list", saved: true })} closeLabel={C.app.close} shift={shift}>
      {sample}
      <div data-ui-v2="rec-full">
        {body && <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { wordBreak: "keep-all" })}>{body}</p>}
        {fail && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
        <div style={{ display: "flex", gap: SPACE(2), marginTop: SPACE(4) }}>
          <Button onClick={remove} style={{ flex: 1 }}>{C.rec.remove}</Button>
          <Button kind="secondary" onClick={() => setFlow({ ...flow, stage: "list", saved: true })} style={{ flex: 1 }}>{C.rec.keep}</Button>
        </div>
      </div>
    </BottomSheet>
  );
}

export { typed };
