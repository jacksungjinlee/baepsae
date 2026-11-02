// 내 덱 tracking sheet (v18.3 Part E): value, money put in and return, the return since the start against KOSPI over
// the same dates (two numbers; the line chart comes with v18.0's per-stock history), each holding's weight bar with its
// target mark, and 추가로 넣을 돈. Everything reads the daily check (rules.js): nothing is shown from stale or failed
// data, and a number whose input is missing is left out, never estimated.
import React, { useEffect, useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE } from "../ui/tokens.js";
import { WeightBar, MoneyInput } from "../ui/components.jsx";
import { C, fill, p1, wonText } from "./format.js";
import { Note, tx } from "./ui.jsx";
import { signedPct } from "./deckcalc.js";
import { deckMoney, indexSince, addMoney } from "./track.js";

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
        <div data-ui-v2="vs-kospi" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: SPACE(2), marginTop: SPACE(3) }}>
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

// "종목별 · 수익률" header and the legend of the weight bars.
export function ByStockHead() {
  return (
    <div style={{ marginTop: SPACE(4) }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{C.deck.byStock}</span>
        <span style={tx(SIZE.xxs, WEIGHT.semi, COLOR.text3)}>{C.deck.ret}</span>
      </div>
      <div data-ui-v2="weight-legend" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>
        <span style={{ display: "block" }}>{C.plan.targetNote}</span>
        <span style={{ display: "block" }}>{C.deck.bandNote}</span>
      </div>
    </div>
  );
}

// Today's weight against the target (both from the daily check). Outside the band (the status from rules.js) the bar
// turns amber; the number is today's weight.
export function WeightLine({ x }) {
  if (x.w == null || !(x.target > 0)) return null;
  const out = BAND.includes(x.status);
  return (
    <div data-ui-v2="weight" data-band={out ? x.status : undefined} style={{ display: "flex", alignItems: "center", gap: SPACE(3), padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>
      <span style={tx(SIZE.xxs, WEIGHT.semi, COLOR.text3, { width: SPACE(8) })}>{C.daily.weight}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <WeightBar current={Math.round(x.w * 1000) / 10} target={Math.round(x.target * 1000) / 10} max={Math.max(30, x.target * 160)}
          label={C.daily.weight} status={out ? "watch" : "ok"} />
      </div>
      <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { width: SPACE(12), textAlign: "right" })}>{`${p1(x.w * 100)}%`}</span>
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
  return (
    <div data-ui-v2="add-money" style={{ marginTop: SPACE(5), paddingTop: SPACE(4), borderTop: `1px solid ${COLOR.line}` }}>
      <MoneyInput label={A.label} unit={C.app.manUnit} value={man} onChange={setMan} clearLabel={A.clear}
        quick={[{ label: A.quick[0], add: 10 }, { label: A.quick[1], add: 100 }, { label: A.quick[2], add: 1000 }]} />
      <Note>{A.body}</Note>
      {!man && <Note data-ui-v2="add-empty">{A.empty}</Note>}
      {man > 0 && !r.eligible.length && A.noneEligible && <Note tone="watch" data-ui-v2="add-none-eligible">{A.noneEligible}</Note>}
      {man > 0 && r.eligible.length > 0 && !r.buys.length && <Note tone="watch" data-ui-v2="add-none">{A.none}</Note>}
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

export { deckMoney };
