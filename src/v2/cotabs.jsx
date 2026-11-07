// ================= 회사 페이지의 탭과 자세히 (v19.1a Parts C · D; boards CoEarn · CoValue · CoValueMore · CoDiv · CoDisc) =================
// Each tab: one headline (a fixed variant of its tile's rule), one chart, two or three numbers, a link to 자세히.
// 실적: KR annual figures (corp.json, 억원) with the report year; revenue growth vs the industry only between peers whose
//   growth has the same basis (engine.growthBasis); 주가는 무엇으로 움직였나 (the old DecompCard maths, facts only).
//   US until v19.2: Yahoo's revenue growth, operating margin and ROE. The growth figure is the latest quarter against the
//   same quarter a year before and always carries that label (cofmt.usGrowthText; no label approved -> no number).
// 가치: PBR against the industry (strip), PBR · PER with industry medians, 지금 가격이 가정하는 것 (KR: the old DcfCard
//   reverse calculation; out of range -> its two messages), the 출렁임 line: the phrase, then (v19.1b data) the beta band
//   "코스피가 1% 움직일 때 평균 {lo}~{hi}% 움직였어요." with its note. No usable band: no card at all, as for a stock with no
//   beta (Jack, PR #68 B6; the 요약 tile says 자료가 없어요). Older files have no band: the phrase only, never a bare beta.
// 배당: KR dividend per share (report year) and three years; 100만원어치 rounded to 1,000원, before tax, with the basis it
//   was really computed on and the price date: KR 1,000,000 ÷ the close × the report's dividend per share (Jack,
//   2026-11-05); US 1,000,000 x Yahoo's yield until v19.2.
// 공시: KR only, disc.json (임원·주요주주 reports for 90 days, 국민연금 5% filings). A row with an exact receipt number is a
//   plain link to that filing on DART (new tab, Jack 2026-11-05: routes.dartFilingUrl); nothing is fetched from DART.
// 자세히: 가치 (every ratio with receipts that reproduce it, 업종 지도, the calculator) and 실적 (margins, 3-year table).
// Charts draw this company in navy and its peers in grey (apricot stays for the deck screens' data marks).
import React, { useMemo, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, TOPIC_ART, HOLDING_SHADES } from "../ui/tokens.js";
import { Icon, IconChip } from "../ui/icons.jsx";
import { StatusChip, Segmented, Amount, Button } from "../ui/components.jsx";
import { C, fill, nf, p1, mdText, priceText, todayKst, wonText } from "./format.js";
import { Page, Card, AppBar, ScreenTitle, DateLine, LoadFail, Footer, Note, tx, tap, useMode } from "./ui.jsx";
import { groupOf, earnKr, earnUs, valueTile, divKr, divUs, riskTile, growthVsInd, annualRows, yoy, decompose, pbrStrip, indMedian,
  roePbrMap, impliedGrowth, receipt, discFor, discDate, perMillionView, perMillionKr, payout, DCF, round, pastNiGrowth, dcfVs } from "./company.js";
import { growthBasis, num, exactData } from "./engine.js";
import { signedPct, eokText } from "./deckcalc.js";
import { withAssume, assumeOf } from "./store.js";
import { OLD_LINKS, dartFilingUrl } from "./routes.js";
import { usOf, priceMd, priceDate, timesText, pctText, yieldText, manWon, bigWon, usGrowthText, dcfHeadText, riskBandText, riskBandNote } from "./cofmt.js";
import { CoinFlow, PayoutRing } from "./coart.jsx";

const all = (...xs) => xs.every((x) => x != null && x !== "");
// A yearly rate inside "해마다 {g}%" (the template has the % sign): "22.1", "−3.2".
const rateText = (g) => (g < 0 ? "\u2212" : "") + p1(Math.abs(g));
const H = ({ children, ...rest }) => <h3 {...rest} style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.4 })}>{children}</h3>;
const Src = ({ children, ...rest }) => (children ? <div {...rest} style={tx(SIZE.xs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(2) })}>{children}</div> : null);
const yearText = (fy) => (fy ? fill(C.app.reportYear, { year: fy }) : null);
function CardHead({ icon, tone, title }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
      <IconChip name={icon} size={32} tone={tone} />
      <h3 style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.4 })}>{title}</h3>
    </div>
  );
}
function Stat({ label, value, sub, ...rest }) {
  return (
    <div {...rest} style={{ background: COLOR.page, borderRadius: RADIUS.sm, padding: `${SPACE(3)}px ${SPACE(3)}px`, minWidth: 0 }}>
      <div style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2)}>{label}</div>
      <div style={tx(SIZE.h3, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3 })}>{value}</div>
      {sub && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{sub}</div>}
    </div>
  );
}
const Stats = ({ children }) => <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: SPACE(2), marginTop: SPACE(3) }}>{children}</div>;
function MoreLink({ label, onClick, id }) {
  if (!label) return null;
  return (
    <button type="button" data-ui-v2={id} onClick={onClick}
      style={{ ...tap, width: "100%", marginTop: SPACE(3), minHeight: TOUCH + SPACE(2), border: "none", borderRadius: RADIUS.lg, background: COLOR.surface,
        padding: `0 ${SPACE(4)}px`, display: "flex", alignItems: "center", gap: SPACE(2), textAlign: "left" }}>
      <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { flex: 1 })}>{label}</span>
      <Icon name="chevronRight" size={18} tone="on" />
    </button>
  );
}

// Three annual bars (oldest first), the latest in navy. values may be negative (a loss bar hangs below the line).
function Bars({ rows, fmt, aria }) {
  const vals = rows.map((r) => r.v);
  const mx = Math.max(...vals.map((v) => Math.abs(v)), 1e-9);
  const neg = vals.some((v) => v < 0);
  const H0 = 96, base = neg ? H0 / 2 : H0;
  return (
    <div data-ui-v2="bars" aria-label={aria} role={aria ? "img" : undefined} style={{ display: "grid", gridTemplateColumns: `repeat(${rows.length}, 1fr)`, gap: SPACE(4), marginTop: SPACE(3) }}>
      {rows.map((r, i) => {
        const h = Math.max(2, (Math.abs(r.v) / mx) * (neg ? H0 / 2 - 4 : H0 - 4));
        const last = i === rows.length - 1;
        return (
          <div key={r.year} data-year={r.year} data-v={r.v} style={{ textAlign: "center", minWidth: 0 }}>
            <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" })}>{fmt(r.v)}</div>
            <div aria-hidden="true" style={{ position: "relative", height: H0, marginTop: SPACE(1) }}>
              <div style={{ position: "absolute", left: "28%", right: "28%", borderRadius: 4, background: last ? COLOR.ink : COLOR.border,
                ...(r.v >= 0 ? { bottom: H0 - base, height: h } : { top: base, height: h }) }} />
              <div style={{ position: "absolute", left: 0, right: 0, top: base, height: 1, background: COLOR.line }} />
            </div>
            <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{r.year}</div>
          </div>
        );
      })}
    </div>
  );
}

// ================= 실적 =================
function Decomp({ co }) {
  const D = C.co.decomp;
  if (!D.title) return null;
  const d = decompose(co);
  const head = d.head ? D.head[d.head] : null;
  // multipliers, as the old card: 3년 주가 = 이익 × 눈높이 (a true equation), each with its inputs (then → now)
  const box = (label, v, from, to, dark) => (
    <div style={{ background: dark ? COLOR.ink : COLOR.page, borderRadius: RADIUS.sm, padding: `${SPACE(3)}px ${SPACE(1)}px`, textAlign: "center", minWidth: 0 }}>
      <div style={tx(SIZE.xs, WEIGHT.semi, dark ? COLOR.surface : COLOR.text2)}>{label}</div>
      <div style={tx(SIZE.body, WEIGHT.heavy, dark ? COLOR.surface : COLOR.ink)}>{timesText(v, v >= 100 ? 0 : 2)}</div>
      {from && to && <div style={tx(SIZE.xxs, WEIGHT.regular, dark ? COLOR.surface : COLOR.text2, { lineHeight: 1.3 })}>{from}{" \u2192 "}{to}</div>}
    </div>
  );
  const op = (ch) => <span aria-hidden="true" style={tx(SIZE.body, WEIGHT.heavy, COLOR.text3, { textAlign: "center" })}>{ch}</span>;
  const won = (v) => (v != null ? fill(C.app.won, { n: nf(Math.round(v)) }) : null);
  const per = (v) => (v != null && v > 0 ? timesText(v, 1) : null);
  const q = co && typeof co.bq === "string" ? /^(\d{4})\.([1-4])Q$/.exec(co.bq) : null;
  const basis = !d.head ? null : q && D.basisQ && d.fyThen ? fill(D.basisQ, { y: q[1], q: q[2], fy: d.fyThen })
    : !q && D.basisY && d.fyThen ? fill(D.basisY, { fy: d.fyThen, fyNow: d.fyThen + 2 }) : null;
  const msg = d.why === "loss" ? D.none : d.why === "missing" ? C.co.tiles.na : null;
  if (!d.head && !msg) return null;
  return (
    <Card data-ui-v2="co-decomp" data-head={d.head || d.why}>
      <CardHead icon="chart-bar" tone="earn" title={D.title} />
      {d.head && all(head, D.price, D.eps, D.per) ? (
        <>
          <p style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3) })}>{head}</p>
          <div data-ui-v2="co-decomp-eq" data-price={d.priceRatio} data-eps={d.eF} data-per={d.mF}
            style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto 1fr", gap: SPACE(1), alignItems: "center", marginTop: SPACE(3) }}>
            {box(D.price, d.priceRatio, won(d.priceThen), won(d.priceNow), true)}{op("=")}{box(D.eps, d.eF, won(d.epsThen), won(d.epsNow))}
            {op("\u00d7")}{box(D.per, d.mF, per(d.perThen), per(d.perNow))}
          </div>
          {D.note && <Note>{D.note}</Note>}
          {basis && <Src>{basis}</Src>}
          {D.past && <Note style={{ marginTop: SPACE(1) }}>{D.past}</Note>}
        </>
      ) : !d.head ? <Note>{msg}</Note> : null}
    </Card>
  );
}

function GrowthVs({ load, s, co }) {
  const E = C.co.earn;
  const v = useMemo(() => growthVsInd(s, co, load.data.stocks, load.coByT), [load, s, co]);
  const label = v ? (v.basis === "y2" ? C.pick.receipt.growthKr : v.basis === "y1" ? C.pick.receipt.growthKr1y : null) : null;
  if (!v || !all(E.vs[v.rule], E.mine, E.ind, label)) return null;
  const mx = Math.max(Math.abs(v.mine), Math.abs(v.med), 1e-9);
  const bar = (x, dark) => (
    <div aria-hidden="true" style={{ height: SPACE(2), background: COLOR.line, borderRadius: 999, marginTop: SPACE(1), overflow: "hidden" }}>
      <div style={{ width: `${Math.max(2, (Math.max(0, x) / mx) * 100)}%`, height: "100%", background: dark ? COLOR.ink : COLOR.border, borderRadius: 999 }} />
    </div>
  );
  return (
    <Card data-ui-v2="co-growth" data-rule={v.rule} data-mine={v.mine} data-med={v.med} data-basis={v.basis}>
      <CardHead icon="trend-up" tone="earn" title={E.vs[v.rule]} />
      <div style={{ marginTop: SPACE(3) }}>
        <div style={{ display: "flex", justifyContent: "space-between", ...tx(SIZE.xs, WEIGHT.semi, COLOR.ink) }}><span>{E.mine}</span><span>{signedPct(v.mine)}</span></div>
        {bar(v.mine, true)}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.semi, COLOR.ink) }}>
          <span>{fill(E.ind, { ind: s.indName })}</span><span>{signedPct(v.med)}</span></div>
        {bar(v.med, false)}
      </div>
      <Src>{label}</Src>
    </Card>
  );
}

export function EarnTab({ load, s, onMore }) {
  const E = C.co.earn;
  const co = load.coByT.get(s.t) || null;
  const [metric, setMetric] = useState("op");
  if (usOf(s)) {
    const r = earnUs(s);
    const growth = usGrowthText(r.g);            // "최근 분기 매출, 1년 전보다 +16.4%": the number only with what it is
    // The verdict (매출이 늘고 있어요 …) reads one quarter against a year before: it shows only with that labelled number.
    const head = r.rule === "na" || !growth ? null : C.co.tiles.earnUs[r.rule];
    const md = priceMd(load, s);
    return (
      <div data-ui-v2="co-earn" data-cls="us" data-rule={r.rule}>
        <Card>
          {head && <H>{head}</H>}
          {growth && <p data-ui-v2="co-us-g3" data-g={r.g} style={tx(SIZE.body, WEIGHT.bold, COLOR.ink, { marginTop: SPACE(2) })}>{growth}</p>}
          <Stats>
            {num(s.opm) != null && E.opm && <Stat label={E.opm} value={pctText(s.opm)} />}
            {num(s.roe) != null && <Stat label="ROE" value={pctText(s.roe)} />}
          </Stats>
          <Src>{C.why.srcPriceUs && md ? fill(C.why.srcPriceUs, { md }) : null}</Src>
          {E.usLater && <Note>{E.usLater}</Note>}
        </Card>
      </div>
    );
  }
  const r = earnKr(co);
  const rows = annualRows(co);
  const opts = [{ value: "rev", label: C.pick.checks.rev }, { value: "op", label: C.plan.rules.opProfit }, { value: "ni", label: E.ni }].filter((o) => o.label);
  const m = opts.some((o) => o.value === metric) ? metric : "op";
  const series = rows ? rows.map((x) => ({ year: x.year, v: x[m] })) : null;
  const okSeries = series && series.every((x) => x.v != null) && series.every((x) => eokText(x.v));
  const last = okSeries ? series[2].v : null, prev = okSeries ? series[1].v : null;
  const ch = okSeries ? yoy(last, prev) : null;
  return (
    <div data-ui-v2="co-earn" data-cls="kr" data-rule={r.rule}>
      <Card>
        {r.rule !== "na" && E.head[r.rule] && <H>{E.head[r.rule]}</H>}
        {opts.length > 1 && <div style={{ marginTop: SPACE(3) }}><Segmented label={C.co.tabs.earn || C.plan.rules.opProfit} value={m} onChange={setMetric} options={opts} /></div>}
        {okSeries && (
          <>
            <div data-ui-v2="co-earn-big" data-metric={m} style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(3) }}>
              <span style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink)}><Amount text={eokText(last)} /></span>
              {ch != null && E.yoy && <span style={tx(SIZE.xs, WEIGHT.bold, ch < 0 ? COLOR.down : ch > 0 ? COLOR.up : COLOR.text2)}>{fill(E.yoy, { pct: signedPct(ch) })}</span>}
            </div>
            <Bars rows={series} fmt={(v) => eokText(v)} />
          </>
        )}
        <Src>{yearText(co && co.fy)}</Src>
      </Card>
      <GrowthVs load={load} s={s} co={co} />
      <Decomp co={co} />
      {rows && E.moreTitle && <MoreLink id="co-earn-more" label={E.more} onClick={onMore} />}
    </div>
  );
}

export function EarnMore({ load, s, pad, onBack, backLabel }) {
  const E = C.co.earn;
  const co = load.coByT.get(s.t) || null;
  const rows = annualRows(co);
  const cols = [[C.pick.checks.rev, "rev"], [C.plan.rules.opProfit, "op"], [E.ni, "ni"]].filter(([l]) => l);
  const margin = (x, k) => (num(x[k]) != null && num(x.rev) > 0 ? pctText((x[k] / x.rev) * 100) : "–");
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={backLabel} />
      <div data-ui-v2="co-earn-more" data-t={s.t}>
        {E.moreTitle && <ScreenTitle>{fill(E.moreTitle, { name: s.nk })}</ScreenTitle>}
        {rows && (
          <Card>
            <div role="table" style={{ display: "grid", gridTemplateColumns: `auto repeat(${rows.length}, minmax(0, 1fr))`, columnGap: SPACE(3), rowGap: SPACE(2) }}>
              <span role="columnheader" />
              {rows.map((x) => <span key={x.year} role="columnheader" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { textAlign: "right" })}>{x.year}</span>)}
              {cols.map(([label, k]) => (
                <React.Fragment key={k}>
                  <span role="rowheader" style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink)}>{label}</span>
                  {rows.map((x) => <span key={x.year} role="cell" style={tx(SIZE.xs, WEIGHT.semi, COLOR.ink, { textAlign: "right" })}>{num(x[k]) != null ? eokText(x[k]) : "–"}</span>)}
                </React.Fragment>
              ))}
              {[[E.opm, "op"], [E.nim, "ni"]].filter(([l]) => l).map(([label, k]) => (
                <React.Fragment key={"m" + k}>
                  <span role="rowheader" style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{label}</span>
                  {rows.map((x) => <span key={x.year} role="cell" style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { textAlign: "right" })}>{margin(x, k)}</span>)}
                </React.Fragment>
              ))}
            </div>
            {E.marginNote && <Note>{E.marginNote}</Note>}
            <Src>{yearText(co && co.fy)}</Src>
          </Card>
        )}
      </div>
      <Footer />
    </Page>
  );
}

// ================= 가치 =================
// v19.3e (board CoValue2): inside the "업종 {n}개 회사와 비교" card the strip is titled "업종 안 PBR 위치" (the count is in
// the card's title); without that title approved, the earlier "업종 {n}개 회사 중 PBR 위치".
function Strip({ s, group, inCard = false }) {
  const V = C.co.value;
  const st = useMemo(() => pbrStrip(s, group), [s, group]);
  if (!st || !all(V.strip, V.me, V.med, V.axisMax, V.stripAria)) return null;
  const X = (x) => `${(x * 100).toFixed(2)}%`;
  return (
    <div data-ui-v2="co-strip" data-n={st.n} data-med={st.med} style={{ marginTop: SPACE(4) }}>
      <div style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{inCard && V.where ? V.where : fill(V.strip, { n: st.n })}</div>
      <div role="img" aria-label={fill(V.stripAria, { ind: s.indName, n: st.n, x: nf(s.pbr, 2), y: nf(st.med, 2) })} style={{ position: "relative", height: SPACE(10), marginTop: SPACE(2) }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: SPACE(5), height: 1, background: COLOR.border }} />
        {st.dots.filter((d) => !d.mine).map((d) => (
          <span key={d.t} style={{ position: "absolute", left: `calc(${X(d.x)} - 4px)`, top: SPACE(5) - 4, width: 8, height: 8, borderRadius: 999, background: COLOR.text3, opacity: 0.45 }} />
        ))}
        <span style={{ position: "absolute", left: `calc(${X(st.medX)} - 1px)`, top: SPACE(2), width: 2, height: SPACE(6), background: COLOR.text2 }} />
        <span data-ui-v2="co-strip-me" style={{ position: "absolute", left: `calc(${X(st.mine)} - 7px)`, top: SPACE(5) - 7, width: 14, height: 14, borderRadius: 999, background: COLOR.ink, border: `2px solid ${COLOR.surface}` }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), ...tx(SIZE.xs, WEIGHT.regular, COLOR.text2) }}>
        <span>{timesText(0, 0)}</span><span>{fill(V.axisMax, { x: nf(round(st.cap, 1), 1) })}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE(3), marginTop: SPACE(1), ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>
        <span>{fill(V.me, { x: nf(s.pbr, 2) })}</span><span style={{ color: COLOR.text2 }}>{fill(V.med, { x: nf(st.med, 2) })}</span>
      </div>
    </div>
  );
}

// 지금 가격이 가정하는 것 (KR): headline, two bars, the reading note, and the inputs as a receipt (start profit with its
// report year, discount rate, 5년 뒤 성장률); out of range or a loss: the old card's message instead. The old card's
// defaults (fade on): parity tests.
// v19.3e 가치 fix (v19.3 Part I, DCF_NI): impliedGrowth grows 순이익, so the second bar is the company's own past 순이익
// growth (company.pastNiGrowth: the yearly average from ni[2] to ni[0], both above 0), labelled "지난 2년 실제 이익 ·
// 연평균 {x}% 늘었어요 / 줄었어요" (no minus sign), then "지금 주가가 가정하는 이익 증가는 지난 2년보다 낮아요. / 높아요. /
// 지난 2년과 비슷해요." (비슷 = within 3 percentage points, on the numbers shown) before the approved note. Never revenue.
// Without both profits above 0 the comparison is hidden (the bar and the sentence), not the card. At the model's edge
// only its message shows, as before.
// DCF_NI off is the card before v19.3e (the second bar was revenue growth with its basis label): kept only so the switch
// can go back, and because tests/test_v2_company.py pins the basis-label count in this file (see the v19.3e report).
export const DCF_NI = true;
const pctNum = (v) => nf(v, v % 1 ? 1 : 0);
export function dcfInputs(r) {
  const D = C.co.dcf;
  if (!D.inputs || r.fy == null || r.ni0 == null || !eokText(r.ni0)) return null;
  return fill(D.inputs, { fy: r.fy, ni: eokText(r.ni0), d: pctNum(r.disc), t: pctNum(r.term) });
}
// The past 순이익 line: "연평균 {x}% 늘었어요" / "줄었어요" with x shown without its sign (one decimal, as the first-year rate).
export function pastNiText(x) {
  const D = C.co.dcf;
  if (typeof x !== "number" || !Number.isFinite(x)) return null;
  const r = round(x, 1);
  const L = r < 0 ? D.pastDown : D.pastUp;
  return L ? fill(L, { x: p1(Math.abs(r)) }) : null;
}
function DcfBar({ icon, tone, label, value, x, mx, dark, ...rest }) {
  return (
    <div {...rest} style={{ display: "flex", alignItems: "center", gap: SPACE(3), marginTop: SPACE(3) }}>
      <IconChip name={icon} size={32} tone={tone} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), flexWrap: "wrap", ...tx(SIZE.xs, WEIGHT.semi, COLOR.ink) }}>
          <span>{label}</span><span style={{ whiteSpace: "nowrap", fontWeight: WEIGHT.heavy }}>{value}</span></div>
        <div aria-hidden="true" style={{ height: SPACE(2), background: COLOR.line, borderRadius: 999, marginTop: SPACE(1), overflow: "hidden" }}>
          <div style={{ width: `${Math.max(2, (Math.max(0, x) / mx) * 100)}%`, height: "100%", background: dark ? COLOR.ink : TOPIC_ART.earn.ink, borderRadius: 999 }} />
        </div>
      </div>
    </div>
  );
}
function Dcf({ load, s, co, a, onTry }) {
  const D = C.co.dcf;
  const r = impliedGrowth(s, co, a);
  if (!D.title || r.why === "us" || r.why === "notReady") return null;
  const msg = r.edge === "low" ? D.low : r.edge === "high" ? D.high : r.why === "loss" ? D.loss : null;
  const g = r.g != null ? round(r.g, 1) : null;
  const head = dcfHeadText(g);                 // 는다 (g >= 0) / 준다 (g < 0, no minus sign): Jack, 2026-11-05
  const inputs = dcfInputs(r);
  if (!DCF_NI) return <DcfRevenue s={s} co={co} a={a} r={r} g={g} msg={msg} head={head} inputs={inputs} onTry={onTry} />;
  if (g != null && !all(head, D.impliedNi, D.perYear, D.note, inputs)) return null;
  if (g == null && !msg) return null;
  const past = g != null ? pastNiGrowth(co) : null;
  const pastText = past ? pastNiText(past.x) : null;
  const vs = past && pastText && D.past ? dcfVs(g, past.x) : null;
  const vsText = vs && D.vs ? D.vs[vs] || null : null;
  const mx = Math.max(Math.abs(g || 0), vs ? Math.abs(past.x) : 0, 1e-9);
  return (
    <Card data-ui-v2="co-dcf" data-g={g ?? ""} data-edge={r.edge || r.why || ""} data-disc={a.disc} data-term={a.term}
      data-past={vs ? round(past.x, 1) : ""} data-vs={vs || ""}>
      <CardHead icon="scales" tone="value" title={D.title} />
      {g != null ? (
        <>
          <p data-ui-v2="co-dcf-head" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3) })}>{head}</p>
          <DcfBar data-ui-v2="co-dcf-implied" icon="scales" tone="on" label={D.impliedNi} value={fill(D.perYear, { g: rateText(g) })} x={g} mx={mx} dark />
          {vs && <DcfBar data-ui-v2="co-dcf-past" icon="trend-up" tone="earn" label={D.past} value={pastText} x={past.x} mx={mx} />}
          <Note data-ui-v2="co-dcf-note">{[vsText, fill(D.note, { t: pctNum(a.term) })].filter(Boolean).map((x, i) => <span key={i}>{i ? " " : ""}{x}</span>)}</Note>
          <div data-ui-v2="co-dcf-inputs" style={{ marginTop: SPACE(2), border: `1px dashed ${COLOR.border}`, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px`,
            ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{inputs}</div>
        </>
      ) : <Note>{msg}</Note>}
      {D.try && onTry && C.co.valueMore.title && C.co.calc.title && <div style={{ marginTop: SPACE(3) }}><Button kind="secondary" onClick={onTry}>{D.try}</Button></div>}
    </Card>
  );
}

// The card before v19.3e (DCF_NI off): the implied first-year rate against the company's revenue growth with its real
// basis. Not shown while DCF_NI is on (v19.3 Part I: never compare the implied 순이익 growth with revenue).
function DcfRevenue({ s, co, a, r, g, msg, head, inputs, onTry }) {
  const D = C.co.dcf;
  const gb = growthBasis(s, co);
  const glabel = gb === "y2" ? C.pick.receipt.growthKr : gb === "y1" ? C.pick.receipt.growthKr1y : null;
  const g3 = num(s.g3);
  if (g != null && !all(head, D.implied, D.perYear, D.note, inputs)) return null;
  if (g == null && !msg) return null;
  const mx = Math.max(Math.abs(g || 0), glabel && g3 != null ? Math.abs(g3) : 0, 1e-9);
  const bar = (x, dark) => (
    <div aria-hidden="true" style={{ height: SPACE(2), background: COLOR.line, borderRadius: 999, marginTop: SPACE(1), overflow: "hidden" }}>
      <div style={{ width: `${Math.max(2, (Math.max(0, x) / mx) * 100)}%`, height: "100%", background: dark ? COLOR.ink : COLOR.border, borderRadius: 999 }} />
    </div>
  );
  return (
    <Card data-ui-v2="co-dcf" data-g={g ?? ""} data-edge={r.edge || r.why || ""} data-disc={a.disc} data-term={a.term}>
      <CardHead icon="scales" tone="value" title={D.title} />
      {g != null ? (
        <>
          <p data-ui-v2="co-dcf-head" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3) })}>{head}</p>
          <div style={{ marginTop: SPACE(3) }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), ...tx(SIZE.xs, WEIGHT.semi, COLOR.ink) }}>
              <span>{D.implied}</span><span style={{ whiteSpace: "nowrap" }}>{fill(D.perYear, { g: rateText(g) })}</span></div>
            {bar(g, true)}
            {glabel && g3 != null && (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), marginTop: SPACE(3), ...tx(SIZE.xs, WEIGHT.semi, COLOR.ink) }}>
                  <span>{glabel}</span><span style={{ whiteSpace: "nowrap" }}>{signedPct(g3)}</span></div>
                {bar(g3, false)}
              </>
            )}
          </div>
          <Note>{fill(D.note, { t: pctNum(a.term) })}</Note>
          <div data-ui-v2="co-dcf-inputs" style={{ marginTop: SPACE(2), border: `1px dashed ${COLOR.border}`, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px`,
            ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{inputs}</div>
        </>
      ) : <Note>{msg}</Note>}
      {D.try && onTry && C.co.valueMore.title && C.co.calc.title && <div style={{ marginTop: SPACE(3) }}><Button kind="secondary" onClick={onTry}>{D.try}</Button></div>}
    </Card>
  );
}

// PER and PBR basis (KR): fetch_data fill_multiples uses the latest four quarters' net income and that quarter's equity
// when corp.json carries the TTM quarter (bq), else the 사업보고서 (fy).
export function valueBasis(co) {
  const V = C.co.value;
  const q = co && typeof co.bq === "string" ? /^(\d{4})\.([1-4])Q$/.exec(co.bq) : null;
  if (q) return V.basisQ ? fill(V.basisQ, { y: q[1], q: q[2] }) : null;
  return co && Number.isInteger(co.fy) && V.basisY ? fill(V.basisY, { fy: co.fy }) : null;
}

// One ratio against the industry median (board CoValue2): "PBR · 1.10배 · 업종 1.60배" and a bar each for 이 회사 (navy,
// the company page's colour for this company) and 업종 (grey). The first two lines keep the label, then the value, as the
// Stat they replace. A negative PER (a loss) has no bar.
function CompareRow({ id, label, mine, med, value, sub }) {
  const mx = Math.max(mine > 0 ? mine : 0, med > 0 ? med : 0, 1e-9);
  const bar = (name, v, dark) => (
    <div style={{ display: "grid", gridTemplateColumns: "48px 1fr", alignItems: "center", gap: SPACE(2), marginTop: SPACE(1) }}>
      <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{name}</span>
      <div aria-hidden="true" style={{ height: SPACE(2), background: COLOR.line, borderRadius: 999, overflow: "hidden" }}>
        {v > 0 && <div style={{ width: `${Math.max(2, (v / mx) * 100)}%`, height: "100%", background: dark ? COLOR.ink : HOLDING_SHADES[HOLDING_SHADES.length - 1], borderRadius: 999 }} />}
      </div>
    </div>
  );
  return (
    <div data-ui-v2={id} style={{ padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap" }}>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { flex: 1 })}>{label}</span>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{value}</span>
        {sub && <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{sub}</span>}
      </div>
      {bar(C.co.earn.mine, mine, true)}
      {med != null && bar(C.why.srcInd, med, false)}
    </div>
  );
}

export function ValueTab({ load, s, store, onMore }) {
  const V = C.co.value;
  const co = load.coByT.get(s.t) || null;
  const group = groupOf(load.data.stocks, s);
  const r = valueTile(s, group);
  const per = num(s.per);
  const perMed = useMemo(() => indMedian(group, (x) => num(x.per)), [group]);
  const head = r.rule === "na" ? null : V.head[r.rule];
  const sub = V.sub[r.rule] || null;
  const risk = riskTile(s);
  const bandLine = riskBandText(s, risk, true);
  const a = assumeOf(store.data, s.t) || { disc: DCF.disc, term: DCF.term };
  const st = useMemo(() => pbrStrip(s, group), [s, group]);
  // v19.3e (board CoValue2): with an industry to compare (a median from 5 or more companies), PBR and PER sit in one card
  // "업종 {n}개 회사와 비교" with a bar each for 이 회사 and 업종, then the 업종 안 PBR 위치 strip. Otherwise as before.
  const compare = r.med != null && st && V.compare && V.where && C.co.earn.mine && C.why.srcInd;
  const pbrSub = r.med != null && V.indMed ? fill(V.indMed, { x: nf(r.med, 2) }) : null;
  const perSub = perMed && V.indMed ? fill(V.indMed, { x: nf(round(perMed.med, 1), 1) }) : null;
  return (
    <div data-ui-v2="co-value" data-rule={r.rule}>
      <Card>
        {head && <H>{head}</H>}
        {head && sub && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{sub}</p>}
        {!compare && r.rule !== "na" && r.rule !== "few" && <Strip s={s} group={group} />}
        {!compare && (
          <Stats>
            {r.pbr != null && <Stat data-ui-v2="co-pbr" label="PBR" value={timesText(r.pbr, 2)} sub={pbrSub} />}
            {per != null && <Stat data-ui-v2="co-per" label="PER" value={timesText(per, 1)} sub={perSub} />}
          </Stats>
        )}
        {!usOf(s) && valueBasis(co) && <Src data-ui-v2="co-value-basis">{valueBasis(co)}</Src>}
        <DateLine date={priceDate(load, s)} fresh={load.fresh} />
      </Card>
      {compare && (
        <Card data-ui-v2="co-compare" data-n={st.n}>
          <CardHead icon="tag" tone="value" title={fill(V.compare, { n: st.n })} />
          <CompareRow id="co-pbr" label="PBR" mine={r.pbr} med={r.med} value={timesText(r.pbr, 2)} sub={pbrSub} />
          {per != null && <CompareRow id="co-per" label="PER" mine={per} med={perMed ? perMed.med : null} value={timesText(per, 1)} sub={perSub} />}
          <Strip s={s} group={group} inCard />
        </Card>
      )}
      {!usOf(s) && <Dcf load={load} s={s} co={co} a={a} onTry={onMore} />}
      {risk.rule !== "na" && C.co.risk[risk.rule] && (
        <Card data-ui-v2="co-risk" data-rule={risk.rule} data-beta={risk.beta} data-lo={risk.band ? risk.band.lo : ""} data-hi={risk.band ? risk.band.hi : ""}>
          <CardHead icon="umbrella" tone="risk" title={C.co.risk[risk.rule]} />
          {bandLine && <p data-ui-v2="co-risk-band" style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink, { marginTop: SPACE(2) })}>{bandLine}</p>}
          {bandLine && riskBandNote(risk) && <Note>{riskBandNote(risk)}</Note>}
        </Card>
      )}
      {C.co.valueMore.title && <MoreLink id="co-value-more" label={V.more} onClick={onMore} />}
    </div>
  );
}

function Scatter({ s, group }) {
  const M = C.co.map;
  const m = useMemo(() => roePbrMap(s, group), [s, group]);
  if (!m || !all(M.title, M.x, M.y, M.line, M.aria)) return null;
  const W = 320, Hh = 220, P = 24;
  const xs = m.pts.map((p) => p.x), ys = m.pts.map((p) => p.y);
  const x0 = Math.min(0, ...xs), x1 = Math.max(...xs, 1), y1 = Math.max(...ys) * 1.1;
  const sx = (x) => P + ((x - x0) / (x1 - x0 || 1)) * (W - 2 * P), sy = (y) => Hh - P - (y / (y1 || 1)) * (Hh - 2 * P);
  const lineY = (x) => Math.max(0, Math.min(y1, m.a + m.b * x));
  const [lx0, lx1] = m.range;                                         // the line only over the peers' ROE range
  const me = m.pts.find((p) => p.mine);
  return (
    <Card data-ui-v2="co-map" data-pos={m.pos} data-n={m.n}>
      <CardHead icon="chart-scatter" tone="value" title={M.title} />
      <svg viewBox={`0 0 ${W} ${Hh}`} width="100%" role="img" aria-label={fill(M.aria, { ind: s.indName, n: m.n, roe: p1(me.x), pbr: nf(me.y, 2) })}
        style={{ display: "block", marginTop: SPACE(3), maxWidth: 480, marginLeft: "auto", marginRight: "auto" }}>
        <line x1={P} y1={Hh - P} x2={W - P} y2={Hh - P} stroke={COLOR.border} />
        <line x1={P} y1={P} x2={P} y2={Hh - P} stroke={COLOR.border} />
        <line x1={sx(lx0)} y1={sy(lineY(lx0))} x2={sx(lx1)} y2={sy(lineY(lx1))} stroke={COLOR.text2} strokeDasharray="4 4" />
        {m.pts.filter((p) => !p.mine).map((p) => <circle key={p.t} cx={sx(p.x)} cy={sy(p.y)} r={4} fill={COLOR.text3} opacity={0.45} />)}
        <circle cx={sx(me.x)} cy={sy(me.y)} r={7} fill={COLOR.ink} stroke={COLOR.surface} strokeWidth={2} />
      </svg>
      <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>
        <div>{M.x}</div><div>{M.y}</div><div>{M.line}</div>
      </div>
      {M[m.pos] && <p style={tx(SIZE.xs, WEIGHT.semi, COLOR.ink, { marginTop: SPACE(2) })}>{M[m.pos]}</p>}
    </Card>
  );
}

function Calc({ load, s, store, setStoreData }) {
  const K = C.co.calc, D = C.co.dcf;
  const co = load.coByT.get(s.t) || null;
  const saved = assumeOf(store.data, s.t);
  const [a, setA] = useState(() => saved || { disc: DCF.disc, term: DCF.term });
  const [done, setDone] = useState(false);
  const r = impliedGrowth(s, co, a);
  if (usOf(s) || r.why === "notReady" || r.why === "us" || !all(K.title, K.intro, K.disc, K.term, K.result)) return null;
  const set = (k, v) => { setDone(false); setA((x) => ({ ...x, [k]: v })); };
  const slider = (k, label, [lo, hi]) => (
    <label style={{ display: "block", marginTop: SPACE(3) }}>
      <span style={{ display: "flex", justifyContent: "space-between", ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}><span>{label}</span><span>{pctText(a[k])}</span></span>
      <input type="range" min={lo} max={hi} step={DCF.step} value={a[k]} aria-label={label} onChange={(e) => set(k, Number(e.target.value))}
        style={{ width: "100%", minHeight: TOUCH, accentColor: COLOR.ink }} />
    </label>
  );
  const res = r.g != null ? fill(K.result, { g: rateText(round(r.g, 1)) }) : r.edge === "low" ? D.low : r.edge === "high" ? D.high : D.loss;
  const inputs = r.g != null ? dcfInputs(r) : null;
  const save = () => {
    const next = withAssume(store.data, s.t, a, todayKst(), Date.now());
    if (next) { setStoreData(next); setDone(true); } else console.warn("[v2] assumption not saved for " + s.t);
  };
  return (
    <Card data-ui-v2="co-calc" data-disc={a.disc} data-term={a.term} data-g={r.g != null ? round(r.g, 1) : ""}>
      <CardHead icon="calculator" tone="value" title={K.title} />
      <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{K.intro}</p>
      {slider("disc", K.disc, DCF.discRange)}
      {slider("term", K.term, DCF.termRange)}
      {res && <div data-ui-v2="co-calc-result" style={{ marginTop: SPACE(3), background: COLOR.page, borderRadius: RADIUS.sm, padding: SPACE(3), ...tx(SIZE.sm, WEIGHT.heavy, COLOR.ink) }}>{res}</div>}
      {inputs && <Src>{inputs}</Src>}
      {K.save && store.writable && (
        <div style={{ marginTop: SPACE(3) }}>
          <Button kind="secondary" onClick={save}>{done && K.saved ? K.saved : K.save}</Button>
        </div>
      )}
      {store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
    </Card>
  );
}

function RatioRow({ label, mean, value, med, calc, first }) {
  const { preview } = useMode();
  return (
    <div data-ui-v2="co-ratio" style={{ padding: `${SPACE(3)}px 0`, borderTop: first ? "none" : `1px solid ${COLOR.line}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(1) }}>
        <span style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{label}</span>
        {!preview && C.menu.glossary && (
          <a href={OLD_LINKS.glossary} aria-label={C.menu.glossary} style={{ ...tap, display: "inline-flex", alignItems: "center", justifyContent: "center", width: TOUCH - 12, height: TOUCH - 12 }}>
            <Icon name="info" size={16} tone="off" />
          </a>
        )}
        <span style={{ flex: 1 }} />
        <span style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{value}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: SPACE(2), ...tx(SIZE.xs, WEIGHT.regular, COLOR.text2) }}>
        <span>{mean}</span>{med && <span style={{ whiteSpace: "nowrap" }}>{med}</span>}
      </div>
      {calc && <div data-ui-v2="co-receipt" style={{ marginTop: SPACE(2), border: `1px dashed ${COLOR.border}`, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px`, ...tx(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{calc}</div>}
    </div>
  );
}

export function ValueMore({ load, s, store, setStoreData, pad, onBack, backLabel }) {
  const V = C.co.valueMore;
  const co = load.coByT.get(s.t) || null;
  const group = groupOf(load.data.stocks, s);
  const r = valueTile(s, group);
  const per = num(s.per);
  const perMed = indMedian(group, (x) => num(x.per));
  const corpOf = (x) => load.coByT.get(x.t) || null;
  const evMed = !usOf(s) ? indMedian(group, (x) => num((corpOf(x) || {}).evE)) : null;
  const pcfMed = !usOf(s) ? indMedian(group, (x) => num((corpOf(x) || {}).pcf)) : null;
  const med = (m, d = 1) => (m && V.med ? fill(V.med, { x: nf(round(m.med, d), d) }) : null);
  const kr = !usOf(s);
  const pbrR = kr ? receipt(s.price, s.bps, s.pbr, 2) : null;
  const perR = kr ? receipt(s.price, s.eps, s.per, 1) : null;
  const won = (v) => fill(C.app.won, { n: nf(Math.round(v)) });
  const rows = [
    r.pbr != null && V.mean.pbr ? { label: "PBR", mean: V.mean.pbr, value: timesText(r.pbr, 2), med: r.med != null && V.med ? fill(V.med, { x: nf(r.med, 2) }) : null,
      calc: pbrR && V.calcPbr ? fill(V.calcPbr, { p: won(pbrR.price), b: won(pbrR.per), x: nf(pbrR.value, 2) }) : null } : null,
    per != null && V.mean.per ? { label: "PER", mean: V.mean.per, value: timesText(per, 1), med: med(perMed),
      calc: perR && V.calcPer ? fill(V.calcPer, { p: won(perR.price), e: won(perR.per), x: nf(perR.value, 1) }) : null } : null,
    kr && co && num(co.evE) != null && V.mean.evE ? { label: "EV/EBITDA", mean: V.mean.evE, value: timesText(co.evE, 1), med: med(evMed) } : null,
    kr && co && num(co.pcf) != null && all(V.mean.pcf, V.pcf) ? { label: V.pcf, mean: V.mean.pcf, value: timesText(co.pcf, 1), med: med(pcfMed) } : null,
  ].filter(Boolean);
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={backLabel} />
      <div data-ui-v2="co-value-more" data-t={s.t}>
        {V.title && <ScreenTitle sub={V.intro || undefined}>{fill(V.title, { name: s.nk })}</ScreenTitle>}
        {rows.length > 0 && V.ratios && (
          <Card data-ui-v2="co-ratios">
            <CardHead icon="tag" tone="value" title={V.ratios} />
            <div style={{ marginTop: SPACE(2) }}>{rows.map((x, i) => <RatioRow key={x.label} {...x} first={i === 0} />)}</div>
            {!usOf(s) && valueBasis(co) && <Src>{valueBasis(co)}</Src>}
            <DateLine date={priceDate(load, s)} fresh={load.fresh} />
          </Card>
        )}
        <Scatter s={s} group={group} />
        <Calc load={load} s={s} store={store} setStoreData={setStoreData} />
      </div>
      <Footer />
    </Page>
  );
}

// ================= 배당 =================
// KR (Jack, 2026-11-05): the yield and the 100만원 line both use the latest 사업보고서's dividend per share over today's
// close (engine.js krYieldToday, company.js perMillionKr), so they always agree; a dps that fails the cross-check with the report's
// own yield shows neither. The per-share figure only when it passes (divKr dpsOk); the 3-year bars and the trend headline
// only with engine.js KR_DIV_TREND on (off until the history is split-adjusted). 배당성향 on one basis (payout).
// v19.1b data (engine.exactData): the yield is the pipeline's verified dyt, the per-share figure and the bars are on
// today's share basis (dps3a: a report year before a split divided by its exact factor), and the trend headline and bars
// show for every comparable stock (divSt same · adj · zero; nc · nd -> 배당을 줘요, no bars). The bars show the years the
// data has (Part O.3 of the v19.3 spec), at least two.
// US: Yahoo's yield only (no per-share dividend in the data until v19.2).
// The payout as won out of 100원 of profit: whole won, one decimal when the whole number would be 0 or 100 (0.3원 is not
// 0원, 99.6원 is not all of it). -> { x, y } as shown text.
export function payoutWon(pct) {
  const w = Math.round(pct);
  const d = w <= 0 || w >= 100 ? 1 : 0;
  const x = Math.round(pct * 10 ** d) / 10 ** d;
  const y = Math.round((100 - x) * 10 ** d) / 10 ** d;
  return { x: nf(x, d), y: nf(y, d) };
}
const warnedPayout = new Set();
export function DivTab({ load, s }) {
  const Dv = C.co.div;
  const co = load.coByT.get(s.t) || null;
  const us = usOf(s);
  const r = us ? divUs(s) : divKr(s, co);
  // na (the per-share figures disagree with the report's yield, or are missing): the tile's own phrase, never an empty card
  // KR payer (trend off): the tile's own phrase 배당을 줘요 (Jack, 2026-11-05); US keeps 배당을 주는 회사예요
  const head = r.rule === "na" ? C.co.tiles.na : r.rule === "noPrev" ? C.co.tiles.div.noPrev
    : r.rule === "streak" ? (Dv.head.streak ? fill(Dv.head.streak, { n: r.n }) : null)
    : r.rule === "pays" ? (us ? Dv.head.pays : C.co.tiles.div.pays) : Dv.head[r.rule];
  const md = priceMd(load, s);
  const fy = us ? null : r.fy;
  // KR (Jack, 2026-11-05): 1,000,000 ÷ today's close × the report's dividend per share (company.js perMillionKr); US: Yahoo's yield
  // (v19.1b data: perMillionKr can also read corp.json's dps3a, but a verified dyt only exists with data.json's own dps3a,
  // so this call needs no corp row; tests/test_v2_company.py pins this line.)
  const pm = r.rule === "none" ? null : us ? perMillionView(r.yieldPct) : perMillionKr(s);
  const basis = us ? Dv.basisUs : Dv.basisKr && fy ? fill(Dv.basisKr, { fy }) : null;
  const po = us ? null : payout(s, co);
  if (po && po.out != null && !warnedPayout.has(s.t)) {
    warnedPayout.add(s.t);
    console.warn(`[v2] payout ratio not shown for ${s.t}: ${po.out.toFixed(1)}% is outside 0-100% (${exactData() ? "cash dividends" : "dividend x shares"} / net income, ${po.fy})`);
  }
  const showDps = !us && r.dpsOk && r.dps != null && r.dps > 0;
  const years = showDps && r.d3 && fy ? [2, 1, 0].filter((i) => r.d3[i] != null).map((i) => ({ year: fy - i, v: r.d3[i] })) : [];
  const bars = years.length >= 2 ? years : null;
  const adjYears = bars && r.adjYears ? r.adjYears.filter((y) => bars.some((b) => b.year === y)) : [];   // earlier bars recalculated
  const line = pm ? (pm.under ? Dv.under1000 : Dv.perYear ? fill(Dv.perYear, { x: manWon(pm.won) }) : null) : null;
  // v19.3e (board CoDiv2): the amount as a coin flow "→ 1년 동안 → 약 {x}" (the screen reader hears the same approved line).
  // Below 1,000원 the sentence as before (never "약 0원").
  const flow = pm && !pm.under && Dv.year && C.app.about ? fill(C.app.about, { x: manWon(pm.won) }) : null;
  // 이익 중 얼마를 배당으로 줬나요?: the payout as "이익 100원 중 {x}원" and "나머지 {y}원은 회사에 남았어요." (whole won; one
  // decimal when the whole number would read 0 or 100).
  const ring = po && po.pct != null && all(Dv.payoutQ, Dv.payoutOf, Dv.payoutRest) ? payoutWon(po.pct) : null;
  return (
    <div data-ui-v2="co-div" data-cls={s.cls} data-rule={r.rule}>
      {(head || (showDps && Dv.dps) || us) && <Card data-ui-v2="co-div-head">
        {head && <H>{head}</H>}
        {showDps && Dv.dps && (
          <div data-ui-v2="co-dps" style={{ display: "flex", alignItems: "baseline", gap: SPACE(2), flexWrap: "wrap", marginTop: SPACE(3) }}>
            <span style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink)}><Amount text={fill(C.app.won, { n: nf(r.dps) })} /></span>
            <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{Dv.dps}</span>
          </div>
        )}
        {/* v19.1b data (Jack, PR #68 B3): the figure above was recalculated for a share count change; say what the report says */}
        {showDps && r.adjFrom != null && Dv.adjNote && <Note data-ui-v2="co-dps-adj">{fill(Dv.adjNote, { x: nf(r.adjFrom) })}</Note>}
        {bars && <Bars rows={bars} fmt={(v) => nf(v)} />}
        {/* v19.1b data (Jack, PR #68 2022/bars): an earlier bar was recalculated for a share count change */}
        {adjYears.length > 0 && Dv.barsAdjNote && <Note data-ui-v2="co-bars-adj">{fill(Dv.barsAdjNote, { years: adjYears.join("·") })}</Note>}
        {showDps && <Src>{yearText(fy)}</Src>}
        {us && Dv.usLater && <Note>{Dv.usLater}</Note>}
      </Card>}
      {pm && all(Dv.million, line, basis) && (
        <Card data-ui-v2="co-million" data-won={pm.won ?? ""} data-under={pm.under ? "1" : ""} data-raw={pm.raw}>
          <CardHead icon="coins" tone="div" title={Dv.million} />
          {flow ? <CoinFlow yearLabel={Dv.year} amount={flow} aria={line} />
            : <div style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(2) })}><Amount text={line} /></div>}
          <Note>{[basis, Dv.noPromise].filter(Boolean).map((x, i) => <span key={i}>{i ? " " : ""}{x}</span>)}</Note>
          <div style={{ marginTop: SPACE(2) }}><StatusChip tone="neutral">{C.plan.preTax}</StatusChip></div>
          <DateLine date={priceDate(load, s)} fresh={load.fresh} />
        </Card>
      )}
      {ring && (
        <Card data-ui-v2="co-payout" data-pct={po.pct}>
          <CardHead icon="chart-pie-slice" tone="div" title={Dv.payoutQ} />
          <div style={{ display: "flex", alignItems: "center", gap: SPACE(4), marginTop: SPACE(3) }}>
            <PayoutRing pct={po.pct} label={`${ring.x}%`} />
            <div style={{ minWidth: 0 }}>
              <p data-ui-v2="co-payout-of" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{fill(Dv.payoutOf, { x: ring.x })}</p>
              {ring.y !== "0" && <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{fill(Dv.payoutRest, { y: ring.y })}</p>}
              {yearText(po.fy) && <Src>{yearText(po.fy)}</Src>}
            </div>
          </div>
        </Card>
      )}
      {(r.yieldPct != null || (!ring && po && po.pct != null && all(Dv.payout, Dv.payoutSub))) && <Card data-ui-v2="co-div-stats">
        <Stats>
          {r.yieldPct != null && <Stat data-ui-v2="co-yield" data-y={r.yieldPct} label={C.pick.receipt.yield} value={yieldText(r.yieldPct)}
            sub={us ? Dv.yieldSubUs : fy ? fill(Dv.basisKr, { fy }) : null} />}
          {!ring && po && po.pct != null && all(Dv.payout, Dv.payoutSub) && <Stat data-ui-v2="co-payout" data-pct={po.pct} label={Dv.payout} value={pctText(po.pct)} sub={Dv.payoutSub} />}
        </Stats>
        {us && <Src>{C.why.srcPriceUs && md ? fill(C.why.srcPriceUs, { md }) : null}</Src>}
      </Card>}
    </div>
  );
}

// ================= 공시 (KR) =================
const DISC_ROWS = 10;                         // the newest reports listed (the counts cover all 90 days)
export function DiscTab({ load, s, disc }) {
  const D = C.co.disc;
  const v = useMemo(() => (disc && disc.status === "ok" ? discFor(disc.data, s) : null), [disc, s]);
  if (!disc || disc.status === "loading" || disc.status === "idle") return <div data-ui-v2="co-disc" data-state="loading" />;
  if (disc.status !== "ok" || !v) return <div data-ui-v2="co-disc" data-state="fail"><LoadFail picture={false} /></div>;
  const n = v.rows.length;
  const dd = discDate(disc.data);              // the newest filing's date, stale when the file stopped or today's list failed
  const side = (label, x, id) => (
    <Stat data-ui-v2={id} label={label} value={fill(D.count, { n: x.n })} sub={x.won != null && x.n > 0 && D.amt ? fill(D.amt, { x: bigWon(x.won) }) : null} />
  );
  return (
    <div data-ui-v2="co-disc" data-state="ok" data-n={n} data-stale={dd && dd.stale ? "1" : "0"}>
      <Card>
        <CardHead icon="identification-badge" tone="disc" title={n ? (D.head ? fill(D.head, { n }) : null) : D.none} />
        {n > 0 && all(D.buys, D.sells, D.count) && <Stats>{side(D.buys, v.buys, "co-buys")}{side(D.sells, v.sells, "co-sells")}</Stats>}
        {n > 0 && D.amtNote && <Note>{D.amtNote}</Note>}
        {n > 0 && D.why && <Note style={{ marginTop: SPACE(1) }}>{D.why}</Note>}
        {n > 0 && D.note && <Note style={{ marginTop: SPACE(1) }}>{D.note}</Note>}
        {n > 0 && all(D.buy, D.sell) && (
          <div data-ui-v2="co-disc-rows" style={{ marginTop: SPACE(3) }}>
            {v.rows.slice(0, DISC_ROWS).map((x) => {
              // The row itself is the link to that filing on DART (exact receipt number only; none -> a plain row of the same
              // height). The arrow-out mark says it opens outside the app (in-app moves use the caret).
              const href = dartFilingUrl(x.rc);
              const st = { display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH, padding: `${SPACE(2)}px 0`, borderTop: `1px solid ${COLOR.line}` };
              const body = (
                <>
                  <span style={tx(SIZE.xs, WEIGHT.semi, COLOR.text2, { width: SPACE(14), flexShrink: 0 })}>{mdText(x.date)}</span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>
                      {x.nm}{x.pos ? <span style={{ color: COLOR.text2, fontWeight: WEIGHT.regular }}>{" · "}{x.pos}</span> : null}</span>
                    <span style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { display: "block" })}>
                      {fill(C.plan.shares, { n: nf(Math.abs(x.q)) })}{x.won != null ? <>{" · "}{fill(C.app.about, { x: bigWon(x.won) })}</> : null}</span>
                  </span>
                  <StatusChip tone="neutral">{x.q > 0 ? D.buy : D.sell}</StatusChip>
                  {href && <Icon name="arrow-square-out" size={16} tone="on" />}
                </>
              );
              const key = x.rc || x.date + x.nm + x.q;
              return href
                ? <a key={key} data-ui-v2="co-disc-row" data-q={x.q} data-rc={x.rc} href={href} target="_blank" rel="noopener"
                    style={{ ...tap, ...st, textDecoration: "none", color: "inherit" }}>{body}</a>
                : <div key={key} data-ui-v2="co-disc-row" data-q={x.q} style={st}>{body}</div>;
            })}
          </div>
        )}
        {D.source && <Src>{D.source}</Src>}
        {dd && dd.date && <DateLine date={dd.date} fresh={{ stale: dd.stale, days: dd.days }} />}
      </Card>
      {v.nps && all(D.nps, D.npsNote) && (
        <Card data-ui-v2="co-nps" data-rt={v.nps.rt}>
          <CardHead icon="bank" tone="disc" title={fill(D.nps, { rt: p1(v.nps.rt) })} />
          {v.nps.chg != null && Math.round(v.nps.chg * 10) !== 0 && <p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { marginTop: SPACE(2) })}>{`${signedPct(v.nps.chg)}p`}</p>}
          <Note>{D.npsNote}</Note>
          <DateLine date={v.nps.date} />
        </Card>
      )}
    </div>
  );
}
