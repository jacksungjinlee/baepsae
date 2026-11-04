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
import React, { useEffect, useMemo, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { StatusChip, Segmented, BottomSheet, Amount, Button } from "../ui/components.jsx";
import { C, fill, nf, p1, mdText, priceText, todayKst, wonText } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, Note, SIDE_W, tx, tap, useMode, useLayout } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { findCompany, groupOf, earnKr, earnUs, valueTile, divKr, divUs, riskTile, warnings, cardRanks, myCards, holdingsOf, RANK_CARDS } from "./company.js";
import { signedPct, eokText } from "./deckcalc.js";
import { useDaily } from "./today.jsx";
import { statusChips, HoldingRules } from "./daily.jsx";
import { peerGroup, keptCount } from "./track.js";
import { BIG_MOVE } from "./rules.js";
import { shownName } from "./legacy.js";
import { withNote, noteOf, NOTE_MAX } from "./store.js";
import { CO_TABS } from "./routes.js";
import { EarnTab, ValueTab, DivTab, DiscTab, ValueMore, EarnMore } from "./cotabs.jsx";
import { usOf, priceMd, closeLine, wonOfUsd, timesText, pctText } from "./cofmt.js";

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
  const add = (topic, label, r, phrase, number, data) => { if (all(label, phrase)) out.push({ topic, label, phrase, number, rule: r.rule, data }); };
  if (usOf(s)) {
    const r = earnUs(s);
    add("earn", T().label.earn, r, r.rule === "na" ? na : T().earnUs[r.rule], r.g != null && C.pick.receipt.growthUs ? `${C.pick.receipt.growthUs} ${signedPct(r.g)}` : null, { g: r.g });
  } else {
    const r = earnKr(co);
    const number = r.pct != null && T().opChange ? fill(T().opChange, { pct: signedPct(r.pct) }) : r.amount != null && T().opAmount && eokText(r.amount) ? fill(T().opAmount, { x: eokText(r.amount) }) : null;
    add("earn", T().label.earn, r, r.rule === "na" ? na : T().earnKr[r.rule], number, { op: r.op });
  }
  {
    const r = valueTile(s, group);
    const number = r.med != null && T().pbr ? fill(T().pbr, { x: nf(r.pbr, 2), y: nf(r.med, 2) }) : r.pbr != null ? `PBR ${timesText(r.pbr, 2)}` : null;
    add("value", T().label.value, r, r.rule === "na" ? na : T().value[r.rule], number, { pbr: r.pbr, med: r.med, n: r.n });
  }
  {
    const r = usOf(s) ? divUs(s) : divKr(s, co);
    const phrase = r.rule === "na" ? na : r.rule === "streak" ? fill(T().div.streak, { n: r.n }) : T().div[r.rule];
    add("div", T().label.div, r, phrase, r.yieldPct != null ? `${C.pick.receipt.yield} ${pctText(r.yieldPct)}` : null, { dps3: r.d3 || null, dps: r.dps ?? null, y: r.yieldPct });
  }
  {
    const r = riskTile(s);
    add("risk", T().label.risk, r, r.rule === "na" ? na : T().risk[r.rule], null, { beta: r.beta ?? null });     // no bare beta (no band yet)
  }
  return out;
}

function Tile({ v, onOpen }) {
  const body = (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name={TOPIC_ICON[v.topic]} size={32} tone={v.topic} />
        <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{v.label}</span>
      </div>
      <div data-ui-v2="tile-phrase" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3), lineHeight: 1.35 })}>{v.phrase}</div>
      {v.number && <div data-ui-v2="tile-number" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{v.number}</div>}
    </>
  );
  const data = Object.fromEntries(Object.entries(v.data || {}).map(([k, x]) => [`data-${k}`, x == null ? "" : Array.isArray(x) ? x.join(",") : String(x)]));
  const style = { ...tap, display: "block", width: "100%", minHeight: SPACE(32), textAlign: "left", border: "none", background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(4) };
  return onOpen
    ? <button type="button" data-ui-v2="co-tile" data-topic={v.topic} data-rule={v.rule} {...data} onClick={onOpen} style={style}>{body}</button>
    : <div data-ui-v2="co-tile" data-topic={v.topic} data-rule={v.rule} {...data} style={{ ...style, cursor: "default" }}>{body}</div>;
}

function Tiles({ load, s, onTab, tabsOn }) {
  const views = useMemo(() => tileViews(load, s), [load, s]);
  if (!views.length) return <span data-ui-v2="co-tiles" data-pending="1" hidden />;
  const co = load.coByT.get(s.t) || null;
  const fy = co && Number.isInteger(co.fy) ? co.fy : null;
  const md = priceMd(load, s);
  const src = usOf(s) ? (C.why.srcPriceUs && md ? fill(C.why.srcPriceUs, { md }) : null)
    : [fy ? fill(C.app.reportYear, { year: fy }) : null, md ? fill(C.why.close, { md }) : null].filter(Boolean).join(" · ");
  const tabOf = { earn: "earn", value: "value", div: "div", risk: "value" };
  return (
    <section data-ui-v2="co-tiles" style={{ marginTop: SPACE(4) }}>
      {T().title && <h3 style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { margin: `0 ${SPACE(1)}px ${SPACE(2)}px` })}>{T().title}</h3>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: SPACE(3) }}>
        {views.map((v) => <Tile key={v.topic} v={v} onOpen={tabsOn ? () => onTab(tabOf[v.topic]) : undefined} />)}
      </div>
      {src && <div data-ui-v2="co-tiles-source" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(2), padding: `0 ${SPACE(1)}px` })}>{src}</div>}
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
      <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), ...tx(SIZE.xxs, WEIGHT.regular, COLOR.text2) }}>
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
  const d1 = typeof s.d1 === "number" && Number.isFinite(s.d1) ? s.d1 : null;
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
      {won && <div data-ui-v2="co-won" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: 2 })}>{won}</div>}
      {won && C.co.fxWon && mdText(load.data.fxDate) && (
        <div data-ui-v2="co-fx" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{fill(C.co.fxWon, { md: mdText(load.data.fxDate), fx: nf(Math.round(load.data.fx * 10) / 10, 1) })}</div>
      )}
      <RangeBar s={s} />
    </section>
  );
}

// ---------------- 왜 움직였나 line (Part B item 2): 2.0's big-move rule, for any stock ----------------
function MoveLine({ load, s, held, onWhy }) {
  const d1 = typeof s.d1 === "number" && Number.isFinite(s.d1) ? s.d1 : null;
  if (d1 == null || Math.abs(d1) < BIG_MOVE) return null;
  const g = peerGroup(s, load.data.stocks);
  const together = g.ok && g.together;
  const h = held.find((x) => x.x.bigMove) || null;
  return (
    <div data-ui-v2="co-move" data-together={together ? "1" : "0"} style={{ marginTop: SPACE(3), background: together ? COLOR.heroCalm : COLOR.surface, borderRadius: RADIUS.md,
      padding: `${SPACE(3)}px ${SPACE(4)}px`, display: "flex", alignItems: "center", gap: SPACE(3) }}>
      <Icon name={together ? "check-circle" : "info"} size={22} tone={together ? "ok" : "on"} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {together ? <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.why.together.replace("\n", " ")}</div>
          : <StatusChip tone="neutral">{C.daily.bigMove}</StatusChip>}
        {g.ok && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{fill(C.why.c1Body, { ind: s.indName, n: g.n, k: g.fell })}</div>}
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
  if (f.code === "cr") return W.cr ? fill(W.cr, { x: nf(f.x) }) : null;
  if (f.code === "icr") return W.icr ? fill(W.icr, { x: nf(f.x, 2) }) : null;
  return W[f.code] || null;
}
function warnSource(w) {
  return [w.quarter && C.co.warn.quarter ? fill(C.co.warn.quarter, { y: w.quarter.y, q: w.quarter.q }) : null,
    w.fy ? fill(C.app.reportYear, { year: w.fy }) : null].filter(Boolean).join(" · ");
}
function Warnings({ load, s, wide }) {
  const [open, setOpen] = useState(false);
  const w = useMemo(() => warnings(s, load.coByT.get(s.t) || null), [load, s]);
  const W = C.co.warn;
  if (!w.ran) return null;                     // US, or the checks could not run: nothing is claimed
  if (!w.flags.length) {
    if (!all(W.none, W.noneSub)) return <span data-ui-v2="co-warn" data-pending="1" hidden />;
    return (
      <Card data-ui-v2="co-warn" data-n="0" style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start", padding: SPACE(4) }}>
        <IconChip name="shield-check" size={32} tone="risk" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{W.none}</div>
          <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2 })}>{W.noneSub}</div>
          {warnSource(w) && <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{warnSource(w)}</div>}
        </div>
      </Card>
    );
  }
  const texts = w.flags.map(warnText);
  if (!W.count || texts.some((x) => !x)) return <span data-ui-v2="co-warn" data-pending="1" hidden />;
  return (
    <>
      <button type="button" data-ui-v2="co-warn" data-n={w.flags.length} onClick={() => setOpen(true)} aria-haspopup="dialog"
        style={{ ...tap, width: "100%", marginTop: SPACE(3), border: "none", textAlign: "left", background: COLOR.watchBg, borderRadius: RADIUS.md, padding: `${SPACE(3)}px ${SPACE(4)}px`,
          display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <Icon name="alert" size={22} tone="on" />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.watch, { display: "block" })}>{fill(W.count, { n: w.flags.length })}</span>
          <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.ink, { display: "block" })}>{texts[0]}</span>
        </span>
        <Icon name="chevronRight" size={18} tone="on" />
      </button>
      <BottomSheet open={open} title={fill(W.count, { n: w.flags.length })} onClose={() => setOpen(false)} closeLabel={C.app.close} shift={wide ? SIDE_W : 0}>
        <div data-ui-v2="co-warn-list">
          {W.sub && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{W.sub}</p>}
          {texts.map((x, i) => (
            <div key={w.flags[i].code} data-flag={w.flags[i].code} style={{ display: "flex", gap: SPACE(2), padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <Icon name="alert" size={18} tone="on" />
              <span style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink)}>{x}</span>
            </div>
          ))}
          {warnSource(w) && <p style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(2) })}>{warnSource(w)}</p>}
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
  return (
    <div data-ui-v2="rank-row" data-card={id} data-side={r.side || (r.na ? "na" : "blank")} data-pct={r.pct ?? ""} style={{ padding: `${SPACE(3)}px 0`, borderTop: `1px solid ${COLOR.line}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{card.name}</span>
        {mine && C.co.fit.mine && <StatusChip tone="neutral">{C.co.fit.mine}</StatusChip>}
        {basis && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { minWidth: 0 })}>{card.basis}</span>}
        <span style={{ flex: 1 }} />
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { whiteSpace: "nowrap" })}>{text}</span>
      </div>
      {basis && pos != null && (
        <div aria-hidden="true" style={{ position: "relative", height: SPACE(2), marginTop: SPACE(2), background: COLOR.line, borderRadius: 999 }}>
          <div style={{ position: "absolute", left: `calc(${pos}% - 5px)`, top: -1, width: 10, height: 10, borderRadius: 999, background: COLOR.ink }} />
        </div>
      )}
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
  return (
    <Card data-ui-v2="co-fit">
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name="clipboard-text" size={32} />
        <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{F.title}</h3>
      </div>
      <div style={{ marginTop: SPACE(2) }}>{mine.ids.map((id) => <RankRow key={id} id={id} r={m.get(id)} />)}</div>
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
          {where(cur, cur === ind ? "ind" : "market") && <Note>{where(cur, cur === ind ? "ind" : "market")}</Note>}
          <DateLine date={load.data.pxDate} fresh={load.fresh} />
        </div>
      </BottomSheet>
    </Card>
  );
}

// ---------------- holding line (Part B item 6) ----------------
function Holdings({ held }) {
  if (!held.length) return null;
  return (
    <Card data-ui-v2="co-held" style={{ padding: `${SPACE(2)}px ${SPACE(4)}px` }}>
      {held.map(({ deckId, name, x }) => {
        const k = keptCount(x, { roe: !!C.plan.rules.roeLimit, op: !!C.plan.rules.opLimit });
        const chips = statusChips(x);
        const line = x.w != null && C.co.hold.weight ? fill(C.co.hold.weight, { name: shownName(name), pct: pctText(x.w * 100) }) : shownName(name);
        return (
          <div key={deckId} data-ui-v2="co-held-row" data-deck-id={deckId} data-status={x.status}
            style={{ display: "flex", alignItems: "center", gap: SPACE(2), flexWrap: "wrap", minHeight: TOUCH, padding: `${SPACE(1)}px 0` }}>
            <Icon name="deck" size={20} tone="on" />
            <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0 })}>{line}</span>
            {chips || (k > 0 ? <span style={tx(SIZE.xxs, WEIGHT.semi, COLOR.ok)}>{fill(C.why.keptTitle, { n: k })}</span> : null)}
          </div>
        );
      })}
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
    const next = withNote(store.data, s.t, text, todayKst());
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
          {M.at && mdText(note.at) && <p style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{fill(M.at, { md: mdText(note.at) })}</p>}
        </>
      )}
      {!editing && !note && M.empty && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{M.empty}</p>}
      {!editing && !note && M.add && store.writable && (
        <div style={{ marginTop: SPACE(3) }}><Button kind="secondary" onClick={start}>{M.add}</Button></div>
      )}
      {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
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
  const { ev } = useDaily(load, store);
  const held = useMemo(() => (s ? holdingsOf(ev, store.data.decks, s.t) : []), [ev, store.data.decks, s]);
  const backLabel = C.co.back || C.app.close;
  if (load.status === "loading") return <Page pad={pad}><AppBar onBack={nav.back} backLabel={backLabel} /></Page>;
  if (!ok) return <Page pad={pad}><AppBar onBack={nav.back} backLabel={backLabel} /><LoadFail picture={false} /><Footer /></Page>;
  if (!s) {
    return (
      <Page pad={pad}>
        <AppBar onBack={nav.back} backLabel={backLabel} />
        <Card data-ui-v2="co-not-found"><p style={tx(SIZE.body, WEIGHT.bold, COLOR.ink)}>{C.co.notFound}</p></Card>
        <Footer />
      </Page>
    );
  }
  // 자세히 screens exist once their title is approved (before that nothing links to them, and an address shows its tab).
  if (ctab === "value-more" && C.co.valueMore.title) return <ValueMore load={load} s={s} store={store} setStoreData={setStoreData} pad={pad} onBack={nav.back} backLabel={backLabel} />;
  if (ctab === "earn-more" && C.co.earn.moreTitle && !usOf(s)) return <EarnMore load={load} s={s} pad={pad} onBack={nav.back} backLabel={backLabel} />;
  const shown = ctab === "value-more" ? "value" : ctab === "earn-more" ? "earn" : ctab;
  return <CompanyPage load={load} s={s} store={store} setStoreData={setStoreData} pad={pad} ctab={shown} disc={disc} nav={nav} held={held}
    preview={preview} wide={wide} backLabel={backLabel} />;
}

function CompanyPage({ load, s, store, setStoreData, pad, ctab, disc, nav, held, preview, wide, backLabel }) {
  const discShown = !usOf(s) && !preview && disc && disc.status !== "none";
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
    <Page pad={pad}>
      <AppBar onBack={nav.back} backLabel={backLabel} />
      <div data-ui-v2="company" data-t={s.t} data-cls={s.cls} data-tab={tab || "summary"}>
        <Header load={load} s={s} />
        {load.fresh && load.fresh.stale && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        <MoveLine load={load} s={s} held={held} onWhy={nav.onWhy} />
        <div ref={mark} aria-hidden="true" />
        {labels ? <CoTabs labels={labels} value={tab || "summary"} onChange={setTab} stickyTop={stickyTop} /> : <span data-ui-v2="co-tabs" data-pending="1" hidden />}
        <TabBoundary key={tab || "summary"} name={tab || "summary"}>
        {!tab && (
          <div data-ui-v2="co-summary">
            <Tiles load={load} s={s} onTab={setTab} tabsOn={!!labels} />
            <Warnings load={load} s={s} wide={wide} />
            <Fit load={load} s={s} store={store} wide={wide} />
            <Holdings held={held} />
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
  );
}
