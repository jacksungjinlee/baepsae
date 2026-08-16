// ================= 뱁새 v11 아이콘 =================
// 1.5px 스트로크의 기하학적 라인 아이콘. 이모지를 대체합니다.
import { C } from "./tokens.js";

const P = {
  compass: <><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5l-2.2 5-5 2.2 2.2-5z" /></>,
  chart: <><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-8" /><path d="M22 20H2" /></>,
  doc: <><path d="M6 2h9l4 4v16H6z" /><path d="M15 2v4h4" /><path d="M9 12h7M9 16h7" /></>,
  spark: <path d="M12 2l2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4z" />,
  shield: <><path d="M12 3l7 3v6c0 4.4-3 7.4-7 9-4-1.6-7-4.6-7-9V6z" /><path d="M9 12l2 2 4-4" /></>,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="0.8" fill="currentColor" /></>,
  trend: <><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></>,
  coins: <><ellipse cx="12" cy="6.5" rx="7" ry="3" /><path d="M5 6.5V12c0 1.7 3.1 3 7 3s7-1.3 7-3V6.5" /><path d="M5 12v5.5c0 1.7 3.1 3 7 3s7-1.3 7-3V12" /></>,
  arrow: <><path d="M4 12h16" /><path d="M13 5l7 7-7 7" /></>,
  back: <><path d="M20 12H4" /><path d="M11 5l-7 7 7 7" /></>,
  close: <><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>,
  rates: <><path d="M3 18c4-1 5-8 9-8s5 5 9 3" /><path d="M4 4v17h17" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 10.5V17" /><path d="M12 7v.5" /></>,
  pen: <><path d="M4 20l4.5-1L19 8.5l-3.5-3.5L5 15.5z" /><path d="M13.5 7l3.5 3.5" /></>,
  check: <path d="M4 12.5l5 5L20 6.5" />,
  alert: <><path d="M12 3l10 17H2z" /><path d="M12 10v4" /><path d="M12 17.5v.5" /></>,
  gear: <><circle cx="12" cy="12" r="3.2" /><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" /></>,
  home: <><path d="M3 11l9-8 9 8" /><path d="M5.5 9.5V21h13V9.5" /></>,
  seed: <><path d="M12 21V11" /><path d="M12 11C12 6 8 4 4 4c0 5 3 7 8 7z" /><path d="M12 13c0-4 3.2-5.5 6.5-5.5 0 4-2.5 5.5-6.5 5.5z" /></>,
  scale: <><path d="M12 3v18M6 21h12" /><path d="M12 6l-6 3 6-3 6 3" /><path d="M6 9l-2.5 5a3.5 3.5 0 0 0 5 0z" /><path d="M18 9l-2.5 5a3.5 3.5 0 0 0 5 0z" /></>,
  flame: <path d="M12 3s5.5 4.5 5.5 10a5.5 5.5 0 0 1-11 0C6.5 8.5 9 7 9.5 4.5 11 6 12 7.5 12 9.5c1.5-1.5 0-4.5 0-6.5z" />,
  book: <><path d="M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2z" /><path d="M4 19a2 2 0 0 1 2-2h14" /></>,
};

export function Ic({ name, size = 18, color = "currentColor", stroke = 1.5, style = {} }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, verticalAlign: "-3px", ...style }} aria-hidden="true">
      {P[name] || P.spark}
    </svg>
  );
}

export const ICON_NAMES = Object.keys(P);

// 뱁 도장 — 에디토리얼 아이덴티티의 서명. 살짝 기울여 실제 도장의 질감을 냅니다.
export const Seal = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" style={{ display: "block", flexShrink: 0 }}>
    <g transform="rotate(-7 20 20)">
      <circle cx="20" cy="20" r="17.2" fill="none" stroke={C.apricotDeep} strokeWidth="2.4" opacity="0.92" />
      <circle cx="20" cy="20" r="14.6" fill="none" stroke={C.apricotDeep} strokeWidth="0.7" opacity="0.55" />
      <text x="20" y="26.2" textAnchor="middle" fontFamily="'Noto Serif KR', serif" fontSize="16.5" fontWeight="900" fill={C.apricotDeep} opacity="0.95">뱁</text>
    </g>
  </svg>
);
