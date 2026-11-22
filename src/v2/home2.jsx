// ================= 홈 for returning visitors (v19.3e, v19.3 Part H, board Home2; today.jsx HOME2) =================
// At the top, as before, the verdict band of the portfolios made with 포트폴리오 만들기 (today.jsx Hero: 오늘 확인할 일 with
// the answers, or the calm band, its big moves and the "아직 자동으로 확인하지 못하는 규칙" line; also the stale band and the
// load-failure message). Those portfolios keep their own per-stock rules and bands and are never judged by the four
// portfolio rules (Jack, 2026-11-08). The calm band's "오늘은 할 일이 없어요" also needs every 가진 종목 portfolio quiet
// (home.quietBlock) and nothing on 오늘 볼 것 (Hero's quiet), so it never sits above a broken or unchecked rule or a card.
// Per portfolio that holds something today (the same portfolios 홈 showed before, in store order; home.js):
//   1. only for a portfolio made with 가진 종목 넣기, the hero (navy): "{date} 종가로 점검했어요" (only when at least one rule
//      could be checked), "내 규칙 {n}개 중 {k}개를 지키고 있어요" (n = the rules that could be checked), four rule tiles with
//      ✓, ! or "확인하지 못했어요", the first broken concentration rule as one sentence and "아직 자동으로 확인하지 못하는
//      규칙이 {n}개 있어요" for the rules that could not be checked. With two or more portfolios each hero starts with its
//      portfolio's name (user text) so the heroes can be told apart.
//   2. the portfolio card: value, "오늘 {±amount} ({±%})", "산 가격보다 {±amount} ({±%}) · 평균 단가를 넣은 {n}종목 기준"
//      (only holdings with a 평균 단가, and only when there is one), "미국 종목은 달러로 계산한 수익을 오늘 환율로 바꿨어요."
//      when a dollar 평균 단가 was converted at today's rate; the price date at the top right. No chart (Part H: until daily
//      price history exists).
//   3. 가진 종목 {n}개 · 비중 · 오늘: mark, name, weight bar in the navy shades by weight (Part C), weight %, today's change
//      (price red/blue, true minus sign). A 가진 종목 portfolio's bar is drawn against its 한 종목 limit (a full bar = the
//      limit, as on the board) and its weight reads against that limit (pfview.limitPct: 30.4% is never "30%"). A built
//      portfolio is never judged by that limit: its full bar is the whole portfolio and its weight is its daily check's own
//      (home.holdingRows: the share among the stocks with a 비중 규칙), with one decimal, as its 비중 규칙 line on 포트폴리오
//      (tracking.jsx WeightLine) and the company page's holding line. A built portfolio also keeps its per-stock chips
//      (규칙 깨짐 · 확인 필요 · …); its "아직 자동으로 확인하지 못하는 규칙" line is the band's at the top, not per card.
// Then 오늘 볼 것: one concentration card per 가진 종목 portfolio whose 한 업종 rule broke ("{group} {x}%" / "{names} · 내
// 규칙은 {limit}%까지"), then the filings rows "{name} 공시 {n}건 · {title} · {date}" (home.filingRows; {title} names a
// direction only when the week's reports all agree, else "지분 변동 보고"). 홈 loads disc.json itself when a Korean stock is
// held (app.jsx, once per visit, after the first paint); a load that failed shows the 공시 tab's failure message here, and
// a list that stopped gives no rows. "오늘은 할 일이 없어요" (Jack, 2026-11-08) only when there is nothing to look at anywhere:
// no verdict band (it speaks for itself, as before), no card, every 가진 종목 portfolio quiet (home.quietBlock: checked,
// nothing broken, 한 종목 · 한 업종 · 내 기준 all checked on every holding, value known) and, with a Korean stock held, today's
// filings checked. Never when no rule could be checked, never while the filings load or after it failed.
// v19.6b (Part B.2, board Today2): the 오늘 볼 것 cards join that list as compact rows (todaylook.jsx LookRows: 확인 필요 first, then the
// 관심 종목 조건 rows, the filings, a watched stock's 지분 변동 and every 국민연금, then 다가오는 일정); each row, a 관심 종목 조건 row and
// the heading open the 오늘 볼 것 page (#home/today). Any of them means "오늘은 할 일이 없어요" does not show.
// 시장 한눈에 unchanged; 종목 순위 under it (v19.5b, rank.jsx: phone after 시장 한눈에, PC the right column). Stale data: the stale band only, nothing checked, never a ✓ (the daily check is not ok, so no block
// exists). Late data whose closes are at most 5 trading days behind (rules.js checkState, Jack 2026-11-19) is not "stale" here:
// everything shows as on a fresh day, under the date line's stale words, with the close's date in the band and the heroes, and
// "{date} 종가 기준으로는 할 일이 없어요." in place of "오늘은 할 일이 없어요" (today.calmLate). Failed: the load-failure message,
// never "할 일이 없어요". No 뱁이 anywhere here (numbers). The account banner waits for v19.4.
import React, { useMemo } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, holdingShades, HOLDING_SHADES } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { Amount, Button } from "../ui/components.jsx";
import { C, fill, p1, mdText, wonText, todayKst } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, Note, OwnCloseNote, KrAgedLine, Cols, useLayout, useRoomy, useNav, tx, tap } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { isCompany, ownCloses } from "./stocklist.js";
import { shownName } from "./legacy.js";
import { MissingNote } from "./tracking.jsx";
import { statusChips } from "./daily.jsx";
import { isImported } from "./pf.js";
import { signedPct } from "./deckcalc.js";
import { ruleLabel, ruleDetail, brokenLine, limitPct, groupName } from "./pfview.jsx";
import { usHeld, limitsOf } from "./pf.js";
import { homeBlocks, concentration, barOf, quietBlock } from "./home.js";
import { MarketGlance, Hero, calmLine } from "./today.jsx";
import { RankCard } from "./rank.jsx";
import { discDate } from "./company.js";
import { filingRows, filingsChecked, holdsKorean } from "./home.js";
import { IcrOffLine, EpsOwnersNote, StmtCurLine, UnitChkLine, NoDataLine, DayNote } from "./fixnote.jsx";
import { watchHits } from "./watch.js";
import { lateSay } from "./tradedays.js";
import { WatchHitRows } from "./watch.jsx";
import { lookModel, lookSay, coversKorean } from "./look.js";
import { LookRows, lookRowCount, pageHas } from "./todaylook.jsx";

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
      <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.onPrimary2, { lineHeight: 1.3, textAlign: "center", wordBreak: "keep-all" })}>{ruleLabel(r)}</span>
      {r.state === "unknown" && <span data-ui-v2="home-rule-unknown" style={tx(SIZE.xs, WEIGHT.regular, COLOR.onPrimary3, { lineHeight: 1.3, textAlign: "center", wordBreak: "keep-all" })}>{C.pfr.unknown}</span>}
      {detail && <span data-ui-v2="home-rule-detail" style={tx(SIZE.xs, WEIGHT.bold, COLOR.highlight, { lineHeight: 1.3, textAlign: "center", wordBreak: "keep-all" })}>{detail}</span>}
      {ok && (
        <span role="img" aria-label={C.daily.ok} style={{ position: "absolute", top: -4, right: -2, width: 20, height: 20, borderRadius: 10, background: COLOR.okBg,
          display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="check" size={14} tone="ok" /></span>
      )}
      {broken && (
        <span aria-hidden="true" style={{ position: "absolute", top: -4, right: -2, width: 20, height: 20, borderRadius: 10, background: COLOR.highlightBg,
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
      style={{ marginTop: SPACE(4), background: COLOR.primary, color: COLOR.onPrimary, borderRadius: RADIUS.lg + 2, padding: SPACE(4) + 2 }}>
      {many && <p data-ui-v2="home-rules-name" style={tx(SIZE.xs, WEIGHT.bold, COLOR.onPrimary, { marginBottom: SPACE(1) })}>{shownName(deck.name)}</p>}
      {/* "{date} 종가로 점검했어요" only when at least one rule was checked: with every tile 확인하지 못했어요 nothing was */}
      {md && st.checked > 0 && <p data-ui-v2="home-checked" style={tx(SIZE.xs, WEIGHT.regular, COLOR.onPrimary3)}>{fill(C.pfr.checked, { date: md })}</p>}
      {st.checked > 0 && <h2 data-ui-v2="home-kept" style={tx(21, WEIGHT.heavy, COLOR.onPrimary, { marginTop: SPACE(1) + 2, lineHeight: 1.35, letterSpacing: "-0.02em", wordBreak: "keep-all" })}>
        {fill(C.pfr.kept, { n: st.checked, k: st.kept })}</h2>}
      <div style={{ marginTop: SPACE(3) + 2, display: "grid", gridTemplateColumns: `repeat(${narrow ? 2 : 4}, minmax(0, 1fr))`, gap: SPACE(1) + 2 }}>
        {st.rules.map((r) => <HeroTile key={r.id} r={r} />)}
      </div>
      {/* 2026-11-08 (Jack): why 재무 경고 0개 could not be checked, when a Korean holding's 이자보상배율 check is off (pf.js icrOff);
          under the tiles, in the hero's light grey (a tile is too narrow for the sentence) */}
      <IcrOffLine show={st.rules.some((x) => x.id === "warn" && x.state === "unknown" && x.icrOff)} style={{ color: COLOR.onPrimary3, marginTop: SPACE(3) }} />
      {/* 2026-11-13 (Jack, Q14): and when a holding's numbers are blank because of the unit check (pf.js unit), the same way */}
      <UnitChkLine show={st.rules.some((x) => x.id === "warn" && x.state === "unknown" && x.unit)} style={{ color: COLOR.onPrimary3, marginTop: SPACE(3) }} />
      {/* and when a Korean holding files its statements in another currency (pf.js stmtCur), the same way */}
      <StmtCurLine cur={(st.rules.find((x) => x.id === "warn" && x.state === "unknown") || {}).stmtCur} style={{ color: COLOR.onPrimary3, marginTop: SPACE(3) }} />
      {/* 2026-11-14 (Jack): and when a Korean holding's checks could not run for lack of input (pf.js noData), the same way */}
      <NoDataLine show={st.rules.some((x) => x.id === "warn" && x.state === "unknown" && x.noData)} style={{ color: COLOR.onPrimary3, marginTop: SPACE(3) }} />
      {line && <p data-ui-v2="home-broken" style={tx(SIZE.xs, WEIGHT.semi, COLOR.onPrimary2, { marginTop: SPACE(3) })}>{line}</p>}
      {st.unchecked > 0 && <p data-ui-v2="home-not-checked" style={tx(SIZE.xs, WEIGHT.regular, COLOR.onPrimary3, { marginTop: SPACE(2) })}>{fill(C.daily.notChecked, { n: st.unchecked })}</p>}
    </section>
  );
}

// ---------------- the portfolio card ----------------
// No value today (a held stock has no price: track.deckMoney why "price"): 포트폴리오 shows no reason line for that case, so
// the card is left out and the console says why; a stock missing from today's data keeps the approved missing line.
// late (rules.js checkState, Jack 2026-11-19): data checked on an older close shows nothing labelled 오늘 (review, 2026-11-19):
// no "오늘 {amount}" and no line that speaks of today's rate or today's data; a number that only such a line explains is left
// out with it (a stock missing from the data: the whole card; a gain at today's rate: the gain line), said in the console.
const warnedMoney = new Set();
function MoneyCard({ block, pxDate, load, late = false }) {
  const { deck, money } = block;
  const lateAbsent = late && money.absent && money.absent.length > 0;
  if (lateAbsent || (!money.ok && !(money.absent && money.absent.length))) {
    const why = lateAbsent ? "late data with a held stock missing from it: its line speaks of today's data" : money.why || "unknown";
    const k = deck.id + "|" + why;
    if (!warnedMoney.has(k)) { warnedMoney.add(k); console.warn(`[v2] ${deck.id}: no portfolio value on the home screen today (${why}): the card is left out`); }
    return null;
  }
  const gainShown = money.ok && money.gain && !(late && money.gain.usdToday);
  if (late && money.ok && money.day) lateSay(`${deck.id}: the home card's change today is left out`);
  if (late && money.ok && money.gain && money.gain.usdToday) {
    const k = deck.id + "|lateUsd";
    if (!warnedMoney.has(k)) { warnedMoney.add(k); console.warn(`[v2] ${deck.id}: late data: the gain-since-purchase line is left out (its dollar costs are converted at the data's rate, which the approved line calls today's)`); }
  }
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
          {money.day && H.day && !late && (
            <span data-ui-v2="home-day" data-pct={Math.round(money.day.pct * 1000) / 1000} style={tx(SIZE.sm, WEIGHT.heavy, tone(Math.round(money.day.pct * 10)))}>
              {fill(H.day, { amount: signedWon(money.day.amount), pct: signedPct(money.day.pct) })}</span>
          )}
        </div>
      )}
      {gainShown && H.gain && H.gainBasis && (
        <p data-ui-v2="home-gain" data-n={money.gain.n} data-ret={Math.round(money.gain.ret * 100000) / 1000} style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1) })}>
          {/* the approved piece stays one text, coloured by its sign as "오늘 …" is (price red/blue only for up/down) */}
          <b style={{ color: tone(Math.round(money.gain.ret * 1000)) }}>{fill(H.gain, { amount: signedWon(money.gain.gain), pct: signedPct(money.gain.ret * 100) })}</b>{" "}
          <span style={{ color: COLOR.text3 }}>{"· "}{fill(H.gainBasis, { n: money.gain.n })}</span>
        </p>
      )}
      {gainShown && money.gain.usdToday && <Note data-ui-v2="usd-today">{C.pfr.usdToday}</Note>}
      {money.absent && money.absent.length > 0 && <MissingNote absent={money.absent} deckId={deck.id} />}
      {/* v19.1c (PR #82): a held US stock priced at an earlier close is in the value and the list below: named once here */}
      <OwnCloseNote groups={ownCloses(load, block.list.rows.filter((r) => r.t && !r.absent).map((r) => block.byT && block.byT.get(r.t)))} data-deck-id={deck.id} />
    </Card>
  );
}

// ---------------- 가진 종목 ----------------
// md: the Korean price date as shown ("11월 13일"), for the no-trade line (fixnote.jsx DayNote).
// late (rules.js checkState): no "비중 · 오늘" column name, no day's change and no no-trade line under it (review, 2026-11-19:
// nothing labelled 오늘 on data checked on an older close); the weights and the check's chips stay.
function HeldCard({ block, onWhy, md = null, late = false, aged = null }) {
  const { openStock } = useNav();
  if (late) lateSay(`${block.deck.id}: the home list's weight/today column name, day's changes and no-trade lines are left out`);
  const { deck, list } = block;
  const rows = list.rows;
  const shades = holdingShades(rows.map((r) => r.w));
  // A 가진 종목 portfolio: against its 한 종목 limit. A built portfolio is never judged by it: a full bar is 100%, one decimal
  // (its weight is the daily check's, as on 포트폴리오: home.holdingRows).
  const imp = isImported(deck);
  const full = imp ? limitsOf(deck).stock : 100;
  const wText = (w) => (imp ? limitPct(w, full) : p1(w * 100));
  const H = C.home;
  if (!H.held) return null;
  return (
    <Card data-ui-v2="home-held" data-deck-id={deck.id} data-kind={imp ? "imported" : "built"} data-full={full} style={{ padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: SPACE(2), marginBottom: 2 }}>
        <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{fill(H.held, { n: rows.length })}</h3>
        {H.cols && !late && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{H.cols}</span>}
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
                    <span data-ui-v2="home-bar" style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${(barOf(r.w, full) * 100).toFixed(1)}%`, borderRadius: 3,
                      background: shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1] }} />
                  </span>
                  <span data-ui-v2="home-weight" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { minWidth: 36, textAlign: "right", whiteSpace: "nowrap" })}>{wText(r.w)}%</span>
                </span>
              )}
              {chips && <span style={{ display: "flex", marginTop: SPACE(1) }}>{chips}</span>}
              {/* 2026-11-14 (Jack, design chat 2026-11-08): no change today, said in the row (the change cell stays empty, never 0.0%) */}
              {!late && !r.absent && r.t && block.byT && <DayNote s={block.byT.get(r.t)} md={md} block={false} style={{ marginTop: SPACE(1) }} />}
              {/* 2026-11-20 (Jack, a): left out past the age limit of its last confirmed close */}
              {r.absent && <KrAgedLine aged={aged} t={r.t} style={{ marginTop: SPACE(1) }} />}
            </span>
            <span data-ui-v2="home-change" style={tx(SIZE.sm, WEIGHT.heavy, r.d1 == null ? COLOR.text3 : tone(Math.round(r.d1 * 10)), { minWidth: 56, textAlign: "right", flexShrink: 0, whiteSpace: "nowrap" })}>
              {r.d1 != null && !late ? signedPct(r.d1) : ""}</span>
          </div>
        );
      })}
    </Card>
  );
}

// ---------------- 오늘 볼 것 ----------------
function LookRow({ icon, title, sub, onClick, data, owner, tone }) {
  return (
    <button type="button" {...data} onClick={onClick}
      style={{ ...tap, width: "100%", marginTop: SPACE(2), border: "none", textAlign: "left", background: COLOR.surface, borderRadius: RADIUS.lg - 2, padding: SPACE(3) + 2,
        display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH }}>
      <IconChip name={icon} size={40} tone={tone} />
      <span style={{ flex: 1, minWidth: 0 }}>
        {owner && <span data-ui-v2="home-look-owner" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { display: "block" })}>{owner}</span>}
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block" })}>{title}</span>
        {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, wordBreak: "keep-all" })}>{sub}</span>}
      </span>
      <Icon name="chevronRight" size={18} tone="on" />
    </button>
  );
}

// What 오늘 볼 것 holds today: the concentration cards, the filings rows, and whether "오늘은 할 일이 없어요" shows there.
// quiet: every 가진 종목 portfolio quiet (home.quietBlock), no card, and, when a Korean stock is held or watched (kr: look.coversKorean),
// today's filings checked (disc.json loaded and current): the verdict band at the top may then say it too. A filings load
// that failed shows the 공시 tab's failure message here (discFail); a list that stopped (the file is old, or that day's
// DART list did not come in: company.discDate stale) shows the 공시 tab's own date line, "{md} 기준 · {n}일째 갱신이
// 멈췄어요" (discOld; with no date to show, the failure message); both beside the filings rows' file-text chip. One still
// loading just holds the line back. The preview page has no filings at all (disc "none"): nothing to wait for there.
// The filings state for the screen and its tests (data-disc): skip (no Korean stock) · wait · ok · stale · fail · none.
export function discState(disc, kr) {
  if (!kr) return "skip";
  const st = disc ? disc.status : "none";
  if (st === "ok") return filingsChecked(disc, disc.data ? discDate(disc.data) : null) ? "ok" : "stale";
  return st === "fail" || st === "none" ? st : "wait";
}
// watch (v19.6c, Part C): the 관심 종목 조건 rows (watch.js watchHits); any of them is something to look at (quiet false).
// m (v19.6b, Part B.2): the 오늘 볼 것 cards (look.js lookModel); their compact rows (todaylook.jsx LookRows) and a failed
// 주요사항 list (issueFail) are something to look at too. kr: a Korean stock held or watched (the filings cover both).
function lookOf(blocks, held, disc, kr, watch = [], m = null) {
  const H = C.home;
  const imported = blocks.filter((b) => b.st);
  const conc = imported.map((b) => ({ b, c: concentration(b.st) })).filter((x) => x.c && H.concentration);
  const fresh = disc && disc.status === "ok" && disc.data ? discDate(disc.data) : null;
  const heldTs = new Set(blocks.flatMap((b) => b.list.rows.filter((r) => r.t && !r.absent).map((r) => r.t)));
  const files = H.filings && C.co.disc.buys && C.co.disc.sells && H.filingsBoth ? filingRows(disc, heldTs, todayKst(), fresh) : [];
  const ds = discState(disc, kr);
  const dd = ds === "stale" ? discDate(disc.data) : null;
  const discOld = dd && dd.date ? dd : null;
  const discFail = ds === "fail" || (ds === "stale" && !discOld);
  const rows = lookRowCount(m, heldTs);
  const issueFail = !!(m && m.issueFail);
  const quiet = (ds === "skip" || ds === "ok" || ds === "none") && imported.every(quietBlock) && !conc.length && !files.length && !watch.length
    && !rows && !issueFail;
  // "오늘은 할 일이 없어요" here: no verdict band (it speaks for itself, as before), at least one 가진 종목 portfolio, all quiet,
  // no card. Never on stale or failed data (no block exists then), never when no rule could be checked (quietBlock), never
  // before the filings were checked when a Korean stock is held.
  const calm = quiet && !held.length && imported.length > 0;
  return { conc, files, quiet, calm, discFail, discOld, ds, watch, m, rows, issueFail, heldTs };
}

function DiscNote({ id, date, children }) {
  return (
    <Card data-ui-v2={id} data-date={date || undefined} style={{ marginTop: SPACE(2), padding: SPACE(3) + 2, display: "flex", alignItems: "center", gap: SPACE(3) }}>
      <IconChip name="file-text" size={40} />
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </Card>
  );
}

// v19.6b: the 오늘 볼 것 heading; with something on the 오늘 볼 것 page (open), the heading opens it (Part B.2: "Tapping a row, or
// the list's header"). The tap area is padded out to the 44 px touch size without moving the heading.
export function LookHead({ open }) {
  const H = C.home;
  return (
    <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { margin: `0 ${SPACE(1)}px` })}>
      {open ? (
        <button type="button" data-ui-v2="home-look-open" onClick={open}
          style={{ ...tap, border: "none", background: "none", display: "inline-flex", alignItems: "center", gap: SPACE(1), padding: `${SPACE(3)}px ${SPACE(2)}px`,
            margin: `-${SPACE(3)}px -${SPACE(2)}px`, ...tx(SIZE.sm, WEIGHT.heavy, COLOR.ink) }}>
          <span>{H.look}</span><Icon name="chevronRight" size={16} tone="on" />
        </button>
      ) : H.look}
    </h3>
  );
}

// lateMd: on late data checked on an older close, that close's date. Then only the calm card shows, saying "{date} 종가
// 기준으로는 할 일이 없어요." (today.calmLate, Jack 2026-11-19) instead of "오늘은 할 일이 없어요": no "오늘 볼 것" heading
// and none of its rows (review, 2026-11-19: nothing labelled 오늘 on an older close, as before the late check). A broken
// concentration rule still shows in its portfolio's hero above (brokenLine); the filings rows wait for fresh data, and the
// 관심 종목 rows have none on late data anyway (watch.js: they need dayState ok).
function Look({ blocks, load, look, go, onWatch, onToday = null, lateMd = null }) {
  const { openStock } = useNav();
  const H = C.home;
  const { conc, files, calm, discFail, discOld, watch, m, rows, issueFail, heldTs } = look;
  if (lateMd && (conc.length || files.length || discFail || discOld || (watch && watch.length))) {
    lateSay(`the things-to-look-at rows are left out (${conc.length} concentration, ${files.length} filings${discFail || discOld ? ", the filings note" : ""}); a broken one-industry rule shows in its hero`);
  }
  if (lateMd) return calm ? <Card data-ui-v2="home-calm" data-late="1" style={{ marginTop: SPACE(5) }}><p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{calmLine(lateMd)}</p></Card> : null;
  if (!H.look || (!conc.length && !files.length && !calm && !discFail && !discOld && !watch.length && !rows && !issueFail)) return null;
  const byT = load.status === "ok" ? load.byT : new Map();
  return (
    <section data-ui-v2="home-look" style={{ marginTop: SPACE(5) }}>
      <LookHead open={onToday && (pageHas(m) || watch.length > 0) ? onToday : null} />
      {conc.map(({ b, c }) => (
        <LookRow key={b.deck.id} icon="buildings" data={{ "data-ui-v2": "home-conc", "data-deck-id": b.deck.id, "data-w": Math.round(c.w * 1000) / 10 }}
          owner={blocks.length > 1 ? shownName(b.deck.name) : null}
          title={`${groupName(c)} ${limitPct(c.w, c.limit)}%`} sub={fill(H.concentration, { names: c.names.join(", "), limit: c.limit })} onClick={() => go("portfolio")} />
      ))}
      {/* v19.6b: 확인 필요 (유상증자 · 전환사채 · 신주인수권부사채, newest first), then v19.6c's 관심 종목 조건 (Part B's order) */}
      <LookRows m={m} part="issue" onOpen={onToday} />
      {/* v19.6b: on 홈 a 관심 종목 조건 row opens the 오늘 볼 것 page too (Part B.2: "Tapping a row … opens the 오늘 볼 것 page");
          its card there opens 관심 종목 */}
      <WatchHitRows hits={watch} load={load} onOpen={onToday || onWatch} />
      {files.map((f) => {
        const s = byT.get(f.t);
        return (
          <LookRow key={"f" + f.t} icon="file-text" data={{ "data-ui-v2": "home-filing", "data-t": f.t, "data-n": f.n, "data-date": f.date,
            "data-up": f.up === true ? "1" : f.up === false ? "0" : "" }}
            title={fill(H.filings, { name: (s && s.nk) || f.t, n: f.n, title: f.up === true ? C.co.disc.buys : f.up === false ? C.co.disc.sells : H.filingsBoth,
              date: mdText(f.date) })}
            onClick={openStock && isCompany(s) ? () => openStock(f.t) : undefined} />
        );
      })}
      {/* v19.6b: a watched stock's 지분 변동 (a held stock's is the 공시 row above) and 국민연금, then 다가오는 일정 */}
      <LookRows m={m} part="filings" onOpen={onToday} heldTs={heldTs} />
      <LookRows m={m} part="dates" onOpen={onToday} />
      {/* the filings did not load: the 공시 tab's own failure message (no picture: this screen has numbers); the list stopped:
          the 공시 tab's own date line. Each beside the filings rows' chip, so it reads as being about the filings. */}
      {discFail && <DiscNote id="home-disc-fail"><LoadFail picture={false} inline /></DiscNote>}
      {discOld && <DiscNote id="home-disc-old" date={discOld.date}><DateLine date={discOld.date} fresh={{ stale: discOld.stale, days: discOld.days }} style={{ marginTop: 0 }} /></DiscNote>}
      {/* v19.6b: the day's 주요사항 list did not come in (disc.json issueOk false): the same failure message, beside the same chip */}
      {issueFail && <DiscNote id="home-issue-fail"><LoadFail picture={false} inline /></DiscNote>}
      {calm && <Card data-ui-v2="home-calm" style={{ marginTop: SPACE(2) }}><p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{C.today.calmEyebrow}</p></Card>}
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
// onWatch (v19.6c): opens 관심 종목 (a 관심 종목 조건 row).
// onToday (v19.6b): opens the 오늘 볼 것 page (#home/today).
export function Home2({ load, store, ev, ctx, onConfirm, pad, onWhy, go, disc = null, onWatch = null, onToday = null }) {
  const decks = store.data.decks;
  const ok = load.status === "ok";
  const narrow = useNarrow();
  // 종목 순위: PC from 1200 px in the right column under 시장 한눈에; from 1024 to 1199 px at the end of the main column (Jack, 2026-11-12)
  const { wide } = useLayout();
  const roomy = useRoomy();
  const rankInMain = wide && !roomy;
  const rankCard = ok && <RankCard key="rank" load={load} store={store} go={go} />;
  const blocks = useMemo(() => (ev.ok ? homeBlocks(decks, ev, ctx, ok ? load.data.stocks : []).map((b) => ({ ...b, byT: ctx.byT })) : []), [decks, ev, ctx, load, ok]);
  // a US stock held today (a sold-out kept one, 0 shares, does not count: final review N3)
  const us = ev.ok && (blocks.some((b) => b.de && b.de.holdings.some((x) => x.cls === "us" && x.qty !== 0)) || decks.some((d) => usHeld(d, load)));
  const usDate = ok && us && load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null;
  // The verdict band of the portfolios made with 포트폴리오 만들기 (their per-stock rules and bands), exactly as before; also
  // the stale band and the load-failure message.
  const held = ev.ok ? ev.decks.filter((d) => d.ok && !d.imported && d.holdings.some((x) => x.qty !== 0)) : [];
  const kr = useMemo(() => coversKorean(decks, store.data, ctx && ctx.byT), [decks, store.data, ctx]);
  // no row when the records cannot be written: its mark could not stop it repeating (review S1)
  const canMark = !!(store.writable && !store.locked);
  const hits = useMemo(() => (ev.ok ? watchHits(store.data, load, undefined, canMark) : []), [store.data, load, ev.ok, canMark]);
  // v19.6b (Part B.2): the 오늘 볼 것 cards (fresh data only); the console names what they leave out
  const lm = useMemo(() => lookModel(load, store, disc, todayKst()), [load, store, disc]);
  React.useEffect(() => { lookSay(lm, "home"); }, [lm]);
  const look = lookOf(blocks, held, disc, kr, hits, lm);
  // late data within 5 trading days (rules.js checkState, Jack 2026-11-19): the date of the close the check ran on
  const lateMd = ev.ok && ev.late && ok ? mdText(load.data.pxDate) : null;
  const many = blocks.length > 1;
  const main = [
    ...blocks.map((b) => (
      <div key={b.deck.id} data-ui-v2="home-block" data-deck-id={b.deck.id}>
        {b.st && <RulesHero block={b} many={many} narrow={narrow} />}
        <MoneyCard block={b} pxDate={ok ? load.data.pxDate : null} load={load} late={!!lateMd} />
        <HeldCard block={b} onWhy={onWhy} md={ok ? mdText(load.data.pxDate) : null} late={!!lateMd} aged={ctx ? ctx.aged : null} />
      </div>
    )),
    ev.ok && (blocks.length > 0 || hits.length > 0 || look.rows > 0 || look.issueFail) && <Look key="look" blocks={blocks} load={load} look={look} go={go} onWatch={onWatch} onToday={onToday} lateMd={lateMd} />,
    ev.ok && !blocks.length && (
      <Card key="today-empty" data-ui-v2="today-empty"><Button kind="secondary" onClick={() => go("build")}>{C.build.title}</Button></Card>
    ),
  ];
  return (
    <Page pad={pad} cols={2}>
      <AppBar />
      <div data-ui-v2="home2" data-disc={ev.ok ? look.ds : undefined}>
        {ok && <DateLine date={load.data.pxDate} fresh={load.fresh} />}
        {usDate && <Note>{fill(C.app.usClose, { md: usDate })}</Note>}
        {/* the week after the DART re-read (src/repair.js epsNoticeOn): one quiet line near the top */}
        <EpsOwnersNote load={load} />
        {store.restored && <Note tone="watch" data-ui-v2="store-merged">{C.store.merged}</Note>}
        {store.unmerged && C.store.locked && <Note tone="watch" data-ui-v2="store-unmerged">{C.store.locked}</Note>}
        {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
        <Hero load={load} ev={ev} held={held} decks={decks} onConfirm={onConfirm} onWhy={onWhy} quiet={look.quiet} />
        <Cols main={rankInMain ? [...main, rankCard] : main} side={ok && [<MarketGlance key="glance" load={load} go={go} />, !rankInMain && rankCard]} />
      </div>
      <Footer />
    </Page>
  );
}
