// ================= 뱁새 2.0 스타일 페이지 (v18.1 Part 2) =================
// styleguide.html 로 빌드돼요 (bash build-styleguide.sh). 앱에서 링크하지 않아요.
// 페이지 안내 글은 영어로만 써요. 한국어는 모두 examples.js (= 목업 문구 CSV) 에서 와요.
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { COLOR, FONT, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, NUM, CONTRAST_PAIRS, AVOID_PAIRS, contrast } from "../src/ui/tokens.js";
import { Icon, ICON_NAMES } from "../src/ui/icons.jsx";
import {
  StatusChip, HeroBand, Button, StatStrip, ListRow, Segmented, Stepper, MoneyInput, BottomActionBar,
  BottomSheet, Collapsible, BottomTabBar, DotStrip, WeightBar, RuleRow, fill,
} from "../src/ui/components.jsx";
import { EX } from "./examples.js";

const txt = (size, weight, color, extra) => ({ fontFamily: FONT, fontSize: size, fontWeight: weight, color, lineHeight: 1.5, ...extra });
const Card = ({ children, style }) => <div style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(5), ...style }}>{children}</div>;

// 한 묶음: 영어 이름 + 설명 + 상태별 예시
function Block({ id, name, note, children }) {
  return (
    <section id={id} data-block={id} style={{ marginTop: SPACE(8) }}>
      <h2 style={txt(SIZE.xs, WEIGHT.heavy, COLOR.text2, { margin: 0, textTransform: "uppercase", letterSpacing: "0.06em" })}>{name}</h2>
      {note && <p style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(1)}px 0 0` })}>{note}</p>}
      <div style={{ display: "flex", flexDirection: "column", gap: SPACE(3), marginTop: SPACE(3) }}>{children}</div>
    </section>
  );
}
const State = ({ label, children }) => (
  <div data-state-label={label}>
    <div style={txt(SIZE.xxs, WEIGHT.semi, COLOR.text2, { marginBottom: SPACE(1) })}>{label}</div>
    {children}
  </div>
);

// ── Part 1: 토큰 ──
const SWATCHES = [
  ["ink", "Main text, primary buttons"], ["text2", "Secondary text"], ["text3", "Small labels, on white only"],
  ["page", "Page background"], ["surface", "Sections"], ["line", "Hairlines"], ["border", "Control borders"],
  ["apricot", "Highlights and marks only"], ["apricotText", "Apricot text"], ["heroCalm", "Hero: nothing to do"],
  ["heroAlert", "Hero: something to check"], ["up", "Price up, on white only"], ["down", "Price down, on white only"],
  ["upOnPage", "Price up on page background"], ["ok", "Status: ok (on okBg)"], ["watch", "Status: watch (on watchBg)"],
  ["brokenBg", "Status: broken (white text)"], ["neutral", "Neutral chip (on neutralBg)"],
];

function Tokens() {
  return (
    <>
      <Block id="colours" name="Colours" note="Status colours never use red or blue: in Korea those mean price direction.">
        <Card style={{ padding: SPACE(3) }}>
          {SWATCHES.map(([k, use]) => (
            <div key={k} data-swatch={k} style={{ display: "flex", alignItems: "center", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
              <span style={{ width: 36, height: 36, borderRadius: RADIUS.sm, background: COLOR[k], border: `1px solid ${COLOR.border}`, flexShrink: 0 }} />
              <span style={{ flex: 1 }}>
                <span style={txt(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block" })}>{k}</span>
                <span style={txt(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{use}</span>
              </span>
              <code style={txt(SIZE.xs, WEIGHT.semi, COLOR.text2, NUM)}>{COLOR[k]}</code>
            </div>
          ))}
        </Card>
      </Block>

      <Block id="contrast" name="Contrast pairs" note="Every text and background pair used. Each must be at least 4.5 : 1.">
        <Card style={{ padding: SPACE(3) }}>
          {CONTRAST_PAIRS.map(([fg, bg]) => {
            const r = contrast(COLOR[fg], COLOR[bg]);
            return (
              <div key={fg + bg} data-pair={`${fg}/${bg}`} data-ratio={r.toFixed(2)} style={{ display: "flex", alignItems: "center", gap: SPACE(3), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
                <span style={{ background: COLOR[bg], color: COLOR[fg], borderRadius: SPACE(2), padding: `${SPACE(1)}px ${SPACE(3)}px`, border: `1px solid ${COLOR.border}`, ...txt(SIZE.sm, WEIGHT.bold, COLOR[fg], NUM) }}>{EX.typeNumber}</span>
                <span style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { flex: 1 })}>{fg} on {bg}</span>
                <span style={txt(SIZE.xs, WEIGHT.heavy, r >= 4.5 ? COLOR.ok : COLOR.ink, NUM)}>{r.toFixed(2)} : 1</span>
              </div>
            );
          })}
          <div style={txt(SIZE.xs, WEIGHT.bold, COLOR.ink, { marginTop: SPACE(3) })}>Not used (below 4.5 : 1)</div>
          {AVOID_PAIRS.map(([fg, bg]) => (
            <div key={fg + bg} data-avoid={`${fg}/${bg}`} style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, NUM)}>
              {fg} on {bg}: {contrast(COLOR[fg], COLOR[bg]).toFixed(2)} : 1
            </div>
          ))}
        </Card>
      </Block>

      <Block id="type" name="Type" note="Pretendard, self-hosted (SIL Open Font License 1.1). Numbers use tabular figures.">
        <Card>
          {Object.entries(SIZE).map(([k, px]) => (
            <div key={k} style={{ display: "flex", alignItems: "baseline", gap: SPACE(3), padding: `${SPACE(1)}px 0` }}>
              <code style={txt(SIZE.xxs, WEIGHT.semi, COLOR.text3, { width: 64, flexShrink: 0, ...NUM })}>{k} {px}</code>
              <span style={txt(px, px >= 18 ? WEIGHT.heavy : WEIGHT.regular, COLOR.ink, { lineHeight: 1.35, whiteSpace: "pre-line" })}>{px >= 18 ? EX.typeTitle : EX.typeBody}</span>
            </div>
          ))}
          <div style={{ display: "flex", gap: SPACE(4), marginTop: SPACE(3), flexWrap: "wrap" }}>
            {Object.entries(WEIGHT).map(([k, w]) => <span key={k} style={txt(SIZE.body, w, COLOR.ink)}>{k} {w}</span>)}
          </div>
          <div data-font-probe style={txt(SIZE.h2, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3), ...NUM })}>{EX.typeNumber} · 48,300 · 1,111</div>
        </Card>
      </Block>

      <Block id="space" name="Spacing, radius, touch" note={`4 px grid. Radius ${RADIUS.sm} / ${RADIUS.md} / ${RADIUS.lg}. Anything you tap is at least ${TOUCH} px.`}>
        <Card style={{ display: "flex", gap: SPACE(3), alignItems: "flex-end", flexWrap: "wrap" }}>
          {[1, 2, 3, 4, 5, 6, 8].map((n) => (
            <div key={n} style={{ textAlign: "center" }}>
              <div style={{ width: SPACE(n), height: SPACE(n), background: COLOR.apricot, borderRadius: 2, margin: "0 auto" }} />
              <code style={txt(SIZE.xxs, WEIGHT.semi, COLOR.text3, NUM)}>{SPACE(n)}</code>
            </div>
          ))}
          {Object.entries(RADIUS).map(([k, r]) => (
            <div key={k} style={{ textAlign: "center" }}>
              <div style={{ width: 48, height: 48, background: COLOR.page, border: `1px solid ${COLOR.border}`, borderRadius: r }} />
              <code style={txt(SIZE.xxs, WEIGHT.semi, COLOR.text3, NUM)}>r {r}</code>
            </div>
          ))}
          <div style={{ textAlign: "center" }}>
            <div style={{ width: TOUCH, height: TOUCH, border: `2px dashed ${COLOR.apricot}`, borderRadius: RADIUS.sm }} />
            <code style={txt(SIZE.xxs, WEIGHT.semi, COLOR.text3, NUM)}>tap {TOUCH}</code>
          </div>
        </Card>
      </Block>

      <Block id="icons" name="Icons" note="One stroke set: 24 px grid, 2 px stroke. No emoji anywhere.">
        <Card style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: SPACE(3) }}>
          {ICON_NAMES.map((n) => (
            <div key={n} data-icon={n} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: SPACE(1) }}>
              <Icon name={n} color={COLOR.ink} />
              <code style={txt(SIZE.xxs, WEIGHT.semi, COLOR.text3)}>{n}</code>
            </div>
          ))}
        </Card>
      </Block>
    </>
  );
}

// ── Part 2: 컴포넌트 ──
function Heroes() {
  const h = EX.hero;
  return (
    <Block id="hero" name="Hero band" note="Calm (nothing to do) or alert (something to check), with a mascot picture slot.">
      <State label="Calm, quiet day">
        <HeroBand tone="calm" eyebrow={h.quiet.eyebrow} title={h.quiet.title} body={h.quiet.body} image={h.quiet.image} imageAlt={h.quiet.imageAlt} />
      </State>
      <State label="Calm, one big move">
        <HeroBand tone="calm" eyebrow={h.bigMove.eyebrow} title={h.bigMove.title} body={h.bigMove.body} image={h.bigMove.image} imageAlt={h.bigMove.imageAlt}
          inset={<div style={{ display: "flex", alignItems: "center", gap: SPACE(2) }}>
            <div style={{ flex: 1 }}>
              <div style={txt(SIZE.xs, WEIGHT.bold, COLOR.ink)}>{h.bigMove.insetLine}</div>
              <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{h.bigMove.insetBody}</div>
            </div>
            <span style={txt(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "flex", alignItems: "center", minHeight: TOUCH })}>{h.bigMove.insetLink}<Icon name="chevronRight" size={16} color={COLOR.ink} /></span>
          </div>} />
      </State>
      <State label="Alert, a rule broke">
        <HeroBand tone="alert" eyebrow={h.alert.eyebrow} title={h.alert.title} body={h.alert.body} image={h.alert.image} imageAlt={h.alert.imageAlt}
          inset={<>
            <div style={txt(SIZE.xxs, WEIGHT.bold, COLOR.text3)}>{h.alert.insetLabel}</div>
            <div style={txt(SIZE.body, WEIGHT.heavy, COLOR.ink)}>{h.alert.insetRule}</div>
            <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, NUM)}>{h.alert.insetDetail}</div>
          </>}
          actions={<>
            <Button kind="primary">{h.alert.sold}</Button>
            <Button kind="secondary">{h.alert.wait}</Button>
            <Button kind="quiet">{h.alert.fix}</Button>
          </>} />
        <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{h.alert.rest}</div>
      </State>
      <State label="Calm, why it moved">
        <HeroBand tone="calm" eyebrow={h.why.eyebrow} title={h.why.title} body={h.why.body} image={h.why.image} imageAlt={h.why.imageAlt} />
      </State>
    </Block>
  );
}

function Stats() {
  const s = EX.stats;
  return (
    <Block id="stat-strip" name="Stat strip">
      <State label="Today screen">
        <Card>
          <div style={txt(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginBottom: SPACE(2) })}>{s.deckLine}</div>
          <StatStrip items={[{ label: s.now, value: s.nowValue }, { label: s.sinceBuy, value: "+8.0%", tone: "up" }, { label: s.today, value: "−0.4%", tone: "down" }]} note={EX.closeDate} />
        </Card>
      </State>
      <State label="My deck screen">
        <Card>
          <div style={txt(SIZE.h1, WEIGHT.heavy, COLOR.ink, NUM)}>{s.deckValue}</div>
          <div style={txt(SIZE.xs, WEIGHT.semi, COLOR.up, { ...NUM, marginBottom: SPACE(3) })}>{s.deckSub}</div>
          <div style={{ display: "flex", gap: SPACE(4), flexWrap: "wrap" }}>
            {[[s.deckMine, COLOR.ink], [s.kospi, COLOR.text3]].map(([t, c]) => (
              <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: SPACE(2), ...txt(SIZE.xs, WEIGHT.bold, COLOR.ink, NUM) }}>
                <span style={{ width: SPACE(3), height: SPACE(1), borderRadius: 2, background: c }} />{t}
              </span>
            ))}
          </div>
        </Card>
      </State>
      <State label="On the page background (darker up-red, upOnPage)">
        <div style={{ padding: `${SPACE(2)}px 0` }}>
          <StatStrip onPage items={[{ label: s.now, value: s.nowValue }, { label: s.sinceBuy, value: "+8.0%", tone: "up" }, { label: s.today, value: "−0.4%", tone: "down" }]} note={EX.closeDate} />
        </div>
      </State>
    </Block>
  );
}

function Rows() {
  const r = EX.rows;
  const chip = (k) => (k ? <StatusChip tone={k === "big" ? "neutral" : k}>{r.chips[k]}</StatusChip> : null);
  return (
    <Block id="list-row" name="List row" note="Name and today's move. A chip appears only when something is unusual.">
      <Card style={{ paddingTop: SPACE(2), paddingBottom: SPACE(2) }}>
        <div style={txt(SIZE.sm, WEIGHT.heavy, COLOR.ink, { padding: `${SPACE(2)}px 0` })}>{r.title}</div>
        {r.list.map((x) => <ListRow key={x.title} title={x.title} sub={x.sub} change={x.value} chip={chip(x.chip)} onClick={() => {}} />)}
      </Card>
    </Block>
  );
}

function Chips() {
  const c = EX.chips;
  return (
    <Block id="status-chip" name="Status chip">
      <Card style={{ display: "flex", gap: SPACE(2), flexWrap: "wrap" }}>
        <StatusChip tone="ok" icon="check">{c.ok}</StatusChip>
        <StatusChip tone="watch" icon="alert">{c.watch}</StatusChip>
        <StatusChip tone="broken" icon="close">{c.broken}</StatusChip>
        <StatusChip tone="neutral">{c.big}</StatusChip>
        <StatusChip tone="neutral">{c.sample}</StatusChip>
      </Card>
    </Block>
  );
}

function Segments() {
  const g = EX.segmented;
  const [strict, setStrict] = useState(1);
  const [split, setSplit] = useState(1);
  const [country, setCountry] = useState(1);
  const opts = (arr) => arr.map((label, i) => ({ value: i, label }));
  return (
    <Block id="segmented" name="Segmented control" note="Tap to try. The note under it follows the choice.">
      <Card style={{ display: "flex", flexDirection: "column", gap: SPACE(5) }}>
        <div>
          <div style={txt(SIZE.sm, WEIGHT.bold, COLOR.ink, { marginBottom: SPACE(2) })}>{g.strict.label}</div>
          <Segmented label={g.strict.label} options={opts(g.strict.options)} value={strict} onChange={setStrict} />
        </div>
        <div>
          <div style={txt(SIZE.sm, WEIGHT.bold, COLOR.ink, { marginBottom: SPACE(2) })}>{g.split.label}</div>
          <Segmented label={g.split.label} options={opts(g.split.options)} value={split} onChange={setSplit} />
          <div data-split-note style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{g.split.notes[split]}</div>
        </div>
        <div>
          <div style={txt(SIZE.sm, WEIGHT.bold, COLOR.ink, { marginBottom: SPACE(2) })}>{g.country.label}</div>
          <Segmented label={g.country.label} options={opts(g.country.options)} value={country} onChange={setCountry} />
          <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{g.country.note}</div>
        </div>
      </Card>
    </Block>
  );
}

function Steppers() {
  const s = EX.stepper;
  const [n, setN] = useState(6);
  const one = (v, set) => <Stepper value={v} min={5} max={30} onChange={set || (() => {})} label={s.label} format={s.format} decLabel={s.dec} incLabel={s.inc} />;
  return (
    <Block id="stepper" name="Stepper" note="Middle value (tap to try), at the minimum, at the maximum.">
      <Card style={{ display: "flex", flexDirection: "column", gap: SPACE(4) }}>
        <div data-stepper-live>{one(n, setN)}<div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{s.note}</div></div>
        <State label="At minimum">{one(5)}</State>
        <State label="At maximum">{one(30)}</State>
      </Card>
    </Block>
  );
}

function moneyWarning(v) {
  if (!v) return EX.money.empty;
  if (v > 100000) return EX.money.tooBig;   // 10억원 = 100,000만원
  return null;
}
function Money() {
  const m = EX.money;
  const [v, setV] = useState(1000);
  const quick = [{ label: m.quick[0], add: 10 }, { label: m.quick[1], add: 100 }, { label: m.quick[2], add: 1000 }];
  const props = { label: m.label, unit: m.unit, placeholder: m.placeholder, quick, clearLabel: m.clear };
  return (
    <Block id="money-input" name="Money input" note={`Amounts in ${EX.money.unit}. Quick-add buttons, and a warning line when needed.`}>
      <State label="Normal (tap to try)">
        <div data-money-live><Card><MoneyInput {...props} value={v} onChange={setV} warning={moneyWarning(v)} /></Card></div>
      </State>
      <State label="Empty">
        <Card><MoneyInput {...props} value={0} onChange={() => {}} warning={moneyWarning(0)} /></Card>
      </State>
      <State label="Very large">
        <Card><MoneyInput {...props} value={120000} onChange={() => {}} warning={moneyWarning(120000)} /></Card>
      </State>
      <State label="Adding money to my deck, too little">
        <Card>
          <MoneyInput {...props} label={m.addLabel} value={5} onChange={() => {}} warning={m.tooSmall} />
          <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{m.addHint}</div>
        </Card>
      </State>
    </Block>
  );
}

function ActionBars() {
  const a = EX.actionBar;
  const sum = (label, count) => <span><span>{label} </span><b style={txt(SIZE.sm, WEIGHT.heavy, COLOR.ink, NUM)}>{count}</b></span>;
  return (
    <Block id="bottom-action-bar" name="Bottom action bar" note="Fixed to the bottom of the screen in the app. Shown in place here.">
      <State label="Candidates"><BottomActionBar summary={sum(a.match.summary, fill(a.match.count, { count: 38 }))} action={fill(a.match.action, { shortN: 12 })} /></State>
      <State label="Picked"><BottomActionBar summary={sum(a.picked.summary, fill(a.picked.count, { count: 6 }))} action={a.picked.action} /></State>
      <State label="Next step"><BottomActionBar summary={null} action={a.next.action} /></State>
      <State label="Bought"><BottomActionBar summary={fill(a.left.summary, { leftText: `12${EX.money.unit}` })} action={a.left.action} /></State>
    </Block>
  );
}

function Sheets() {
  const s = EX.sheet;
  const [open, setOpen] = useState(false);
  const field = (label, value) => (
    <label style={txt(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", marginTop: SPACE(3) })}>{label}
      <div style={{ marginTop: SPACE(1), border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, minHeight: TOUCH, display: "flex", alignItems: "center", padding: `0 ${SPACE(3)}px`, ...txt(SIZE.body, WEIGHT.semi, COLOR.ink, NUM) }}>{value}</div>
    </label>
  );
  const form = (<>
    <p style={txt(SIZE.sm, WEIGHT.regular, COLOR.text2, { margin: 0 })}>{s.body}</p>
    {field(s.date, "2026-10-31")}
    {field(s.qty, "36")}
    <div style={{ marginTop: SPACE(4) }}><Button>{s.save}</Button></div>
  </>);
  return (
    <Block id="bottom-sheet" name="Bottom sheet" note="Slides up from the bottom. The button opens the real one; close it with the X, a tap outside, or Esc.">
      <State label="Record form"><BottomSheet inline open title={s.title} closeLabel={EX.close} onClose={() => {}}>{form}</BottomSheet></State>
      <State label="Done">
        <BottomSheet inline open title={s.doneTitle} closeLabel={EX.close} onClose={() => {}}>
          <div style={{ display: "flex", gap: SPACE(3), alignItems: "center" }}>
            <img src={s.doneImage} alt={s.doneImageAlt} width={64} height={64} />
            <p style={txt(SIZE.sm, WEIGHT.regular, COLOR.text2, { margin: 0 })}>{s.doneBody}</p>
          </div>
          <div style={{ marginTop: SPACE(4) }}><Button kind="secondary">{s.doneLink}</Button></div>
        </BottomSheet>
      </State>
      <Button kind="secondary" onClick={() => setOpen(true)} style={{ fontFamily: FONT }}><span data-open-sheet>Open the real sheet</span></Button>
      <BottomSheet open={open} title={s.title} closeLabel={EX.close} onClose={() => setOpen(false)}>{form}</BottomSheet>
    </Block>
  );
}

function Collapsibles() {
  const c = EX.collapsible;
  return (
    <Block id="collapsible" name="Collapsible section" note="Closed and open. Tap a heading to toggle.">
      <Card style={{ paddingTop: 0, paddingBottom: 0 }}>
        <Collapsible title={c.stage.title}>
          <p style={txt(SIZE.sm, WEIGHT.regular, COLOR.text2, { margin: 0 })}>{c.stage.body}</p>
        </Collapsible>
        <Collapsible title={c.ruleHelp.title} defaultOpen>
          <p style={txt(SIZE.sm, WEIGHT.regular, COLOR.text2, { margin: 0 })}>{c.ruleHelp.body}</p>
          <div style={{ display: "flex", gap: SPACE(2), marginTop: SPACE(2), flexWrap: "wrap" }}>
            {c.ruleHelp.choices.map((x) => <StatusChip key={x} tone="neutral">{x}</StatusChip>)}
          </div>
        </Collapsible>
        <Collapsible title={c.receipts.title} defaultOpen>
          {c.receipts.items.map(([k, v]) => (
            <div key={k} style={{ display: "flex", gap: SPACE(3), padding: `${SPACE(1)}px 0` }}>
              <span style={txt(SIZE.xs, WEIGHT.bold, COLOR.text3, { width: 72, flexShrink: 0 })}>{k}</span>
              <span style={txt(SIZE.xs, WEIGHT.regular, COLOR.ink, NUM)}>{v}</span>
            </div>
          ))}
        </Collapsible>
      </Card>
    </Block>
  );
}

function Tabs() {
  const t = EX.tabs;
  const [v, setV] = useState("today");
  const tabs = [
    { id: "today", label: t.today, icon: "today" }, { id: "deck", label: t.deck, icon: "deck" },
    { id: "build", label: t.build, icon: "build" }, { id: "search", label: t.search, icon: "search", disabled: true, aria: t.searchAria },
  ];
  return (
    <Block id="bottom-tab-bar" name="Bottom tab bar" note={`Fixed to the bottom in the app. ${EX.tabs.search} is greyed out because the mockup has no search screen yet.`}>
      <State label="Tap to try"><BottomTabBar tabs={tabs} value={v} onChange={setV} label={t.label} /></State>
      <State label="My deck selected"><BottomTabBar tabs={tabs} value="deck" label={t.label} /></State>
    </Block>
  );
}

function Dots() {
  const d = EX.dots;
  const items = (arr) => arr.map((pct, i) => ({ id: i === 0 ? "mine" : `p${i}`, pct }));
  return (
    <Block id="dot-strip" name="Dot-strip chart" note="Today's move for every stock in the same industry. Mine is the apricot dot; the dark line is the industry average.">
      <State label="Whole industry fell">
        <Card>
          <div style={txt(SIZE.sm, WEIGHT.heavy, COLOR.ink)}>{d.title}</div>
          <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginBottom: SPACE(3) })}>{d.sub}</div>
          <DotStrip items={items(d.sector)} mine="mine" avgLabel={d.avgLabel} mineLabel={d.mineLabel} aria={d.aria} />
        </Card>
      </State>
      <State label="Only mine fell">
        <Card>
          <div style={txt(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginBottom: SPACE(3) })}>{d.aloneTitle}</div>
          <DotStrip items={items(d.alone)} mine="mine" avgLabel={d.avgLabel} mineLabel={d.mineLabel} aria={d.aloneTitle} />
        </Card>
      </State>
    </Block>
  );
}

function Weights() {
  const w = EX.weight;
  return (
    <Block id="weight-bar" name="Weight bar" note="Bar is the current weight; the apricot mark is the target. Outside 0.75 to 1.25 times the target turns amber.">
      <Card>
        {w.rows.map((r) => (
          <div key={r.title} style={{ padding: `${SPACE(2)}px 0` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: SPACE(2) }}>
              <span style={txt(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{r.title}</span>
              <span style={txt(SIZE.xs, WEIGHT.bold, COLOR.text2, NUM)}>{r.current}%</span>
            </div>
            <WeightBar current={r.current} target={w.target} max={30} label={w.label} />
          </div>
        ))}
        <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{w.note}</div>
      </Card>
    </Block>
  );
}

function Rules() {
  const r = EX.rules, c = EX.chips;
  return (
    <Block id="rule-row" name="Rule row" note="Check icon, the number now, and the line that triggers the rule.">
      <State label="All fine">
        <Card style={{ paddingTop: SPACE(2), paddingBottom: SPACE(2) }}>
          <div style={txt(SIZE.sm, WEIGHT.heavy, COLOR.ink, { paddingTop: SPACE(2) })}>{r.title}</div>
          <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{r.sub}</div>
          {r.ok.map((x) => <RuleRow key={x.name} name={x.name} now={x.now} limit={x.limit} state="ok" stateLabel={c.ok} />)}
        </Card>
      </State>
      <State label="Watch and broken">
        <Card style={{ paddingTop: 0, paddingBottom: 0 }}>
          <RuleRow name={r.watch.name} now={fill(r.watch.now, { pct: r.watch.pct })} limit={r.watch.limit} state="watch" stateLabel={c.watch} />
          <RuleRow name={r.broken.name} now={r.broken.now} limit={r.broken.limit} state="broken" stateLabel={c.broken} />
        </Card>
      </State>
    </Block>
  );
}

function Page() {
  return (
    <div style={{ maxWidth: 520, margin: "0 auto", padding: `${SPACE(5)}px ${SPACE(4)}px ${SPACE(12)}px` }}>
      <header style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <img src="icon-192.png" alt="" width={40} height={40} style={{ borderRadius: RADIUS.sm }} />
        <div style={{ flex: 1 }}>
          <h1 style={txt(SIZE.h2, WEIGHT.heavy, COLOR.ink, { margin: 0 })}>{EX.brand} 2.0 · Style page</h1>
          <div style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2)}>v18.1 design system. Not linked from the app.</div>
        </div>
        <span data-sample-label><StatusChip tone="neutral">{EX.sample}</StatusChip></span>
      </header>
      <p style={txt(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(3) })}>
        Every Korean line here is copied from the approved mockup (docs/design/mockup-copy.csv). Companies and numbers are made up.
      </p>
      <Tokens />
      <Heroes /><Stats /><Rows /><Chips /><Segments /><Steppers /><Money /><ActionBars />
      <Sheets /><Collapsibles /><Tabs /><Dots /><Weights /><Rules />
      <footer style={{ marginTop: SPACE(10), ...txt(SIZE.xxs, WEIGHT.regular, COLOR.text2) }}>
        <div>{EX.sampleNote}</div>
        <div style={{ marginTop: SPACE(1) }}>{EX.footer}</div>
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<Page />);
