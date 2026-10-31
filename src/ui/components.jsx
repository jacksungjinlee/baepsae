// ================= 뱁새 2.0 컴포넌트 (v18.1 Part 2) =================
// 화면 문구는 모두 props 로 받아요 (Part 3 에서 src/copy/ko.js 의 키로 바뀔 자리). 이 파일에는 한국어 문구를 두지 않아요.
// 아직 기존 화면은 이 컴포넌트를 쓰지 않아요 (Part 4 게이트).
// 간격은 4px 격자(SPACE), 누르는 곳은 44px 이상(TOUCH), 숫자는 모두 고정폭(tabular-nums).
import React, { useState, useEffect, useRef } from "react";
import { COLOR, STATUS, FONT, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "./tokens.js";
import { Icon } from "./icons.jsx";

// 모든 글자에 고정폭 숫자를 켜요 (숫자가 없는 글에는 영향 없음)
const T = (size, weight, color, extra) => ({ fontFamily: FONT, fontSize: size, fontWeight: weight, color, lineHeight: 1.5,
  letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums", ...extra });
const Section = ({ children, style }) => (
  <section style={{ background: COLOR.surface, borderRadius: RADIUS.lg, padding: SPACE(5), ...style }}>{children}</section>
);
const tapReset = { WebkitTapHighlightColor: "transparent", cursor: "pointer", fontFamily: FONT, padding: 0 };   // 브라우저 기본 버튼 여백(1px 6px)을 지워요
// 반올림한 뒤에 부호를 붙여요 (-0.04 가 "−0.0%" 로 보이지 않게). 숫자가 아니면 "–"
const fmtPct = (v, d = 1) => {
  const n = Number(v);
  if (v == null || !Number.isFinite(n)) return "–";
  const r = Number(n.toFixed(d));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}%`;
};
// "{pct}" 같은 자리 표시를 채워요 (Part 3 문구 파일과 같은 방식)
export const fill = (tpl, vars) => String(tpl).replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] != null ? String(vars[k]) : m));
// 오름 빨강은 흰 바탕에서만 4.5:1 을 넘어요. page 바탕 위에서는 upOnPage 를 써요
const priceColor = (v, onPage) => (v > 0 ? (onPage ? COLOR.upOnPage : COLOR.up) : v < 0 ? COLOR.down : COLOR.text2);
const toneColor = (tone, onPage) => (tone === "up" ? (onPage ? COLOR.upOnPage : COLOR.up) : tone === "down" ? COLOR.down : COLOR.ink);

// ── 상태 칩: 괜찮아요 · 지켜봐요 · 규칙 깨짐 · 큰 움직임/예시/태그 ──
// 긴 칩은 좁은 화면에서 줄을 바꿔요 (옆 칸을 덮지 않게)
export function StatusChip({ tone = "neutral", children, icon }) {
  const c = STATUS[tone] || STATUS.neutral;
  return (
    <span data-ui="status-chip" data-tone={tone} style={T(SIZE.xxs, WEIGHT.bold, c.fg, {
      display: "inline-flex", alignItems: "center", gap: SPACE(1), background: c.bg, borderRadius: RADIUS.sm,
      padding: `${SPACE(1)}px ${SPACE(2)}px`, maxWidth: "100%", wordBreak: "keep-all", lineHeight: 1.35 })}>
      {icon && <Icon name={icon} size={12} color={c.fg} />}<span>{children}</span>
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
      {inset && <div style={{ marginTop: SPACE(4), background: COLOR.surface, borderRadius: RADIUS.md, padding: SPACE(3) }}>{inset}</div>}
      {actions && <div style={{ marginTop: SPACE(4), display: "flex", flexDirection: "column", gap: SPACE(2) }}>{actions}</div>}
    </section>
  );
}

export function Button({ kind = "primary", children, onClick, disabled = false, type = "button", style }) {
  const k = {
    primary: { background: COLOR.ink, color: COLOR.surface, border: "none" },
    secondary: { background: COLOR.surface, color: COLOR.ink, border: `1px solid ${COLOR.border}` },
    quiet: { background: "transparent", color: COLOR.text2, border: "none" },
  }[kind];
  return (
    <button data-ui="button" data-kind={kind} type={type} disabled={disabled} onClick={onClick} style={{ ...tapReset, ...k, ...T(SIZE.body, WEIGHT.bold, k.color),
      minHeight: TOUCH, borderRadius: RADIUS.sm, padding: `0 ${SPACE(4)}px`, width: "100%", opacity: disabled ? 0.45 : 1,
      cursor: disabled ? "default" : "pointer", ...style }}>{children}</button>
  );
}

// ── 숫자 띠: 지금 · 산 뒤로 (+ 작은 회색 줄) ──
// onPage: page(베이지) 바탕 위에 놓을 때. 작은 글자는 text2, 오름 숫자는 upOnPage 로 바뀌어요
export function StatStrip({ items, note, onPage = false }) {
  const small = onPage ? COLOR.text2 : COLOR.text3;
  return (
    <div data-ui="stat-strip" data-on-page={onPage ? "1" : undefined}>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${items.length}, 1fr)`, gap: SPACE(3) }}>
        {items.map((it) => (
          <div key={it.label}>
            <div style={T(SIZE.xxs, WEIGHT.semi, small)}>{it.label}</div>
            <div style={T(SIZE.h3, WEIGHT.heavy, toneColor(it.tone, onPage))}>{it.value}</div>
            {it.sub && <div style={T(SIZE.xxs, WEIGHT.regular, small)}>{it.sub}</div>}
          </div>
        ))}
      </div>
      {note && <div style={T(SIZE.xxs, WEIGHT.regular, small, { marginTop: SPACE(2) })}>{note}</div>}
    </div>
  );
}

// ── 목록 줄: 이름 + 오늘 % · 예외일 때만 칩 ── (흰 섹션 안에 놓아요)
export function ListRow({ title, sub, value, change, chip, onClick }) {
  const act = onClick ? {
    role: "button", tabIndex: 0, onClick,
    onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(e); } },
  } : {};
  return (
    <div data-ui="list-row" {...act}
      style={{ ...(onClick ? tapReset : { fontFamily: FONT }), display: "flex", alignItems: "center", gap: SPACE(3), minHeight: TOUCH + SPACE(3), padding: `${SPACE(2)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <div data-ui-part="main" style={{ flex: 1, minWidth: 0 }}>
        <div style={T(SIZE.body, WEIGHT.bold, COLOR.ink, { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>{title}</div>
        {(sub || chip) && <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE(1), columnGap: SPACE(2), alignItems: "center", marginTop: SPACE(1) }}>
          {chip}{sub && <span style={T(SIZE.xxs, WEIGHT.regular, COLOR.text3)}>{sub}</span>}
        </div>}
      </div>
      <div data-ui-part="side" style={{ textAlign: "right", flexShrink: 0 }}>
        {value && <div style={T(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{value}</div>}
        {change != null && <div style={T(SIZE.xs, WEIGHT.bold, priceColor(change))}>{fmtPct(change)}</div>}
      </div>
    </div>
  );
}

// ── 고르기 버튼 묶음 (라디오: 화살표 키로 옮겨요) ──
export function Segmented({ options, value, onChange, label }) {
  const refs = useRef([]);
  const idx = Math.max(0, options.findIndex((o) => o.value === value));
  const move = (e) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const j = (idx + step + options.length) % options.length;
    if (onChange) onChange(options[j].value);
    if (refs.current[j]) refs.current[j].focus();
  };
  return (
    <div data-ui="segmented" role="radiogroup" aria-label={label} onKeyDown={move}
      style={{ display: "grid", gridTemplateColumns: `repeat(${options.length}, 1fr)`, background: COLOR.page, borderRadius: RADIUS.sm, padding: SPACE(1), gap: SPACE(1) }}>
      {options.map((o, i) => {
        const on = i === idx;
        return (
          <button key={o.value} ref={(el) => { refs.current[i] = el; }} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1}
            onClick={() => onChange && onChange(o.value)}
            style={{ ...tapReset, border: "none", minHeight: TOUCH, padding: `0 ${SPACE(1)}px`, borderRadius: RADIUS.sm - SPACE(1), background: on ? COLOR.surface : "transparent",
              boxShadow: on ? "0 1px 2px rgba(28,43,69,0.12)" : "none", ...T(SIZE.xs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text2, { wordBreak: "keep-all", lineHeight: 1.3 }) }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// ── 숫자 늘리기·줄이기 ──
export function Stepper({ value, min = -Infinity, max = Infinity, onChange, label, format = "{count}", decLabel, incLabel }) {
  const btn = (dis) => ({ ...tapReset, width: TOUCH, height: TOUCH, borderRadius: RADIUS.sm, border: `1px solid ${COLOR.border}`, background: COLOR.surface,
    display: "flex", alignItems: "center", justifyContent: "center", opacity: dis ? 0.4 : 1, cursor: dis ? "default" : "pointer" });
  const set = (v) => { if (onChange && Number.isFinite(v)) onChange(v); };
  return (
    <div data-ui="stepper" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: SPACE(3) }}>
      <span style={T(SIZE.body, WEIGHT.semi, COLOR.ink)}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: SPACE(3) }}>
        <button type="button" aria-label={decLabel} disabled={value <= min} onClick={() => set(Math.max(min, value - 1))} style={btn(value <= min)}><Icon name="minus" size={20} color={COLOR.ink} /></button>
        <span data-ui="stepper-value" aria-live="polite" style={T(SIZE.h3, WEIGHT.heavy, COLOR.ink, { minWidth: SPACE(12), textAlign: "center" })}>{fill(format, { count: value })}</span>
        <button type="button" aria-label={incLabel} disabled={value >= max} onClick={() => set(Math.min(max, value + 1))} style={btn(value >= max)}><Icon name="plus" size={20} color={COLOR.ink} /></button>
      </div>
    </div>
  );
}

// ── 금액 입력 (만원): 빠른 더하기 + 경고 줄 ──
// 만원 단위 정수만 받아요. 숫자·쉼표 말고 다른 글자(소수점, 빼기)가 들어오면 그 입력은 받지 않아요.
// 입력하는 동안은 쉼표 없이 보여 주고(지우기·커서가 튀지 않게), 칸을 벗어나면 1,000 처럼 묶어 보여 줘요.
// 글자 크기는 16px 이상: 아이폰 사파리는 16px 보다 작은 입력칸을 누르면 화면을 확대해요.
const parseMan = (s) => {
  const raw = String(s).replace(/,/g, "").trim();
  if (!/^\d*$/.test(raw)) return null;
  return raw === "" ? 0 : Number(raw);
};
export function MoneyInput({ value, onChange, label, unit, placeholder, quick, clearLabel, warning }) {
  const n = Number(value) || 0;
  const [draft, setDraft] = useState(null);          // 입력 중인 글자 (null = 입력 중 아님)
  const shown = draft != null ? draft : (n ? n.toLocaleString("ko-KR") : "");
  return (
    <div data-ui="money-input">
      <label style={T(SIZE.sm, WEIGHT.bold, COLOR.ink, { display: "block" })}>
        {label}
        <div style={{ position: "relative", display: "flex", alignItems: "center", gap: SPACE(2), marginTop: SPACE(2), border: `1px solid ${COLOR.border}`, borderRadius: RADIUS.md, padding: `0 ${SPACE(3)}px`, minHeight: TOUCH + SPACE(1), background: COLOR.surface }}>
          {shown === "" && placeholder && <span aria-hidden="true" style={T(SIZE.body, WEIGHT.regular, COLOR.text2, { position: "absolute", left: SPACE(3), right: SPACE(3) + SPACE(10), textAlign: "right", pointerEvents: "none", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" })}>{placeholder}</span>}
          <input inputMode="numeric" autoComplete="off" value={shown} aria-placeholder={placeholder}
            onFocus={() => setDraft(n ? String(n) : "")}
            onBlur={() => setDraft(null)}
            onChange={(e) => { const v = parseMan(e.target.value); if (v == null) return; setDraft(e.target.value.replace(/,/g, "")); onChange(v); }}
            style={{ flex: 1, minWidth: 0, width: "100%", minHeight: TOUCH, padding: 0, border: "none", outline: "none", background: "transparent", textAlign: "right",
              ...(shown ? T(SIZE.h3, WEIGHT.heavy, COLOR.ink) : T(SIZE.body, WEIGHT.regular, COLOR.ink)) }} />
          <span style={T(SIZE.sm, WEIGHT.semi, COLOR.text2, { width: SPACE(8), textAlign: "right", flexShrink: 0 })}>{unit}</span>
        </div>
      </label>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${quick.length + 1}, 1fr)`, gap: SPACE(2), marginTop: SPACE(2) }}>
        {quick.map((q) => (
          <button key={q.label} type="button" onClick={() => { setDraft(null); onChange(n + q.add); }} style={{ ...tapReset, minHeight: TOUCH, borderRadius: RADIUS.sm, border: `1px solid ${COLOR.border}`, background: COLOR.surface, ...T(SIZE.xs, WEIGHT.bold, COLOR.ink) }}>{q.label}</button>
        ))}
        <button type="button" onClick={() => { setDraft(null); onChange(0); }} style={{ ...tapReset, minHeight: TOUCH, borderRadius: RADIUS.sm, border: "none", background: COLOR.page, ...T(SIZE.xs, WEIGHT.bold, COLOR.text2) }}>{clearLabel}</button>
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
      <div style={{ flex: 1, minWidth: 0, ...T(SIZE.xs, WEIGHT.semi, COLOR.text2) }}>{summary}</div>
      <div style={{ width: SPACE(38), flexShrink: 0 }}><Button onClick={onAction}>{action}</Button></div>
    </div>
  );
}

// ── 아래에서 올라오는 시트 ──
// 열리면: 뒤 화면 스크롤을 멈추고, 포커스를 시트 안으로 옮겨 가두고, 닫히면 원래 자리로 돌려줘요.
// 바깥(어두운 곳)을 눌렀다 뗄 때만 닫혀요 — 시트 안에서 끌다가 바깥에서 놓으면 닫히지 않아요.
// 화면이 낮으면(가로 화면, 키보드) 시트 안이 스크롤돼요. 제목과 닫기 버튼은 위에 붙어 있어요.
// inline: 스타일 페이지에서 겹치지 않고 제자리에 보여 줄 때만 써요
const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';
export function BottomSheet({ open, title, onClose, closeLabel, children, inline = false }) {
  const panelRef = useRef(null);
  const downOnBackdrop = useRef(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open || inline) return undefined;
    const opener = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const panel = panelRef.current;
    const first = panel && panel.querySelector(FOCUSABLE);
    (first || panel) && (first || panel).focus();
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); closeRef.current(); return; }
      if (e.key !== "Tab" || !panel) return;
      const f = [...panel.querySelectorAll(FOCUSABLE)];
      if (!f.length) { e.preventDefault(); panel.focus(); return; }
      const a = f[0], z = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === a || !panel.contains(document.activeElement))) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && (document.activeElement === z || !panel.contains(document.activeElement))) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      if (opener && opener.focus && document.contains(opener)) opener.focus();
    };
  }, [open, inline]);
  if (!open) return null;
  const panel = (
    <div ref={panelRef} role="dialog" aria-modal={inline ? undefined : "true"} aria-label={title} tabIndex={-1}
      style={{ background: COLOR.surface, width: "100%", maxWidth: 520, outline: "none",
        borderRadius: `${RADIUS.lg}px ${RADIUS.lg}px ${inline ? RADIUS.lg : 0}px ${inline ? RADIUS.lg : 0}px`,
        maxHeight: inline ? "none" : "88vh", overflowY: inline ? "visible" : "auto", overscrollBehavior: "contain",
        padding: `0 ${SPACE(5)}px calc(${SPACE(6)}px + ${inline ? "0px" : "env(safe-area-inset-bottom)"})`, boxShadow: inline ? "0 -2px 12px rgba(28,43,69,0.10)" : "none" }}>
      <div style={{ position: inline ? "static" : "sticky", top: 0, background: COLOR.surface, paddingTop: SPACE(3), zIndex: 1 }}>
        <div style={{ width: SPACE(10), height: SPACE(1), borderRadius: 2, background: COLOR.border, margin: "0 auto" }} />
        <div style={{ display: "flex", alignItems: "center", marginTop: SPACE(2) }}>
          <h3 style={T(SIZE.h3, WEIGHT.heavy, COLOR.ink, { margin: 0, flex: 1 })}>{title}</h3>
          <button type="button" aria-label={closeLabel} onClick={onClose} style={{ ...tapReset, width: TOUCH, height: TOUCH, border: "none", background: "none", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="close" color={COLOR.text2} /></button>
        </div>
      </div>
      <div style={{ marginTop: SPACE(2) }}>{children}</div>
    </div>
  );
  if (inline) return <div data-ui="bottom-sheet" data-inline="1">{panel}</div>;
  return (
    <div data-ui="bottom-sheet"
      onPointerDown={(e) => { downOnBackdrop.current = e.target === e.currentTarget; }}
      onClick={(e) => { if (downOnBackdrop.current && e.target === e.currentTarget) onClose(); downOnBackdrop.current = false; }}
      style={{ position: "fixed", inset: 0, background: "rgba(28,43,69,0.45)", zIndex: 90, display: "flex", alignItems: "flex-end", justifyContent: "center" }}>
      {panel}
    </div>
  );
}

// ── 접는 섹션 ──
export function Collapsible({ title, sub, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div data-ui="collapsible" data-open={open ? "1" : "0"} style={{ borderTop: `1px solid ${COLOR.line}` }}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} style={{ ...tapReset, width: "100%", minHeight: TOUCH + SPACE(1), border: "none", background: "none", display: "flex", alignItems: "center", gap: SPACE(2), padding: 0, textAlign: "left" }}>
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
          <button key={t.id} type="button" aria-current={on ? "page" : undefined} aria-label={t.aria || t.label} disabled={t.disabled} onClick={() => onChange && onChange(t.id)}
            style={{ ...tapReset, border: "none", background: "none", minHeight: TOUCH + SPACE(3), display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: SPACE(1), opacity: t.disabled ? 0.45 : 1, cursor: t.disabled ? "default" : "pointer" }}>
            <Icon name={t.icon} size={22} color={on ? COLOR.ink : COLOR.text3} />
            <span style={T(SIZE.xxs, on ? WEIGHT.heavy : WEIGHT.semi, on ? COLOR.ink : COLOR.text3)}>{t.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ── 점 띠 그래프: 같은 업종의 오늘 등락 (내 종목 강조, 업종 평균 표시) ──
// 다른 종목 점은 text3 그대로(흰 바탕 4.8:1). 그림 요소도 3:1 이상이어야 해요.
export function DotStrip({ items, mine, avgLabel, mineLabel, aria }) {   // items: [{ id, pct }], mine: 내 종목 id
  const ok = (items || []).filter((i) => Number.isFinite(Number(i.pct)));
  if (!ok.length) return null;
  const vals = ok.map((i) => Number(i.pct));
  const lo = Math.min(...vals, 0), hi = Math.max(...vals, 0);
  const span = hi - lo || 1;
  const x = (v) => 6 + ((v - lo) / span) * 88;          // % 위치 (양끝 여백 6%)
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const lx = (v) => Math.min(78, Math.max(22, x(v)));   // 글자는 양끝에서 잘리지 않게
  const me = ok.find((i) => i.id === mine);
  return (
    <figure data-ui="dot-strip" role="img" aria-label={aria} style={{ margin: 0 }}>
      <div style={{ position: "relative", height: SPACE(19) }}>
        <div style={{ position: "absolute", left: "6%", right: "6%", top: SPACE(9) + 2, height: 2, background: COLOR.line }} />
        <div style={{ position: "absolute", left: `${x(0)}%`, top: SPACE(6) + 2, height: SPACE(6) + 2, width: 1, background: COLOR.border }} />
        <div style={{ position: "absolute", left: `${x(avg)}%`, top: SPACE(5), height: SPACE(9), width: 2, background: COLOR.ink, transform: "translateX(-1px)" }} />
        <div style={T(SIZE.xxs, WEIGHT.bold, COLOR.ink, { position: "absolute", top: 0, left: `${lx(avg)}%`, transform: "translateX(-50%)", whiteSpace: "nowrap" })}>{fill(avgLabel, { pct: fmtPct(avg) })}</div>
        {ok.map((i) => { const m = i.id === mine; return (
          <div key={i.id} data-mine={m ? "1" : undefined} style={{ position: "absolute", top: m ? SPACE(8) - 1 : SPACE(8) + 2, left: `${x(i.pct)}%`, transform: "translateX(-50%)", zIndex: m ? 2 : 1,
            width: m ? 16 : 10, height: m ? 16 : 10, borderRadius: 999,
            background: m ? COLOR.apricot : COLOR.text3, border: m ? `2px solid ${COLOR.surface}` : `1px solid ${COLOR.surface}`, boxSizing: "border-box" }} />
        ); })}
        {me && <div style={T(SIZE.xxs, WEIGHT.bold, COLOR.apricotText, { position: "absolute", top: SPACE(14), left: `${lx(me.pct)}%`, transform: "translateX(-50%)", whiteSpace: "nowrap" })}>{fill(mineLabel, { pct: fmtPct(me.pct) })}</div>}
      </div>
    </figure>
  );
}

// ── 비중 막대 + 목표 표시 ──
// 목표의 0.75~1.25배 안이면 정상(진한 막대), 밖이면 지켜봐요(호박색). 막대 밖으로 나가는 값은 끝에 붙여요.
export function WeightBar({ current, target, max, label, status }) {
  const cur = Math.max(0, Number(current) || 0), tgt = Math.max(0, Number(target) || 0);
  const top = max > 0 ? max : Math.max(cur, tgt, 1) * 1.6;
  const pct = (v) => Math.min(100, (v / top) * 100);
  const ratio = tgt > 0 ? cur / tgt : 1;
  const tone = status || (ratio > 1.25 || ratio < 0.75 ? "watch" : "ok");
  const bar = tone === "watch" ? COLOR.watch : COLOR.ink;
  return (
    <div data-ui="weight-bar" data-tone={tone} role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={Math.round(top)} aria-valuenow={cur} aria-valuetext={`${cur}%`}>
      <div style={{ position: "relative", height: SPACE(2) + 2, background: COLOR.page, borderRadius: 999 }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pct(cur)}%`, background: bar, borderRadius: 999 }} />
        <div style={{ position: "absolute", top: -SPACE(1), bottom: -SPACE(1), width: 3, borderRadius: 2, background: COLOR.apricot, left: `${pct(tgt)}%`, transform: "translateX(-1.5px)" }} />
      </div>
    </div>
  );
}

// ── 규칙 한 줄: 확인 아이콘 + "지금 22% · 30% 넘으면 지켜봐요" ──
export function RuleRow({ name, now, limit, state = "ok", stateLabel }) {
  const ic = state === "ok" ? { name: "check", fg: COLOR.ok, bg: COLOR.okBg } : state === "watch" ? { name: "alert", fg: COLOR.watch, bg: COLOR.watchBg } : { name: "close", fg: COLOR.broken, bg: COLOR.brokenBg };
  return (
    <div data-ui="rule-row" data-state={state} style={{ display: "flex", gap: SPACE(3), alignItems: "flex-start", padding: `${SPACE(3)}px 0`, borderBottom: `1px solid ${COLOR.line}` }}>
      <span style={{ width: SPACE(7), height: SPACE(7), borderRadius: 999, background: ic.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={ic.name} size={16} color={ic.fg} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={T(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{name}</div>
        <div style={T(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{[now, limit].filter(Boolean).join(" · ")}</div>
      </div>
      {stateLabel && <StatusChip tone={state === "ok" ? "ok" : state === "watch" ? "watch" : "broken"}>{stateLabel}</StatusChip>}
    </div>
  );
}

export { Section, fmtPct, priceColor };
