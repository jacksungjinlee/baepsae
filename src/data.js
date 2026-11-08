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

// v19.1c (Jack, 2026-11-07): data.json 의 staleAfter = 다음 발행이 와 있어야 하는 시각 (한국 시간 ISO, 예정일의 마지막 정해진
// 실행 + 2시간 · 주말·휴장일은 파이프라인이 이미 셌어요). 시각과 시간대가 다 적힌 값만 읽어요 ("2026-11-10" 같은 날짜만 있는 값은
// 브라우저가 UTC 자정으로 읽어서 받지 않아요). 못 읽으면 null → 예전 규칙(STALE_DAYS)만 써요.
const STALE_AT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
export function staleAfterTime(v) {
  if (typeof v !== "string" || !STALE_AT.test(v)) return null;
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : null;
}

// 한국 날짜(YYYY-MM-DD) — 기기의 시간대와 상관없이 (한국은 서머타임이 없어서 +9시간이면 돼요). 날짜 사이의 날 수도 한국 달력으로.
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
export const kstDate = (t) => new Date(t + 9 * 3600000).toISOString().slice(0, 10);
const dayNo = (iso) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))) / 86400000;
export const kstDaysBetween = (fromIso, toIso) => Math.round(dayNo(toIso) - dayNo(fromIso));

// { md: "10월 30일", stale: bool, days } — 표시 문구는 detail.jsx 의 DateBadge 와 2.0 의 DateLine 이 만들어요.
// stale: staleAfter 가 지났거나(v19.1c), 발행 뒤 STALE_DAYS 일이 지났을 때. 4일 규칙은 staleAfter 가 있어도 그대로 둬요
// (Jack 확인, 2026-11-07): staleAfter 가 잘못 먼 날로 적혀도 경고가 예전보다 늦게 뜨는 일은 없어요.
// days = 경고 문구의 n. staleAfter 가 지났고 nextPub(발행 예정일, YYYY-MM-DD)이 있으면 그 예정일 아침부터 센 날 (Jack, 2026-11-07):
// n = 예정일부터 오늘까지 한국 달력의 날 수 + 1 (예정일 = 1일째 · 최소 1) — 이때 due: true 가 붙어요. 토요일 발행을 화요일에 놓치면
// 화요일 16:48 에 n = 1 ('갱신이 늦어지고 있어요'), 수요일에 2. 그 밖에는(예전 파일 · nextPub 없음 · 4일 규칙만 걸림) 지금처럼
// 발행 뒤 지난 날 수 (내림). 문구는 staleWordsLate 를 봐요.
// 날 수는 줄지 않아요: 4일 규칙의 경고가 staleAfter 보다 먼저 떴으면(긴 연휴처럼 예정일이 먼 때, backstopFirst) staleAfter 가 지난
// 뒤에도 두 셈 중 큰 쪽을 써요. '6일째 갱신이 멈췄어요'가 '갱신이 늦어지고 있어요'로 되돌아가는 일은 없어요. staleAfter 가 먼저
// 지났으면 예정일부터 센 날 그대로예요 (토요일 발행을 놓치면 목요일에 3, 그 아침 4일 규칙이 걸려도).
export function freshness(contentDate, publishedAt, lang, now, staleAfter, nextPub) {
  const t = now == null ? Date.now() : now;
  const sincePub = daysSince(publishedAt, t);
  const at = staleAfterTime(staleAfter);
  const late = at != null && t > at;
  const stale = late || (sincePub != null && sincePub > STALE_DAYS);
  if (late && typeof nextPub === "string" && ISO_DATE.test(nextPub)) {
    const fromDue = Math.max(1, kstDaysBetween(nextPub, kstDate(t)) + 1);
    const keep = backstopFirst(publishedAt, staleAfter) && sincePub != null;
    return { md: mdOf(contentDate, lang), days: keep ? Math.max(fromDue, sincePub) : fromDue, stale, due: true };
  }
  return { md: mdOf(contentDate, lang), days: sincePub, stale };
}

// 4일 규칙의 경고(발행 뒤 STALE_DAYS 일 넘게)가 staleAfter 가 지나기 전에 이미 떴는지: 발행 시각 + (STALE_DAYS + 1)일 ≤ staleAfter.
// 그랬다면 화면은 그때부터 발행 뒤 날 수를 보여 왔으니, staleAfter 뒤에도 그 날 수보다 작은 n 으로 바꾸지 않아요 (freshness ·
// 2.0 홈 띠 rules.js dayState). 둘 중 하나라도 읽을 수 없으면 false.
export function backstopFirst(publishedAt, staleAfter) {
  const p = Date.parse(publishedAt || "");
  const at = staleAfterTime(staleAfter);
  return Number.isFinite(p) && at != null && p + (STALE_DAYS + 1) * 86400000 <= at;
}

// v19.1c: 늦음 판단에 쓰는 data.json 의 두 칸을 읽을 수 없을 때 크게 남겨요 (조용한 대체 없음). 돌려줌: 남긴 경고 수.
// staleAfter 가 없거나 못 읽으면 발행 뒤 4일 규칙만 쓰고, staleAfter 는 읽는데 nextPub 이 없거나 날짜가 아니면 n 을 발행 뒤 날 수로 세요.
export function warnStaleFields(j, where) {
  const sa = j && j.staleAfter, np = j && j.nextPub;
  if (sa == null) { console.warn("[뱁새] " + where + ": data.json 에 staleAfter 가 없어요 · 늦음 경고는 발행 뒤 " + STALE_DAYS + "일 규칙만 써요"); return 1; }
  if (staleAfterTime(sa) == null) {
    console.warn("[뱁새] " + where + ": data.json 의 staleAfter " + JSON.stringify(sa) + " 를 읽을 수 없어요 · 늦음 경고는 발행 뒤 " + STALE_DAYS + "일 규칙만 써요");
    return 1;
  }
  if (!(typeof np === "string" && ISO_DATE.test(np))) {
    console.warn("[뱁새] " + where + ": data.json 의 nextPub " + (np == null ? "이 없어요" : JSON.stringify(np) + " 이 날짜가 아니에요")
      + " · staleAfter 가 지나면 늦음 경고의 n 은 예정일이 아니라 발행 뒤 날 수로 세요");
    return 1;
  }
  return 0;
}

// v19.1c: 예전 뱁새의 기업분석 · 첫 화면 성적표는 corp.json 의 날짜를 보여요. corp.json 에는 staleAfter · nextPub 이 없어서, data.json
// 과 같은 발행(publishedAt 이 같은 시각)일 때만 data.json 의 것을 빌려 써요. 다른 발행이면 예전 4일 규칙 (console 에 남겨요).
// data.json 의 발행 정보는 한 번 받아 두고, corp.json 이 다른 발행이면 다시 받아요 (포트폴리오가 받은 data.json 도 같이 써요).
let DATA_PUB = null, DATA_PUB_PENDING = null;
const pubOf = (j) => ({ publishedAt: (j && j.publishedAt) || null, staleAfter: j && j.staleAfter != null ? j.staleAfter : null,
  nextPub: j && j.nextPub != null ? j.nextPub : null });
export function samePublish(a, b) {
  const x = Date.parse(a || ""), y = Date.parse(b || "");
  return Number.isFinite(x) && x === y;
}
export function rememberDataPublish(j) { DATA_PUB = pubOf(j); }
export async function loadDataPublishFor(corpPublishedAt) {
  if (DATA_PUB && samePublish(DATA_PUB.publishedAt, corpPublishedAt)) return DATA_PUB;
  if (!DATA_PUB_PENDING) {
    DATA_PUB_PENDING = loadJson("./data.json", (j) => !!j && typeof j === "object" && !Array.isArray(j)).then((r) => {
      DATA_PUB_PENDING = null;
      if (!r.ok) {
        console.warn("[뱁새] data.json: " + r.error + " · 기업분석 · 첫 화면 성적표의 늦음 경고는 발행 뒤 " + STALE_DAYS + "일 규칙만 써요");
        return null;
      }
      warnStaleFields(r.data, "기업분석 · 첫 화면 성적표");
      DATA_PUB = pubOf(r.data);
      return DATA_PUB;
    });
  }
  return DATA_PUB_PENDING;
}
// corp.json 의 날짜 표시(DateBadge)에 넘길 staleAfter · nextPub. pub: loadDataPublishFor 의 결과 (null 이면 받는 중이거나 못 받음 ·
// 못 받은 건 그쪽에서 남겨요). 같은 발행이 아니면 null 둘 (4일 규칙)이고 그 이유를 남겨요.
export function corpStaleArgs(corpPublishedAt, pub, where) {
  const none = { staleAfter: null, nextPub: null };
  if (!pub) return none;
  if (!samePublish(corpPublishedAt, pub.publishedAt)) {
    console.warn("[뱁새] " + where + ": corp.json(" + corpPublishedAt + ")과 data.json(" + pub.publishedAt + ")의 발행이 달라 늦음 경고는 발행 뒤 "
      + STALE_DAYS + "일 규칙만 써요");
    return none;
  }
  return { staleAfter: pub.staleAfter, nextPub: pub.nextPub };
}

// v19.1c: 열어 둔 화면이 '늦음'을 놓치지 않게 다시 볼 시각 (데이터를 다시 받지는 않아요). 아침에 열어 둔 앱도 staleAfter(예정일 16:47)가
// 지나면 경고가 떠야 해요. → 지금부터 freshness 가 바뀔 수 있는 가장 이른 때까지 남은 ms: staleAfter 바로 뒤, 각 발행 시각
// (publishedAts) 에서 날 수가 하나 느는 때 (4일 규칙 · 예전 n), 그리고 staleAfter 가 있으면 다음 한국 자정 (예정일부터 센 n).
// 1초 여유를 두고, 길어도 FRESH_RECHECK_MAX_MS (1시간) 마다 다시 봐요.
// 읽을 수 있는 시각이 하나도 없으면 null (그때는 화면이 다시 보일 때만 다시 봐요).
const DAY_MS = 86400000;
export const FRESH_RECHECK_MAX_MS = 3600000;
export function nextFreshChange(now, publishedAts, staleAfter) {
  const t = now == null ? Date.now() : now;
  const at = [];
  const due = staleAfterTime(staleAfter);
  if (due != null && due >= t) at.push(due + 1000);
  if (due != null) at.push(Date.parse(kstDate(t) + "T00:00:00+09:00") + DAY_MS + 1000);
  for (const p of publishedAts || []) {
    const pt = Date.parse(p || "");
    if (Number.isFinite(pt)) at.push(pt + (Math.floor((t - pt) / DAY_MS) + 1) * DAY_MS + 1000);
  }
  if (!at.length) return null;
  return Math.max(1000, Math.min(FRESH_RECHECK_MAX_MS, Math.min(...at) - t));
}

// 멈춤 문구 (Jack, 2026-11-07 디자인 채팅): n ≤ 1 (예정일 당일, 또는 예전 셈으로 발행 뒤 하루 이내)은 '갱신이 늦어지고 있어요',
// 2부터는 예전 그대로 '{n}일째 갱신이 멈췄어요'. n 을 모르면(발행 시각을 읽을 수 없음) 날 수를 말할 수 없어서 '늦어지고 있어요'.
export const STALE_LATE_MAX_DAYS = 1;
export const staleWordsLate = (days) => days == null || days <= STALE_LATE_MAX_DAYS;

// ---- 미국 종목의 자기 가격 날짜 (v19.1c, Jack 2026-11-07) ----
// data.json 의 미국 종목 pxd = 그 종목의 마지막 종가 날짜. 미국 기준일(usPxDate)의 봉이 없는 종목에만 있고, 그때 d1 은 없어요.
// 가격은 숨기지 않고 그 날짜를 보여 주며, 그 종목이 들어간 목록·합계에는 짧은 안내를 붙여요. 시장 구분(cls)이 아니라 pxd 가
// 있는지로만 봐요 (379800 KODEX 미국S&P500 은 cls 가 us 지만 한국거래소 가격이에요).
// ownCloseDate: 읽을 수 있는 날짜(YYYY-MM-DD)이고 기준일과 다를 때만 그 날짜, 아니면 null.
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
export function ownCloseDate(s, marketDate) {
  const d = s && s.pxd;
  return typeof d === "string" && ISO_DAY.test(d) && d !== marketDate ? d : null;
}
// 화면에 나온 종목들 → [{ date, ts }]: 날짜마다 한 묶음, 새 날짜 먼저, 묶음 안은 화면 순서, 같은 종목은 한 번만. 오늘 데이터에
// 없는 종목(null)이나 자기 날짜가 없는 종목은 빠져요. 이름은 티커(t) — 미국 종목만 pxd 가 있어요.
export function ownCloseGroups(stocks, marketDate) {
  const by = new Map(), seen = new Set();
  for (const s of stocks || []) {
    if (!s || s.t == null || s.t === "") continue;
    const t = String(s.t);
    const d = ownCloseDate(s, marketDate);
    if (!d || seen.has(t)) continue;
    seen.add(t);
    if (!by.has(d)) by.set(d, []);
    by.get(d).push(t);
  }
  return [...by.entries()].sort((a, b) => (a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0)).map(([date, ts]) => ({ date, ts }));
}
// 그 종목 가격의 날짜: pxd 가 없으면 기준일(marketDate), 읽을 수 있는 pxd 면 그 날짜, pxd 가 기준일과 같으면 기준일, 읽을 수 없는
// pxd 면 null (기준일이 아닌 건 아는데 언제인지 몰라요: 틀린 날짜를 보이느니 날짜를 빼요).
export function stockPriceDate(s, marketDate) {
  const md = typeof marketDate === "string" && ISO_DAY.test(marketDate) ? marketDate : null;
  if (!s || s.pxd == null) return md;
  return ownCloseDate(s, marketDate) || (s.pxd === marketDate ? md : null);
}
// 불러올 때 남기는 기록: 자기 날짜가 있는 종목(own: [[t, 날짜]]) · pxd 가 기준일과 같은 종목(same: [t], 가격은 기준일 것이라 그대로) ·
// pxd 를 읽을 수 없는 종목(bad: [t] — 날짜를 말할 수 없어서 화면에 날짜 없이, 오늘 변화도 없이 나가요. 관문이 막는 경우라 여기 오면
// 크게 알려요).
export function ownCloseReport(stocks, marketDate) {
  const own = [], same = [], bad = [];
  for (const s of stocks || []) {
    if (!s || s.pxd == null) continue;
    const d = ownCloseDate(s, marketDate);
    if (d) own.push([String(s.t), d]);
    else if (s.pxd === marketDate) same.push(String(s.t));
    else bad.push(String(s.t));
  }
  return { own, same, bad };
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
  let noRiskN = 0;
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
             mcap: v("cap"), lo: v("lo"), hi: v("hi"), g3Q: (L.cls || b.cls) === "us", g3Kr: (L.cls || b.cls) === "kr" },   // 미국 g3 = 최근 분기 · 1년 전 대비
        ...(L.est ? { nk: EST_NAME.ko, ne: EST_NAME.en, est: true } : {}),
        ...(L.pxd != null ? { pxd: L.pxd } : {}),   // v19.1c: 미국 종목의 자기 가격 날짜 (그 종목이 들어간 화면이 안내해요)
        live: !L.est && !partial });
      delete byT[b.t]; delete byNorm[norm(b.t)];
    } else {
      // 내장 목록에 없는 종목 (v17.5 리뷰): 지어낸 기본값(베타 1 · 변동성 30 · PER 0 …)을 넣지 않아요.
      // · 가격이 없으면 담을 수 없어 목록에서 빼요 (크게 기록).
      // · 베타·변동성이 없으면 목록에는 두되(이미 담은 종목이 사라지지 않게) noRisk 로 표시해요.
      //   화면에는 β·σ 를 '–'로, 위험 계산에서는 빼요(그 비중은 위험 계산에서 현금처럼). 담고 있으면 배너로 알려요.
      // · PER·PBR·배당·알파·시총 같은 빈 칸은 0 이 아니라 비워 두고 화면에 '–'로 보여요.
      if (!(L.price > 0)) { skipped.push(L.t); return; }
      const noRisk = L.beta == null || L.vol == null;
      if (noRisk) noRiskN += 1;
      out.push({ t: L.t, nk: L.nk || L.t, ne: L.ne || L.t, s: L.s || "index", cls: L.cls || "kr",
        ccy: L.ccy, fxu: !!L.fxu, price: L.price, beta: noRisk ? null : L.beta, vol: noRisk ? null : L.vol,
        ...(noRisk ? { noRisk: true } : {}),
        per: keep(L.per), pbr: keep(L.pbr), dy: keep(L.dy), al: keep(L.al),
        cap: keep(L.cap), val: keep(L.val), sh: L.sh, mdd: L.mdd, hit: L.hit, mom: L.mom,
        pz: L.pz, vz: L.vz, mz: L.mz, qz: L.qz, live: !L.est, auto: true,
        ...(L.pxd != null ? { pxd: L.pxd } : {}),   // v19.1c: 위와 같아요
        x: { dk: L.dk, de: L.de, roe: L.roe, debt: L.debt, opm: L.opm, g3: L.g3, frn: L.frn,
             mcap: L.cap, lo: L.lo, hi: L.hi, g3Q: L.cls === "us", g3Kr: L.cls === "kr" } });
    }
  });
  if (skipped.length) {
    console.warn("[뱁새] 가격이 없어 포트폴리오 목록에서 뺀 종목 " + skipped.length + "개: "
      + skipped.slice(0, 20).join(", ") + (skipped.length > 20 ? " …" : ""));
  }
  if (noRiskN) console.warn("[뱁새] 베타·변동성이 없어 위험 계산에서 빼는 종목 " + noRiskN + "개 (목록에는 있어요)");
  Object.values(byT).forEach((b) => out.push({ ...b, live: false }));   // 오늘 데이터에 없는 내장 종목 = 예시 가격
  return out;
}

// ---- 한국 매출 성장(g3)이 어떻게 계산됐는지 (Jack, 2026-11-05: '3년'이라고 부르지 않아요) ----
// 파이프라인(fetch_data.py parse_dart_list): 당기 · 전전기 매출이 둘 다 0 보다 크면 최근 2년 연평균 ((당기 ÷ 전전기)^0.5 − 1),
// 아니면 (전전기 매출이 없거나 0 이하, 또는 당기 매출이 0 이하) 당기가 0 이 아니고 전기가 0 보다 클 때 최근 1년 (당기 ÷ 전기 − 1).
// corp.json 의 매출(rev, [당기, 전기, 전전기], 억원, 0.1 단위로 반올림)과 g3(0.1 단위)로 거꾸로 맞춰 봐요.
// 2.0 의 src/v2/engine.js growthBasis 와 같은 규칙이에요. 예전 뱁새는 2.0 코드를 가져오지 않아서 여기 따로 두고 (2.0 이 이걸
// 가져다 쓰도록 합치는 건 이 PR 밖이에요), tests/test_app_data.py 가 둘이 같은지 봐요.
// "y2" (최근 2년 연평균) · "y1" (최근 1년) · null (알 수 없음: 이름표 없이 숨겨요).
const REV_HALF = 0.05, G3_HALF = 0.05;
export function krGrowthBasis(g3, rev) {
  const g = typeof g3 === "number" && Number.isFinite(g3) ? g3 : null;
  if (g == null || !Array.isArray(rev)) return null;
  const r = [0, 1, 2].map((i) => (typeof rev[i] === "number" && Number.isFinite(rev[i]) ? rev[i] : null));
  const has = (i) => r[i] != null;
  const lo = (i) => r[i] - REV_HALF, hi = (i) => r[i] + REV_HALF;
  const pos = (x) => Math.max(x, 1e-9);
  const sure2 = has(0) && has(2) && lo(0) > 0 && lo(2) > 0;
  const may2 = has(0) && has(2) && hi(0) > 0 && hi(2) > 0;
  const may1 = !sure2 && has(0) && has(1) && hi(1) > 0;
  const range2 = may2 ? [(Math.sqrt(pos(lo(0)) / hi(2)) - 1) * 100, lo(2) > 0 ? (Math.sqrt(hi(0) / lo(2)) - 1) * 100 : Infinity] : null;
  let range1 = null;
  if (may1) {
    if (lo(1) > 0) {
      const c = [lo(0), hi(0)].flatMap((a) => [lo(1), hi(1)].map((b) => (a / b - 1) * 100));
      range1 = [Math.min(...c), Math.max(...c)];
    } else range1 = [-Infinity, Infinity];
  }
  const fits = (rg) => !!rg && rg[0] <= g + G3_HALF + 1e-9 && rg[1] >= g - G3_HALF - 1e-9;
  const in2 = fits(range2), in1 = fits(range1);
  return in2 && !in1 ? "y2" : in1 && !in2 ? "y1" : null;
}

// ---- 한국 매출 성장 문장 (Jack, 2026-11-05) ----
// 줄어든 경우 '감소했어요' · '줄었어요' · 'shrank' 옆에 마이너스 부호를 붙이지 않아요: 숫자는 절댓값이에요.
// 보이는 숫자(소수 한 자리로 반올림, 부호 없이)가 0.0 이면 늘었다고도 줄었다고도 하지 않고 '거의 변하지 않았어요' ·
// 'was flat' 이라고 써요 (Jack, 2026-11-05). 0.04 → 0.0 → 그대로, 0.05 → 0.1 → 늘었어요 (자바스크립트 toFixed 반올림).
// 계산 기준을 모르면 null: 문장을 빼요.
const g3Shown = (g3) => Math.abs(g3).toFixed(1);
// 성적표(검색 결과 카드)의 한 줄. 숫자는 소수 한 자리까지 (g3 는 원래 0.1 단위라 보이는 숫자는 예전 그대로예요: 13.5, 3), 늘었으면 '+'.
export function krGrowthScoreLine(g3, rev, en) {
  const basis = krGrowthBasis(g3, rev);
  if (!basis) return null;
  const two = basis === "y2", n = Number(g3Shown(g3));
  if (n === 0) return en ? `Revenue was flat over the last ${two ? "2 years" : "year"}.` : `매출은 최근 ${two ? "2년" : "1년"} 동안 거의 변하지 않았어요.`;
  const up = g3 > 0, x = (up ? "+" : "") + n;
  if (en) return two ? `Revenue ${up ? "grew" : "shrank"} ${x}% a year over the last 2 years.` : `Revenue ${up ? "grew" : "shrank"} ${x}% over the last year.`;
  return two ? `매출은 최근 2년간 연평균 ${x}% ${up ? "성장했어요" : "감소했어요"}.` : `매출은 최근 1년간 ${x}% ${up ? "성장했어요" : "감소했어요"}.`;
}
// 기업분석 리버스 DCF 의 문장 (줄표 없이 두 문장, 부호 없는 숫자, 소수 한 자리). 1년짜리에는 '연평균'이 없어요.
export function krGrowthDcfLine(g3, rev) {
  const basis = krGrowthBasis(g3, rev);
  if (!basis) return null;
  const x = g3Shown(g3);
  const what = Number(x) === 0 ? "거의 변하지 않았어요" : `${basis === "y2" ? "연평균 " : ""}${x}% ${g3 < 0 ? "줄었어요" : "늘었어요"}`;
  return `이 회사 매출은 최근 ${basis === "y2" ? "2년" : "1년"} 동안 ${what}. 지금 주가가 가정하는 성장률과 비교해 보세요.`;
}

// ---- 기업분석 리버스 DCF 의 첫 문장 (Jack, 2026-11-05) ----
// 카드의 '성장률이 5년에 걸쳐 영구성장률로 수렴' 칸이 켜져 있으면(기본) 2.0 의 '지금 가격이 가정하는 것'과 같은 계산이에요
// (corp.jsx reverseDcf: 첫해 증가율이 5년에 걸쳐 영구성장률로 바뀌고, 첫해 범위는 −30% ~ +60%). 그래서 그때는 2.0 의 승인된
// 문장(src/copy/v2.js co.dcf.headUp · headDown · high · low · note)을 글자 그대로 써요. 칸을 끄면 5년 내내 같은 증가율이라
// '첫해' 문장이 맞지 않아요: 카드가 예전 문장을 그대로 보여요 (corp.jsx DcfCard).
// 예전 뱁새는 2.0 코드를 가져오지 않아서 여기 따로 두고, tests/test_oldapp_dcf_wording.py 가 2.0 과 같은지 봐요.
// 숫자도 2.0 처럼: 첫해 증가율을 소수 한 자리로 반올림한 뒤 0 이상(0, −0 포함)이면 '는다는', 0보다 작으면 '준다는' 에 빼기 없이.
// 첫 문장(head)에는 2.0 처럼 마침표가 없어요: 카드에서 한 줄을 따로 차지해요.
const REV_DCF = {
  headUp: "지금 주가에는 이익이 첫해 {g}% 는다는 가정이 담겨 있어요",
  headDown: "지금 주가에는 이익이 첫해 {g}% 준다는 가정이 담겨 있어요",
  high: "지금 주가가 맞으려면 이익이 첫해 60% 넘게 늘어야 해요.",
  low: "지금 주가는 이익이 첫해 30% 넘게 준다고 가정해도 설명되지 않을 만큼 낮아요. 모형 밖의 이유(부채, 소송, 지배구조 등)가 있을 수 있어요.",
  note: "예측이 아니라 지금 가격을 거꾸로 읽은 숫자예요. 증가율은 5년에 걸쳐 {t}%까지 바뀐다고 놓고 계산했어요.",
};
// 첫 문장 아래 2.0 의 설명 줄 (co.dcf.note): 2.0 카드처럼 영구성장률({t})을 이 줄에 보여요 (예전 첫 문장의 '(이후 2%)' 대신).
// {t} 는 2.0 cotabs pctNum 그대로: 2 → "2", 2.5 → "2.5". 숫자가 아니면 null.
export function krRevDcfNote(term) {
  if (typeof term !== "number" || !Number.isFinite(term)) return null;
  return REV_DCF.note.replace("{t}", term.toLocaleString("ko-KR", { minimumFractionDigits: term % 1 ? 1 : 0, maximumFractionDigits: term % 1 ? 1 : 0 }));
}
// rev: reverseDcf 의 결과 ({ g } · { edge: "high" | "low" }). 문장을 만들 수 없으면 null.
export function krRevDcfText(rev) {
  if (!rev) return null;
  if (rev.edge === "high") return REV_DCF.high;
  if (rev.edge === "low") return REV_DCF.low;
  if (typeof rev.g !== "number" || !Number.isFinite(rev.g)) return null;
  const g = Math.round(rev.g * 10) / 10;                                           // 2.0 cotabs: round(r.g, 1)
  const x = (Math.round(Math.abs(g) * 10) / 10).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });   // 2.0 p1
  return (g < 0 ? REV_DCF.headDown : REV_DCF.headUp).replace("{g}", x);
}

// corp.json 을 한 번만 받아요 (검색 칸의 성적표와 포트폴리오의 한국 매출성장 이름표가 같이 써요. 기업분석 탭은 따로 받아요). 받는 중이면 그 요청을 같이 기다리고,
// 못 받으면 { failed: true } (실패는 기억하지 않아요: 다음에 다시 받아요).
let CORP_DATA = null, CORP_PENDING = null;
export async function loadCorpOnce() {
  if (CORP_DATA) return CORP_DATA;
  if (!CORP_PENDING) {
    CORP_PENDING = loadJson("./corp.json", (d) => d && Array.isArray(d.companies) && d.companies.length > 0).then((r) => {
      CORP_PENDING = null;
      if (!r.ok) return { failed: true, companies: [], sectors: {} };
      CORP_DATA = r.data;
      return CORP_DATA;
    });
  }
  return CORP_PENDING;
}
