// 홈 (v19.0c; the 오늘 screen of v18.3 Part E). Returning visitors: the date line, the hero band with the rule verdict
// (REDESIGN 3), one strip per portfolio (value, return, today's move, my stocks) and 시장 한눈에 (the 시장 tab's four
// tiles, each with its own date). First visit (no saved portfolio): the hero with the 뱁이 carrying twigs (baepi-16-build),
// the descriptor and catchphrase, 포트폴리오 만들기, the iPhone home-screen hint and 거래대금 상위 종목 as names only —
// CLAUDE.md: 뱁이 never on a screen that shows numbers, so that screen has none (no prices, changes or tiles; dates are
// not numbers). The 가진 종목 넣기 card waits for its feature.
// States, from the daily check in rules.js (evaluateAll):
//   loading            nothing yet
//   failed / undated   the load-failure message (a file did not load, was refused, or cannot be dated)
//   stale              "데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요" (no status is computed at all); when n <= 1
//                      (v19.1c: the due day, n counted from nextPub) today.staleLate instead (format.todayStaleText)
//   no held stock      no verdict (nothing was checked), only the way to 포트폴리오 만들기
//   오늘 확인할 일      규칙 깨짐 or 확인 필요 (watch band, v19.0b: apricot marks data only): each one named, with its
//                      rule, numbers and report year. The pill is 규칙 깨짐's navy when any stock broke a rule, else amber.
//   할 일 없음          green band "매도 조건에 걸린 종목이 없어요": only when nothing is 규칙 깨짐 or 확인 필요. The
//                      eyebrow "오늘은 할 일이 없어요" only when every holding is 할 일 없음 (REDESIGN 2.1: steps 1-3 all
//                      clear, so no 지켜봐요 and no weight outside its band).
// Counts are of distinct stocks: a stock held in two portfolios is one stock to look at (its lines still show per
// portfolio, since each one keeps its own answers).
// Every verdict band carries "아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요" whenever any rule is not checked, so a
// calm band never hides a sell condition we could not check. A big move (|d1| >= 5%) is a note with a link to 왜 움직였나,
// never a status. 다음 일정 is hidden until the v18.0 calendar.
// v19.0b: the verdict carries a state icon (check-circle on calm days, flag on 확인할 일 days), never a 뱁이 picture
// (CLAUDE.md: 뱁이 never beside a verdict or on a card with numbers). The stale band is not a verdict: no icon.
// PC (v19.0d, boards PcHome · PcHomeNew): the date line and the verdict across the top, then two columns — my portfolios
// on the left, 시장 한눈에 on the right (its tiles stacked). First visit: the hero across the top (the 뱁이 at 176 px on the
// right, 포트폴리오 만들기 under the words), then 거래대금 상위 종목 with 한국 and 미국 side by side (still no numbers).
import React, { useMemo } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, TOUCH } from "../ui/tokens.js";
import { HeroBand, StatStrip, ListRow, Button } from "../ui/components.jsx";
import { C, fill, mdText, wonText, todayKst, todayStaleText } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, Note, OwnCloseNote, Mascot, IMG, Cols, useLayout, useCol, useNav, tx, tap } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { isCompany, ownCloses, ownCloseGroups } from "./stocklist.js";
import { shownName } from "./legacy.js";
import { MissingNote } from "./tracking.jsx";
import { MarketTiles } from "./market.jsx";
import { PopularLists } from "./stocks.jsx";
import { IosHint } from "./hint.jsx";
import { Welcome } from "./guide.jsx";
import { evaluateAll, todayCtx } from "./rules.js";
import { withConfirm } from "./store.js";
import { reasonView, statusChips, DividendAnswers, Line } from "./daily.jsx";
import { signedPct } from "./deckcalc.js";
import { deckMoney, deckDayChange, peerGroup, subjectParticle, todayCounts } from "./track.js";
import { pfState, isImported, usHeld } from "./pf.js";
import { ImportedDeck } from "./pfview.jsx";

// The daily check for every saved deck (nothing is computed from stale or failed data: ev.ok false, ev.why says why).
export function useDaily(load, store) {
  const decks = store.data.decks;
  const ctx = useMemo(() => todayCtx(load), [load]);
  const ev = useMemo(() => evaluateAll(decks, ctx), [decks, ctx]);
  return { ev, ctx };
}

export function confirmer(store, setStoreData) {
  return (deckId, item, answer) => {
    const next = withConfirm(store.data, deckId, item, answer, todayKst(), Date.now());
    if (next) setStoreData(next);
    else console.warn("[v2] answer not recorded: " + JSON.stringify(item));
  };
}

// "{name}이 / 가\n매도 조건에 걸렸어요": the particle from the name's last letter or digit (track.js subjectParticle).
export function brokenTitle(name) {
  return fill(subjectParticle(name) === "i" ? C.today.brokenTitle : C.today.brokenTitleGa, { name });
}

const namesOf = (deck) => new Map(((deck && deck.holdings) || []).map((h) => [h.t, h.nk]));
const isTodo = (x) => x.status === "broken" || x.status === "check";
const lines = (xs) => { const ls = xs.filter(Boolean); return ls.length ? ls.map((l, i) => <span key={i} style={{ display: "block" }}>{l}</span>) : null; };

export function LinkButton({ children, onClick, ...rest }) {
  return (
    <button type="button" onClick={onClick} {...rest}
      style={{ ...tap, border: "none", background: "none", minHeight: TOUCH, ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { textDecoration: "underline", textUnderlineOffset: 3, whiteSpace: "nowrap" }) }}>
      {children}
    </button>
  );
}

// One stock to look at today: its name, the rule that fired (or what needs confirming), numbers, report year, and the
// 확인 필요 answers (Part C's DividendAnswers: both answers stay open, the chosen one marked). sellSaid: the band above
// already says "규칙대로면 팔 때예요…", so a confirmed cut does not repeat it.
function TodoItem({ x, deck, onConfirm, sellSaid, first }) {    // first: its name is already the band's title
  const names = namesOf(deck);
  const views = x.reasons.filter((r) => (r.level === "broken" || r.level === "check") && r.code !== "divCut" && r.code !== "divDrop")
    .map((r) => [r, reasonView(r, x, names)]).filter(([, v]) => v);
  return (
    <div data-ui-v2="todo-item" data-t={x.t} data-status={x.status} style={{ paddingTop: first ? 0 : SPACE(3), marginTop: first ? 0 : SPACE(3), borderTop: first ? "none" : `1px solid ${COLOR.line}` }}>
      {!first && <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{x.nk}</div>}
      {x.status === "broken" && <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.today.sellLabel}</div>}
      <div style={{ marginTop: SPACE(1) }}>
        <DividendAnswers x={x} onConfirm={(item, answer) => onConfirm(deck.id, item, answer)} sellSaid={sellSaid} />
        {views.map(([r, v], i) => <Line key={i} code={r.code} level={r.level} {...v} first={i === 0 && !x.divDrops.length} />)}
      </div>
    </div>
  );
}

// 크게 움직인 종목: name, today's change, and "같은 업종이 다 같이 빠졌어요" only when its real industry group (5+
// members) fell together. A note only: it never changes a status. 자세히 보기 opens 왜 움직였나.
function BigMoves({ items, load, onWhy }) {
  return (
    <div data-ui-v2="big-moves">
      <div style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{fill(C.today.bigInset, { n: items.length })}</div>
      {items.map(({ x, deckId }) => {
        const g = peerGroup(load.byT.get(x.t), load.data.stocks);
        return (
          <div key={x.t} data-big-move={x.t} style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(1) }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>
                <span>{x.nk}</span>{" "}<span style={{ color: x.d1 < 0 ? COLOR.down : COLOR.up }}>{signedPct(x.d1)}</span>
              </div>
              {g.ok && g.together && <div data-ui-v2="together" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.today.together}</div>}
            </div>
            <LinkButton data-ui-v2="why-link" onClick={() => onWhy(deckId, x.t)}>{C.today.more}</LinkButton>
          </div>
        );
      })}
    </div>
  );
}

function Hero({ load, ev, held, decks, onConfirm, onWhy }) {
  if (!ev.ok) {
    if (ev.why === "loading") return null;
    if (ev.why === "stale") {
      return (
        <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-stale">
          <HeroBand tone="stale" title={todayStaleText(ev.days)} />
        </div>
      );
    }
    return <LoadFail />;                                  // failed, refused, or a publication time that cannot be read
  }
  if (!held.length) return null;                         // nothing held, nothing checked: no verdict at all
  const all = held.flatMap((de) => de.holdings.map((x) => ({ x, deckId: de.id })));
  const todo = all.filter(({ x }) => isTodo(x)).sort((a, b) => (a.x.status === "broken" ? 0 : 1) - (b.x.status === "broken" ? 0 : 1));
  const seen = new Set();
  const bigs = all.filter(({ x }) => x.bigMove && !seen.has(x.t) && seen.add(x.t));
  const nc = ev.notChecked > 0 ? <span data-ui-v2="today-not-checked">{fill(C.daily.notChecked, { n: ev.notChecked })}</span> : null;
  const deckOf = (id) => decks.find((d) => d.id === id);
  if (todo.length) {
    const first = todo[0].x;
    const broken = first.status === "broken";
    const { todoTs, rest, restCalm } = todayCounts(held);
    return (
      <>
        <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-hero" data-state="todo">
          <HeroBand tone="alert" level={broken ? "broken" : "watch"} eyebrow={fill(C.today.todoN, { n: todoTs.size })} title={broken ? brokenTitle(first.nk) : first.nk}
            body={lines([broken ? C.daily.sellNow : null, restCalm ? fill(C.today.rest, { n: rest }) : null, nc])}
            inset={<>
              {todo.map(({ x, deckId }, i) => <TodoItem key={deckId + x.t} x={x} deck={deckOf(deckId)} onConfirm={onConfirm} sellSaid={broken} first={i === 0} />)}
              {/* v19.1c: an item here about a US stock priced at an earlier close (pxd, carried by the daily check) read that
                  close: the same note, naming only those stocks */}
              <OwnCloseNote groups={ownCloseGroups(todo.map(({ x }) => x), null)} data-scope="todo" />
            </>} />
        </div>
        {bigs.length > 0 && <Card><BigMoves items={bigs} load={load} onWhy={onWhy} /></Card>}
      </>
    );
  }
  const { allNone } = todayCounts(held);
  const allD1 = all.every(({ x }) => x.d1 != null);
  return (
    <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-hero" data-state="calm">
      <HeroBand tone="calm" eyebrow={allNone ? C.today.calmEyebrow : undefined} title={C.today.calmTitle}
        body={lines([bigs.length ? fill(C.today.bigN, { n: bigs.length }) : allD1 ? C.today.noBigMove : null, nc])}
        inset={bigs.length ? <BigMoves items={bigs} load={load} onWhy={onWhy} /> : null} />
    </div>
  );
}

// One deck: value, return since purchase, today's move as a small grey line, then my stocks (chips only on
// exceptions). A big mover's row opens 왜 움직였나; any other row opens the 2.0 company page (v19.1a), each with its mark.
function DeckStrip({ de, deck, ctx, onWhy, go, load }) {
  const { openStock } = useNav();
  const m = deckMoney(deck, de, ctx);                    // v19.0c: a stock missing from today's data is left out, and said
  const gone = new Set(de.absent || []);
  const day = deckDayChange(de);
  const items = m.ok ? [{ label: C.today.value, value: wonText(m.value) },
    ...(m.ret != null ? [{ label: C.today.ret, value: signedPct(m.ret * 100), tone: m.ret > 0 ? "up" : m.ret < 0 ? "down" : undefined }] : [])] : [];
  return (
    <Card data-ui-v2="deck-strip" data-deck-id={de.id}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0 })}>{shownName(deck ? deck.name : de.name)}</h3>
        <LinkButton onClick={() => go("portfolio")}>{C.today.more}</LinkButton>
      </div>
      {items.length > 0 && (
        <div style={{ marginTop: SPACE(2) }}>
          <StatStrip items={items} note={day != null ? <span data-ui-v2="day-change"><span>{C.today.day}</span>{" "}<span>{signedPct(day)}</span></span> : null} />
        </div>
      )}
      {m.absent && m.absent.length > 0 && <MissingNote absent={m.absent} deckId={de.id} />}
      {/* v19.1c: a held US stock priced at an earlier close (pxd) is in the value and the list below: named once here */}
      <OwnCloseNote groups={ownCloses(load, de.holdings.filter((x) => !gone.has(x.t)).map((x) => ctx.byT.get(x.t)))} data-deck-id={de.id} />
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(4) })}>{fill(C.deck.mine, { n: de.holdings.length })}</div>
      {de.holdings.map((x) => (
        <div key={x.t} data-today-holding={x.t} data-status={x.status}>
          <ListRow title={x.nk} change={gone.has(x.t) ? null : x.d1} chip={statusChips(x)} lead={<CoMark t={x.t} name={x.nk} size={SPACE(9)} />}
            onClick={x.bigMove && !gone.has(x.t) ? () => onWhy(de.id, x.t) : !gone.has(x.t) && openStock && isCompany(ctx.byT.get(x.t)) ? () => openStock(x.t) : undefined} />
        </div>
      ))}
    </Card>
  );
}

// v19.3d: one portfolio made with 가진 종목 넣기 on 홈: its four portfolio rules and its holdings (pfview.jsx).
function ImportedStrip({ deck, de, ctx, load, go }) {
  const { openStock } = useNav();
  const st = useMemo(() => pfState(deck, ctx, load.status === "ok" ? load.data.stocks : []), [deck, ctx, load]);
  const m = de && de.ok ? deckMoney(deck, de, ctx) : { ok: false };
  return <ImportedDeck deck={deck} st={st} m={m} openStock={openStock} byT={ctx.byT} onMore={() => go("portfolio")} home />;
}

// 홈's first visit (no saved portfolio): no numbers on this screen (it shows a 뱁이).
// The date line stays (a date is not a number here, and it carries the "N일째 갱신이 멈췄어요" warning).
function FirstVisit({ load, go }) {
  const { wide } = useLayout();
  if (wide) {
    return (
      <>
        {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        <Card data-ui-v2="home-hero" style={{ display: "flex", alignItems: "center", gap: SPACE(6), marginTop: SPACE(4), padding: `${SPACE(6)}px ${SPACE(8)}px` }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3 })}>{C.about.ko.hero.descriptor}</h2>
            <p style={tx(SIZE.body, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(2) })}>{C.about.ko.hero.catch}</p>
            <div data-ui-v2="home-start" style={{ marginTop: SPACE(5), maxWidth: SPACE(70) }}><Button onClick={() => go("build")}>{C.build.title}</Button></div>
          </div>
          <Mascot src={IMG.build} alt={C.build.s0.imgAlt} size={176} />
        </Card>
        <IosHint kind="first" />
        {load.status === "fail" && <LoadFail picture={false} />}
        {load.status === "ok" && <PopularLists load={load} plain />}
      </>
    );
  }
  return (
    <>
      {load.status === "ok" && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      <Card data-ui-v2="home-hero" style={{ display: "flex", alignItems: "center", gap: SPACE(4), marginTop: SPACE(4) }}>
        <Mascot src={IMG.build} alt={C.build.s0.imgAlt} size={92} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3 })}>{C.about.ko.hero.descriptor}</h2>
          <p style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>{C.about.ko.hero.catch}</p>
        </div>
      </Card>
      <div data-ui-v2="home-start" style={{ marginTop: SPACE(3) }}><Button onClick={() => go("build")}>{C.build.title}</Button></div>
      <IosHint kind="first" />
      {load.status === "fail" && <LoadFail picture={false} />}
      {load.status === "ok" && <PopularLists load={load} plain />}
    </>
  );
}

// 시장 한눈에: the 시장 tab's four tiles and the way there. Without macro.json: the same failure line as the 시장 tab,
// in place of the tiles (never a row of "–" without a word).
// PC: in the narrow side column the four tiles stack; standing alone across the page (nothing in the main column, e.g.
// stale data or no saved portfolio with stocks) they sit four in a row.
function MarketGlance({ load, go }) {
  const { wide } = useLayout();
  const col = useCol();
  const tiles = !wide ? 2 : col === "side" ? 1 : 4;
  return (
    <Card data-ui-v2="market-glance">
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginBottom: SPACE(3) }}>
        <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0 })}>{C.home.market || C.app.tabs.market}</h3>
        <LinkButton data-ui-v2="market-more-link" onClick={() => go("market")}>{C.home.marketMore || C.today.more}</LinkButton>
      </div>
      {load.macro ? <MarketTiles load={load} cols={tiles} /> : <LoadFail picture={false} />}
    </Card>
  );
}

// welcome (v19.3c Part E): { onTry, onBrowse } while the first-visit guide's welcome is on (guide.jsx): it takes the place of
// 홈's content until the user picks 직접 해 보기 or 그냥 둘러볼게요.
export function Home({ load, store, setStoreData, pad, onWhy, go, welcome = null }) {
  const decks = store.data.decks;
  const first = decks.length === 0 && !store.locked;
  const { ev, ctx } = useDaily(load, store);
  const onConfirm = confirmer(store, setStoreData);
  const ok = load.status === "ok";
  const held = ev.ok ? ev.decks.filter((d) => d.ok && d.holdings.length) : [];
  // v19.3d (v19.3 F.1): portfolios made with 가진 종목 넣기 have no per-stock rules: their own strip shows the four
  // portfolio rules (pf.js), never 확인 필요 for every stock, and they take no part in the verdict above.
  const imported = ev.ok ? decks.filter(isImported) : [];
  const us = held.some((de) => de.holdings.some((x) => x.cls === "us")) || (ev.ok && decks.some((d) => usHeld(d, load)));   // v19.3d: 가진 종목 too
  const usDate = ok && us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  if (welcome) {
    return (
      <Page pad={pad} cols={2}>
        <AppBar />
        <Welcome load={load} first={first} onTry={welcome.onTry} onBrowse={welcome.onBrowse} onImport={welcome.onImport} />
        <Footer />
      </Page>
    );
  }
  if (first) {
    return (
      <Page pad={pad} cols={2}>
        <AppBar />
        <FirstVisit load={load} go={go} />
        <Footer />
      </Page>
    );
  }
  return (
    <Page pad={pad} cols={2}>
      <AppBar />
      {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
      {store.restored && <Note tone="watch" data-ui-v2="store-merged">{C.store.merged}</Note>}
      {store.unmerged && C.store.locked && <Note tone="watch" data-ui-v2="store-unmerged">{C.store.locked}</Note>}
      {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
      <Hero load={load} ev={ev} held={held} decks={decks} onConfirm={onConfirm} onWhy={onWhy} />
      <Cols main={[
        ...held.map((de) => <DeckStrip key={de.id} de={de} deck={decks.find((d) => d.id === de.id)} ctx={ctx} onWhy={onWhy} go={go} load={load} />),
        ...imported.map((d) => <ImportedStrip key={d.id} deck={d} de={ev.decks.find((x) => x.id === d.id)} ctx={ctx} load={load} go={go} />),
        ev.ok && !held.length && !imported.length && (
          <Card key="today-empty" data-ui-v2="today-empty"><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></Card>
        ),
      ]} side={ok && <MarketGlance load={load} go={go} />} />
      <Footer />
    </Page>
  );
}
