// ================= 회사 페이지 (v19.1a, docs/tasks/v19.1-company-page.md Parts A-F; boards CoSummary · CoPage · PcCompany) =================
// #stocks/<code> opens a Korean or US company inside 2.0 (every company tapped anywhere in 2.0 comes here; the old app's
// 기업분석 stays behind 예전 뱁새 보기). Three layers: 요약 (this file: header, 왜 움직였나 line, four tiles, 재무 경고,
// 내 기준과 맞는 정도, holding line, 내 메모) → tabs 실적 · 가치 · 배당 · 공시 (cotabs.jsx) → 자세히 (cotabs.jsx).
// Rules kept here:
// - Every tile phrase comes from a fixed rule in company.js on the numbers the tile shows (words and numbers can't drift).
// - Copy waiting for Jack's yes is null in src/copy/v2.js: the element is left out (tab bar: only when all five names
//   are approved). Nothing is shown with an unapproved word, and no number is shown without its label.
// - Each section says what its numbers are as of: the price date (KR pxDate · US usPxDate), the report year (fy), the
//   disc.json date. US per-share figures in $ first with 원 small (Jack's decision 7).
// - No 뱁이 anywhere on company screens (they all show numbers): the load-failure message here has no picture.
// - Unknown code: "이 종목의 데이터를 찾지 못했어요." (the old app's sentence), never an empty page.
// PC (v19.0d frame): one column of up to 720 px, the same content.
// v19.3e (v19.3 Part I, boards CoSummary2 · CoSummaryUS): each 요약 tile carries its small picture (coart.jsx) and the
// board's coloured edge; the "재무 경고 신호는 없어요" card lists one chip per check that ran and passed (never one for a
// check that did not run); a rise day reads as one ("…개가 올랐어요"); the holding card says "내 포트폴리오의 {x}%" when one
// portfolio holds the stock (가진 종목 넣기 portfolios count too); the US header lines wait behind cofmt.js US_HEAD2.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, TOPIC_ART } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { StatusChip, Segmented, BottomSheet, Amount, Button } from "../ui/components.jsx";
import { C, fill, nf, p1, mdText, priceText, todayKst, wonText } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, Note, CardPic, SIDE_W, tx, tap, useMode, useLayout } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { findCompany, groupOf, earnKr, earnUs, valueTile, divKr, divUs, riskTile, warnings, cardRanks, myCards, holdingsOf, RANK_CARDS,
  splitGuardCount, SPLIT_GUARD, divCheckCount, warnChips, warnKind, uncheckedCount } from "./company.js";
import { EarnBars, ValueScale, Coins, Waves } from "./coart.jsx";
import { pfRows, isImported, limitsOf } from "./pf.js";
import { limitPct } from "./pfview.jsx";
import { signedPct, eokText } from "./deckcalc.js";
import { useDaily } from "./today.jsx";
import { statusChips, HoldingRules, StatusLines } from "./daily.jsx";
import { peerGroup, keptCount } from "./track.js";
import { BIG_MOVE } from "./rules.js";
import { shownName } from "./legacy.js";
import { withNote, noteOf, NOTE_MAX } from "./store.js";
import { CO_TABS } from "./routes.js";
import { isCompany } from "./stocklist.js";
import { todayD1 } from "./engine.js";
import { EarnTab, ValueTab, DivTab, DiscTab, ValueMore, EarnMore } from "./cotabs.jsx";
import { icrOffShown, stmtNotWonFor, unitHeldFor, unitRowsBlank } from "./fix.js";
import { IcrOffNote, IcrOffLine, StmtCurNote, FcurNote, PbrZeroNote, UnitChkNote, NoStmtNote } from "./fixnote.jsx";
import { fcurRowsBlank, fcurBlank, fcurDyBlank, pbrZeroOf, pbrZeroRowsBlank } from "./fcur.js";
import { RecordButton, RecordFlow, companyFlow } from "./records.jsx";
import { decksFor } from "./records.js";
import { usOf, priceMd, priceDate, lineDate, closeLine, wonOfUsd, wonLineUsd, fxDateLine, US_HEAD2, timesText, pctText, yieldText, usGrowthText, riskBandText } from "./cofmt.js";

const T = () => C.co.tiles;
export const TOPIC_ICON = { earn: "trend-up", value: "tag", div: "coins", risk: "umbrella", disc: "file-text" };
const all = (...xs) => xs.every((x) => x != null && x !== "");
// The labels of the five tabs (US: no 공시 until v19.2). null when any name still waits for Jack (no tab bar then).
export function tabLabels(s, discShown) {
  const t = C.co.tabs;
  const ids = ["summary", "earn", "value", "div", ...(discShown ? ["disc"] : [])];
  const labels = ids.map((id) => [id, t[id]]);
  return labels.every(([, l]) => l) && C.co.tabsLabel ? labels : null;
}

// ---------------- tiles (Part B) ----------------
// -> [{ topic, label, phrase, number, rule, data }] for the tiles whose words are all approved (others left out).
export function tileViews(load, s) {
  const co = load.coByT.get(s.t) || null;
  const group = groupOf(load.data.stocks, s);
  const na = T().na;
  const out = [];
  // Each tile carries the date or report its number comes from (v19.1a review): 실적 · 배당 the 사업보고서 (fy), 가치 · 출렁임
  // the price date (PBR at today's close, beta through it). US: the US close date.
  const fy = co && Number.isInteger(co.fy) ? co.fy : Number.isInteger(s.fy) ? s.fy : null;
  const md = priceMd(load, s);
  const asOf = md ? fill(C.app.asOf, { md }) : null;
  const report = !usOf(s) && fy ? fill(C.app.reportYear, { year: fy }) : null;
  // KR 배당: the yield is that report's dividend per share over today's close (Jack, 2026-11-05), so its basis names both;
  // the year is the dps's own (divKr r.fy). A 배당 basis line only under a number (a payer with no trusted yield: phrase only).
  const basisOf = { earn: usOf(s) ? asOf : report, value: asOf, div: (r) => (usOf(s) ? asOf : r.fy != null ? fill(C.co.div.basisKr, { fy: r.fy }) : null), risk: asOf };
  // v19.3e (Part I, board CoSummary2): each tile also carries its small picture (coart.jsx), drawn from the same rule and
  // numbers as its phrase; none on 자료가 없어요 (na), and no coins on 배당이 없어요.
  const add = (topic, label, r, phrase, number, data, art = null) => {
    const b = typeof basisOf[topic] === "function" ? basisOf[topic](r) : basisOf[topic];
    if (all(label, phrase)) out.push({ topic, label, phrase, number, rule: r.rule, data, basis: r.rule === "na" || (topic === "div" && !number) ? null : b,
      art: r.rule === "na" ? null : art });
  };
  if (usOf(s)) {
    const r = earnUs(s);
    const number = usGrowthText(r.g);
    // The phrase reads one quarter against the same quarter a year before: no phrase without the number that says so.
    add("earn", T().label.earn, r, r.rule === "na" ? na : number ? T().earnUs[r.rule] : null, number, { g: r.g });
  } else {
    const r = earnKr(co);
    const number = r.pct != null && T().opChange ? fill(T().opChange, { pct: signedPct(r.pct) }) : r.amount != null && T().opAmount && eokText(r.amount) ? fill(T().opAmount, { x: eokText(r.amount) }) : null;
    add("earn", T().label.earn, r, r.rule === "na" ? na : T().earnKr[r.rule], number, { op: r.op }, { kind: "bars", op: r.op });
  }
  // US statements not in dollars (data.json fcur, #114 review): the 가치 and 배당 tiles stay, as "–" with their number's label
  // ("PBR –", "배당수익률 –") and no picture, date or verdict; Tiles puts them last and the reason line right under them.
  // A PBR that rounds to 0.00 (data.json pbrZero, Jack 2026-11-13): the 가치 tile the same way, rule "pbr0" and its own line.
  const blankTile = (topic, label, rule = "fcur") => out.push({ topic, label: T().label[topic], phrase: "–", number: `${label} –`, rule, data: {}, basis: null, art: null });
  if (fcurBlank(s) && T().label.value) blankTile("value", "PBR");
  else if (pbrZeroOf(s) && T().label.value) blankTile("value", "PBR", "pbr0");
  else {
    const r = valueTile(s, group);
    const number = r.med != null && T().pbr ? fill(T().pbr, { x: nf(r.pbr, 2), y: nf(r.med, 2) }) : r.pbr != null ? `PBR ${timesText(r.pbr, 2)}` : null;
    add("value", T().label.value, r, r.rule === "na" ? na : T().value[r.rule], number, { pbr: r.pbr, med: r.med, n: r.n },
      r.med != null ? { kind: "scale", pbr: r.pbr, med: r.med, ends: !!(number && T().pbr && number === fill(T().pbr, { x: nf(r.pbr, 2), y: nf(r.med, 2) })) } : null);
  }
  if (fcurDyBlank(s) && T().label.div && C.pick.receipt.yield) blankTile("div", C.pick.receipt.yield);
  else {
    const r = usOf(s) ? divUs(s) : divKr(s, co);
    const phrase = r.rule === "na" ? na : r.rule === "streak" ? fill(T().div.streak, { n: r.n }) : T().div[r.rule];
    const number = r.yieldPct != null ? `${C.pick.receipt.yield} ${yieldText(r.yieldPct)}` : null;
    add("div", T().label.div, r, phrase, number, { dps3: r.d3 || null, dps: r.dps ?? null, y: r.yieldPct, dpsok: r.dpsOk ? "1" : "" },
      divArt(r.rule));
  }
  {
    // v19.1b data: the beta band as the number ("코스피 1% → 평균 0.9~1.1%"); no band -> na. Older files: the phrase only
    // (no betaSE in the data), never a bare beta.
    const r = riskTile(s);
    const number = r.rule === "na" ? null : riskBandText(s, r);
    add("risk", T().label.risk, r, r.rule === "na" ? na : T().risk[r.rule], number,
      { beta: r.beta ?? null, lo: r.band ? r.band.lo : null, hi: r.band ? r.band.hi : null }, { kind: "waves", rule: r.rule });
  }
  return out;
}

// The 배당 tile's coins say no more than its phrase: rising stacks only for 늘렸어요 (streak · raised), equal stacks for
// 작년과 비슷하게 (steady: the years compared paid alike), one stack for a payer whose years are not compared (pays: the US,
// or Korea without the trend; noPrev: no record of last year), so no picture implies a history the data does not show.
// No picture for 줄였어요 (cut), 배당이 없어요 (none) or 자료가 없어요 (na).
export function divArt(rule) {
  if (rule === "streak" || rule === "raised") return { kind: "coins", shape: "rising" };
  if (rule === "steady") return { kind: "coins", shape: "even" };
  if (rule === "pays" || rule === "noPrev") return { kind: "coins", shape: "one" };
  return null;
}

// The tile's picture (coart.jsx). 출렁임's legend: 이 회사 (co.earn.mine) and 시장 (the same word as the 시장 tab).
export function TileArt({ art }) {
  if (!art) return null;
  if (art.kind === "bars") return <EarnBars op={art.op} />;
  if (art.kind === "scale") return <ValueScale pbr={art.pbr} med={art.med} ends={art.ends && T().scale ? T().scale : null} />;
  if (art.kind === "coins") return <Coins shape={art.shape} />;
  if (art.kind === "waves") return <Waves rule={art.rule} mine={C.co.earn.mine} market={C.app.tabs.market} />;
  return null;
}

function Tile({ v, onOpen }) {
  const body = (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name={TOPIC_ICON[v.topic]} size={32} tone={v.topic} />
        <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{v.label}</span>
      </div>
      <div data-ui-v2="tile-phrase" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3), lineHeight: 1.35 })}>{v.phrase}</div>
      <TileArt art={v.art} />
      {v.number && <div data-ui-v2="tile-number" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{v.number}</div>}
      {v.basis && <div data-ui-v2="tile-basis" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: 2 })}>{v.basis}</div>}
    </>
  );
  const data = Object.fromEntries(Object.entries(v.data || {}).map(([k, x]) => [`data-${k}`, x == null ? "" : Array.isArray(x) ? x.join(",") : String(x)]));
  // The board's coloured edge on the left of each tile (tokens.js TOPIC_ART: the topic's darker shade; 실적's is its light
  // tint #B9CDEB, never a blue: Jack, 2026-11-08).
  const edge = TOPIC_ART[v.topic] ? { boxShadow: `inset 4px 0 0 ${TOPIC_ART[v.topic].ink}` } : {};
  const style = { ...tap, display: "block", width: "100%", minHeight: SPACE(32), textAlign: "left", border: "none", background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(4), ...edge };
  return onOpen
    ? <button type="button" data-ui-v2="co-tile" data-topic={v.topic} data-rule={v.rule} {...data} onClick={onOpen} style={style}>{body}</button>
    : <div data-ui-v2="co-tile" data-topic={v.topic} data-rule={v.rule} {...data} style={{ ...style, cursor: "default" }}>{body}</div>;
}

// The interim split guard hides some Korean yields (company.js SPLIT_GUARD): say how many, once per data load (app.jsx
// calls this when the data arrives, so the count is in the console whichever screen opens first).
// v19.1b data: no guard; the exact check's own counts instead (payers whose yield could not be verified stay blank).
const guardLogged = new WeakSet();
export function logSplitGuard(load) {
  const stocks = load && load.status === "ok" && load.data ? load.data.stocks : null;
  if (!stocks || guardLogged.has(stocks)) return;
  guardLogged.add(stocks);
  const x = divCheckCount(stocks, load.coByT);
  if (x) {
    const line = `[v2] Korean dividends: exact split check (data.json divCheck) · same ${x.st.same} · adj ${x.st.adj} · nc ${x.st.nc} `
      + `· nd ${x.st.nd} · zero ${x.st.zero} · yield shown for ${x.shown} / ${x.payers} payers with a report year`;
    if (x.hidden) console.warn(`${line}; not verified (no yield, no 100-man-won line, no payout, left out of a plan's dividend): ${x.hidden}, e.g. ${x.examples.join(", ")}`);
    else console.info(line);
    return;
  }
  const g = splitGuardCount(stocks, load.coByT);
  if (g.hidden) console.warn(`[v2] dividend split guard: yield, 100-man-won line and payout hidden for ${g.hidden} / ${g.of} Korean payers `
    + `(today's yield ${SPLIT_GUARD}x the report's or more, or no report yield to check; until split-adjusted dividends). Largest: `
    + g.examples.map((x) => `${x.t} ${x.ratio == null ? "no report yield" : x.ratio + "x"}`).join(", "));
}

// Statements not in won (corp.json stmtCur): the 실적 and 가치 tiles could only say 자료가 없어요, which is not why their numbers
// are missing; they are left out and the currency line above the tiles says why (Jack's line, once). The same for a company
// whose statement numbers the unit check blanked (unitChk, Jack 2026-11-13): its line, once, above the tiles.
const AMOUNT_TILES = ["earn", "value"];
// US statements not in dollars (data.json fcur, #114 review): the 가치 and 배당 tiles show "–" with their label (tileViews
// rule "fcur"); they go last (실적 · 출렁임, then 가치 · 배당), so the reason line sits right under them, once. Keyed on the
// data: the same tiles while the currency's name waits for Jack, only without the line.
// The tiles in screen order: tiles held at "–" (rule fcur · pbr0) after the others, each group in its own order. (pure; tests)
export function orderTiles(views) {
  const held = (x) => x.rule === "fcur" || x.rule === "pbr0";
  return [...views.filter((x) => !held(x)), ...views.filter(held)];
}
function Tiles({ load, s, onTab, tabsOn }) {
  const cur = stmtNotWonFor(s, load.coByT.get(s.t) || null) || unitHeldFor(s, load.coByT.get(s.t) || null);
  const views = useMemo(() => orderTiles(tileViews(load, s).filter((x) => !(cur && AMOUNT_TILES.includes(x.topic)))), [load, s, cur]);
  if (!views.length) return <span data-ui-v2="co-tiles" data-pending="1" hidden />;
  const md = priceMd(load, s);
  const src = usOf(s) && C.why.srcPriceUs && md ? fill(C.why.srcPriceUs, { md }) : null;     // US: the source of every tile number
  const tabOf = { earn: "earn", value: "value", div: "div", risk: "value" };
  return (
    <section data-ui-v2="co-tiles" style={{ marginTop: SPACE(4) }}>
      {T().title && <h3 style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { margin: `0 ${SPACE(1)}px ${SPACE(2)}px` })}>{T().title}</h3>}
      {/* the unit check (unitChk): the 실적 · 가치 tiles have no numbers; the reason once, before them */}
      <UnitChkNote s={s} co={load.coByT.get(s.t) || null} style={{ margin: `0 ${SPACE(1)}px ${SPACE(2)}px` }} />
      {/* statements not in won (corp.json stmtCur): the 실적 · 가치 tiles have no numbers; the reason once, before them */}
      <StmtCurNote s={s} co={load.coByT.get(s.t) || null} style={{ margin: `0 ${SPACE(1)}px ${SPACE(2)}px` }} />
      {/* no statements at all (fix.js noStmtFor, Jack 2026-11-14): why 실적 · 가치 · 배당 say 자료가 없어요, once before them */}
      <NoStmtNote s={s} co={load.coByT.get(s.t) || null} style={{ margin: `0 ${SPACE(1)}px ${SPACE(2)}px` }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: SPACE(3) }}>
        {views.map((v) => <Tile key={v.topic} v={v} onOpen={tabsOn ? () => onTab(tabOf[v.topic]) : undefined} />)}
      </div>
      {/* US statements not in dollars (data.json fcur): the reason once, right under the 가치 · 배당 tiles showing – */}
      {views.some((v) => v.rule === "fcur") && <FcurNote s={s} style={{ margin: `${SPACE(2)}px ${SPACE(1)}px 0` }} />}
      {/* a PBR that rounds to 0.00 (data.json pbrZero): its own line, right under the 가치 tile showing – */}
      {views.some((v) => v.rule === "pbr0") && <PbrZeroNote s={s} style={{ margin: `${SPACE(2)}px ${SPACE(1)}px 0` }} />}
      {src && <div data-ui-v2="co-tiles-source" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(2), padding: `0 ${SPACE(1)}px` })}>{src}</div>}
    </section>
  );
}

// ---------------- header (Part B item 1) ----------------
function RangeBar({ s }) {
  const lo = s.lo, hi = s.hi, p = s.price;
  if (!all(C.co.lo, C.co.hi) || !(typeof lo === "number" && typeof hi === "number" && hi > lo && typeof p === "number")) return null;
  const x = Math.min(1, Math.max(0, (p - lo) / (hi - lo)));
  const f = (v) => priceText({ ...s, price: v });
  return (
    <div data-ui-v2="co-range" data-lo={lo} data-hi={hi} style={{ marginTop: SPACE(3) }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), ...tx(SIZE.xs, WEIGHT.regular, COLOR.text2) }}>
        <span>{fill(C.co.lo, { x: f(lo) })}</span><span>{fill(C.co.hi, { x: f(hi) })}</span>
      </div>
      <div aria-hidden="true" style={{ position: "relative", height: SPACE(2), marginTop: SPACE(1) }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 3, height: 2, background: COLOR.border, borderRadius: 2 }} />
        <div style={{ position: "absolute", left: `calc(${x * 100}% - 5px)`, top: -1, width: 10, height: 10, borderRadius: 999, background: COLOR.ink }} />
      </div>
    </div>
  );
}

function Header({ load, s }) {
  const d1 = todayD1(s);                   // v19.1c: none for a stock priced at an earlier close (its date is in closeLine)
  const won = usOf(s) ? wonOfUsd(load, s.price) : null;
  const ind = s.indName && typeof s.indName === "string" ? s.indName : null;
  return (
    <section data-ui-v2="co-head" data-t={s.t} data-cls={s.cls} style={{ marginTop: SPACE(2) }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <CoMark s={s} size={48} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 data-ui-v2="co-name" style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.25, letterSpacing: "-0.03em", overflowWrap: "anywhere" })}>{s.nk}</h2>
          <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>
            <span>{C.pick.market[s.cls]}</span>{ind && <><span>{" · "}</span><span>{ind}</span></>}{usOf(s) && <><span>{" · "}</span><span>{s.t}</span></>}
          </p>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(3) }}>
        <span data-ui-v2="co-price" style={tx(30, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.1, letterSpacing: "-0.02em" })}><Amount text={priceText(s)} /></span>
        {d1 != null && <span data-ui-v2="co-change" style={tx(SIZE.sm, WEIGHT.heavy, d1 < 0 ? COLOR.down : d1 > 0 ? COLOR.upOnPage : COLOR.text2)}>{signedPct(d1)}</span>}
        {closeLine(load, s) && <span data-ui-v2="co-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{closeLine(load, s)}</span>}
      </div>
      {won && <div data-ui-v2="co-won" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: 2 })}>{(US_HEAD2 && wonLineUsd(load, s.price)) || won}</div>}
      {/* The rate's own date (cofmt.fxDateLine): always without US_HEAD2; with it, whenever the rate is from another day than
          the price date in the header, so the won line never reads as that day's rate */}
      {won && fxDateLine(load, s) && <div data-ui-v2="co-fx" data-fx-date={load.data.fxDate} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{fxDateLine(load, s)}</div>}
      <RangeBar s={s} />
    </section>
  );
}

// ---------------- 왜 움직였나 line (Part B item 2): 2.0's big-move rule, for any stock ----------------
function MoveLine({ load, s, held, onWhy }) {
  const d1 = todayD1(s);
  if (d1 == null || Math.abs(d1) < BIG_MOVE) return null;
  const g = peerGroup(s, load.data.stocks);
  // v19.3e (Part I): a rise day reads as one ("{ind} 종목 {n}개 중 {k}개가 올랐어요", "업종이 다 같이 오른 날이에요"); a fall
  // day as before. Without the rise lines approved, the fall day's count line (k fell) as before.
  const up = d1 > 0 && !!(C.co.moveUp && C.co.moveUp.together && C.co.moveUp.body);
  const together = g.ok && (up ? g.togetherUp : g.together);
  const h = held.find((x) => x.x.bigMove) || null;
  return (
    <div data-ui-v2="co-move" data-together={together ? "1" : "0"} style={{ marginTop: SPACE(3), background: together ? COLOR.heroCalm : COLOR.surface, borderRadius: RADIUS.md,
      padding: `${SPACE(3)}px ${SPACE(4)}px`, display: "flex", alignItems: "center", gap: SPACE(3) }}>
      <Icon name={together ? "check-circle" : "info"} size={22} tone={together ? "ok" : "on"} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {together ? <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{(up ? C.co.moveUp.together : C.why.together).replace("\n", " ")}</div>
          : <StatusChip tone="neutral">{C.daily.bigMove}</StatusChip>}
        {g.ok && <div data-ui-v2="co-move-count" data-up={up ? "1" : "0"} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>
          {up ? fill(C.co.moveUp.body, { ind: s.indName, n: g.n, k: g.rose }) : fill(C.why.c1Body, { ind: s.indName, n: g.n, k: g.fell })}</div>}
      </div>
      {h && onWhy && (
        <button type="button" data-ui-v2="co-why" onClick={() => onWhy(h.deckId, s.t)}
          style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, display: "flex", alignItems: "center", gap: 2, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { whiteSpace: "nowrap" }) }}>
          {C.today.more}<Icon name="chevronRight" size={16} tone="on" />
        </button>
      )}
    </div>
  );
}

// ---------------- 재무 경고 (Part B item 4, Korea only) ----------------
export function warnText(f) {
  const W = C.co.warn;
  if (f.code === "cr") return W.cr ? fill(W.cr, { x: nf(Math.abs(f.x)) }) : null;                  // a ratio of assets: never negative
  // Jack, PR #68 (2026-11-07): an operating loss (ratio below 0, interest above 0) says so without a number
  if (f.code === "icr") return f.x < 0 || Object.is(f.x, -0) ? W.icrLoss || null : W.icr ? fill(W.icr, { x: nf(f.x, 2) }) : null;
  return W[f.code] || null;
}
function warnSource(w) {
  return [w.quarter && C.co.warn.quarter ? fill(C.co.warn.quarter, { y: w.quarter.y, q: w.quarter.q }) : null,
    w.fy ? fill(C.app.reportYear, { year: w.fy }) : null].filter(Boolean).join(" · ");
}
// v19.3e (Part I): the chips of the checks that ran and passed (company.warnChips), on the "없어요" card only.
function WarnChipGrid({ chips }) {
  const W = C.co.warn;
  if (!chips.length) return null;
  return (
    <div data-ui-v2="co-warn-chips" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: SPACE(1) + 2, marginTop: SPACE(3) }}>
      {chips.map((c) => (
        <span key={c} data-ui-v2="co-warn-chip" data-check={c} style={{ display: "flex", alignItems: "center", gap: SPACE(1) + 2, padding: `${SPACE(2)}px ${SPACE(2) + 2}px`,
          borderRadius: RADIUS.sm, background: COLOR.heroCalm, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { lineHeight: 1.35 }) }}>
          <Icon name="check-circle" size={18} tone="ok" />{W.chips[c]}
        </span>
      ))}
    </div>
  );
}
function Warnings({ load, s, wide }) {
  const [open, setOpen] = useState(false);
  const w = useMemo(() => warnings(s, load.coByT.get(s.t) || null), [load, s]);
  const W = C.co.warn;
  // 공시 단위 확인 (Jack, 2026-11-13): no 재무 경고 is computed from statements read in the wrong unit (corp.json flRan []); the line
  // where the card would be, never "경고 신호는 없어요"
  if (unitHeldFor(s, load.coByT.get(s.t) || null) && C.co.unitChk) {
    return (
      <Card data-ui-v2="co-warn-unit" style={{ display: "flex", gap: SPACE(3), alignItems: "center", padding: SPACE(4) }}>
        <IconChip name="info" size={32} tone="risk" />
        <UnitChkNote s={s} co={load.coByT.get(s.t) || null} style={{ flex: 1, minWidth: 0, marginTop: 0 }} />
      </Card>
    );
  }
  // 2026-11-08 (Jack; say-why audit rows 1 and 6): 이자보상배율 is switched off until the DART re-read (corp.json flWhy.icr
  // "off"). Under the list when a warning fired; when nothing can be claimed, the line alone where the card would be
  // (no '없어요' head: the existing rule allows "확인한 …" only for flWhy.icr "ie"). Goes by itself when flWhy.icr changes.
  const off = s.cls === "kr" && icrOffShown(load.coByT.get(s.t) || null);
  if (!w.flags.length) {
    // 2026-11-14 (Jack): no check could run (corp.json flRan []: no statements yet (KONEX, new listings), 우선주, statements
    // not in won (the currency line above the tiles says why)). Its own state, never '…없어요': "재무 경고 · 확인하지 못했어요"
    // with the approved words of the 재무 경고 chip (rank.warn) and of a rule that could not be checked (pfr.unknown), and under
    // them Jack's reason line (co.warn.noData). Not for funds (no statements to check) or a file without flRan (nothing known).
    if (warnKind(s, w) === "unchecked" && all(C.rank.warn, C.pfr.unknown)) {
      return (
        <Card data-ui-v2="co-warn-unchecked" style={{ display: "flex", gap: SPACE(3), alignItems: "center", padding: SPACE(4) }}>
          <IconChip name="info" size={32} tone="risk" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.rank.warn}</div>
            <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{C.pfr.unknown}</div>
            {/* Jack, 2026-11-14: the reason, under it (우선주 too) */}
            {W.noData && <div data-ui-v2="co-warn-nodata" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{W.noData}</div>}
          </div>
        </Card>
      );
    }
    if (!w.allRan && !w.partial && off && C.fix.icr) {
      // The line alone, no chips: v19.3e shows chips only when every check ran ("확인이 덜 돌면 카드도 칩도 없음"), and
      // 이자보상배율 did not run.
      return (
        <Card data-ui-v2="co-warn-off" style={{ display: "flex", gap: SPACE(3), alignItems: "center", padding: SPACE(4) }}>
          <IconChip name="info" size={32} tone="risk" />
          <IcrOffNote show style={{ flex: 1, minWidth: 0, marginTop: 0 }} />
        </Card>
      );
    }
    // Jack, 2026-11-14: some checks ran and found nothing while the rest had no input (기아: 자본잠식). The closest approved
    // line, "확인한 재무 경고 신호는 없어요", with the ✓ chips of the checks that ran and Jack's count line for the others
    // (co.warn.uncheckedN). Never the plain "…없어요" (that needs every check).
    const some = warnKind(s, w) === "some";            // some ran with nothing found, at least one ✓ chip to show (company.js)
    if (!w.allRan && !w.partial && !some) return null;  // no flag, no check known to have run or no ✓ to show: nothing is claimed
    // partial (Jack, PR #68 B7): 이자보상배율 alone could not be checked, for want of an interest line -> "확인한 …" + why
    const head = w.partial || some ? W.nonePartial : W.none;
    const subText = some ? null : w.partial ? W.noneSubNoIcr : (w.sub === "fin" && W.noneSubFin) || (w.sub === "holding" && W.noneSubHolding) || W.noneSub;
    if (!head || (!some && !subText)) return <span data-ui-v2="co-warn" data-pending="1" hidden />;
    // v19.3e (Part I): one chip per check that ran and passed (company.warnChips: flRan, no flag); a check that did not run
    // or does not apply (flNa) gets none, never a ✓.
    const chips = warnChips(w).filter((c) => W.chips && W.chips[c]);
    const cnt = uncheckedCount(w, off) && W.uncheckedN ? fill(W.uncheckedN, { k: uncheckedCount(w, off) }) : null;
    return (
      <Card data-ui-v2="co-warn" data-n="0" data-partial={w.partial ? "1" : some ? "some" : undefined} style={{ padding: SPACE(4) }}>
        <div style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start" }}>
          <IconChip name="shield-check" size={32} tone="risk" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{head}</div>
            {subText && <div data-ui-v2="co-warn-sub" data-sub={w.partial ? "noIcr" : w.sub || ""} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{subText}</div>}
            {/* Jack, 2026-11-14: how many checks could not run, under "확인한 …" (its own line, not PR #68's sub-line) */}
            {some && cnt && <div data-ui-v2="co-warn-count" data-k={uncheckedCount(w, off)} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{cnt}</div>}
            {warnSource(w) && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{warnSource(w)}</div>}
          </div>
        </div>
        <WarnChipGrid chips={chips} />
      </Card>
    );
  }
  const texts = w.flags.map(warnText);
  if (!W.count || texts.some((x) => !x)) return <span data-ui-v2="co-warn" data-pending="1" hidden />;
  // Jack, PR #68 (2026-11-07): under the 이자보상배율 warning, say when it used the cash-flow statement's interest paid
  const cfNote = (code) => code === "icr" && w.icrCf && W.icrCfNote ? W.icrCfNote : null;
  // 2026-11-14 (Jack): the count must not read as all four checks when one did not run. When 이자보상배율 alone could not run
  // for want of an interest line (warn.js icrIe: flWhy.icr "ie", the other three ran), the approved PR #68 line says which and
  // why, under the first warning and under the list.
  const noIcr = w.icrIe && W.noneSubNoIcr ? W.noneSubNoIcr : null;
  // Jack, 2026-11-14: any other check that could not run -> "4가지 중 {k}가지는 필요한 자료가 없어서 확인하지 못했어요." in the same
  // two places (never both lines: company.js uncheckedCount is 0 where noIcr goes or the off line explains it)
  const cnt = uncheckedCount(w, off) && W.uncheckedN ? fill(W.uncheckedN, { k: uncheckedCount(w, off) }) : null;
  return (
    <>
      <button type="button" data-ui-v2="co-warn" data-n={w.flags.length} onClick={() => setOpen(true)} aria-haspopup="dialog"
        style={{ ...tap, width: "100%", marginTop: SPACE(3), border: "none", textAlign: "left", background: COLOR.watchBg, borderRadius: RADIUS.md, padding: `${SPACE(3)}px ${SPACE(4)}px`,
          display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <Icon name="alert" size={22} tone="on" />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.watch, { display: "block" })}>{fill(W.count, { n: w.flags.length })}</span>
          <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.ink, { display: "block" })}>{texts[0]}</span>
          {cfNote(w.flags[0].code) && <span data-ui-v2="co-warn-cf" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2 })}>{cfNote(w.flags[0].code)}</span>}
          {noIcr && <span data-ui-v2="co-warn-noicr" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2 })}>{noIcr}</span>}
          {cnt && <span data-ui-v2="co-warn-count" data-k={uncheckedCount(w, off)} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2 })}>{cnt}</span>}
          <IcrOffLine show={off} />
        </span>
        <Icon name="chevronRight" size={18} tone="on" />
      </button>
      <BottomSheet open={open} title={fill(W.count, { n: w.flags.length })} onClose={() => setOpen(false)} closeLabel={C.app.close} shift={wide ? SIDE_W : 0}>
        <div data-ui-v2="co-warn-list">
          {W.sub && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{W.sub}</p>}
          {texts.map((x, i) => (
            <div key={w.flags[i].code} data-flag={w.flags[i].code} style={{ display: "flex", gap: SPACE(2), padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <Icon name="alert" size={18} tone="on" />
              <span style={{ minWidth: 0 }}>
                <span style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink, { display: "block" })}>{x}</span>
                {cfNote(w.flags[i].code) && <span data-ui-v2="co-warn-cf" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2 })}>{cfNote(w.flags[i].code)}</span>}
              </span>
            </div>
          ))}
          <IcrOffNote show={off} />
          {noIcr && <p data-ui-v2="co-warn-noicr" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{noIcr}</p>}
          {cnt && <p data-ui-v2="co-warn-count" data-k={uncheckedCount(w, off)} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{cnt}</p>}
          {warnSource(w) && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(2) })}>{warnSource(w)}</p>}
        </div>
      </BottomSheet>
    </>
  );
}

// ---------------- 내 기준과 맞는 정도 (Part B item 5) + the 8-card sheet (Part D) ----------------
export function rankText(r) {
  if (r.na) return C.build.s1.finNA;
  if (r.blank) return "–";
  if (r.side === "top") return fill(C.build.s1.topPct, { pct: r.pct });
  return C.co.fit.bottom ? fill(C.co.fit.bottom, { pct: r.pct }) : null;
}
function RankRow({ id, r, mine, basis }) {
  const text = rankText(r);
  if (text == null) return null;
  const card = C.build.cards[id];
  const pos = r.side === "top" ? 100 - r.pct : r.side === "bottom" ? r.pct : null;
  // v19.3b Part A: the 기준's picture on its tint chip in front of the row (the rows used no line icons before).
  return (
    <div data-ui-v2="rank-row" data-card={id} data-side={r.side || (r.na ? "na" : "blank")} data-pct={r.pct ?? ""}
      style={{ padding: `${SPACE(3)}px 0`, borderTop: `1px solid ${COLOR.line}`, display: "flex", alignItems: "center", gap: SPACE(3) }}>
      <CardPic id={id} size="fit" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
          <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{card.name}</span>
          {mine && C.co.fit.mine && <StatusChip tone="neutral">{C.co.fit.mine}</StatusChip>}
          {basis && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { minWidth: 0 })}>{card.basis}</span>}
          <span style={{ flex: 1 }} />
          <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { whiteSpace: "nowrap" })}>{text}</span>
        </div>
        {basis && pos != null && (
          <div aria-hidden="true" style={{ position: "relative", height: SPACE(2), marginTop: SPACE(2), background: COLOR.line, borderRadius: 999 }}>
            <div style={{ position: "absolute", left: `calc(${pos}% - 5px)`, top: -1, width: 10, height: 10, borderRadius: 999, background: COLOR.ink }} />
          </div>
        )}
      </div>
    </div>
  );
}
function Fit({ load, s, store, wide }) {
  const F = C.co.fit;
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState("market");
  const mine = useMemo(() => myCards(store.data.decks), [store.data.decks]);
  const mk = useMemo(() => cardRanks(s, load.data.stocks, "market"), [load, s]);
  const ind = useMemo(() => cardRanks(s, load.data.stocks, "ind"), [load, s]);
  if (!F.title || !mk.rows.length) return null;
  const byId = (res) => new Map(res.rows.map((r) => [r.id, r]));
  const m = byId(mk);
  const note = mine.picked ? F.picked : F.sample;
  const where = (res, sc) => (sc === "ind" ? (F.inInd ? fill(F.inInd, { ind: s.indName, n: nf(res.n) }) : null) : (F.inMarket ? fill(F.inMarket, { market: C.pick.market[s.cls], n: nf(res.n) }) : null));
  const indOk = !ind.few && ind.rows.length > 0 && all(F.market, F.ind);
  const cur = scope === "ind" && indOk ? ind : mk;
  const cm = byId(cur);
  const co = load.coByT.get(s.t) || null;           // 공시 단위 확인 (unitChk): the line under rows left blank by it
  return (
    <Card data-ui-v2="co-fit">
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name="clipboard-text" size={32} />
        <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{F.title}</h3>
      </div>
      <div style={{ marginTop: SPACE(2) }}>{mine.ids.map((id) => <RankRow key={id} id={id} r={m.get(id)} />)}</div>
      {/* a 가치 or 배당 row with no rank because its number was not computed (data.json fcur): the reason once, under the rows */}
      {fcurRowsBlank(s, mine.ids.map((id) => m.get(id))) && <FcurNote s={s} />}
      {pbrZeroRowsBlank(s, mine.ids.map((id) => m.get(id))) && <PbrZeroNote s={s} />}
      {unitRowsBlank(s, co, mine.ids.map((id) => m.get(id))) && <UnitChkNote s={s} co={co} />}
      {(note || where(mk, "market")) && <Note>{[note, where(mk, "market")].filter(Boolean).map((x, i) => <span key={i}>{i ? " " : ""}{x}</span>)}</Note>}
      {F.all && F.sheet && (
        <div style={{ marginTop: SPACE(3) }}>
          <Button kind="secondary" onClick={() => setOpen(true)}>{F.all}</Button>
        </div>
      )}
      <BottomSheet open={open} title={F.sheet || ""} onClose={() => setOpen(false)} closeLabel={C.app.close} shift={wide ? SIDE_W : 0}>
        <div data-ui-v2="co-fit-sheet" data-scope={cur === ind ? "ind" : "market"}>
          {indOk && <Segmented label={F.sheet} value={scope} onChange={setScope} options={[{ value: "market", label: F.market }, { value: "ind", label: F.ind }]} />}
          <div style={{ marginTop: SPACE(2) }}>{RANK_CARDS.map((id) => <RankRow key={id} id={id} r={cm.get(id)} mine={mine.picked && mine.ids.includes(id)} basis />)}</div>
          {fcurRowsBlank(s, cur.rows) && <FcurNote s={s} />}
          {pbrZeroRowsBlank(s, cur.rows) && <PbrZeroNote s={s} />}
          {unitRowsBlank(s, co, cur.rows) && <UnitChkNote s={s} co={co} />}
          {where(cur, cur === ind ? "ind" : "market") && <Note>{where(cur, cur === ind ? "ind" : "market")}</Note>}
          {lineDate(load, s) && <DateLine date={lineDate(load, s)} fresh={load.fresh} />}
        </div>
      </BottomSheet>
    </Card>
  );
}

// ---------------- holding line (Part B item 6) ----------------
// v19.3e (Part I, board CoSummary2): with one portfolio holding the stock, "내 포트폴리오의 {x}%" with its weight bar and
// value; with two or more, each keeps its name ("{name}의 {pct}") so they can be told apart. A portfolio made with 가진 종목
// 넣기 counts too (imported: its weight and value from pf.pfRows, no per-stock chips: it has no per-stock rules).
export function importedHeld(decks, ev, ctx, t) {
  if (!ev || !ev.ok) return [];
  const out = [];
  for (const d of decks || []) {
    if (!isImported(d)) continue;
    const v = pfRows(d, ctx);
    const r = v.rows.find((x) => x.t === t && !x.absent);
    if (r) out.push({ deckId: d.id, name: d.name, x: { t, w: v.ok ? r.w : null, value: r.value }, imported: true, deck: d });
  }
  return out;
}
// The share as the rest of the page shows it: a built portfolio as its 비중 규칙 line does ("지금 14.5%", one decimal); a
// 가진 종목 portfolio against its 한 종목 limit (pfview.limitPct: never reads as the limit when it broke it, as on 홈 and
// 포트폴리오). -> the number without "%".
export function holdShare(x, imported, deck) {
  if (imported) return limitPct(x.w, limitsOf(deck).stock);
  const r = Math.round(x.w * 1000) / 10;
  return p1(r === 0 ? 0 : r);
}
// "내 포트폴리오의 {x}%" only when the user has a single portfolio; otherwise each line names its portfolio ("{name}의 {pct}").
export function holdLine(h, single) {
  const { name, x, imported, deck } = h;
  if (x.w == null) return shownName(name);
  const v = holdShare(x, imported, deck);
  if (single && C.co.hold.mine) return fill(C.co.hold.mine, { x: v });
  return C.co.hold.weight ? fill(C.co.hold.weight, { name: shownName(name), pct: `${v}%` }) : shownName(name);
}
// action (v19.6a): the 기록 button, under the rows.
// onRemove (Jack 2026-11-13, J4): (deckId, t) opens 종목 바꾸기 of that portfolio with the stock's 빼기 sheet (the sold-out line)
function Holdings({ held, single, action = null, onRemove = null }) {
  if (!held.length) return action ? <Card data-ui-v2="co-held" data-empty="1" style={{ padding: `${SPACE(3)}px ${SPACE(4)}px` }}>{action}</Card> : null;
  return (
    <Card data-ui-v2="co-held" style={{ padding: `${SPACE(2)}px ${SPACE(4)}px` }}>
      {held.map(({ deckId, name, x, imported }) => {
        // a 0-share kept holding (v19.6a): no "규칙 n개가 모두 지켜지고 있어요" (its rules are not read for it; review N5)
        const k = imported || x.qty === 0 ? 0 : keptCount(x, { roe: !!C.plan.rules.roeLimit, op: !!C.plan.rules.opLimit });
        const chips = imported ? null : statusChips(x);
        const line = holdLine(held.find((h) => h.deckId === deckId), single);
        return (
          <div key={deckId} data-ui-v2="co-held-row" data-deck-id={deckId} data-status={x.status} data-kind={imported ? "imported" : undefined}
            style={{ padding: `${SPACE(2)}px 0`, borderTop: deckId === held[0].deckId ? "none" : `1px solid ${COLOR.line}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH }}>
              <IconChip name="deck" size={36} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span data-ui-v2="co-held-line" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block", wordBreak: "keep-all" })}>{line}</span>
                {x.w != null && (
                  <div aria-hidden="true" style={{ height: SPACE(1) + 2, background: COLOR.line, borderRadius: 999, marginTop: SPACE(1), overflow: "hidden" }}>
                    <div style={{ width: `${Math.min(100, Math.max(0, x.w * 100))}%`, height: "100%", background: COLOR.ink, borderRadius: 999 }} />
                  </div>
                )}
              </div>
              {x.value != null && x.value > 0 && <span data-ui-v2="co-held-value" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { whiteSpace: "nowrap" })}><Amount text={wonText(x.value)} /></span>}
            </div>
            {(chips || k > 0) && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE(1), marginTop: SPACE(1), paddingLeft: 36 + SPACE(3) }}>
                {chips || <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.ok)}>{fill(C.why.keptTitle, { n: k })}</span>}
              </div>
            )}
            {/* Jack, 2026-11-14: a sold-out kept holding that fails any of its rules shows them (the held stock's wording), never blank */}
            {!imported && x.qty === 0 && x.soldOutFails && (
              <div data-ui-v2="sold-out-fails" style={{ paddingLeft: 36 + SPACE(3) }}>
                <StatusLines x={x} names={new Map(((held.find((h) => h.deckId === deckId) || {}).deck || { holdings: [] }).holdings.map((y) => [y.t, y.nk]))} />
              </div>
            )}
            {/* Jack, 2026-11-13: this portfolio sold the stock out and kept it in the plan (0 shares, rules.SOLD_OUT_BANDS) */}
            {!imported && x.qty === 0 && C.daily.soldOutKept && (
              <p data-ui-v2="sold-out-kept" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1), paddingLeft: 36 + SPACE(3), wordBreak: "keep-all" })}>
                {onRemove ? <button type="button" data-ui-v2="sold-out-remove" onClick={() => onRemove(deckId, x.t)}
                  style={{ ...tap, border: "none", background: "none", padding: 0, textAlign: "left", minHeight: TOUCH, color: "inherit", font: "inherit",
                    textDecoration: "underline", textUnderlineOffset: 3 }}>{C.daily.soldOutKept}</button> : C.daily.soldOutKept}
              </p>
            )}
          </div>
        );
      })}
      {action && <div style={{ padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>{action}</div>}
    </Card>
  );
}

// ---------------- 내 메모 (Part E) ----------------
function Memo({ s, store, setStoreData, held }) {
  const M = C.co.memo;
  const note = noteOf(store.data, s.t);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [bad, setBad] = useState(false);
  if (!M.title) return null;
  const start = () => { setText(note ? note.text : ""); setBad(false); setEditing(true); };
  const save = () => {
    const next = withNote(store.data, s.t, text, todayKst(), Date.now());   // ts: the later edit wins when two tabs meet
    if (!next) { setBad(true); console.warn("[v2] note not saved for " + s.t); return; }
    setStoreData(next);
    setEditing(false);
  };
  const rules = held.filter((h) => h.x && Array.isArray(h.x.rules) && h.x.rules.length);
  return (
    <Card data-ui-v2="co-memo">
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name="note-pencil" size={32} />
        <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { flex: 1 })}>{M.title}</h3>
        {!editing && note && M.edit && store.writable && (
          <button type="button" data-ui-v2="co-memo-edit" onClick={start} style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { textDecoration: "underline", textUnderlineOffset: 3 }) }}>{M.edit}</button>
        )}
      </div>
      {!editing && note && (
        <>
          <p data-ui-v2="co-memo-text" style={tx(SIZE.sm, WEIGHT.regular, COLOR.ink, { marginTop: SPACE(2), whiteSpace: "pre-wrap" })}>{note.text}</p>
          {M.at && mdText(note.at) && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{fill(M.at, { md: mdText(note.at) })}</p>}
        </>
      )}
      {!editing && !note && M.empty && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{M.empty}</p>}
      {!editing && !note && M.add && store.writable && (
        <div style={{ marginTop: SPACE(3) }}><Button kind="secondary" onClick={start}>{M.add}</Button></div>
      )}
      {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
      {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
      {editing && (
        <div data-ui-v2="co-memo-form" style={{ marginTop: SPACE(2) }}>
          <textarea value={text} maxLength={NOTE_MAX} rows={4} aria-label={M.title} onChange={(e) => setText(e.target.value)} placeholder={M.empty || undefined}
            style={{ display: "block", width: "100%", border: `1px solid ${bad ? COLOR.watch : COLOR.border}`, borderRadius: RADIUS.sm, padding: SPACE(3), resize: "vertical",
              background: COLOR.surface, ...tx(SIZE.body, WEIGHT.regular, COLOR.ink) }} />
          <div style={{ display: "flex", gap: SPACE(2), marginTop: SPACE(2) }}>
            <div style={{ flex: 1 }}><Button kind="secondary" onClick={() => setEditing(false)}>{C.app.close}</Button></div>
            <div style={{ flex: 1 }}><Button onClick={save}>{C.plan.save}</Button></div>
          </div>
        </div>
      )}
      {rules.length > 0 && M.rules && (
        <div data-ui-v2="co-memo-rules" style={{ marginTop: SPACE(4) }}>
          <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{M.rules}</div>
          {M.rulesNote && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{M.rulesNote}</p>}
          {rules.map((h) => (
            <div key={h.deckId} data-deck-id={h.deckId}>
              {rules.length > 1 && <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(2) })}>{shownName(h.name)}</div>}
              <HoldingRules x={h.x} names={new Map((h.deck.holdings || []).map((y) => [y.t, y.nk]))} />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ---------------- the page ----------------
// A crash inside one tab shows the load-failure message there (no picture) and never stays after moving to another tab.
class TabBoundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(err) { console.warn("[v2] company tab error (" + this.props.name + "): " + ((err && err.message) || err)); }
  render() { return this.state.failed ? <LoadFail picture={false} /> : this.props.children; }
}

function CoTabs({ labels, value, onChange, stickyTop }) {
  return (
    <div role="tablist" aria-label={C.co.tabsLabel} data-ui-v2="co-tabs"
      style={{ position: "sticky", top: stickyTop, zIndex: 30, background: COLOR.page, display: "flex", margin: `${SPACE(3)}px -${SPACE(1)}px 0`, borderBottom: `1px solid ${COLOR.border}` }}>
      {labels.map(([id, label]) => {
        const on = id === value;
        return (
          <button key={id} type="button" role="tab" aria-selected={on ? "true" : "false"} data-tab={id} data-selected={on ? "1" : undefined} onClick={() => onChange(id)}
            style={{ ...tap, flex: 1, minHeight: TOUCH + SPACE(1), border: "none", background: "none", boxShadow: on ? `inset 0 -3px 0 ${COLOR.ink}` : "none",
              ...tx(SIZE.sm, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text3) }}>{label}</button>
        );
      })}
    </div>
  );
}

// loc: { code, ctab } from the address. disc: { status: idle · loading · ok · fail · none, data } (disc.json, live page only).
// nav: { setTab(ctab), more(ctab), back(), onWhy(deckId, t) }.
export function Company({ load, store, setStoreData, pad, code, ctab, disc, nav }) {
  const { preview } = useMode();
  const { wide } = useLayout();
  const ok = load.status === "ok";
  const s = ok ? findCompany(load, code) : null;
  const { ev, ctx } = useDaily(load, store);
  const held = useMemo(() => (s ? holdingsOf(ev, store.data.decks, s.t) : []), [ev, store.data.decks, s]);
  const heldAll = useMemo(() => (s ? [...held, ...importedHeld(store.data.decks, ev, ctx, s.t)] : []), [held, ev, ctx, store.data.decks, s]);   // v19.3e
  const backLabel = C.co.back || C.app.close;
  if (load.status === "loading") return <Page pad={pad}><AppBar onBack={nav.back} backLabel={backLabel} /></Page>;
  if (!ok) return <Page pad={pad}><AppBar onBack={nav.back} backLabel={backLabel} /><LoadFail picture={false} /><Footer /></Page>;
  if (!s) {
    // A fund (an address typed by hand: nothing in 2.0 links a fund here) is not "not found": it has no company page.
    const fund = ok && load.byT.get(code) && !isCompany(load.byT.get(code));
    return (
      <Page pad={pad}>
        <AppBar onBack={nav.back} backLabel={backLabel} />
        <Card data-ui-v2="co-not-found" data-fund={fund ? "1" : undefined}>
          <p style={tx(SIZE.body, WEIGHT.bold, COLOR.ink)}>{fund ? C.co.fundNote || C.stocks.krOnly : C.co.notFound}</p></Card>
        <Footer />
      </Page>
    );
  }
  // 자세히 screens exist once their title is approved (before that nothing links to them, and an address shows its tab).
  if (ctab === "value-more" && C.co.valueMore.title) return <ValueMore load={load} s={s} store={store} setStoreData={setStoreData} pad={pad} onBack={nav.back} backLabel={backLabel} />;
  if (ctab === "earn-more" && C.co.earn.moreTitle && !usOf(s)) return <EarnMore load={load} s={s} pad={pad} onBack={nav.back} backLabel={backLabel} />;
  const shown = ctab === "value-more" ? "value" : ctab === "earn-more" ? "earn" : ctab;
  return <CompanyPage load={load} s={s} store={store} setStoreData={setStoreData} pad={pad} ctab={shown} disc={disc} nav={nav} held={held} heldAll={heldAll}
    preview={preview} wide={wide} backLabel={backLabel} />;
}

function CompanyPage({ load, s, store, setStoreData, pad, ctab, disc, nav, held, heldAll, preview, wide, backLabel }) {
  const discShown = !usOf(s) && !preview && disc && disc.status !== "none";
  // v19.6a: 기록 when a portfolio has the stock (held, sold out, planned, or taken out: then 배당 받았어요 only); two or more
  // portfolios ask which one first (records.jsx)
  const [flow, setFlow] = useState(null);
  const canRecord = store.writable && !store.locked && decksFor(store.data, s.t).length > 0;
  const labels = tabLabels(s, discShown);
  // A tab opens from its address even while its name waits for Jack (no tab bar then, so nothing links to it); 공시 only
  // where it exists (Korea, live page).
  const tab = CO_TABS.includes(ctab) && (ctab !== "disc" || discShown) ? ctab : null;
  const stickyTop = wide ? TOUCH + SPACE(6) : preview ? TOUCH : 0;
  const setTab = (id) => nav.setTab(id === "summary" ? null : id);
  // Switching tabs keeps the page where it is (the router does not jump to the top between a company's tabs), but when
  // the tab bar is already stuck at the top, the new tab starts right under it.
  const mark = useRef(null);
  const seen = useRef(tab);
  useEffect(() => {
    if (seen.current === tab) return;
    seen.current = tab;
    const el = mark.current;
    try {
      const top = el ? el.getBoundingClientRect().top + window.scrollY - stickyTop : null;
      if (top != null && window.scrollY > top) window.scrollTo(0, top);
    } catch (e) { /* ignore */ }
  }, [tab]);
  return (
    <>
    <Page pad={pad}>
      <AppBar onBack={nav.back} backLabel={backLabel} />
      <div data-ui-v2="company" data-t={s.t} data-cls={s.cls} data-tab={tab || "summary"}>
        <Header load={load} s={s} />
        {load.fresh && load.fresh.stale && lineDate(load, s) && <DateLine date={lineDate(load, s)} fresh={load.fresh} />}
        <MoveLine load={load} s={s} held={held} onWhy={nav.onWhy} />
        <div ref={mark} aria-hidden="true" />
        {labels ? <CoTabs labels={labels} value={tab || "summary"} onChange={setTab} stickyTop={stickyTop} /> : <span data-ui-v2="co-tabs" data-pending="1" hidden />}
        <TabBoundary key={tab || "summary"} name={tab || "summary"}>
        {!tab && (
          <div data-ui-v2="co-summary">
            <Tiles load={load} s={s} onTab={setTab} tabsOn={!!labels} />
            <Warnings load={load} s={s} wide={wide} />
            <Fit load={load} s={s} store={store} wide={wide} />
            <Holdings held={heldAll} single={store.data.decks.length === 1}
              action={canRecord ? <div data-ui-v2="co-record"><RecordButton name={s.nk} onClick={() => setFlow(companyFlow(store.data, s.t, s.nk))} /></div> : null}
              onRemove={nav.removeFrom && store.writable && !store.locked ? nav.removeFrom : null} />
            <Memo s={s} store={store} setStoreData={setStoreData} held={held} />
          </div>
        )}
        {tab === "earn" && <EarnTab load={load} s={s} onMore={() => nav.more("earn-more")} />}
        {tab === "value" && <ValueTab load={load} s={s} store={store} onMore={() => nav.more("value-more")} />}
        {tab === "div" && <DivTab load={load} s={s} />}
        {tab === "disc" && <DiscTab load={load} s={s} disc={disc} />}
        </TabBoundary>
      </div>
      <Footer />
    </Page>
    {/* outside Page: its wrapper changes at the PC width, and a half-typed record must survive that */}
    <RecordFlow flow={flow} setFlow={setFlow} load={load} store={store} setStoreData={setStoreData} />
    </>
  );
}
