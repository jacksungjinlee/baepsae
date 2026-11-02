// 덱 짜기: 시작 · 기준 · 빼기 · 조건 (테마 is hidden in the beta; 꼭 담을 종목 lives in 조건), then 후보 고르기 and
// 매수 계획 · 샀어요. A live count of candidates sits in the bottom bar.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Segmented, Stepper, MoneyInput, StatusChip } from "../ui/components.jsx";
import {
  CARDS, DECKS, STRICT, MIX, METHODS, MAX_PCTS, CUSHIONS, EXCLUDE_LIVE, EXCLUDE_PENDING, POINTS_TOTAL, POINTS_MAX, COUNT_RANGE,
  MIN_PER_STOCK_MAN, applyDeck, defaultSettings, activeCards, pointsUsed, strictTop, topOverall, bestCard,
  marketsOf, canPin, PINNED_MAX,
} from "./engine.js";
import { C, fill, nf, manText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, PendingChip, Footer, Note, Label, Toggle, ActionBar, TextInput, ChoiceGrid, OldAppNote, tx, tap } from "./ui.jsx";
import { deckState, defaultPicks, pickItems, computePlan, pinnable, aboutWon, cushionStocks, clashPieces } from "./deckcalc.js";
import { Pick } from "./pick.jsx";
import { Plan } from "./plan.jsx";

export const STEPS = ["start", "cards", "exclude", "terms"];
export const newBuilder = () => ({ step: 0, stage: "steps", settings: defaultSettings(), picks: null });

export function Build({ load, builder, setBuilder, onExit, store, setStoreData, goToday }) {
  if (load.status !== "ok" || load.missing.length) {
    return (
      <Page>
        <AppBar onBack={onExit} backLabel={C.build.backToday} search />
        <ScreenTitle>{C.build.title}</ScreenTitle>
        {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        {load.status === "fail" && <LoadFail />}
        {load.status === "ok" && <Card data-ui-v2="build-not-ready"><PendingChip /></Card>}
        <Footer />
      </Page>
    );
  }
  if (builder.stage === "pick") return <Pick load={load} builder={builder} setBuilder={setBuilder} />;
  if (builder.stage === "plan") return <Plan load={load} builder={builder} setBuilder={setBuilder} store={store} setStoreData={setStoreData} goToday={goToday} />;
  return <Steps load={load} builder={builder} setBuilder={setBuilder} onExit={onExit} />;
}

function StepDots({ step }) {
  return (
    <ol aria-label={C.build.stepsAria} style={{ listStyle: "none", display: "flex", gap: SPACE(2), padding: 0, margin: `${SPACE(3)}px 0 0` }}>
      {STEPS.map((k, i) => (
        <li key={k} aria-current={i === step ? "step" : undefined} style={{ flex: 1 }}>
          <div style={{ height: SPACE(1), borderRadius: 2, background: i <= step ? COLOR.ink : COLOR.border }} />
          <div style={tx(SIZE.xxs, i === step ? WEIGHT.heavy : WEIGHT.semi, i === step ? COLOR.ink : COLOR.text2, { marginTop: SPACE(1) })}>{C.build.steps[k]}</div>
        </li>
      ))}
    </ol>
  );
}

function Option({ title, sub, onClick, id }) {
  return (
    <button type="button" data-deck={id} onClick={onClick}
      style={{ ...tap, width: "100%", textAlign: "left", border: `1px solid ${COLOR.border}`, background: COLOR.surface, borderRadius: RADIUS.md,
        padding: `${SPACE(3)}px ${SPACE(4)}px`, marginTop: SPACE(2), display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(4) }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.body, WEIGHT.bold, COLOR.ink, { display: "block" })}>{title}</span>
        <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{sub}</span>
      </span>
      <Icon name="chevronRight" size={20} color={COLOR.text2} />
    </button>
  );
}

function Steps({ load, builder, setBuilder, onExit }) {
  const st = builder.settings;
  const step = builder.step;
  const set = (patch) => setBuilder((b) => ({ ...b, settings: { ...b.settings, ...patch }, picks: null }));
  const go = (n) => { setBuilder((b) => ({ ...b, step: n })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const ds = useMemo(() => deckState(load, st), [load, st]);
  const active = activeCards(st.points);
  const noCards = !active.length;
  const last = step === STEPS.length - 1;
  // Steps 기준 and 빼기 stop only when nothing passes at all, so 종목 수 and 한국 : 미국 in 조건 stay reachable.
  // 조건 stops whenever 후보 고르기 could not be filled (a market short of survivors, or the industry limits).
  const lower = last ? ds.blocked : ds.res.survivors === 0;
  const blocked = noCards || lower;
  const restart = () => setBuilder(newBuilder());
  const start = (id) => { setBuilder((b) => ({ ...b, settings: applyDeck(b.settings, id), picks: null, step: 1 })); try { window.scrollTo(0, 0); } catch (e) { /* ignore */ } };
  const toPick = () => {
    setBuilder((b) => ({ ...b, stage: "pick", picks: defaultPicks(ds) }));
    try { window.scrollTo(0, 0); } catch (e) { /* ignore */ }
  };
  // A settings clash (e.g. 5 stocks x max 10%) is not fixed by lowering the criteria: the button stays "후보 n개 보기"
  // (off) and the clash line above names the limits. "기준을 낮춰 주세요" is only for too few survivors.
  const tooFew = last ? ds.check.block || ds.pre.short : ds.res.survivors === 0;
  const action = noCards ? C.build.pickCardsBtn : tooFew ? C.build.lowerBtn : last ? fill(C.build.seeCands, { shortN: ds.shortN }) : C.build.next;
  const summary = (
    <span data-ui-v2="match-count"><span>{C.build.matchSummary}</span>{" "}
      <b style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{fill(C.app.count, { count: nf(ds.res.survivors) })}</b></span>
  );
  return (
    <Page pad={SPACE(30)}>
      <AppBar onBack={step === 0 ? onExit : () => go(step - 1)} backLabel={step === 0 ? C.build.backToday : C.build.prevStep} search />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(2), marginTop: SPACE(1) }}>
        <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.build.title}</div>
        {step > 0 && <button type="button" onClick={restart} style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{C.build.restart}</button>}
      </div>
      <DateLine date={load.data.pxDate} fresh={load.fresh} />
      <StepDots step={step} />
      {step === 0 && <StepStart start={start} />}
      {step === 1 && <StepCards st={st} set={set} ds={ds} load={load} />}
      {step === 2 && <StepExclude st={st} set={set} ds={ds} />}
      {step === 3 && <StepTerms st={st} set={set} ds={ds} load={load} />}
      {step > 0 && !noCards && <SurvivorNotes ds={ds} two={marketsOf(st).length === 2} />}
      <Footer />
      {step > 0 && <ActionBar summary={summary} action={action} disabled={blocked} onAction={() => (last ? toPick() : go(step + 1))} />}
    </Page>
  );
}

// Per market: the market's own survivor count (a two-market deck names the market first).
function SurvivorNotes({ ds, two }) {
  return (
    <div data-ui-v2="survivor-notes">
      {ds.res.blanks > 0 && <Note data-ui-v2="blanks">{fill(C.build.s1.blanks, { n: nf(ds.res.blanks) })}</Note>}
      {ds.check.markets.map((m) => (
        <Note key={m.mk} tone="watch" data-ui-v2={m.state} data-market={m.mk}>
          {two && <span>{C.pick.market[m.mk]}{" · "}</span>}
          <span>{m.state === "zero" ? C.build.zero : m.state === "short" ? fill(C.build.short, { n: nf(m.have), need: m.need })
            : fill(C.build.few, { n: nf(m.have) })}</span>
        </Note>
      ))}
      {!ds.check.block && ds.pre.short && (
        <Note tone="watch" data-ui-v2="ind-block">
          {[...new Set(ds.pre.blocked.map((b) => (b.code === "indCap" && b.indName ? fill(C.plan.clashParts.ind, { ind: b.indName }) : C.pick.limitInd)))].map((t, i) => (
            <span key={i}>{i ? " · " : ""}{t}</span>
          ))}
          {" "}<span>{C.build.indFix}</span>
        </Note>
      )}
      {ds.clash && (
        <Note tone="watch" data-ui-v2="clash">
          {clashPieces(ds.clash).map((p, i) => <span key={i}>{i ? " · " : ""}{p.map((x, j) => <span key={j}>{j ? " " : ""}{x}</span>)}</span>)}
          {C.plan.clash && <span>{" "}{C.plan.clash}</span>}
        </Note>
      )}
    </div>
  );
}

function StepStart({ start }) {
  const s0 = C.build.s0;
  return (
    <div>
      <div style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}><ScreenTitle sub={s0.body}>{s0.title}</ScreenTitle></div>
        <img src="baepi-4.png" alt={s0.imgAlt} width={72} height={72} style={{ objectFit: "contain", marginTop: SPACE(2) }} />
      </div>
      <OldAppNote />
      <div style={{ marginTop: SPACE(3) }}>
        <Option id="blank" title={s0.blank} sub={s0.blankSub} onClick={() => start(null)} />
        {DECKS.filter((d) => !d.hidden).map((d) => (
          <Option key={d.id} id={d.id} title={C.build.decks[d.id].name} sub={C.build.decks[d.id].sub} onClick={() => start(d.id)} />
        ))}
      </div>
    </div>
  );
}

function StepCards({ st, set, ds }) {
  const s1 = C.build.s1;
  const used = pointsUsed(st.points);
  const left = POINTS_TOTAL - used;
  const top = strictTop(st.strict);
  const setPts = (id, v) => set({ points: { ...st.points, [id]: v } });
  const preview = topOverall(ds.res, 3);
  return (
    <div>
      <ScreenTitle sub={s1.body}>{s1.title}</ScreenTitle>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{s1.pointsLeft}</span>
          <span data-ui-v2="points-left" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}>{left}</span>
        </div>
        {CARDS.map((c) => {
          const cc = C.build.cards[c.id];
          const pts = st.points[c.id] || 0;
          const name = (
            <span style={{ display: "block" }}>
              <span style={tx(SIZE.body, WEIGHT.bold, COLOR.ink, { display: "block" })}>{cc.name}</span>
              {cc.basis && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{cc.basis}</span>}
              <span style={{ display: "flex", flexWrap: "wrap", gap: SPACE(1), marginTop: SPACE(1) }}>
                {c.pending && <PendingChip />}
                {!c.pending && pts > 0 && top != null && <StatusChip tone="neutral">{fill(s1.topPct, { pct: top })}</StatusChip>}
              </span>
              {c.id === "stable" && pts > 0 && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{s1.finNA}</span>}
            </span>
          );
          return (
            <div key={c.id} data-card={c.id} style={{ borderTop: `1px solid ${COLOR.line}`, padding: `${SPACE(3)}px 0`, marginTop: SPACE(2) }}>
              {c.pending ? name : (
                <Stepper value={pts} min={0} max={Math.min(POINTS_MAX, pts + left)} onChange={(v) => setPts(c.id, v)} label={name}
                  decLabel={fill(s1.dec, { card: cc.name })} incLabel={fill(s1.inc, { card: cc.name, n: pts })} />
              )}
            </div>
          );
        })}
      </Card>
      <Card>
        <Label>{s1.strictLabel}</Label>
        <Segmented label={s1.strictAria} value={st.strict} onChange={(v) => set({ strict: v })}
          options={STRICT.map((x) => ({ value: x.id, label: s1.strict[x.id] }))} />
        <Note>{top == null ? s1.looseNote : fill(s1.strictNote, { pct: top })}</Note>
      </Card>
      {activeCards(st.points).length > 0 && (
        <Card data-ui-v2="preview">
          <Label>{s1.preview}</Label>
          {!preview.length && <Note>{s1.previewNone}</Note>}
          {preview.map((x) => {
            const b = bestCard(x, st.points);
            return (
              <div key={x.t} style={{ display: "flex", justifyContent: "space-between", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderTop: `1px solid ${COLOR.line}` }}>
                <span style={{ minWidth: 0 }}>
                  <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{x.s.nk}</span>
                  {b && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}><span>{C.build.cards[b.id].name}</span>{" "}<span>{fill(s1.score, { score: Math.round(b.score) })}</span></span>}
                </span>
                <span data-ui-v2="preview-score" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { flexShrink: 0 })}>{fill(s1.score, { score: Math.round(x.total) })}</span>
              </div>
            );
          })}
        </Card>
      )}
    </div>
  );
}

function StepExclude({ st, set, ds }) {
  const s3 = C.build.s3;
  const order = ["warned", "loss", "young", "debt", "noDiv", "china", "sin", "holding"];
  return (
    <div>
      <ScreenTitle sub={s3.body}>{s3.title}</ScreenTitle>
      <Card style={{ paddingTop: SPACE(2), paddingBottom: SPACE(2) }}>
        {order.map((k) => {
          const sw = s3.switches[k];
          if (EXCLUDE_PENDING.includes(k)) return <Toggle key={k} on={false} disabled label={sw.name} sub={sw.sub} chip={<PendingChip />} onChange={() => {}} />;
          if (!EXCLUDE_LIVE.includes(k)) return null;
          return <Toggle key={k} on={!!st.exclude[k]} label={sw.name} sub={sw.sub} side={fill(C.app.count, { count: nf(ds.res.excludeCounts[k]) })}
            onChange={(v) => set({ exclude: { ...st.exclude, [k]: v } })} />;
        })}
      </Card>
      <Note>{s3.liquidity}</Note>
    </div>
  );
}

function StepTerms({ st, set, ds, load }) {
  const s4 = C.build.s4;
  const amt = st.amountMan;
  const warning = !amt ? s4.amountEmpty : amt < 50 ? s4.under50 : amt > 100000 ? s4.over10 : null;
  const maxN = Math.floor(amt / MIN_PER_STOCK_MAN);
  const mk = marketsOf(st);
  const [q, setQ] = useState("");
  const results = pinnable(load, q, st.pinned);
  const [pinMsg, setPinMsg] = useState(null);
  const cushionOk = cushionStocks(load).length > 0;
  const pin = (s) => {
    const why = canPin(s, ds.pinned);
    if (why === "industry") { setPinMsg(C.pick.limitInd); return; }
    if (why) return;
    setPinMsg(null);
    set({ pinned: [...st.pinned, s.t] });
    setQ("");
  };
  // 2022 line per sizing choice, from the list that 후보 고르기 would pre-select
  const y2022 = useMemo(() => {
    if (!(amt > 0)) return null;
    const picks = pickItems(ds, defaultPicks(ds));
    const out = {};
    for (const m of METHODS) {
      const r = computePlan(load, { ...st, method: m }, picks, ds.pinned);
      out[m] = r.ok && r.y2022.ok ? r.y2022.won : null;
    }
    return Object.values(out).every((v) => v != null) ? out : "hide";
  }, [ds, st, load, amt]);
  return (
    <div>
      <ScreenTitle>{s4.title}</ScreenTitle>
      <Card>
        <MoneyInput label={s4.amountLabel} unit={C.app.manUnit} value={amt} onChange={(v) => set({ amountMan: v })}
          quick={[{ label: s4.quick[0], add: 10 }, { label: s4.quick[1], add: 100 }, { label: s4.quick[2], add: 1000 }]} clearLabel={s4.clear} warning={warning} />
        {amt >= 50 && amt <= 100000 && <Note>{fill(s4.perStock, { x: manText(nf(Math.round(amt / st.count))) })}</Note>}
      </Card>
      <Card>
        <Label>{s4.mixLabel}</Label>
        <ChoiceGrid label={s4.mixAria} value={st.mix} onChange={(v) => set({ mix: v })} options={MIX.map((x) => ({ value: x.id, label: s4.mix[x.id] }))} />
        {mk.includes("us") && <Note>{s4.usWhole}</Note>}
      </Card>
      <Card>
        <Stepper value={st.count} min={Math.max(COUNT_RANGE[0], st.pinned.length + 1)} max={COUNT_RANGE[1]} onChange={(v) => set({ count: v })}
          label={s4.countLabel} format={C.app.count} decLabel={s4.countDec} incLabel={s4.countInc} />
        <Note>{s4.countNote}</Note>
        {amt > 0 && st.count > maxN && <Note tone="watch" data-ui-v2="too-many">{fill(s4.tooMany, { amount: manText(nf(amt)), n: Math.max(0, maxN) })}</Note>}
      </Card>
      <Card data-ui-v2="pinned">
        <Label style={{ marginBottom: 0 }}>{s4.pinnedTitle}</Label>
        <Note style={{ marginTop: SPACE(1) }}>{s4.pinnedBody}</Note>
        {st.pinned.map((t) => {
          const s = load.byT.get(t);
          if (!s) return null;
          return (
            <div key={t} style={{ display: "flex", alignItems: "center", gap: SPACE(2), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0 })}>{s.nk}</span>
              <span data-ui-v2="manual-chip"><StatusChip tone="neutral">{C.pick.manual}</StatusChip></span>
              <button type="button" aria-label={fill(s4.removeAria, { name: s.nk })} onClick={() => set({ pinned: st.pinned.filter((x) => x !== t) })}
                style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: "none", background: "none", ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{s4.remove}</button>
            </div>
          );
        })}
        {pinMsg && <Note tone="watch" data-ui-v2="pin-limit">{pinMsg}</Note>}
        {st.pinned.length < PINNED_MAX && (
          <>
            <TextInput label={null} ariaLabel={s4.pinnedTitle} value={q} onChange={setQ} />
            {results.map((s) => (
              <div key={s.t} style={{ display: "flex", alignItems: "center", gap: SPACE(2), padding: `${SPACE(1)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block" })}>{s.nk}</span>
                  <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{s.t}</span>
                </span>
                <button type="button" aria-label={fill(s4.addAria, { name: s.nk })} disabled={st.count <= st.pinned.length + 1}
                  onClick={() => pin(s)}
                  style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, background: COLOR.surface, padding: `0 ${SPACE(3)}px`, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{s4.add}</button>
              </div>
            ))}
          </>
        )}
      </Card>
      <Card>
        <Label>{s4.methodLabel}</Label>
        <Segmented label={s4.methodLabel} value={st.method} onChange={(v) => set({ method: v })} options={METHODS.map((m) => ({ value: m, label: s4.method[m] }))} />
        <Note>{s4.methodNote[st.method]}</Note>
        {y2022 !== "hide" && (
          <div data-ui-v2="y2022-methods" style={{ marginTop: SPACE(3) }}>
            <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink)}>{s4.y2022Label}</div>
            {!y2022 ? <Note>{s4.y2022Empty}</Note> : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: SPACE(1), marginTop: SPACE(1) }}>
                {METHODS.map((m) => (
                  <div key={m} style={tx(SIZE.xs, m === st.method ? WEIGHT.heavy : WEIGHT.regular, m === st.method ? COLOR.ink : COLOR.text2, { textAlign: "center" })}>{aboutWon(y2022[m])}</div>
                ))}
              </div>
            )}
          </div>
        )}
        <div style={{ display: "flex", gap: SPACE(2), alignItems: "flex-start", marginTop: SPACE(3) }}>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { flex: 1 })}>{s4.eventNote}</span>
          <PendingChip />
        </div>
      </Card>
      <Card>
        <Label>{s4.maxLabel}</Label>
        <Segmented label={s4.maxLabel} value={st.maxPct} onChange={(v) => set({ maxPct: v })} options={MAX_PCTS.map((p) => ({ value: p, label: `${p}%` }))} />
      </Card>
      {cushionOk && (
        <Card>
          <Label>{s4.cushionLabel}</Label>
          <Segmented label={s4.cushionAria} value={st.cushion} onChange={(v) => set({ cushion: v })}
            options={CUSHIONS.map((p) => ({ value: p, label: p === 0 ? C.app.none : `${p}%` }))} />
          <Note>{s4.cushionNote}</Note>
        </Card>
      )}
      <Card>
        <TextInput label={s4.nameLabel} value={st.name} onChange={(v) => set({ name: v.slice(0, 30) })} />
      </Card>
    </div>
  );
}

