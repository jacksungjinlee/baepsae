// ================= 뱁새 2.0 디자인 토큰 (v18.1 Part 1 · v19.6d 어두운 화면) =================
// docs/tasks/v18.1-design-system-and-copy.md 의 표 그대로예요. 값을 바꿀 때는 Jack 의 결정이 필요해요.
//
// v19.6d (docs/tasks/v19.6-records-alerts-dark.md Part D): 색마다 밝은 값과 어두운 값 두 가지가 있어요. 밝은 값은 예전 표
// 그대로이고, 어두운 값은 Part D 의 표예요 (표에 없는 것은 보드 Home2Dark · BuildCards2Dark · CoSummary2Dark · HomeMovers2Dark
// 의 색, 보드에도 없으면 대비를 맞춰 고른 값이고 줄마다 적어 두었어요).
// 화면은 이 값(#…)을 직접 쓰지 않고 아래의 COLOR · TOPIC_CHIP · HOLDING_SHADES … 를 써요. 그 값은 CSS 변수
// "var(--bs-이름, 밝은 값)" 이고, 페이지(app.html)가 변수를 두 번 정해요 (themeCss: :root 에 밝은 값, 어두운 화면에 어두운 값).
// 그래서 토큰을 쓰는 모든 스타일은 다시 그리지 않아도 화면 모드를 따라가요. 지금 있는 화면도, 앞으로 만들 화면도
// (COLOR.ink 같은 토큰만 쓰면) 어두운 화면이 저절로 돼요. 변수가 없는 곳(스타일 페이지)에서는 밝은 값이 그대로 나와요.
// PALETTE.light / PALETTE.dark 는 같은 값을 #… 로 가진 표예요 (대비 검사 · 스타일 페이지 · 빌드가 써요).

const LIGHT = {}, DARK = {};
// name: CSS 변수 이름(--bs-name). 두 표에 값을 넣고, 화면이 쓸 토큰 값을 돌려줘요.
function tok(name, light, dark) {
  if (name in LIGHT) throw new Error("token twice: " + name);
  LIGHT[name] = light;
  DARK[name] = dark;
  return `var(--bs-${name}, ${light})`;
}
const table = (rows) => Object.fromEntries(Object.entries(rows).map(([k, [l, d]]) => [k, tok(k, l, d)]));

export const COLOR = table({
  ink: ["#1C2B45", "#E8ECF2"],          // 본문 글 · 선 · 그래프의 '이 회사' (어두운 화면: 밝은 글)
  // v19.6d: ink 는 글이기도 하고 바탕이기도 했어요. 바탕으로 쓰는 남색(주 버튼 · 홈의 남색 띠 · 고른 칩 · 번호 동그라미)은 primary,
  // 그 위의 글은 onPrimary 예요. 밝은 화면에서는 예전과 같은 색이에요.
  primary: ["#1C2B45", "#31456B"],      // 남색 바탕
  onPrimary: ["#FFFFFF", "#FFFFFF"],    // 남색 바탕 위 글 (예전에는 surface 를 글자로 썼어요)
  onPrimary2: ["#E3E7EE", "#E3E7EE"],   // 남색 바탕 위 둘째 글 (홈 규칙 칸 이름 · 깨진 규칙 줄). 보드의 #C3CCD9 는 깨진 칸 위에서 3.9:1 이라 밝은 값 그대로
  onPrimary3: ["#CBD3DF", "#CBD3DF"],   // 남색 바탕 위 작은 글 (점검 날짜 · 확인하지 못했어요). 보드의 #AEB9C9 는 규칙 칸 위에서 3.8:1 이라 밝은 값 그대로
  text2: ["#5B6576", "#9BA6B7"],        // 보조 글 (흰 바탕·page 바탕 모두 4.5:1 이상)
  text3: ["#6B7280", "#8E99AA"],        // 작은 라벨 — 흰 바탕에서만
  page: ["#F5F3EF", "#10151E"],         // 섹션 사이 바탕
  surface: ["#FFFFFF", "#1A2231"],      // 섹션
  line: ["#F0EDE8", "#2A3446"],         // 가는 구분선
  border: ["#E8E4DE", "#3A4558"],       // 입력칸·버튼 테두리
  edge: ["#D9D4CC", "#3A4558"],         // v19.6d: 빈 칸의 테두리 (계량기 빈 칸 · 안내 단계 점) — 보드 #D9D4CC → #3A4558
  edgeStrong: ["#C9C2B8", "#465267"],   // v19.6d: 더 진한 빈 테두리 (기준 카드의 −/+ · 점검표의 빈 점) — 보드 #C9C2B8 → #465267
  chipEdge: ["#E3DED6", "#334055"],     // v19.6d: 종목 순위의 고르지 않은 칩 테두리 (보드 HomeMovers2Dark)
  winEdge: ["#ECE8E1", "#2A3446"],      // v19.6d: 종목 순위 목록 창의 테두리 (보드)
  track: ["#ECE8E1", "#232C3C"],        // v19.6d: 한국 · 미국 고르기의 바탕 (보드)
  apricot: ["#C97757", "#E08E6A"],      // 강조 표시·마커만 (본문 글자에는 쓰지 않아요)
  apricotText: ["#A9542F", "#F0A27F"],  // 살구색 글자
  heroCalm: ["#EDF4EF", "#1C3328"],     // 오늘 히어로: 할 일 없음
  heroAlert: ["#FBF1EA", "#3A3018"],    // (v19.0b 부터 쓰지 않아요: 확인할 일 띠는 watchBg — 살구색은 데이터 표시에만) 어두운 값은 [Q14] watchBg
  up: ["#D6303F", "#FF6B75"],           // 오름 (한국 관례) — 흰 바탕에서만
  down: ["#2563EB", "#7AA2FF"],         // 내림 — 흰 바탕에서만
  upOnPage: ["#B4232F", "#FF6B75"],     // page 바탕 위 오름 숫자 (up 은 page 위 4.35:1 로 미달)
  ok: ["#1F7A4D", "#6FD39F"], okBg: ["#E7F4EC", "#1C3328"],              // 괜찮아요
  watch: ["#8A5A00", "#F1C25B"], watchBg: ["#FFF3D6", "#3A3018"],        // 지켜봐요 · 경고
  broken: ["#FFFFFF", "#FFFFFF"], brokenBg: ["#1C2B45", "#31456B"],      // 규칙 깨짐
  neutral: ["#3D4B63", "#C3CCD9"], neutralBg: ["#EEF0F4", "#232C3C"],    // 큰 움직임 · 예시 · 태그
  select: ["#F2F0EB", "#232C3C"],       // v19.0b: 고른 것(탭 알약 · 고른 줄 · 고른 칩) 과 아이콘 칩의 바탕. 고른 줄은 왼쪽에 3px 남색 선
  highlight: ["#FFE2A8", "#FFE2A8"],    // v19.6d: 남색 위 따뜻한 강조 (홈 깨진 규칙의 숫자) · 처음 안내의 밝은 테두리. 살구색 아님
  highlightBg: ["#FFE2A8", "#5A4718"],  // v19.6d: 홈 깨진 규칙 칸의 '!' 동그라미 — 보드 #FFE2A8 → #5A4718
});

// v19.6d: 덮개와 그림자. 밝은 화면은 예전 남색 반투명 그대로, 어두운 화면은 검정으로 더 짙게 (남색 덮개는 어두운 page 위에서
// 시트와 page 를 구별하지 못해요). 대비 검사에는 들어가지 않아요 (#… 가 아니라서 PALETTE 에 있지만 CONTRAST_PAIRS 에 없어요).
export const OVERLAY = table({
  scrim: ["rgba(28,43,69,0.45)", "rgba(0,0,0,0.6)"],       // 아래에서 올라오는 시트 뒤
  guide: ["rgba(28,43,69,0.55)", "rgba(0,0,0,0.62)"],      // 처음 안내의 어두운 부분 (보드: 남색 55%)
  shadow: ["rgba(28,43,69,0.10)", "rgba(0,0,0,0.4)"],      // 아래 고정 막대의 그림자
  pop: ["rgba(28,43,69,0.35)", "rgba(0,0,0,0.55)"],        // 처음 안내 말풍선의 그림자
  lift: ["rgba(0,0,0,0.25)", "rgba(0,0,0,0.4)"],           // 처음부터 만들기 카드의 그림 다섯 장
});

// v19.0b (Jack, 2026-11-03): 아이콘은 Phosphor duotone 두 층(선 · 바탕)이고, 색은 이 표의 것뿐이에요 (v19.0b 네 가지 + v19.1 주제 색 다섯).
// 살구색은 아이콘에 쓰지 않아요 (살구색은 목표 비중 선 · 순위 숫자 · 팩터 점 · 그래프 속 '내 포트폴리오' 같은 데이터 표시에만).
// v19.1 Part H (Jack, 2026-11-05): 주제 색 다섯 가지를 더했어요. 선은 언제나 남색(#1C2B45)이고 바탕 층만 주제 색이에요.
// 칩 바탕도 같은 주제의 옅은 색(TOPIC_CHIP)이에요. 주제 색은 좋고 나쁨을 뜻하지 않아요. 살구색 · 가격 빨강 · 파랑은 없어요.
// ICON_TONE 은 밝은 화면의 표이고 아이콘의 두 층(path)에 그대로 그려요. v19.6d: 어두운 화면에서는 ICON_TONE_DARK (Part D) 가
// 같은 두 층을 덮어 칠해요 (themeCss 의 svg[data-tone] 규칙. CSS 규칙은 SVG 의 fill 속성보다 앞서요).
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
// v19.6d Part D: 어두운 화면의 아이콘. 선은 밝게(#E8ECF2), 바탕 층은 더 진한 주제 색 (선과 바탕 5.7–7.6:1).
export const ICON_TONE_DARK = {
  on: { line: "#E8ECF2", fill: "#4A5872" },
  off: { line: "#8E99AA", fill: "#2E384A" },
  ok: { line: "#6FD39F", fill: "#2E5A44" },
  onNavy: { line: "#FFFFFF", fill: "#4A5F87" },
  earn: { line: "#E8ECF2", fill: "#3B5480" },
  value: { line: "#E8ECF2", fill: "#2F6047" },
  div: { line: "#E8ECF2", fill: "#6B5A2A" },
  risk: { line: "#E8ECF2", fill: "#4C4275" },
  disc: { line: "#E8ECF2", fill: "#2C6464" },
};
for (const t of Object.keys(ICON_TONE)) {
  tok(`icon-${t}-line`, ICON_TONE[t].line, ICON_TONE_DARK[t].line);
  tok(`icon-${t}-fill`, ICON_TONE[t].fill, ICON_TONE_DARK[t].fill);
}
export const TOPICS = ["earn", "value", "div", "risk", "disc"];
// 칩 바탕 (Part D: 어두운 화면은 진한 주제 색)
export const TOPIC_CHIP = {
  earn: tok("chip-earn", "#EAF1FB", "#1D2B43"),
  value: tok("chip-value", "#E9F5EE", "#1C3328"),
  div: tok("chip-div", "#FBF4E1", "#362E1D"),
  risk: tok("chip-risk", "#F1EDF9", "#2A2541"),
  disc: tok("chip-disc", "#E6F4F4", "#1B3535"),
};
// v19.3e (v19.3 Part I, 보드 CoSummary2 · CoValue2 · CoDiv2, Jack 승인 보드 48판): 회사 페이지의 작은 그림(가치 눈금 · 배당 동전)과
// 요약 칸 왼쪽 띠(company.jsx)에 쓰는 같은 주제의 진한 색(ink)과 옅은 색(light). 실적 막대와 출렁임 물결은 아래 CHART 색이에요.
// 실적은 진한 색이 없어요 (Jack, 2026-11-08: 데이터 막대 · 선에는 파랑을 쓰지 않고, 주제 색은 띠 · 칩 · 아이콘 바탕에만): 실적 칸의
// 왼쪽 띠는 실적의 옅은 주제 색(#B9CDEB, ICON_TONE.earn 바탕)이고 light 는 칩 바탕색(TOPIC_CHIP.earn)이에요.
// 아이콘 색이 아니에요(아이콘은 위 ICON_TONE 만). 주제 색처럼 좋고 나쁨을 뜻하지 않아요. 살구색 · 가격 빨강 · 파랑 · 회사 로고 색은
// 없어요.
// v19.6d: 진한 색(띠 · 동전 테두리)은 어두운 화면에서도 같아요 (보드 CoSummary2Dark 가 그대로 둬요). 옅은 색은 보드대로: 가치 눈금의
// 옅은 초록은 #24493A, 동전의 옅은 금색은 보드처럼 그대로(밝은 동전), 실적은 칩 바탕의 어두운 값.
export const TOPIC_ART = {
  earn: { ink: tok("art-earn-ink", ICON_TONE.earn.fill, ICON_TONE.earn.fill), light: tok("art-earn-light", "#EAF1FB", "#1D2B43") },
  value: { ink: tok("art-value-ink", "#4E9A72", "#4E9A72"), light: tok("art-value-light", "#DCEFE3", "#24493A") },
  div: { ink: tok("art-div-ink", "#C59A2E", "#C59A2E"), light: tok("art-div-light", "#F6EACB", "#F6EACB") },
  risk: { ink: tok("art-risk-ink", "#8C78C6", "#8C78C6"), light: tok("art-risk-light", "#B9C1CE", "#B9C1CE") },
};
export const ICON_CHIP = { bg: COLOR.select, radius: "30%" };   // 아이콘 칩: 크기의 30% 둥글기
export const SELECTED = { background: COLOR.select };                 // 고른 칩 · 고른 카드 · 탭 알약
export const SELECTED_ROW = { background: COLOR.select, boxShadow: `inset 3px 0 0 ${COLOR.ink}` };   // 고른 줄: 왼쪽 3px 남색 선

// v19.3c Part D: 기준의 점수 점 (기준마다 다섯 개)은 그 기준 주제의 진한 색, 빈 점은 테두리 색(COLOR.border)이에요. 주제 색처럼
// 어느 기준인지만 말하고 좋고 나쁨은 말하지 않아요. v19.6d: 어두운 화면에서도 같은 색 (보드 BuildCards2Dark). plain 은 주제가 없는
// 점(시작 화면의 점 설명).
export const TOPIC_DOT = {
  value: tok("dot-value", "#4E9A72", "#4E9A72"),
  div: tok("dot-div", "#C59A2E", "#C59A2E"),
  earn: tok("dot-earn", "#6E93CF", "#6E93CF"),
  risk: tok("dot-risk", "#8C78C6", "#8C78C6"),
  disc: tok("dot-disc", "#3E9A9A", "#3E9A9A"),
  plain: tok("dot-plain", "#7C889C", "#7C889C"),
  none: tok("dot-none", "#5A6B87", "#9BA6B7"),       // a 기준 without a topic (none today)
};

// v19.3b Part C (Jack, 2026-11-06): 그래프에서 종목(보유 종목)은 비중이 큰 순서대로 이 남색 계열 여섯 가지로 칠해요. 일곱 번째부터는
// 가장 옅은 색을 되풀이해요. 회사 로고 · 글자 표시의 색(company.js MARK_COLORS)은 그래프를 칠하지 않아요. 가격 빨강 · 파랑은 오름 ·
// 내림에만, 주제 색은 기준과 주제에만, 살구색은 데이터 표시에만 써요.
// v19.6d Part D: 어두운 화면은 거꾸로 (가장 큰 종목이 가장 밝아요).
const SHADES_DARK = ["#E8ECF2", "#C3CCD9", "#9BA6B7", "#7C889C", "#5A6B87", "#3D4B63"];
export const HOLDING_SHADES = ["#1C2B45", "#3D4B63", "#5A6B87", "#7C889C", "#9AA3B2", "#C9D0DB"].map((c, i) => tok(`shade-${i}`, c, SHADES_DARK[i]));
// 그 칸 위의 글자 색 (점검표의 업종 지도): surface · ink · 검정 중 4.5:1 이 넘는 첫 색, 화면 모드마다 따로 골라요.
const firstReadable = (shade, P) => [P.surface, P.ink, "#000000"].find((c) => contrast(c, shade) >= 4.5) || "#000000";
export const HOLDING_TEXT = HOLDING_SHADES.map((v, i) => tok(`shade-text-${i}`, firstReadable(LIGHT[`shade-${i}`], LIGHT), firstReadable(DARK[`shade-${i}`], DARK)));
export const holdingShade = (rank) => HOLDING_SHADES[Math.min(HOLDING_SHADES.length - 1, Math.max(0, Math.floor(Number(rank)) || 0))];
export const holdingText = (shade) => HOLDING_TEXT[HOLDING_SHADES.indexOf(shade)] || COLOR.ink;
// weights: 종목마다 비중(숫자) → 같은 순서의 색. 비중이 큰 종목부터 진한 색이고, 비중이 같으면 앞에 있는 종목이 먼저예요.
// 비중이 숫자가 아니면(빈칸) 맨 뒤 순위로 봐요 (빈칸을 0 으로 바꿔 순위를 매기지 않아요: 그래도 색은 하나 받아요).
export function holdingShades(weights) {
  const w = (weights || []).map((x) => (typeof x === "number" && Number.isFinite(x) ? x : null));
  const order = w.map((x, i) => i).sort((a, b) => (w[a] == null) - (w[b] == null) || (w[b] ?? 0) - (w[a] ?? 0) || a - b);
  const out = new Array(w.length);
  order.forEach((i, rank) => { out[i] = holdingShade(rank); });
  return out;
}
// v19.3e (Jack, 2026-11-08): 회사 페이지 그래프의 색. 실적 막대는 남색 · 회청색 단계(최근 해 #1C2B45, 앞선 해 #9AA3B2)로,
// 파랑은 쓰지 않아요 (한국에서 파랑은 '내림'으로 읽혀요). '이 회사'는 어느 그래프에서나 남색(출렁임 물결 포함)이에요. compare
// (회청색)는 지금 두 곳에만 써요: 출렁임 물결의 시장 선과 그 범례, 가치 탭의 '지난 2년 실제 이익' 막대. 실적 탭의 업종 중간 막대
// (HOLDING_SHADES 맨 끝)와 업종 지도의 다른 회사 점(COLOR.text3)은 예전 색 그대로예요.
// v19.6d: 어두운 화면에서 '이 회사'는 밝은 글색(ink), 비교는 보드의 #6F7B8E (어두운 카드 위 3.5:1). scaleMid · scaleEnd 는 가치 눈금의
// 회색 쪽 (보드 CoSummary2Dark), mineEst 는 점검표 '2022년 같은 해라면' 의 내 포트폴리오 막대.
export const CHART = {
  mine: COLOR.ink, latest: COLOR.ink,
  compare: tok("chart-compare", "#9AA3B2", "#6F7B8E"),
  scaleMid: tok("chart-scale-mid", "#E3E7EE", "#2B3548"),
  scaleEnd: tok("chart-scale-end", "#B9C1CE", "#B9C1CE"),
  mineEst: tok("chart-mine-est", "#5A6B87", "#9BA6B7"),
};
CHART.earlier = CHART.compare;

// 상태 색은 빨강·파랑을 쓰지 않아요 (한국에서는 가격 방향을 뜻하니까요)
export const STATUS = {
  ok: { fg: COLOR.ok, bg: COLOR.okBg },
  watch: { fg: COLOR.watch, bg: COLOR.watchBg },
  broken: { fg: COLOR.broken, bg: COLOR.brokenBg },
  neutral: { fg: COLOR.neutral, bg: COLOR.neutralBg },
};

// v19.6d: 뱁이 그림(baepi-* 파일 모두, baepi-mark 포함)은 어두운 화면에서 이 밝은 칩 위에 앉아요. 그림은 다시 칠하거나 뒤집지 않아요
// (CLAUDE.md). 밝은 화면에는 칩이 없어요 (themeCss 의 img[src*="baepi-"] 규칙).
export const MASCOT_CHIP = "#F5F3EF";

// 두 화면 모드의 모든 값 (--bs-이름 → 색). PALETTE.light 는 예전 값 그대로예요.
export const PALETTE = { light: LIGHT, dark: DARK };
// 토큰 하나("var(--bs-이름, …)")의 그 화면 모드 값 (#…). 토큰이 아니면 그대로 돌려줘요 (검사 · 스타일 페이지).
export const tokenName = (t) => (String(t).match(/^var\(--bs-([\w-]+),/) || [])[1] || null;
export const valueOf = (t, mode = "light") => { const n = tokenName(t); return n ? PALETTE[mode][n] : t; };
// 화면 모드마다 브라우저 위쪽 막대의 색 (theme-color): page 와 같아요.
export const THEME_COLOR = { light: LIGHT.page, dark: DARK.page };

export const FONT = "'Pretendard Variable', Pretendard, -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif";
export const SIZE = { h1: 28, h2: 22, h3: 18, body: 16, sm: 15, xs: 13, xxs: 12 };
export const WEIGHT = { heavy: 800, bold: 700, semi: 600, regular: 400 };
export const SPACE = (n) => n * 4;              // 4px 격자
export const RADIUS = { sm: 12, md: 14, lg: 20 };
export const TOUCH = 44;                        // 누르는 곳은 44px 이상
export const NUM = { fontVariantNumeric: "tabular-nums" };

// 글자·바탕 대비 — 스타일 페이지와 테스트가 모두 이 목록을 검사해요 (4.5:1 이상). v19.6d: 두 화면 모드 모두.
export const CONTRAST_PAIRS = [
  ["ink", "surface"], ["ink", "page"], ["text2", "surface"], ["text2", "page"], ["text3", "surface"],
  ["apricotText", "surface"], ["up", "surface"], ["down", "surface"], ["upOnPage", "page"],
  ["ok", "okBg"], ["watch", "watchBg"], ["broken", "brokenBg"], ["neutral", "neutralBg"],
  ["ink", "heroCalm"], ["ink", "heroAlert"], ["text2", "heroCalm"], ["text2", "heroAlert"], ["surface", "ink"],
  ["ok", "heroCalm"], ["apricotText", "heroAlert"],
  // v19.0b: 판정 띠의 알약(할 일 없음 · 확인할 일 · 규칙 깨짐), 확인할 일 띠(watchBg) 위의 글, 고른 것(select) 위의 글
  ["surface", "ok"], ["surface", "watch"], ["ink", "watchBg"], ["text2", "watchBg"], ["ink", "select"], ["text2", "select"],
  // v19.6d: 남색 바탕(primary) 위의 글, 홈 깨진 규칙 칸의 '!' (규칙 칸의 반투명 바탕 위 글은 tests/test_v196d_dark.py 가 따로 봐요)
  ["onPrimary", "primary"], ["onPrimary2", "primary"], ["onPrimary3", "primary"], ["highlight", "primary"], ["watch", "highlightBg"],
];

// 쓰지 않는 조합 — 4.5:1 미달이라 스타일 페이지에 "쓰지 않아요"로 보여 줘요 (밝은 화면에서 잰 값)
export const AVOID_PAIRS = [["up", "page"], ["text3", "page"], ["text3", "select"]];
// v19.6d: 밝은 화면에서는 괜찮지만 어두운 화면에서 4.5:1 이 안 되는 조합. 한 코드가 두 화면을 그리니 두 목록 모두 쓰지 않아요.
// (흰 글자를 초록 · 노랑 알약 위에: 알약의 글은 surface. 남색 바탕색을 글자로: 글은 ink. text2 를 border 바탕 위에.)
export const AVOID_PAIRS_DARK = [["onPrimary", "ok"], ["onPrimary", "watch"], ["primary", "surface"], ["primary", "page"], ["text2", "border"]];

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
export function contrast(fg, bg) {
  const a = lum(fg), b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

// ---------------- v19.6d: the page's colour sheet (build-app.sh puts it in app.html's <style>) ----------------
// :root carries the light values; [data-theme="dark"] (set by the head script, src/v2/theme.js) the dark ones. If the head
// script never ran (no data-theme), the device setting decides (prefers-color-scheme), so 자동 still works. color-scheme
// follows, so the browser's own parts (scroll bars, form controls) match. Icons: the two layers of every Phosphor icon
// take their tone's colour from a rule (it outranks the SVG fill attributes, which keep the light values). 뱁이 pictures
// sit on a light chip in dark mode only. Placeholder text in fields: the browser's own grey reads 3.5:1 on the dark surface,
// so in dark mode it takes text3 (5.5:1); the light screen keeps the browser's grey as before.
const decl = (p) => Object.entries(p).map(([k, v]) => `--bs-${k}:${v}`).join(";");
export function themeCss() {
  const dark = `${decl(DARK)};color-scheme:dark`;
  const icons = Object.keys(ICON_TONE).map((t) => `svg[data-tone="${t}"]>[data-layer="fill"]{fill:var(--bs-icon-${t}-fill)}`
    + `svg[data-tone="${t}"]>[data-layer="line"]{fill:var(--bs-icon-${t}-line)}`).join("");
  const darkOnly = (root) => `${root} img[src*="baepi-"]{background:${MASCOT_CHIP};border-radius:22%;padding:4px}`
    + `${root} img[src*="baepi-mark"]{border-radius:50%;padding:2px}`
    + `${root} ::placeholder{color:var(--bs-text3);opacity:1}`;
  return `:root{${decl(LIGHT)};color-scheme:light}:root[data-theme="dark"]{${dark}}`
    + `@media (prefers-color-scheme: dark){:root:not([data-theme]){${dark}}${darkOnly(":root:not([data-theme])")}}`
    + icons + darkOnly(':root[data-theme="dark"]');
}
