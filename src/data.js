// ================= 데이터 파일 읽기 (v17.5) =================
// 여섯 군데(첫 화면 검색 · 포트폴리오 · 기업분석 · 기업분석의 공시 · 공시·수급 · 금리·원자재)가 모두 이걸 써요.
// 실패하면 { ok:false } 를 돌려주고, 화면은 '불러오지 못했어요'를 보여줘요.
// 빈 결과나 내장 예시 데이터를 실제 시세처럼 보여주지 않기 위해서예요.

// JSON 에 NaN·Infinity 가 끼면 브라우저는 파일 전체를 거부해요. 따옴표 밖에 있는 것만 null 로 고쳐요
// (미국 기업 설명 글에는 'NaN' 같은 낱말이 들어갈 수 있어서 따옴표 안은 건드리지 않아요).
export function repairJsonText(s) {
  const parts = [];
  let last = 0, n = 0, inStr = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s.charCodeAt(i);
    if (inStr) {
      if (ch === 92) { i++; continue; }          // \ 다음 글자는 건너뜀
      if (ch === 34) inStr = false;              // "
      continue;
    }
    if (ch === 34) { inStr = true; continue; }
    let len = 0;
    if (ch === 78 && s.startsWith("NaN", i)) len = 3;
    else if (ch === 73 && s.startsWith("Infinity", i)) len = 8;
    else if (ch === 45 && s.startsWith("-Infinity", i)) len = 9;
    if (len) {
      parts.push(s.slice(last, i), "null");
      i += len - 1; last = i + 1; n++;
    }
  }
  parts.push(s.slice(last));
  return { text: parts.join(""), n };
}

function gcEvent(name) {
  try { window.goatcounter && window.goatcounter.count({ path: "evt-" + name, title: name, event: true }); } catch (e) {}
}

export async function loadJson(path, check) {
  try {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) return { ok: false, data: null, error: "HTTP " + r.status };
    const raw = await r.text();
    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      const fixed = repairJsonText(raw);
      if (!fixed.n) throw e;
      data = JSON.parse(fixed.text);
      console.warn("[뱁새] " + path + ": NaN·Infinity " + fixed.n + "개를 null 로 고쳐서 읽었어요");
      gcEvent("data-repair");
    }
    if (check && !check(data)) return { ok: false, data: null, error: "형식이 예상과 달라요" };
    return { ok: true, data, error: null };
  } catch (e) {
    return { ok: false, data: null, error: String((e && e.message) || e) };
  }
}

// ---- 날짜 (화면에는 실행일이 아니라 내용의 날짜를 보여줘요) ----
export const STALE_DAYS = 4;   // 발행(publishedAt) 뒤 이만큼 지나면 '갱신이 멈췄어요'. 주말·연휴에는 조용해요.
const MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function mdOf(iso, lang) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!m) return null;
  const mo = Number(m[2]), d = Number(m[3]);
  return lang === "en" ? MON_EN[mo - 1] + " " + d : mo + "월 " + d + "일";
}

export function daysSince(ts, now) {
  const t = Date.parse(ts || "");
  if (isNaN(t)) return null;
  return Math.floor(((now == null ? Date.now() : now) - t) / 86400000);
}

// { md: "10월 30일", stale: bool, days } — 표시 문구는 detail.jsx 의 DateBadge 가 만들어요
export function freshness(contentDate, publishedAt, lang, now) {
  const days = daysSince(publishedAt, now);
  return { md: mdOf(contentDate, lang), days, stale: days != null && days > STALE_DAYS };
}
