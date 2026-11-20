// ================= 내 기준 상위 {x}%: one number per stock (v19.7 Part D [B3]) =================
// THE one function (spec [B3]) is v19.5b's ranks.js criteriaPct. v19.7a carried a word-for-word copy here while its base had no
// ranks.js; v19.5b is merged, so this file is now that function itself (v19.7b): the 담기 sheet, 내 기준으로 찾기, 두 종목 비교 and
// 홈's 내 기준 list read one function. tests/test_v197a_edit.py still checks it gives v19.5b's numbers. Pure; no Korean here.
export { criteriaPct } from "./ranks.js";
