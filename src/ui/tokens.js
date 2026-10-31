// ================= 뱁새 2.0 디자인 토큰 (v18.1 Part 1) =================
// docs/tasks/v18.1-design-system-and-copy.md 의 표 그대로예요. 값을 바꿀 때는 Jack 의 결정이 필요해요.
// 아직 기존 화면은 이 토큰을 쓰지 않아요 (Part 4 게이트: Jack 이 스타일 페이지와 문구를 승인한 뒤).

export const COLOR = {
  ink: "#1C2B45",          // 본문, 주 버튼
  text2: "#5B6576",        // 보조 글 (흰 바탕·page 바탕 모두 4.5:1 이상)
  text3: "#6B7280",        // 작은 라벨 — 흰 바탕에서만
  page: "#F5F3EF",         // 섹션 사이 바탕
  surface: "#FFFFFF",      // 섹션
  line: "#F0EDE8",         // 가는 구분선
  border: "#E8E4DE",       // 입력칸·버튼 테두리
  apricot: "#C97757",      // 강조 표시·마커만 (본문 글자에는 쓰지 않아요)
  apricotText: "#A9542F",  // 살구색 글자
  heroCalm: "#EDF4EF",     // 오늘 히어로: 할 일 없음
  heroAlert: "#FBF1EA",    // 오늘 히어로: 확인할 것
  up: "#D6303F",           // 오름 (한국 관례) — 흰 바탕에서만
  down: "#2563EB",         // 내림 — 흰 바탕에서만
  upOnPage: "#B4232F",     // page 바탕 위 오름 숫자 (up 은 page 위 4.35:1 로 미달)
  ok: "#1F7A4D", okBg: "#E7F4EC",              // 괜찮아요
  watch: "#8A5A00", watchBg: "#FFF3D6",        // 지켜봐요 · 경고
  broken: "#FFFFFF", brokenBg: "#1C2B45",      // 규칙 깨짐
  neutral: "#3D4B63", neutralBg: "#EEF0F4",    // 큰 움직임 · 예시 · 태그
};

// 상태 색은 빨강·파랑을 쓰지 않아요 (한국에서는 가격 방향을 뜻하니까요)
export const STATUS = {
  ok: { fg: COLOR.ok, bg: COLOR.okBg },
  watch: { fg: COLOR.watch, bg: COLOR.watchBg },
  broken: { fg: COLOR.broken, bg: COLOR.brokenBg },
  neutral: { fg: COLOR.neutral, bg: COLOR.neutralBg },
};

export const FONT = "'Pretendard Variable', Pretendard, -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif";
export const SIZE = { h1: 28, h2: 22, h3: 18, body: 16, sm: 15, xs: 13, xxs: 12 };
export const WEIGHT = { heavy: 800, bold: 700, semi: 600, regular: 400 };
export const SPACE = (n) => n * 4;              // 4px 격자
export const RADIUS = { sm: 12, md: 14, lg: 20 };
export const TOUCH = 44;                        // 누르는 곳은 44px 이상
export const NUM = { fontVariantNumeric: "tabular-nums" };

// 글자·바탕 대비 — 스타일 페이지와 테스트가 모두 이 목록을 검사해요 (4.5:1 이상)
export const CONTRAST_PAIRS = [
  ["ink", "surface"], ["ink", "page"], ["text2", "surface"], ["text2", "page"], ["text3", "surface"],
  ["apricotText", "surface"], ["up", "surface"], ["down", "surface"], ["upOnPage", "page"],
  ["ok", "okBg"], ["watch", "watchBg"], ["broken", "brokenBg"], ["neutral", "neutralBg"],
  ["ink", "heroCalm"], ["ink", "heroAlert"], ["text2", "heroCalm"], ["text2", "heroAlert"], ["surface", "ink"],
  ["ok", "heroCalm"], ["apricotText", "heroAlert"],
];

// 쓰지 않는 조합 — 4.5:1 미달이라 스타일 페이지에 "쓰지 않아요"로 보여 줘요
export const AVOID_PAIRS = [["up", "page"], ["text3", "page"]];

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
export function contrast(fg, bg) {
  const a = lum(fg), b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
