// 왜 움직였나 (v18.3 Part E): one held stock, one day. Reached from 오늘: the 크게 움직인 종목 note (자세히 보기) and a
// big mover's row in my stocks. REDESIGN 3: header (name, industry, official close, change, date), the verdict band,
// then the checks:
//   1. 이 종목만 빠진 게 아니에요: every stock of the same real industry group (5+ members, same market) today, mine
//      highlighted, group average marked. Never for a missing, "other" or "etc" group.
//   2. (news, v18.4) hidden.
//   3. 내 규칙: the rule book with today's results (Part C), the explainer folded.
// 다음에 확인할 일 and the "past big days" fold wait for v18.0. Sources are folded at the bottom.
// A price move is never a rule: the verdict comes from the daily check only.
import React from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS } from "../ui/tokens.js";
import { HeroBand, DotStrip, Collapsible, StatusChip } from "../ui/components.jsx";
import { hasGroup } from "./engine.js";
import { C, fill, mdText, priceText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, Footer, tx } from "./ui.jsx";
import { StatusLines, HoldingRules } from "./daily.jsx";
import { signedPct } from "./deckcalc.js";
import { peerGroup, keptCount } from "./track.js";
import { useDaily, confirmer, brokenTitle } from "./today.jsx";

const R = () => C.plan.rules;
const BAND = ["low", "high", "trim"];

// Rules with approved wording that the rule book shows (keptCount counts only those).
const kept = (x) => keptCount(x, { roe: !!R().roeLimit, op: !!R().opLimit });

const pendingCount = (x) => (x.rules || []).filter((r) => r.result === "pending").length;

function Verdict({ x, g, names, onConfirm }) {
  const nc = pendingCount(x);
  const ncLine = nc > 0 ? <span style={{ display: "block" }} data-ui-v2="why-not-checked">{fill(C.daily.notChecked, { n: nc })}</span> : null;
  if (x.status === "none" || BAND.includes(x.status)) {
    const k = kept(x);
    const together = g.ok && g.together;
    let title = together ? C.why.together : k ? fill(C.why.keptTitle, { n: k }) : null;
    const calm = x.status === "none";
    const eyebrow = calm && title ? C.why.noTodo : undefined;
    if (!title) title = calm ? C.why.noTodo : x.nk;
    return (
      <div style={{ marginTop: SPACE(4) }} data-ui-v2="why-verdict" data-status={x.status}>
        <HeroBand tone={x.status === "trim" ? "alert" : "calm"} eyebrow={eyebrow} title={title}
          body={together && k ? <><span style={{ display: "block" }}>{fill(C.why.keptBody, { n: k })}</span>{ncLine}</> : ncLine}
          image={calm ? "baepi-1.png" : undefined} imageAlt={calm ? C.why.alt : undefined}
          inset={calm ? null : <StatusLines x={x} names={names} />} />
      </div>
    );
  }
  const eyebrow = x.status === "broken" ? C.daily.broken : x.status === "check" && C.daily.check ? C.daily.check : C.daily.watch;
  return (
    <div style={{ marginTop: SPACE(4) }} data-ui-v2="why-verdict" data-status={x.status}>
      <HeroBand tone="alert" eyebrow={eyebrow} title={x.status === "broken" ? brokenTitle(x.nk) : x.nk} body={ncLine}
        image={x.status === "watch" ? undefined : "baepi-4.png"} imageAlt={x.status === "watch" ? undefined : C.today.todoAlt}
        inset={<StatusLines x={x} names={names} onConfirm={onConfirm} />} />
    </div>
  );
}

function Check({ n, title, children, ...rest }) {
  return (
    <Card {...rest}>
      <div style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start" }}>
        <span aria-hidden="true" style={{ width: SPACE(7), height: SPACE(7), borderRadius: 999, background: COLOR.ink, flexShrink: 0,
          display: "flex", alignItems: "center", justifyContent: "center", ...tx(SIZE.xs, WEIGHT.heavy, COLOR.surface) }}>{n}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          {title && <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.4 })}>{title}</h3>}
          {children}
        </div>
      </div>
    </Card>
  );
}

function Explainer() {
  const arrow = <span aria-hidden="true" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text3)}>{"→"}</span>;
  return (
    <div style={{ marginTop: SPACE(3) }}>
      <Collapsible title={C.why.explainTitle}>
        <div data-ui-v2="why-explain" style={{ display: "flex", flexWrap: "wrap", gap: SPACE(2), alignItems: "center" }}>
          <StatusChip tone="ok">{C.daily.ok}</StatusChip>{arrow}<StatusChip tone="watch">{C.daily.watch}</StatusChip>{arrow}
          <StatusChip tone="broken">{C.daily.broken}</StatusChip>
        </div>
        <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{C.why.explainBody}</p>
      </Collapsible>
    </div>
  );
}

function Sources({ s, g, x, md }) {
  const fy = (x.rules || []).reduce((a, r) => (Number.isInteger(r.fy) && (a == null || r.fy > a) ? r.fy : a), null);
  const rows = [
    s.cls === "kr" ? [C.why.srcPrice, fill(C.why.srcPriceKr, { md })] : C.why.srcPriceUs ? [C.why.srcPrice, fill(C.why.srcPriceUs, { md })] : null,
    g.ok ? [C.why.srcInd, fill(C.why.srcIndN, { ind: s.indName, n: g.n })] : null,
    fy ? [C.why.srcRules, fill(C.app.reportYear, { year: fy })] : null,
  ].filter(Boolean);
  if (!rows.length) return null;
  return (
    <Card data-ui-v2="why-sources">
      <Collapsible title={C.why.sources}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: "flex", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
            <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { width: SPACE(16), flexShrink: 0 })}>{k}</span>
            <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { minWidth: 0 })}>{v}</span>
          </div>
        ))}
      </Collapsible>
    </Card>
  );
}

export function Why({ load, store, setStoreData, target, onBack, pad }) {
  const { ev } = useDaily(load, store);
  const de = ev.ok && target ? ev.decks.find((d) => d.id === target.deckId) : null;
  const x = de && de.ok ? de.holdings.find((h) => h.t === target.t) || null : null;
  const s = x && load.status === "ok" ? load.byT.get(x.t) : null;
  const deck = de ? store.data.decks.find((d) => d.id === de.id) : null;
  if (!x || !s || !deck) {
    return <Page pad={pad}><AppBar onBack={onBack} backLabel={C.build.backToday} /><Footer /></Page>;
  }
  const names = new Map(deck.holdings.map((h) => [h.t, h.nk]));
  const conf = confirmer(store, setStoreData);
  const g = peerGroup(s, load.data.stocks);
  const md = mdText(s.cls === "us" ? load.data.usPxDate || load.data.pxDate : load.data.pxDate);
  // Today's change as the data gives it (d1, % between official closes). The won change is not shown: worked back from
  // a rounded percentage it would look exact and be off by a few won.
  const d1 = typeof s.d1 === "number" && Number.isFinite(s.d1) ? s.d1 : null;
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.build.backToday} />
      <ScreenTitle>{fill(C.why.title, { name: x.nk })}</ScreenTitle>
      <div data-ui-v2="why-head" style={{ marginTop: SPACE(1) }}>
        <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>
          {hasGroup(s) && s.indName ? <><span>{s.indName}</span>{" · "}</> : null}<span>{fill(C.why.close, { md })}</span>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(1) }}>
          <span style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink)}>{priceText(s)}</span>
          {d1 != null && <span data-ui-v2="why-change" style={tx(SIZE.sm, WEIGHT.bold, d1 < 0 ? COLOR.down : d1 > 0 ? COLOR.upOnPage : COLOR.text2)}>
            {signedPct(d1)}</span>}
        </div>
      </div>
      <Verdict x={x} g={g} names={names} onConfirm={(item, answer) => conf(deck.id, item, answer)} />
      {g.ok && (
        <Check n={1} title={g.together ? C.why.c1Title : null} data-ui-v2="why-peers">
          <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: g.together ? SPACE(1) : 0 })}>
            {fill(C.why.c1Body, { ind: s.indName, n: g.n, k: g.fell })}</p>
          <div style={{ marginTop: SPACE(2), background: COLOR.surface, borderRadius: RADIUS.sm }}>
            <DotStrip items={g.items} mine={x.t} avgLabel={C.why.avg} mineLabel={fill(C.why.mine, { name: x.nk })}
              aria={fill(C.why.c1Aria, { ind: s.indName, n: g.n, name: x.nk, pct: signedPct(d1), avg: signedPct(g.avg) })} />
          </div>
        </Check>
      )}
      <Check n={g.ok ? 2 : 1} title={kept(x) ? fill(C.why.keptTitle, { n: kept(x) }) : R().title} data-ui-v2="why-rules">
        <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{C.why.alertLine}</p>
        <HoldingRules x={x} names={names} />
        <Explainer />
      </Check>
      <Sources s={s} g={g} x={x} md={md} />
      <Footer />
    </Page>
  );
}
