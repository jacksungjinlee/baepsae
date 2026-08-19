// ================= 뱁새 v11 디자인 토큰 =================
// 브랜드: 먹남(Ink Navy) + 살구(Apricot), 따뜻한 오프화이트 바탕.
// 시장 관례색(상승 빨강 / 하락 파랑)은 브랜드색과 절대 섞지 않습니다.

export const C = {
  // 바탕과 글자
  bg: "#FAF8F5",        // 따뜻한 오프화이트 — 순백을 쓰지 않는 것이 브랜드입니다
  ink: "#1C2B45",       // 본문/제목 잉크 (네이비 계열의 거의-검정)
  sub: "#5C6B80",       // 보조 텍스트
  faint: "#93A0B0",     // 흐린 텍스트
  line: "#E7E1D8",      // 헤어라인 (따뜻한 회색)

  // 브랜드 축 1: 먹남 (신뢰의 앵커) — 기존 blue 계열을 대체
  blue: "#1B2B4B",      // 주 액션/헤더/핵심 수치
  blueDeep: "#12203A",  // 눌림/강조
  blueSoft: "#EBEDF3",  // 네이비 소프트 배경

  // 브랜드 축 2: 살구 (시그니처 악센트 — 화면당 한 번만)
  apricot: "#E8987A",
  apricotDeep: "#C97757",
  apricotSoft: "#FAEDE6",

  // 상태색 (채도를 낮춰 새 팔레트에 맞춤)
  teal: "#2E9E8F",  tealSoft: "#E4F4F1",   // 양호
  sand: "#C98F2B",  sandSoft: "#F8EFDC",   // 주의
  coral: "#C94F4F", coralSoft: "#F8E7E7",  // 경고/위험
  violet: "#566BB8",
  gold: "#C99A3F",

  // 시장 관례색 — 브랜드 네이비와 뚜렷이 구분되는 밝은 파랑
  up: "#D64545",        // 상승 (빨강)
  down: "#3B6FD4",      // 하락 (파랑)
};

export const FONT =
  "'Pretendard Variable', Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', -apple-system, sans-serif";

// 브랜드 순간 전용 세리프 — 로고 락업, 스테이지 타이틀, 태그라인에만 씁니다.
export const SERIF = "'Noto Serif KR', 'Apple SD Gothic Neo', serif";

// 라디우스 스케일 — 부드러운 라운드를 절제된 값으로
export const RAD = { card: 8, btn: 8, chip: 999, input: 6 };

// 헤어라인 카드: 그림자 대신 선으로 위계를 만듭니다
export const HAIR = "1px solid " + C.line;


// ---- 내비게이션 히스토리 (뒤로가기 지원) ----
export const NAV = { stack: [], installed: false };
export function navPush(undo) {
  try {
    NAV.stack.push(undo);
    history.pushState({ baepsae: NAV.stack.length }, "");
  } catch (e) {}
}
export function navInstall() {
  if (NAV.installed) return;
  NAV.installed = true;
  try {
    window.addEventListener("popstate", () => {
      const undo = NAV.stack.pop();
      if (undo) { try { undo(); } catch (e) {} }
    });
  } catch (e) {}
}
