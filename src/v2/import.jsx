// ================= 가진 종목 넣기 (v19.3d, v19.3 Part F, board Import2) =================
// Three steps: the holdings → 기준 (the 포트폴리오 만들기 기준 카드 step, build.jsx StepCards; 빼기 and 조건 are skipped)
// → 점검 (report.jsx). Address #portfolio/import; the half-made list lives in the app (app.jsx importer), so a tab switch
// keeps it.
// - Search by Korean name, English name, 6-digit code or US ticker (pf.js findStocks), Korea and US (and the bond / gold
//   funds). Each row: logo, name, market, quantity (Korea whole shares, US up to 4 decimals) or, with 금액으로 넣기, an
//   amount in 만원 (saved with that day's close and date: the value moves with the price afterwards), value and weight,
//   and an optional 평균 단가 (never filled in: "+ 평균 단가 넣기 (선택)").
// - 붙여 넣기: one stock per line, name or code then quantity. A preview shows what was read and nothing is added until
//   이대로 넣기; a line with no stock or no single clear quantity is listed with its number (the line itself in grey); a
//   partial name two or more stocks match asks the user to pick (never guessed).
// - Donut of value by holding in the navy shades by weight (Part C) with "{n}종목" and the total, and the date line.
// The step labels (종목 넣기 · 기준 · 점검) are not approved words yet: the stepper shows three bars only.
// No 뱁이 (numbers on every step). No Korean here: src/copy/v2.js.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, SELECTED, HOLDING_SHADES, holdingShades } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Amount } from "../ui/components.jsx";
import { C, fill, nf, mdText, wonText, todayKst } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, PendingBlock, Footer, Note, ActionBar, useLayout, tx, tap } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { defaultSettings, activeCards, num } from "./engine.js";
import { deckState } from "./deckcalc.js";
import { StepCards } from "./build.jsx";
import { findStocks, parsePaste, okQty, draftOk, importedRecord, usdOf, wonPrice, marketKey } from "./pf.js";
import { qtyText } from "./pfview.jsx";
import { Report } from "./report.jsx";
import { withDeck, writeStore } from "./store.js";

export const newImporter = () => ({ step: 0, drafts: [], settings: defaultSettings(), amount: false, paste: null });
// Something typed that leaving would throw away.
export const importInProgress = (im) => !!im && (im.drafts.length > 0 || im.step > 0);

const clean = (x) => String(x == null ? "" : x).replace(/[,\s]/g, "");
const NUM = /^\d+(\.\d+)?$/;
// What a row's fields say: { qty | amountWon, avg } as numbers (null when blank or not valid).
export function readDraft(d, s) {
  const q = clean(d.qty), a = clean(d.amount), v = clean(d.avg);
  const qty = NUM.test(q) && okQty(Number(q), s) ? Number(q) : null;
  const man = NUM.test(a) && Number(a) > 0 ? Number(a) : null;
  const avg = NUM.test(v) && Number(v) > 0 && (v.split(".")[1] || "").length <= 2 ? Number(v) : null;
  return { t: d.t, mode: d.mode, qty, amountWon: man != null ? Math.round(man * 10000) : null, avg, badQty: d.mode === "qty" && q !== "" && qty == null,
    badAmount: d.mode === "amount" && a !== "" && man == null, badAvg: v !== "" && avg == null };
}

function StepBars({ step }) {
  return (
    <ol aria-label={C.build.stepsAria} style={{ listStyle: "none", display: "flex", gap: SPACE(2), padding: 0, margin: `${SPACE(3)}px 0 0` }}>
      {[0, 1, 2].map((i) => (
        <li key={i} aria-current={i === step ? "step" : undefined} style={{ flex: 1 }}>
          <div style={{ height: SPACE(1), borderRadius: 2, background: i <= step ? COLOR.ink : COLOR.border }} />
        </li>
      ))}
    </ol>
  );
}

// importer: { step, drafts, settings, amount, paste }; setImporter: its setter. onExit: leave (back). onSaved(deck): the
// portfolio was saved by 매일 점검 시작하기.
export function Import({ load, store, setStoreData, importer, setImporter, onExit, onSaved }) {
  if (load.status !== "ok" || load.missing.length) {
    return (
      <Page>
        <AppBar onBack={onExit} backLabel={C.build.prevStep} />
        <ScreenTitle>{C.imp.title}</ScreenTitle>
        {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        {load.status === "fail" && <LoadFail />}
        {load.status === "ok" && <PendingBlock data-ui-v2="import-not-ready" />}
        <Footer />
      </Page>
    );
  }
  const go = (step) => { setImporter((m) => ({ ...m, step })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  if (importer.step === 1) return <CardsStep load={load} importer={importer} setImporter={setImporter} go={go} />;
  if (importer.step === 2) {
    return <ReportStep load={load} store={store} setStoreData={setStoreData} importer={importer} go={go} onSaved={onSaved} />;
  }
  return <HoldingsStep load={load} importer={importer} setImporter={setImporter} go={go} onExit={onExit} />;
}

// ---------------- step 1: the holdings ----------------
function HoldingsStep({ load, importer, setImporter, go, onExit }) {
  const [q, setQ] = useState("");
  const stocks = load.data.stocks;
  const byT = load.byT;
  const fx = num(load.data.fx);
  const drafts = importer.drafts;
  const set = (patch) => setImporter((m) => ({ ...m, ...patch }));
  const setDraft = (t, patch) => setImporter((m) => ({ ...m, drafts: m.drafts.map((d) => (d.t === t ? { ...d, ...patch } : d)) }));
  const add = (s, extra = {}) => setImporter((m) => (m.drafts.some((d) => d.t === s.t) ? m
    : { ...m, drafts: [...m.drafts, { t: s.t, mode: m.amount ? "amount" : "qty", qty: "", amount: "", avg: "", avgOpen: false, ...extra }] }));
  const remove = (t) => setImporter((m) => ({ ...m, drafts: m.drafts.filter((d) => d.t !== t) }));
  const results = useMemo(() => findStocks(stocks, q, 8), [stocks, q]);
  // values and weights of the rows that are ready (a quantity or an amount, and today's price)
  const rows = drafts.map((d) => {
    const s = byT.get(d.t) || null;
    const r = readDraft(d, s);
    const px = s ? wonPrice(s, fx) : null;
    const value = !(px > 0) ? null : d.mode === "amount" ? r.amountWon : r.qty != null ? r.qty * px : null;
    return { d, s, r, value: value > 0 ? value : null };
  });
  const ready = rows.filter((x) => x.value != null);
  const total = ready.reduce((a, x) => a + x.value, 0);
  const shades = holdingShades(rows.map((x) => (x.value != null && total > 0 ? x.value / total : null)));
  // every row must make a record store.js accepts (draftOk mirrors its checks), so 매일 점검 시작하기 can never be refused
  const allOk = rows.length > 0 && rows.every((x) => x.s && draftOk({ mode: x.d.mode, qty: x.r.qty, amountWon: x.r.amountWon }, x.s, fx) && !x.r.badAvg);
  const us = rows.some((x) => usdOf(x.s));
  const md = mdText(load.data.pxDate);
  const usMd = us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  return (
    <Page pad={SPACE(30)}>
      <AppBar onBack={onExit} backLabel={C.build.prevStep} />
      <StepBars step={0} />
      <DateLine date={load.data.pxDate} fresh={load.fresh} />
      <ScreenTitle>{C.imp.title}</ScreenTitle>
      <Search q={q} setQ={setQ} results={results} drafts={drafts} onAdd={(s) => { add(s); setQ(""); }} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: SPACE(2), marginTop: SPACE(3) }}>
        <ModeButton icon="clipboard-text" title={C.imp.paste} sub={C.imp.pasteSub} on={!!importer.paste} data="paste"
          onClick={() => set({ paste: importer.paste ? null : { text: "", picks: {} } })} />
        <ModeButton icon="scales" title={C.imp.amount} sub={C.imp.amountSub} on={importer.amount} data="amount"
          onClick={() => set({ amount: !importer.amount })} />
      </div>
      {importer.paste && <PastePanel load={load} paste={importer.paste} setPaste={(p) => set({ paste: p })} drafts={drafts}
        onConfirm={(lines) => setImporter((m) => ({ ...m, paste: null, drafts: mergeLines(m.drafts, lines) }))} />}
      {ready.length > 0 && <Donut rows={rows} total={total} shades={shades} />}
      {rows.length > 0 && (
        <Card data-ui-v2="import-rows">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2) }}>
            <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.pick.picked}</span>
            <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.imp.cols}</span>
          </div>
          {rows.map((x, i) => (
            <DraftRow key={x.d.t} x={x} shade={shades[i]} total={total} onChange={(patch) => setDraft(x.d.t, patch)} onRemove={() => remove(x.d.t)} />
          ))}
          {md && (
            <p data-ui-v2="import-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3) })}>
              {us && fx ? fill(C.imp.priceLine, { date: md, fx: nf(Math.round(fx)) }) : fill(C.why.close, { md })}
            </p>
          )}
          {usMd && <Note>{fill(C.app.usClose, { md: usMd })}</Note>}
        </Card>
      )}
      <Footer />
      <ActionBar summary={rows.length ? fill(C.app.stocksN, { n: rows.length }) : null} action={C.imp.check} disabled={!allOk} onAction={() => go(1)} />
    </Page>
  );
}

// Pasted lines the user confirmed: a stock already listed gets the quantity added (two accounts); otherwise a new row.
function mergeLines(drafts, lines) {
  const out = drafts.map((d) => ({ ...d }));
  for (const l of lines) {
    const cur = out.find((d) => d.t === l.s.t);
    if (!cur) { out.push({ t: l.s.t, mode: "qty", qty: String(l.qty), amount: "", avg: "", avgOpen: false }); continue; }
    if (cur.mode !== "qty") continue;          // never reached: PastePanel marks such a line "amount" and does not pass it
    const before = Number(clean(cur.qty));
    cur.qty = NUM.test(clean(cur.qty)) ? String(Math.round((before + l.qty) * 10000) / 10000) : String(l.qty);
  }
  return out;
}

function Search({ q, setQ, results, drafts, onAdd }) {
  const s4 = C.build.s4;
  return (
    <div data-ui-v2="import-search" style={{ marginTop: SPACE(3) }}>
      <label style={{ display: "flex", alignItems: "center", gap: SPACE(2), background: COLOR.surface, border: `2px solid ${COLOR.ink}`, borderRadius: RADIUS.md,
        padding: `0 ${SPACE(3)}px`, minHeight: TOUCH + SPACE(2) }}>
        <Icon name="magnifying-glass" size={20} tone="on" />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={C.imp.search} aria-label={C.imp.search} autoComplete="off"
          style={{ flex: 1, minWidth: 0, border: "none", outline: "none", background: "transparent", ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
      </label>
      {q.trim() && !results.length && <Note data-ui-v2="import-none">{C.imp.none}</Note>}
      {results.length > 0 && (
        <Card style={{ padding: `${SPACE(1)}px ${SPACE(4)}px`, marginTop: SPACE(2) }}>
          {results.map((s) => {
            const had = drafts.some((d) => d.t === s.t);
            return (
              <div key={s.t} data-import-result={s.t} style={{ display: "flex", alignItems: "center", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
                <CoMark s={s} size={SPACE(8)} />
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{s.nk}</span>
                  <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{s.t} · {marketOf(s)}</span>
                </span>
                {had ? <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{s4.added}</span> : (
                  <button type="button" aria-label={fill(s4.addAria, { name: s.nk })} onClick={() => onAdd(s)}
                    style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, background: COLOR.surface,
                      padding: `0 ${SPACE(3)}px`, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{s4.add}</button>
                )}
              </div>
            );
          })}
        </Card>
      )}
    </div>
  );
}

// The market a row shows: the data has no exchange name, so 한국 / 미국 (Part F: "otherwise 한국 / 미국").
// v19.3d review: the currency decides (pf.js marketKey): 379800 KODEX 미국S&P500 is a KRX listing in won (한국).
const marketOf = (s) => C.pick.market[marketKey(s)];

function ModeButton({ icon, title, sub, on, onClick, data }) {
  return (
    <button type="button" data-ui-v2="import-mode" data-mode={data} aria-pressed={on} onClick={onClick}
      style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(2), textAlign: "left", minHeight: TOUCH + SPACE(4), padding: `${SPACE(2)}px ${SPACE(3)}px`,
        borderRadius: RADIUS.md, background: on ? SELECTED.background : COLOR.surface, border: on ? `2px solid ${COLOR.ink}` : "2px solid transparent", minWidth: 0 }}>
      <span style={{ width: SPACE(9), height: SPACE(9), borderRadius: "30%", background: COLOR.select, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={icon} size={20} tone="on" />
      </span>
      <span style={{ minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{title}</span>
        <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{sub}</span>
      </span>
    </button>
  );
}

// 붙여 넣기: the text, then what was read (nothing is added until 이대로 넣기).
function PastePanel({ load, paste, setPaste, onConfirm, drafts = [] }) {
  const parsed = useMemo(() => parsePaste(paste.text, load.data.stocks, around(C.plan.shares, "n")[1]), [paste.text, load.data.stocks]);
  // a line where the user picked one of several stocks: read again with that stock (its own quantity rule)
  const lines = parsed.map((l) => {
    if (l.st !== "pick" || !paste.picks[l.line]) return l;
    const s = load.byT.get(paste.picks[l.line]);
    return s && l.qty != null && okQty(l.qty, s) ? { ...l, st: "ok", s } : { ...l, st: "noQty", s };
  }).map((l) => (l.st === "ok" && drafts.some((d) => d.t === l.s.t && d.mode === "amount") ? { ...l, st: "amount" } : l));
  // "amount": the stock is already listed by amount, and a quantity cannot be added to an amount. The line is shown as not
  // used (marked, with the line in grey) and 이대로 넣기 leaves it out; its own sentence waits for Jack's wording.
  const ok = lines.filter((l) => l.st === "ok");
  return (
    <Card data-ui-v2="paste-panel">
      <label style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block" })}>
        {C.imp.paste}
        <textarea value={paste.text} onChange={(e) => setPaste({ ...paste, text: e.target.value })} rows={5} aria-label={C.imp.paste}
          style={{ display: "block", width: "100%", marginTop: SPACE(1), border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, padding: SPACE(3), resize: "vertical",
            boxSizing: "border-box", background: COLOR.surface, ...tx(SIZE.body, WEIGHT.regular, COLOR.ink) }} />
      </label>
      {lines.length > 0 && (
        <div data-ui-v2="paste-preview" style={{ marginTop: SPACE(3) }}>
          <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.imp.previewTitle}</div>
          {lines.map((l) => <PasteLine key={l.line} l={l} onPick={(t) => setPaste({ ...paste, picks: { ...paste.picks, [l.line]: t } })} />)}
          <div style={{ marginTop: SPACE(3) }}>
            <button type="button" data-ui-v2="paste-confirm" disabled={!ok.length} onClick={() => onConfirm(ok)}
              style={{ ...tap, width: "100%", minHeight: TOUCH, border: "none", borderRadius: RADIUS.sm, background: COLOR.ink, opacity: ok.length ? 1 : 0.45,
                ...tx(SIZE.body, WEIGHT.bold, COLOR.surface) }}>{C.imp.confirm}</button>
          </div>
        </div>
      )}
    </Card>
  );
}

function PasteLine({ l, onPick }) {
  const row = { padding: `${SPACE(2)}px 0`, borderTop: `1px solid ${COLOR.line}` };
  if (l.st === "ok") {
    return (
      <div data-paste-line={l.line} data-st="ok" style={{ ...row, display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <CoMark s={l.s} size={SPACE(7)} />
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0 })}>{l.s.nk}</span>
        <span style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink)}>{fill(C.plan.shares, { n: qtyText(l.qty) })}</span>
      </div>
    );
  }
  if (l.st === "amount") {
    return (
      <div data-paste-line={l.line} data-st="amount" style={{ ...row, display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <span aria-hidden="true" style={{ display: "flex" }}><Icon name="warning" size={18} tone="on" /></span>
        <CoMark s={l.s} size={SPACE(7)} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.text2, { display: "block", textDecoration: "line-through" })}>{l.s.nk}</span>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block", wordBreak: "break-all" })}>{l.text}</span>
        </span>
      </div>
    );
  }
  if (l.st === "pick") {
    return (
      <div data-paste-line={l.line} data-st="pick" style={row}>
        <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.watch)}>{fill(C.imp.pick, { q: l.q })}</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE(1), marginTop: SPACE(1) }}>
          {l.choices.map((s) => (
            <button key={s.t} type="button" data-pick={s.t} onClick={() => onPick(s.t)}
              style={{ ...tap, minHeight: TOUCH, border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, background: COLOR.surface, padding: `0 ${SPACE(3)}px`,
                ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{s.nk}</button>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div data-paste-line={l.line} data-st={l.st} style={row}>
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.watch)}>{fill(l.st === "noStock" ? C.imp.noStockLine : C.imp.noQtyLine, { n: l.line })}</div>
      <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { wordBreak: "break-all" })}>{l.text}</div>
    </div>
  );
}

// A number field with its unit after it ("[40]주", "[150]만원"); label: what a screen reader says.
function NumField({ value, onChange, label, unit, before, invalid, width = 88, decimals = true, dataUi }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: SPACE(1), ...tx(SIZE.sm, WEIGHT.semi, COLOR.ink) }}>
      {before && <span>{before}</span>}
      <input type="text" inputMode={decimals ? "decimal" : "numeric"} value={value} aria-label={label} aria-invalid={invalid ? "true" : undefined} data-ui-v2={dataUi}
        onChange={(e) => onChange(e.target.value)}
        style={{ width, minHeight: TOUCH - SPACE(1), border: invalid ? `2px solid ${COLOR.watch}` : `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm,
          padding: `0 ${SPACE(2)}px`, textAlign: "right", background: COLOR.surface, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
      {unit && <span>{unit}</span>}
    </span>
  );
}
// A copy line split at one {slot}: [before, after].
const around = (tpl, slot) => { const i = tpl.indexOf(`{${slot}}`); return i < 0 ? [tpl, ""] : [tpl.slice(0, i), tpl.slice(i + slot.length + 2)]; };

function DraftRow({ x, shade, total, onChange, onRemove }) {
  const { d, s, r, value } = x;
  const name = s ? s.nk : d.t;
  const usd = usdOf(s);
  // Each word next to a field is a whole approved piece: 수량 (주) before the quantity, 만원 after the amount, 평균 단가 before
  // the 평균 단가 (US: "$" in front; the won amount needs no unit word of its own).
  const [ab] = around(C.imp.avg, "price");
  const w = value != null && total > 0 ? value / total : null;
  return (
    <div data-import-row={d.t} data-mode={d.mode} style={{ display: "flex", gap: SPACE(3), padding: `${SPACE(3)}px 0`, borderTop: `1px solid ${COLOR.line}` }}>
      <CoMark s={s} t={d.t} name={name} size={SPACE(10)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap" }}>
          <span style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{name}</span>
          <span data-ui-v2="import-market" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{marketOf(s)}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(1) }}>
          {d.mode === "amount"
            ? <NumField value={d.amount} onChange={(v) => onChange({ amount: v })} label={C.today.value} unit={C.app.manUnit} invalid={r.badAmount} dataUi="import-amount" />
            : <NumField value={d.qty} onChange={(v) => onChange({ qty: v })} label={C.plan.qty} before={C.plan.qty} invalid={r.badQty} decimals={usd} dataUi="import-qty" />}
        </div>
        {w != null && (
          <div aria-hidden="true" style={{ height: SPACE(1) + 2, background: COLOR.page, borderRadius: 999, marginTop: SPACE(2) }}>
            <div style={{ width: `${Math.min(100, w * 100)}%`, height: "100%", background: shade || HOLDING_SHADES[HOLDING_SHADES.length - 1], borderRadius: 999 }} />
          </div>
        )}
        <div style={{ marginTop: SPACE(1) }}>
          {d.avgOpen || d.avg ? (
            <NumField value={d.avg} onChange={(v) => onChange({ avg: v })} label={C.imp.addAvg} before={usd ? `${ab.trim()} $` : ab.trim()}
              invalid={r.badAvg} dataUi="import-avg" />
          ) : (
            <button type="button" data-ui-v2="import-add-avg" onClick={() => onChange({ avgOpen: true })}
              style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, padding: 0, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.imp.addAvg}</button>
          )}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
        {value != null && <span data-ui-v2="import-value" style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}><Amount text={wonText(value)} /></span>}
        {w != null && <span data-ui-v2="import-weight" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{Math.round(w * 100)}%</span>}
        <button type="button" aria-label={fill(C.build.s4.removeAria, { name })} onClick={onRemove}
          style={{ ...tap, marginTop: "auto", minHeight: TOUCH, minWidth: TOUCH, border: "none", background: "none", ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.build.s4.remove}</button>
      </div>
    </div>
  );
}

// Value by holding: a ring in the navy shades (Part C) with "{n}종목" and the total, and a legend with each weight.
function Donut({ rows, total, shades }) {
  const { wide } = useLayout();
  const R = 52, SW = 22, L = 2 * Math.PI * R;
  let at = 0;
  const segs = rows.map((x, i) => ({ x, i })).filter(({ x }) => x.value != null).map(({ x, i }) => {
    const f = x.value / total;
    const seg = { key: x.d.t, len: f * L, off: at, color: shades[i] };
    at += f * L;
    return seg;
  });
  const legend = rows.filter((x) => x.value != null).map((x) => ({ t: x.d.t, s: x.s, w: x.value / total, color: shades[rows.indexOf(x)] }));
  return (
    <Card data-ui-v2="import-donut" style={{ display: "flex", alignItems: "center", gap: SPACE(4), flexWrap: wide ? "nowrap" : "wrap" }}>
      <div style={{ position: "relative", width: 128, height: 128, flexShrink: 0, margin: "0 auto" }}>
        <svg width={128} height={128} viewBox="0 0 128 128" aria-hidden="true">
          <circle cx={64} cy={64} r={R} fill="none" stroke={COLOR.page} strokeWidth={SW} />
          {segs.map((g) => (
            <circle key={g.key} cx={64} cy={64} r={R} fill="none" stroke={g.color} strokeWidth={SW} strokeDasharray={`${Math.max(0, g.len - 1.5)} ${L}`}
              strokeDashoffset={-g.off} transform="rotate(-90 64 64)" />
          ))}
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.app.stocksN, { n: legend.length })}</span>
          <span data-ui-v2="import-total" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{wonText(total)}</span>
        </div>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, flex: 1, minWidth: 180 }}>
        {legend.map((g) => (
          <li key={g.t} style={{ display: "flex", alignItems: "center", gap: SPACE(2), padding: `${SPACE(1)}px 0` }}>
            <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 3, background: g.color, flexShrink: 0 }} />
            <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.ink, { flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{g.s ? g.s.nk : g.t}</span>
            <span style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{Math.round(g.w * 100)}%</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ---------------- step 2: 기준 ----------------
function CardsStep({ load, importer, setImporter, go }) {
  const st = importer.settings;
  const set = (patch) => setImporter((m) => ({ ...m, settings: { ...m.settings, ...patch } }));
  const ds = useMemo(() => deckState(load, st), [load, st]);
  const none = !activeCards(st.points).length;
  return (
    <Page pad={SPACE(30)}>
      <AppBar onBack={() => go(0)} backLabel={C.build.prevStep} />
      <StepBars step={1} />
      <DateLine date={load.data.pxDate} fresh={load.fresh} />
      <StepCards st={st} set={set} ds={ds} coach={null} />
      <Footer />
      <ActionBar summary={null} action={none ? C.build.pickCardsBtn : C.build.next} disabled={none} onAction={() => go(2)} />
    </Page>
  );
}

// ---------------- step 3: 점검 ----------------
function ReportStep({ load, store, setStoreData, importer, go, onSaved }) {
  const today = todayKst();
  const deck = useMemo(() => importedRecord({ drafts: importer.drafts.map((d) => readDraft(d, load.byT.get(d.t))), load, settings: importer.settings,
    id: "d" + Date.now().toString(36), name: C.deck.title, today }), [importer.drafts, importer.settings, load]);
  const [fail, setFail] = useState(false);
  // 매일 점검 시작하기: the portfolio is checked (store.js withDeck names a refused one in the console) and written here,
  // so the screen moves on only once it is really saved.
  const start = () => {
    // the rows were checked on the first step (draftOk mirrors store.js), so withDeck refusing is not expected; if it ever
    // does, the console names the row and the screen asks to check the inputs (never the storage line, which is not why)
    const next = withDeck(store.data, deck, today);
    if (!next) { setFail("input"); return; }
    if (!store.writable || !writeStore(next, store.key, today)) { setFail("storage"); return; }
    setFail(false);
    setStoreData(next, true);
    onSaved(deck);
  };
  return (
    <Page pad={SPACE(10)}>
      <AppBar onBack={() => go(1)} backLabel={C.build.prevStep} />
      <StepBars step={2} />
      <Report load={load} deck={deck} />
      {fail === "storage" && <Note tone="watch" data-ui-v2="report-fail">{C.store.unavailable}</Note>}
      {fail === "input" && <Note tone="watch" data-ui-v2="report-fail">{C.plan.badInput}</Note>}
      <div data-ui-v2="report-buttons" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: SPACE(2), marginTop: SPACE(4) }}>
        <button type="button" data-ui-v2="report-again" onClick={() => go(0)}
          style={{ ...tap, minHeight: TOUCH + SPACE(1), borderRadius: RADIUS.sm, border: `1px solid ${COLOR.border}`, background: COLOR.surface, ...tx(SIZE.sm, WEIGHT.bold, COLOR.ink) }}>{C.rpt.again}</button>
        <button type="button" data-ui-v2="report-start" onClick={start}
          style={{ ...tap, minHeight: TOUCH + SPACE(1), borderRadius: RADIUS.sm, border: "none", background: COLOR.ink, ...tx(SIZE.sm, WEIGHT.bold, COLOR.surface) }}>{C.rpt.start}</button>
      </div>
      <Footer />
    </Page>
  );
}
