// ================= 내 기준으로 찾기 (v19.7b Part D, board PfFind3) · 두 종목 비교 (Part E, board PfCompare3): the lists and facts =================
// Pure functions, no React and no Korean text (finder.jsx and compare.jsx turn the results into copy from src/copy/v2.js).
// Unit tests: tests/test_v197b_find.py (run through Node), including the real-data check (Acceptance 2) on a published file set.
//
// The finder ranks with the build engine itself (engine.screen) and this portfolio's saved settings: its 기준 points, 빼기
// switches (exclude), strictness (strict) and market mix (mix). 꼭 담을 종목 (settings.pinned) are not set aside: a stock the
// build pinned is either still in the portfolio (then it is held, below) or was taken out (then it may come back). The
// markets' survivors are one list, best total first (engine.topOverall's order: total, then code).
// From that list, in this order (every row the list drops is counted for the console; nothing is dropped silently):
//   1. held       a stock already in the portfolio as edited: a stored holding (a pending 빼기 too, until 바꾼 내용 저장), a
//                 pending 담기, and a listing of the same company as one of them (engine.sameCompany: GOOG while GOOGL is held);
//   2. guarded    with points on 가치, the rows the 가치 list's own guards leave out (ranks.valueGuarded: PBR ≤ 0, a Korean PBR that
//                 rounds to 0.00, the US 4× rule), as 홈's 내 기준 list does (v19.5b review 3): their vz ranks a wrong PBR first;
//   3. one each   one company, one row (ranks.oneEach: the better-placed share class stays).
// What is left is "the candidates"; each carries its 내 기준 number (ranks.criteriaPct, spec [B3]: its weighted score as a
// percentile among all scorable stocks of its market, before the floor, 빼기 and any filter) and whether its industry group is
// new to the portfolio (a real group, engine.hasGroup, with no target in the edited list).
// The four chips (spec Part D), each at most FIND_TOP rows:
//   all      the candidates in rank order;
//   newInd   only those whose group is new to the portfolio;
//   lowVol   the first LOW_VOL_SHARE of the candidates by rank (rounded up), sorted by vol, lowest first (ties keep rank order);
//            a blank vol is left out, never read as 0;
//   div      verified payers: Korea dyt above 0 (engine.dytOf, a file with the split check: exactData), US Yahoo's yield above 0
//            (engine.okDy, as v19.5b's 배당수익률 list reads it). A blank or unverified yield is not a payer.
// Two facts make the compare verdict (Part E): the 내 기준 number and vol, each compared as shown (상위 {x}% · 연 변동성 x.x%). A
// blank on either side, or the same shown value, leaves that fact out (no approved line says "the same").
import { screen, activeCards, hasGroup, dytOf, okDy, exactData, num, sameCompany, strictTop } from "./engine.js";
import { criteriaPct, valueGuarded, usesValue, oneEach } from "./ranks.js";
import * as E from "./edit.js";

export const FIND_TOP = 20;
export const LOW_VOL_SHARE = 0.2;
export const FIND_CHIPS = ["all", "newInd", "lowVol", "div"];
const plain = (x) => !!x && typeof x === "object" && !Array.isArray(x);

// The portfolio's saved 기준 as screen() reads them, or null when no live card has points (the finder asks for 기준 first).
// exclude: the saved 빼기 switches (missing -> none on); strict and mix as saved (missing -> the engine's own defaults).
export function findSettings(deck) {
  const st = deck && plain(deck.settings) ? deck.settings : null;
  const points = st && plain(st.points) ? st.points : {};
  if (!activeCards(points).length) return null;
  return { points, exclude: plain(st.exclude) ? st.exclude : {}, strict: typeof st.strict === "string" ? st.strict : undefined,
    mix: typeof st.mix === "string" ? st.mix : undefined, pinned: [] };
}
export const hasFindPoints = (deck) => findSettings(deck) != null;

// The codes already in the portfolio as edited (see the top): stored holdings, pending 빼기 and pending 담기.
export function heldCodes(deck, draft) {
  const out = new Set();
  for (const h of (deck && deck.holdings) || []) if (h && typeof h.t === "string") out.add(h.t);
  for (const a of (draft && draft.adds) || []) if (a && typeof a.t === "string") out.add(a.t);
  return out;
}
// The industry groups that have a target in the edited list (a 안전자산 part is not an industry; a holding without a group adds none).
export function heldGroups(deck, draft, byT) {
  const out = new Set();
  for (const r of E.editRows(deck, draft || E.emptyDraft())) {
    if (!(num(r.pct) > 0)) continue;
    const g = E.groupOf(r, byT);
    if (g && g !== E.CUSHION) out.add(g);
  }
  return out;
}
// A stock's group is new to the portfolio: a real group (engine.hasGroup) with no target in the edited list.
export const newGroup = (s, groups) => !!s && hasGroup(s) && !groups.has(s.ind);

// The candidates (see the top). load: { data: { stocks }, byT }. -> { rows: [{ s, t, total, pct, newInd }], dropped: { held, same,
// guarded, oneEach }, settings } or null without 기준 points.
const listMemo = new WeakMap();
export function findList(load, deck, draft) {
  const st = findSettings(deck);
  if (!st || !load || !load.data || !Array.isArray(load.data.stocks)) return null;
  const stocks = load.data.stocks;
  const held = heldCodes(deck, draft);
  const groups = heldGroups(deck, draft, load.byT);
  const key = JSON.stringify([st, [...held].sort(), [...groups].sort()]);
  let m = listMemo.get(stocks);
  if (!m) { m = new Map(); listMemo.set(stocks, m); }
  if (m.has(key)) return m.get(key);
  const res = screen(stocks, st);
  const all = Object.values(res.markets).flatMap((x) => x.survivors).sort((a, b) => b.total - a.total || (a.t < b.t ? -1 : 1));
  const heldRows = [...held].map((t) => load.byT && load.byT.get(t)).filter(Boolean);
  const dropped = { held: 0, same: 0, guarded: 0, oneEach: 0 };
  const guard = usesValue(st.points);
  const kept = [];
  for (const x of all) {
    if (held.has(x.t)) { dropped.held++; continue; }
    if (x.s.cls === "us" && heldRows.some((h) => h.cls === "us" && sameCompany(h, x.s))) { dropped.same++; continue; }
    if (guard && valueGuarded(x.s, x.s.cls === "us" ? "us" : "kr")) { dropped.guarded++; continue; }
    kept.push(x);
  }
  const one = oneEach(kept);
  dropped.oneEach = kept.length - one.length;
  const pcts = { kr: criteriaPct(stocks, "kr", st.points), us: criteriaPct(stocks, "us", st.points) };
  const rows = one.map((x) => {
    const mk = x.s.cls === "us" ? "us" : "kr";
    const pct = pcts[mk].has(x.t) ? pcts[mk].get(x.t) : null;
    return { s: x.s, t: x.t, total: x.total, pct, newInd: newGroup(x.s, groups) };
  });
  const out = { rows, dropped, settings: st, survivors: all.length };
  if (dropped.guarded || dropped.same || dropped.oneEach) {
    console.info(`[v2] find (${deck && deck.id}): ${all.length} stocks pass screen(); left out ${dropped.held} held, ${dropped.same} share classes `
      + `of a held company, ${dropped.guarded} by the value guards, ${dropped.oneEach} second share classes; ${rows.length} candidates`);
  }
  m.set(key, out);
  return out;
}

// Is this stock a verified dividend payer (the 배당 주는 종목 chip)?
export function paysDividend(s) {
  if (!s) return false;
  if (s.cls === "kr") { const y = exactData() ? dytOf(s) : null; return y != null && y > 0; }
  if (s.cls === "us") { const y = okDy(s); return y != null && y > 0; }
  return false;
}
// One chip's rows (at most FIND_TOP), each with its rank in the shown list (1, 2, …). list: findList's result.
export function chipRows(list, chip) {
  if (!list) return [];
  const rows = list.rows;
  let out;
  if (chip === "newInd") out = rows.filter((r) => r.newInd);
  else if (chip === "div") out = rows.filter((r) => paysDividend(r.s));
  else if (chip === "lowVol") {
    const top = rows.slice(0, Math.ceil(rows.length * LOW_VOL_SHARE));
    out = top.map((r, i) => ({ r, i, v: num(r.s.vol) })).filter((x) => x.v != null).sort((a, b) => a.v - b.v || a.i - b.i).map((x) => x.r);
  } else out = rows;
  return out.slice(0, FIND_TOP).map((r, i) => ({ ...r, rank: i + 1 }));
}
// The strictness the list was made with (for the console and tests): the engine's top-% cut, or null (loose).
export const listStrictTop = (list) => (list ? strictTop(list.settings.strict) : null);

// ---------------- 두 종목 비교 (Part E) ----------------
// The holdings a candidate can be compared with: the stored holdings still in the edited list (not a pending 담기, which is not
// held yet; not a pending 빼기). -> rows of edit.editRows with h.
export const compareHoldings = (deck, draft) => E.editRows(deck, draft || E.emptyDraft()).filter((r) => !!r.h);
// The default holding [Part E]: the first whose rule is broken today (brokenOf(t) true), else the one with the lowest 내 기준 rank
// (the largest 상위 x%; one without a number is not ranked), else the first. -> t or null.
export function defaultHolding(rows, pctOf, brokenOf) {
  if (!rows.length) return null;
  const br = rows.find((r) => brokenOf(r.t));
  if (br) return br.t;
  let worst = null;
  for (const r of rows) {
    const p = pctOf(r.t);
    if (p == null) continue;
    if (!worst || p > worst.p) worst = { t: r.t, p };
  }
  return worst ? worst.t : rows[0].t;
}
// The verdict's facts as shown: fit = 상위 x% (whole numbers), vol = 연 변동성 rounded to one decimal. a: the holding, b: the
// candidate, each { pct, vol } (null = blank). -> { fit: "better" | "worse" | null, vol: "smaller" | "bigger" | null, kind }
// kind: both · fitBig · lessSmall · worse (two facts) · fit · less · small · big (one fact) · null (none).
const r1 = (v) => Math.round(v * 10) / 10;
export function verdictOf(a, b) {
  const pa = num(a && a.pct), pb = num(b && b.pct);
  const va = num(a && a.vol), vb = num(b && b.vol);
  const fit = pa != null && pb != null && pa !== pb ? (pb < pa ? "better" : "worse") : null;
  const vol = va != null && vb != null && r1(va) !== r1(vb) ? (r1(vb) < r1(va) ? "smaller" : "bigger") : null;
  let kind = null;
  if (fit && vol) kind = fit === "better" ? (vol === "smaller" ? "both" : "fitBig") : vol === "smaller" ? "lessSmall" : "worse";
  else if (fit) kind = fit === "better" ? "fit" : "less";
  else if (vol) kind = vol === "smaller" ? "small" : "big";
  return { fit, vol, kind };
}
// "{group} {a}% → {b}% · 업종 {n}개 → {m}개": the industry part that moves most, before and after (real groups only: no 안전자산 part,
// no part without a group), and how many groups there are. Ties: the part that shrinks (the holding's), then the larger before.
// -> { key, name, a, b, n, m } or null when no group changes.
export function afterChange(before, after) {
  const real = (p) => p && p.key && p.name && !p.cushion;
  const A = new Map(before.filter(real).map((p) => [p.key, p]));
  const B = new Map(after.filter(real).map((p) => [p.key, p]));
  const n = [...A.values()].filter((p) => p.pct > 0).length, m = [...B.values()].filter((p) => p.pct > 0).length;
  let best = null;
  for (const k of new Set([...A.keys(), ...B.keys()])) {
    const a = A.has(k) ? A.get(k).pct : 0, b = B.has(k) ? B.get(k).pct : 0;
    const d = Math.abs(b - a);
    if (d < 1e-9) continue;
    const name = (B.get(k) || A.get(k)).name;
    const better = !best || d > best.d + 1e-9 || (Math.abs(d - best.d) <= 1e-9 && ((b < a && !(best.b < best.a)) || ((b < a) === (best.b < best.a) && a > best.a)));
    if (better) best = { key: k, name, a, b, d };
  }
  return best ? { key: best.key, name: best.name, a: best.a, b: best.b, n, m } : null;
}
