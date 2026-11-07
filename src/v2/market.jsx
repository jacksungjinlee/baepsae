// 시장 tab (v19.0c, Jack's choice for step 1: the plan's question 2). Four tiles — 코스피, S&P 500 (level and change from
// macro.json idxHist), 국고채 3년 and 원/달러 (level only: the data has no daily change for them, so none is shown) — each
// with its own content date; a value that is missing or cannot be dated shows "–". When macro.json did not load, the
// approved load-failure line is shown above the tiles (원/달러 still comes from data.json). Two buttons open the old app's
// full screens (금리·원자재, 공시·수급: ./baepsae.html?from=app#macro · #disc, routes.js OLD_LINKS, read once by src/shell.jsx); the preview page has
// none. MarketTiles is also 홈's 시장 한눈에. No 뱁이 here: the tiles are numbers.
// PC (v19.0d, board PcMarket): two columns, the tiles on the left and the two buttons on the right (the preview page,
// without the buttons: the four tiles in one row). In 홈's narrow side column the tiles stack (cols 1).
import React, { useEffect } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { C, fill, nf, mdText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, Cols, tx, tap, useMode, useLayout } from "./ui.jsx";
import { signedPct } from "./deckcalc.js";
import { marketTiles } from "./stocklist.js";
import { OLD_LINKS } from "./routes.js";

const DASH = "–";
const warned = new Set();
const warnOnce = (msg) => { if (!warned.has(msg)) { warned.add(msg); console.warn(msg); } };

function valueText(x) {
  if (x.value == null) return DASH;
  if (x.kind === "index") return nf(x.value, 2);
  if (x.kind === "rate") return `${nf(x.value, 2)}%`;
  return fill(C.app.won, { n: nf(x.value, 1) });
}

// One tile: name, value, today's change (indices only), its own date.
function Tile({ x }) {
  const change = x.kind === "index" && x.change != null && x.value != null ? x.change : null;
  return (
    <div data-ui-v2="market-tile" data-id={x.id} data-has-value={x.value != null ? "1" : "0"}
      style={{ background: COLOR.page, borderRadius: RADIUS.md, padding: `${SPACE(3)}px ${SPACE(3)}px`, minWidth: 0 }}>
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.market[x.id]}</div>
      <div data-ui-v2="tile-value" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1), whiteSpace: "nowrap" })}>{valueText(x)}</div>
      <div style={{ display: "flex", flexWrap: "wrap", columnGap: SPACE(2), alignItems: "baseline" }}>
        {change != null && <span data-ui-v2="tile-change" style={tx(SIZE.xs, WEIGHT.bold, change < 0 ? COLOR.down : change > 0 ? COLOR.upOnPage : COLOR.text2)}>{signedPct(change)}</span>}
        {x.date && <span data-ui-v2="tile-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.app.asOf, { md: mdText(x.date) })}</span>}
      </div>
    </div>
  );
}

// cols: tiles per row (2 by default: the phone, and 시장's left column on PC).
export function MarketTiles({ load, cols = 2 }) {
  const tiles = marketTiles(load);
  useEffect(() => {
    for (const x of tiles) if (x.why && load.status === "ok") warnOnce(`[v2] market tile ${x.id}: ${x.value == null ? "no value" : "no change"} (${x.why})`);
  });
  return (
    <div data-ui-v2="market-tiles" data-cols={cols} style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: SPACE(2) }}>
      {tiles.map((x) => <Tile key={x.id} x={x} />)}
    </div>
  );
}

// A button into the old app: icon chip, label, chevron.
function OldLink({ href, icon, label, id, first }) {
  return (
    <a data-ui-v2="old-screen" data-id={id} href={href}
      style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(3), borderTop: first ? "none" : `1px solid ${COLOR.line}`, textDecoration: "none" }}>
      <IconChip name={icon} size={36} />
      <span style={tx(SIZE.body, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0 })}>{label}</span>
      <Icon name="chevronRight" size={20} tone="off" />
    </a>
  );
}

export function Market({ load, pad }) {
  const { preview } = useMode();
  const { wide } = useLayout();
  const ok = load.status === "ok";
  return (
    <Page pad={pad} cols={2}>
      <AppBar />
      <ScreenTitle>{C.app.tabs.market}</ScreenTitle>
      {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {load.status === "fail" && <LoadFail />}
      {ok && !load.macro && <LoadFail picture={false} />}
      <Cols main={ok && <Card data-ui-v2="market-tiles-card"><MarketTiles load={load} cols={wide && preview ? 4 : 2} /></Card>}
        side={!preview && (
          <Card data-ui-v2="market-more" style={{ paddingTop: SPACE(2), paddingBottom: SPACE(2) }}>
            {C.market.oldNote && <Note style={{ marginBottom: SPACE(2) }}>{C.market.oldNote}</Note>}
            <OldLink id="macro" href={OLD_LINKS.macro} icon="percent" label={C.market.macro} first />
            <OldLink id="disc" href={OLD_LINKS.disc} icon="file-text" label={C.market.disc} />
          </Card>
        )} />
      <Footer />
    </Page>
  );
}
