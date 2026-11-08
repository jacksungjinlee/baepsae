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
  heroAlert: "#FBF1EA",    // (v19.0b 부터 쓰지 않아요: 확인할 일 띠는 watchBg — 살구색은 데이터 표시에만)
  up: "#D6303F",           // 오름 (한국 관례) — 흰 바탕에서만
  down: "#2563EB",         // 내림 — 흰 바탕에서만
  upOnPage: "#B4232F",     // page 바탕 위 오름 숫자 (up 은 page 위 4.35:1 로 미달)
  ok: "#1F7A4D", okBg: "#E7F4EC",              // 괜찮아요
  watch: "#8A5A00", watchBg: "#FFF3D6",        // 지켜봐요 · 경고
  broken: "#FFFFFF", brokenBg: "#1C2B45",      // 규칙 깨짐
  neutral: "#3D4B63", neutralBg: "#EEF0F4",    // 큰 움직임 · 예시 · 태그
  select: "#F2F0EB",       // v19.0b: 고른 것(탭 알약 · 고른 줄 · 고른 칩) 과 아이콘 칩의 바탕. 고른 줄은 왼쪽에 3px 남색 선
};

// v19.0b (Jack, 2026-11-03): 아이콘은 Phosphor duotone 두 층(선 · 바탕)이고, 색은 이 표의 것뿐이에요 (v19.0b 네 가지 + v19.1 주제 색 다섯).
// 살구색은 아이콘에 쓰지 않아요 (살구색은 목표 비중 선 · 순위 숫자 · 팩터 점 · 그래프 속 '내 포트폴리오' 같은 데이터 표시에만).
// v19.1 Part H (Jack, 2026-11-05): 주제 색 다섯 가지를 더했어요. 선은 언제나 남색(#1C2B45)이고 바탕 층만 주제 색이에요.
// 칩 바탕도 같은 주제의 옅은 색(TOPIC_CHIP)이에요. 주제 색은 좋고 나쁨을 뜻하지 않아요. 살구색 · 가격 빨강 · 파랑은 없어요.
export const ICON_TONE = {
  on: { line: "#1C2B45", fill: "#CBD3DF" },       // 켜짐 · 기본
  off: { line: "#6B7280", fill: "#E3E6EB" },      // 꺼짐 · 보조
  ok: { line: "#1F7A4D", fill: "#CDEBD9" },       // 괜찮아요 · 할 일 없음
  onNavy: { line: "#FFFFFF", fill: "#5A6B87" },   // 남색 바탕 위
  earn: { line: "#1C2B45", fill: "#B9CDEB" },     // 주제: 실적
  value: { line: "#1C2B45", fill: "#BFE0CC" },    // 주제: 가치
  div: { line: "#1C2B45", fill: "#EBD49A" },      // 주제: 배당
  risk: { line: "#1C2B45", fill: "#D3C8EC" },     // 주제: 출렁임 · 위험
  disc: { line: "#1C2B45", fill: "#B5DDDD" },     // 주제: 공시 · 수급 · 금리 차트 등
};
export const TOPICS = ["earn", "value", "div", "risk", "disc"];
export const TOPIC_CHIP = { earn: "#EAF1FB", value: "#E9F5EE", div: "#FBF4E1", risk: "#F1EDF9", disc: "#E6F4F4" };
// v19.3e (v19.3 Part I, 보드 CoSummary2 · CoValue2 · CoDiv2, Jack 승인 보드 48판): 회사 페이지의 작은 그림(가치 눈금 · 배당 동전)과
// 요약 칸 왼쪽 띠에 쓰는 같은 주제의 진한 색(ink)과 옅은 색(light). 실적 막대와 출렁임 물결은 아래 CHART 색이에요 (Jack, 2026-11-08).
// 아이콘 색이 아니에요(아이콘은 위 ICON_TONE 만).
// 주제 색처럼 좋고 나쁨을 뜻하지 않아요. 살구색 · 가격 빨강 · 파랑 · 회사 로고 색은 없어요.
export const TOPIC_ART = {
  earn: { ink: "#6E93CF", light: "#DCE7F7" },
  value: { ink: "#4E9A72", light: "#DCEFE3" },
  div: { ink: "#C59A2E", light: "#F6EACB" },
  risk: { ink: "#8C78C6", light: "#B9C1CE" },
};
export const ICON_CHIP = { bg: COLOR.select, radius: "30%" };   // 아이콘 칩: 크기의 30% 둥글기
export const SELECTED = { background: COLOR.select };                 // 고른 칩 · 고른 카드 · 탭 알약
export const SELECTED_ROW = { background: COLOR.select, boxShadow: `inset 3px 0 0 ${COLOR.ink}` };   // 고른 줄: 왼쪽 3px 남색 선

// v19.3b Part C (Jack, 2026-11-06): 그래프에서 종목(보유 종목)은 비중이 큰 순서대로 이 남색 계열 여섯 가지로 칠해요. 일곱 번째부터는
// 가장 옅은 색을 되풀이해요. 회사 로고 · 글자 표시의 색(company.js MARK_COLORS)은 그래프를 칠하지 않아요. 가격 빨강 · 파랑은 오름 ·
// 내림에만, 주제 색은 기준과 주제에만, 살구색은 데이터 표시에만 써요.
export const HOLDING_SHADES = ["#1C2B45", "#3D4B63", "#5A6B87", "#7C889C", "#9AA3B2", "#C9D0DB"];
// v19.3e (Jack, 2026-11-08): 회사 페이지 그래프의 색. 실적 막대는 남색 · 회청색 단계(최근 해 #1C2B45, 앞선 해 #9AA3B2)로,
// 파랑은 쓰지 않아요 (한국에서 파랑은 '내림'으로 읽혀요). '이 회사'는 어느 그래프에서나 남색(출렁임 물결 포함)이에요. compare
// (회청색)는 지금 두 곳에만 써요: 출렁임 물결의 시장 선과 그 범례, 가치 탭의 '지난 2년 실제 이익' 막대. 실적 탭의 업종 중간 막대
// (HOLDING_SHADES 맨 끝)와 업종 지도의 다른 회사 점(COLOR.text3)은 예전 색 그대로예요. 둘 다 위의 색(COLOR.ink · HOLDING_SHADES
// 다섯째)을 그대로 써요.
export const CHART = { mine: COLOR.ink, compare: HOLDING_SHADES[4], latest: COLOR.ink, earlier: HOLDING_SHADES[4] };
export const holdingShade = (rank) => HOLDING_SHADES[Math.min(HOLDING_SHADES.length - 1, Math.max(0, Math.floor(Number(rank)) || 0))];
// weights: 종목마다 비중(숫자) → 같은 순서의 색. 비중이 큰 종목부터 진한 색이고, 비중이 같으면 앞에 있는 종목이 먼저예요.
// 비중이 숫자가 아니면(빈칸) 맨 뒤 순위로 봐요 (빈칸을 0 으로 바꿔 순위를 매기지 않아요: 그래도 색은 하나 받아요).
export function holdingShades(weights) {
  const w = (weights || []).map((x) => (typeof x === "number" && Number.isFinite(x) ? x : null));
  const order = w.map((x, i) => i).sort((a, b) => (w[a] == null) - (w[b] == null) || (w[b] ?? 0) - (w[a] ?? 0) || a - b);
  const out = new Array(w.length);
  order.forEach((i, rank) => { out[i] = holdingShade(rank); });
  return out;
}

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
  // v19.0b: 판정 띠의 알약(할 일 없음 · 확인할 일 · 규칙 깨짐), 확인할 일 띠(watchBg) 위의 글, 고른 것(select) 위의 글
  ["surface", "ok"], ["surface", "watch"], ["ink", "watchBg"], ["text2", "watchBg"], ["ink", "select"], ["text2", "select"],
];

// 쓰지 않는 조합 — 4.5:1 미달이라 스타일 페이지에 "쓰지 않아요"로 보여 줘요
export const AVOID_PAIRS = [["up", "page"], ["text3", "page"], ["text3", "select"]];

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
export function contrast(fg, bg) {
  const a = lum(fg), b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
