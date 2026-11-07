// ================= 회사 페이지의 작은 그림 (v19.3e, v19.3 Part I; boards CoSummary2 · CoValue2 · CoDiv2) =================
// The small visuals the 요약 tiles and the 가치 · 배당 tabs carry under their approved phrases: three bars (실적), a scale
// (가치), coins (배당), two waves (출렁임), the 100만원 coin flow and the payout ring. Each one draws only what its tile's
// own rule already says (company.js), on the same numbers, so a picture never says more than the words beside it:
// - 실적: the three 사업보고서 operating profits, oldest first, only when all three are above 0 (a loss has no bar).
// - 가치: the PBR against the industry median: the median sits in the middle, the company at 50% × PBR ÷ median
//   (clamped to the ends). No 싸게 · 비싸게 words under it: those are not approved yet (v19.3e report).
// - 배당: three coin stacks (decoration only: no number in it).
// - 출렁임: a schematic, not a price chart. The market line is fixed; the company's swing follows the tile's own rule
//   (big · similar · small), never a number of its own.
// Colours: the topic tints of CLAUDE.md and their darker board shades (tokens.js TOPIC_ART), navy for "this company"
// where a chart compares it with others (the company page's rule), never a logo colour, never price red or blue.
// No Korean here: labels come from src/copy/v2.js through the callers.
import React from "react";
import { COLOR, SIZE, WEIGHT, SPACE, TOPIC_ART } from "../ui/tokens.js";
import { tx } from "./ui.jsx";

// 실적: three bars, the latest in the topic's dark shade.
export function EarnBars({ op }) {
  const v = Array.isArray(op) ? [op[2], op[1], op[0]] : [];
  if (v.length !== 3 || !v.every((x) => typeof x === "number" && Number.isFinite(x) && x > 0)) return null;
  const mx = Math.max(...v);
  const A = TOPIC_ART.earn;
  return (
    <div data-ui-v2="tile-art" data-art="bars" aria-hidden="true" style={{ display: "flex", alignItems: "flex-end", gap: 5, height: 34, marginTop: SPACE(2) }}>
      {v.map((x, i) => (
        <span key={i} data-v={x} style={{ width: 12, height: Math.max(4, Math.round((x / mx) * 34)), borderRadius: "3px 3px 1px 1px", background: i === 2 ? A.ink : A.light }} />
      ))}
    </div>
  );
}

// 가치: where this PBR sits against the industry median (the median in the middle).
export const scaleAt = (pbr, med) => (pbr > 0 && med > 0 ? Math.min(0.96, Math.max(0.04, (0.5 * pbr) / med)) : null);
export function ValueScale({ pbr, med }) {
  const x = scaleAt(pbr, med);
  if (x == null) return null;
  const A = TOPIC_ART.value;
  return (
    <div data-ui-v2="tile-art" data-art="scale" data-x={Math.round(x * 1000) / 1000} aria-hidden="true" style={{ position: "relative", height: 26, marginTop: SPACE(2) }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 9, height: 8, borderRadius: 4,
        background: `linear-gradient(90deg, ${A.ink} 0%, ${A.light} 45%, #E3E7EE 55%, #B9C1CE 100%)` }} />
      <div style={{ position: "absolute", left: "calc(50% - 1px)", top: 5, width: 2, height: 16, background: COLOR.ink }} />
      <div style={{ position: "absolute", left: `calc(${(x * 100).toFixed(1)}% - 7px)`, top: 6, width: 14, height: 14, borderRadius: 7, background: COLOR.ink,
        border: `2px solid ${COLOR.surface}`, boxSizing: "border-box" }} />
    </div>
  );
}

// 배당: three coin stacks (board CoSummary2), a decoration with no number. shape "rising" (늘렸어요: 2 · 3 · 4 coins, as the
// board) or "even" (a payer with no rise: 3 · 3 · 3). company.divArt picks it from the tile's rule.
export function Coins({ width = 92, shape = "even" }) {
  const A = TOPIC_ART.div;
  const stack = (cx, n) => Array.from({ length: n }, (_, i) => (
    <ellipse key={cx + "-" + i} cx={cx} cy={30 - i * 5} rx={8} ry={3} fill={i % 2 ? A.light : A.ink} stroke={A.ink} strokeWidth={0.9} />
  ));
  return (
    <svg data-ui-v2="tile-art" data-art="coins" data-shape={shape === "rising" ? "rising" : "even"} width={width} height={Math.round((width * 34) / 66)} viewBox="0 0 66 34" aria-hidden="true" style={{ display: "block", marginTop: SPACE(2) }}>
      {shape === "rising" ? <>{stack(14, 2)}{stack(34, 3)}{stack(54, 4)}</> : <>{stack(14, 3)}{stack(34, 3)}{stack(54, 3)}</>}
    </svg>
  );
}

// 출렁임: two schematic waves. The market's swing is fixed; the company's follows the tile's rule.
const SWING = { big: 11, similar: 4.5, small: 1.8 };
const PATTERN = [0, -1, 1, -0.8, 0.9, -1, 0.85, -0.9, 1, -0.95, 0.8, -0.7, 0.3];
const wave = (amp) => PATTERN.map((k, i) => `${i * 10},${(17 + k * amp).toFixed(1)}`).join(" ");
export function Waves({ rule, mine, market }) {
  const amp = SWING[rule];
  if (amp == null) return null;
  const A = TOPIC_ART.risk;
  const key = (color, label, w) => (
    <span data-ui-v2="wave-key" style={{ display: "inline-flex", alignItems: "center", gap: SPACE(1), whiteSpace: "nowrap" }}>
      <span aria-hidden="true" style={{ width: 12, height: w, borderRadius: 2, background: color, display: "inline-block" }} />{label}
    </span>
  );
  return (
    <div data-ui-v2="tile-art" data-art="waves" data-rule={rule} style={{ marginTop: SPACE(2) }}>
      <svg width="100%" height="34" viewBox="0 0 120 34" preserveAspectRatio="none" aria-hidden="true" style={{ display: "block" }}>
        <polyline points={wave(3)} fill="none" stroke={A.light} strokeWidth={2} vectorEffect="non-scaling-stroke" />
        <polyline points={wave(amp)} fill="none" stroke={A.ink} strokeWidth={2.4} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      {mine && market && (
        <div aria-hidden="true" style={{ display: "flex", flexWrap: "wrap", columnGap: SPACE(3), marginTop: SPACE(1), ...tx(SIZE.xs, WEIGHT.regular, COLOR.text2) }}>
          {key(A.ink, mine, 3)}{key(A.light, market, 2)}
        </div>
      )}
    </div>
  );
}

// 100만원어치 → 1년 동안 → 약 {x}: a big coin stack, a dashed arrow with its label, a small stack with the amount.
export function CoinFlow({ yearLabel, amount, aria }) {
  const A = TOPIC_ART.div;
  const big = Array.from({ length: 8 }, (_, i) => (
    <ellipse key={i} cx={30} cy={66 - i * 8} rx={26} ry={8} fill={i % 2 ? A.light : A.ink} stroke={A.ink} strokeWidth={1.4} />
  ));
  return (
    <div data-ui-v2="co-coinflow" role="img" aria-label={aria} style={{ display: "flex", alignItems: "flex-end", gap: SPACE(2), marginTop: SPACE(3) }}>
      <svg width={60} height={76} viewBox="0 0 60 76" aria-hidden="true" style={{ display: "block", flexShrink: 0 }}>{big}</svg>
      <div aria-hidden="true" style={{ flex: 1, minWidth: 0, paddingBottom: SPACE(5), textAlign: "center" }}>
        <div style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2)}>{yearLabel}</div>
        <svg width="100%" height={16} viewBox="0 0 100 16" preserveAspectRatio="none" style={{ display: "block", marginTop: 2 }}>
          <path d="M2 8 H94" stroke={A.ink} strokeWidth={3} strokeDasharray="6 5" vectorEffect="non-scaling-stroke" fill="none" />
          <path d="M88 2 L97 8 L88 14" fill="none" stroke={A.ink} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div aria-hidden="true" style={{ flexShrink: 0, textAlign: "center", minWidth: 72 }}>
        <svg width={40} height={22} viewBox="0 0 40 22" style={{ display: "block", margin: "0 auto" }}>
          <ellipse cx={20} cy={15} rx={18} ry={6} fill={A.ink} stroke={A.ink} strokeWidth={1.2} />
          <ellipse cx={20} cy={8} rx={18} ry={6} fill={A.light} stroke={A.ink} strokeWidth={1.2} />
        </svg>
        <div data-ui-v2="co-coinflow-amount" style={tx(SIZE.sm, WEIGHT.heavy, COLOR.ink, { marginTop: SPACE(1), whiteSpace: "nowrap" })}>{amount}</div>
      </div>
    </div>
  );
}

// The payout ring: "이익 100원 중 {x}원" with the share drawn in the 배당 shade and the rest in its light tint.
export function PayoutRing({ pct, label }) {
  const R = 39, SW = 14, L = 2 * Math.PI * R;
  const f = Math.min(1, Math.max(0, pct / 100));
  const A = TOPIC_ART.div;
  return (
    <div aria-hidden="true" style={{ position: "relative", width: 96, height: 96, flexShrink: 0 }}>
      <svg width={96} height={96} viewBox="0 0 96 96" style={{ display: "block" }}>
        <circle cx={48} cy={48} r={R} fill="none" stroke={A.light} strokeWidth={SW} />
        <circle cx={48} cy={48} r={R} fill="none" stroke={A.ink} strokeWidth={SW} strokeDasharray={`${(f * L).toFixed(1)} ${L.toFixed(1)}`} transform="rotate(-90 48 48)" />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", ...tx(SIZE.h3, WEIGHT.heavy, COLOR.ink) }}>{label}</div>
    </div>
  );
}
