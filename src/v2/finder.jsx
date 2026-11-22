// ================= 내 기준으로 찾기 (v19.7b, docs/tasks/v19.7-portfolio-edit.md Part D, board PfFind3) =================
// #portfolio/edit/<portfolio id>/find, opened from 종목 바꾸기's "+ 종목 더하기 · 내 기준으로 찾기". The list is the build engine's own
// ranking with this portfolio's saved 기준 (find.js findList: screen() with its points, 빼기, strictness and mix, without the stocks
// already in it), one 내 기준 number per stock ("상위 {x}%", ranks.criteriaPct), four chips (전체 · 없는 업종 · 주가 변동 작은 순 ·
// 배당 주는 종목), at most 20 rows each. Each row: rank, logo, name (opens the company page), 새 업종 when its industry group has no
// target in the portfolio, "{industry} · 연 변동성 {vol}%" (only the industry when vol is blank), and two actions: 비교 (두 종목
// 비교, compare.jsx) and + 담기 (the 담기 sheet of 종목 바꾸기, Part C). Nothing here saves a target: 담기 waits for 바꾼 내용 저장.
// A portfolio without 기준 points: the approved line and the 기준 cards (BuildCards2, build.jsx StepCards); 저장 writes the chosen
// points (and strictness) to that portfolio's settings at once, and the list shows.
// Date line under the list (the board's place): "{date} 종가" with "· {year}년 사업보고서 기준" (or the quarter line) as 홈's 내 기준
// list says it (ranks.dateBasis · oneReportYear · quarterBasis); US rows "{date} 종가 (미국 시간)". Stale or a held publish: the
// usual date line with its warning at the top too (ui.jsx DateLine). Failed data: the load-failure message (editor.jsx).
// No line says a candidate will earn more. No 뱁이 (the screen shows scores). No Korean here: src/copy/v2.js.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Button, StatusChip } from "../ui/components.jsx";
import { C, fill, mdText, p1, todayKst } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, Footer, Note, CardPic, OwnCloseNote, tx, tap, useLayout, useNav, useHeld } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { activeCards, screen } from "./engine.js";
import { dateBasis, oneReportYear, quarterBasis } from "./ranks.js";
import { ownCloses, isCompany } from "./stocklist.js";
import { Dots, StepCards } from "./build.jsx";
import { writeStore } from "./store.js";
import * as E from "./edit.js";
import * as F from "./find.js";

// The industry words of a row: the group's name (a US group as "미국 · {ind}", as the 담기 sheet says it), else 업종 정보 없음.
export function indText(s, load, names) {
  const name = E.indOf({ t: s.t, add: { ind: s.ind || null } }, load.byT, names);
  if (!name) return C.rpt.noInd;
  return s.cls === "us" ? fill(C.pick.usInd, { ind: name }) : name;
}
// "{industry} · 연 변동성 {vol}%", or the industry alone when vol is blank (never a 0 in its place).
export function rowSub(s, load, names) {
  const ind = indText(s, load, names);
  const v = typeof s.vol === "number" && Number.isFinite(s.vol) ? s.vol : null;
  return v == null ? ind : fill(C.find.row, { industry: ind, vol: p1(v) });
}

// The date line's pieces for the rows shown (see the top). -> [string]
export function listDate(load, rows, points) {
  const out = [];
  const kr = rows.filter((r) => r.s.cls === "kr"), us = rows.filter((r) => r.s.cls === "us");
  const md = mdText(load.data.pxDate), mdUs = mdText(load.data.usPxDate);
  if (kr.length && md) {
    out.push(fill(C.rank.date, { date: md }));
    const basis = dateBasis("kr", "mine", null, points);
    const year = basis === "report" ? oneReportYear(kr, load.coByT).year : null;
    if (year != null) out.push(fill(C.app.reportYear, { year }));
    if (basis === "quarter" && quarterBasis(kr, load.coByT).quarter) out.push(C.rank.quarter);
  }
  if (us.length && mdUs) out.push(fill(C.rank.dateUs, { date: mdUs }));
  return out;
}

// A chip (one at a time). The board's pill: navy when chosen.
function FindChip({ id, on, onClick, children }) {
  return (
    <button type="button" data-ui-v2="find-chip" data-chip={id} aria-pressed={on ? "true" : "false"} onClick={onClick}
      style={{ ...tap, flex: "none", display: "inline-flex", alignItems: "center", height: TOUCH, padding: "0 14px", borderRadius: TOUCH / 2, border: "none",
        background: on ? COLOR.primary : COLOR.surface, boxShadow: on ? "none" : `inset 0 0 0 1px ${COLOR.chipEdge}`,
        ...tx(SIZE.xs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.onPrimary : COLOR.neutral, { whiteSpace: "nowrap" }) }}>{children}</button>
  );
}

// The portfolio's 기준 with their points: picture chip, name, five dots (read out as "{기준} {n}점").
export function PointsCard({ points }) {
  const cards = activeCards(points || {});
  return (
    <Card data-ui-v2="find-points" style={{ padding: `${SPACE(3)}px ${SPACE(4)}px` }}>
      <p style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginBottom: SPACE(2) })}>{C.find.card}</p>
      <div style={{ display: "flex", flexWrap: "wrap", columnGap: SPACE(3), rowGap: SPACE(2) }}>
        {cards.map((c) => (
          <span key={c.id} data-find-card={c.id} data-points={points[c.id]} style={{ display: "inline-flex", alignItems: "center", gap: SPACE(1) + 2 }}>
            <CardPic id={c.id} />
            <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink)}>{C.build.cards[c.id].name}</span>
            <Dots id={c.id} n={points[c.id]} size={7} gap={3} label={fill(C.build.s1.slot, { card: C.build.cards[c.id].name, n: points[c.id] })} />
          </span>
        ))}
      </div>
    </Card>
  );
}

// One candidate. On a narrow phone the two actions go under the name (the editor's rows do the same), so 320 px keeps the name.
function Row({ r, sub, onOpen, onCompare, onAdd, canCompare }) {
  const nameId = `find-name-${r.t}`;
  const btn = { ...tap, minHeight: TOUCH, minWidth: TOUCH, border: "none", background: "none", padding: `0 ${SPACE(2)}px`, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { whiteSpace: "nowrap" }) };
  return (
    <li data-find-row={r.t} data-rank={r.rank} data-pct={r.pct == null ? "" : r.pct} data-new-ind={r.newInd ? "1" : undefined}
      style={{ listStyle: "none", padding: `${SPACE(2) + 2}px 0`, borderTop: r.rank > 1 ? `1px solid ${COLOR.line}` : "none" }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", columnGap: SPACE(2) + 2, rowGap: SPACE(1) }}>
        <span data-ui-v2="find-no" style={tx(SIZE.xs, WEIGHT.heavy, COLOR.text3, { width: 18, textAlign: "center", flexShrink: 0 })}>{r.rank}</span>
        <CoMark s={r.s} t={r.t} name={r.s.nk} size={SPACE(9)} />
        {/* the name and its line: one 44 px tap target that opens the company page */}
        {(() => {
          const body = (
            <>
              <span style={{ display: "flex", alignItems: "center", gap: SPACE(2), minWidth: 0 }}>
                <span id={nameId} data-ui-v2="find-name" style={tx(SIZE.body - 1, WEIGHT.bold, COLOR.ink, { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", minWidth: 0 })}>{r.s.nk}</span>
                {r.newInd && <span data-ui-v2="find-new-ind" style={{ flexShrink: 0 }}><StatusChip tone="neutral">{C.find.newInd}</StatusChip></span>}
              </span>
              <span data-ui-v2="find-row-sub" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, wordBreak: "keep-all" })}>{sub}</span>
            </>
          );
          const box = { flex: "1 1 120px", minWidth: 0, minHeight: TOUCH, display: "flex", flexDirection: "column", justifyContent: "center" };
          return onOpen
            ? <button type="button" data-ui-v2="find-open" onClick={onOpen} style={{ ...tap, ...box, border: "none", background: "none", padding: 0, textAlign: "left" }}>{body}</button>
            : <div style={box}>{body}</div>;
        })()}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", flexShrink: 0, marginLeft: "auto" }}>
          <b data-ui-v2="find-pct" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { paddingRight: SPACE(2) })}>{r.pct != null ? fill(C.rank.mineX, { x: r.pct }) : "–"}</b>
          <span style={{ display: "flex" }}>
            {canCompare && <button type="button" data-ui-v2="find-compare" aria-describedby={nameId} onClick={onCompare} style={{ ...btn, color: COLOR.text2 }}>{C.find.compare}</button>}
            <button type="button" data-ui-v2="find-add" aria-label={fill(C.build.s4.addAria, { name: r.s.nk })} onClick={onAdd} style={btn}>{C.find.add}</button>
          </span>
        </div>
      </div>
    </li>
  );
}

// The 기준 cards for a portfolio without points (BuildCards2): the chosen points and strictness, saved with 저장.
function PickPoints({ deck, load, store, setStoreData }) {
  const base = deck.settings && typeof deck.settings === "object" ? deck.settings : {};
  const [st, setSt] = useState(() => ({ points: { ...(base.points && typeof base.points === "object" ? base.points : {}) }, strict: base.strict || "normal" }));
  const [fail, setFail] = useState(null);
  const settings = { points: st.points, strict: st.strict, exclude: base.exclude && typeof base.exclude === "object" ? base.exclude : {}, mix: base.mix, pinned: [] };
  const ds = useMemo(() => ({ res: screen(load.data.stocks, settings) }), [load, st]);
  const can = activeCards(st.points).length > 0 && store.writable && !store.locked;
  const save = () => {
    if (!can) return;
    const today = todayKst();
    const r = E.withPoints(store.data, deck.id, st.points, st.strict, today);
    if (!r.ok) { console.warn("[v2] criteria points not saved: " + r.why); setFail("refused"); return; }
    if (!writeStore(r.data, store.key, today)) { setFail("storage"); return; }
    setStoreData(r.data, true);
    console.info(`[v2] ${deck.id}: criteria points saved for the finder`);
  };
  return (
    <div data-ui-v2="find-no-points">
      <Note data-ui-v2="find-no-points-line" style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink)}>{C.find.noPoints}</Note>
      {/* records that cannot be written: the editor's own notes (저장 stays off) */}
      {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
      {store.locked && <Note tone="watch">{C.store.locked}</Note>}
      <StepCards st={st} set={(patch) => setSt((x) => ({ ...x, ...patch }))} ds={ds} load={load} coach={null} />
      <div style={{ marginTop: SPACE(4) }}><Button onClick={save} disabled={!can}>{C.find.savePoints}</Button></div>
      {fail === "storage" && <Note tone="watch" data-ui-v2="store-fail">{C.store.unavailable}</Note>}
      {fail === "refused" && <Note tone="watch" data-ui-v2="edit-save-fail">{C.edit.saveFail}</Note>}
    </div>
  );
}

// deck: the stored portfolio; draft: the edits waiting (held stocks and pending 담기 are not offered again). chip / setChip: the
// chosen chip (kept by the editor, so coming back from 두 종목 비교 keeps it). onCompare(t) · onAdd(s): the row's two actions.
export function Finder({ deck, draft, load, store, setStoreData, pad, chip, setChip, onBack, onCompare, onAdd }) {
  const { wide } = useLayout();
  const { openStock } = useNav();
  const held = useHeld();
  const names = useMemo(() => E.indNames(load.data.stocks), [load]);
  const list = useMemo(() => F.findList(load, deck, draft), [load, deck, draft]);
  const points = list ? list.settings.points : null;
  const rows = list ? F.chipRows(list, chip) : [];
  const canCompare = F.compareHoldings(deck, draft).length > 0;
  const dates = list && rows.length ? listDate(load, rows, points) : [];
  const chipRow = wide ? { display: "flex", flexWrap: "wrap", gap: 6 }
    : { display: "flex", gap: 6, overflowX: "auto", scrollbarWidth: "thin", marginLeft: -SPACE(4), marginRight: -SPACE(4), paddingLeft: SPACE(4), paddingRight: SPACE(4) };
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.edit.title} />
      {(load.fresh && load.fresh.stale) || held ? <DateLine date={load.data.pxDate} fresh={load.fresh} /> : null}
      <div data-ui-v2="find" data-deck-id={deck.id} data-chip={chip} data-n={rows.length}>
        {/* the sub says points were given: not over the 기준 cards of a portfolio that has none (review) */}
        <ScreenTitle sub={list ? C.find.sub : null}>{C.find.title}</ScreenTitle>
        {!list ? <PickPoints deck={deck} load={load} store={store} setStoreData={setStoreData} /> : (
          <>
            <PointsCard points={points} />
            <div data-ui-v2="find-chips" role="group" aria-label={C.find.title} style={{ ...chipRow, marginTop: SPACE(3) }}>
              {F.FIND_CHIPS.map((c) => <FindChip key={c} id={c} on={c === chip} onClick={() => setChip(c)}>{C.find.chips[c]}</FindChip>)}
            </div>
            <Card data-ui-v2="find-list" style={{ padding: `${SPACE(2)}px ${SPACE(4)}px` }}>
              {rows.length ? (
                <ol style={{ margin: 0, padding: 0 }}>
                  {rows.map((r) => (
                    <Row key={r.t} r={r} sub={rowSub(r.s, load, names)} canCompare={canCompare} onCompare={() => onCompare(r.t)} onAdd={() => onAdd(r.s)}
                      onOpen={openStock && isCompany(r.s) ? () => openStock(r.t) : null} />
                  ))}
                </ol>
              ) : <p data-ui-v2="find-empty" style={tx(SIZE.sm, WEIGHT.semi, COLOR.text2, { padding: `${SPACE(4)}px 0`, wordBreak: "keep-all" })}>
                {chip === "newInd" ? C.find.emptyNewInd : C.find.empty}</p>}
            </Card>
            {dates.length > 0 && (
              <p data-ui-v2="find-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(2)}px ${SPACE(1)}px 0`, wordBreak: "keep-all" })}>
                {dates.map((d, i) => <span key={i}>{i ? " · " : ""}{d}</span>)}
              </p>
            )}
            {chip === "newInd" && rows.length > 0 && (
              <p data-ui-v2="find-new-ind-line" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(1)}px ${SPACE(1)}px 0`, wordBreak: "keep-all" })}>{C.find.newIndLine}</p>
            )}
            <OwnCloseNote groups={ownCloses(load, rows.map((r) => r.s), { compact: true })} style={{ margin: `${SPACE(1)}px ${SPACE(1)}px 0` }} />
          </>
        )}
      </div>
      <Footer />
    </Page>
  );
}
