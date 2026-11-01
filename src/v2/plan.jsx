// 매수 계획 · 샀어요: whole shares, money left, past-year dividend, the 2022 line, weights with a one-line reason each,
// 내 투자 규칙 per holding (each rule checked or 준비 중), 이 덱의 주의점, and the purchase record kept in this browser.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { MoneyInput, WeightBar, Collapsible, BottomSheet, Button } from "../ui/components.jsx";
import { ruleBook, hasGroup } from "./engine.js";
import { C, fill, nf, p1, mdText, wonText, todayKst } from "./format.js";
import { Page, AppBar, ScreenTitle, DateLine, Footer, Note, Card, Label, ActionBar, RuleLine, TextInput, tx } from "./ui.jsx";
import { deckState, pickItems, computePlan, deckDisplayName, reasonsLine, clashPieces, aboutWon, missingPct } from "./deckcalc.js";
import { writeStore } from "./store.js";

export function Plan({ load, builder, setBuilder, store, setStoreData, goToday }) {
  const st = builder.settings;
  const ds = useMemo(() => deckState(load, st), [load, st]);
  const items = pickItems(ds, builder.picks);
  const r = useMemo(() => (st.amountMan > 0 ? computePlan(load, st, items, ds.pinned) : null), [load, st, ds, builder.picks]);
  const [sheet, setSheet] = useState(null);       // null | "form" | "done"
  const s4 = C.build.s4;
  const back = () => { setBuilder((b) => ({ ...b, stage: "pick" })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const setAmount = (v) => setBuilder((b) => ({ ...b, settings: { ...b.settings, amountMan: v } }));
  const N = items.length + ds.pinned.length;
  const deckLine = [deckDisplayName(st), fill(C.app.stocksN, { n: N }), fill(C.plan.methodLine, { method: s4.method[st.method] })].join(" · ");
  const ok = r && r.ok;
  const plan = ok ? r.plan : null;
  const usRows = ok && plan.rows.some((x) => x.s.cls === "us" && x.shares > 0);
  const usDate = load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  return (
    <Page pad={SPACE(30)}>
      <AppBar onBack={back} backLabel={C.plan.back} />
      <DateLine date={load.data.pxDate} fresh={load.fresh} />
      <ScreenTitle>{C.plan.title}</ScreenTitle>
      <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>{deckLine}</div>
      <Card>
        <MoneyInput label={C.plan.amountLabel} unit={C.app.manUnit} value={st.amountMan} onChange={setAmount} clearLabel={s4.clear}
          quick={[{ label: s4.quick[0], add: 10 }, { label: s4.quick[1], add: 100 }, { label: s4.quick[2], add: 1000 }]}
          warning={!st.amountMan ? s4.amountEmpty : st.amountMan > 100000 ? s4.over10 : null} />
      </Card>
      {r && !r.ok && <Clash parts={r.clash} />}
      {ok && <Summary r={r} />}
      {ok && plan.tooSmall && (
        <Note tone="watch" data-ui-v2="too-small">{fill(C.plan.tooSmall, { n: plan.rows.length, price: fill(C.app.won, { n: nf(Math.round(plan.cheapest)) }) })}</Note>
      )}
      {ok && (
        <Card data-ui-v2="plan-rows">
          <Label>{C.plan.stocks}</Label>
          <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>{C.plan.targetNote}</div>
          {plan.rows.map((x) => <PlanRow key={x.t} x={x} />)}
          <Note>{fill(C.plan.priceNote, { md: mdText(load.data.pxDate), fx: nf(Math.round(load.data.fx)) })}</Note>
          {usRows && usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
        </Card>
      )}
      {ok && <Rules load={load} rows={plan.rows} st={st} ds={ds} />}
      {ok && <DeckWarnings rows={plan.rows} st={st} />}
      <Footer />
      {ok && plan.spent > 0 && (
        <ActionBar summary={fill(C.plan.left, { leftText: wonText(plan.left) })} action={C.plan.bought} onAction={() => setSheet("form")} />
      )}
      {ok && (
        <RecordSheet open={!!sheet} stage={sheet} onClose={() => setSheet(null)} load={load} st={st} plan={plan} ds={ds}
          store={store} setStoreData={setStoreData} onDone={() => setSheet("done")} goToday={() => { setSheet(null); goToday(); }} />
      )}
    </Page>
  );
}

function Clash({ parts }) {
  const pieces = clashPieces(parts);
  return (
    <div data-ui-v2="clash" role="alert" style={{ marginTop: SPACE(3), background: COLOR.watchBg, borderRadius: RADIUS.md, padding: SPACE(4), display: "flex", gap: SPACE(2) }}>
      <Icon name="alert" size={20} color={COLOR.watch} />
      <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.watch)}>
        {pieces.map((p, i) => <span key={i}>{i ? " · " : ""}{p.map((x, j) => <span key={j}>{j ? " " : ""}{x}</span>)}</span>)}
        {C.plan.clash && <div>{C.plan.clash}</div>}
      </div>
    </div>
  );
}

// Risk lines: the 2022 line when any holding has a figure (holdings without one move like the rest, with the approved
// v17.5 note naming their share); else the yearly-swing line; else the approved "can't calculate" line. Never silent.
function Summary({ r }) {
  const { plan, div, y2022, vol } = r;
  const partial = (share) => share > 1e-9 && <div data-ui-v2="risk-partial" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>{fill(C.plan.riskPartial, { pct: missingPct(share) })}</div>;
  const big = (v) => <div style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}>{v}</div>;
  return (
    <Card data-ui-v2="plan-summary">
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.plan.ifBuy}</div>
      {big(fill(C.plan.left, { leftText: wonText(plan.left) }))}
      <div style={{ marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.plan.div}</div>
      {big(aboutWon(div.won))}
      <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>{C.plan.preTax}</div>
      {div.unknown > 0 && <div data-ui-v2="div-unknown" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>{fill(C.plan.divUnknown, { n: div.unknown })}</div>}
      {y2022.ok && (
        <div data-ui-v2="y2022">
          <div style={{ marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.plan.y2022}</div>
          {big(aboutWon(Math.min(0, y2022.won)))}
          <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>{C.plan.y2022Note}</div>
          {partial(y2022.missing)}
        </div>
      )}
      {!y2022.ok && vol != null && (
        <div data-ui-v2="vol-line" style={{ marginTop: SPACE(3) }}>
          <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>{fill(C.plan.volLine, { amt: nf(Math.round((vol.vol * plan.spent) / 10000)) })}</div>
          {partial(vol.missing)}
        </div>
      )}
      {!y2022.ok && vol == null && plan.spent > 0 && (
        <div data-ui-v2="risk-none" style={{ marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.semi, COLOR.text2) }}>{C.plan.riskNone}</div>
      )}
    </Card>
  );
}

function PlanRow({ x }) {
  const line = [reasonsLine(x.reasons), x.shares === 0 && x.px > 0 ? C.plan.reason.tooPricey : null].filter(Boolean).join(" · ");
  return (
    <div data-row={x.t} style={{ padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(3) }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { minWidth: 0 })}>{x.s.nk}</span>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flexShrink: 0, textAlign: "right" })}>
          <span>{fill(C.plan.shares, { n: nf(x.shares) })}</span>{" · "}<span>{wonText(x.cost)}</span>
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3), marginTop: SPACE(2) }}>
        <div style={{ flex: 1 }}><WeightBar current={Math.round(x.w * 1000) / 10} target={Math.round(x.targetW * 1000) / 10} max={Math.max(30, x.targetW * 160)} label={C.plan.weightAria} status={x.shares > 0 ? "ok" : "watch"} /></div>
        <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { width: SPACE(12), textAlign: "right" })}>{`${p1(x.w * 100)}%`}</span>
      </div>
      {line && <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{line}</div>}
    </div>
  );
}

// ---------------- 내 투자 규칙 ----------------
export function rulesFor(load, row, st, ds) {
  const s = row.s;
  if (row.kind === "cushion") return ruleBook({ ...s, cls: "etf" }, null, {}, row.targetW).filter((x) => x.id === "band");
  return ruleBook(s, load.coByT.get(s.t) || null, st.points, row.targetW);
}

function RuleList({ rules }) {
  const R = C.plan.rules;
  const line = (x) => {
    const src = x.fy ? fill(C.app.reportYear, { year: x.fy }) : null;
    switch (x.id) {
      case "divCut": return x.check === "pending" ? <RuleLine key={x.id} name={R.divCut} pending />
        : <RuleLine key={x.id} name={R.dividend} now={fill(R.dpsChange, { a: nf(Math.round(x.prev)), b: nf(Math.round(x.dps)) })} limit={R.divLimit} source={src} />;
      case "audit": return <RuleLine key={x.id} name={R.audit} pending />;
      case "acquisition": return <RuleLine key={x.id} name={R.acquisition} pending />;
      case "embezzle": return R.embezzle ? <RuleLine key={x.id} name={R.embezzle} pending /> : null;
      case "debtCeiling": return x.check === "pending" ? <RuleLine key={x.id} name={R.debt} pending />
        : <RuleLine key={x.id} name={R.debt} now={fill(R.now, { x: nf(Math.round(x.debt)) })} limit={fill(R.over, { x: x.limit })} source={src} />;
      case "roeFloor": return R.roeLimit ? <RuleLine key={x.id} name={R.roe} now={fill(R.now, { x: p1(x.roe) })} limit={fill(R.roeLimit, { x: x.floor })} source={src} /> : null;
      case "opDecline": return R.opLimit ? <RuleLine key={x.id} name={R.opProfit} limit={R.opLimit} source={src} /> : null;
      case "cet1": return <RuleLine key={x.id} name={R.cet1} pending />;
      case "kics": return <RuleLine key={x.id} name={R.kics} pending />;
      default: return null;
    }
  };
  const section = (kind, title) => {
    const rows = rules.filter((x) => x.kind === kind).map(line).filter(Boolean);
    return rows.length ? <div style={{ marginTop: SPACE(2) }}><div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{title}</div>{rows}</div> : null;
  };
  const band = rules.find((x) => x.id === "band");
  return (
    <div>
      {section("sell", R.sell)}
      {section("keep", R.keep)}
      {band && (
        <div style={{ marginTop: SPACE(3) }}>
          <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{fill(R.band, { pct: p1(band.target * 100) })}</div>
          <RuleLine name={fill(R.bandText, { a: p1(band.bands[0] * 100), b: p1(band.bands[1] * 100), c: p1(band.bands[2] * 100) })} />
        </div>
      )}
    </div>
  );
}

function reasonOf(row, st) {
  if (row.kind === "cushion") return fill(C.plan.reason.cushion, { pct: st.cushion });
  if (row.kind === "pinned") return C.plan.reason.pinned;
  return null;
}

function Rules({ load, rows, st, ds }) {
  const R = C.plan.rules;
  const all = Object.values(ds.cands).flat();
  return (
    <Card data-ui-v2="rules">
      <Label>{R.title}</Label>
      {R.intro && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{R.intro}</div>}
      <div style={{ marginTop: SPACE(3) }}>
        {rows.filter((x) => x.shares > 0).map((x) => {
          const cand = all.find((c) => c.t === x.t);
          const b = cand ? Object.entries(cand.scores).filter(([, v]) => typeof v === "number").sort((p, q) => (st.points[q[0]] || 0) * q[1] - (st.points[p[0]] || 0) * p[1]).slice(0, 2) : [];
          const why = reasonOf(x, st);
          return (
            <Collapsible key={x.t} title={fill(R.open, { name: x.s.nk })}>
              <div data-rules-for={x.t}>
                <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{R.reason}</div>
                <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>
                  {why ? why : b.map(([id, v], i) => <span key={id}>{i ? " · " : ""}<span>{C.build.cards[id].name}</span>{" "}<span>{fill(C.build.s1.score, { score: Math.round(v) })}</span></span>)}
                </div>
                <RuleList rules={rulesFor(load, x, st, ds)} />
              </div>
            </Collapsible>
          );
        })}
      </div>
      <Note>{R.priceNote}</Note>
    </Card>
  );
}

function DeckWarnings({ rows, st }) {
  const W = C.plan.deckWarn;
  const held = rows.filter((x) => x.shares > 0 && x.kind !== "cushion");
  const lines = [];
  if (held.some((x) => x.s.ind === "bank") || (st.points.div || 0) > 0) lines.push(W.rates);
  const semi = held.find((x) => x.s.ind === "semi");
  if (semi) lines.push(fill(W.semi, { name: semi.s.nk }));
  if (held.some((x) => x.s.cls === "us") && W.usTaxSource) lines.push(W.usTax, W.usTaxSource);   // needs its source and year
  if (!lines.length) return null;
  lines.push(W.knew);
  return (
    <Card data-ui-v2="deck-warn">
      <Label>{W.title}</Label>
      {lines.map((l, i) => <div key={i} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { padding: `${SPACE(1)}px 0` })}>{l}</div>)}
    </Card>
  );
}

// ---------------- 샀어요 ----------------
function RecordSheet({ open, stage, onClose, load, st, plan, ds, store, setStoreData, onDone, goToday }) {
  const rows = plan.rows.filter((x) => x.shares > 0);
  const [date, setDate] = useState("");
  const [vals, setVals] = useState({});
  const [fail, setFail] = useState(false);
  const [tried, setTried] = useState(false);
  const setV = (t, k, v) => setVals((m) => ({ ...m, [t]: { ...(m[t] || {}), [k]: v } }));
  const today = todayKst();
  const parsed = rows.map((x) => {
    const v = vals[x.t] || {};
    const qs = v.qty != null ? String(v.qty).replace(/,/g, "").trim() : "";
    const ps = v.price != null ? String(v.price).replace(/,/g, "").trim() : "";
    const q = qs === "" ? x.shares : /^\d+$/.test(qs) ? Number(qs) : NaN;          // whole shares only
    const p = ps === "" ? x.s.price : /^\d+(\.\d+)?$/.test(ps) ? Number(ps) : NaN;
    return { x, q, p, badQ: !(Number.isInteger(q) && q >= 0), badP: !(Number.isFinite(p) && p > 0) };
  });
  const badDate = date !== "" && !(/^\d{4}-\d{2}-\d{2}$/.test(date) && date <= today);
  const save = () => {
    if (badDate || parsed.some((r) => r.badQ || r.badP)) { setTried(true); return; }
    const day = date || today;
    const purchases = parsed.filter((r) => r.q > 0).map((r) => ({ t: r.x.t, date: day, qty: r.q, price: r.p, ccy: r.x.s.cls === "us" ? "USD" : "KRW" }));
    const id = `d${Date.now().toString(36)}`;
    const deck = {
      id, name: deckDisplayName(st), createdAt: todayKst(), pxDate: load.data.pxDate, fyNote: "rule inputs as of purchase",
      settings: { deck: st.deck, points: st.points, strict: st.strict, exclude: st.exclude, mix: st.mix, count: st.count, method: st.method,
        maxPct: st.maxPct, cushion: st.cushion, amountMan: st.amountMan, pinned: st.pinned },
      holdings: plan.rows.map((x) => ({ t: x.t, nk: x.s.nk, cls: x.s.cls, ind: hasGroup(x.s) ? x.s.ind : null, kind: x.kind, target: x.targetW,
        reasons: x.reasons, setAt: todayKst(), plannedQty: x.shares, rules: rulesFor(load, x, st, ds) })),
      purchases,
    };
    const next = { ...store.data, decks: [...store.data.decks, deck] };
    if (!store.writable || !writeStore(next, store.key)) { setFail(true); return; }
    setFail(false);
    setStoreData(next, true);
    onDone();
  };
  const P = C.plan;
  if (!open) return null;
  if (stage === "done") {
    return (
      <BottomSheet open title={P.done} onClose={onClose} closeLabel={C.app.close}>
        <div data-ui-v2="record-done" style={{ display: "flex", gap: SPACE(3), alignItems: "center" }}>
          <img src="baepi-5.png" alt={P.doneAlt} width={64} height={64} style={{ objectFit: "contain" }} />
          {P.doneBody && <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2)}>{fill(P.doneBody, { n: rows.length })}</p>}
        </div>
        <div style={{ marginTop: SPACE(4) }}><Button kind="secondary" onClick={goToday}>{P.doneLink}</Button></div>
      </BottomSheet>
    );
  }
  return (
    <BottomSheet open title={P.sheetTitle} onClose={onClose} closeLabel={C.app.close}>
      <div data-ui-v2="record-form" aria-label={P.boughtAria}>
        <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2)}>{fill(P.sheetBody, { md: mdText(load.data.pxDate) })}</p>
        <TextInput label={P.date} type="date" value={date} onChange={setDate} max={today} invalid={tried && badDate} />
        {rows.map((x) => (
          <div key={x.t} data-record={x.t} style={{ marginTop: SPACE(4), paddingTop: SPACE(2), borderTop: `1px solid ${COLOR.line}` }}>
            <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{x.s.nk}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: SPACE(2) }}>
              <TextInput label={P.qty} inputMode="numeric" placeholder={nf(x.shares)} value={(vals[x.t] || {}).qty || ""} onChange={(v) => setV(x.t, "qty", v)}
                invalid={tried && parsed.find((r) => r.x.t === x.t).badQ} />
              <TextInput label={x.s.cls === "us" ? P.priceUsd : P.priceWon} inputMode="decimal" placeholder={x.s.cls === "us" ? nf(x.s.price, 2) : nf(x.s.price)}
                value={(vals[x.t] || {}).price || ""} onChange={(v) => setV(x.t, "price", v)} invalid={tried && parsed.find((r) => r.x.t === x.t).badP} />
            </div>
          </div>
        ))}
        {fail && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
        <div style={{ marginTop: SPACE(4) }}><Button onClick={save}>{P.save}</Button></div>
      </div>
    </BottomSheet>
  );
}

