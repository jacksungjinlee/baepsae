// ================= 뱁새 2.0 아이콘 (v18.1 Part 1 → v19.0b Phosphor duotone) =================
// Phosphor duotone (@phosphor-icons/core, MIT: vendor/phosphor/LICENSE): 256 격자, 두 층(바탕 · 선)을 인라인 SVG 로 그려요.
// 바깥 주소에서 아무것도 받지 않아요. path 데이터는 src/ui/phosphor.js (tools/vendor_phosphor.py 가 만들어요).
// 색은 tokens.js 의 ICON_TONE (on · off · ok · onNavy, v19.1 주제 색 earn · value · div · risk · disc)뿐이에요. 살구색은 아이콘에 쓰지 않아요.
// 이모지는 어디에도 쓰지 않아요.
// 예전 이름(check · alert · today …)은 그대로 쓸 수 있어요: ALIAS 가 Phosphor 이름으로 바꿔 줘요.
import React from "react";
import { ICON_TONE, ICON_CHIP, TOPIC_CHIP } from "./tokens.js";
import { PH } from "./phosphor.js";

// 예전 이름 → Phosphor 이름 (v19.0b). 탭 이름은 v19.0c 의 탭(홈 · 포트폴리오)과 같은 그림이에요.
export const ALIAS = {
  check: "check", alert: "warning", info: "info", close: "x", plus: "plus", minus: "minus",
  chevronRight: "caret-right", chevronDown: "caret-down", back: "caret-left",
  today: "house", deck: "chart-pie-slice", build: "plus-circle", search: "magnifying-glass",
  calendar: "calendar-dots", news: "newspaper", rule: "clipboard-text", dot: "circle-dashed",
};

export const ICON_NAMES = [...new Set([...Object.keys(ALIAS), ...Object.keys(PH)])];
export const ICON_TONES = Object.keys(ICON_TONE);

// 없는 이름은 그리지 않고, 이름마다 한 번 크게 알려요 (조용한 실패 금지)
const warned = new Set();
function warnUnknown(name) {
  if (warned.has(name)) return;
  warned.add(name);
  console.warn("[icons] unknown icon name, nothing drawn: " + String(name));
}

// tone: on(남색 · 기본) · off(회색) · ok(초록) · onNavy(남색 바탕 위 흰색) · 주제 색 다섯(선은 남색)
export function Icon({ name, size = 24, tone = "on", title, style }) {
  const key = ALIAS[name] || name;
  const d = PH[key];
  if (!d) { warnUnknown(name); return null; }
  const t = ICON_TONE[tone] || ICON_TONE.on;
  return (
    <svg data-icon={name} data-ph={key} data-tone={ICON_TONE[tone] ? tone : "on"} width={size} height={size} viewBox="0 0 256 256"
      role={title ? "img" : undefined} aria-hidden={title ? undefined : true} aria-label={title} style={{ flexShrink: 0, display: "block", ...style }}>
      <path data-layer="fill" d={d[0]} fill={t.fill} />
      <path data-layer="line" d={d[1]} fill={t.line} />
    </svg>
  );
}

// 아이콘 칩: 따뜻한 회색 바탕(select), 크기의 30% 둥글기 (섹션 · 메뉴 · 뱁이 대신 놓는 자리)
// v19.1 Part H: tone 이 주제(earn · value · div · risk · disc)면 칩 바탕도 그 주제의 옅은 색(TOPIC_CHIP)이에요.
export function IconChip({ name, size = 36, tone = "on", style }) {
  return (
    <span data-ui="icon-chip" data-icon={name} data-topic={TOPIC_CHIP[tone] ? tone : undefined} style={{ width: size, height: size, borderRadius: ICON_CHIP.radius,
      background: TOPIC_CHIP[tone] || ICON_CHIP.bg,
      display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0, ...style }}>
      <Icon name={name} size={Math.round(size * 0.6)} tone={tone} />
    </span>
  );
}
