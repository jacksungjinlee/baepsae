// 내 덱 tracking sheet (v18.3 Part E): value, money put in and return, the return since the start against KOSPI over
// the same dates (two numbers; the line chart comes with v18.0's per-stock history), each holding's weight bar with its
// target mark, and 추가로 넣을 돈. Everything reads the daily check (rules.js): nothing is shown from stale or failed
// data, and a number whose input is missing is left out, never estimated.
import React, { useEffect, useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE } from "../ui/tokens.js";
import { MoneyInput } from "../ui/components.jsx";
import { C, fill, p1, wonText } from "./format.js";
import { Note, tx } from "./ui.jsx";
import { signedPct } from "./deckcalc.js";
import { deckMoney, indexSince, addMoney, addMessage, bandOf, plainEdges } from "./track.js";

const signedWon = (v) => (v > 0 ? "+" : "") + wonText(v);
// Each left-out number is logged once per page view (loudly, with the reason), not on every render.
const warned = new Set();
const warnOnce = (msg) => { if (!warned.has(msg)) { warned.add(msg); console.warn(msg); } };
const BAND = ["low", "high", "trim"];

// Value, 원금 · 수익, and 내 덱 vs 코스피 since the deck's first purchase. m: deckMoney(deck, de).
export function DeckSummary({ deck, m, load }) {
  const idx = load.macro && load.macro.idxHist ? load.macro.idxHist.KOSPI : null;
  const k = useMemo(() => (m.cost != null && idx ? indexSince(deck, idx, load.data.pxDate) : { ok: false, why: idx ? "cost" : "noIndex" }),
    [deck, idx, load, m.cost]);
  useEffect(() => {
    if (m.noFx.length) warnOnce(`[v2] ${deck.id}: US purchases without an exchange rate (${m.noFx.join(", ")}): money put in and return left out`);
    if (m.cost != null && !k.ok) warnOnce(`[v2] ${deck.id}: KOSPI comparison left out (${k.why})`);
  });
  return (
    <div data-ui-v2="deck-summary" style={{ marginTop: SPACE(3) }}>
      <div data-ui-v2="deck-value" style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink)}>{wonText(m.value)}</div>
      {m.cost != null && (
        <div data-ui-v2="deck-money" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>
          {fill(C.deck.money, { cost: wonText(m.cost), gain: signedWon(m.gain), pct: signedPct(m.ret * 100) })}
        </div>
      )}
      {m.cost == null && C.deck.noFx && <Note>{C.deck.noFx}</Note>}
      {k.ok && (
        <div data-ui-v2="vs-kospi" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: SPACE(2), marginTop: SPACE(3) }}>
          <div data-ui-v2="vs-mine" style={{ background: COLOR.page, borderRadius: 12, padding: `${SPACE(2)}px ${SPACE(3)}px`, ...tx(SIZE.sm, WEIGHT.heavy, COLOR.ink) }}>
            {fill(C.deck.vsMine, { pct: signedPct(m.ret * 100) })}
          </div>
          <div data-ui-v2="vs-index" style={{ background: COLOR.page, borderRadius: 12, padding: `${SPACE(2)}px ${SPACE(3)}px`, ...tx(SIZE.sm, WEIGHT.heavy, COLOR.text2) }}>
            {fill(C.deck.vsKospi, { pct: signedPct(k.ret * 100) })}
          </div>
        </div>
      )}
    </div>
  );
}

// "종목별 · 수익률" header and the legend of the weight bars. plain: see plainEdges.
export function ByStockHead({ plain }) {
  return (
    <div style={{ marginTop: SPACE(4) }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{C.deck.byStock}</span>
        <span style={tx(SIZE.xxs, WEIGHT.semi, COLOR.text3)}>{C.deck.ret}</span>
      </div>
      <div data-ui-v2="weight-legend" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>
        <span style={{ display: "block" }}>{C.plan.targetNote}</span>
        {plain && <span style={{ display: "block" }} data-ui-v2="band-note">{C.deck.bandNote}</span>}
      </div>
    </div>
  );
}

// The weight bar: today's weight (filled), the target (apricot mark) and the three edges used today (thin marks), on a
// scale wide enough for all of them. The v18.1 WeightBar draws only the target, so this one is drawn here.
function BandBar({ w, target, bands, out }) {
  const top = Math.max(w * 1.1, target * 1.6, (bands ? bands[2] : 0) * 1.1, 0.01);
  const at = (v) => `${Math.min(100, Math.max(0, (v / top) * 100))}%`;
  return (
    <div data-ui-v2="band-bar" data-top={top} role="meter" aria-label={C.daily.weight} aria-valuemin={0} aria-valuemax={Math.round(top * 1000) / 10}
      aria-valuenow={Math.round(w * 1000) / 10} aria-valuetext={`${p1(w * 100)}%`}
      style={{ position: "relative", height: SPACE(2) + 2, background: COLOR.page, borderRadius: 999 }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: at(w), background: out ? COLOR.watch : COLOR.ink, borderRadius: 999 }} />
      {(bands || []).map((b, i) => (
        <div key={i} data-edge={i} style={{ position: "absolute", top: -2, bottom: -2, width: 1, left: at(b), background: COLOR.text3 }} />
      ))}
      <div data-target="1" style={{ position: "absolute", top: -SPACE(1), bottom: -SPACE(1), width: 3, borderRadius: 2, background: COLOR.apricot, left: at(target), transform: "translateX(-1.5px)" }} />
    </div>
  );
}

// Today's weight against the target (both from the daily check), and under it the edges actually used today (CSV 543
// pieces, as the rule book shows them). Outside the band (the status from rules.js) the bar turns amber.
export function WeightLine({ x }) {
  if (x.w == null || !(x.target > 0)) return null;
  const out = BAND.includes(x.status);
  const b = bandOf(x);
  const edges = b ? [fill(C.daily.bandLow, { x: p1(b.bands[0] * 100) }), fill(C.daily.bandHigh, { x: p1(b.bands[1] * 100) }),
    fill(C.daily.bandTrim, { x: p1(b.bands[2] * 100) })] : [];
  return (
    <div data-ui-v2="weight" data-band={out ? x.status : undefined} style={{ padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <span style={tx(SIZE.xxs, WEIGHT.semi, COLOR.text3, { width: SPACE(8) })}>{C.daily.weight}</span>
        <div style={{ flex: 1, minWidth: 0 }}><BandBar w={x.w} target={x.target} bands={b ? b.bands : null} out={out} /></div>
        <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { width: SPACE(12), textAlign: "right" })}>{`${p1(x.w * 100)}%`}</span>
      </div>
      {edges.length > 0 && (
        <div data-ui-v2="weight-edges" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>
          {edges.map((e, i) => <span key={i}>{i ? " · " : ""}{e}</span>)}
        </div>
      )}
    </div>
  );
}

// 추가로 넣을 돈: most underweight first, whole shares, skipping 규칙 깨짐 · 확인 필요 · 지켜봐요 and anything above 1.25x
// target (track.js addMoney), then the money left.
export function AddMoney({ de }) {
  const [man, setMan] = useState(0);
  const r = useMemo(() => addMoney(de, man * 10000), [de, man]);
  if (!r.ok) return null;
  const A = C.deck.add;
  const msg = addMessage(r, man * 10000);
  return (
    <div data-ui-v2="add-money" style={{ marginTop: SPACE(5), paddingTop: SPACE(4), borderTop: `1px solid ${COLOR.line}` }}>
      <MoneyInput label={A.label} unit={C.app.manUnit} value={man} onChange={setMan} clearLabel={A.clear}
        quick={[{ label: A.quick[0], add: 10 }, { label: A.quick[1], add: 100 }, { label: A.quick[2], add: 1000 }]} />
      <Note>{A.body}</Note>
      {!man && <Note data-ui-v2="add-empty">{A.empty}</Note>}
      {/* "금액을 늘려 보세요" (CSV 79) only when even the cheapest eligible share costs more than the amount. When every name
          is skipped, or the edges stop every buy, more money would not help: the pending line (omitted until approved). */}
      {msg === "none" && <Note tone="watch" data-ui-v2="add-none">{A.none}</Note>}
      {msg === "noneEligible" && (A.noneEligible ? <Note tone="watch" data-ui-v2="add-none-eligible">{A.noneEligible}</Note>
        : <span data-ui-v2="add-none-eligible" hidden />)}
      {r.buys.length > 0 && (
        <div data-ui-v2="add-buys" style={{ marginTop: SPACE(3) }}>
          {r.buys.map((b) => (
            <div key={b.t} data-add={b.t} style={{ display: "flex", justifyContent: "space-between", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { minWidth: 0 })}>{b.nk}</span>
              <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flexShrink: 0, textAlign: "right" })}>
                <span>{fill(C.plan.shares, { n: b.shares.toLocaleString("ko-KR") })}</span>{" · "}<span>{wonText(b.cost)}</span>
              </span>
            </div>
          ))}
          <div data-ui-v2="add-left" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(2) })}>
            {fill(A.left, { leftText: fill(A.leftText, { x: wonText(r.left) }) })}
          </div>
        </div>
      )}
    </div>
  );
}

export { deckMoney, plainEdges };
