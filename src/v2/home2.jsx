// ================= 홈 for returning visitors (v19.3e, v19.3 Part H, board Home2), behind today.jsx HOME2 =================
// Per portfolio that holds something today (the same portfolios 홈 showed before, in store order; home.js):
//   1. the hero (navy): "{date} 종가로 점검했어요", "내 규칙 {n}개 중 {k}개를 지키고 있어요" (n = the rules that could be
//      checked), four rule tiles with ✓, ! or "확인하지 못했어요", the first broken concentration rule as one sentence and
//      "아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요" for the rules that could not be checked. With two or more portfolios
//      each hero starts with its portfolio's name (user text) so the heroes can be told apart.
//   2. the portfolio card: value, "오늘 {±amount} ({±%})", "산 가격보다 {±amount} ({±%}) · 평균 단가를 넣은 {n}종목 기준"
//      (only holdings with a 평균 단가, and only when there is one), "미국 종목은 달러로 계산한 수익을 오늘 환율로 바꿨어요."
//      when a dollar 평균 단가 was converted at today's rate; the price date at the top right. No chart (Part H: until daily
//      price history exists).
//   3. 가진 종목 {n}개 · 비중 · 오늘: mark, name, weight bar in the navy shades by weight (Part C; a full bar = the 한 종목
//      limit, as on the board), weight %, today's change (price red/blue, true minus sign). A built portfolio keeps its
//      per-stock chips (규칙 깨짐 · 확인 필요 · …) and its "아직 자동으로 확인하지 못하는 규칙" line for per-stock rules.
// Then 오늘 볼 것 (only when there is something): every built portfolio's 규칙 깨짐 / 확인 필요 items first (the band that sat
// at the top of 홈 before, with its answers), then one concentration card per portfolio whose 한 업종 rule broke ("{group}
// {x}%" / "{names} · 내 규칙은 {limit}%까지"), then 크게 움직인 종목. Filings join in v19.6b (disc.json is not loaded on 홈).
// 시장 한눈에 unchanged. Stale data: the stale band only, nothing checked, never a ✓ (the daily check is not ok, so no block
// exists). Failed: the load-failure message. No 뱁이 anywhere here (numbers). The account banner waits for v19.4.
import React, { useMemo } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, holdingShades, HOLDING_SHADES } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { HeroBand, Amount, Button } from "../ui/components.jsx";
import { C, fill, mdText, wonText } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, Note, Cols, useNav, tx, tap } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { isCompany } from "./stocklist.js";
import { shownName } from "./legacy.js";
import { MissingNote } from "./tracking.jsx";
import { statusChips } from "./daily.jsx";
import { signedPct } from "./deckcalc.js";
import { ruleLabel, ruleDetail, brokenLine, limitPct } from "./pfview.jsx";
import { usHeld, limitsOf } from "./pf.js";
import { homeBlocks, concentration, barOf, weightPct } from "./home.js";
import { TodoItem, BigMoves, MarketGlance, brokenTitle, isTodo, lines } from "./today.jsx";
import { todayCounts } from "./track.js";

const signedWon = (v) => (v > 0 ? "+" : "") + wonText(v);
const tone = (v) => (v > 0 ? COLOR.up : v < 0 ? COLOR.down : COLOR.text2);

// ---------------- the hero: the four portfolio rules ----------------
const RULE_ICON = { stock: "chart-pie-slice", ind: "buildings", fit: "clipboard-text", warn: "shield-check" };
function HeroTile({ r }) {
  const ok = r.state === "ok", broken = r.state === "broken";
  const detail = broken ? ruleDetail(r) : null;
  return (
    <div data-ui-v2="home-rule" data-rule={r.id} data-state={r.state}
      style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: SPACE(1) + 2, padding: `${SPACE(2) + 2}px 2px ${SPACE(2)}px`,
        borderRadius: RADIUS.md, background: broken ? "rgba(255,226,168,.18)" : "rgba(255,255,255,.08)", minWidth: 0 }}>
      <Icon name={RULE_ICON[r.id]} size={24} tone="onNavy" style={{ opacity: r.state === "unknown" ? 0.6 : 1 }} />
      <span style={tx(SIZE.xs, WEIGHT.semi, "#E3E7EE", { lineHeight: 1.3, textAlign: "center", wordBreak: "keep-all" })}>{ruleLabel(r)}</span>
      {r.state === "unknown" && <span data-ui-v2="home-rule-unknown" style={tx(SIZE.xs, WEIGHT.regular, "#CBD3DF", { lineHeight: 1.3, textAlign: "center", wordBreak: "keep-all" })}>{C.pfr.unknown}</span>}
      {detail && <span data-ui-v2="home-rule-detail" style={tx(SIZE.xs, WEIGHT.bold, "#FFE2A8", { lineHeight: 1.3, textAlign: "center", wordBreak: "keep-all" })}>{detail}</span>}
      {ok && (
        <span role="img" aria-label={C.daily.ok} style={{ position: "absolute", top: -4, right: -2, width: 20, height: 20, borderRadius: 10, background: COLOR.okBg,
          display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="check" size={14} tone="ok" /></span>
      )}
      {broken && (
        <span aria-hidden="true" style={{ position: "absolute", top: -4, right: -2, width: 20, height: 20, borderRadius: 10, background: "#FFE2A8",
          display: "flex", alignItems: "center", justifyContent: "center", ...tx(SIZE.xs, 900, COLOR.watch, { lineHeight: 1 }) }}>!</span>
      )}
    </div>
  );
}

function RulesHero({ block, many, narrow }) {
  const { st, deck } = block;
  if (!st || !st.ok) return null;
  const md = mdText(st.pxDate);
  const line = brokenLine(st);
  return (
    <section data-ui-v2="home-rules" data-deck-id={deck.id} data-kept={st.kept} data-checked={st.checked}
      style={{ marginTop: SPACE(4), background: COLOR.ink, color: COLOR.surface, borderRadius: RADIUS.lg + 2, padding: SPACE(4) + 2 }}>
      {many && <p data-ui-v2="home-rules-name" style={tx(SIZE.xs, WEIGHT.bold, COLOR.surface, { marginBottom: SPACE(1) })}>{shownName(deck.name)}</p>}
      {md && <p style={tx(SIZE.xs, WEIGHT.regular, "#CBD3DF")}>{fill(C.pfr.checked, { date: md })}</p>}
      {st.checked > 0 && <h2 data-ui-v2="home-kept" style={tx(21, WEIGHT.heavy, COLOR.surface, { marginTop: SPACE(1) + 2, lineHeight: 1.35, letterSpacing: "-0.02em", wordBreak: "keep-all" })}>
        {fill(C.pfr.kept, { n: st.checked, k: st.kept })}</h2>}
      <div style={{ marginTop: SPACE(3) + 2, display: "grid", gridTemplateColumns: `repeat(${narrow ? 2 : 4}, minmax(0, 1fr))`, gap: SPACE(1) + 2 }}>
        {st.rules.map((r) => <HeroTile key={r.id} r={r} />)}
      </div>
      {line && <p data-ui-v2="home-broken" style={tx(SIZE.xs, WEIGHT.semi, "#E3E7EE", { marginTop: SPACE(3) })}>{line}</p>}
      {st.unchecked > 0 && <p data-ui-v2="home-not-checked" style={tx(SIZE.xs, WEIGHT.regular, "#CBD3DF", { marginTop: SPACE(2) })}>{fill(C.daily.notChecked, { n: st.unchecked })}</p>}
    </section>
  );
}

// ---------------- the portfolio card ----------------
function MoneyCard({ block, pxDate }) {
  const { deck, money } = block;
  const md = mdText(pxDate);
  const H = C.home;
  return (
    <Card data-ui-v2="home-money" data-deck-id={deck.id} data-kind={deck.kind === "imported" ? "imported" : "built"} style={{ padding: `${SPACE(4)}px ${SPACE(4) + 2}px ${SPACE(3) + 2}px` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2) }}>
        <h3 style={tx(SIZE.sm, WEIGHT.bold, COLOR.text2, { minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{shownName(deck.name)}</h3>
        {md && <span data-ui-v2="home-money-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { whiteSpace: "nowrap" })}>{fill(C.why.close, { md })}</span>}
      </div>
      {money.ok && (
        <div style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(1) }}>
          <span data-ui-v2="home-value" data-v={Math.round(money.value)} style={tx(30, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.15, letterSpacing: "-0.02em" })}>
            <Amount text={wonText(money.value)} /></span>
          {money.day && H.day && (
            <span data-ui-v2="home-day" data-pct={Math.round(money.day.pct * 1000) / 1000} style={tx(SIZE.sm, WEIGHT.heavy, tone(Math.round(money.day.pct * 10)))}>
              {fill(H.day, { amount: signedWon(money.day.amount), pct: signedPct(money.day.pct) })}</span>
          )}
        </div>
      )}
      {money.ok && money.gain && H.gain && H.gainBasis && (
        <p data-ui-v2="home-gain" data-n={money.gain.n} data-ret={Math.round(money.gain.ret * 100000) / 1000} style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1) })}>
          {/* the approved piece stays one text, coloured by its sign as "오늘 …" is (price red/blue only for up/down) */}
          <b style={{ color: tone(Math.round(money.gain.ret * 1000)) }}>{fill(H.gain, { amount: signedWon(money.gain.gain), pct: signedPct(money.gain.ret * 100) })}</b>{" "}
          <span style={{ color: COLOR.text3 }}>{"· "}{fill(H.gainBasis, { n: money.gain.n })}</span>
        </p>
      )}
      {money.ok && money.gain && money.gain.usdToday && <Note data-ui-v2="usd-today">{C.pfr.usdToday}</Note>}
      {money.absent && money.absent.length > 0 && <MissingNote absent={money.absent} deckId={deck.id} />}
    </Card>
  );
}

// ---------------- 가진 종목 ----------------
function HeldCard({ block, onWhy }) {
  const { openStock } = useNav();
  const { deck, de, list, st } = block;
  const rows = list.rows;
  const shades = holdingShades(rows.map((r) => r.w));
  const limit = limitsOf(deck).stock;
  const H = C.home;
  if (!H.held) return null;
  return (
    <Card data-ui-v2="home-held" data-deck-id={deck.id} style={{ padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), marginBottom: 2 }}>
        <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{fill(H.held, { n: rows.length })}</h3>
        {H.cols && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{H.cols}</span>}
      </div>
      {rows.map((r, i) => {
        const big = r.x && r.x.bigMove && !r.absent;
        const open = big && onWhy ? () => onWhy(deck.id, r.t) : r.t && !r.absent && openStock && isCompany(block.byT && block.byT.get(r.t)) ? () => openStock(r.t) : undefined;
        const chips = r.x ? statusChips(r.x) : null;
        const act = open ? { role: "button", tabIndex: 0, onClick: open, onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } } } : {};
        return (
          <div key={r.key} data-home-holding={r.key} data-status={r.x ? r.x.status : undefined} data-weight={r.w != null ? Math.round(r.w * 1000) / 10 : undefined} {...act}
            style={{ ...(open ? tap : {}), display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH, padding: `${SPACE(2) + 1}px 0`, borderTop: `1px solid ${COLOR.line}` }}>
            {r.t ? <CoMark t={r.t} name={r.nk} size={32} /> : <span aria-hidden="true" style={{ width: 32, flexShrink: 0 }} />}
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" })}>{r.nk}</span>
              {r.w != null && (
                <span style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(1) }}>
                  <span aria-hidden="true" style={{ flex: 1, height: 6, borderRadius: 3, background: COLOR.line, position: "relative", overflow: "hidden" }}>
                    <span data-ui-v2="home-bar" style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${(barOf(r.w, limit) * 100).toFixed(1)}%`, borderRadius: 3,
                      background: shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1] }} />
                  </span>
                  <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { width: 36, textAlign: "right" })}>{weightPct(r.w)}%</span>
                </span>
              )}
              {chips && <span style={{ display: "flex", marginTop: SPACE(1) }}>{chips}</span>}
            </span>
            <span data-ui-v2="home-change" style={tx(SIZE.sm, WEIGHT.heavy, r.d1 == null ? COLOR.text3 : tone(Math.round(r.d1 * 10)), { minWidth: 56, textAlign: "right", flexShrink: 0, whiteSpace: "nowrap" })}>
              {r.d1 != null ? signedPct(r.d1) : ""}</span>
          </div>
        );
      })}
      {de && de.notChecked > 0 && <Note data-ui-v2="today-not-checked">{fill(C.daily.notChecked, { n: de.notChecked })}</Note>}
    </Card>
  );
}

// ---------------- 오늘 볼 것 ----------------
function LookRow({ icon, title, sub, onClick, data, owner }) {
  return (
    <button type="button" {...data} onClick={onClick}
      style={{ ...tap, width: "100%", marginTop: SPACE(2), border: "none", textAlign: "left", background: COLOR.surface, borderRadius: RADIUS.lg - 2, padding: SPACE(3) + 2,
        display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH }}>
      <IconChip name={icon} size={40} />
      <span style={{ flex: 1, minWidth: 0 }}>
        {owner && <span data-ui-v2="home-look-owner" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { display: "block" })}>{owner}</span>}
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{title}</span>
        {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, wordBreak: "keep-all" })}>{sub}</span>}
      </span>
      <Icon name="chevronRight" size={18} tone="on" />
    </button>
  );
}

function Look({ blocks, load, decks, onConfirm, onWhy, go }) {
  const H = C.home;
  const built = blocks.filter((b) => b.de && !b.de.imported);
  const all = built.flatMap((b) => b.de.holdings.map((x) => ({ x, deckId: b.de.id })));
  const todo = all.filter(({ x }) => isTodo(x)).sort((a, b) => (a.x.status === "broken" ? 0 : 1) - (b.x.status === "broken" ? 0 : 1));
  const seen = new Set();
  const bigs = all.filter(({ x }) => x.bigMove && !seen.has(x.t) && seen.add(x.t));
  const conc = blocks.map((b) => ({ b, c: concentration(b.st) })).filter((x) => x.c && H.concentration);
  if (!H.look || (!todo.length && !conc.length && !bigs.length)) return null;
  const deckOf = (id) => decks.find((d) => d.id === id);
  let band = null;
  if (todo.length) {
    const first = todo[0].x;
    const broken = first.status === "broken";
    const { todoTs, rest, restCalm } = todayCounts(built.map((b) => b.de));
    band = (
      <div data-ui-v2="today-todo" style={{ marginTop: SPACE(2) }}>
        <HeroBand tone="alert" level={broken ? "broken" : "watch"} eyebrow={fill(C.today.todoN, { n: todoTs.size })} title={broken ? brokenTitle(first.nk) : first.nk}
          body={lines([broken ? C.daily.sellNow : null, restCalm ? fill(C.today.rest, { n: rest }) : null])}
          inset={todo.map(({ x, deckId }, i) => <TodoItem key={deckId + x.t} x={x} deck={deckOf(deckId)} onConfirm={onConfirm} sellSaid={broken} first={i === 0} />)} />
      </div>
    );
  }
  return (
    <section data-ui-v2="home-look" style={{ marginTop: SPACE(5) }}>
      <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { margin: `0 ${SPACE(1)}px` })}>{H.look}</h3>
      {band}
      {conc.map(({ b, c }) => (
        <LookRow key={b.deck.id} icon="buildings" data={{ "data-ui-v2": "home-conc", "data-deck-id": b.deck.id, "data-w": Math.round(c.w * 1000) / 10 }}
          owner={blocks.length > 1 ? shownName(b.deck.name) : null}
          title={`${c.name} ${limitPct(c.w, c.limit)}%`} sub={fill(H.concentration, { names: c.names.join(", "), limit: c.limit })} onClick={() => go("portfolio")} />
      ))}
      {bigs.length > 0 && <Card data-ui-v2="home-bigs" style={{ marginTop: SPACE(2) }}><BigMoves items={bigs} load={load} onWhy={onWhy} /></Card>}
    </section>
  );
}

function useNarrow() {
  const q = "(max-width: 359px)";
  const get = () => { try { return window.matchMedia(q).matches; } catch (e) { return false; } };
  const [n, setN] = React.useState(get);
  React.useEffect(() => {
    let m;
    try { m = window.matchMedia(q); } catch (e) { return undefined; }
    const on = () => setN(m.matches);
    if (m.addEventListener) m.addEventListener("change", on); else m.addListener(on);
    return () => { if (m.removeEventListener) m.removeEventListener("change", on); else m.removeListener(on); };
  }, []);
  return n;
}

// ev, ctx: the daily check (today.jsx useDaily). onConfirm: the 확인 필요 answers (today.jsx confirmer).
export function Home2({ load, store, ev, ctx, onConfirm, pad, onWhy, go }) {
  const decks = store.data.decks;
  const ok = load.status === "ok";
  const narrow = useNarrow();
  const blocks = useMemo(() => (ev.ok ? homeBlocks(decks, ev, ctx, ok ? load.data.stocks : []).map((b) => ({ ...b, byT: ctx.byT })) : []), [decks, ev, ctx, load, ok]);
  const us = ev.ok && (blocks.some((b) => b.de && b.de.holdings.some((x) => x.cls === "us")) || decks.some((d) => usHeld(d, load)));
  const usDate = ok && us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  let top = null;
  if (!ev.ok && ev.why === "stale") {
    top = <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-stale"><HeroBand tone="stale" title={fill(C.today.stale, { n: ev.days })} /></div>;
  } else if (!ev.ok && ev.why !== "loading") top = <LoadFail />;
  const many = blocks.length > 1;
  const main = [
    ...blocks.map((b) => (
      <div key={b.deck.id} data-ui-v2="home-block" data-deck-id={b.deck.id}>
        <RulesHero block={b} many={many} narrow={narrow} />
        <MoneyCard block={b} pxDate={ok ? load.data.pxDate : null} />
        <HeldCard block={b} onWhy={onWhy} />
      </div>
    )),
    ev.ok && blocks.length > 0 && <Look key="look" blocks={blocks} load={load} decks={decks} onConfirm={onConfirm} onWhy={onWhy} go={go} />,
    ev.ok && !blocks.length && (
      <Card key="today-empty" data-ui-v2="today-empty"><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></Card>
    ),
  ];
  return (
    <Page pad={pad} cols={2}>
      <AppBar />
      <div data-ui-v2="home2">
        {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        {usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
        {store.restored && <Note tone="watch" data-ui-v2="store-merged">{C.store.merged}</Note>}
        {store.unmerged && C.store.locked && <Note tone="watch" data-ui-v2="store-unmerged">{C.store.locked}</Note>}
        {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
        {top}
        <Cols main={main} side={ok && <MarketGlance load={load} go={go} />} />
      </div>
      <Footer />
    </Page>
  );
}
