// ================= 2.0: 관심 종목 screens (v19.6c, docs/tasks/v19.6-records-alerts-dark.md Part C, board Watch2) =================
// WatchScreen   #stocks/watch: "관심 종목 · + 추가", the sub line, one card per watched stock (mark, name, "price · change", the
//               condition chips, the bell that opens the condition sheet) and the bottom line. Met (fresh data): the chip turns
//               green with a check; blank: "정보 없음" and, under the card, the company page's own line for why it is blank;
//               stale data: the values beside the stale date line, never a check. No 뱁이 (numbers); the empty state is its line.
// WatchSection  the 종목 tab's 관심 종목 section (at the top, only when the list is not empty) with 전체 보기 ›.
// WatchButton   the company page: 관심 종목에 추가 / 관심 종목에서 빼기 (and the 30-stock line when the list is full).
// CondSheet     the conditions of one stock (no board: the sheet's labels wait for Jack, the approved 가격 · PBR · 배당수익률 meanwhile).
// WatchHitRows  홈's 오늘 볼 것: "{name} · 관심 종목 조건", the hit line and the price date (watch.js watchHits).
// Colours: the shared tokens only (dark mode covers the screen). Icons: Phosphor duotone, the table's tones.
import React, { useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { Button, BottomSheet } from "../ui/components.jsx";
import { C, fill, mdText, todayKst } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, Note, OwnCloseNote, tx, tap, useNav, useLayout, SIDE_W } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { isCompany, ownCloses } from "./stocklist.js";
import { todayD1 } from "./engine.js";
import { signedPct } from "./deckcalc.js";
import { closeLine } from "./cofmt.js";
import { DayNote, FcurNote, PbrZeroNote, FgnCutNote, UnitChkNote, StmtCurNote, NoStmtNote, PrefNote, prefText } from "./fixnote.jsx";
import { fcurBlank, fcurDyBlank, pbrZeroOf, fgnBlank } from "./fcur.js";
import { unitHeldFor, stmtNotWonFor, noStmtFor } from "./fix.js";
import { divShareHidden } from "./company.js";
import { WATCH_MAX, WATCH_KINDS, WATCH_DEC, okWatchValue, watchOf, watchOrder, withWatchAdd, withWatchRemove, withWatchConds } from "./store.js";
import { watchFresh, condState, condsOf, condText, nowValue, hitText, watchValue } from "./watch.js";

const W = () => C.watch;
const usOf = (s) => !!s && s.cls === "us";
const canWrite = (store) => !!(store && store.writable && !store.locked);
// "{name} · 관심 종목 조건" (Appendix 1's 오늘 볼 것 title): the condition sheet's title and its bell button's name too
export const hitTitle = (name) => `${name} · ${W().hitKind}`;

// ---------------- one chip ----------------
// st: watch.js condState. "{condition} · 지금 {now}" (met: green with a check) or "{condition} · 정보 없음".
function CondChip({ st, us }) {
  const met = st.state === "met";
  const label = condText(st.k, st.v, us);
  const tail = st.val == null ? W().blank : fill(W().now, { now: nowValue(st.k, st.val, us) });
  return (
    <span data-ui-v2="watch-chip" data-k={st.k} data-state={st.state} data-v={st.v} data-val={st.val == null ? "" : st.val}
      style={{ display: "inline-flex", alignItems: "center", flexWrap: "wrap", gap: SPACE(1) + 2, padding: `${SPACE(1) + 1}px ${SPACE(2) + 1}px`, borderRadius: RADIUS.sm + 2,
        background: met ? COLOR.okBg : COLOR.select, ...tx(SIZE.xs, WEIGHT.bold, met ? COLOR.ok : COLOR.ink, { lineHeight: 1.35 }) }}>
      {met && <Icon name="check-circle" size={14} tone="ok" />}
      <span>{label}</span>
      <span style={{ fontWeight: WEIGHT.semi, color: COLOR.text3 }}>{"· "}{tail}</span>
    </span>
  );
}

// The company page's own line for a blank value, once per card (the same pieces the company page uses).
function BlankWhy({ s, co, kinds }) {
  if (!s || !kinds.length) return null;
  const pbr = kinds.includes("pbrBelow"), dy = kinds.includes("dyAtLeast");
  const style = { marginTop: SPACE(2) };
  const out = [];
  if (prefText(s)) out.push(<PrefNote key="pref" s={s} style={style} />);
  else {
    if ((pbr && fcurBlank(s)) || (dy && fcurDyBlank(s))) out.push(<FcurNote key="fcur" s={s} style={style} />);
    if (pbr && pbrZeroOf(s)) out.push(<PbrZeroNote key="pbr0" s={s} style={style} />);
    const fg = [...(pbr && fgnBlank(s, "pbr") ? ["pbr"] : []), ...(dy && fgnBlank(s, "dy") ? ["dy"] : [])];
    if (fg.length) out.push(<FgnCutNote key="fgn" s={s} fields={fg} style={style} />);
    if (pbr && unitHeldFor(s, co)) out.push(<UnitChkNote key="unit" s={s} co={co} style={style} />);
    else if (pbr && stmtNotWonFor(s, co)) out.push(<StmtCurNote key="cur" s={s} co={co} style={style} />);
    else if (pbr && noStmtFor(s, co)) out.push(<NoStmtNote key="nostmt" s={s} co={co} style={style} />);
    if (dy && !usOf(s) && divShareHidden(s, co) && C.co.div.shareHidden) out.push(<Note key="divh" data-ui-v2="div-share-hidden" style={style}>{C.co.div.shareHidden}</Note>);
  }
  return out.length ? <>{out}</> : null;
}

// ---------------- one watched stock ----------------
function WatchCard({ t, e, load, fresh, onCond, canEdit }) {
  const { openStock } = useNav();
  const ok = load.status === "ok";
  const s = ok ? load.byT.get(t) || null : null;
  const name = (s && s.nk) || (e && e.nk) || t;
  const us = s ? usOf(s) : !/^\d/.test(t);
  const sts = condsOf(e).map((c) => condState(load, s, c, fresh));
  const d1 = s ? todayD1(s) : null;
  const price = s && watchValue(s, "pxBelow") != null ? nowValue("pxBelow", watchValue(s, "pxBelow"), us) : null;
  const open = s && openStock && isCompany(s) ? () => openStock(t) : null;
  const co = ok && s ? load.coByT.get(t) || null : null;
  const head = (
    <>
      <CoMark t={t} name={name} size={40} />
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{name}</span>
        {price && (
          <span data-ui-v2="watch-price" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>
            <span>{price}</span>{d1 != null && <><span>{" · "}</span><span>{signedPct(d1)}</span></>}
          </span>
        )}
      </span>
    </>
  );
  return (
    <section data-ui-v2="watch-card" data-t={t} data-missing={s ? undefined : "1"}
      style={{ marginTop: SPACE(2) + 2, background: COLOR.surface, borderRadius: RADIUS.lg, padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        {open
          ? <button type="button" data-ui-v2="watch-open" onClick={open} style={{ ...tap, flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: SPACE(3), border: "none",
            background: "none", padding: 0, textAlign: "left", minHeight: TOUCH }}>{head}</button>
          : <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH }}>{head}</div>}
        {canEdit && (
          <button type="button" data-ui-v2="watch-bell" aria-label={hitTitle(name)} aria-haspopup="dialog" onClick={() => onCond(t, name, s)}
            style={{ ...tap, width: TOUCH, height: TOUCH, flexShrink: 0, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center",
              marginRight: -SPACE(2) }}>
            <Icon name="bell" size={24} tone="on" />
          </button>
        )}
      </div>
      {s && <DayNote s={s} md={mdText(load.data.pxDate)} style={{ marginTop: SPACE(1) }} />}
      {sts.length > 0 && (
        <div data-ui-v2="watch-chips" style={{ marginTop: SPACE(2) + 2, display: "flex", flexWrap: "wrap", gap: SPACE(1) + 2 }}>
          {sts.map((st) => <CondChip key={st.k} st={st} us={us} />)}
        </div>
      )}
      <BlankWhy s={s} co={co} kinds={sts.filter((x) => x.state === "blank").map((x) => x.k)} />
    </section>
  );
}

// ---------------- the condition sheet ----------------
// Labels: the proposals (C.watch.form, waiting for Jack) or, until then, approved names (가격 · PBR · 배당수익률); under each
// field the chip of what was typed, so the direction (아래 · 이상) and the unit read before 저장.
const LABEL = {
  pxBelow: (us) => (us ? W().form.pxUs : W().form.pxKr) || C.why.srcPrice,
  pbrBelow: () => W().form.pbr || "PBR",
  dyAtLeast: () => W().form.dy || C.pick.receipt.yield,
};
// typed text -> the number (commas and spaces dropped), "" -> null (no condition), NaN when it is not a valid number for the
// kind (a Korean price whole won; the decimals and limits of store.js WATCH_DEC · okWatchValue).
export function parseCond(k, text, us) {
  const raw = String(text == null ? "" : text).replace(/[,\s]/g, "");
  if (!raw) return null;
  if (!/^\d+(\.\d+)?$/.test(raw)) return NaN;
  const v = Number(raw);
  const dec = (raw.split(".")[1] || "").length;
  if (dec > (k === "pxBelow" && !us ? 0 : WATCH_DEC[k])) return NaN;
  return okWatchValue(k, v) ? v : NaN;
}
const typedOf = (k, v, us) => (v == null ? "" : k === "pxBelow" && !us ? String(Math.round(v)) : String(v));

export function CondSheet({ open, store, setStoreData, onClose }) {
  const { wide } = useLayout();
  const t = open && open.t;
  const e = t ? watchOf(store.data)[t] : null;
  const us = !!(open && open.us);
  const [text, setText] = useState(() => Object.fromEntries(WATCH_KINDS.map((k) => [k, typedOf(k, (condsOf(e).find((c) => c.k === k) || {}).v, us)])));
  if (!open || !e) return null;
  const vals = Object.fromEntries(WATCH_KINDS.map((k) => [k, parseCond(k, text[k], us)]));
  const bad = WATCH_KINDS.some((k) => Number.isNaN(vals[k]));
  const save = () => {
    if (bad) return;
    const conds = WATCH_KINDS.filter((k) => vals[k] != null).map((k) => ({ k, v: vals[k] }));
    const next = withWatchConds(store.data, t, conds, todayKst(), Date.now());
    if (!next) { console.warn("[v2] watch-list conditions not saved for " + t); return; }
    setStoreData(next);
    onClose();
  };
  const remove = () => {
    const next = withWatchRemove(store.data, t, todayKst(), Date.now());
    if (next) setStoreData(next);
    onClose();
  };
  return (
    <BottomSheet open title={hitTitle(open.name)} onClose={onClose} closeLabel={C.app.close} shift={wide ? SIDE_W : 0}>
      <div data-ui-v2="watch-sheet" data-t={t}>
        {W().form.hint && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{W().form.hint}</p>}
        {WATCH_KINDS.map((k) => {
          const v = vals[k];
          const now = open.s ? watchValue(open.s, k) : null;
          return (
            <div key={k} data-ui-v2="watch-field" data-k={k}>
              <label style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", marginTop: SPACE(3) })}>
                {LABEL[k](us)}
                <span style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(1) }}>
                  {k === "pxBelow" && us && <span aria-hidden="true" style={tx(SIZE.body, WEIGHT.semi, COLOR.text2)}>$</span>}
                  <input type="text" inputMode={k === "pxBelow" && !us ? "numeric" : "decimal"} value={text[k]} autoComplete="off"
                    onChange={(ev) => setText((x) => ({ ...x, [k]: ev.target.value.slice(0, 16) }))} aria-invalid={Number.isNaN(v) ? "true" : undefined}
                    style={{ flex: 1, minWidth: 0, minHeight: TOUCH, border: Number.isNaN(v) ? `2px solid ${COLOR.watch}` : `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm,
                      padding: `0 ${SPACE(3)}px`, background: COLOR.surface, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
                  {k === "dyAtLeast" && <span aria-hidden="true" style={tx(SIZE.body, WEIGHT.semi, COLOR.text2)}>%</span>}
                </span>
              </label>
              {v != null && !Number.isNaN(v) && (
                <div data-ui-v2="watch-preview" style={{ marginTop: SPACE(1) + 2 }}>
                  <CondChip st={{ k, v, val: now, state: now == null ? "blank" : "stale" }} us={us} />
                </div>
              )}
              {/* an empty field: today's value (or 정보 없음), so there is something to compare with before typing */}
              {v == null && (
                <p data-ui-v2="watch-now" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>
                  {now == null ? W().blank : fill(W().now, { now: nowValue(k, now, us) })}</p>
              )}
              {Number.isNaN(v) && W().form.bad && <Note tone="watch" data-ui-v2="watch-bad">{W().form.bad}</Note>}
            </div>
          );
        })}
        <div style={{ marginTop: SPACE(4) }}><Button onClick={save} disabled={bad}>{C.lim.save}</Button></div>
        <div style={{ marginTop: SPACE(2) }}><Button kind="secondary" onClick={remove}>{W().removeCo}</Button></div>
      </div>
    </BottomSheet>
  );
}

// ---------------- the screen ----------------
// onBack: back to 종목 · onAdd: 종목 with its search field (where a stock is found and added on its company page).
export function WatchScreen({ load, store, setStoreData, pad, onBack, onAdd }) {
  const ok = load.status === "ok";
  const w = watchOf(store.data);
  const order = watchOrder(w);
  const fresh = watchFresh(load);
  const [cond, setCond] = useState(null);                 // { t, name, s, us }: the open condition sheet
  const shown = ok ? order.map((t) => load.byT.get(t)).filter(Boolean) : [];
  const usDate = ok && shown.some(usOf) && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  const edit = canWrite(store);
  return (
    <>
      <Page pad={pad}>
        <AppBar onBack={onBack} backLabel={C.app.tabs.stocks} />
        <div data-ui-v2="watch" data-n={order.length} data-fresh={fresh ? "1" : "0"}>
          <div style={{ marginTop: SPACE(2), display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(2) }}>
            <h2 style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3 })}>{W().title}</h2>
            <button type="button" data-ui-v2="watch-add" onClick={onAdd}
              style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, padding: `0 ${SPACE(1)}px`, ...tx(SIZE.sm, WEIGHT.heavy, COLOR.ink) }}>{W().add}</button>
          </div>
          {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
          {usDate && <Note data-ui-v2="us-close">{fill(C.app.usClose, { md: usDate })}</Note>}
          <OwnCloseNote groups={ok ? ownCloses(load, shown) : []} />
          <p data-ui-v2="watch-sub" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{W().sub}</p>
          {load.status === "fail" && <LoadFail picture={false} />}
          {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
          {/* records (or this list) that could not be read were kept aside: say so, never "아직 관심 종목이 없어요" (review S2) */}
          {store.locked && C.store.locked && <Note tone="watch" data-ui-v2="store-locked">{C.store.locked}</Note>}
          {/* records another tab (or the app before v19.6c) left were merged back: said here too, where the list is (review B1) */}
          {store.restored && <Note tone="watch" data-ui-v2="store-merged">{C.store.merged}</Note>}
          {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
          {ok && !order.length && !store.locked && <Card data-ui-v2="watch-empty"><p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{W().empty}</p></Card>}
          {ok && order.map((t) => (
            <WatchCard key={t} t={t} e={w[t]} load={load} fresh={fresh} canEdit={edit}
              onCond={(tt, name, s) => setCond({ t: tt, name, s, us: s ? usOf(s) : !/^\d/.test(tt) })} />
          ))}
          {ok && order.length > 0 && <p data-ui-v2="watch-bottom" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3) })}>{W().bottom}</p>}
        </div>
        <Footer />
      </Page>
      {cond && <CondSheet key={cond.t} open={cond} store={store} setStoreData={setStoreData} onClose={() => setCond(null)} />}
    </>
  );
}

// ---------------- 종목 tab: the section ----------------
export const SECTION_N = 5;
// row: (s) -> the StockRow of 종목 (stocks.jsx passes it, with its tap and the no-trade line).
export function WatchSection({ load, store, onOpen, row }) {
  const order = watchOrder(watchOf(store.data));
  if (!order.length || load.status !== "ok") return null;
  const rows = order.map((t) => load.byT.get(t)).filter(Boolean).slice(0, SECTION_N);
  return (
    <Card data-ui-v2="watch-section" data-n={order.length}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0 })}>{W().title}</h3>
        <button type="button" data-ui-v2="watch-all" onClick={onOpen}
          style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { whiteSpace: "nowrap" }) }}>{C.rank.all}</button>
      </div>
      {rows.map((s) => row(s))}
    </Card>
  );
}

// ---------------- the company page ----------------
export function WatchButton({ s, store, setStoreData }) {
  const [full, setFull] = useState(false);
  if (!s || !canWrite(store)) return null;
  const w = watchOf(store.data);
  const on = !!w[s.t];
  const tapIt = () => {
    if (on) {
      const next = withWatchRemove(store.data, s.t, todayKst(), Date.now());
      if (next) setStoreData(next);
      setFull(false);
      return;
    }
    if (Object.keys(w).length >= WATCH_MAX) { setFull(true); return; }
    const next = withWatchAdd(store.data, s.t, s.nk, todayKst(), Date.now());
    if (next) setStoreData(next); else console.warn("[v2] not added to the watch list: " + s.t);
  };
  return (
    <div data-ui-v2="watch-co" data-on={on ? "1" : "0"} style={{ marginTop: SPACE(3) }}>
      <button type="button" data-ui-v2="watch-toggle" onClick={tapIt}
        style={{ ...tap, display: "inline-flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH, padding: `0 ${SPACE(4)}px`, borderRadius: 999,
          border: `1px solid ${COLOR.border}`, background: on ? COLOR.select : COLOR.surface, ...tx(SIZE.sm, WEIGHT.bold, COLOR.ink) }}>
        <Icon name="bell" size={20} tone={on ? "on" : "off"} />
        <span>{on ? W().removeCo : W().addCo}</span>
      </button>
      {full && !on && <Note tone="watch" data-ui-v2="watch-cap">{W().cap}</Note>}
    </div>
  );
}

// ---------------- 홈: 오늘 볼 것 ----------------
// hits: watch.js watchHits. Each row: "{name} · 관심 종목 조건", the hit line, and the stock's price date ("{md} 종가", US
// "{date} 종가 (미국 시간)": cofmt.closeLine). Tapping opens 관심 종목 (the 오늘 볼 것 page comes with v19.6b).
export function WatchHitRows({ hits, load, onOpen }) {
  return hits.map((h) => {
    const date = closeLine(load, h.s);
    return (
      <button key={h.t + "|" + h.k} type="button" data-ui-v2="home-watch" data-t={h.t} data-k={h.k} data-date={h.date} onClick={onOpen}
        style={{ ...tap, width: "100%", marginTop: SPACE(2), border: "none", textAlign: "left", background: COLOR.surface, borderRadius: RADIUS.lg - 2, padding: SPACE(3) + 2,
          display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH }}>
        <IconChip name="bell" size={40} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{hitTitle(h.s.nk || h.t)}</span>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, wordBreak: "keep-all" })}>{hitText(h.k, h.v, h.val, usOf(h.s))}</span>
          {date && <span data-ui-v2="home-watch-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{date}</span>}
        </span>
        <Icon name="chevronRight" size={18} tone="on" />
      </button>
    );
  });
}
