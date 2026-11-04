// 종목 tab (v19.0c, board CStock): search, 최근 본 종목, 내 포트폴리오 종목 and 거래대금 상위 종목 (Korean and US lists).
// Tapping a Korean company opens the old app's 기업분석 on it (./baepsae.html#corp=CODE, read once by src/shell.jsx) until
// the 2.0 company page ships; tapping a US stock or a fund says "기업분석은 한국 상장 기업만 볼 수 있어요." under its row.
// The preview page (fictional data) never links into the old app: its rows only show that line for US stocks.
// No 뱁이 here (the lists show today's changes). StockRow and PopularLists are reused on 홈.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { C, fill, mdText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, tx, tap, useMode } from "./ui.jsx";
import { signedPct } from "./deckcalc.js";
import { isKrCompany, popularLists, searchStocks, myStocks } from "./stocklist.js";
import { readRecent, addRecent, RECENT_KEY, PREVIEW_RECENT_KEY } from "./recent.js";
import { OLD_LINKS } from "./routes.js";

const changeColor = (v) => (v > 0 ? COLOR.up : v < 0 ? COLOR.down : COLOR.text2);

// One stock: a first-letter badge, the name (US: the ticker under it; Korean: the code, unless plain), today's change.
// plain: no numbers at all (홈's first visit, which shows a 뱁이). onTap / href / note: from useStockTap (see below).
export function StockRow({ s, name, t, cls, plain = false, note, onTap, href }) {
  const nk = name || (s && s.nk) || t;
  const d1 = s && typeof s.d1 === "number" && Number.isFinite(s.d1) ? s.d1 : null;
  const sub = cls === "us" ? t : plain ? null : t;
  const body = (
    <>
      {/* the first letter of the name, drawn by CSS from data-initial (src/v2/template.html): a decoration, not text */}
      <span aria-hidden="true" data-initial={String(nk).trim().slice(0, 1)} style={{ width: SPACE(9), height: SPACE(9), borderRadius: RADIUS.sm, background: COLOR.select, display: "flex",
        alignItems: "center", justifyContent: "center", flexShrink: 0, ...tx(SIZE.xs, WEIGHT.heavy, COLOR.ink) }} />
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{nk}</span>
        {sub && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{sub}</span>}
      </span>
      {!plain && d1 != null && <span style={tx(SIZE.xs, WEIGHT.bold, changeColor(d1), { flexShrink: 0 })}>{signedPct(d1)}</span>}
    </>
  );
  const style = { ...tap, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(2), width: "100%", padding: `${SPACE(1)}px 0`,
    border: "none", borderBottom: note ? "none" : `1px solid ${COLOR.line}`, background: "none", textAlign: "left", textDecoration: "none" };
  return (
    <div data-ui-v2="stock-row" data-t={t} data-cls={cls || ""}>
      {href ? <a href={href} onClick={onTap} style={style}>{body}</a>
        : onTap ? <button type="button" onClick={onTap} aria-expanded={note ? "true" : "false"} style={style}>{body}</button>
          : <div style={{ ...style, cursor: "default" }}>{body}</div>}
      {note && <div data-ui-v2="kr-only" role="status" style={{ borderBottom: `1px solid ${COLOR.line}`, paddingBottom: SPACE(2) }}><Note style={{ marginTop: 0 }}>{note}</Note></div>}
    </div>
  );
}

// What a tap does, shared by every list: a Korean company -> the old app's 기업분석 (live page only); anything else -> the
// line under the row. Every tap is remembered for 최근 본 종목.
export function useStockTap() {
  const { preview } = useMode();
  const key = preview ? PREVIEW_RECENT_KEY : RECENT_KEY;
  const [recent, setRecent] = useState(() => readRecent(key));
  const [noteFor, setNoteFor] = useState(null);
  const props = (row) => {
    const corp = isKrCompany(row.s || { cls: row.cls, etf: false });
    const onTap = () => {
      setRecent(addRecent(row.t, key));
      if (!corp) setNoteFor((x) => (x === row.t ? null : row.t));
    };
    return { onTap: corp && preview ? undefined : onTap, href: corp && !preview ? OLD_LINKS.corp(row.t) : undefined,
      note: !corp && noteFor === row.t ? C.stocks.krOnly : null };
  };
  return { recent, props };
}

// 거래대금 상위 종목: two lists (한국 · 미국), each with its own date. plain: names only (홈's first visit).
export function PopularLists({ load, plain = false, tapper }) {
  const lists = useMemo(() => popularLists(load), [load]);
  const own = useStockTap();
  const tp = tapper || own;
  if (!lists || (!lists.kr.length && !lists.us.length)) return null;
  const part = (key, items, date) => items.length > 0 && (
    <div data-ui-v2="popular-list" data-market={key} style={{ marginTop: SPACE(3) }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: SPACE(2) }}>
        <span style={tx(SIZE.xs, WEIGHT.heavy, COLOR.ink)}>{C.pick.market[key]}</span>
        <span data-ui-v2="list-date" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2)}>{fill(C.app.asOf, { md: mdText(date) })}</span>
      </div>
      {items.map((s) => <StockRow key={s.t} s={s} t={s.t} cls={s.cls} plain={plain} {...tp.props({ t: s.t, cls: s.cls, s })} />)}
    </div>
  );
  return (
    <Card data-ui-v2="popular">
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name="chart-bar" size={32} />
        <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink)}>{C.home.popular}</h3>
      </div>
      {part("kr", lists.kr, lists.krDate)}
      {part("us", lists.us, lists.usDate)}
    </Card>
  );
}

export function Stocks({ load, store, pad }) {
  const [q, setQ] = useState("");
  const tp = useStockTap();
  const ok = load.status === "ok";
  const results = useMemo(() => (ok ? searchStocks(load, q) : []), [load, q, ok]);
  const mine = useMemo(() => myStocks(store.data.decks, load), [store.data.decks, load]);
  const recent = ok ? tp.recent.map((t) => load.byT.get(t)).filter(Boolean) : [];
  const typing = q.trim().length > 0;
  // US prices are at their own close date: say so when it differs from the Korean one and a US row is on screen
  // (as 홈 and 포트폴리오 do). The 거래대금 lists carry their own dates.
  const usShown = (typing ? results : [...recent, ...mine.map((x) => x.s || x)]).some((s) => s && s.cls === "us");
  const usDate = ok && usShown && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  return (
    <Page pad={pad}>
      <AppBar />
      <ScreenTitle>{C.app.tabs.stocks}</ScreenTitle>
      {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
      {usDate && <Note data-ui-v2="us-close">{fill(C.app.usClose, { md: usDate })}</Note>}
      {load.status === "fail" && <LoadFail picture={false} />}
      {ok && (
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
      {!typing && ok && <PopularLists load={load} tapper={tp} />}
      <Footer />
    </Page>
  );
}
