// ================= 두 종목 비교 · 바꾸기 (v19.7b, docs/tasks/v19.7-portfolio-edit.md Part E, board PfCompare3) =================
// #portfolio/edit/<portfolio id>/compare/<candidate code>, opened from 비교 on 내 기준으로 찾기. The candidate against one holding:
// by default the holding with a broken rule, else the one with the lowest 내 기준 rank (find.js defaultHolding); "어떤 종목과
// 비교할까요?" picks another (hidden with one holding).
// - Verdict (cards lead with the conclusion): only from two facts, 내 기준 (상위 x%) and the past year's price swings (vol), with the
//   approved variants (find.js verdictOf). A blank or equal fact is left out; with neither, no verdict line. Never returns.
// - Rows (holding | candidate), plain values, no colour judging, each the company page's own number and its own blank rules
//   (compareCells): 내 기준 · 업종 (+ 새 업종) · 주가 변동 (지난 1년) · 코스피 1% → (the β band, US against S&P 500; 자료가 없어요
//   when unreliable) · PBR · 배당수익률 (verified only) · 오늘 주가가 가정하는 성장 (impliedGrowth: its number and edge lines) ·
//   재무 경고 신호 ("확인한" rules). A number the data blanked reads "–" with the same approved line the company page puts there.
//   Under the table the approved β note.
// - 바꾸면 업종 비중: the bar after the swap and "{group} {a}% → {b}% · 업종 {n}개 → {m}개" for the part that moves most.
// - "{candidate}만 담기" → the 담기 sheet (Part C). "{holding}과/와 바꾸기" → the 빼기 sheet for the holding with 더 잘 맞는 종목을
//   찾았어요 picked; after it completes the candidate takes the holding's target (edit.js swapDraft · sellAndSwap). The note under
//   the buttons explains both (its second sentence only when there are shares to sell).
// No 뱁이 (numbers). No Korean here: src/copy/v2.js.
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Button, BottomSheet } from "../ui/components.jsx";
import { C, fill, p1 } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, Footer, Note, SIDE_W, tx, tap, useLayout, useHeld } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { num } from "./engine.js";
import { riskTile, impliedGrowth, divKr, divUs, divShareHidden, round } from "./company.js";
import { criteriaPct } from "./fitpct.js";
import { riskBandText, riskBandNote, timesText, yieldText, usOf } from "./cofmt.js";
import { subjectParticle } from "./track.js";
import { stmtNotWonFor, unitHeldFor, pxBadFor, pxBadHidesFor, noStmtFor, fixNotesHidden, epsLineKind, epsBasisCardGone } from "./fix.js";
import { pxBadText, pxBadOneText, unitChkText, stmtCurText, fcurNoteText, prefText, prefFitText, epsFixText } from "./fixnote.jsx";
import { fcurBlank, fcurDyBlank, pbrZeroOf, fgnBlank, FGN_LINE_KEYS } from "./fcur.js";
import { IndBar, pctText, addWarnView } from "./editparts.jsx";
import { indText, listDate } from "./finder.jsx";
import * as E from "./edit.js";
import * as F from "./find.js";

const DASH = "–";                                      // "–": a blank number, as everywhere in 2.0 (never 0)
const rateText = (g) => (g < 0 ? "−" : "") + p1(Math.abs(g));     // the company page's first-year rate (cotabs.jsx)
const cell = (text, note = null, data = {}) => ({ text, note, data });
// The verdict box (review, 2026-11-15): one neutral box for every wording, so "…덜 맞고 … 더 컸어요" never sits on the calm green; true
// gives the board's green (COLOR.heroCalm) to every wording, if Jack prefers it.
export const VERDICT_CALM = false;
// The β band in a cell: the short form once Jack approves it (cmp.p), and only in a cell whose benchmark is the row label's
// (review S3: under "코스피 1% →" a US stock keeps "S&P 500 1% → 평균 …"); else the company page's approved tile text, whole.
function betaText(s, r, shortOk = false) {
  const b = r.band;
  const short = !shortOk ? null : b.one ? C.cmp.p.betaOne : C.cmp.p.beta;
  if (short) return b.one ? fill(short, { x: (b.lo < 0 ? "−" : "") + p1(Math.abs(b.lo)) }) : fill(short, { lo: (b.lo < 0 ? "−" : "") + p1(Math.abs(b.lo)), hi: (b.hi < 0 ? "−" : "") + p1(Math.abs(b.hi)) });
  return riskBandText(s, r);
}
// The line under a foreign company's number blanked for its kind (fixnote.jsx FgnCutNote, #133: co.fgnCut, co.fgnNoCmp for
// "nocompare-own", co.fgnStopped for a day the check stopped); null while that kind's copy is missing (a plain "–").
function fgnLine(s, k) {
  const hit = FGN_LINE_KEYS.find(([, has]) => has(s.fgnCut[k]));
  return hit && C.co[hit[0]] ? C.co[hit[0]] : null;
}
// The company page's PER/EPS line where its 지금 가격이 가정하는 것 card has no numbers (impliedGrowth "basis"; cotabs Dcf).
function epsBasisLine(s) {
  if (epsBasisCardGone(s) || fixNotesHidden()) return null;
  return epsLineKind(s) === "total" ? C.fix.total || null : epsFixText();
}

// The eight cells of one stock (pure; tests). s: its data.json row (null: not in today's data, every number "–") · co: its corp.json
// row · ctx: { stocks, points, names, load, groups (the portfolio's industry groups, for 새 업종) | null, row (its edit row) | null,
// betaShort (this cell's benchmark is the β row label's: the short β form may be used once approved) }.
// -> { fit, ind, vol, beta, pbr, dy, growth, warn }: { text, note, data }
export function compareCells(s, co, ctx) {
  const out = {};
  // 내 기준: the one number (criteriaPct), "–" when it cannot be scored (우선주: the company page's line)
  const mk = s && s.cls === "us" ? "us" : "kr";
  const pct = s && (s.cls === "kr" || s.cls === "us") && ctx.points ? criteriaPct(ctx.stocks, mk, ctx.points).get(s.t) : undefined;
  out.fit = typeof pct === "number" ? cell(fill(C.rank.mineX, { x: pct }), null, { pct }) : cell(DASH, s ? prefFitText(s) : null, { pct: "" });
  // 업종: the group's name (안전자산 for a 채권·금 holding); a candidate whose group is new to the portfolio adds 새 업종
  const row = ctx.row || (s ? { t: s.t, add: { ind: s.ind || null } } : null);
  const g = row ? E.indOf(row, ctx.load.byT, ctx.names) : null;
  const indName = g === E.CUSHION ? C.build.s4.cushionLabel : s ? indText(s, ctx.load, ctx.names) : g || C.rpt.noInd;
  const fresh = !!(ctx.groups && s && F.newGroup(s, ctx.groups));
  out.ind = cell(fresh ? `${indName} · ${C.find.newInd}` : indName, null, { newInd: fresh ? "1" : "" });
  if (!s) {
    for (const k of ["vol", "beta", "pbr", "dy", "growth", "warn"]) out[k] = cell(DASH);
    return out;
  }
  // 주가 변동 (지난 1년): vol, "연 변동성 {x}%"; blanked for a broken price history -> the company page's line
  const v = num(s.vol);
  out.vol = v != null ? cell(fill(C.rank.num.vol, { x: p1(v) }), null, { vol: v })
    : cell(DASH, pxBadHidesFor(s, co, "vol") ? pxBadText(s, co) || pxBadOneText(s, co, "vol") : null, { vol: "" });
  // 코스피 1% →: the β band (riskTile, v19.3 Part O); a broken price history -> "–" with its line; no band -> 자료가 없어요
  if (pxBadFor(s, co)) out.beta = cell(DASH, pxBadOneText(s, co, "beta") || pxBadText(s, co), { band: "pxbad" });
  else {
    const r = riskTile(s);
    out.beta = r.band ? cell(betaText(s, r, !!ctx.betaShort), null, { lo: r.band.lo, hi: r.band.hi, one: r.band.one ? "1" : "" }) : cell(C.co.tiles.na, null, { band: "" });
  }
  // PBR: the company page's order of blanks (Tiles: statements not in won or the unit check; then the US lines); else the PBR
  // with two decimals, or 자료가 없어요 for none (and the no-statements line where it explains it)
  if (stmtNotWonFor(s, co) || unitHeldFor(s, co)) out.pbr = cell(DASH, unitChkText(s, co) || stmtCurText(s, co), { blank: "cur" });
  else if (fcurBlank(s)) out.pbr = cell(DASH, fcurNoteText(s), { blank: "fcur" });
  else if (pbrZeroOf(s)) out.pbr = cell(DASH, C.co.pbrZero || null, { blank: "pbr0" });
  else if (fgnBlank(s, "pbr")) out.pbr = cell(DASH, fgnLine(s, "pbr"), { blank: "fgn" });
  else {
    const pbr = num(s.pbr);
    // none: 자료가 없어요, with the company page's reason when it has one (no statements yet; a 우선주: its header line)
    out.pbr = pbr > 0 ? cell(timesText(pbr, 2), null, { pbr })
      : cell(C.co.tiles.na, noStmtFor(s, co) ? C.co.noStmt || null : prefText(s), { pbr: "" });
  }
  // 배당수익률: verified only (divKr / divUs, the 배당 tile's yield), else "–" with the line the company page gives that blank
  if (fcurDyBlank(s)) out.dy = cell(DASH, fcurNoteText(s), { blank: "fcur" });
  else if (fgnBlank(s, "dy")) out.dy = cell(DASH, fgnLine(s, "dy"), { blank: "fgn" });
  else {
    const r = usOf(s) ? divUs(s) : divKr(s, co);
    out.dy = r.yieldPct != null ? cell(yieldText(r.yieldPct), null, { y: r.yieldPct })
      : cell(DASH, !usOf(s) && divShareHidden(s, co) ? C.co.div.shareHidden || null : noStmtFor(s, co) ? C.co.noStmt || null : null, { y: "" });
  }
  // 오늘 주가가 가정하는 성장: impliedGrowth, the company page's number ("첫해 {g}%") or its edge line; US and no data -> "–"
  const ig = impliedGrowth(s, co);
  const D = C.co.dcf;
  if (ig.g != null) out.growth = cell(fill(D.perYear, { g: rateText(round(ig.g, 1)) }), null, { g: round(ig.g, 1) });
  else if (ig.edge === "low" || ig.edge === "high") out.growth = cell(D[ig.edge], null, { edge: ig.edge, long: "1" });
  else if (ig.why === "loss") out.growth = cell(D.loss, null, { edge: "loss", long: "1" });
  else out.growth = cell(DASH, ig.why === "basis" ? epsBasisLine(s) : null, { edge: ig.why || "" });
  // 재무 경고 신호: the 담기 sheet's rule (the company page's): a count when every check ran, "확인한 …" when only some did, Jack's
  // line when none could; the lines that say what could not be checked under it. US stocks: no Korean filings to check -> "–".
  const wv = addWarnView(s, co);
  if (wv.kind === "flags" || wv.kind === "none") out.warn = cell(fill(C.app.count, { count: wv.w.flags.length }), wv.why, { n: wv.w.flags.length, kind: wv.kind });
  else if (wv.kind === "partial" || wv.kind === "some") out.warn = cell(wv.warnLine, wv.why, { n: 0, kind: wv.kind, long: "1" });
  else if (wv.unchecked) out.warn = cell(C.co.warn.noData, null, { kind: "unchecked", long: "1" });
  else out.warn = cell(DASH, null, { kind: "" });
  return out;
}
export const ROWS = ["fit", "ind", "vol", "beta", "pbr", "dy", "growth", "warn"];

// The verdict line (find.js verdictOf's kind), with the particle after the candidate's name. -> string or null
export function verdictText(kind, b) {
  if (!kind) return null;
  const V = C.cmp.verdict;
  const consonant = subjectParticle(b) === "i";
  const topic = kind === "lessSmall" || kind === "worse" || kind === "less";
  const key = consonant ? kind : kind + (topic ? "Neun" : "Ga");
  return V[key] ? fill(V[key], { b }) : null;
}
export const swapLabel = (a) => fill(subjectParticle(a) === "i" ? C.cmp.swap : C.cmp.swapWa, { a });
export const swapNoteText = (a, b, x) => fill(subjectParticle(b) === "i" ? C.cmp.swapNote : C.cmp.swapNoteGa, { a, b, x });

// "어떤 종목과 비교할까요?": the holdings, one to pick (a radio group in a sheet).
function Picker({ rows, value, deck, load, names, shift, onPick, onClose }) {
  return (
    <BottomSheet open title={C.cmp.picker} onClose={onClose} closeLabel={C.app.close} shift={shift}>
      <div role="radiogroup" aria-label={C.cmp.picker} data-ui-v2="cmp-picker" style={{ display: "flex", flexDirection: "column" }}>
        {rows.map((r) => {
          const on = r.t === value;
          const ind = E.indOf(r, load.byT, names);
          return (
            <button key={r.t} type="button" role="radio" aria-checked={on ? "true" : "false"} data-pick={r.t} onClick={() => onPick(r.t)}
              style={{ ...tap, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(2), padding: `${SPACE(1)}px ${SPACE(2)}px`, border: "none",
                borderRadius: RADIUS.sm, background: on ? COLOR.select : "none", boxShadow: on ? `inset 3px 0 0 ${COLOR.ink}` : "none", textAlign: "left" }}>
              <CoMark t={r.t} name={r.nk} s={load.byT.get(r.t)} size={SPACE(8)} />
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{r.nk}</span>
                <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>
                  {fill(C.edit.row, { qty: E.heldShares(deck, r.t).toLocaleString("ko-KR", { maximumFractionDigits: 4 }), industry: ind === E.CUSHION ? C.build.s4.cushionLabel : ind || C.rpt.noInd })}</span>
              </span>
              {on && <Icon name="check" size={18} tone="on" />}
            </button>
          );
        })}
      </div>
    </BottomSheet>
  );
}

// deck · draft: the stored portfolio and the edits waiting · candT: the candidate's code · holdT / setHoldT: the holding chosen
// (null: the default) · xOf(t): today's evaluation of a holding (its broken rule) · onAdd(s) · onSwap(holdT, s): the two buttons.
export function Compare({ deck, draft, load, pad, candT, holdT, setHoldT, xOf, onBack, onAdd, onSwap }) {
  const { wide } = useLayout();
  const held = useHeld();
  const [picking, setPicking] = useState(false);
  const names = useMemo(() => E.indNames(load.data.stocks), [load]);
  const points = (F.findSettings(deck) || {}).points || null;
  const cand = load.byT.get(candT) || null;
  const holds = F.compareHoldings(deck, draft);
  const pctOf = (t) => {
    const s = load.byT.get(t);
    if (!s || !points || (s.cls !== "kr" && s.cls !== "us")) return null;
    const p = criteriaPct(load.data.stocks, s.cls === "us" ? "us" : "kr", points).get(t);
    return typeof p === "number" ? p : null;
  };
  const def = F.defaultHolding(holds, pctOf, (t) => !!E.brokenReason(xOf(t)));
  const h = holds.find((r) => r.t === holdT) || holds.find((r) => r.t === def) || null;
  const groups = F.heldGroups(deck, draft, load.byT);
  const page = (body) => (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.find.title} />
      {(load.fresh && load.fresh.stale) || held ? <DateLine date={load.data.pxDate} fresh={load.fresh} /> : null}
      <div data-ui-v2="cmp" data-deck-id={deck.id} data-cand={candT} data-hold={h ? h.t : ""}>
        <ScreenTitle>{C.cmp.title}</ScreenTitle>
        {body}
      </div>
      <Footer />
    </Page>
  );
  // a code not in today's data: the company page's own line (editor.jsx shows 내 기준으로 찾기 instead when there is no 기준 or no
  // holding to compare with)
  if (!cand || !h || !points) return page(<Note data-ui-v2="cmp-none">{C.co.notFound}</Note>);
  const hs = load.byT.get(h.t) || null;
  const ctxBase = { stocks: load.data.stocks, points, names, load };
  // the β row's label: "코스피 1% →"; two US stocks read against S&P 500 (the words before "평균" in the approved US tile text; proposal
  // P4 until Jack says yes, docs/tasks/v18.3-new-strings-pending.md). A cell may drop its benchmark only when it is the label's.
  const bothUs = !!hs && usOf(hs) && usOf(cand);
  const usBeta = (C.co.tiles.riskBand.us || "").split(" \u2192 ")[0];
  const betaLabel = bothUs && usBeta ? `${usBeta} \u2192` : C.cmp.rows.beta;
  const sameBench = (s) => !!s && (bothUs || !usOf(s));
  const A = compareCells(hs, hs ? load.coByT.get(h.t) || null : null, { ...ctxBase, groups: null, row: h, betaShort: sameBench(hs) });
  const B = compareCells(cand, load.coByT.get(cand.t) || null, { ...ctxBase, groups, row: null, betaShort: sameBench(cand) });
  const vd = F.verdictOf({ pct: A.fit.data.pct === "" ? null : A.fit.data.pct, vol: A.vol.data.vol === "" ? null : A.vol.data.vol },
    { pct: B.fit.data.pct === "" ? null : B.fit.data.pct, vol: B.vol.data.vol === "" ? null : B.vol.data.vol });
  const verdict = verdictText(vd.kind, cand.nk);
  const bandShown = [hs, cand].map((s) => (s && !pxBadFor(s, load.coByT.get(s.t) || null) ? riskTile(s) : null)).filter((r) => r && r.band);
  const betaNote = bandShown.length ? (bandShown.some((r) => !r.band.one) ? C.co.risk.bandNote : riskBandNote(bandShown[0])) : null;
  // after the swap: the bar, its line and the note's target all come from the write the swap will make (edit.swapView, review
  // B1/S5): with shares, 팔고 빼기's stored target set; without, the draft's
  const add = { t: cand.t, nk: cand.nk, cls: cand.cls === "us" || cand.cls === "kr" ? cand.cls : null, ind: cand.ind || null, kind: "pinned", s: cand };
  const sv = E.swapView(deck, draft, h.t, add);
  const before = E.indBar(sv ? sv.before : E.editRows(deck, draft), load.byT, names);
  const after = sv ? E.indBar(sv.rows, load.byT, names) : before;
  const ch = sv ? F.afterChange(before, after) : null;
  const shares = !!sv && sv.path === "sale";
  const head = (s, nk, t, label) => (
    <th scope="col" style={{ textAlign: "left", verticalAlign: "bottom", padding: `0 0 ${SPACE(2)}px ${SPACE(2)}px`, fontWeight: "normal" }}>
      <div style={{ display: "flex" }}><CoMark s={s || undefined} t={t} name={nk} size={SPACE(8)} /></div>
      <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { display: "block", marginTop: SPACE(1), wordBreak: "keep-all", overflowWrap: "anywhere" })}>{nk}</span>
      <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{label}</span>
    </th>
  );
  const val = (c, id, side) => (
    <td data-cmp-cell={id} data-side={side} {...Object.fromEntries(Object.entries(c.data).map(([k, v]) => [`data-${k}`, v == null ? "" : String(v)]))}
      style={{ verticalAlign: "top", padding: `${SPACE(2) + 2}px 0 ${SPACE(2) + 2}px ${SPACE(2)}px`, borderTop: `1px solid ${COLOR.line}` }}>
      <span style={tx(c.data.long ? SIZE.xs : SIZE.sm, c.data.long ? WEIGHT.semi : WEIGHT.heavy, COLOR.ink, { display: "block", wordBreak: "keep-all", overflowWrap: "anywhere" })}>{c.text}</span>
      {c.note && <span data-ui-v2="cmp-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block", marginTop: 2, wordBreak: "keep-all" })}>{c.note}</span>}
    </td>
  );
  const labels = { ...C.cmp.rows, beta: betaLabel };
  const dates = listDate(load, [hs, cand].filter(Boolean).map((s) => ({ s })), points);
  return (
    <>
      {page(
        <>
          {verdict && (
            <section data-ui-v2="cmp-verdict" data-kind={vd.kind} data-tint={VERDICT_CALM ? "calm" : "neutral"} style={{ background: VERDICT_CALM ? COLOR.heroCalm : COLOR.neutralBg, borderRadius: RADIUS.lg, padding: `${SPACE(3) + 2}px ${SPACE(4)}px`, marginTop: SPACE(3) }}>
              <p style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.45, wordBreak: "keep-all" })}>{verdict}</p>
            </section>
          )}
          {holds.length > 1 && (
            <div data-ui-v2="cmp-pick" style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: SPACE(2), marginTop: SPACE(3) }}>
              <span id="cmp-pick-q" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{C.cmp.picker}</span>
              <button type="button" id="cmp-pick-btn" data-ui-v2="cmp-pick-open" aria-haspopup="dialog" aria-labelledby="cmp-pick-q cmp-pick-btn" onClick={() => setPicking(true)}
                style={{ ...tap, display: "inline-flex", alignItems: "center", gap: SPACE(1), minHeight: TOUCH, padding: `0 ${SPACE(3)}px`, borderRadius: TOUCH / 2,
                  border: "none", background: COLOR.surface, boxShadow: `inset 0 0 0 1px ${COLOR.chipEdge}`, ...tx(SIZE.xs, WEIGHT.heavy, COLOR.ink, { maxWidth: "100%" }) }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.nk}</span>
                <Icon name="caret-down" size={16} tone="on" />
              </button>
            </div>
          )}
          <Card data-ui-v2="cmp-table" style={{ padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
            <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
              <colgroup><col style={{ width: "32%" }} /><col style={{ width: "34%" }} /><col style={{ width: "34%" }} /></colgroup>
              <thead><tr><td />{head(hs, h.nk, h.t, C.cmp.held)}{head(cand, cand.nk, cand.t, C.cmp.cand)}</tr></thead>
              <tbody>
                {ROWS.map((id) => (
                  <tr key={id} data-cmp-row={id}>
                    <th scope="row" style={{ textAlign: "left", verticalAlign: "top", padding: `${SPACE(2) + 2}px 0`, borderTop: `1px solid ${COLOR.line}`,
                      ...tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { wordBreak: "keep-all" }) }}>{labels[id]}</th>
                    {val(A[id], id, "hold")}
                    {val(B[id], id, "cand")}
                  </tr>
                ))}
              </tbody>
            </table>
            {betaNote && <Note data-ui-v2="cmp-beta-note">{betaNote}</Note>}
          </Card>
          <Card data-ui-v2="cmp-after" data-path={sv ? sv.path : ""} style={{ padding: `${SPACE(3) + 2}px ${SPACE(4)}px` }}>
            <h3 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginBottom: SPACE(2) })}>{C.cmp.after}</h3>
            <IndBar parts={after} />
            {ch && (
              <p data-ui-v2="cmp-after-line" data-ind={ch.key} style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(2), wordBreak: "keep-all" })}>
                {fill(C.cmp.afterLine, { group: ch.name, a: pctText(ch.a), b: pctText(ch.b), n: ch.n, m: ch.m })}</p>
            )}
          </Card>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: SPACE(2), marginTop: SPACE(4) }}>
            <Button kind="secondary" onClick={() => onAdd(cand)} style={{ padding: `0 ${SPACE(2)}px`, fontSize: SIZE.sm, wordBreak: "keep-all" }}>
              <span data-ui-v2="cmp-add">{fill(C.cmp.addOnly, { b: cand.nk })}</span></Button>
            <Button onClick={() => onSwap(h.t, cand)} style={{ padding: `0 ${SPACE(2)}px`, fontSize: SIZE.sm, wordBreak: "keep-all" }}>
              <span data-ui-v2="cmp-swap">{swapLabel(h.nk)}</span></Button>
          </div>
          <p data-ui-v2="cmp-swap-note" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(2)}px ${SPACE(1)}px 0`, lineHeight: 1.5, wordBreak: "keep-all" })}>
            {sv && sv.pct != null && <span data-ui-v2="cmp-swap-x" data-x={sv.pct}>{swapNoteText(h.nk, cand.nk, pctText(sv.pct))}</span>}
            {shares && <span>{" "}{C.cmp.swapSale}</span>}
          </p>
          {dates.length > 0 && (
            <p data-ui-v2="cmp-date" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(2)}px ${SPACE(1)}px 0` })}>
              {dates.map((d, i) => <span key={i}>{i ? " · " : ""}{d}</span>)}
            </p>
          )}
        </>
      )}
      {picking && <Picker rows={holds} value={h.t} deck={deck} load={load} names={names} shift={wide ? SIDE_W : 0}
        onPick={(t) => { setHoldT(t); setPicking(false); }} onClose={() => setPicking(false)} />}
    </>
  );
}
