// ================= 뱁새 2.0 컴포넌트 (v18.1 Part 2) =================
// 화면 문구는 모두 props 로 받아요 (Part 3 에서 src/copy/ko.js 의 키로 바뀔 자리). 이 파일에는 한국어 문구를 두지 않아요.
// 아직 기존 화면은 이 컴포넌트를 쓰지 않아요 (Part 4 게이트).
import React, { useState, useEffect } from "react";
import { COLOR, STATUS, FONT, SIZE, WEIGHT, SPACE, RADIUS, TOUCH, NUM } from "./tokens.js";
import { Icon } from "./icons.jsx";

const T = (size, weight, color, extra) => ({ fontFamily: FONT, fontSize: size, fontWeight: weight, color, lineHeight: 1.5, letterSpacing: "-0.01em", ...extra });
const Section = ({ children, style }) => (
  <section style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(5), ...style }}>{children}</section>
);
const tapReset = { WebkitTapHighlightColor: "transparent", cursor: "pointer", fontFamily: FONT };
// 반올림한 뒤에 부호를 붙여요 (-0.04 가 "−0.0%" 로 보이지 않게)
const fmtPct = (v, d = 1) => {
  const r = Number(Number(v).toFixed(d));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}%`;
};
// "{pct}" 같은 자리 표시를 채워요 (Part 3 문구 파일과 같은 방식)
export const fill = (tpl, vars) => String(tpl).replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] != null ? String(vars[k]) : m));
const priceColor = (v, onPage) => (v > 0 ? (onPage ? COLOR.upOnPage : COLOR.up) : v < 0 ? COLOR.down : COLOR.text2);

// ── 상태 칩: 괜찮아요 · 지켜봐요 · 규칙 깨짐 · 큰 움직임/예시/태그 ──
export function StatusChip({ tone = "neutral", children, icon }) {
  const c = STATUS[tone] || STATUS.neutral;
  return (
    <span data-ui="status-chip" data-tone={tone} style={T(SIZE.xxs, WEIGHT.bold, c.fg, {
      display: "inline-flex", alignItems: "center", gap: SPACE(1), background: c.bg, borderRadius: 999,
      padding: `${SPACE(1)}px ${SPACE(2.5)}px`, whiteSpace: "nowrap", lineHeight: 1.3 })}>
      {icon && <Icon name={icon} size={12} color={c.fg} />}{children}
    </span>
  );
}

// ── 히어로 띠: calm(할 일 없음) · alert(확인할 것). 뱁이 그림 자리 포함 ──
export function HeroBand({ tone = "calm", eyebrow, title, body, image, imageAlt, inset, actions }) {
  const bg = tone === "alert" ? COLOR.heroAlert : COLOR.heroCalm;
  return (
    <section data-ui="hero-band" data-tone={tone} style={{ background: bg, borderRadius: RADIUS.lg, padding: SPACE(5), position: "relative" }}>
      <div style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {eyebrow && <div style={T(SIZE.xs, WEIGHT.bold, tone === "alert" ? COLOR.apricotText : COLOR.ok)}>{eyebrow}</div>}
          <h2 style={T(SIZE.h2, WEIGHT.heavy, COLOR.ink, { margin: `${SPACE(1)}px 0 0`, lineHeight: 1.35, whiteSpace: "pre-line" })}>{title}</h2>
          {body && <p style={T(SIZE.sm, WEIGHT.regular, COLOR.text2, { margin: `${SPACE(2)}px 0 0`, whiteSpace: "pre-line" })}>{body}</p>}
        </div>
        {image && <img src={image} alt={imageAlt || ""} width={72} height={72} style={{ objectFit: "contain", flexShrink: 0 }} />}
      </div>
      {inset && <div style={{ marginTop: SPACE(4), background: COLOR.surface, borderRadius: RADIUS.sm, padding: SPACE(3) }}>{inset}</div>}
      {actions && <div style={{ marginTop: SPACE(4), display: "flex", flexDirection: "column", gap: SPACE(2) }}>{actions}</div>}
    </section>
  );
}

export function Button({ kind = "primary", children, onClick, style }) {
  const k = {
    primary: { background: COLOR.ink, color: COLOR.surface, border: "none" },
    secondary: { background: COLOR.surface, color: COLOR.ink, border: `1px solid ${COLOR.border}` },
    quiet: { background: "transparent", color: COLOR.text2, border: "none" },
  }[kind];
  return (
    <button data-ui="button" data-kind={kind} onClick={onClick} style={{ ...tapReset, ...k, ...T(SIZE.body, WEIGHT.bold, k.color),
      minHeight: TOUCH, borderRadius: RADIUS.sm, padding: `0 ${SPACE(4)}px`, width: "100%", ...style }}>{children}</button>
  );
}

// ── 숫자 띠: 지금 · 산 뒤로 (+ 작은 회색 줄) ──
export function StatStrip({ items, note }) {
  return (
    <div data-ui="stat-strip">
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${items.length}, 1fr)`, gap: SPACE(3) }}>
        {items.map((it) => (
          <div key={it.label}>
            <div style={T(SIZE.xxs, WEIGHT.semi, COLOR.text3)}>{it.label}</div>
            <div style={T(SIZE.h3, WEIGHT.heavy, it.tone === "up" ? COLOR.up : it.tone === "down" ? COLOR.down : COLOR.ink, NUM)}>{it.value}</div>
            {it.sub && <div style={T(SIZE.xxs, WEIGHT.regular, COLOR.text3, NUM)}>{it.sub}</div>}
          </div>
        ))}
      </div>
      {note && <div style={T(SIZE.xxs, WEIGHT.regular, COLOR.text3, { marginTop: SPACE(2), ...NUM })}>{note}</div>}
    </div>
  );
}

// ── 목록 줄: 이름 + 오늘 % · 예외일 때만 칩 ──
export function ListRow({ title, sub, value, change, chip, onClick }) {
  return (
    <div data-ui="list-row" role={onClick ? "button" : undefined} onClick={onClick}
      style={{ ...tapReset, display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + 12, padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={T(SIZE.body, WEIGHT.bold, COLOR.ink, { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{title}</div>
        {(sub || chip) && <div style={{ display: "flex", flexWrap: "wrap", columnGap: SPACE(2), rowGap: 2, alignItems: "center", marginTop: 2 }}>
          {chip}{sub && <span style={T(SIZE.xxs, WEIGHT.regular, COLOR.text3, { whiteSpace: "nowrap" })}>{sub}</span>}
        </div>}
      </div>
      <div style={{ textAlign: "right" }}>
        {value && <div style={T(SIZE.sm, WEIGHT.bold, COLOR.ink, NUM)}>{value}</div>}
        {change != null && <div style={T(SIZE.xs, WEIGHT.bold, priceColor(change), NUM)}>{fmtPct(change)}</div>}
      </div>
    </div>
  );
}

// ── 고르기 버튼 묶음 ──
export function Segmented({ options, value, onChange, label }) {
  return (
    <div data-ui="segmented" role="radiogroup" aria-label={label}
      style={{ display: "grid", gridTemplateColumns: `repeat(${options.length}, 1fr)`, background: COLOR.page, borderRadius: RADIUS.sm, padding: 3, gap: 3 }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} role="radio" aria-checked={on} onClick={() => onChange && onChange(o.value)}
            style={{ ...tapReset, border: "none", minHeight: TOUCH, borderRadius: RADIUS.sm - 3, background: on ? COLOR.surface : "transparent",
              boxShadow: on ? "0 1px 2px rgba(28,43,69,0.12)" : "none", ...T(SIZE.xs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text2) }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// ── 숫자 늘리기·줄이기 ──
export function Stepper({ value, min, max, onChange, label, format = "{count}", decLabel, incLabel }) {
  const btn = (dis) => ({ ...tapReset, width: TOUCH, height: TOUCH, borderRadius: RADIUS.sm, border: `1px solid ${COLOR.border}`, background: COLOR.surface,
    display: "flex", alignItems: "center", justifyContent: "center", opacity: dis ? 0.4 : 1 });
  return (
    <div data-ui="stepper" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(3) }}>
      <span style={T(SIZE.body, WEIGHT.semi, COLOR.ink)}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <button aria-label={decLabel} disabled={value <= min} onClick={() => onChange(Math.max(min, value - 1))} style={btn(value <= min)}><Icon name="minus" size={20} color={COLOR.ink} /></button>
        <span data-ui="stepper-value" style={T(SIZE.h3, WEIGHT.heavy, COLOR.ink, { minWidth: 48, textAlign: "center", ...NUM })}>{fill(format, { count: value })}</span>
        <button aria-label={incLabel} disabled={value >= max} onClick={() => onChange(Math.min(max, value + 1))} style={btn(value >= max)}><Icon name="plus" size={20} color={COLOR.ink} /></button>
      </div>
    </div>
  );
}

// ── 금액 입력 (만원): 빠른 더하기 + 경고 줄 ──
export function MoneyInput({ value, onChange, label, unit, placeholder, quick, clearLabel, warning }) {
  const n = Number(value) || 0;
  return (
    <div data-ui="money-input">
      <label style={T(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block" })}>
        {label}
        <div style={{ display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(2), border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.sm, padding: `0 ${SPACE(3)}px`, minHeight: TOUCH + 4, background: COLOR.surface }}>
          <input inputMode="numeric" value={value === 0 || value === "" ? "" : n.toLocaleString("ko-KR")} placeholder={placeholder}
            onChange={(e) => onChange(Number(e.target.value.replace(/[^0-9]/g, "")) || 0)}
            style={{ flex: 1, minWidth: 0, width: "100%", minHeight: TOUCH, padding: 0, border: "none", outline: "none", background: "transparent", textAlign: "right",
              ...(n ? T(SIZE.h3, WEIGHT.heavy, COLOR.ink, NUM) : T(SIZE.sm, WEIGHT.regular, COLOR.ink)) }} />
          <span style={T(SIZE.sm, WEIGHT.semi, COLOR.text2)}>{unit}</span>
        </div>
      </label>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${quick.length + 1}, 1fr)`, gap: SPACE(2), marginTop: SPACE(2) }}>
        {quick.map((q) => (
          <button key={q.label} onClick={() => onChange(n + q.add)} style={{ ...tapReset, minHeight: TOUCH, borderRadius: RADIUS.sm, border: `1px solid ${COLOR.border}`, background: COLOR.surface, ...T(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{q.label}</button>
        ))}
        <button onClick={() => onChange(0)} style={{ ...tapReset, minHeight: TOUCH, borderRadius: RADIUS.sm, border: "none", background: COLOR.page, ...T(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{clearLabel}</button>
      </div>
      {warning && <div data-ui="money-warning" role="status" style={T(SIZE.xs, WEIGHT.semi, COLOR.watch, { marginTop: SPACE(2), background: COLOR.watchBg, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px` })}>{warning}</div>}
    </div>
  );
}

// ── 아래 고정 버튼 띠 (후보 수 등) ──
export function BottomActionBar({ summary, action, onAction, fixed = false }) {
  return (
    <div data-ui="bottom-action-bar" style={{ position: fixed ? "fixed" : "relative", left: 0, right: 0, bottom: 0, background: COLOR.surface,
      borderTop: `1px solid ${COLOR.line}`, padding: `${SPACE(3)}px ${SPACE(4)}px calc(${SPACE(3)}px + env(safe-area-inset-bottom))`,
      display: "flex", alignItems: "center", gap: SPACE(3), borderRadius: fixed ? 0 : RADIUS.sm }}>
      <div style={{ flex: 1, ...T(SIZE.xs, WEIGHT.semi, COLOR.text2, NUM) }}>{summary}</div>
      <div style={{ width: 150 }}><Button onClick={onAction}>{action}</Button></div>
    </div>
  );
}

// ── 아래에서 올라오는 시트 ──
// inline: 스타일 페이지에서 겹치지 않고 제자리에 보여 줄 때만 써요
export function BottomSheet({ open, title, onClose, closeLabel, children, inline = false }) {
  useEffect(() => {
    if (!open || inline) return undefined;
    const k = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose, inline]);
  if (!open) return null;
  const panel = (
      <div role="dialog" aria-modal={inline ? undefined : "true"} aria-label={title} onClick={(e) => e.stopPropagation()}
        style={{ background: COLOR.surface, width: "100%", maxWidth: 520, borderRadius: `${RADIUS.lg}px ${RADIUS.lg}px ${inline ? RADIUS.lg : 0}px ${inline ? RADIUS.lg : 0}px`,
          padding: `${SPACE(3)}px ${SPACE(5)}px calc(${SPACE(6)}px + ${inline ? "0px" : "env(safe-area-inset-bottom)"})`, boxShadow: inline ? "0 -2px 12px rgba(28,43,69,0.10)" : "none" }}>
        <div style={{ width: 40, height: 4, borderRadius: 2, background: COLOR.border, margin: "0 auto" }} />
        <div style={{ display: "flex", alignItems: "center", marginTop: SPACE(3) }}>
          <h3 style={T(SIZE.h3, WEIGHT.heavy, COLOR.ink, { margin: 0, flex: 1 })}>{title}</h3>
          <button aria-label={closeLabel} onClick={onClose} style={{ ...tapReset, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="close" color={COLOR.text2} /></button>
        </div>
        <div style={{ marginTop: SPACE(2) }}>{children}</div>
      </div>
  );
  if (inline) return <div data-ui="bottom-sheet" data-inline="1">{panel}</div>;
  return (
    <div data-ui="bottom-sheet" onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(28,43,69,0.45)", zIndex: 90, display: "flex", alignItems: "flex-end", justifyContent: "center" }}>
      {panel}
    </div>
  );
}

// ── 접는 섹션 ──
export function Collapsible({ title, sub, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div data-ui="collapsible" data-open={open ? "1" : "0"} style={{ borderTop: `1px solid ${COLOR.line}` }}>
      <button aria-expanded={open} onClick={() => setOpen(!open)} style={{ ...tapReset, width: "100%", minHeight: TOUCH + 4, border: "none", background: "none", display: "flex", alignItems: "center", gap: SPACE(2), padding: 0, textAlign: "left" }}>
        <span style={{ flex: 1 }}>
          <span style={T(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block" })}>{title}</span>
          {sub && <span style={T(SIZE.xxs, WEIGHT.regular, COLOR.text3, { display: "block" })}>{sub}</span>}
        </span>
        <Icon name="chevronDown" size={20} color={COLOR.text2} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .15s" }} />
      </button>
      {open && <div style={{ paddingBottom: SPACE(3) }}>{children}</div>}
    </div>
  );
}

// ── 아래 탭: 오늘 · 내 덱 · 덱 짜기 · 찾기 ──
export function BottomTabBar({ tabs, value, onChange, label, fixed = false }) {
  return (
    <nav data-ui="bottom-tab-bar" aria-label={label} style={{ position: fixed ? "fixed" : "relative", left: 0, right: 0, bottom: 0, background: COLOR.surface,
      borderTop: `1px solid ${COLOR.line}`, display: "grid", gridTemplateColumns: `repeat(${tabs.length}, 1fr)`, paddingBottom: "env(safe-area-inset-bottom)", borderRadius: fixed ? 0 : RADIUS.sm }}>
      {tabs.map((t) => {
        const on = t.id === value;
        return (
          <button key={t.id} aria-current={on ? "page" : undefined} aria-label={t.aria || t.label} disabled={t.disabled} onClick={() => onChange && onChange(t.id)}
            style={{ ...tapReset, border: "none", background: "none", minHeight: TOUCH + 12, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, opacity: t.disabled ? 0.45 : 1 }}>
            <Icon name={t.icon} size={22} color={on ? COLOR.ink : COLOR.text3} />
            <span style={T(SIZE.xxs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text3)}>{t.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ── 점 띠 그래프: 같은 업종의 오늘 등락 (내 종목 강조, 업종 평균 표시) ──
export function DotStrip({ items, mine, avgLabel, mineLabel, aria }) {   // items: [{ id, pct }], mine: 내 종목 id
  const vals = items.map((i) => i.pct);
  const lo = Math.min(...vals, 0), hi = Math.max(...vals, 0);
  const span = hi - lo || 1;
  const x = (v) => 6 + ((v - lo) / span) * 88;          // % 위치 (양끝 여백 6%)
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const lx = (v) => Math.min(78, Math.max(22, x(v)));   // 글자는 양끝에서 잘리지 않게
  const me = items.find((i) => i.id === mine);
  return (
    <figure data-ui="dot-strip" role="img" aria-label={aria} style={{ margin: 0 }}>
      <div style={{ position: "relative", height: 76 }}>
        <div style={{ position: "absolute", left: "6%", right: "6%", top: 38, height: 2, background: COLOR.line }} />
        <div style={{ position: "absolute", left: `${x(0)}%`, top: 26, height: 26, width: 1, background: COLOR.border }} />
        <div style={{ position: "absolute", left: `${x(avg)}%`, top: 18, height: 40, width: 2, background: COLOR.ink, transform: "translateX(-1px)" }} />
        <div style={T(SIZE.xxs, WEIGHT.bold, COLOR.ink, { position: "absolute", top: 0, left: `${lx(avg)}%`, transform: "translateX(-50%)", whiteSpace: "nowrap", ...NUM })}>{fill(avgLabel, { pct: fmtPct(avg) })}</div>
        {items.map((i) => { const m = i.id === mine; return (
          <div key={i.id} data-mine={m ? "1" : undefined} style={{ position: "absolute", top: m ? 31 : 34, left: `${x(i.pct)}%`, transform: "translateX(-50%)", zIndex: m ? 2 : 1,
            width: m ? 16 : 10, height: m ? 16 : 10, borderRadius: 999,
            background: m ? COLOR.apricot : COLOR.text3, opacity: m ? 1 : 0.55, border: m ? `2px solid ${COLOR.surface}` : "none" }} />
        ); })}
        {me && <div style={T(SIZE.xxs, WEIGHT.bold, COLOR.apricotText, { position: "absolute", top: 56, left: `${lx(me.pct)}%`, transform: "translateX(-50%)", whiteSpace: "nowrap", ...NUM })}>{fill(mineLabel, { pct: fmtPct(me.pct) })}</div>}
      </div>
    </figure>
  );
}

// ── 비중 막대 + 목표 표시 ──
export function WeightBar({ current, target, max, label, status }) {
  const top = max || Math.max(current, target) * 1.6;
  const ratio = target > 0 ? current / target : 1;
  const tone = status || (ratio > 1.25 || ratio < 0.75 ? "watch" : "ok");   // 목표의 0.75~1.25배 안이면 정상
  const fill = tone === "watch" ? COLOR.watch : COLOR.ink;
  return (
    <div data-ui="weight-bar" aria-label={label} role="img">
      <div style={{ position: "relative", height: 10, background: COLOR.page, borderRadius: 999 }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${Math.min(100, (current / top) * 100)}%`, background: fill, borderRadius: 999 }} />
        <div style={{ position: "absolute", top: -4, bottom: -4, width: 3, borderRadius: 2, background: COLOR.apricot, left: `${(target / top) * 100}%`, transform: "translateX(-1.5px)" }} />
      </div>
    </div>
  );
}

// ── 규칙 한 줄: 확인 아이콘 + "지금 22% · 30% 넘으면 지켜봐요" ──
export function RuleRow({ name, now, limit, state = "ok", stateLabel }) {
  const ic = state === "ok" ? { name: "check", fg: COLOR.ok, bg: COLOR.okBg } : state === "watch" ? { name: "alert", fg: COLOR.watch, bg: COLOR.watchBg } : { name: "close", fg: COLOR.broken, bg: COLOR.brokenBg };
  return (
    <div data-ui="rule-row" data-state={state} style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start", padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <span style={{ width: 28, height: 28, borderRadius: 999, background: ic.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={ic.name} size={16} color={ic.fg} />
      </span>
      <div style={{ flex: 1 }}>
        <div style={T(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{name}</div>
        <div style={T(SIZE.xs, WEIGHT.regular, COLOR.text2, NUM)}>{[now, limit].filter(Boolean).join(" · ")}</div>
      </div>
      {stateLabel && <StatusChip tone={state === "ok" ? "ok" : state === "watch" ? "watch" : "broken"}>{stateLabel}</StatusChip>}
    </div>
  );
}

export { Section, fmtPct, priceColor };
