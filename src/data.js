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

// ---- 오늘 데이터(data.json)와 앱 내장 목록 합치기 ----
// 금현물을 KRX 에서 못 받아 국제 금값으로 환산했을 때: KRX 가격처럼 보이지 않게 이름부터 바꿔요
export const EST_NAME = { ko: "금현물 · 국제 금값 환산", en: "Gold · converted from world price" };
export function mergeStocks(base, live) {
  if (!live) return base.map((b) => ({ ...b, live: false }));
  // 미국 티커는 표기가 갈려요(BRK.B / BRK-B). 점·하이픈을 무시하고 맞춰봅니다.
  const norm = (x) => String(x || "").toUpperCase().replace(/[.\-]/g, "");
  const byT = Object.fromEntries(base.map((s) => [s.t, s]));
  const byNorm = {};
  base.forEach((s) => { byNorm[norm(s.t)] = s; });
  const out = [], skipped = [];
  const keep = (x) => (x != null ? x : null);   // 빈 칸은 빈 칸으로 (0 으로 바꾸지 않음)
  live.forEach((L) => {
    const b = byT[L.t] || byNorm[norm(L.t)];
    if (b) {
      // v17.5: 오늘 데이터의 값만 써요. 빈 칸(적자라 PER 없음 등)은 '–'로 두고, 2025 내장 값을 섞지 않아요.
      // 베타·변동성은 계산에 꼭 필요해서 비었으면 내장 값을 쓰되, 그 종목은 '실시간 아님'으로 표시해요.
      const partial = L.price == null || L.beta == null || L.vol == null;
      const v = (k) => (L[k] != null ? L[k] : null);
      out.push({ ...b, price: L.price != null ? L.price : b.price, beta: L.beta != null ? L.beta : b.beta,
        vol: L.vol != null ? L.vol : b.vol, per: v("per"), pbr: v("pbr"), dy: v("dy"), al: v("al"),
        sh: L.sh, mdd: L.mdd, hit: L.hit, mom: L.mom, cap: L.cap, val: L.val,
        pz: L.pz, vz: L.vz, mz: L.mz, qz: L.qz,
        x: { ...(b.x || {}), roe: v("roe"), debt: v("debt"), opm: v("opm"), g3: v("g3"), frn: v("frn"),
             mcap: v("cap"), lo: v("lo"), hi: v("hi") },
        ...(L.est ? { nk: EST_NAME.ko, ne: EST_NAME.en, est: true } : {}),
        live: !L.est && !partial });
      delete byT[b.t]; delete byNorm[norm(b.t)];
    } else {
      // 내장 목록에 없는 종목 (v17.5 리뷰): 가격·베타·변동성이 모두 있어야 포트폴리오에 담을 수 있어요.
      // 위험 계산에 꼭 필요한 값이라, 지어낸 기본값(베타 1 · 변동성 30)을 넣지 않고 목록에서 뺍니다 (기업분석에는 그대로 있어요).
      // PER·PBR·배당·알파·시총 같은 빈 칸은 0 이 아니라 비워 두고 화면에 '–'로 보여요.
      if (!(L.price > 0) || L.beta == null || L.vol == null) { skipped.push(L.t); return; }
      out.push({ t: L.t, nk: L.nk || L.t, ne: L.ne || L.t, s: L.s || "index", cls: L.cls || "kr",
        ccy: L.ccy, fxu: !!L.fxu, price: L.price, beta: L.beta, vol: L.vol,
        per: keep(L.per), pbr: keep(L.pbr), dy: keep(L.dy), al: keep(L.al),
        cap: keep(L.cap), val: keep(L.val), sh: L.sh, mdd: L.mdd, hit: L.hit, mom: L.mom,
        pz: L.pz, vz: L.vz, mz: L.mz, qz: L.qz, live: !L.est, auto: true,
        x: { dk: L.dk, de: L.de, roe: L.roe, debt: L.debt, opm: L.opm, g3: L.g3, frn: L.frn,
             mcap: L.cap, lo: L.lo, hi: L.hi } });
    }
  });
  if (skipped.length) {
    console.warn("[뱁새] 가격·베타·변동성 중 빈 값이 있어 포트폴리오 목록에서 뺀 종목 " + skipped.length + "개: "
      + skipped.slice(0, 20).join(", ") + (skipped.length > 20 ? " …" : ""));
  }
  Object.values(byT).forEach((b) => out.push({ ...b, live: false }));   // 오늘 데이터에 없는 내장 종목 = 예시 가격
  return out;
}
