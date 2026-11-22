// ================= 이번 주 정리 card on 홈 (v19.6e, docs/tasks/v19.6-records-alerts-dark.md Part E, board Weekly2) =================
// One card per portfolio 홈 shows (home.homeBlocks: the portfolios holding something today, in store order: "the one 홈 uses",
// v19.3 Part H), at the top of 홈 under its date line, only while the week's numbers are final (weekly.js weekState) and 홈's own
// daily check runs on fresh data (home2.jsx: never on late data, round 2, where the week it would call 이번 주 is already the week
// before; nor on stale or failed data, where 홈 has no portfolio blocks). Behind weekcfg.js WEEKLY_ON (on since
// Jack approved the left-out lines, 2026-11-22).
//   hero (navy)   "{the week's first Korean trading day} ~ {pxDate}", 이번 주 정리, and for a portfolio made with 가진 종목 넣기
//                 the rule line of its 홈 hero ("내 규칙 {n}개 중 {k}개를 지키고 있어요", the same n and k, only when 홈's hero shows it:
//                 at least one rule checked). With two or more portfolios the portfolio's name (user text) starts it, as 홈's heroes do.
//   tiles         내 포트폴리오 (the week's % in price red/blue, "{±won} · 코스피 {±%}"; a won amount that rounds to 0 has no sign) ·
//                 받은 배당 ("{won}", "{n}건"; only with a record counted) · 공시 ("{n}건", "유상증자 {a} · 지분 변동 {b}": only the kinds
//                 오늘 볼 것 can show, so no 지분 변동 while look.js ROLE_OF is null) · 다음 주 / 다음 주 미국 일정 ("실적 발표 {n}", the
//                 first name). A tile with nothing to show is left out; a tile whose words are not approved yet is left out too (the
//                 console says which).
//   mover         가장 많이 움직인 종목: mark, name, the week's move, and the reason line only from the same-industry rule (fell · rose).
//   notes         the stocks left out of the week's gain (C.weekly.leftOut; more than LEFT_NAMES names: C.weekly.leftOutMore with
//                 the first LEFT_NAMES), US dividends without a rate (C.tax.divNoFx), and under WEEK_NV "note" the Naver footnote
//                 (C.weekly.nvNote, Jack 2026-11-22) naming every counted stock (and the mover) whose last-week close was confirmed
//                 through Naver: each only with approved words. "note" without its footnote's words is read as "out" (round 2); so is a
//                 card with more than LEFT_NAMES such stocks while the capped footnote (C.weekly.nvNoteMore) has no words: those stocks
//                 are then left out and named by the approved left-out line, never used without a footnote that names them all.
//   닫기          hides that portfolio's card for that week on this device (weekly.js closeWeek).
// No card when nothing but the hero would show. No 뱁이 (numbers). Colours: tokens only (dark mode). Facts only: no forecast or advice.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { C, fill, mdText, wonText, exactWon } from "./format.js";
import { tx, tap, useLayout, useNav, useMode } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { signedPct } from "./deckcalc.js";
import { isCompany } from "./stocklist.js";
import { shownName } from "./legacy.js";
import { weeklyModel, readClosed, closeWeek, WEEK_KEY, PREVIEW_WEEK_KEY, FILING_KINDS } from "./weekly.js";
import { insiderTitle } from "./todaylook.jsx";
import { WEEK_NV } from "./weekcfg.js";

const W = () => C.weekly;
// the sign of the amount as shown (format.wonText rounds: 만원 from 1만원, else 원): "+0원" never shows (round 2)
const signedWon = (v) => (Math.round(Math.abs(v)) > 0 && v > 0 ? "+" : "") + wonText(v);
// names on the left-out line before "외 {n}종목" (the approved app.krOwnCloseListMore shape, OWN_LIST_MAX)
export const LEFT_NAMES = 5;
// The WEEK_NV mode in effect: "note" needs its footnote's words (C.weekly.nvNote); without them the rows are left out ("out").
export const nvMode = (nv) => (nv === "note" && !W().nvNote ? "out" : nv);
// The stocks the footnote names: the counted ones confirmed through Naver, then the mover when it is one of them (its move reads c1w).
export const nvNames = (m) => {
  const out = (m && m.money ? m.money.per : []).filter((p) => p.nv).map((p) => p.nk);
  if (m && m.mover && m.mover.nv && !out.includes(m.mover.nk)) out.push(m.mover.nk);
  return out;
};
// One card's model: under "note" with more than LEFT_NAMES Naver-confirmed names and no capped footnote words, the card is worked out
// again under "out" (see notes above). -> { m, mode, said }
export function cardModel(args, mode) {
  const m = weeklyModel({ ...args, nv: mode });
  if (mode !== "note" || !m.ok || nvNames(m).length <= LEFT_NAMES || W().nvNoteMore) return { m, mode, said: null };
  return { m: weeklyModel({ ...args, nv: "out" }), mode: "out",
    said: `${nvNames(m).length} Naver-confirmed stocks: the capped footnote waits for Jack (C.weekly.nvNoteMore), so they are left out as under "out"` };
}
const tone = (r) => (r > 0 ? COLOR.up : r < 0 ? COLOR.down : COLOR.text2);
const r1 = (x) => Math.round(x * 10);                       // the sign as shown at one decimal

// What a card shows, from the model and the approved words. -> { tiles, mover, notes, say: [console lines], show }
export function weeklyView(m, opts = {}) {
  const say = [];
  const tiles = [], notes = [];
  if (!m || !m.ok) return { tiles, mover: null, notes, say, show: false };
  const L = W();
  // 내 포트폴리오
  const money = m.money;
  const names = money.left.map((x) => x.nk);
  if (money.left.length) say.push(`left out of the week's gain: ${money.left.map((x) => `${x.t || x.nk} (${x.why})`).join(", ")}`);
  if (!money.ok) say.push("no stock's week could be worked out: no portfolio tile");
  else if (money.left.length && !L.leftOut) say.push("the line naming the stocks left out waits for Jack (C.weekly.leftOut): no portfolio tile");
  else if (money.left.length > LEFT_NAMES && !L.leftOutMore) say.push(`${money.left.length} stocks left out: the capped line waits for Jack (C.weekly.leftOutMore): no portfolio tile`);
  else {
    const k = m.kospi && m.kospi.pct != null ? m.kospi.pct : null;
    if (k == null) say.push(`no KOSPI week (${m.kospi ? m.kospi.why : "none"})`);
    tiles.push({ id: "pf", icon: "chart-pie-slice", tone: "earn", label: L.pf, big: signedPct(money.pct), bigTone: tone(r1(money.pct)),
      sub: [signedWon(money.gain), k != null ? fill(L.kospi, { pct: signedPct(k) }) : null].filter(Boolean).join(" · "),
      data: { "data-pct": Math.round(money.pct * 1000) / 1000, "data-gain": Math.round(money.gain), "data-kospi": k != null ? Math.round(k * 1000) / 1000 : "",
        "data-n": money.n, "data-left": money.left.length } });
    if (names.length > LEFT_NAMES) notes.push({ id: "left", text: fill(L.leftOutMore, { names: names.slice(0, LEFT_NAMES).join(", "), n: names.length - LEFT_NAMES }) });
    else if (names.length) notes.push({ id: "left", text: fill(L.leftOut, { n: names.length, names: names.join(", ") }) });
  }
  const pfShown = tiles.length > 0;
  // 받은 배당
  if (m.divs.n > 0) {
    tiles.push({ id: "div", icon: "coins", tone: "div", label: L.div, big: exactWon(m.divs.won), sub: fill(L.count, { n: m.divs.n }),
      data: { "data-won": Math.round(m.divs.won), "data-n": m.divs.n, "data-nofx": m.divs.noFx } });
  }
  // a US dividend of the week without a rate: named whether or not another dividend made a tile (never "0원 · 0건", round 2)
  if (m.divs.noFx > 0 && C.tax && C.tax.divNoFx) notes.push({ id: "divfx", text: fill(C.tax.divNoFx, { n: m.divs.noFx }) });
  // 공시
  const f = m.files;
  // the insider cards 오늘 볼 것 can show (a title: look.js ROLE_OF reads the role; while it is null, none, said in the console)
  const kinds = f.ok ? { ...f.kinds, ins: f.ins.filter((c) => insiderTitle(c)).length } : null;
  if (f.ok && f.ins.length > kinds.ins) say.push(`${f.ins.length - kinds.ins} insider report(s) of the week not counted: the today-look page cannot show them yet (look.js ROLE_OF)`);
  const fn = kinds ? FILING_KINDS.reduce((a, k) => a + kinds[k], 0) : 0;
  if (f.ok && fn > 0) {
    const present = FILING_KINDS.filter((k) => kinds[k] > 0);
    const missing = present.filter((k) => !L.kinds[k]);
    if (missing.length) say.push(`this week's filings include ${missing.join(", ")}, whose tile word waits for Jack (C.weekly.kinds): no filings tile`);
    else {
      tiles.push({ id: "disc", icon: "file-text", tone: "disc", label: L.disc, big: fill(L.count, { n: fn }),
        sub: present.map((k) => fill(L.kinds[k], { n: kinds[k] })).join(" · "), data: { "data-n": fn } });
    }
  } else if (!f.ok && f.why !== "none" && f.why !== "noKr" && !(f.why === "disc" && opts.discWait)) say.push(`this week's filings were not checked (${f.why}): no filings tile`);
  // 다음 주
  const earn = m.next.filter((r) => r.kind === "earn"), xd = m.next.filter((r) => r.kind === "xd");
  const rows = m.next.filter((r) => r.kind === "earn" || (r.kind === "xd" && L.exDiv));
  if (xd.length && !L.exDiv) say.push(`next week's ex-dividend dates (${xd.map((r) => r.t).join(", ")}) wait for their word (C.weekly.exDiv)`);
  if (rows.length && L.earn) {
    const big = [earn.length ? fill(L.earn, { n: earn.length }) : null, xd.length && L.exDiv ? fill(L.exDiv, { n: xd.length }) : null].filter(Boolean).join(" · ");
    tiles.push({ id: "next", icon: "calendar-dots", tone: "earn", label: m.kr ? L.nextUs : L.next, big, sub: rows[0].nk,
      data: { "data-n": rows.length, "data-first": rows[0].t, "data-date": rows[0].date } });
  }
  // 가장 많이 움직인 종목
  const mover = m.mover ? { ...m.mover, line: m.mover.why === "fell" ? L.fell : m.mover.why === "rose" ? L.rose : null } : null;
  // WEEK_NV "note" (Jack, 2026-11-22): every number shown that reads a Naver-confirmed last-week close is named (the tile's counted
  // stocks, the mover), at most LEFT_NAMES names with "외 {n}종목" (cardModel keeps it from ever needing more without those words)
  const nv = m.nv === "note" ? nvNames({ money: { per: pfShown ? money.per : [] }, mover }) : [];
  if (nv.length > LEFT_NAMES && L.nvNoteMore) notes.push({ id: "nv", text: fill(L.nvNoteMore, { names: nv.slice(0, LEFT_NAMES).join(", "), n: nv.length - LEFT_NAMES }) });
  else if (nv.length && nv.length <= LEFT_NAMES && L.nvNote) notes.push({ id: "nv", text: fill(L.nvNote, { names: nv.join(", ") }) });
  const show = tiles.length > 0 || !!mover;
  if (!show) say.push("nothing to show but the heading: no card");
  return { tiles, mover, notes, say, show };
}

const said = new Set();
function weeklySay(id, lines) {
  for (const l of lines) {
    const k = id + "|" + l;
    if (said.has(k)) continue;
    said.add(k);
    console.warn(`[v2] weekly (${id}): ${l}`);
  }
}

function Tile({ t }) {
  return (
    <div data-ui-v2="weekly-tile" data-tile={t.id} {...t.data}
      style={{ background: COLOR.surface, borderRadius: RADIUS.lg - 2, padding: SPACE(3) + 2, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <IconChip name={t.icon} tone={t.tone} size={30} />
        <span data-ui-v2="weekly-label" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { minWidth: 0, lineHeight: 1.35, wordBreak: "keep-all" })}>{t.label}</span>
      </div>
      <p data-ui-v2="weekly-big" style={tx(19, WEIGHT.heavy, t.bigTone || COLOR.ink, { marginTop: SPACE(2), lineHeight: 1.3, wordBreak: "keep-all" })}>{t.big}</p>
      {t.sub && <p data-ui-v2="weekly-sub" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: 2, wordBreak: "keep-all", overflowWrap: "anywhere" })}>{t.sub}</p>}
    </div>
  );
}

function Mover({ mv }) {
  const { openStock } = useNav();
  const open = openStock && isCompany(mv.s) ? () => openStock(mv.t) : null;
  const act = open ? { role: "button", tabIndex: 0, onClick: open, onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } } } : {};
  return (
    <section data-ui-v2="weekly-mover" data-t={mv.t} data-pct={Math.round(mv.pct * 1000) / 1000} data-why={mv.why || ""} {...act}
      style={{ ...(open ? tap : {}), marginTop: SPACE(2) + 2, background: COLOR.surface, borderRadius: RADIUS.lg, padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
      <p data-ui-v2="weekly-mover-label" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{W().mover}</p>
      <div style={{ marginTop: SPACE(2), display: "flex", alignItems: "center", gap: SPACE(2) + 2, minHeight: TOUCH }}>
        <CoMark t={mv.t} name={mv.nk} size={36} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span data-ui-v2="weekly-mover-name" style={tx(15.5, WEIGHT.heavy, COLOR.ink, { display: "block", wordBreak: "keep-all" })}>
            {mv.nk}{" "}<span data-ui-v2="weekly-mover-pct" style={{ color: tone(r1(mv.pct)), whiteSpace: "nowrap" }}>{signedPct(mv.pct)}</span>
          </span>
          {mv.line && <span data-ui-v2="weekly-mover-why" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", wordBreak: "keep-all" })}>{mv.line}</span>}
        </span>
        {open && <Icon name="chevronRight" size={16} tone="on" />}
      </div>
    </section>
  );
}

function WeeklyCard({ block, m, v, many, onClose, nvSet }) {
  const { wide } = useLayout();
  const st = block.st;
  const w = m.week;
  const titleId = "weekly-title-" + block.deck.id;
  const kept = !!(st && st.ok && st.checked > 0 && C.pfr.kept);
  const cols = wide ? Math.min(4, Math.max(2, v.tiles.length)) : 2;
  return (
    <section data-ui-v2="weekly" data-deck-id={block.deck.id} data-week={w.mon} data-from={w.first} data-to={w.to} data-nv={m.nv} data-nv-set={nvSet}
      aria-labelledby={titleId} style={{ marginTop: SPACE(4) }}>
      <div data-ui-v2="weekly-hero" style={{ background: COLOR.primary, color: COLOR.onPrimary, borderRadius: RADIUS.lg + 2, padding: SPACE(4) + 2 }}>
        {many && <p data-ui-v2="weekly-name" style={tx(SIZE.xs, WEIGHT.bold, COLOR.onPrimary, { marginBottom: SPACE(1) })}>{shownName(block.deck.name)}</p>}
        <p data-ui-v2="weekly-range" style={tx(SIZE.xs, WEIGHT.regular, COLOR.onPrimary3)}>{fill(W().range, { from: mdText(w.first), to: mdText(w.to) })}</p>
        <h2 id={titleId} data-ui-v2="weekly-title" style={tx(SIZE.h2, WEIGHT.heavy, COLOR.onPrimary, { marginTop: SPACE(1) + 2, lineHeight: 1.3 })}>{W().title}</h2>
        {kept && <p data-ui-v2="weekly-kept" data-n={st.checked} data-k={st.kept} style={tx(14, WEIGHT.regular, COLOR.onPrimary2, { marginTop: SPACE(1) + 2, wordBreak: "keep-all" })}>
          {fill(C.pfr.kept, { n: st.checked, k: st.kept })}</p>}
      </div>
      {v.tiles.length > 0 && (
        <div data-ui-v2="weekly-tiles" style={{ marginTop: SPACE(2) + 2, display: "grid", gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: SPACE(2) }}>
          {v.tiles.map((t) => <Tile key={t.id} t={t} />)}
        </div>
      )}
      {v.mover && <Mover mv={v.mover} />}
      {v.notes.map((n) => (
        <p key={n.id} data-ui-v2={"weekly-note-" + n.id} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2), padding: `0 ${SPACE(1)}px`, wordBreak: "keep-all" })}>{n.text}</p>
      ))}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: SPACE(1) }}>
        <button type="button" data-ui-v2="weekly-close" aria-describedby={titleId} onClick={onClose}
          style={{ ...tap, minHeight: TOUCH, minWidth: TOUCH, padding: `0 ${SPACE(3)}px`, border: "none", background: "none", ...tx(SIZE.sm, WEIGHT.bold, COLOR.text2) }}>
          {C.app.close}</button>
      </div>
    </section>
  );
}

// blocks: home.homeBlocks (홈's own) · load · ctx: rules.todayCtx · disc: app.jsx's · nv: WEEK_NV (tests may pass another).
export function WeeklyCards({ blocks, load, ctx, disc, nv = WEEK_NV }) {
  const { preview } = useMode();
  const key = preview ? PREVIEW_WEEK_KEY : WEEK_KEY;
  const mode = nvMode(nv);
  if (mode !== nv) weeklySay("all", [`WEEK_NV "${nv}" without its footnote's words (C.weekly.nvNote): read as "${mode}"`]);
  const models = useMemo(() => blocks.map((b) => {
    const x = cardModel({ deck: b.deck, load, ctx, disc }, mode);
    if (x.said) weeklySay(b.deck.id, [x.said]);
    return { b, m: x.m };
  }), [blocks, load, ctx, disc, mode]);
  const discWait = !!disc && disc.status !== "ok" && disc.status !== "fail" && disc.status !== "none";
  const firstOk = models.find((x) => x.m.ok);
  const mon = firstOk ? firstOk.m.week.mon : null;
  const [bump, setBump] = useState(0);
  const [gone, setGone] = useState(() => new Set());                       // closed this visit (also when storage is blocked)
  const closed = useMemo(() => new Set(mon ? readClosed(key, mon) : []), [key, mon, bump]);
  const many = blocks.length > 1;
  const out = [];
  for (const { b, m } of models) {
    if (!m.ok) { if (m.why !== "notFinal") weeklySay(b.deck.id, [`no card (${m.why})`]); continue; }
    if (closed.has(b.deck.id) || gone.has(m.week.mon + "|" + b.deck.id)) continue;
    const v = weeklyView(m, { discWait });
    weeklySay(b.deck.id, v.say);
    if (!v.show) continue;
    const close = () => {
      closeWeek(key, m.week.mon, b.deck.id);
      setGone((g) => new Set([...g, m.week.mon + "|" + b.deck.id]));
      setBump((x) => x + 1);
    };
    out.push(<WeeklyCard key={b.deck.id} block={b} m={m} v={v} many={many} onClose={close} nvSet={nv} />);
  }
  return out.length ? <div data-ui-v2="weekly-cards">{out}</div> : null;
}
