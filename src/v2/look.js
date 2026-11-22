// ================= 2.0: 오늘 볼 것 cards (v19.6b, docs/tasks/v19.6-records-alerts-dark.md Part B.2, board Today2) =================
// What the 오늘 볼 것 page (#home/today, todaylook.jsx) and 홈's 오늘 볼 것 list show beside the v19.3e rows: pure functions, no
// React and no Korean text (the words come from src/copy/v2.js C.look; the role words below are read from it too).
// Unit tests: tests/test_v196b_cards.py (run through Node).
//
// Stocks covered (Part B.2): every stock held in any portfolio (more than 0 shares today: held.js heldQty) and every 관심 종목.
// The 유상증자 · 전환사채 · 신주인수권부사채 cards only for stocks actually held ([Q3]: their lines talk about the user's own stake).
// Everything here needs fresh data (rules.dayState ok, the rule of 홈's daily check and of the 관심 종목 rows): on stale, late or
// failed data there is no card (홈 shows its stale band or the load-failure message). The disc.json cards also need today's
// filing list (home.filingsChecked: loaded and current); otherwise none of them, and 홈 shows the 공시 tab's failure message or
// its date line, as before (Jack, 2026-11-08: never rows from a list that stopped).
//
//   issue    disc.json issue, held stocks, filed (d) within the last ISSUE_DAYS days (KST today included), newest first. Left out:
//            a withdrawal (wd), a decision marked 확인했어요 (store.js isSeen: the same stock, kind and numbers on the same filing
//            or board date; a correction with other numbers shows again), and the shapes the approved lines do not cover yet
//            (issueBody null: a 유무상증자 (bonus), a 기타주식 issue (cls other), one that issues both classes (n2 · p2), or a rights
//            issue whose method is neither 주주배정 nor 제3자배정 · 일반공모): the PR asks Jack for their wording (#145's notes for
//            this PR); the console names them. A filing whose numbers are not read (pend) or blank gets the 숫자를 읽지 못했어요
//            line. When the day's 주요사항 list failed (issueOk false) there is no issue card and the page says the list did not
//            load (issueFail); a file without the section at all (from before #145) has none, said in the console.
//   insider  disc.json insider, held and watched stocks, filed within the last INSIDER_DAYS days, |q| × today's official close at
//            least INSIDER_MIN_WON (1억원; disc.json amt used that run's price, so the amount is recomputed). Title by role
//            (임원 · 주요주주; someone who is both, or a row without a role, waits for Jack's title: left out, said in the
//            console); the body names the position (pos, blank: 임원·주요주주) with 이/가 by its last syllable.
//            NOT ON YET: the screens do not read the role field (ROLE_OF null below), so no insider card shows (title "none",
//            said in the console). #145's test tests/test_v196b_answers.py test_the_role_field_is_not_read_by_either_app_yet pins
//            that no screen reads it; changing that test needs Jack's yes (CLAUDE.md). With his yes: set ROLE_OF to the function
//            that returns the row's role field, and let that test allow this one read in look.js.
//   nps      disc.json nps, held and watched stocks, filed within the last NPS_DAYS days: "{a}%에서 {b}%로" with b = rt and
//            a = rt − chg, one decimal; left out when chg is blank or a and b round to the same number.
//   dates    US 실적 발표 (data.json ed, Yahoo's confirmed date) and 배당락일 (xd) of held and watched US stocks from today to
//            today + DATE_DAYS (KST; the dates are US local dates, said under the rows), earliest first, at most DATES_MAX.
//            No Korean dates ([Q15]: no reliable source); when a Korean stock is held the card says they are not shown yet.
import { C } from "./format.js";
import { num } from "./engine.js";
import { heldQty } from "./held.js";
import { watchOf, isSeen } from "./store.js";
import { dayState } from "./rules.js";
import { filingsChecked, holdsKorean } from "./home.js";
import { discDate } from "./company.js";

export const ISSUE_DAYS = 30;
export const INSIDER_DAYS = 7;
export const NPS_DAYS = 7;
export const DATE_DAYS = 7;
export const DATES_MAX = 5;
export const INSIDER_MIN_WON = 1e8;
// How lookModel reads an insider row's role (see the top of this file): null = not read yet, so the insider cards stay off.
export const ROLE_OF = null;

const ymdOf = (d) => (typeof d === "string" && /^\d{8}$/.test(d) ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : null);
const isIso = (x) => typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x) && !Number.isNaN(Date.parse(x + "T00:00:00Z"))
  && new Date(x + "T00:00:00Z").toISOString().slice(0, 10) === x;
const dayNum = (iso) => Date.parse(iso + "T00:00:00Z") / 86400000;
export const addDays = (iso, n) => new Date(Date.parse(iso + "T00:00:00Z") + n * 86400000).toISOString().slice(0, 10);
// a filing date within the last `days` days, today (KST) included, never after today
export const within = (iso, today, days) => isIso(iso) && isIso(today) && iso <= today && dayNum(today) - dayNum(iso) < days;
const desc = (a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : String(a.rc || a.t) < String(b.rc || b.t) ? 1 : -1);
const pos = (x) => typeof x === "number" && Number.isFinite(x) && x > 0;

// The role words disc.json writes (fetch_data INSIDER_ROLES): 임원 · 주요주주 · and, for someone who is both, Jack's "임원·주요주주"
// (2026-11-19, 7c), which is also the spec's word for a blank position (C.look.posAny). The two single roles are its two halves.
export function roleWords() {
  const both = C.look && C.look.posAny;
  const [exec, major] = typeof both === "string" ? both.split("·") : [];
  return { both: both || null, exec: exec || null, major: major || null };
}

// Which stocks the cards cover. decks: store.data.decks (the in-memory view) · data: store.data.
export function coverage(decks, data) {
  const held = new Set();
  for (const d of decks || []) if (d) for (const t of heldQty(d).keys()) held.add(t);
  const watched = new Set(Object.keys(watchOf(data)));
  return { held, watched, all: new Set([...held, ...watched]) };
}
// A Korean stock among the covered ones (held: home.holdsKorean; watched: its market in today's data, else a 6-digit code).
export function coversKorean(decks, data, byT = null) {
  if (holdsKorean(decks, byT)) return true;
  for (const t of Object.keys(watchOf(data))) {
    const s = byT && typeof byT.get === "function" ? byT.get(t) : null;
    if (s ? s.cls === "kr" : /^\d{6}$/.test(t)) return true;
  }
  return false;
}

// ---------------- 유상증자 · 전환사채 · 신주인수권부사채 ----------------
// The approved body a row reads with: "holders" · "others" (rights), "cb", "bw", "unread" (the numbers are not read: the
// fallback line), or null when the approved lines do not cover its shape yet (see the top of this file).
export function issueBody(r) {
  if (!r || typeof r !== "object") return null;
  if (r.kind === "rights") {
    if (r.bonus === true || r.cls === "other" || r.n2 != null || r.p2 != null) return null;
    if (r.pend === true || !pos(r.n) || !pos(r.p)) return "unread";
    return r.how === "holders" || r.how === "others" ? r.how : null;
  }
  if (r.kind === "cb" || r.kind === "bw") return r.pend === true || !pos(r.amt) || !pos(r.p) ? "unread" : r.kind;
  return null;
}
// disc: app.jsx's { status, data } · held: Set · today: KST YYYY-MM-DD · data: store.data (the 확인했어요 marks).
// -> { cards: [{ rc, t, nk, kind, date, body, n, p, amt, bd, cor }], skipped: [{ t, rc, why }], fail, missing }
export function issueCards(disc, held, today, data) {
  const out = { cards: [], skipped: [], fail: false, missing: false };
  if (!disc || !disc.data) return out;
  const d = disc.data;
  if (!Array.isArray(d.issue)) { out.missing = d.issue === undefined; out.fail = !out.missing; return out; }
  if (d.issueOk !== true) { out.fail = true; return out; }
  for (const r of d.issue) {
    if (!r || typeof r !== "object" || !held.has(r.t) || r.wd === true) continue;
    const date = ymdOf(r.d);
    if (!within(date, today, ISSUE_DAYS)) continue;
    const body = issueBody(r);
    if (!body) {
      out.skipped.push({ t: r.t, rc: r.rc, why: r.bonus === true ? "bonus: a rights and bonus issue" : r.cls === "other" ? "cls other: a non-common class"
        : r.n2 != null || r.p2 != null ? "both classes (n2 · p2)" : `method ${JSON.stringify(r.how)}` });
      continue;
    }
    if (isSeen(data, r)) continue;
    out.cards.push({ rc: r.rc, t: r.t, nk: r.nk, kind: r.kind, date, body, n: pos(r.n) ? r.n : null, p: pos(r.p) ? r.p : null,
      amt: pos(r.amt) ? r.amt : null, bd: typeof r.bd === "string" ? r.bd : null, cor: r.cor === true });
  }
  out.cards.sort(desc);
  return out;
}

// ---------------- 임원 · 주요주주 지분 변동 ----------------
// byT: today's data rows. roleOf: reads a row's role (lookModel passes ROLE_OF; null: not read, every title "none").
// -> { cards: [{ rc, t, nk, date, role, title ("exec" | "major" | "both" | "none"), pos, q, won, up, s }], skipped }
export function insiderCards(disc, cover, today, byT, roleOf = null) {
  const out = { cards: [], skipped: [] };
  if (!disc || !disc.data || !Array.isArray(disc.data.insider)) return out;
  const R = roleWords();
  for (const x of disc.data.insider) {
    if (!x || typeof x !== "object" || !cover.all.has(x.t) || !Number.isInteger(x.q) || x.q === 0) continue;
    const date = ymdOf(x.d);
    if (!within(date, today, INSIDER_DAYS)) continue;
    const s = byT && byT.get(x.t);
    const px = s ? num(s.price) : null;
    if (!(px > 0)) { out.skipped.push({ t: x.t, rc: x.rc, why: "no official close in today's data" }); continue; }
    const won = Math.abs(x.q) * px;
    if (won < INSIDER_MIN_WON) continue;
    const r0 = roleOf ? roleOf(x) : null;
    const role = typeof r0 === "string" ? r0 : null;
    const title = !roleOf ? "none" : role != null && role === R.exec ? "exec" : role != null && role === R.major ? "major" : "both";
    if (role != null && role !== R.exec && role !== R.major && role !== R.both) out.skipped.push({ t: x.t, rc: x.rc, why: `role ${JSON.stringify(role)} is not one of the three` });
    const p = typeof x.pos === "string" ? x.pos.trim() : "";
    out.cards.push({ rc: x.rc, t: x.t, nk: (s && s.nk) || x.nk || x.t, date, role, title, pos: p && p !== "-" ? p : null, q: x.q, won, up: x.q > 0, s });
  }
  out.cards.sort(desc);
  return out;
}

// ---------------- 국민연금 ----------------
const r1 = (x) => Math.round(x * 10) / 10;
export function npsCards(disc, cover, today, byT) {
  const out = [];
  if (!disc || !disc.data || !Array.isArray(disc.data.nps)) return out;
  for (const x of disc.data.nps) {
    if (!x || typeof x !== "object" || !cover.all.has(x.t)) continue;
    const date = ymdOf(x.d);
    const rt = num(x.rt), chg = num(x.chg);
    if (!within(date, today, NPS_DAYS) || rt == null || chg == null) continue;
    const a = r1(rt - chg), b = r1(rt);
    if (a === b) continue;
    const s = byT && byT.get(x.t);
    out.push({ t: x.t, nk: (s && s.nk) || x.nk || x.t, date, a, b, up: b > a, rc: null });
  }
  return out.sort(desc);
}

// ---------------- 다가오는 일정 ----------------
// -> [{ t, nk, date, kind: "earn" | "xd", s }] (US local dates), earliest first, then 실적 발표 before 배당락일, at most DATES_MAX.
export function dateRows(byT, cover, today) {
  const out = [];
  if (!isIso(today)) return out;
  const end = addDays(today, DATE_DAYS);
  for (const t of cover.all) {
    const s = byT && byT.get(t);
    if (!s || s.cls !== "us") continue;
    for (const [kind, f] of [["earn", "ed"], ["xd", "xd"]]) {
      const v = s[f];
      if (isIso(v) && v >= today && v <= end) out.push({ t, nk: s.nk || t, date: v, kind, s });
    }
  }
  out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.kind !== b.kind ? (a.kind === "earn" ? -1 : 1) : a.t < b.t ? -1 : 1));
  return out.slice(0, DATES_MAX);
}

// ---------------- everything for one screen ----------------
// load: the data · store: { data } (the in-memory view) · disc: app.jsx's · today: KST · now (tests).
// -> { fresh, kr, krHeld, ds, issue, insider, nps, dates, noKr, issueFail, discFail, discOld, any, skipped }
//   ds: the filings state (home2.jsx discState): skip (no Korean stock covered) · wait · ok · stale · fail · none.
//   any: a card of any kind (an insider card whose title waits for Jack is counted here; todaylook.jsx pageHas leaves it out).
export function lookModel(load, store, disc, today, now) {
  const empty = { fresh: false, kr: false, krHeld: false, ds: "skip", issue: [], insider: [], nps: [], dates: [], noKr: false,
    issueFail: false, discFail: false, discOld: null, any: false, skipped: [], missing: false };
  if (!load || load.status !== "ok" || !dayState(load, now).ok) return empty;
  const data = store && store.data;
  const decks = (data && data.decks) || [];
  const cover = coverage(decks, data);
  const kr = coversKorean(decks, data, load.byT), krHeld = holdsKorean(decks, load.byT);
  const st = !kr ? "skip" : disc ? disc.status : "none";
  const dd = disc && disc.status === "ok" && disc.data ? discDate(disc.data, now) : null;
  const ds = st === "skip" ? "skip" : st === "ok" ? (filingsChecked(disc, dd) ? "ok" : "stale") : st === "fail" || st === "none" ? st : "wait";
  const checked = ds === "ok";
  const iss = checked ? issueCards(disc, cover.held, today, data) : { cards: [], skipped: [], fail: false, missing: false };
  const ins = checked ? insiderCards(disc, cover, today, load.byT, ROLE_OF) : { cards: [], skipped: [] };
  const nps = checked ? npsCards(disc, cover, today, load.byT) : [];
  const dates = dateRows(load.byT, cover, today);
  const discOld = ds === "stale" && dd && dd.date ? dd : null;
  const issueFail = checked && iss.fail && [...cover.held].some((t) => { const s = load.byT.get(t); return s ? s.cls === "kr" : /^\d{6}$/.test(t); });
  const any = iss.cards.length > 0 || ins.cards.length > 0 || nps.length > 0 || dates.length > 0;
  return { fresh: true, kr, krHeld, ds, issue: iss.cards, insider: ins.cards, nps, dates, noKr: krHeld, issueFail,
    discFail: ds === "fail" || (ds === "stale" && !discOld), discOld, any, skipped: [...iss.skipped, ...ins.skipped], missing: iss.missing };
}

// The console lines for what the cards leave out (no silent hiding), once per load and list.
const said = new Set();
export function lookSay(m, where) {
  if (!m || !m.fresh) return;
  const lines = [];
  if (m.skipped.length) lines.push(`left out (no approved wording yet, or no close to size it): ${m.skipped.map((x) => `${x.t} ${x.rc || ""} (${x.why})`).join("; ")}`);
  const both = m.insider.filter((c) => c.title === "both");
  if (both.length && !(C.look && C.look.insBoth)) lines.push(`insider cards waiting for Jack's title (role both or blank): ${both.map((c) => `${c.t} ${c.rc}`).join(", ")}`);
  const none = m.insider.filter((c) => c.title === "none");
  if (none.length) lines.push(`insider cards not shown, the role field is not read yet (waits for Jack's yes to a test edit): ${none.map((c) => `${c.t} ${c.rc}`).join(", ")}`);
  if (m.missing) lines.push("disc.json has no issue section (a file from before PR 145): no rights, CB or BW cards");
  for (const l of lines) {
    const k = where + "|" + l;
    if (said.has(k)) continue;
    said.add(k);
    console.warn(`[v2] today-look (${where}): ${l}`);
  }
}
