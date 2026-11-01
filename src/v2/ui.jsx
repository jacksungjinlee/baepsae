// Shared pieces for the 2.0 screens, built on the v18.1 tokens and components. No Korean here: text comes in props
// or from src/copy/v2.js.
import React, { createContext, useContext } from "react";
import { COLOR, FONT, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { StatusChip, Button } from "../ui/components.jsx";
import { C, fill, mdText } from "./format.js";

export const tx = (size, weight, color, extra) => ({ fontFamily: FONT, fontSize: size, fontWeight: weight, color, lineHeight: 1.5,
  letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums", margin: 0, ...extra });
const tap = { WebkitTapHighlightColor: "transparent", cursor: "pointer", fontFamily: FONT, padding: 0 };
export const TAB_H = TOUCH + SPACE(3);

// The current app. 찾기 and the header link "예전 뱁새 보기" open it (Part F: the main address shows 2.0).
export const OLD_APP = "./baepsae.html";

// Which page this is: the live app or the preview with fictional example data (app-preview.html).
export const ModeContext = createContext({ preview: false });
export const useMode = () => useContext(ModeContext);

// "예시 데이터" label: on every screen of the preview page, right in the app bar.
export function SampleLabel() {
  return <span data-ui-v2="sample-label"><StatusChip tone="neutral">{C.app.sample}</StatusChip></span>;
}

export function Page({ children, pad = SPACE(6) }) {
  return <main style={{ maxWidth: 520, margin: "0 auto", padding: `${SPACE(4)}px ${SPACE(4)}px ${pad}px` }}>{children}</main>;
}

export function Card({ children, style, ...rest }) {
  return <section {...rest} style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(5), marginTop: SPACE(3), ...style }}>{children}</section>;
}

// App bar: preview name on every screen, optional back button.
export function AppBar({ onBack, backLabel, right }) {
  const { preview } = useMode();
  return (
    <header data-ui-v2="app-bar" style={{ display: "flex", alignItems: "center", gap: SPACE(2), minHeight: TOUCH,
      ...(preview ? { position: "sticky", top: 0, zIndex: 40, background: COLOR.page, margin: `0 -${SPACE(4)}px`, padding: `0 ${SPACE(4)}px` } : {}) }}>
      {onBack ? (
        <button type="button" aria-label={backLabel} onClick={onBack}
          style={{ ...tap, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center", marginLeft: -SPACE(3) }}>
          <Icon name="back" color={COLOR.ink} />
        </button>
      ) : <img src="icon-192.png" alt="" width={28} height={28} style={{ borderRadius: RADIUS.sm - SPACE(1) }} />}
      <h1 style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { flex: 1, minWidth: 0 })}>{C.app.title}</h1>
      {preview && <SampleLabel />}
      {!preview && (
        <a data-ui-v2="old-app-link" href={OLD_APP}
          style={{ ...tx(SIZE.xxs, WEIGHT.semi, COLOR.text2, { whiteSpace: "nowrap" }), minHeight: TOUCH, display: "inline-flex", alignItems: "center",
            padding: `0 ${SPACE(1)}px`, textDecoration: "underline", textUnderlineOffset: 3, WebkitTapHighlightColor: "transparent" }}>{C.app.oldApp}</a>
      )}
      {right}
    </header>
  );
}

export function ScreenTitle({ children, sub }) {
  return (
    <div style={{ marginTop: SPACE(2) }}>
      <h2 style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3, whiteSpace: "pre-line" })}>{children}</h2>
      {sub && <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{sub}</p>}
    </div>
  );
}

// "10월 30일 기준" — the content date. Publication stopped for more than 4 days: "· N일째 갱신이 멈췄어요" in warning colour.
export function DateLine({ date, fresh }) {
  const md = mdText(date);
  if (!md) return null;
  const stale = !!(fresh && fresh.stale);
  return (
    <div data-ui-v2="date-line" data-stale={stale ? "1" : "0"} style={tx(SIZE.xs, stale ? WEIGHT.bold : WEIGHT.regular, stale ? COLOR.watch : COLOR.text2, { marginTop: SPACE(1) })}>
      <span>{fill(C.app.asOf, { md })}</span>
      {stale && <span>{" · "}</span>}
      {stale && <span>{fill(C.app.stale, { n: fresh.days })}</span>}
    </div>
  );
}

export function LoadFail() {
  return (
    <div data-ui-v2="load-fail" role="alert" style={{ textAlign: "center", padding: `${SPACE(10)}px ${SPACE(4)}px` }}>
      <img src="baepi-2.png" alt={C.app.loadFailAlt} width={80} height={80} style={{ objectFit: "contain" }} />
      <p style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(3) })}>{C.app.loadFail}</p>
    </div>
  );
}

export function PendingChip() {
  return <span data-ui-v2="pending"><StatusChip tone="neutral">{C.app.pending}</StatusChip></span>;
}

export function Footer() {
  return (
    <footer data-ui-v2="footer" style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(8) })}>
      <div>{C.app.footer}</div>
      <div style={{ marginTop: SPACE(1) }}>{C.app.credit}</div>
    </footer>
  );
}

export function Note({ children, tone, style, ...rest }) {
  const t = tone === "watch" ? { color: COLOR.watch, bg: COLOR.watchBg } : null;
  return (
    <div {...rest} role={tone ? "status" : undefined} style={tx(SIZE.xs, t ? WEIGHT.semi : WEIGHT.regular, t ? t.color : COLOR.text2, {
      marginTop: SPACE(2), ...(t ? { background: t.bg, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px` } : {}), ...style })}>{children}</div>
  );
}

export function Label({ children, style }) {
  return <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink, { marginBottom: SPACE(2), ...style })}>{children}</div>;
}

// On/off switch row (the v18.1 set has no switch): label, second line, count on the right.
export function Toggle({ on, onChange, label, sub, side, disabled, chip }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => !disabled && onChange(!on)}
      style={{ ...tap, width: "100%", minHeight: TOUCH + SPACE(3), border: "none", borderBottom: `1px solid ${COLOR.line}`, background: "none",
        display: "flex", alignItems: "center", gap: SPACE(3), textAlign: "left", padding: `${SPACE(2)}px 0`, cursor: disabled ? "default" : "pointer" }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={tx(SIZE.sm, WEIGHT.bold, disabled ? COLOR.text2 : COLOR.ink, { display: "block" })}>{label}</span>
        <span style={{ display: "flex", flexWrap: "wrap", gap: SPACE(2), alignItems: "center" }}>
          {sub && <span style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{sub}</span>}
          {chip}
        </span>
      </span>
      {side != null && <span style={tx(SIZE.xs, WEIGHT.bold, COLOR.text2)}>{side}</span>}
      <span aria-hidden="true" style={{ width: SPACE(11), height: SPACE(6) + 2, borderRadius: 999, background: on ? COLOR.ink : COLOR.border, position: "relative", flexShrink: 0, opacity: disabled ? 0.5 : 1 }}>
        <span style={{ position: "absolute", top: 3, left: on ? SPACE(5) + 3 : 3, width: SPACE(5), height: SPACE(5), borderRadius: 999, background: COLOR.surface, transition: "left .15s" }} />
      </span>
    </button>
  );
}

// Fixed bar above the bottom edge: summary on the left, one main button.
export function ActionBar({ summary, action, onAction, disabled }) {
  return (
    <div data-ui-v2="action-bar" style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 50, background: COLOR.surface, borderTop: `1px solid ${COLOR.line}`,
      padding: `${SPACE(3)}px ${SPACE(4)}px calc(${SPACE(3)}px + env(safe-area-inset-bottom))` }}>
      <div style={{ maxWidth: 520, margin: "0 auto", display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <div style={{ flex: 1, minWidth: 0, ...tx(SIZE.xs, WEIGHT.semi, COLOR.text2) }}>{summary}</div>
        <div style={{ flexShrink: 0, minWidth: SPACE(30), maxWidth: "60%" }}>
          <Button onClick={onAction} disabled={disabled} style={{ padding: `0 ${SPACE(3)}px` }}>{action}</Button>
        </div>
      </div>
    </div>
  );
}

// One rule line in 내 투자 규칙. Nothing is evaluated daily yet (Part C), so no rule gets a green check: a rule we can
// check shows the rule icon with its number and report; a rule we cannot check yet shows a dot and 준비 중.
export function RuleLine({ name, now, limit, source, pending, note }) {
  const ic = pending ? { name: "dot", fg: COLOR.neutral, bg: COLOR.neutralBg } : { name: "rule", fg: COLOR.neutral, bg: COLOR.neutralBg };
  return (
    <div data-ui-v2="rule-line" data-check={pending ? "pending" : "checked"} data-icon={ic.name} style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start", padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <span style={{ width: SPACE(7), height: SPACE(7), borderRadius: 999, background: ic.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={ic.name} size={16} color={ic.fg} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{name}</div>
        {pending ? <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{C.app.notChecked}</div>
          : <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{[now, limit].filter(Boolean).map((x, i) => <span key={i}>{i ? " · " : ""}{x}</span>)}</div>}
        {note && <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.watch)}>{note}</div>}
        {source && <div style={tx(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{source}</div>}
      </div>
      {pending && <PendingChip />}
    </div>
  );
}

// Radio choices that wrap onto more rows on narrow screens (the 5 Korea:US options would wrap inside a segmented bar).
export function ChoiceGrid({ options, value, onChange, label, min = 96 }) {
  return (
    <div data-ui-v2="choice-grid" role="radiogroup" aria-label={label}
      style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))`, gap: SPACE(2) }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
            style={{ ...tap, minHeight: TOUCH, borderRadius: RADIUS.sm, padding: `0 ${SPACE(2)}px`, whiteSpace: "nowrap",
              border: on ? `2px solid ${COLOR.ink}` : `1px solid ${COLOR.border}`, background: on ? COLOR.surface : COLOR.page,
              ...tx(SIZE.xs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text2) }}>{o.label}</button>
        );
      })}
    </div>
  );
}

export function TextInput({ label, value, onChange, inputMode, placeholder, type = "text", ariaLabel, invalid, max }) {
  return (
    <label style={tx(SIZE.xs, WEIGHT.bold, COLOR.ink, { display: "block", marginTop: SPACE(3) })}>
      {label}
      <input type={type} value={value} inputMode={inputMode} placeholder={placeholder} aria-label={ariaLabel} onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid ? "true" : undefined} max={max}
        style={{ display: "block", width: "100%", marginTop: SPACE(1), minHeight: TOUCH, border: invalid ? `2px solid ${COLOR.watch}` : `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm,
          padding: `0 ${SPACE(3)}px`, background: COLOR.surface, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
    </label>
  );
}

export { tap };
