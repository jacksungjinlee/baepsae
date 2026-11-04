// 뱁새 2.0 이 예전 뱁새를 여는 바로가기 (v19.0c). app.html 의 ☰ 메뉴(용어 사전 · 데이터 출처) · 시장(금리·원자재 · 공시·수급) ·
// 종목(한국 회사)이 이 주소로 와요 (src/v2/routes.js 의 OLD_LINKS 와 짝). 순수 함수라서 tests/test_v2_lists.py 가 바로 돌려 봐요.
//   #macro · #disc · #corp=종목코드 (기업분석의 그 회사) · #info=glossary | #info=sources (정보 탭의 그 카드)
// 모르는 # 은 null: 예전 뱁새는 아무것도 하지 않고 주소도 그대로 둬요.
export function readDeepLink(hash) {
  const h = String(hash || "");
  let m;
  if (h === "#macro") return { tab: "macro" };
  if (h === "#disc") return { tab: "disc" };
  if ((m = /^#corp=([0-9A-Za-z]{1,12})$/.exec(h))) return { tab: "corp", corp: m[1] };
  if ((m = /^#info=(glossary|sources)$/.exec(h))) return { tab: "info", info: m[1] };
  return null;
}
