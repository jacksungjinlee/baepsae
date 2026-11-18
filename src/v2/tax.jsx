// ================= 연말에 확인할 숫자 (v19.6f, Part F, board TaxCheck2): #portfolio/tax =================
// Every portfolio together, from Nov 1 to Dec 31 (KST) of tax.js TAX_YEAR, reached from 내 수익 ("연말에 확인할 숫자 ›",
// TaxLink) when the user has a US sale this year, a US holding or a dividend this year (tax.taxOpen: the same rule for the
// link and the address; app.jsx turns a closed #portfolio/tax into #portfolio).
//   올해 해외 주식 양도차익   this year's US realized gains in won, exact to the 원; the bar to the 250만원 deduction; below ·
//                            above (with the estimate, 약, to 1,000원) · loss. Shown with a US sale this year or a US holding.
//   지금 손실 중인 미국 종목  held US stocks at a loss today (unrealized; facts only, never a word about selling). Needs today's
//                            data, fresh: on stale data the card says the data stopped and shows no number.
//   올해 받은 배당 (세금 떼기 전)  this year's dividend records turned back into pre-tax amounts, 약, to 1,000원.
// Never a sum that silently leaves records out: what is left out is named on the card with an approved line (Jack's yes to
// M1-M4 on 2026-11-19), and said in the console with counts. Load failure: the approved message only. No 뱁이 (the
// screen shows money). Tokens only (dark mode). No Korean here: src/copy/v2.js tax.*.
import React, { useMemo } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, TOUCH, CHART } from "../ui/tokens.js";
import { Amount, priceColor } from "../ui/components.jsx";
import { IconChip } from "../ui/icons.jsx";
import { C, fill, mdText, todayKst, todayStaleText, exactWon } from "./format.js";
import { Page, Card, AppBar, LoadFail, Footer, Note, OwnCloseNote, tx, tap } from "./ui.jsx";
import { ownCloses } from "./stocklist.js";
import { todayCtx } from "./rules.js";
import { missingNames } from "./tracking.jsx";
import { CoMark } from "./logo.jsx";
import { TAX_YEAR, taxWindow, taxRecords, yearGains, yearDivs, heldLosses, taxState } from "./tax.js";

const said = new Set();
const say = (m) => { if (!said.has(m)) { said.add(m); console.info("[v2] tax: " + m); } };

// "연말에 확인할 숫자 ›" on 내 수익 (above 기록 내려받기). The approved text carries its own ›.
export function TaxLink({ onClick }) {
  return (
    <Card data-ui-v2="tax-link" style={{ padding: 0 }}>
      <button type="button" onClick={onClick} style={{ ...tap, width: "100%", minHeight: TOUCH + SPACE(4), display: "flex", alignItems: "center", gap: SPACE(3),
        border: "none", background: "none", padding: `${SPACE(3)}px ${SPACE(4)}px`, textAlign: "left" }}>
        <IconChip name="receipt" size={38} />
        <span style={tx(SIZE.body - 1, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0, wordBreak: "keep-all" })}>{C.tax.link}</span>
      </button>
    </Card>
  );
}

const small = (extra) => tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { lineHeight: 1.5, wordBreak: "keep-all", ...extra });
// A card's head: the icon chip and the title, and (sub) a small line under the title, such as the card's content date.
function Head({ icon, tone, sub, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) + 2, marginBottom: SPACE(3) }}>
      <IconChip name={icon} tone={tone} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <h3 style={tx(SIZE.h3 - 1, WEIGHT.heavy, COLOR.ink, { wordBreak: "keep-all" })}>{children}</h3>
        {sub}
      </div>
    </div>
  );
}

// 올해 해외 주식 양도차익: the sum, the bar to 250만원 (not in the loss state), the state line, then the notes.
function GainCard({ g, win }) {
  const st = taxState(g.gain);
  // exactly 250만원 has its own line (M4, Jack 2026-11-19): "…보다 0원 적어요." is not something a person says (review B)
  const line = st.kind === "loss" ? fill(C.tax.loss, { x: exactWon(st.x) })
    : st.kind === "above" ? fill(C.tax.above, { x: exactWon(st.x), t: exactWon(st.t) })
    : st.kind === "equal" ? C.tax.equal
    : fill(C.tax.below, { x: exactWon(st.x) });
  const both = [C.tax.allDecks, win.ria ? C.tax.ria : null].filter(Boolean).join(" ");
  return (
    <Card data-ui-v2="tax-gain" data-state={st.kind} data-g={g.gain} data-x={st.x} data-t={st.t == null ? undefined : st.t} style={{ padding: `${SPACE(4)}px ${SPACE(4) + 2}px` }}>
      <Head icon="receipt" tone="earn">{C.tax.gainTitle}</Head>
      <span data-ui-v2="tax-g" style={tx(30, WEIGHT.heavy, COLOR.ink, { letterSpacing: "-0.02em", lineHeight: 1.25, display: "block" })}><Amount text={exactWon(g.gain)} /></span>
      {st.bar != null && (
        <div data-ui-v2="tax-bar" data-fill={Math.round(st.bar * 1000) / 1000}>
          <div aria-hidden="true" style={{ marginTop: SPACE(2) + 2, position: "relative", height: 16, borderRadius: 8, background: COLOR.neutralBg }}>
            <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${st.bar * 100}%`, borderRadius: 8, background: CHART.mine }} />
            <span style={{ position: "absolute", right: 0, top: -4, bottom: -4, width: 2, background: COLOR.ink }} />
          </div>
          <div style={{ marginTop: SPACE(1) + 2, display: "flex", justifyContent: "space-between", ...tx(SIZE.xs, WEIGHT.regular, COLOR.text2) }}>
            <span>0</span><span>{C.tax.deduction}</span>
          </div>
        </div>
      )}
      <p data-ui-v2="tax-line" style={tx(SIZE.sm - 1, WEIGHT.bold, COLOR.ink, { marginTop: SPACE(2) + 2, wordBreak: "keep-all" })}>{line}</p>
      <p data-ui-v2="tax-explain" style={small({ marginTop: SPACE(1) })}>{C.tax.explain}</p>
      <p data-ui-v2="tax-all" data-ria={win.ria ? "1" : "0"} style={small({ marginTop: SPACE(1) + 2 })}>{both}</p>
      {/* M5 (Jack 2026-11-19, 조세특례제한법 §91의27: tax.js): after the RIA line, under the same condition (tax year 2026) */}
      {win.ria && <p data-ui-v2="tax-hedge" style={small({ marginTop: SPACE(1) + 2 })}>{C.tax.hedge}</p>}
      {win.settle && <p data-ui-v2="tax-settle" style={small({ marginTop: SPACE(1) + 2 })}>{C.tax.settle}</p>}
      {g.left > 0 && <p data-ui-v2="tax-left" data-n={g.left} style={small({ marginTop: SPACE(1) + 2 })}>{fill(C.ret.soldLeftOut, { n: g.left })}</p>}
      {g.usdOnly && <p data-ui-v2="tax-usd-only" style={small({ marginTop: SPACE(1) + 2 })}>{C.rec.usdOnly}</p>}
      <p data-ui-v2="tax-gain-note" style={small({ marginTop: SPACE(1) + 2 })}>{C.tax.gainNote}</p>
    </Card>
  );
}

// 지금 손실 중인 미국 종목: one row per stock (all portfolios), biggest loss first, then the note and the lines naming what was
// left out. stale: today's data stopped, so the card says so and shows no number. Its content date (CLAUDE.md: each section
// carries its own; review B, round 1): the approved 내 수익 date line under the title, with the data's US price date (the rows
// are those closes at the data's rate; a stock priced at an earlier close is named by OwnCloseNote below).
function LossCard({ ls, stale, load, byT, nameOf }) {
  if (stale) {
    return (
      <Card data-ui-v2="tax-loss" data-stale="1" style={{ padding: `${SPACE(4)}px ${SPACE(4) + 2}px` }}>
        <Head icon="deck">{C.tax.lossTitle}</Head>
        <Note tone="watch" data-ui-v2="tax-stale" style={{ marginTop: 0 }}>{todayStaleText(stale.days)}</Note>
      </Card>
    );
  }
  const stocks = ls.rows.map((r) => byT.get(r.t)).filter(Boolean);
  const absent = ls.absent.map((t) => ({ t, nk: nameOf(t), cls: "us", cost: null }));
  const d = load.status === "ok" ? load.data.usPxDate || load.data.pxDate : null;
  const md = mdText(d);
  return (
    <Card data-ui-v2="tax-loss" data-n={ls.rows.length} style={{ padding: `${SPACE(4)}px ${SPACE(4) + 2}px` }}>
      <Head icon="deck" sub={md ? <p data-ui-v2="tax-loss-date" style={small()}>{fill(C.ret.date, { date: md })}</p> : null}>{C.tax.lossTitle}</Head>
      {ls.rows.map((r) => {
        const s = byT.get(r.t);
        return (
          <div key={r.t} data-ui-v2="tax-loss-row" data-t={r.t} data-v={r.gain} style={{ display: "flex", alignItems: "center", gap: SPACE(2) + 2, padding: `${SPACE(1) + 2}px 0` }}>
            <CoMark s={s} t={r.t} name={nameOf(r.t)} size={30} />
            <span style={tx(SIZE.sm - 0.5, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0, overflowWrap: "anywhere" })}>{nameOf(r.t)}</span>
            <span style={tx(SIZE.sm - 0.5, WEIGHT.heavy, priceColor(r.gain), { whiteSpace: "nowrap" })}><Amount text={exactWon(r.gain)} /></span>
          </div>
        );
      })}
      {/* no stock at a loss: M3 (Jack 2026-11-19) in place of the rows; the note about the rows comes with rows only */}
      {ls.rows.length === 0 && <p data-ui-v2="tax-loss-none" style={tx(SIZE.sm - 1, WEIGHT.bold, COLOR.ink, { wordBreak: "keep-all" })}>{C.tax.lossNone}</p>}
      {ls.rows.length > 0 && <p data-ui-v2="tax-loss-note" style={small({ marginTop: SPACE(1) + 2 })}>{C.tax.lossNote}</p>}
      {/* the names in these lines are tickers, as 내 수익 and the missing-stock line write a US stock */}
      {ls.noAvg.length > 0 && <Note data-ui-v2="tax-no-avg">{fill(C.ret.noAvg, { n: ls.noAvg.length, names: ls.noAvg.join(", ") })}</Note>}
      {ls.noFx.length > 0 && <Note data-ui-v2="tax-no-fx">{fill(C.tax.lossNoFx, { n: ls.noFx.length, names: ls.noFx.join(", ") })}</Note>}
      {absent.length > 0 && <Note tone="watch" data-ui-v2="tax-missing">{fill(C.missing.line, { n: absent.length, names: missingNames(absent) })}</Note>}
      {ls.noPrice.length > 0 && <Note tone="watch" data-ui-v2="tax-no-price">{C.ret.noPrice}</Note>}
      {ls.usdOnly && <Note data-ui-v2="tax-usd-today">{C.pfr.usdToday}</Note>}
      <OwnCloseNote groups={ownCloses(load, stocks)} data-ui-v2="tax-own-close" />
    </Card>
  );
}

// 올해 받은 배당 (세금 떼기 전): "약" small, the amount large (as on the board), then the note.
function DivCard({ dv }) {
  const [pre, post] = String(C.tax.divAmount).split("{x}");
  return (
    <Card data-ui-v2="tax-div" data-v={dv.won} data-n={dv.n} style={{ padding: `${SPACE(4)}px ${SPACE(4) + 2}px` }}>
      <Head icon="coins" tone="div">{C.tax.divTitle}</Head>
      <span data-ui="amount" data-ui-v2="tax-div-amount" style={{ display: "block" }}>
        <span style={tx(SIZE.body, WEIGHT.heavy, COLOR.text2)}>{pre}</span>
        <span style={tx(26, WEIGHT.heavy, COLOR.ink, { letterSpacing: "-0.02em" })}><Amount text={exactWon(dv.won)} /></span>
        {post ? <span style={tx(SIZE.body, WEIGHT.heavy, COLOR.text2)}>{post}</span> : null}
      </span>
      {dv.noFx > 0 && <p data-ui-v2="tax-div-no-fx" style={small({ marginTop: SPACE(1) + 2 })}>{fill(C.tax.divNoFx, { n: dv.noFx })}</p>}
      <p data-ui-v2="tax-div-note" style={small({ marginTop: SPACE(1) + 2 })}>{C.tax.divNote}</p>
    </Card>
  );
}

export function Tax({ load, store, pad, onBack }) {
  const today = todayKst();
  const win = taxWindow(today);
  const decks = store.data.decks;
  const has = useMemo(() => taxRecords(decks), [decks]);
  const ctx = useMemo(() => todayCtx(load), [load]);
  const ok = load.status === "ok";
  const live = ok && ctx.state.ok;
  const g = useMemo(() => (ok && (has.usSale || has.usHeld) ? yearGains(decks) : null), [ok, has, decks]);
  const dv = useMemo(() => (ok && has.div ? yearDivs(decks) : null), [ok, has, decks]);
  const ls = useMemo(() => {
    if (!live || !has.usHeld) return null;
    const pxOf = (t) => { const s = ctx.byT.get(t); return s && s.price > 0 ? s.price : null; };
    return heldLosses(decks, { pxOf, fx: ctx.fx, absent: { has: (t) => !ctx.byT.has(t) } });
  }, [live, has, decks, ctx]);
  // the name a stock has in today's data, else in the user's own records (holding or history entry), else its code
  const nameOf = (t) => {
    const s = ctx.byT.get(t);
    if (s && s.nk) return s.nk;
    for (const d of decks || []) {
      const h = (d.holdings || []).find((x) => x && x.t === t) || (d.history || []).find((x) => x && x.t === t);
      if (h && h.nk) return h.nk;
    }
    return t;
  };

  // What stays out, and why, said once each in the console (no fallback is silent).
  if (g && g.left) say(`${g.left} US sale(s) dated ${TAX_YEAR} left out of the gain (gain unknown: no average price, no rate, or more than held); the approved soldLeftOut line names the count`);
  const showDiv = !!dv && dv.n + dv.noFx > 0;
  if (dv && dv.noFx) say(`${dv.noFx} US dividend(s) dated ${TAX_YEAR} have no exchange rate: left out of the pre-tax sum (${dv.n} counted); the approved divNoFx line names the count`);
  let showLoss = false;
  if (ls) {
    const out = { noAvg: ls.noAvg, noFx: ls.noFx, absent: ls.absent, noPrice: ls.noPrice };
    const named = Object.entries(out).filter(([, v]) => v.length).map(([k, v]) => `${k} ${v.join(", ")}`);
    if (ls.noToday.length) say(`losses card left out: no exchange rate in today's data (${ls.noToday.length} US stock(s) held)`);
    else {
      showLoss = true;
      if (named.length) say(`losses card: ${ls.held} US stock(s) held, ${ls.rows.length} at a loss; left out and named on the card: ${named.join("; ")}`);
    }
  }
  const stale = ok && !ctx.state.ok && has.usHeld ? { days: ctx.state.days } : null;
  const md = mdText(today);
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.app.tabs.portfolio} />
      <div data-ui-v2="tax" data-year={TAX_YEAR} data-today={today}>
        <p data-ui-v2="tax-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>
          {fill(C.tax.date, { date: md })}{" · "}{C.tax.until}
        </p>
        <h2 style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1) })}>{C.tax.title}</h2>
        {load.status === "fail" && <LoadFail picture={false} />}
        {g && <GainCard g={g} win={win} />}
        {(stale || (showLoss && ls)) && <LossCard ls={ls} stale={stale} load={load} byT={ctx.byT} nameOf={nameOf} />}
        {showDiv && <DivCard dv={dv} />}
        {ok && (
          <p data-ui-v2="tax-footer" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3), padding: `0 ${SPACE(1)}px`, lineHeight: 1.5, wordBreak: "keep-all" })}>{C.tax.footer}</p>
        )}
      </div>
      <Footer />
    </Page>
  );
}
