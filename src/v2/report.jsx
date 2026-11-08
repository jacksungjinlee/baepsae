// ================= 내 포트폴리오 점검 (v19.3d, v19.3 Part G and O.1, board Report2) =================
// The report for the holdings of 가진 종목 넣기 against the 기준 the user chose. Every number from pf.js; every section
// carries its own content date; ranks are within each market. A missing number shows "–" (read out as 데이터 없음) and
// "doesn't apply" shows 해당 없음: never an empty dot. Stale data: the report opens with the stale line and still shows
// what that close gives (a one-time check, Part G); failed data: the load-failure message.
//   1 headline: 잘 맞아요 / 덜 맞아요 (screen()'s cut; 넉넉하게 50%), the unscored holdings named, 내 기준 and its ten slots
//   2 포트폴리오 전체로 보면: weighted average 상위 % per 기준 on a track (left = best, the top {top}% tinted)
//   3 종목별로 보면: full dot = top 30% · half = top 50% · empty = the rest
//   4 어느 업종에 몰려 있나요?: a treemap by industry group and holding (navy shades), the two concentration rules
//   5 2022: the β range (Part O.1) against 코스피 and S&P 500 (원화)
//   6 연 배당금 (지난 1년 기준), before tax
//   7 비중을 바꿔 보면: starts at today's weights and moves only when the user moves one (never a suggestion)
// No 뱁이 (numbers everywhere). No Korean here: src/copy/v2.js.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOPIC_CHIP, HOLDING_SHADES, holdingShades } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Amount, Collapsible } from "../ui/components.jsx";
import { C, fill, mdText, wonText, p1 } from "./format.js";
import { Card, LoadFail, Note, CardPic, tx, useHeld } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { CARDS, POINTS_TOTAL } from "./engine.js";
import { CARD_PICS, dotColor } from "./pictures.js";
import { Slot } from "./build.jsx";
import { RuleTile, groupName } from "./pfview.jsx";
import { pfState, range2022, dividendYear, reportDates, dotOf, averages, moveWeight, squarify } from "./pf.js";
import { missingPct } from "./deckcalc.js";

const cardName = (id) => C.build.cards[id].name;
const pct0 = (w) => Math.round(w * 100);
const around = (tpl, slot) => { const i = tpl.indexOf(`{${slot}}`); return i < 0 ? [tpl, ""] : [tpl.slice(0, i), tpl.slice(i + slot.length + 2)]; };

function Section({ icon, title, children, id }) {
  return (
    <Card data-ui-v2={id}>
      <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { display: "flex", alignItems: "center", gap: SPACE(3) })}>
        {icon && <span style={{ width: SPACE(9), height: SPACE(9), borderRadius: "30%", background: COLOR.select, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon name={icon} size={20} tone="on" />
        </span>}
        <span>{title}</span>
      </h3>
      {children}
    </Card>
  );
}

// deck: the portfolio record (pf.js importedRecord) the report is about.
export function Report({ load, deck }) {
  const held = useHeld();
  // a one-time check: stale data still gives a result, said up front (the 홈 check never shows a ✓ on it)
  const st = useMemo(() => (load.status !== "ok" ? null : pfState(deck, { state: { ok: true }, byT: load.byT, coByT: load.coByT, fx: load.data.fx,
    pxDate: load.data.pxDate }, load.data.stocks)), [deck, load]);
  if (load.status === "fail") return <LoadFail picture={false} />;
  if (load.status !== "ok") return null;
  const stale = !!(load.fresh && load.fresh.stale);
  if (!st || !st.ok) return <LoadFail picture={false} />;
  // A later publish waits for this screen (HeldContext, Jack 2026-11-08): its line in place of the stale note (the date of
  // the result stays in the line under the headline: rpt.dates).
  return (
    <div data-ui-v2="report">
      {(stale || held) && (
        <Note tone="watch" data-ui-v2="report-stale" data-held={held ? "1" : undefined}>
          {held ? C.app.heldNew : fill(C.rpt.stale, { n: load.fresh.days, date: mdText(load.data.pxDate) })}
        </Note>
      )}
      <Headline st={st} deck={deck} load={load} />
      <Whole st={st} />
      <ByStock st={st} />
      <Industry st={st} />
      {/* both need every holding's value today (the 가진 종목 넣기 flow only reaches 점검 when they all have one) */}
      {st.view.ok && <Y2022 st={st} load={load} />}
      {st.view.ok && <Dividends st={st} load={load} />}
      {/* keyed by the publish: its weights start again from today's when newer data comes in (2026-11-08, a page brought
          back into view: app.jsx), never the old weights over the new rows */}
      <Sandbox key={load.data.publishedAt} st={st} />
    </div>
  );
}

// ---------------- 1 ----------------
function Headline({ st, deck, load }) {
  const d = reportDates(st.view, { pxDate: load.data.pxDate }, load.coByT);
  const parts = C.rpt.dates.split(" · ");
  const md = mdText(d.pxDate);
  const usMd = load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  const dateLine = [md && fill(parts[0], { date: md }), d.krYear != null && fill(parts[1], { year: d.krYear })].filter(Boolean);
  const s = st.stats;
  const slots = CARDS.filter((c) => !c.pending).flatMap((c) => {
    const n = (deck.settings.points || {})[c.id] || 0;
    return Array.from({ length: n }, (_, i) => ({ id: c.id, n, first: i === 0 }));
  });
  const warn = st.rules.find((r) => r.id === "warn");
  return (
    <Card data-ui-v2="report-head" style={{ marginTop: SPACE(3) }}>
      {dateLine.length > 0 && <div data-ui-v2="report-dates" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>
        {dateLine.map((x, i) => <span key={i}>{i ? " · " : ""}{x}</span>)}
      </div>}
      {/* the US close when it is another day (the approved app.usClose line); "미국 {fy} 회계연도" waits for v19.2's SEC data */}
      {d.us && usMd && <div data-ui-v2="report-us-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.app.usClose, { md: usMd })}</div>}
      <h2 data-ui-v2="report-headline" style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1), lineHeight: 1.35, textWrap: "balance" })}>
        {fill(C.rpt.head, { a: s.fit.length, b: s.less.length })}
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: SPACE(2), marginTop: SPACE(3) }}>
        <Group label={C.rpt.fit} rows={s.fit} icon="check-circle" tone="ok" bg={COLOR.okBg} id="fit" />
        <Group label={C.rpt.less} rows={s.less} icon="circle-dashed" tone="on" bg={COLOR.page} id="less" />
      </div>
      {s.unscored.length > 0 && (
        <Note data-ui-v2="report-unscored">{fill(C.rpt.unscored, { n: s.unscored.length, names: s.unscored.map((r) => r.nk).join(", ") })}</Note>
      )}
      <div data-ui-v2="report-mine" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(3) })}>
        {[C.rpt.mine, ...s.cards.map((c) => fill(C.build.s1.slot, { card: cardName(c.id), n: c.pts }))].join(" · ")}
      </div>
      <div role="group" aria-label={C.build.s1.meter} style={{ display: "grid", gridTemplateColumns: `repeat(${POINTS_TOTAL}, minmax(0, 32px))`, justifyContent: "space-between",
        columnGap: SPACE(1), marginTop: SPACE(2) }}>
        {Array.from({ length: POINTS_TOTAL }, (_, i) => <Slot key={i} slot={slots[i]} />)}
      </div>
      {warn && <div style={{ marginTop: SPACE(3) }}><RuleTile r={warn} /></div>}
    </Card>
  );
}

function Group({ label, rows, icon, tone, bg, id }) {
  return (
    <div data-ui-v2={"report-" + id} data-n={rows.length} style={{ background: bg, borderRadius: RADIUS.md, padding: SPACE(3), minWidth: 0 }}>
      <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink, { display: "flex", alignItems: "center", gap: SPACE(1) })}>
        <Icon name={icon} size={16} tone={tone} /><span>{label}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE(1), marginTop: SPACE(2) }}>
        {rows.map((r) => <span key={r.key} title={r.nk} data-group-row={r.key} style={{ display: "flex" }}><CoMark t={r.t} s={r.s} name={r.nk} size={SPACE(8)} /></span>)}
      </div>
    </div>
  );
}

// ---------------- 2 ----------------
function Whole({ st }) {
  const s = st.stats;
  const fit = st.rules.find((r) => r.id === "fit");
  return (
    <Section id="report-whole" icon="clipboard-text" title={C.rpt.whole}>
      {s.cards.map((c) => {
        const a = s.avg[c.id];
        const tint = TOPIC_CHIP[CARD_PICS[c.id].topic];
        return (
          <div key={c.id} data-report-card={c.id} data-avg={a ? a.shown : undefined} style={{ display: "flex", alignItems: "center", gap: SPACE(3), marginTop: SPACE(3) }}>
            <CardPic id={c.id} size="fit" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2) }}>
                <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{cardName(c.id)}</span>
                {a ? <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{fill(C.rpt.avgTop, { x: a.shown })}</span>
                  : <span aria-label={C.rpt.noData} style={tx(SIZE.sm, WEIGHT.heavy, COLOR.text2)}>–</span>}
              </div>
              <div aria-hidden="true" style={{ position: "relative", height: SPACE(2), borderRadius: 999, background: COLOR.page, marginTop: SPACE(1) + 2 }}>
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${s.top}%`, background: tint, borderRadius: 999 }} />
                {a && <div style={{ position: "absolute", top: -3, width: 14, height: 14, borderRadius: 999, background: COLOR.ink, border: `2px solid ${COLOR.surface}`,
                  left: `calc(${Math.min(100, Math.max(0, a.x))}% - 7px)` }} />}
              </div>
            </div>
          </div>
        );
      })}
      <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3) })}>{fill(C.rpt.trackNote, { top: s.top })}</p>
      {fit && <div style={{ marginTop: SPACE(2) }}><RuleTile r={fit} /></div>}
      <div style={{ marginTop: SPACE(2) }}>
        <Collapsible title={C.rpt.how}><p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.rpt.howNote}</p></Collapsible>
      </div>
    </Section>
  );
}

// ---------------- 3 ----------------
function Dot({ id, kind }) {
  const label = kind === "full" ? C.rpt.dots[0] : kind === "half" ? C.rpt.dots[1] : kind === "empty" ? C.rpt.dots[2] : kind === "na" ? C.rpt.na : C.rpt.noData;
  if (kind === "blank") return <span role="img" aria-label={label} data-dot="blank" style={tx(SIZE.sm, WEIGHT.bold, COLOR.text2)}>–</span>;
  if (kind === "na") return <span data-dot="na" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { whiteSpace: "nowrap" })}>{label}</span>;
  const c = id ? dotColor(id) : COLOR.text2;
  const bg = kind === "full" ? c : kind === "half" ? `linear-gradient(90deg, ${c} 50%, ${COLOR.surface} 50%)` : COLOR.surface;
  return <span role="img" aria-label={label} data-dot={kind} style={{ display: "inline-block", width: 16, height: 16, borderRadius: 999, background: bg,
    boxShadow: `inset 0 0 0 1.5px ${kind === "empty" ? "#C9C2B8" : c}` }} />;
}

function ByStock({ st }) {
  const s = st.stats;
  const rows = st.view.rows.filter((r) => s.per.get(r.key).scored);
  const shades = holdingShades(st.view.rows.map((r) => r.w));
  const shadeOf = (r) => shades[st.view.rows.indexOf(r)] || HOLDING_SHADES[HOLDING_SHADES.length - 1];
  const cols = s.cards.length;
  // v19.3d2 review: the name column keeps at least NAME_MIN for the name itself (it was 132px with the logo: 3 cards
  // overflowed a 320px phone by 16px). The logo shows only when the table has room for it besides that (measured on the
  // table's own width, again when it changes); what still does not fit scrolls inside the card, never the page, with a
  // fade at the right edge while columns are hidden there.
  const NAME_MIN = 64, LOGO = SPACE(8) + SPACE(2), COL = 56;
  const box = useRef(null);
  const [fit, setFit] = useState(() => ({ logo: typeof window !== "undefined" && window.innerWidth >= 480, more: false }));   // a first guess
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const measure = () => {
      const logo = el.clientWidth >= NAME_MIN + LOGO + cols * COL;
      const more = el.scrollWidth - el.scrollLeft - el.clientWidth > 1;
      setFit((f) => (f.logo === logo && f.more === more ? f : { logo, more }));
    };
    measure();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    if (ro) ro.observe(el);
    window.addEventListener("resize", measure);
    el.addEventListener("scroll", measure, { passive: true });
    return () => { if (ro) ro.disconnect(); window.removeEventListener("resize", measure); el.removeEventListener("scroll", measure); };
  }, [cols]);
  const nameMin = NAME_MIN + (fit.logo ? LOGO : 0);
  const grid = { display: "grid", gridTemplateColumns: `minmax(${nameMin}px, 1fr) repeat(${cols}, 52px)`, alignItems: "center", columnGap: SPACE(1) };
  return (
    <Section id="report-bystock" icon="list" title={C.rpt.byStock}>
      <div style={{ position: "relative", marginTop: SPACE(3) }}>
      <div ref={box} data-ui-v2="bystock-scroll" data-logo={fit.logo ? "1" : "0"} style={{ overflowX: "auto" }}>
        <div style={{ minWidth: nameMin + cols * COL }}>
          <div style={{ ...grid, paddingBottom: SPACE(2), borderBottom: `1px solid ${COLOR.line}` }}>
            <span />
            {s.cards.map((c) => (
              <span key={c.id} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                <CardPic id={c.id} />
                <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { textAlign: "center", lineHeight: 1.2 })}>{cardName(c.id)}</span>
              </span>
            ))}
          </div>
          {rows.map((r) => (
            <div key={r.key} data-report-row={r.key} style={{ ...grid, padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <span style={{ display: "flex", alignItems: "center", gap: SPACE(2), minWidth: 0 }}>
                {fit.logo && <CoMark t={r.t} s={r.s} name={r.nk} size={SPACE(8)} />}
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{r.nk}</span>
                  <span aria-hidden="true" style={{ display: "block", height: 4, borderRadius: 999, background: COLOR.page, marginTop: 3 }}>
                    <span style={{ display: "block", height: "100%", width: `${Math.min(100, (r.w || 0) * 100)}%`, background: shadeOf(r), borderRadius: 999 }} />
                  </span>
                </span>
              </span>
              {s.cards.map((c) => (
                <span key={c.id} data-cell={c.id} style={{ display: "flex", justifyContent: "center" }}><Dot id={c.id} kind={dotOf(s.per.get(r.key).cells[c.id])} /></span>
              ))}
            </div>
          ))}
        </div>
      </div>
      {fit.more && <div aria-hidden="true" data-ui-v2="bystock-more" style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: SPACE(8), pointerEvents: "none",
        background: `linear-gradient(to right, ${COLOR.surface}00, ${COLOR.surface})` }} />}
      </div>
      <div data-ui-v2="dot-legend" style={{ display: "flex", flexWrap: "wrap", gap: SPACE(3), marginTop: SPACE(3) }}>
        {["full", "half", "empty"].map((k, i) => (
          <span key={k} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "inline-flex", alignItems: "center", gap: SPACE(1) })}>
            <span aria-hidden="true" style={{ display: "inline-flex" }}><Dot id={null} kind={k} /></span><span>{C.rpt.dots[i]}</span>
          </span>
        ))}
      </div>
    </Section>
  );
}

// ---------------- 4 ----------------
const TM_W = 320, TM_H = 200;
// The text colour on a treemap block: the first of white, navy ink and black that reads at 4.5:1 or more on that shade
// (#7C889C needs black: white 3.6:1, navy 4.0:1).
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
export const textOn = (shade) => [COLOR.surface, COLOR.ink, "#000000"].find((c) => ratio(c, shade) >= 4.5) || "#000000";
function Industry({ st }) {
  const v = st.view;
  const stock = st.rules.find((r) => r.id === "stock"), ind = st.rules.find((r) => r.id === "ind");
  const shades = holdingShades(v.rows.map((r) => r.w));
  const order = v.ok ? [...st.ind.groups.flatMap((g) => g.rows), ...st.ind.none.rows] : [];
  const rects = v.ok ? squarify(order.map((r) => ({ key: r.key, v: r.w })), 0, 0, TM_W, TM_H) : [];
  const byKey = new Map(v.rows.map((r, i) => [r.key, { r, shade: shades[i] }]));
  const legend = v.ok ? [...st.ind.groups.map((g) => ({ k: g.ind, name: groupName(g) || C.rpt.noInd, w: g.w })), ...(st.ind.none.rows.length ? [{ k: "none", name: C.rpt.noInd, w: st.ind.none.w }] : [])] : [];
  return (
    <Section id="report-industry" icon="chart-pie-slice" title={C.rpt.ind}>
      {rects.length > 0 && (
        <div data-ui-v2="treemap" style={{ position: "relative", width: "100%", aspectRatio: `${TM_W} / ${TM_H}`, marginTop: SPACE(3), borderRadius: RADIUS.md, overflow: "hidden" }}>
          {rects.map((x) => {
            const { r, shade } = byKey.get(x.key);
            const ink = textOn(shade);
            const big = x.w >= 64 && x.h >= 40;
            return (
              <div key={x.key} data-tm={x.key} title={r.nk} style={{ position: "absolute", left: `${(x.x / TM_W) * 100}%`, top: `${(x.y / TM_H) * 100}%`,
                width: `${(x.w / TM_W) * 100}%`, height: `${(x.h / TM_H) * 100}%`, background: shade, boxShadow: `inset 0 0 0 1px ${COLOR.surface}`, padding: SPACE(1) + 2,
                boxSizing: "border-box", overflow: "hidden" }}>
                {big && <span style={tx(SIZE.sm, WEIGHT.heavy, ink, { display: "block", lineHeight: 1.2 })}>{pct0(r.w)}%</span>}
                {big && <span style={tx(SIZE.xs, WEIGHT.semi, ink, { display: "block", lineHeight: 1.25, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{r.nk}</span>}
              </div>
            );
          })}
        </div>
      )}
      {legend.length > 0 && (
        <div data-ui-v2="ind-legend" style={{ display: "flex", flexWrap: "wrap", columnGap: SPACE(3), rowGap: SPACE(1), marginTop: SPACE(2) }}>
          {legend.map((g) => <span key={g.k} data-ind={g.k} style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>{g.name} {pct0(g.w)}%</span>)}
        </div>
      )}
      <div style={{ display: "grid", gap: SPACE(2), marginTop: SPACE(3) }}>
        <RuleTile r={stock} />
        <RuleTile r={ind} />
      </div>
    </Section>
  );
}

// ---------------- 5 ----------------
function Y2022({ st, load }) {
  const R = load.r2022;
  const est = range2022(st.view, R);
  const kr = R.kr * 100, us = R.usWon * 100;
  const [mineL] = around(C.deck.vsMine, "pct");
  const [kospiL] = around(C.deck.vsKospi, "pct");
  const scale = Math.max(Math.abs(kr), Math.abs(us), est.ok && est.big ? est.big : 0, 1) * 1.15;
  const bar = (f, color, light) => (
    <div aria-hidden="true" style={{ position: "relative", height: SPACE(3), background: COLOR.page, borderRadius: 4 }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${(f / scale) * 100}%`, background: color, borderRadius: 4 }} />
      {light != null && <div style={{ position: "absolute", left: `${(f / scale) * 100}%`, top: 0, bottom: 0, width: `${((light - f) / scale) * 100}%`, background: color, opacity: 0.4, borderRadius: 4 }} />}
    </div>
  );
  const row = (label, value, b, id) => (
    <div data-y2022={id} style={{ display: "grid", gridTemplateColumns: "104px 1fr 72px", alignItems: "center", gap: SPACE(2), marginTop: SPACE(2) }}>
      <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink)}>{label}</span>{b}<span style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink, { textAlign: "right" })}>{value}</span>
    </div>
  );
  const MINUS = "−";
  const mine = !est.ok || est.est === "uncertain" ? null : est.est === "one" ? `${MINUS}${est.small}%` : `${MINUS}${est.small}~${est.big}%`;
  let sentence = null;
  if (est.ok && est.est === "uncertain") sentence = C.rpt.y2022Unsure;
  else if (est.ok && est.est === "one") sentence = fill(C.rpt.y2022One, { x: est.small, amount: wonText(est.amountSmall) });
  else if (est.ok) sentence = fill(C.rpt.y2022Range, { small: est.small, big: est.big, amount_small: wonText(est.amountSmall), amount_big: wonText(est.amountBig) });
  return (
    <Section id="report-2022" icon="umbrella" title={C.rpt.y2022}>
      <div style={{ marginTop: SPACE(2) }}>
        {mine && row(mineL.trim(), mine, bar(est.small, "#5A6B87", est.est === "range" ? est.big : null), "mine")}
        {row(kospiL.trim(), `${MINUS}${p1(Math.abs(kr))}%`, bar(Math.abs(kr), "#9AA3B2"), "kospi")}
        {row(C.rpt.sp500Won, `${MINUS}${p1(Math.abs(us))}%`, bar(Math.abs(us), "#9AA3B2"), "sp500")}
      </div>
      {sentence && <p data-ui-v2="y2022-line" style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink, { marginTop: SPACE(3) })}>{sentence}</p>}
      {!est.ok && est.why === "half" && <Note>{C.plan.riskHalf}</Note>}
      {!est.ok && est.why === "none" && <Note>{C.plan.riskNone}</Note>}
      {/* left out, each kind with its own line: no data at all (added by name: no 2022 price), and in the data without a
          usable β (#83's line, with their share) */}
      {est.ok && est.noPrice.length > 0 && <Note data-ui-v2="y2022-out">{fill(C.rpt.y2022Out, { n: est.noPrice.length, names: est.noPrice.join(", ") })}</Note>}
      {est.ok && est.noBetaShare > 1e-9 && <Note data-ui-v2="y2022-partial">{fill(C.plan.riskPartial, { pct: missingPct(est.noBetaShare) })}</Note>}
      <div style={{ marginTop: SPACE(2) }}>
        <Collapsible title={C.rpt.how}>
          <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.rpt.y2022How} {C.rpt.y2022Band}</p>
          <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{C.plan.y2022Source}</p>
        </Collapsible>
      </div>
    </Section>
  );
}

// ---------------- 6 ----------------
function Dividends({ st, load }) {
  const d = dividendYear(st.view, load.data.fx, load.coByT);
  return (
    <Section id="report-div" icon="coins" title={C.plan.div}>
      <div data-ui-v2="report-div-total" style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(2) })}><Amount text={fill(C.app.about, { x: wonText(d.won) })} /></div>
      <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{C.rpt.divNote}</p>
      {/* say-why (Jack, 2026-11-08): only when a US stock with a known dividend is in the total (pf.dividendYear us), and
          the US stocks with no dividend data named apart (usGone), never twice with the 0원 line */}
      {d.us && <Note data-ui-v2="report-div-us">{C.rpt.divUs}</Note>}
      {d.usGone > 0 && <Note data-ui-v2="report-div-us-gone">{fill(C.rpt.divUsGone, { n: d.usGone })}</Note>}
      {d.unknown > 0 && <Note>{fill(C.plan.divUnknown, { n: d.unknown })}</Note>}
      {d.unchecked.length > 0 && <Note>{fill(C.plan.divUnchecked, { n: d.unchecked.length, names: d.unchecked.map((x) => x.nk).join(", ") })}</Note>}
    </Section>
  );
}

// ---------------- 7 ----------------
function Sandbox({ st }) {
  const s = st.stats;
  const rows = st.view.rows;
  const start = useMemo(() => new Map(rows.map((r) => [r.key, r.w])), [rows]);
  const [w, setW] = useState(start);
  if (!s.cards.length || !st.view.ok) return null;
  const after = averages(rows, s.per, s.cards, w);
  const moved = rows.filter((r) => Math.abs((w.get(r.key) || 0) - r.w) > 1e-6);
  return (
    <Section id="report-sandbox" icon="note-pencil" title={C.rpt.sandbox}>
      {rows.map((r) => (
        <label key={r.key} data-sandbox={r.key} style={{ display: "grid", gridTemplateColumns: "28px 1fr 88px", alignItems: "center", gap: SPACE(2), marginTop: SPACE(2) }}>
          <CoMark t={r.t} s={r.s} name={r.nk} size={SPACE(7)} />
          <input type="range" min={0} max={100} step={1} value={Math.round((w.get(r.key) || 0) * 100)} aria-label={r.nk}
            onChange={(e) => setW((m) => moveWeight(m, r.key, Number(e.target.value) / 100))} style={{ width: "100%", accentColor: COLOR.ink }} />
          <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { textAlign: "right" })}>
            {moved.includes(r) ? <>{pct0(r.w)}% → <b style={{ color: COLOR.ink }}>{pct0(w.get(r.key))}%</b></> : `${pct0(r.w)}%`}
          </span>
        </label>
      ))}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))", gap: SPACE(2), marginTop: SPACE(3) }}>
        {s.cards.map((c) => {
          const b = s.avg[c.id], a = after[c.id];
          return (
            <div key={c.id} data-sandbox-card={c.id} style={{ background: TOPIC_CHIP[CARD_PICS[c.id].topic], borderRadius: RADIUS.md, padding: SPACE(2), textAlign: "center" }}>
              <CardPic id={c.id} style={{ background: "transparent" }} />
              <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.ink)}>{cardName(c.id)}</div>
              <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{b ? `${b.shown}%` : "–"} → {a ? `${a.shown}%` : "–"}</div>
            </div>
          );
        })}
      </div>
      <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{C.rpt.sandboxNote}</p>
    </Section>
  );
}

