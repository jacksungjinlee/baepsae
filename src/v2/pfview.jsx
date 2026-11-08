// ================= 포트폴리오 규칙 네 가지 on screen (v19.3d, v19.3 Parts F.1 and G) =================
// A portfolio made with 가진 종목 넣기 has no per-stock rule book (store.js kind "imported"), so 홈 and 포트폴리오 show
// its four portfolio rules (pf.js pfState) instead of 확인 필요 for every stock: "{date} 종가로 점검했어요", "내 규칙 {n}개
// 중 {k}개를 지키고 있어요", one tile per rule with ✓, ! or "확인하지 못했어요" (never ✓ when a rule could not be checked),
// the one-line reason of the first broken concentration rule, and the holdings with their weights and today's change.
// Stale or failed data: nothing is checked (the screens' own stale line or load-failure message says so). No 뱁이 here.
// The same tiles open the 점검 report's 어느 업종에 몰려 있나요? chips (report.jsx). No Korean here: src/copy/v2.js.
import React from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, HOLDING_SHADES, holdingShades } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Button, ListRow, StatStrip } from "../ui/components.jsx";
import { C, fill, nf, mdText, wonText } from "./format.js";
import { Card, Note, tx } from "./ui.jsx";
import { CoMark } from "./logo.jsx";
import { shownName } from "./legacy.js";
import { isCompany } from "./stocklist.js";
import { subjectParticle } from "./track.js";
import { MissingNote } from "./tracking.jsx";
import { avgOf } from "./pf.js";
import { signedPct } from "./deckcalc.js";

const pct = (w) => Math.round(w * 100);
// v19.3e: a share shown against its limit. Whole %, but with one decimal (two if needed) whenever the whole number would
// put it on the wrong side of the limit: 30.4% against "30% 이하" is broken and must not read "30%" (pf.js compares the
// exact share). -> the number as text, without "%".
export function limitPct(w, limit) {
  const p = w * 100;
  if (p > 0 && p < 0.95) return nf(Math.round(p * 10) / 10, 1);         // a small holding never reads 0%
  const over = p > limit + 1e-9;
  for (const d of [0, 1, 2]) {
    const k = 10 ** d;
    const r = Math.round(p * k) / k;
    if (d === 2 || (over ? r > limit : r <= limit)) return nf(r, d);
  }
  return nf(p, 2);
}
// Shares: whole numbers as they are, a fraction (US, or derived from an amount) with up to 4 decimals.
export const qtyText = (q) => Number(q).toLocaleString("ko-KR", { maximumFractionDigits: 4 });
const money = (v, ccy) => (ccy === "USD" ? "$" + nf(v, 2) : fill(C.app.won, { n: nf(Math.round(v)) }));
const cardName = (id) => C.build.cards[id].name;

// The rule's name with its limit ("한 종목 30% 이하") and what was found ("최대 25%", "반도체 38%"), or null.
export function ruleLabel(r) {
  if (r.id === "stock") return fill(C.pfr.stock, { x: r.limit });
  if (r.id === "ind") return fill(C.pfr.ind, { x: r.limit });
  if (r.id === "fit") return fill(C.pfr.fit, { top: r.limit });
  return C.pfr.warn;
}
export function ruleDetail(r) {
  if (r.state === "unknown") return null;
  if (r.id === "stock") return fill(C.pfr.max, { y: limitPct(r.max.w, r.limit) });
  if (r.id === "ind") return r.top.name ? `${r.top.name} ${limitPct(r.top.w, r.limit)}%` : null;
  if (r.id === "fit") {
    const worst = r.cards.map((c) => [c.id, r.avg[c.id]]).sort((a, b) => b[1].shown - a[1].shown)[0];
    return worst ? `${cardName(worst[0])} ${fill(C.rpt.avgTop, { x: worst[1].shown })}` : null;
  }
  return r.flagged.length ? r.flagged.join(", ") : null;
}
// "{group}이 38%예요. 내 규칙은 35%까지예요." for the first broken concentration rule (the stock's or the group's name).
export function brokenLine(st) {
  const r = st && st.ok ? st.rules.find((x) => x.state === "broken" && (x.id === "stock" || x.id === "ind")) : null;
  if (!r) return null;
  const group = r.id === "stock" ? r.max.nk : r.top.name;
  if (!group) return null;
  const w = r.id === "stock" ? r.max.w : r.top.w;
  return fill(subjectParticle(group) === "i" ? C.pfr.over : C.pfr.overGa, { group, x: limitPct(w, r.limit), limit: r.limit });
}

const STATE_ICON = { ok: { name: "check-circle", tone: "ok" }, broken: { name: "warning", tone: "on" } };
// One rule: its name, then ✓ (괜찮아요) or ! with what was found, or 확인하지 못했어요.
export function RuleTile({ r }) {
  const ic = STATE_ICON[r.state];
  const detail = ruleDetail(r);
  const bg = r.state === "ok" ? COLOR.okBg : r.state === "broken" ? COLOR.watchBg : COLOR.page;
  return (
    <div data-ui-v2="pf-rule" data-rule={r.id} data-state={r.state} style={{ background: bg, borderRadius: RADIUS.md, padding: `${SPACE(2) + 2}px ${SPACE(3)}px`,
      display: "flex", alignItems: "flex-start", gap: SPACE(2), minWidth: 0 }}>
      {ic && <span role="img" aria-label={r.state === "ok" ? C.daily.ok : undefined} aria-hidden={r.state === "ok" ? undefined : true}
        style={{ display: "flex", flexShrink: 0, marginTop: 1 }}><Icon name={ic.name} size={20} tone={ic.tone} /></span>}
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", lineHeight: 1.4 })}>{ruleLabel(r)}</span>
        {r.state === "unknown" ? <span data-ui-v2="pf-rule-unknown" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>{C.pfr.unknown}</span>
          : detail && <span data-ui-v2="pf-rule-detail" style={tx(SIZE.xs, WEIGHT.bold, r.state === "broken" ? COLOR.watch : COLOR.ok, { display: "block", wordBreak: "keep-all" })}>{detail}</span>}
      </span>
    </div>
  );
}

export function RuleTiles({ st }) {
  return (
    <div data-ui-v2="pf-rules" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: SPACE(2), marginTop: SPACE(3) }}>
      {st.rules.map((r) => <RuleTile key={r.id} r={r} />)}
    </div>
  );
}

// "{date} 종가로 점검했어요" (only when at least one rule was checked: with every tile 확인하지 못했어요 nothing was) ·
// "내 규칙 {n}개 중 {k}개를 지키고 있어요" · the first broken rule's line · the unchecked count.
export function RulesHead({ st, pxDate }) {
  const md = mdText(pxDate);
  const line = brokenLine(st);
  return (
    <div data-ui-v2="pf-head" data-kept={st.kept} data-checked={st.checked} style={{ marginTop: SPACE(3) }}>
      {md && st.checked > 0 && <div data-ui-v2="pf-checked" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{fill(C.pfr.checked, { date: md })}</div>}
      {st.checked > 0 && <div data-ui-v2="pf-kept" style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1) })}>{fill(C.pfr.kept, { n: st.checked, k: st.kept })}</div>}
      {line && <div data-ui-v2="pf-broken" style={tx(SIZE.sm, WEIGHT.semi, COLOR.watch, { marginTop: SPACE(1) })}>{line}</div>}
      {st.unchecked > 0 && <Note data-ui-v2="pf-not-checked">{fill(C.daily.notChecked, { n: st.unchecked })}</Note>}
      <RuleTiles st={st} />
    </div>
  );
}

// A weight bar in the holding's navy shade (Part C: by weight rank; logo colours never colour a chart).
function WeightBar({ w, shade }) {
  return (
    <div aria-hidden="true" style={{ height: SPACE(1) + 2, background: COLOR.page, borderRadius: 999, marginTop: SPACE(1) }}>
      <div style={{ width: `${Math.min(100, Math.max(0, w * 100))}%`, height: "100%", background: shade, borderRadius: 999 }} />
    </div>
  );
}

// One portfolio made with 가진 종목 넣기 (홈 · 포트폴리오). st: pfState (or { ok: false } on stale or failed data, then
// no number), m: deckMoney (value and, when every holding has a 평균 단가, 원금 · 수익).
export function ImportedDeck({ deck, st, m, openStock, byT, onRemove, onMore, home = false }) {
  const rows = st && st.ok ? st.view.rows : null;
  const shades = rows ? holdingShades(rows.map((r) => r.w)) : [];
  const n = rows ? rows.length : (deck.imported || []).length;
  const items = m && m.ok ? [{ label: C.today.value, value: wonText(m.value) }] : [];
  return (
    <Card data-ui-v2={home ? "deck-strip" : undefined} data-deck-id={deck.id} data-kind="imported">
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
        <h3 style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0 })}>{shownName(deck.name)}</h3>
        {onMore && <button type="button" onClick={onMore} style={{ border: "none", background: "none", minHeight: 44, cursor: "pointer",
          ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { textDecoration: "underline", textUnderlineOffset: 3 }) }}>{C.today.more}</button>}
      </div>
      {items.length > 0 && <div style={{ marginTop: SPACE(2) }}><StatStrip items={items} /></div>}
      {m && m.ok && m.cost != null && (
        <div data-ui-v2="deck-money" style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>
          {fill(C.deck.money, { cost: wonText(m.cost), gain: (m.gain > 0 ? "+" : "") + wonText(m.gain), pct: signedPct(m.ret * 100) })}
        </div>
      )}
      {m && m.ok && m.cost != null && m.usdToday && <Note data-ui-v2="usd-today">{C.pfr.usdToday}</Note>}
      {m && m.absent && m.absent.length > 0 && <MissingNote absent={m.absent} deckId={deck.id} />}
      {st && st.ok && <RulesHead st={st} pxDate={st.pxDate} />}
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(4) })}>{fill(C.deck.mine, { n })}</div>
      {rows && rows.map((r, i) => {
        const a = r.t ? avgOf(deck, r.t) : null;
        const sub = r.frozen ? fill(C.app.asOf, { md: mdText(r.date) })
          : r.byAmount ? null : a ? fill(C.deck.holding, { qty: qtyText(r.qty), price: money(a.avg, a.ccy) }) : fill(C.plan.shares, { n: qtyText(r.qty) });
        const open = r.t && !r.absent && openStock && isCompany(byT && byT.get(r.t)) ? () => openStock(r.t) : undefined;
        return (
          <div key={r.key} data-pf-holding={r.key} data-weight={r.w != null ? Math.round(r.w * 1000) / 10 : undefined}>
            <ListRow title={r.nk} sub={sub} value={r.w != null ? `${pct(r.w)}%` : null} change={!r.absent && r.s ? (r.s.d1 ?? null) : null} onClick={open}
              lead={r.t ? <CoMark t={r.t} name={r.nk} size={SPACE(9)} /> : null} />
            {r.w != null && <WeightBar w={r.w} shade={shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1]} />}
            {r.absent && onRemove && (
              <div data-ui-v2="missing-remove" style={{ padding: `${SPACE(1)}px 0 ${SPACE(2)}px` }}>
                <Button kind="secondary" onClick={() => onRemove(r.t)} style={{ width: "auto", padding: `0 ${SPACE(4)}px` }}>{C.missing.remove}</Button>
              </div>
            )}
          </div>
        );
      })}
    </Card>
  );
}
