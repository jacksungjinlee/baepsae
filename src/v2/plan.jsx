// 매수 계획 · 샀어요: whole shares, money left, past-year dividend, the 2022 line, weights with a one-line reason each,
// 내 투자 규칙 per holding (each rule checked or 준비 중), 이 포트폴리오의 주의점, and the purchase record kept in this browser.
// v19.0b: big numbers show their unit smaller ("12" + small "만원"). 내 투자 규칙 has its section icon. 기록했어요 keeps the
// happy 뱁이 (baepi-5): every variant of that sheet (KR or US buys, preview or live) shows only a count of stocks, never
// money, prices, returns, weights or scores (CLAUDE.md: a count of stocks is not a number; Jack, 2026-11-04).
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { MoneyInput, WeightBar, Collapsible, BottomSheet, Button, Amount, amountParts } from "../ui/components.jsx";
import { C, fill, nf, p1, mdText, wonText, todayKst, staleText } from "./format.js";
import { Page, AppBar, ScreenTitle, DateLine, Footer, Note, OwnCloseNote, Card, Label, ActionBar, RuleLine, TextInput, SampleLabel, Mascot, IMG, CardScores, useMode, useLayout, SIDE_W, tx } from "./ui.jsx";
import { ownCloses } from "./stocklist.js";
import { usOf, priceDate } from "./cofmt.js";
import { deckState, pickItems, computePlan, deckDisplayName, reasonsLine, clashView, aboutWon, missingPct, rulesFor, deckRecord, opAmounts, y2022View, divDropBody } from "./deckcalc.js";
import { writeStore, recordId } from "./store.js";
import { rateFor, rateEnv, DATE_FROM } from "./records.js";
import { dataSplits, splitSince } from "./lots.js";
import { KR_DIV_TREND, exactData, usDividendCounted } from "./engine.js";
import { epsFixFor } from "./fix.js";
import { EpsFixNote } from "./fixnote.jsx";

export function Plan({ load, builder, setBuilder, store, setStoreData, goToday, goPortfolio }) {
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
          <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.plan.targetNote}</div>
          {plan.rows.map((x) => <PlanRow key={x.t} x={x} />)}
          <Note>{fill(C.plan.priceNote, { md: mdText(load.data.pxDate), fx: nf(Math.round(load.data.fx)) })}</Note>
          {usRows && usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
          {/* v19.1c: a planned US stock priced at an earlier close (pxd): its shares are worked out at that close */}
          <OwnCloseNote groups={ownCloses(load, plan.rows.map((x) => x.s))} />
        </Card>
      )}
      {ok && <Rules load={load} rows={plan.rows} st={st} ds={ds} />}
      {ok && <DeckWarnings rows={plan.rows} st={st} />}
      <Footer />
      {ok && plan.spent > 0 && !builder.recorded && (   // a recorded plan never offers 샀어요 again (Jack, 11월 10일)
        <ActionBar summary={fill(C.plan.left, { leftText: wonText(plan.left) })} action={C.plan.bought} onAction={() => setSheet("form")} />
      )}
      {ok && (
        <RecordSheet open={!!sheet} stage={sheet} load={load} st={st} plan={plan} ds={ds}
          // Jack, 11월 10일: a recorded plan is finished. 기록했어요 closed any way (닫기 · Esc · outside) opens 포트폴리오 with the
          // new portfolio and the next 포트폴리오 만들기 starts fresh (app.jsx doneToPortfolio), so 샀어요 never records the same plan
          // twice. The 샀어요 form itself still closes back to the plan.
          onClose={() => { if (sheet === "done") { setSheet(null); goPortfolio(); } else setSheet(null); }}
          store={store} setStoreData={setStoreData} onDone={() => { setBuilder((b) => ({ ...b, recorded: true })); setSheet("done"); }}
          goToday={() => { setSheet(null); goToday(); }} />
      )}
    </Page>
  );
}

function Clash({ parts }) {
  const { pieces, sentence } = clashView(parts);
  return (
    <div data-ui-v2="clash" role="alert" style={{ marginTop: SPACE(3), background: COLOR.watchBg, borderRadius: RADIUS.md, padding: SPACE(4), display: "flex", gap: SPACE(2) }}>
      <Icon name="alert" size={20} tone="on" />
      <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.watch)}>
        {sentence && <div data-ui-v2="clash-text">{sentence}</div>}
        <div data-ui-v2="clash-list" style={sentence ? tx(SIZE.xs, WEIGHT.semi, COLOR.watch, { marginTop: SPACE(1) }) : undefined}>
          {pieces.map((p, i) => <span key={i}>{i ? " · " : ""}{p.map((x, j) => <span key={j}>{j ? " " : ""}{x}</span>)}</span>)}
        </div>
      </div>
    </div>
  );
}

// The 2022 line (v19.1b data, deckcalc.y2022View: "약 50~77만원 줄어들 수 있어요"), units drawn small like Amount. A narrow
// column never breaks inside the amount or inside a word (keep-all), so the three columns of 포트폴리오 만들기 4단계 wrap the
// same way. v: y2022View's { parts, text, pieces: [pre, amount, verb] }.
export function Y2022Amount({ v }) {
  const [pre, amount, verb] = v.pieces;
  const nw = { whiteSpace: "nowrap" };
  return (
    <span data-ui="amount" data-ui-v2={v.parts.length > 1 ? "y2022-range" : "y2022-one"} style={{ wordBreak: "keep-all" }}>
      {pre}<span style={nw}>{amountParts(amount).map(([p, small], i) => (small ? <span key={i} data-unit="1" style={{ fontSize: "max(12px, 0.6em)", fontWeight: WEIGHT.bold }}>{p}</span> : p))}</span>
      {verb ? " " : ""}{verb ? <span>{verb}</span> : null}
    </span>
  );
}

// Risk lines: the 2022 line when any holding has a figure (holdings without one move like the rest, with the approved
// v17.5 note naming their share); else the yearly-swing line; else the approved "can't calculate" line. Never silent.
// v19.1b data (Part O.1): the 2022 line is a range from the beta band, explained by plan.y2022Range; when its smaller
// end is not a fall, plan.y2022Wide says so instead of a number. Older files: one number, as before.
function Summary({ r }) {
  const { plan, div, y2022 } = r;
  const yv = y2022.ok ? y2022View(y2022) : null;
  // more than half of the money without data: no 2022 number and no yearly swing (the current app's rule)
  const half = !!(y2022.half || (r.vol && r.vol.half));
  const vol = r.vol && !r.vol.half ? r.vol : null;
  // say-why (Jack, 2026-11-08): a bought US stock's 연 배당금 is Yahoo's current dividend rate made into a year
  // (engine.annualDividend: dy x cost), not the past year the label names. Said with 점검's line, word for word, when one
  // went into the total (engine.usDividendCounted). No US stock, or only ones whose dividend is unknown (divUnknown): no line.
  const usDiv = usDividendCounted(plan.rows);
  const partial = (share) => share > 1e-9 && <div data-ui-v2="risk-partial" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.plan.riskPartial, { pct: missingPct(share) })}</div>;
  const big = (v) => <div data-ui-v2="big-number" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}><Amount text={v} /></div>;
  return (
    <Card data-ui-v2="plan-summary">
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.plan.ifBuy}</div>
      {big(fill(C.plan.left, { leftText: wonText(plan.left) }))}
      <div style={{ marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.plan.div}</div>
      {big(aboutWon(div.won))}
      <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.plan.preTax}</div>
      {usDiv && <div data-ui-v2="div-us" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.rpt.divUs}</div>}
      {div.unknown > 0 && <div data-ui-v2="div-unknown" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.plan.divUnknown, { n: div.unknown })}</div>}
      {/* Korean holdings whose dividend the company page does not trust (engine.annualDividend unchecked): left out of the
          total and named, never silently (Jack, 2026-11-05). Long lists wrap; a name is never cut. */}
      {div.unchecked.length > 0 && (
        <div data-ui-v2="div-unchecked" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { overflowWrap: "anywhere" })}>
          {fill(C.plan.divUnchecked, { n: div.unchecked.length, names: div.unchecked.map((x) => x.nk || x.t).join(", ") })}
        </div>
      )}
      {y2022.ok && (
        <div data-ui-v2="y2022" data-band={yv ? (yv.wide ? "wide" : yv.parts.length > 1 ? "range" : "one") : ""}>
          <div style={{ marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.plan.y2022}</div>
          {yv && yv.wide
            ? <div data-ui-v2="y2022-wide" style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink)}>{C.plan.y2022Wide}</div>
            : yv ? <div data-ui-v2="big-number" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}><Y2022Amount v={yv} /></div>
            : big(aboutWon(Math.min(0, y2022.won)))}
          {!(yv && yv.wide) && <div data-ui-v2="y2022-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>
            {yv && yv.parts.length > 1 && C.plan.y2022NoteRange ? C.plan.y2022NoteRange : C.plan.y2022Note}</div>}
          {yv && !yv.wide && yv.parts.length > 1 && C.plan.y2022Range && <div data-ui-v2="y2022-range-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.plan.y2022Range}</div>}
          <div data-ui-v2="y2022-source" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{C.plan.y2022Source}</div>
          {!(yv && yv.wide) && partial(y2022.missing)}
        </div>
      )}
      {!y2022.ok && !half && vol != null && (
        <div data-ui-v2="vol-line" style={{ marginTop: SPACE(3) }}>
          <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>{fill(C.plan.volLine, { amt: nf(Math.round((vol.vol * plan.spent) / 10000)) })}</div>
          {partial(vol.missing)}
        </div>
      )}
      {half && (
        <div data-ui-v2="risk-half" style={{ marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.semi, COLOR.text2) }}>{C.plan.riskHalf}</div>
      )}
      {!y2022.ok && !half && vol == null && plan.spent > 0 && (
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
      {line && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{line}</div>}
    </div>
  );
}

// ---------------- 내 투자 규칙 ---------------- (rulesFor: deckcalc.js, shared with the daily-check tests)

function RuleList({ rules, name, s }) {
  const R = C.plan.rules;
  const line = (x) => {
    const src = x.fy ? fill(C.app.reportYear, { year: x.fy }) : null;
    switch (x.id) {
      // a checked dividend-cut rule is always Korean; with the trend switch off it is not checked (준비 중): its history may
      // hide a split (engine.js KR_DIV_TREND). The saved rule keeps its baseline for when the switch is on. v19.1b data
      // (exactData): the rule book is checked on a comparable, split-checked history (dps3a), so it shows as checked; one
      // saved while the history is not comparable (comparable: false, engine.ruleBook) shows as 준비 중 until it is.
      case "divCut": return x.check === "pending" || x.comparable === false || !(KR_DIV_TREND || exactData()) ? <RuleLine key={x.id} name={R.divCut} pending />
        // 사기 전에 이미 줄었으면 '팔 때'처럼 읽히지 않게, 승인된 확인 필요 문장 한 쌍으로 보여요 (스펙 규칙 4)
        : x.droppedBefore ? <RuleLine key={x.id} name={R.dividend} now={fill(C.pick.caution.divDrop, { name, a: nf(Math.round(x.prev)), b: nf(Math.round(x.dps)) })}
            note={divDropBody()} limit={R.divLimit} source={src} />
        : <RuleLine key={x.id} name={R.dividend} now={fill(R.dpsChange, { a: nf(Math.round(x.prev)), b: nf(Math.round(x.dps)) })} limit={R.divLimit} source={src} />;
      case "audit": return <RuleLine key={x.id} name={R.audit} pending />;
      case "acquisition": return <RuleLine key={x.id} name={R.acquisition} pending />;
      case "embezzle": return R.embezzle ? <RuleLine key={x.id} name={R.embezzle} pending /> : null;
      case "debtCeiling": return x.check === "pending" ? <RuleLine key={x.id} name={R.debt} pending />
        : <RuleLine key={x.id} name={R.debt} now={fill(R.now, { x: nf(Math.round(x.debt)) })} limit={fill(R.over, { x: x.limit })} source={src} />;
      case "roeFloor": return R.roeLimit ? <RuleLine key={x.id} name={R.roe} now={fill(R.now, { x: p1(x.roe) })} limit={fill(R.roeLimit, { x: x.floor })} source={src} /> : null;
      case "opDecline": return R.opLimit ? <RuleLine key={x.id} name={R.opProfit} now={opAmounts(x.op)} limit={R.opLimit} source={src} /> : null;
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
  // 2026-11-08 (Jack): a Korean ROE shown here (the ROE floor rule) is from the same net income as PER/EPS (fixnote.jsx)
  const roeShown = !!R.roeLimit && rules.some((x) => x.id === "roeFloor");
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
      <EpsFixNote s={s} show={epsFixFor(s) && roeShown} />
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
      <Label style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}><IconChip name="clipboard-text" size={32} /><span>{R.title}</span></Label>
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
                  {why ? why : <CardScores list={b} />}
                </div>
                <RuleList rules={rulesFor(load, x, st, ds)} name={x.s.nk} s={x.s} />
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
  // Ways the deck can fall (rates, semiconductors), closed by "이런 이유로 떨어지는 건 처음부터 알고 시작한 일이에요."; the US
  // tax line is not a fall, so it stands apart, with its source and year under it (REDESIGN 4.1).
  const falls = [];
  if (held.some((x) => x.s.ind === "bank") || (st.points.div || 0) > 0) falls.push(W.rates);
  const semi = held.find((x) => x.s.ind === "semi");
  if (semi) falls.push(fill(W.semi, { name: semi.s.nk }));
  const tax = held.some((x) => x.s.cls === "us") && W.usTaxSource;   // needs its source and year
  if (!falls.length && !tax) return null;
  const line = (l, i) => <div key={i} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { padding: `${SPACE(1)}px 0` })}>{l}</div>;
  return (
    <Card data-ui-v2="deck-warn">
      <Label>{W.title}</Label>
      {falls.length > 0 && [...falls, W.knew].map(line)}
      {tax && (
        <div data-ui-v2="us-tax" style={{ marginTop: falls.length ? SPACE(2) : 0 }}>
          {line(W.usTax, "t")}
          <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3)}>{W.usTaxSource}</div>
        </div>
      )}
    </Card>
  );
}

// ---------------- 샀어요 ----------------
// Preview page: the sheet covers the app bar, so the "예시 데이터" label sits right under the sheet's title too.
function SheetSample() {
  return <div style={{ marginBottom: SPACE(2) }}><SampleLabel /></div>;
}

// v19.1c: under a US row of 샀어요 whose price is not at the Korean date the sheet names (sheetBody "{md} 종가"): "미국 {md}
// 종가" (co.usClose) with the row's own date (cofmt.priceDate: usPxDate, or the stock's pxd). Before v19.1c a US row read the
// Korean date only. Nothing for Korean rows, or when the dates are the same.
function RecordClose({ load, s }) {
  const own = usOf(s) ? priceDate(load, s) : null;
  const md = own && own !== load.data.pxDate ? mdText(own) : null;
  if (!md || !C.co.usClose) return null;
  return <div data-ui-v2="record-close" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.co.usClose, { md })}</div>;
}

function RecordSheet({ open, stage, onClose, load, st, plan, ds, store, setStoreData, onDone, goToday }) {
  const rows = plan.rows.filter((x) => x.shares > 0);
  const [date, setDate] = useState("");
  const [vals, setVals] = useState({});
  const [fail, setFail] = useState(false);
  const [tried, setTried] = useState(false);
  const [noRate, setNoRate] = useState(null);     // v19.6a: no exchange rate for the date yet (US rows): "past" | "today" | null
  const [savedN, setSavedN] = useState(0);        // distinct stocks actually recorded (quantity > 0): 기록했어요's {n}
  const setV = (t, k, v) => setVals((m) => ({ ...m, [t]: { ...(m[t] || {}), [k]: v } }));
  const today = todayKst();
  // round-3: a data.json split between the chosen date and today puts today's close on another share basis: that row's price
  // must be typed (no default, no close as the placeholder; the sheet's "비워 두면 … 종가로 기록돼요" line is hidden then)
  const splits = useMemo(() => dataSplits(load.data).list, [load]);
  const needP = (t) => splitSince(splits, t, date || today, today);
  const parsed = rows.map((x) => {
    const v = vals[x.t] || {};
    const qs = v.qty != null ? String(v.qty).replace(/,/g, "").trim() : "";
    const ps = v.price != null ? String(v.price).replace(/,/g, "").trim() : "";
    const q = qs === "" ? x.shares : /^\d+$/.test(qs) ? Number(qs) : NaN;          // whole shares only
    const p = ps === "" ? (needP(x.t) ? null : x.s.price) : /^\d+(\.\d+)?$/.test(ps) ? Number(ps) : NaN;
    // a row not bought (0 shares) needs no price; a typed one must still be a price
    const badP = q === 0 && ps === "" ? false : !(Number.isFinite(p) && p > 0);
    return { x, q, p, badQ: !(Number.isInteger(q) && q >= 0), badP };
  });
  const anyNeedP = rows.some((x) => needP(x.t));
  // v19.6a round-2 review: a year before 2000 is a typo (records.js DATE_FROM): refused with the same line
  const badDate = date !== "" && !(/^\d{4}-\d{2}-\d{2}$/.test(date) && date <= today && date >= DATE_FROM);
  const save = () => {
    if (badDate || parsed.some((r) => r.badQ || r.badP)) { setTried(true); return; }
    const day = date || today;
    // A US purchase keeps the exchange rate of its own date (v19.6a A.1: today's data.json fx, as before, or a past date's
    // close from macro.json fxHist), so 포트폴리오 can show 원금 in won (Part E). A past date whose rate the data does not
    // have yet is not saved (never another day's rate): the approved "환율 정보를 불러오지 못해 …" line says so (today on stale
    // data: records.jsx's today line). A date before 2016 is saved without a rate and marked noFx (never costed at planFx).
    const usRows = parsed.filter((r) => r.q > 0 && r.x.s.cls === "us");
    const rate = usRows.length ? rateFor(day, rateEnv(load, today)) : { ok: true, fx: null };
    if (!rate.ok) { console.warn(`[v2] purchase not saved: no exchange rate for ${day} (${rate.why})`); setNoRate(rate.why === "today" ? "today" : "past"); setTried(true); return; }
    setNoRate(null);
    const fx = usRows.length && typeof rate.fx === "number" && rate.fx > 0 ? rate.fx : null;
    const purchases = parsed.filter((r) => r.q > 0).map((r) => (r.x.s.cls === "us"
      ? { id: recordId(), t: r.x.t, date: day, qty: r.q, price: r.p, ccy: "USD", ...(fx ? { fx } : rate.before ? { noFx: true } : {}) }
      : { id: recordId(), t: r.x.t, date: day, qty: r.q, price: r.p, ccy: "KRW" }));   // id: two tabs' copies merge by it
    const id = `d${Date.now().toString(36)}`;
    const deck = deckRecord({ load, st, plan, purchases, id, today: todayKst() });
    const next = { ...store.data, decks: [...store.data.decks, deck] };
    if (!store.writable || !writeStore(next, store.key, today)) { setFail(true); return; }
    setFail(false);
    setSavedN(new Set(purchases.map((p) => p.t)).size);
    setStoreData(next, true);
    onDone();
  };
  const P = C.plan;
  const { preview } = useMode();
  const { wide } = useLayout();
  if (!open) return null;
  if (stage === "done") {
    return (
      <BottomSheet open title={P.done} onClose={onClose} closeLabel={C.app.close} shift={wide ? SIDE_W : 0}>
        {preview && <SheetSample />}
        <div data-ui-v2="record-done" style={{ display: "flex", gap: SPACE(3), alignItems: "center" }}>
          <Mascot src={IMG.happy} alt={P.doneAlt} size={64} />
          {P.doneBody && savedN > 0 && <p data-ui-v2="done-body" style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2)}>{fill(P.doneBody, { n: savedN })}</p>}
        </div>
        <div style={{ marginTop: SPACE(4) }}><Button kind="secondary" onClick={goToday}>{P.doneLink || C.app.tabs.home}</Button></div>
      </BottomSheet>
    );
  }
  return (
    <BottomSheet open title={P.sheetTitle} onClose={onClose} closeLabel={C.app.close} shift={wide ? SIDE_W : 0}>
      {preview && <SheetSample />}
      <div data-ui-v2="record-form" aria-label={P.boughtAria}>
        {!anyNeedP && <p data-ui-v2="plan-close-line" style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2)}>{fill(P.sheetBody, { md: mdText(load.data.pxDate) })}</p>}
        <TextInput label={P.date} type="date" value={date} onChange={(v) => { setDate(v); setNoRate(null); }} max={today} invalid={tried && badDate} />
        {rows.map((x) => (
          <div key={x.t} data-record={x.t} style={{ marginTop: SPACE(4), paddingTop: SPACE(2), borderTop: `1px solid ${COLOR.line}` }}>
            <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{x.s.nk}</div>
            <RecordClose load={load} s={x.s} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: SPACE(2) }}>
              <TextInput label={P.qty} inputMode="numeric" placeholder={nf(x.shares)} value={(vals[x.t] || {}).qty || ""} onChange={(v) => setV(x.t, "qty", v)}
                invalid={tried && parsed.find((r) => r.x.t === x.t).badQ} />
              <TextInput label={x.s.cls === "us" ? P.priceUsd : P.priceWon} inputMode="decimal" placeholder={needP(x.t) ? undefined : x.s.cls === "us" ? nf(x.s.price, 2) : nf(x.s.price)}
                value={(vals[x.t] || {}).price || ""} onChange={(v) => setV(x.t, "price", v)} invalid={tried && parsed.find((r) => r.x.t === x.t).badP} />
            </div>
          </div>
        ))}
        {fail && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
        {tried && (badDate || parsed.some((r) => r.badQ || r.badP)) && <Note tone="watch" data-ui-v2="bad-input">{P.badInput}</Note>}
        {noRate === "past" && <Note tone="watch" data-ui-v2="rec-no-rate" data-why="past">{C.rec.noPastRate}</Note>}
        {noRate === "today" && (C.rec.noTodayRate || (load.fresh && load.fresh.stale)) && (
          <Note tone="watch" data-ui-v2="rec-no-rate" data-why="today">{C.rec.noTodayRate || staleText(load.fresh.days)}</Note>
        )}
        <div style={{ marginTop: SPACE(4) }}><Button onClick={save}>{P.save}</Button></div>
      </div>
    </BottomSheet>
  );
}

