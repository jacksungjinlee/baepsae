// ================= 2.0: 오늘 볼 것 (v19.6b, docs/tasks/v19.6-records-alerts-dark.md Part B.2, board Today2) =================
// TodayLook   the 오늘 볼 것 page (#home/today), opened from 홈's 오늘 볼 것 header or one of its new rows. Cards, in Part B.2's
//             order: 확인 필요 (유상증자 · 전환사채 · 신주인수권부사채 결정, newest first: tag 확인 필요, the approved body by kind and
//             method or the 숫자를 읽지 못했어요 line, 공시 보기 and 확인했어요 (store.js seen: the card goes away)), then 관심 종목 조건 (watch.jsx's rows), then 임원 · 주요주주 지분 변동 and 국민연금 (newest first), then
//             다가오는 일정 (US dates with the US-date note; the no-Korean-dates line when a Korean stock is held). Every card shows
//             its own filing date; the page's date line is the price date the 지분 변동 amounts use. When disc.json failed or its
//             list stopped, the 공시 tab's failure message or date line (as on 홈); when the day's 주요사항 list failed
//             (issueOk false), the failure message where the 확인 필요 cards would be. An empty page (the last card marked, a
//             reload with nothing to show) and stale, late or failed data go back to 홈, which says why (as #home/why does
//             without its target). Facts only: no advice anywhere.
// LookRows    홈's compact rows for the new kinds (title and date, like the v19.3e 공시 row; home2.jsx Look and the first-visit
//             list): each opens this page. The held stocks' 지분 변동 stay the v19.3e 공시 row on 홈 (it counts every report of the
//             week, the cards only those of 1억원 or more), so only a watched stock's 지분 변동 gets a row of its own there.
// 공시 보기 (Part B.2; Jack's yes of 2026-11-22): the left button of a 확인 필요 card, a plain link to that one filing in DART's own
// viewer (routes.js dartFilingUrl: the exact receipt number only, else no button), new tab, noopener, with the arrow-out mark
// the company page's 공시 rows use. Nothing is fetched from DART (tests/test_v2_app.py: this card and the 공시 tab only).
// No 뱁이 anywhere here (numbers). Colours: the shared tokens only (dark mode covers the screen). Icons: Phosphor duotone with
// the topic tints (확인 필요 출렁임·위험 · 지분 변동 and 국민연금 공시·수급 · 일정 실적).
import React, { useEffect, useMemo, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { StatusChip } from "../ui/components.jsx";
import { C, fill, nf, p1, mdText, todayKst } from "./format.js";
import { Page, Card, AppBar, DateLine, LoadFail, Footer, tx, tap } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { bigWon } from "./cofmt.js";
import { subjectParticle } from "./track.js";
import { withSeen } from "./store.js";
import { watchHits } from "./watch.js";
import { WatchHitRows } from "./watch.jsx";
import { lookModel, lookSay } from "./look.js";
import { dartFilingUrl } from "./routes.js";

const L = () => C.look;
const MARK = 28;                                    // the company mark beside a title (the letter mark stays at 12 px or more)
// "{name} · {title}" (the shape of watch.jsx hitTitle)
const titled = (name, kind) => (kind ? `${name} · ${kind}` : null);
// a share as the pipeline stores it (fetch_data _issue_pct): two decimals ("20.58", "7", "3.5"), and below 0.005% two significant
// digits ("0.0012"), so a small ratio never reads "0%"
export const pct2 = (x) => (x >= 0.005
  ? Number(Math.round(x * 100) / 100).toLocaleString("ko-KR", { maximumFractionDigits: 2 })
  : Number(x).toLocaleString("ko-KR", { maximumSignificantDigits: 2 }));

// ---------------- words ----------------
export const issueTitle = (c) => titled(c.nk, L()[c.kind]);
export function issueText(c) {
  if (c.body === "unread") return L().unread;
  if (c.body === "holders" || c.body === "others") return fill(c.body === "holders" ? L().rightsHolders : L().rightsOthers, { n: nf(c.n), p: pct2(c.p) });
  if (c.body === "cb" || c.body === "bw") return fill(c.body === "cb" ? L().cbBody : L().bwBody, { amt: bigWon(c.amt), p: pct2(c.p) });
  return null;
}
const INS_TITLE = { exec: "insExec", major: "insMajor", both: "insBoth" };
export const insiderTitle = (c) => titled(c.nk, L()[INS_TITLE[c.title]]);
export function insiderText(c) {
  const p = c.pos || L().posAny;
  const ga = subjectParticle(p) !== "i";
  return fill(c.up ? (ga ? L().insUpGa : L().insUp) : (ga ? L().insDownGa : L().insDown), { pos: p, amt: bigWon(c.won) });
}
export const npsTitle = (c) => titled(c.nk, L().nps);
export const npsText = (c) => fill(c.up ? L().npsUp : L().npsDown, { a: p1(c.a), b: p1(c.b) });
const dateKind = (k) => (k === "earn" ? L().earn : L().exDiv);
// The cards a screen can show: the insider cards with a title (임원 · 주요주주, and C.look.insBoth for both or blank; none while
// the role is not read: look.js ROLE_OF, lookSay).
export const shownInsider = (m) => m.insider.filter((c) => insiderTitle(c));
// Whether the page has a card to show (besides the 관심 종목 조건 ones the caller counts): the heading opens it only then.
export const pageHas = (m) => !!(m && m.fresh && (m.issue.length || shownInsider(m).length || m.nps.length || m.dates.length));

// The approved sentence with its 지분을 늘린 보고 / 지분을 줄인 보고 in bold (board Today2; the same words as co.disc.buys · sells).
function Bolded({ text, part }) {
  const i = part ? text.indexOf(part) : -1;
  if (i < 0) return text;
  return <>{text.slice(0, i)}<b style={{ fontWeight: WEIGHT.heavy, color: COLOR.ink }}>{part}</b>{text.slice(i + part.length)}</>;
}

// ---------------- one card ----------------
function LookCard({ icon, tone, t, name, title, titleId, tag, date, children, actions, ...rest }) {
  return (
    <section {...rest} style={{ marginTop: SPACE(2), background: COLOR.surface, borderRadius: RADIUS.lg - 2, padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) + 2 }}>
        <IconChip name={icon} tone={tone} size={40} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 data-ui-v2="look-title" id={titleId} style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "flex", alignItems: "center", gap: SPACE(1) + 2, lineHeight: 1.35, wordBreak: "keep-all" })}>
            {t && <CoMark t={t} name={name} size={MARK} />}
            <span style={{ minWidth: 0 }}>{title}</span>
          </h3>
          {date && <p data-ui-v2="look-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: 2 })}>{date}</p>}
        </div>
        {tag}
      </div>
      {children}
      {actions}
    </section>
  );
}
const body = (text, extra) => (
  <p data-ui-v2="look-body" style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(2), lineHeight: 1.55, wordBreak: "keep-all" })}>{extra || text}</p>
);
const btn = { ...tap, flex: 1, minHeight: TOUCH, borderRadius: RADIUS.sm, display: "flex", alignItems: "center", justifyContent: "center", gap: SPACE(1) + 2,
  padding: `0 ${SPACE(3)}px`, textDecoration: "none", cursor: "pointer" };

// tabIndex -1: focus can be put on the card (the page moves it to the next card when one is marked 확인했어요)
const issueKey = (c) => String(c.rc || c.t + c.date);
const half = `0 1 calc(50% - ${SPACE(1)}px)`;
function IssueCard({ c, onSeen }) {
  const titleId = "look-title-" + issueKey(c);
  const href = dartFilingUrl(c.rc);
  return (
    <LookCard data-ui-v2="look-issue" data-t={c.t} data-rc={c.rc} data-kind={c.kind} data-body={c.body} data-date={c.date} data-key={issueKey(c)} tabIndex={-1}
      icon="warning" tone="risk" t={c.t} name={c.nk} title={issueTitle(c)} titleId={titleId} date={mdText(c.date)}
      tag={<span data-ui-v2="look-tag" style={{ flexShrink: 0 }}><StatusChip tone="watch">{C.daily.check}</StatusChip></span>}
      actions={(href || onSeen) && (
        // the board's two halves: 공시 보기 on the left (outlined), 확인했어요 on the right (navy); either one alone keeps its half
        <div style={{ marginTop: SPACE(3), display: "flex", gap: SPACE(2) }}>
          {href && (
            <a data-ui-v2="look-open" aria-describedby={titleId} href={href} target="_blank" rel="noopener"
              style={{ ...btn, flex: half, border: `1.5px solid ${COLOR.edge}`, background: COLOR.surface, ...tx(SIZE.sm, WEIGHT.bold, COLOR.ink) }}>
              {L().open}<Icon name="arrow-square-out" size={16} tone="on" /></a>
          )}
          {onSeen && (
            <button type="button" data-ui-v2="look-seen" aria-describedby={titleId} onClick={() => onSeen(c)}
              style={{ ...btn, flex: half, marginLeft: "auto", border: "none", background: COLOR.primary, ...tx(SIZE.sm, WEIGHT.bold, COLOR.onPrimary) }}>{L().seen}</button>
          )}
        </div>
      )}>
      {body(issueText(c))}
    </LookCard>
  );
}

function InsiderCard({ c }) {
  const text = insiderText(c);
  return (
    <LookCard data-ui-v2="look-insider" data-t={c.t} data-rc={c.rc} data-role={c.title} data-date={c.date} data-won={Math.round(c.won)}
      icon="identification-badge" tone="disc" t={c.t} name={c.nk} title={insiderTitle(c)} date={mdText(c.date)}>
      {body(text, <Bolded text={text} part={c.up ? C.co.disc.buys : C.co.disc.sells} />)}
    </LookCard>
  );
}

function NpsCard({ c }) {
  return (
    <LookCard data-ui-v2="look-nps" data-t={c.t} data-date={c.date} data-a={c.a} data-b={c.b}
      icon="bank" tone="disc" t={c.t} name={c.nk} title={npsTitle(c)} date={mdText(c.date)}>
      {body(npsText(c))}
    </LookCard>
  );
}

function DatesCard({ rows, noKr }) {
  return (
    <LookCard data-ui-v2="look-dates" data-n={rows.length} icon="calendar-dots" tone="earn" title={L().dates}>
      {rows.map((r) => (
        <div key={r.t + r.kind + r.date} data-ui-v2="look-date-row" data-t={r.t} data-kind={r.kind} data-date={r.date}
          style={{ display: "flex", alignItems: "center", gap: SPACE(2) + 2, paddingTop: SPACE(2) + 1 }}>
          <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { width: SPACE(17), flexShrink: 0, whiteSpace: "nowrap" })}>{mdText(r.date)}</span>
          <CoMark t={r.t} name={r.nk} size={MARK} />
          <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{r.nk}</span>
          <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { flexShrink: 0, whiteSpace: "nowrap" })}>{dateKind(r.kind)}</span>
        </div>
      ))}
      {rows.length > 0 && <p data-ui-v2="look-us-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{L().usNote}</p>}
      {noKr && <p data-ui-v2="look-no-kr" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(rows.length ? 1 : 2) })}>{L().noKr}</p>}
    </LookCard>
  );
}

// The 공시 tab's failure message or date line, beside the file-text chip (as on 홈: home2.jsx DiscNote).
function FileNote({ id, date, children }) {
  return (
    <Card data-ui-v2={id} data-date={date || undefined} style={{ marginTop: SPACE(2), padding: SPACE(3) + 2, display: "flex", alignItems: "center", gap: SPACE(3) }}>
      <IconChip name="file-text" size={40} />
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </Card>
  );
}
export function LookNotes({ m, prefix }) {
  return (
    <>
      {m.discFail && <FileNote id={prefix + "-disc-fail"}><LoadFail picture={false} inline /></FileNote>}
      {m.discOld && <FileNote id={prefix + "-disc-old"} date={m.discOld.date}><DateLine date={m.discOld.date} fresh={{ stale: m.discOld.stale, days: m.discOld.days }} style={{ marginTop: 0 }} /></FileNote>}
      {m.issueFail && <FileNote id={prefix + "-issue-fail"}><LoadFail picture={false} inline /></FileNote>}
    </>
  );
}

// 지분 변동 and 국민연금 together, newest first (a 지분 변동 before a 국민연금 filing of the same day)
const filingsOf = (m) => [...shownInsider(m).map((c) => ({ c, k: "ins" })), ...m.nps.map((c) => ({ c, k: "nps" }))]
  .sort((a, b) => (a.c.date < b.c.date ? 1 : a.c.date > b.c.date ? -1 : a.k === b.k ? 0 : a.k === "ins" ? -1 : 1));

// ---------------- the page ----------------
// onBack: back to 홈 · onLeave: the same, when there is nothing to show · onWatch: opens 관심 종목 (a 관심 종목 조건 card).
export function TodayLook({ load, store, setStoreData, disc, pad, onBack, onLeave, onWatch }) {
  const today = todayKst();
  const m = useMemo(() => lookModel(load, store, disc, today), [load, store, disc, today]);
  const canMark = !!(store.writable && !store.locked);
  const hits = useMemo(() => (m.fresh ? watchHits(store.data, load, undefined, canMark) : []), [m.fresh, store.data, load, canMark]);
  const filings = filingsOf(m);
  const cards = m.issue.length + hits.length + filings.length + (m.dates.length ? 1 : 0);
  // settled: the data is in and, with a Korean stock covered, the filings too (loaded, failed or stopped)
  const settled = load.status === "fail" || (load.status === "ok" && (!m.fresh || m.ds !== "wait"));
  const leave = settled && (!m.fresh || (!cards && !m.discFail && !m.discOld && !m.issueFail));
  useEffect(() => { lookSay(m, "page"); }, [m]);
  useEffect(() => {
    if (!leave) return;
    console.info(`[v2] today-look: nothing to show here (${load.status !== "ok" ? "no data" : !m.fresh ? "the data is not fresh" : "no card"}): back to the home screen`);
    onLeave();
  }, [leave]);
  // After 확인했어요 the card goes away: focus moves to the next 확인 필요 card, or to the page heading when it was the last one.
  const headRef = useRef(null);
  const [focusTo, setFocusTo] = useState(null);           // { key } | { head: true }
  useEffect(() => {
    if (!focusTo) return;
    const el = focusTo.key ? document.querySelector(`[data-ui-v2="look-issue"][data-key="${focusTo.key}"]`) : headRef.current;
    if (el && typeof el.focus === "function") { try { el.focus(); } catch (e) { /* ignore */ } }
    setFocusTo(null);
  }, [focusTo, m]);
  const onSeen = canMark ? (c) => {
    const next = withSeen(store.data, c, todayKst(), Date.now());
    if (!next) { console.warn("[v2] today-look: the mark was not saved for " + c.t + " " + c.rc); return; }
    const i = m.issue.findIndex((x) => issueKey(x) === issueKey(c));
    const after = i >= 0 ? m.issue[i + 1] : null;
    setStoreData(next);
    setFocusTo(after ? { key: issueKey(after) } : { head: true });
  } : null;
  const ok = load.status === "ok" && m.fresh;
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.app.tabs.home} />
      {ok && (
        <div data-ui-v2="today-look" data-disc={m.ds} data-n={cards}>
          <h2 ref={headRef} tabIndex={-1} data-ui-v2="today-look-head" style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(2) })}>{C.home.look}</h2>
          <DateLine date={load.data.pxDate} fresh={load.fresh} />
          <LookNotes m={m} prefix="look" />
          {m.issue.map((c) => <IssueCard key={issueKey(c)} c={c} onSeen={onSeen} />)}
          <WatchHitRows hits={hits} load={load} onOpen={onWatch} />
          {filings.map(({ c, k }) => (k === "ins" ? <InsiderCard key={"i" + c.rc} c={c} /> : <NpsCard key={"n" + c.t + c.date} c={c} />))}
          {(m.dates.length > 0 || (cards > 0 && m.noKr)) && <DatesCard rows={m.dates} noKr={m.noKr} />}
        </div>
      )}
      <Footer />
    </Page>
  );
}

// ---------------- 홈's compact rows ----------------
// One row: the icon chip, the title and the date (and, for 일정, the US-date note), opening the 오늘 볼 것 page.
function Row({ icon, tone, title, sub, note, onOpen, data }) {
  return (
    <button type="button" {...data} onClick={onOpen}
      style={{ ...tap, width: "100%", marginTop: SPACE(2), border: "none", textAlign: "left", background: COLOR.surface, borderRadius: RADIUS.lg - 2, padding: SPACE(3) + 2,
        display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH }}>
      <IconChip name={icon} tone={tone} size={40} />
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block", wordBreak: "keep-all" })}>{title}</span>
        {sub && <span data-ui-v2="home-look-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2 })}>{sub}</span>}
        {note && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{note}</span>}
      </span>
      <Icon name="chevronRight" size={18} tone="on" />
    </button>
  );
}
// part: "issue" (확인 필요: before the 관심 종목 rows) · "filings" (a watched stock's 지분 변동 and every 국민연금) · "dates".
// heldTs: the stocks 홈's 공시 row already covers (their 지분 변동 cards get no row of their own here).
export function LookRows({ m, part, onOpen, heldTs = null }) {
  if (!m || !m.fresh) return null;
  if (part === "issue") {
    return m.issue.map((c) => (
      <Row key={"is" + (c.rc || c.t + c.date)} icon="warning" tone="risk" title={issueTitle(c)} sub={mdText(c.date)} onOpen={onOpen}
        data={{ "data-ui-v2": "home-issue", "data-t": c.t, "data-rc": c.rc, "data-kind": c.kind, "data-date": c.date }} />
    ));
  }
  if (part === "filings") {
    return filingsOf(m).filter(({ c, k }) => k !== "ins" || !(heldTs && heldTs.has(c.t))).map(({ c, k }) => (k === "ins"
      ? <Row key={"in" + c.rc} icon="identification-badge" tone="disc" title={insiderTitle(c)} sub={mdText(c.date)} onOpen={onOpen}
          data={{ "data-ui-v2": "home-insider", "data-t": c.t, "data-rc": c.rc, "data-date": c.date }} />
      : <Row key={"np" + c.t + c.date} icon="bank" tone="disc" title={npsTitle(c)} sub={mdText(c.date)} onOpen={onOpen}
          data={{ "data-ui-v2": "home-nps", "data-t": c.t, "data-date": c.date }} />));
  }
  if (part === "dates" && m.dates.length) {
    return <Row icon="calendar-dots" tone="earn" title={L().dates} sub={mdText(m.dates[0].date)} note={L().usNote} onOpen={onOpen}
      data={{ "data-ui-v2": "home-dates", "data-n": m.dates.length, "data-date": m.dates[0].date }} />;
  }
  return null;
}
// How many compact rows LookRows draws (home2.jsx: anything here means 오늘 볼 것 is not quiet).
export const lookRowCount = (m, heldTs = null) => (m && m.fresh
  ? m.issue.length + filingsOf(m).filter(({ c, k }) => k !== "ins" || !(heldTs && heldTs.has(c.t))).length + (m.dates.length ? 1 : 0) : 0);
