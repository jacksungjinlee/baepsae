// ================= 이번 주 정리 card on 홈 (v19.6e, docs/tasks/v19.6-records-alerts-dark.md Part E, board Weekly2) =================
// One card per portfolio 홈 shows (home.homeBlocks: the portfolios holding something today, in store order: "the one 홈 uses",
// v19.3 Part H), at the top of 홈 under its date line, only while the week's numbers are final (weekly.js weekState) and 홈's own
// daily check runs (fresh or late data: never on stale or failed data, where 홈 has no portfolio blocks). Behind weekcfg.js
// WEEKLY_ON (off until Jack approves the left-out line).
//   hero (navy)   "{the week's first Korean trading day} ~ {pxDate}", 이번 주 정리, and for a portfolio made with 가진 종목 넣기
//                 the rule line of its 홈 hero ("내 규칙 {n}개 중 {k}개를 지키고 있어요", the same n and k, only when 홈's hero shows it:
//                 at least one rule checked). With two or more portfolios the portfolio's name (user text) starts it, as 홈's heroes do.
//   tiles         내 포트폴리오 (the week's % in price red/blue, "{±won} · 코스피 {±%}") · 받은 배당 ("{won}", "{n}건") · 공시 ("{n}건",
//                 "유상증자 {a} · 지분 변동 {b}") · 다음 주 / 다음 주 미국 일정 ("실적 발표 {n}", the first name). A tile with nothing
//                 to show is left out; a tile whose words are not approved yet is left out too (the console says which).
//   mover         가장 많이 움직인 종목: mark, name, the week's move, and the reason line only from the same-industry rule (fell · rose).
//   notes         the stocks left out of the week's gain (C.weekly.leftOut), US dividends without a rate (C.tax.divNoFx), and under
//                 WEEK_NV "note" the Naver footnote (C.weekly.nvNote): each only with approved words.
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
import { WEEK_NV } from "./weekcfg.js";

const W = () => C.weekly;
const signedWon = (v) => (v > 0 ? "+" : "") + wonText(v);
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
  else {
    const k = m.kospi && m.kospi.pct != null ? m.kospi.pct : null;
    if (k == null) say.push(`no KOSPI week (${m.kospi ? m.kospi.why : "none"})`);
    tiles.push({ id: "pf", icon: "chart-pie-slice", tone: "earn", label: L.pf, big: signedPct(money.pct), bigTone: tone(r1(money.pct)),
      sub: [signedWon(money.gain), k != null ? fill(L.kospi, { pct: signedPct(k) }) : null].filter(Boolean).join(" · "),
      data: { "data-pct": Math.round(money.pct * 1000) / 1000, "data-gain": Math.round(money.gain), "data-kospi": k != null ? Math.round(k * 1000) / 1000 : "",
        "data-n": money.n, "data-left": money.left.length } });
    if (money.left.length) notes.push({ id: "left", text: fill(L.leftOut, { n: money.left.length, names: names.join(", ") }) });
    const nvNames = money.per.filter((p) => p.nv).map((p) => p.t);
    if ((opts.nv || m.nv) === "note" && nvNames.length) {
      if (L.nvNote) notes.push({ id: "nv", text: fill(L.nvNote, { names: nvNames.join(", ") }) });
      else say.push(`Naver-confirmed rows used (${nvNames.join(", ")}): their footnote waits for Jack (C.weekly.nvNote)`);
    }
  }
  // 받은 배당
  if (m.divs.n + m.divs.noFx > 0) {
    tiles.push({ id: "div", icon: "coins", tone: "div", label: L.div, big: exactWon(m.divs.won), sub: fill(L.count, { n: m.divs.n }),
      data: { "data-won": Math.round(m.divs.won), "data-n": m.divs.n, "data-nofx": m.divs.noFx } });
    if (m.divs.noFx > 0 && C.tax && C.tax.divNoFx) notes.push({ id: "divfx", text: fill(C.tax.divNoFx, { n: m.divs.noFx }) });
  }
  // 공시
  const f = m.files;
  if (f.ok && f.n > 0) {
    const present = FILING_KINDS.filter((k) => f.kinds[k] > 0);
    const missing = present.filter((k) => !L.kinds[k]);
    if (missing.length) say.push(`this week's filings include ${missing.join(", ")}, whose tile word waits for Jack (C.weekly.kinds): no filings tile`);
    else {
      tiles.push({ id: "disc", icon: "file-text", tone: "disc", label: L.disc, big: fill(L.count, { n: f.n }),
        sub: present.map((k) => fill(L.kinds[k], { n: f.kinds[k] })).join(" · "), data: { "data-n": f.n } });
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

function WeeklyCard({ block, m, v, many, onClose }) {
  const { wide } = useLayout();
  const st = block.st;
  const w = m.week;
  const titleId = "weekly-title-" + block.deck.id;
  const kept = !!(st && st.ok && st.checked > 0 && C.pfr.kept);
  const cols = wide ? Math.min(4, Math.max(2, v.tiles.length)) : 2;
  return (
    <section data-ui-v2="weekly" data-deck-id={block.deck.id} data-week={w.mon} data-from={w.first} data-to={w.to} data-nv={m.nv}
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
  const models = useMemo(() => blocks.map((b) => ({ b, m: weeklyModel({ deck: b.deck, load, ctx, disc, nv }) })), [blocks, load, ctx, disc, nv]);
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
    out.push(<WeeklyCard key={b.deck.id} block={b} m={m} v={v} many={many} onClose={close} />);
  }
  return out.length ? <div data-ui-v2="weekly-cards">{out}</div> : null;
}
