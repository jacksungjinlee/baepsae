// 매일 점검 on 내 덱 (v18.3 Part C): each held stock's status from the daily rule check (rules.js), the reasons with
// their numbers and report year, the 확인 필요 answers (실제로 줄였어요 / 줄인 게 아니에요), and the rule book with
// today's results. The 오늘 hero (today.jsx), the 내 덱 tracking sheet (tracking.jsx) and 왜 움직였나 (why.jsx) are
// Part E: they read the same evaluation and reuse the pieces exported here.
// A chip only on exceptions (REDESIGN 3): 규칙 깨짐, 지켜봐요 (also for 확인 필요), 큰 움직임. No chip = fine.
import React from "react";
import { COLOR, SIZE, WEIGHT, SPACE } from "../ui/tokens.js";
import { ListRow, StatusChip, Button, Collapsible } from "../ui/components.jsx";
import { C, fill, nf, p1 } from "./format.js";
import { RuleLine, tx } from "./ui.jsx";
import { signedPct } from "./deckcalc.js";

const R = () => C.plan.rules;
const yearText = (fy) => (fy ? fill(C.app.reportYear, { year: fy }) : null);
const won = (v) => nf(Math.round(v));

// The {항목} of "… 자료를 받지 못해 확인이 필요해요". A band without weights names the stocks whose price is missing.
function itemOf(r, x, names) {
  const map = { dps: R().dividend, debt: R().debt, roe: R().roe, op: R().opProfit, price: C.daily.price };
  if (r.input === "price" && r.missingPrice && r.missingPrice.length && !r.missingPrice.includes(x.t)) {
    return [r.missingPrice.map((t) => names.get(t) || t).join(" · "), C.daily.price].join(" ");
  }
  return map[r.input] || null;
}

function opPieces(op) {
  const base = op && op[1] != null && op[1] > 0 && op[0] != null ? fill(C.pick.caution.opFall, { pct: signedPct((op[0] / op[1] - 1) * 100) }) : R().opProfit;
  return [base, R().opLimit].filter(Boolean);
}

const bandPiece = (band, bands) => (band === "low" ? fill(C.daily.bandLow, { x: p1(bands[0] * 100) })
  : band === "high" ? fill(C.daily.bandHigh, { x: p1(bands[1] * 100) }) : fill(C.daily.bandTrim, { x: p1(bands[2] * 100) }));

// One reason -> { pieces, body, source, confirm } (also used by the 오늘 hero and 왜 움직였나, Part E)
export function reasonView(r, x, names) {
  switch (r.code) {
    case "divCut": return { pieces: [R().divCut, fill(R().dpsChange, { a: won(r.a), b: won(r.b) })], body: C.daily.sellNow, source: yearText(r.fy) };
    case "divDrop": return { pieces: [fill(C.pick.caution.divDrop, { name: x.nk, a: won(r.a), b: won(r.b) })], body: C.pick.caution.divDropBody,
      source: yearText(r.fy), confirm: r.confirm };
    case "missing": { const item = itemOf(r, x, names); return item ? { pieces: [fill(C.daily.missing, { item })] } : null; }
    case "debtOver": return { pieces: [fill(C.daily.keepLine, { item: R().debt, x: won(r.now), limit: r.limit })], source: yearText(r.fy) };
    case "roeUnder": return { pieces: [fill(C.daily.keepLine, { item: R().roe, x: p1(r.now), limit: r.limit })], source: yearText(r.fy) };
    case "opFell2": return { pieces: opPieces(r.op), source: yearText(r.fy) };
    case "band": return { pieces: [C.daily.weight, fill(R().now, { x: p1(r.now * 100) }), bandPiece(r.band, r.bands)] };
    case "noRules": return { pieces: [C.app.notChecked] };
    default: return null;
  }
}

// 확인 필요 shows the 지켜봐요 chip until its own chip label is approved (C.daily.check); a weight band gets a chip
// only once its name is approved (C.daily.band), otherwise its line on 내 덱 says it.
export function statusChips(x) {
  const chips = [];
  const band = C.daily.band && C.daily.band[x.status];
  if (x.status === "broken") chips.push(<StatusChip key="s" tone="broken">{C.daily.broken}</StatusChip>);
  else if (x.status === "check" && C.daily.check) chips.push(<StatusChip key="s" tone="watch">{C.daily.check}</StatusChip>);
  else if (x.status === "check" || x.status === "watch") chips.push(<StatusChip key="s" tone="watch">{C.daily.watch}</StatusChip>);
  else if (band) chips.push(<StatusChip key="s" tone="neutral">{band}</StatusChip>);
  if (x.bigMove) chips.push(<StatusChip key="b" tone="neutral">{C.daily.bigMove}</StatusChip>);
  return chips.length ? <span data-ui-v2="status-chips" style={{ display: "inline-flex", flexWrap: "wrap", gap: SPACE(1) }}>{chips}</span> : null;
}

export function StatusLines({ x, names, onConfirm }) {
  const views = x.reasons.map((r) => [r, reasonView(r, x, names)]).filter(([, v]) => v);
  if (!views.length) return null;
  return (
    <div data-ui-v2="status-lines" style={{ padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>
      {views.map(([r, v], i) => (
        <div key={i} data-ui-v2="status-line" data-code={r.code} style={{ marginTop: i ? SPACE(2) : 0 }}>
          <div style={tx(SIZE.xs, WEIGHT.bold, r.level === "broken" ? COLOR.ink : r.level === "check" || r.level === "watch" ? COLOR.watch : COLOR.text2)}>
            {v.pieces.map((p, j) => <span key={j}>{j ? " · " : ""}{p}</span>)}
          </div>
          {v.body && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{v.body}</div>}
          {v.source && <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{v.source}</div>}
          {v.confirm && onConfirm && (
            <div data-ui-v2="confirm" style={{ display: "flex", flexDirection: "column", gap: SPACE(2), marginTop: SPACE(2) }}>
              <Button kind="secondary" onClick={() => onConfirm(v.confirm, "cut")}>{C.daily.confirmCut}</Button>
              <Button kind="secondary" onClick={() => onConfirm(v.confirm, "notCut")}>{C.daily.confirmNotCut}</Button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// Today's result -> the RuleLine state: ok (check) · watch (alert: fails, needs a check, or input missing) · broken.
// An annual rule whose report is still the purchase report shows the plain rule icon: nothing new to compare yet.
function stateOf(r) {
  if (r.result === "broken") return "broken";
  if (r.result === "fail" || r.result === "check" || r.result === "missing" || r.result === "band") return "watch";
  if (r.result === "ok") return r.newer === false ? undefined : "ok";
  return undefined;
}

export function HoldingRules({ x, names }) {
  const line = (r) => {
    const src = yearText(r.fy);
    const st = stateOf(r);
    const miss = r.result === "missing" ? (() => { const item = itemOf(r, x, names); return item ? fill(C.daily.missing, { item }) : null; })() : null;
    const label = r.result === "broken" ? C.daily.broken : null;
    const pend = (name) => <RuleLine key={r.id} name={name} pending />;
    switch (r.id) {
      case "divCut": return r.check === "pending" ? pend(R().divCut)
        : <RuleLine key={r.id} name={R().dividend} now={r.now ? fill(R().dpsChange, { a: won(r.now.a), b: won(r.now.b) }) : null} limit={R().divLimit}
            source={src} state={st} stateLabel={label} note={miss} />;
      case "audit": return pend(R().audit);
      case "acquisition": return pend(R().acquisition);
      case "embezzle": return R().embezzle ? pend(R().embezzle) : null;
      case "cet1": return pend(R().cet1);
      case "kics": return pend(R().kics);
      case "debtCeiling":
        if (r.check === "pending") return pend(R().debt);
        if (r.result === "na") return <RuleLine key={r.id} name={R().debt} now={C.daily.finNA} />;
        return <RuleLine key={r.id} name={R().debt} now={r.now != null ? fill(R().now, { x: won(r.now) }) : null} limit={fill(R().over, { x: r.limit })}
          source={src} state={st} note={miss} />;
      case "roeFloor": return R().roeLimit && r.check !== "pending"
        ? <RuleLine key={r.id} name={R().roe} now={r.now != null ? fill(R().now, { x: p1(r.now) }) : null} limit={fill(R().roeLimit, { x: r.limit })} source={src} state={st} note={miss} />
        : null;
      case "opDecline": return R().opLimit && r.check !== "pending"
        ? <RuleLine key={r.id} name={R().opProfit} limit={R().opLimit} source={src} state={st} note={miss} /> : null;
      default: return null;
    }
  };
  const section = (kind, title) => {
    const rows = x.rules.filter((r) => r.kind === kind).map(line).filter(Boolean);
    return rows.length ? <div style={{ marginTop: SPACE(2) }}><div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{title}</div>{rows}</div> : null;
  };
  const band = x.rules.find((r) => r.id === "band" && r.check === "checked");
  const bandMiss = band && band.result === "missing" ? itemOf(band, x, names) : null;
  return (
    <div data-rules-today={x.t}>
      {section("sell", R().sell)}
      {section("keep", R().keep)}
      {band && (
        <div style={{ marginTop: SPACE(3) }}>
          <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{fill(R().band, { pct: p1(band.target * 100) })}</div>
          <RuleLine name={fill(R().bandText, { a: p1(band.bands[0] * 100), b: p1(band.bands[1] * 100), c: p1(band.bands[2] * 100) })}
            now={band.now != null ? fill(R().now, { x: p1(band.now * 100) }) : null} state={stateOf(band)}
            note={bandMiss ? fill(C.daily.missing, { item: bandMiss }) : null} />
        </div>
      )}
    </div>
  );
}

// One held stock on 내 덱: the row, then (when the check ran today) its status lines and its rule book with results.
// Part E: change = the return since purchase (won, %), extra = the weight bar with its target mark.
export function HoldingRow({ title, sub, x, names, onConfirm, change, extra }) {
  return (
    <div data-holding={x ? x.t : undefined} data-status={x ? x.status : undefined} data-big={x && x.bigMove ? "1" : undefined}>
      <ListRow title={title} sub={sub} chip={x ? statusChips(x) : null} change={change} />
      {extra}
      {x && <StatusLines x={x} names={names} onConfirm={onConfirm} />}
      {x && (
        <Collapsible title={fill(R().open, { name: title })}>
          <HoldingRules x={x} names={names} />
        </Collapsible>
      )}
    </div>
  );
}
