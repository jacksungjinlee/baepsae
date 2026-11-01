// 후보 고르기: top 2 x N candidates per market, N pre-selected; max 2 per industry group; 회사 단계 hidden (v18.0).
// 주의할 점 always shown when a check finds something; receipts show the inputs with their report year.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { StatusChip, Collapsible } from "../ui/components.jsx";
import { NA, canAdd, cautionContext, cautions, fyOf, isFin, num, marketsOf, CARDS } from "./engine.js";
import { C, fill, nf, p1, mdText } from "./format.js";
import { Page, AppBar, ScreenTitle, DateLine, Footer, Note, Card, ActionBar, tx, tap } from "./ui.jsx";
import { deckState, deckDisplayName, cautionTexts } from "./deckcalc.js";

export function Pick({ load, builder, setBuilder }) {
  const st = builder.settings;
  const ds = useMemo(() => deckState(load, st), [load, st]);
  const ctx = useMemo(() => cautionContext(load.data.stocks), [load]);
  const [msg, setMsg] = useState(null);
  const picks = builder.picks || [];
  const all = Object.values(ds.cands).flat();
  const pickedStocks = picks.map((t) => load.byT.get(t)).filter(Boolean);
  const N = st.count;
  const total = picks.length + ds.pinned.length;
  const full = Object.keys(ds.cands).every((mk) => picks.filter((t) => (load.byT.get(t) || {}).cls === mk).length === (ds.counts[mk] || 0));
  const two = marketsOf(st).length === 2;
  const back = () => { setBuilder((b) => ({ ...b, stage: "steps", step: 3 })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const toggle = (c) => {
    if (picks.includes(c.t)) { setMsg(null); setBuilder((b) => ({ ...b, picks: picks.filter((t) => t !== c.t) })); return; }
    const why = canAdd(c.s, pickedStocks, ds.pinned, ds.counts, ds.settings);
    if (why === "market") { setMsg(fill(C.pick.limitN, { n: ds.counts[c.s.cls] })); return; }
    if (why === "industry") { setMsg(C.pick.limitInd); return; }
    if (why === "indCap") { setMsg(fill(C.plan.clashParts.ind, { ind: c.s.indName })); return; }
    setMsg(null);
    setBuilder((b) => ({ ...b, picks: [...picks, c.t] }));
  };
  const toPlan = () => { setBuilder((b) => ({ ...b, stage: "plan" })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const deckLine = [deckDisplayName(st), fill(C.app.stocksN, { n: N })].join(" · ");
  return (
    <Page pad={SPACE(30)}>
      <AppBar onBack={back} backLabel={C.pick.back} />
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(1) })}>{C.pick.title}</div>
      <DateLine date={load.data.pxDate} fresh={load.fresh} />
      {ds.cands.us && ds.cands.us.length > 0 && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate && (
        <Note style={{ marginTop: 0 }}>{fill(C.app.usClose, { md: mdText(load.data.usPxDate) })}</Note>
      )}
      <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>{deckLine}</div>
      <ScreenTitle sub={C.pick.body}>{fill(C.pick.heading, { n: N })}</ScreenTitle>
      {msg && <Note tone="watch" data-ui-v2="pick-limit">{msg}</Note>}
      {ds.pinned.map((s) => (
        <Candidate key={s.t} c={{ t: s.t, s, scores: {}, total: null }} pinned load={load} st={st} ctx={ctx} />
      ))}
      {Object.keys(ds.cands).map((mk) => (
        <section key={mk} data-market={mk}>
          {two && (
            <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(5) })}>
              <span>{C.pick.market[mk]}</span>{" "}
              <span>{picks.filter((t) => (load.byT.get(t) || {}).cls === mk).length}</span>{" / "}<span>{fill(C.app.count, { count: ds.counts[mk] })}</span>
            </div>
          )}
          {ds.cands[mk].map((c) => (
            <Candidate key={c.t} c={c} picked={picks.includes(c.t)} onToggle={() => toggle(c)} load={load} st={st} ctx={ctx} />
          ))}
        </section>
      ))}
      <Footer />
      <ActionBar summary={<span><span>{C.pick.picked}</span>{" "}<b style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{total}</b>{" / "}<span>{fill(C.app.count, { count: N })}</span></span>}
        action={full ? C.pick.makePlan : fill(C.pick.chooseN, { n: N })} disabled={!full} onAction={toPlan} />
    </Page>
  );
}

// One candidate. pinned = a 꼭 담을 종목: no score (it skipped screening), labelled 고정 · 검증 안 함, cautions still shown.
function Candidate({ c, picked, onToggle, load, st, ctx, pinned }) {
  const s = c.s;
  const co = load.coByT.get(s.t) || null;
  const cau = cautions(s, co, ctx);
  const lines = cau.items.flatMap((x) => cautionTexts(x, s).map((t, i) => ({ t, body: i > 0 })));
  // debt, revenue and dividends come from the annual report: say which year (KR, DART)
  const annualFy = s.cls === "kr" && cau.items.some((x) => ["debtHigh", "revFall", "divDrop", "opFall"].includes(x.code)) ? fyOf(s, co) : null;
  const ranked = Object.entries(c.scores).filter(([, v]) => v !== NA).sort((a, b) => (st.points[b[0]] || 0) * b[1] - (st.points[a[0]] || 0) * a[1]).slice(0, 2);
  const indLine = s.cls === "us" ? (s.indName ? fill(C.pick.usInd, { ind: s.indName }) : null) : s.indName || null;
  return (
    <Card data-cand={pinned ? undefined : s.t} data-pinned={pinned ? s.t : undefined} data-picked={picked ? "1" : "0"}
      style={{ border: picked || pinned ? `2px solid ${COLOR.ink}` : `2px solid transparent` }}>
      <div style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{s.nk}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE(2), alignItems: "center", marginTop: SPACE(1) }}>
            {pinned ? <><StatusChip tone="neutral">{C.build.s4.fixed}</StatusChip><StatusChip tone="watch">{C.pick.unverified}</StatusChip></>
              : <StatusChip tone="neutral">{fill(C.build.s1.score, { score: Math.round(c.total) })}</StatusChip>}
            {indLine && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{indLine}</span>}
          </div>
          <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>
            {ranked.map(([id, v], i) => <span key={id}>{i ? " · " : ""}<span>{C.build.cards[id].name}</span>{" "}<span>{fill(C.build.s1.score, { score: Math.round(v) })}</span></span>)}
          </div>
        </div>
        {!pinned && (
          <button type="button" onClick={onToggle} aria-pressed={picked} aria-label={fill(picked ? C.build.s4.removeAria : C.build.s4.addAria, { name: s.nk })}
            style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH + SPACE(4), borderRadius: RADIUS.sm, flexShrink: 0, padding: `0 ${SPACE(3)}px`,
              border: picked ? `1px solid ${COLOR.border}` : "none", background: picked ? COLOR.surface : COLOR.ink, ...tx(SIZE.xs, WEIGHT.bold, picked ? COLOR.ink : COLOR.surface) }}>
            {picked ? C.build.s4.remove : C.build.s4.add}
          </button>
        )}
      </div>
      {lines.length > 0 && (
        <div data-ui-v2="caution" style={{ marginTop: SPACE(2), background: COLOR.watchBg, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px` }}>
          {lines.map((l, i) => (
            <div key={i} style={tx(SIZE.xs, l.body ? WEIGHT.regular : WEIGHT.semi, COLOR.watch)}>{l.body ? l.t : fill(C.pick.worry, { worry: l.t })}</div>
          ))}
          {annualFy != null && <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.watch)}>{fill(C.app.reportYear, { year: annualFy })}</div>}
        </div>
      )}
      {!lines.length && C.pick.caution.checksRun && <Note data-ui-v2="caution-none">{fill(C.pick.caution.checksRun, { checks: cau.ran.join(" · ") })}</Note>}
      <div style={{ marginTop: SPACE(2) }}>
        <Collapsible title={C.pick.receipts}>
          <Receipts s={s} co={co} c={c} st={st} />
        </Collapsible>
      </div>
    </Card>
  );
}

function Row({ k, v }) {
  return (
    <div style={{ display: "flex", gap: SPACE(3), padding: `${SPACE(1)}px 0` }}>
      <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text3, { width: SPACE(24), flexShrink: 0 })}>{k}</span>
      <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.ink)}>{v}</span>
    </div>
  );
}

function Receipts({ s, co, c, st }) {
  const R = C.pick.receipt;
  const pbr = num(s.pbr), roe = num(s.roe), debt = num(s.debt);
  const y = s.cls === "kr" ? (num(s.dps) != null && s.price > 0 ? (s.dps / s.price) * 100 : null) : num(s.dy);
  const fy = s.cls === "kr" ? fyOf(s, co) : null;
  const growth = num(s.g3), growthLabel = s.cls === "us" ? R.growthUs : R.growthKr;
  return (
    <div data-ui-v2="receipts">
      {c.total != null && CARDS.filter((x) => !x.pending && (st.points[x.id] || 0) > 0).map((x) => (
        <Row key={x.id} k={C.build.cards[x.id].name} v={c.scores[x.id] === NA ? C.build.s1.finNA : fill(C.build.s1.score, { score: Math.round(c.scores[x.id]) })} />
      ))}
      {pbr != null && <Row k="PBR" v={fill(R.times, { x: nf(pbr, 2) })} />}
      {y != null && (s.cls === "us" || fy != null) && <Row k={R.yield} v={`${p1(y)}%`} />}
      {roe != null && (s.cls === "us" || fy != null) && <Row k="ROE" v={`${p1(roe)}%`} />}
      {debt != null && s.cls === "kr" && fy != null && <Row k={R.debt} v={isFin(s) ? C.build.s1.finNA : `${nf(Math.round(debt))}%`} />}
      {debt != null && s.cls === "us" && R.debtUs && <Row k={R.debtUs} v={isFin(s) ? C.build.s1.finNA : `${nf(Math.round(debt))}%`} />}
      {growth != null && growthLabel && <Row k={growthLabel} v={`${p1(growth)}%`} />}
      {fy != null && <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(1) })}>{fill(C.app.reportYear, { year: fy })}</div>}
    </div>
  );
}
