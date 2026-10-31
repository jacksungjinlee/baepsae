// ================= 뱁새 2.0 아이콘 (v18.1 Part 1) =================
// 한 벌의 선 아이콘: 24px 격자, 2px 선. 이모지는 어디에도 쓰지 않아요.
import React from "react";

const P = {
  check: <path d="M5 12.5l4.2 4.2L19 7" />,
  alert: <><path d="M12 4l9 16H3z" /><path d="M12 10v4.5" /><path d="M12 17.6v.1" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5.5" /><path d="M12 7.6v.1" /></>,
  close: <><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>,
  plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
  minus: <path d="M5 12h14" />,
  chevronRight: <path d="M9 5l7 7-7 7" />,
  chevronDown: <path d="M5 9l7 7 7-7" />,
  back: <path d="M15 5l-7 7 7 7" />,
  today: <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" /></>,
  deck: <><rect x="4" y="5" width="16" height="5" rx="1.5" /><rect x="4" y="14" width="16" height="5" rx="1.5" /></>,
  build: <><rect x="4" y="4" width="7" height="7" rx="1.5" /><rect x="13" y="4" width="7" height="7" rx="1.5" /><rect x="4" y="13" width="7" height="7" rx="1.5" /><path d="M16.5 13v7M13 16.5h7" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></>,
  calendar: <><rect x="4" y="5.5" width="16" height="14.5" rx="2" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" /></>,
  news: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 9.5h8M8 13h8M8 16.5h5" /></>,
  rule: <><path d="M6 4h9l3 3v13H6z" /><path d="M9 11h6M9 14.5h6" /></>,
  dot: <circle cx="12" cy="12" r="3.5" />,
};

export const ICON_NAMES = Object.keys(P);

export function Icon({ name, size = 24, color = "currentColor", title, style }) {
  const body = P[name];
  if (!body) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" role={title ? "img" : undefined} aria-hidden={title ? undefined : true}
      aria-label={title} style={{ flexShrink: 0, display: "block", ...style }}>
      {body}
    </svg>
  );
}
