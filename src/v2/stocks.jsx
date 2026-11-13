// 종목 tab (v19.0c, board CStock): search, 최근 본 종목, 내 포트폴리오 종목 and 종목 순위 (v19.5b, rank.jsx: 홈's card as a
// still list of 30 with the same choice, where 홈's 전체 보기 lands; it replaced the two 거래대금 상위 종목 lists, whose order is
// now the 거래대금 chip).
// v19.1a: tapping a Korean or US company opens its 2.0 company page (#stocks/<code>, company.jsx), on the live page and
// the preview alike; tapping a fund (not a company) shows a line under its row (co.fundNote once approved; until then the
// line it showed before, stocks.krOnly), and nothing else. Nothing here links into the old app any more. Each row carries the company mark (logo.jsx).
// No 뱁이 here (the lists show today's changes). useStockTap is reused by 홈's 종목 순위 (rank.jsx).
// PC (v19.0d): the search field is the top bar's (nav.jsx TopBar, its words come in as q), so this screen shows no field
// of its own; the results, lists and taps are the same.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { C, fill, mdText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, OwnCloseNote, tx, tap, useMode, useNav } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { signedPct } from "./deckcalc.js";
import { todayD1 } from "./engine.js";
import { isCompany, searchStocks, myStocks, ownCloses } from "./stocklist.js";
import { RankCard } from "./rank.jsx";
import { readRecent, addRecent, RECENT_KEY, PREVIEW_RECENT_KEY } from "./recent.js";

const changeColor = (v) => (v > 0 ? COLOR.up : v < 0 ? COLOR.down : COLOR.text2);

// One stock: a first-letter badge, the name (US: the ticker under it; Korean: the code, unless plain), today's change.
// plain: no numbers at all (not used since v19.5b's 홈 shows 종목 순위). onTap / note / expands: from useStockTap (see below).
export function StockRow({ s, name, t, cls, plain = false, note, onTap, href, expands = false }) {
  const nk = name || (s && s.nk) || t;
  const d1 = todayD1(s);                   // v19.1c: no change for a stock priced at an earlier close (the list's note names it)
  const sub = cls === "us" ? t : plain ? null : t;
  const body = (
    <>
      {/* v19.1a: the company mark (logo.jsx: the letter is drawn by CSS from data-initial, a decoration, not text) */}
      <CoMark t={t} name={nk} size={SPACE(9)} />
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{nk}</span>
        {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{sub}</span>}
      </span>
      {!plain && d1 != null && <span style={tx(SIZE.xs, WEIGHT.bold, changeColor(d1), { flexShrink: 0 })}>{signedPct(d1)}</span>}
    </>
  );
  const style = { ...tap, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(2), width: "100%", padding: `${SPACE(1)}px 0`,
    border: "none", borderBottom: note ? "none" : `1px solid ${COLOR.line}`, background: "none", textAlign: "left", textDecoration: "none" };
  return (
    <div data-ui-v2="stock-row" data-t={t} data-cls={cls || ""}>
      {href ? <a href={href} onClick={onTap} style={style}>{body}</a>
        : onTap ? <button type="button" onClick={onTap} aria-expanded={expands ? (note ? "true" : "false") : undefined} style={style}>{body}</button>
          : <div style={{ ...style, cursor: "default" }}>{body}</div>}
      {note && <div data-ui-v2="row-note" role="status" style={{ borderBottom: `1px solid ${COLOR.line}`, paddingBottom: SPACE(2) }}><Note style={{ marginTop: 0 }}>{note}</Note></div>}
    </div>
  );
}

// What a tap does, shared by every list: a company (Korean or US) -> its 2.0 company page; a fund -> the line under the
// row (when approved). Every tap is remembered for 최근 본 종목.
export function useStockTap() {
  const { preview } = useMode();
  const { openStock } = useNav();
  const key = preview ? PREVIEW_RECENT_KEY : RECENT_KEY;
  const [recent, setRecent] = useState(() => readRecent(key));
  const [noteFor, setNoteFor] = useState(null);
  const props = (row) => {
    const corp = isCompany(row.s || { cls: row.cls, etf: false });
    const onTap = () => {
      setRecent(addRecent(row.t, key));
      if (corp && openStock) openStock(row.t);
      else setNoteFor((x) => (x === row.t ? null : row.t));
    };
    // a fund: the line under its row, as before v19.1a ('기업분석은 한국 상장 기업만 …') until co.fundNote is approved
    const fundLine = C.co.fundNote || C.stocks.krOnly;
    return { onTap, expands: !corp, note: !corp && noteFor === row.t ? fundLine : null };
  };
  return { recent, props };
}

// q: the PC top bar's search words (null on the phone, where this screen has its own field). ownQ / setOwnQ: the phone
// field's words, kept by the app shell (v19.1a: a company page and back keep them); without them the field keeps its own.
export function Stocks({ load, store, pad, q: topQ = null, ownQ: shellQ, setOwnQ }) {
  const [localQ, setLocalQ] = useState("");
  const ownQ = setOwnQ ? shellQ || "" : localQ;
  const setQ = setOwnQ || setLocalQ;
  const top = topQ != null;
  const q = top ? topQ : ownQ;
  const tp = useStockTap();
  const ok = load.status === "ok";
  const results = useMemo(() => (ok ? searchStocks(load, q) : []), [load, q, ok]);
  const mine = useMemo(() => myStocks(store.data.decks, load), [store.data.decks, load]);
  const recent = ok ? tp.recent.map((t) => load.byT.get(t)).filter(Boolean) : [];
  const typing = q.trim().length > 0;
  // US prices are at their own close date: say so when it differs from the Korean one and a US row is on screen
  // (as 홈 and 포트폴리오 do). 종목 순위 carries its own date.
  const usShown = (typing ? results : [...recent, ...mine.map((x) => x.s || x)]).some((s) => s && s.cls === "us");
  const usDate = ok && usShown && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  // v19.1c: the shown rows (search results, or recent and my stocks) with a US stock priced at an earlier close (pxd):
  // named under the date line. 종목 순위 carries its own note.
  const own = ok ? ownCloses(load, typing ? results : [...recent, ...mine.map((x) => x.s)]) : [];
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.app.tabs.stocks}</ScreenTitle>
      {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {usDate && <Note data-ui-v2="us-close">{fill(C.app.usClose, { md: usDate })}</Note>}
      <OwnCloseNote groups={own} />
      {load.status === "fail" && <LoadFail picture={false} />}
      {ok && !top && (
        <label data-ui-v2="stock-search" style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(3), minHeight: TOUCH + SPACE(1),
          background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.md, padding: `0 ${SPACE(3)}px` }}>
          <Icon name="search" size={20} tone="off" />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value.slice(0, 40))} aria-label={C.stocks.search || C.app.tabs.stocks}
            placeholder={C.stocks.search || undefined} enterKeyHint="search" autoComplete="off"
            style={{ flex: 1, minWidth: 0, border: "none", outline: "none", background: "transparent", minHeight: TOUCH, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
        </label>
      )}
      {typing && (
        <Card data-ui-v2="search-results">
          {results.map((s) => <StockRow key={s.t} s={s} t={s.t} cls={s.cls} {...tp.props({ t: s.t, cls: s.cls, s })} />)}
          {!results.length && (C.stocks.noResult ? <Note data-ui-v2="no-result">{C.stocks.noResult}</Note> : <span data-ui-v2="no-result" data-pending="1" hidden />)}
        </Card>
      )}
      {!typing && recent.length > 0 && (
        <Card data-ui-v2="recent">
          {C.stocks.recent && <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.stocks.recent}</h3>}
          {recent.map((s) => <StockRow key={s.t} s={s} t={s.t} cls={s.cls} {...tp.props({ t: s.t, cls: s.cls, s })} />)}
        </Card>
      )}
      {!typing && mine.length > 0 && (
        <Card data-ui-v2="my-stocks">
          <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{C.stocks.mine || fill(C.deck.mine, { n: mine.length })}</h3>
          {mine.map((x) => <StockRow key={x.t} s={x.s} name={x.nk} t={x.t} cls={x.cls} {...tp.props(x)} />)}
        </Card>
      )}
      {!typing && ok && <RankCard load={load} store={store} full tapper={tp} />}
      <Footer />
    </Page>
  );
}
