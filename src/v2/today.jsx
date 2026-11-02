// 오늘 (v18.3 Part E): the hero band is the rule verdict (REDESIGN 3), then one strip per deck and my stocks.
// States, from the daily check in rules.js (evaluateAll):
//   loading            nothing yet
//   failed / undated   the load-failure message (a file did not load, was refused, or cannot be dated)
//   stale              "데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요" (no status is computed at all)
//   no held stock      no verdict (nothing was checked), only the way to 덱 짜기
//   오늘 확인할 일      규칙 깨짐 or 확인 필요 (apricot band): each one named, with its rule, numbers and report year
//   할 일 없음          green band "매도 조건에 걸린 종목이 없어요": only when nothing is 규칙 깨짐 or 확인 필요. The
//                      eyebrow "오늘은 할 일이 없어요" also needs no 줄일 차례 (a trim is something to do).
// Every verdict band carries "아직 자동으로 확인하지 못하는 규칙이 {n}개 있어요" whenever any rule is not checked, so a
// calm band never hides a sell condition we could not check. A big move (|d1| >= 5%) is a note with a link to 왜 움직였나,
// never a status. 다음 일정 is hidden until the v18.0 calendar.
import React, { useMemo } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, TOUCH } from "../ui/tokens.js";
import { HeroBand, StatStrip, ListRow, Button } from "../ui/components.jsx";
import { C, fill, mdText, wonText, todayKst } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, tx, tap } from "./ui.jsx";
import { evaluateAll, todayCtx } from "./rules.js";
import { withConfirm } from "./store.js";
import { reasonView, statusChips, DividendAnswers, Line } from "./daily.jsx";
import { signedPct } from "./deckcalc.js";
import { deckMoney, deckDayChange, peerGroup, endsInBatchim } from "./track.js";

// The daily check for every saved deck (nothing is computed from stale or failed data: ev.ok false, ev.why says why).
export function useDaily(load, store) {
  const decks = store.data.decks;
  const ctx = useMemo(() => todayCtx(load), [load]);
  const ev = useMemo(() => evaluateAll(decks, ctx), [decks, ctx]);
  return { ev, ctx };
}

export function confirmer(store, setStoreData) {
  return (deckId, item, answer) => {
    const next = withConfirm(store.data, deckId, item, answer, todayKst());
    if (next) setStoreData(next);
    else console.warn("[v2] answer not recorded: " + JSON.stringify(item));
  };
}

// "{name}이\n매도 조건에 걸렸어요" needs a name ending in a final consonant. Other names use the 가 form once it is
// approved; until then the band's title is the name alone (the lines below it say 걸린 규칙 · 매도 조건).
export function brokenTitle(name) {
  if (endsInBatchim(name)) return fill(C.today.brokenTitle, { name });
  if (C.today.brokenTitleGa) return fill(C.today.brokenTitleGa, { name });
  return name;
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
function TodoItem({ x, deck, onConfirm, sellSaid, first }) {
  const names = namesOf(deck);
  const views = x.reasons.filter((r) => (r.level === "broken" || r.level === "check") && r.code !== "divCut" && r.code !== "divDrop")
    .map((r) => [r, reasonView(r, x, names)]).filter(([, v]) => v);
  return (
    <div data-ui-v2="todo-item" data-t={x.t} data-status={x.status} style={{ paddingTop: first ? 0 : SPACE(3), marginTop: first ? 0 : SPACE(3), borderTop: first ? "none" : `1px solid ${COLOR.line}` }}>
      <div style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{x.nk}</div>
      {x.status === "broken" && <div style={tx(SIZE.xxs, WEIGHT.bold, COLOR.text2)}>{C.today.sellLabel}</div>}
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
          <HeroBand tone="alert" title={fill(C.today.stale, { n: ev.days })} />
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
    const rest = all.length - todo.length;
    const restCalm = rest > 0 && all.every(({ x }) => isTodo(x) || x.status === "none");
    return (
      <>
        <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-hero" data-state="todo">
          <HeroBand tone="alert" eyebrow={fill(C.today.todoN, { n: todo.length })} title={broken ? brokenTitle(first.nk) : first.nk}
            body={lines([broken ? C.daily.sellNow : null, restCalm ? fill(C.today.rest, { n: rest }) : null, nc])}
            image="baepi-4.png" imageAlt={C.today.todoAlt}
            inset={todo.map(({ x, deckId }, i) => <TodoItem key={deckId + x.t} x={x} deck={deckOf(deckId)} onConfirm={onConfirm} sellSaid={broken} first={i === 0} />)} />
        </div>
        {bigs.length > 0 && <Card><BigMoves items={bigs} load={load} onWhy={onWhy} /></Card>}
      </>
    );
  }
  const trim = all.some(({ x }) => x.status === "trim");
  const allD1 = all.every(({ x }) => x.d1 != null);
  return (
    <div style={{ marginTop: SPACE(4) }} data-ui-v2="today-hero" data-state="calm">
      <HeroBand tone="calm" eyebrow={trim ? undefined : C.today.calmEyebrow} title={C.today.calmTitle}
        body={lines([bigs.length ? fill(C.today.bigN, { n: bigs.length }) : allD1 ? C.today.noBigMove : null, nc])}
        image={bigs.length ? "baepi-2.png" : "baepi-9.png"} imageAlt={bigs.length ? C.today.bigAlt : C.today.calmAlt}
        inset={bigs.length ? <BigMoves items={bigs} load={load} onWhy={onWhy} /> : null} />
    </div>
  );
}

// One deck: value, return since purchase, today's move as a small grey line, then my stocks (chips only on
// exceptions). A big mover's row opens 왜 움직였나.
function DeckStrip({ de, deck, ctx, onWhy, go }) {
  const m = deckMoney(deck, de, ctx);
  const day = deckDayChange(de);
  const items = m.ok ? [{ label: C.today.value, value: wonText(m.value) },
    ...(m.ret != null ? [{ label: C.today.ret, value: signedPct(m.ret * 100), tone: m.ret > 0 ? "up" : m.ret < 0 ? "down" : undefined }] : [])] : [];
  return (
    <Card data-ui-v2="deck-strip" data-deck-id={de.id}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0 })}>{deck ? deck.name : de.name}</h3>
        <LinkButton onClick={() => go("deck")}>{C.today.more}</LinkButton>
      </div>
      {items.length > 0 && (
        <div style={{ marginTop: SPACE(2) }}>
          <StatStrip items={items} note={day != null ? <span data-ui-v2="day-change"><span>{C.today.day}</span>{" "}<span>{signedPct(day)}</span></span> : null} />
        </div>
      )}
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(4) })}>{fill(C.deck.mine, { n: de.holdings.length })}</div>
      {de.holdings.map((x) => (
        <div key={x.t} data-today-holding={x.t} data-status={x.status}>
          <ListRow title={x.nk} change={x.d1} chip={statusChips(x)} onClick={x.bigMove ? () => onWhy(de.id, x.t) : undefined} />
        </div>
      ))}
    </Card>
  );
}

export function Today({ load, store, setStoreData, pad, onWhy, go }) {
  const decks = store.data.decks;
  const { ev, ctx } = useDaily(load, store);
  const onConfirm = confirmer(store, setStoreData);
  const ok = load.status === "ok";
  const held = ev.ok ? ev.decks.filter((d) => d.ok && d.holdings.length) : [];
  const us = held.some((de) => de.holdings.some((x) => x.cls === "us"));
  const usDate = ok && us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.today.title}</ScreenTitle>
      {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
      <Hero load={load} ev={ev} held={held} decks={decks} onConfirm={onConfirm} onWhy={onWhy} />
      {held.map((de) => <DeckStrip key={de.id} de={de} deck={decks.find((d) => d.id === de.id)} ctx={ctx} onWhy={onWhy} go={go} />)}
      {ev.ok && !held.length && (
        <Card data-ui-v2="today-empty"><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></Card>
      )}
      <Footer />
    </Page>
  );
}
