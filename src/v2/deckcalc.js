// Glue between the engine and the screens: screening, picks and the plan for the current settings,
// plus the code -> copy mapping for reasons, clashes and cautions.
import {
  screen, splitCounts, survivorCheck, candidates, preselect, size, planShares, annualDividend, estimate2022,
  deckVol, num, liquidity, isStockLike, ruleBook, hasGroup, band2022, exactData,
} from "./engine.js";
import { C, fill, nf, p1, wonText, signed } from "./format.js";

// Everything the builder needs for the current settings. blocked = 후보 고르기 could not be filled: a market has
// fewer survivors than it must fill, or the industry limits leave too few pickable names (pre.blocked says which).
export function deckState(load, settings) {
  const res = screen(load.data.stocks, settings);
  const counts = splitCounts(settings);
  const check = survivorCheck(res, counts);
  const pinned = (settings.pinned || []).map((t) => load.byT.get(t)).filter(Boolean);
  const cands = candidates(res, counts, pinned, settings);
  const pre = preselect(cands, counts, pinned, settings);
  const shortN = Object.values(cands).reduce((a, x) => a + x.length, 0);
  // Settings that cannot all hold (e.g. 5 stocks x max 10%): found on the pre-selected list before 후보 고르기
  // (amount-free; the liquidity cap is checked again in 매수 계획 once the amount is known).
  let clash = null;
  if (!check.block && !pre.short) {
    const all = Object.values(cands).flat();
    const items = [...pre].map((t) => all.find((c) => c.t === t)).filter(Boolean);
    const sz = size({ picks: items, pinned, cushion: cushionStocks(load), settings, amountWon: 0 });
    if (!sz.ok) clash = sz.clash;
  }
  return { res, counts, check, cands, shortN, pinned, pre, clash, settings, blocked: check.block || pre.short || !!clash };
}

export const defaultPicks = (ds) => [...ds.pre];

export function pickItems(ds, picks) {
  const all = Object.values(ds.cands).flat();
  return (picks || []).map((t) => all.find((c) => c.t === t)).filter(Boolean);
}

// The cushion assets of this page ([{ s, share }]); empty unless every one of them is in the data with a price.
export function cushionStocks(load) {
  const out = load.cushion.map((c) => ({ s: load.byT.get(c.t), share: c.share }));
  return out.every((x) => x.s && num(x.s.price) > 0) ? out : [];
}

export function computePlan(load, settings, items, pinned) {
  const amountWon = settings.amountMan * 10000;
  const sz = size({ picks: items, pinned, cushion: cushionStocks(load), settings, amountWon });
  if (!sz.ok) return { ok: false, clash: sz.clash };
  const plan = planShares(sz.items, amountWon, load.data.fx);
  const div = annualDividend(plan.rows, load.data.fx, load.coByT);
  const y2022 = estimate2022(plan.rows, load.r2022);
  const vol = y2022.ok ? null : deckVol(plan.rows, load.data.settings, amountWon);
  return { ok: true, items: sz.items, plan, div, y2022, vol, amountWon };
}

// "일부 종목(비중 {pct}%)…": the same rounding as the current app (whole %, or one decimal below 1%, at least 0.1)
export const missingPct = (share) => (share * 100 >= 1 ? nf(Math.round(share * 100)) : nf(Math.max(share * 100, 0.1), 1));

// Stocks the user may pin as 꼭 담을 종목: company shares incl. preferred, with a price and known liquidity.
export function pinnable(load, q, pinnedTs) {
  const query = String(q || "").trim();
  if (!query) return [];
  const up = query.toUpperCase();
  const out = [];
  for (const s of load.data.stocks) {
    if (!isStockLike(s) || !(num(s.price) > 0) || liquidity(s) == null || pinnedTs.includes(s.t)) continue;
    if ((s.nk && s.nk.includes(query)) || String(s.t).toUpperCase().startsWith(up) || (s.ne && s.ne.toUpperCase().includes(up))) out.push(s);
    if (out.length >= 6) break;
  }
  return out;
}

export function deckDisplayName(settings) {
  if (settings.name && settings.name.trim()) return settings.name.trim();
  if (settings.deck && C.build.decks[settings.deck]) return fill(C.app.deckName, { name: C.build.decks[settings.deck].name });
  return C.deck.title;
}

export function reasonText(r) {
  const R = C.plan.reason;
  switch (r.code) {
    case "rank": return fill(R.rank, { rank: r.rank });
    case "indCap": return r.indName ? fill(R.indCap, { ind: r.indName }) : null;
    case "steadyMore": return R.steadyMore;
    case "steadyLess": return R.steadyLess;
    case "core": return R.core;
    case "maxCap": return fill(R.maxCap, { pct: r.pct });
    case "mktSteady": return fill(R.mktSteady, { mkt: C.pick.market[r.mk], pct: r.pct });
    case "mktVolatile": return fill(R.mktVolatile, { mkt: C.pick.market[r.mk], pct: r.pct });
    case "pinned": return R.pinned;
    case "cushion": return fill(R.cushion, { pct: r.pct });
    case "liqCap": return R.liqCap;
    default: return null;
  }
}
export const reasonsLine = (rs) => (rs || []).map(reasonText).filter(Boolean).join(" · ");

// Clash parts as separate text pieces (each one a copy string).
export function clashPieces(parts) {
  const P = C.plan.clashParts;
  const out = [];
  for (const p of parts) {
    if (p.code === "indCount") out.push([P.indCount]);
    else if (p.code === "count") out.push([P.count, fill(C.app.count, { count: p.n })]);
    else if (p.code === "max") out.push([fill(P.max, { pct: p.pct })]);
    else if (p.code === "ind" && p.indName) out.push([fill(P.ind, { ind: p.indName })]);
    else if (p.code === "mix") out.push([P.mix]);
    else if (p.code === "liq" && P.liq) out.push([P.liq]);
    else if (p.code === "cushion") out.push([p.pct > 0 ? fill(C.plan.reason.cushion, { pct: p.pct }) : C.build.s4.cushionLabel]);
    // an industry group without a name has no approved label: it is left out (never "업종은 최대 1/3" without a name)
  }
  return out;
}

// The clash block: Jack's sentence ("… 아래 조건 중 하나를 바꿔 보세요.") only when at least one condition is listed under
// it; with none, the block keeps the alert alone and the button stays off (the caller blocks either way).
export function clashView(parts) {
  const pieces = clashPieces(parts || []);
  return { pieces, sentence: pieces.length ? C.plan.clash : null };
}

export function cautionTexts(c, s) {
  const K = C.pick.caution;
  switch (c.code) {
    case "pbrHigh": return [fill(K.pbrHigh, { metric: "PBR", x: nf(c.pbr, 2) })];
    case "debtHigh": return [fill(K.debtHigh, { pct: nf(Math.round(c.debt)) })];
    case "revFall": return [K.revFall];
    case "opFall": return opPieces(c.op, c.pct);
    case "volHigh": return K.volHigh ? [fill(K.volHigh, { vol: p1(c.vol) })] : [];
    case "divDrop": return [fill(K.divDrop, { name: s.nk, a: nf(Math.round(c.a)), b: nf(Math.round(c.b)) }), divDropBody()];
    default: return [];
  }
}

// The rule book saved for one plan row at 샀어요 (the same call 매수 계획 shows). Cushion funds get the band only.
export function rulesFor(load, row, st) {
  const s = row.s;
  if (row.kind === "cushion") return ruleBook({ ...s, cls: "etf" }, null, {}, row.targetW).filter((x) => x.id === "band");
  return ruleBook(s, load.coByT.get(s.t) || null, st.points, row.targetW);
}

// The deck record saved at 샀어요 (store.js validates it on read and import). Besides the rule books it keeps the plan's
// own numbers: plannedQty and planPx per holding (the price the plan used, in the stock's own currency) and planFx (the
// USD/KRW rate the plan used). The daily check takes the whole-share rounding gap from these only (rules.planWeights),
// never from the quantities or prices typed in the sheet (purchases).
export function deckRecord({ load, st, plan, purchases, id, today }) {
  const fx = num(load.data.fx);
  return {
    id, name: deckDisplayName(st), createdAt: today, pxDate: load.data.pxDate, fyNote: "rule inputs as of purchase",
    ...(fx > 0 ? { planFx: fx } : {}),
    settings: { deck: st.deck, points: st.points, strict: st.strict, exclude: st.exclude, mix: st.mix, count: st.count, method: st.method,
      maxPct: st.maxPct, cushion: st.cushion, amountMan: st.amountMan, pinned: st.pinned },
    holdings: plan.rows.map((x) => ({ t: x.t, nk: x.s.nk, cls: x.s.cls, ind: hasGroup(x.s) ? x.s.ind : null, kind: x.kind, target: x.targetW,
      reasons: x.reasons, setAt: today, plannedQty: x.shares, ...(num(x.s.price) > 0 ? { planPx: x.s.price } : {}), rules: rulesFor(load, x, st) })),
    purchases,
  };
}

// ---------------- 영업이익 2년 연속 감소 (후보 고르기 주의할 점 · 포트폴리오 매일 점검) ----------------
// One wording for both screens. op = [this year, last year, two years ago] in 억원 (corp.json).
// Amount in 억원 (조원 from 1조): needs the unit wording (pending app.eok / app.jo), null until then.
export function eokText(v) {
  if (!C.app.eok || num(v) == null) return null;
  const a = Math.abs(v), neg = v < 0;
  // the unit is chosen after rounding: 9,999.6억 is "1.0조원", never "10,000억원"
  if (Math.round(a) >= 10000 && C.app.jo) return signed(fill(C.app.jo, { n: nf(a / 10000, 1) }), neg);
  return signed(fill(C.app.eok, { n: nf(Math.round(a)) }), neg && Math.round(a) > 0);
}
// "{two years ago} → {last year} → {this year}", oldest first like "주당 {a}원 → {b}원". null while the unit waits.
export function opAmounts(op) {
  const xs = op ? [op[2], op[1], op[0]].map(eokText) : [];
  return xs.length === 3 && xs.every(Boolean) ? xs.join(" → ") : null;
}
// The fact line: the approved sentence when Jack says yes (pick.caution.opFallFull), else "영업이익 (작년 대비) −x%" when
// last year was a profit, else just "영업이익"; then the three amounts once their unit is approved.
export function opPieces(op, pct) {
  const head = C.pick.caution.opFallFull || (pct != null && Number.isFinite(pct) ? fill(C.pick.caution.opFall, { pct: signedPct(pct) }) : C.plan.rules.opProfit);
  return [head, opAmounts(op)].filter(Boolean);
}

export const aboutWon = (won) => fill(C.app.about, { x: wonText(won) });
// The 배당 감소 hint (확인 필요): v19.1b data has already ruled out splits on the history it compares, so its hint asks only
// about a special dividend (Jack, PR #68 B4); files before v19.1b keep the hint that names 액면분할 too.
export const divDropBody = () => (exactData() && C.pick.caution.divDropBodyExact ? C.pick.caution.divDropBodyExact : C.pick.caution.divDropBody);

// The 2022 line with the beta band (v19.1b data, Part O.1; engine.band2022; Jack, PR #68): the size of the fall with no minus
// sign, the smaller fall first, won only, ending 줄어들 수 있어요 (the label says 2022년처럼 떨어지면):
//   both ends from 1만원 -> 만원 as wonText does, from 1억 too: "약 50~77만원 줄어들 수 있어요" (plan.y2022MayRange)
//   both ends below 1만원 -> 원: "약 4,000~8,000원 …" (plan.y2022May)
//   the two ends on either side of 1만원 -> the app's won format (wonText) on each end, unit repeated: "약 7,500원~1만원 …"
//   both ends the same amount -> one: "약 63만원 줄어들 수 있어요" (plan.y2022May)
// short: the narrow columns of 포트폴리오 만들기 4단계, the same without 약 (build.s4.y2022MayRange · y2022May). The smaller end
// not a fall (whole % 0 or a gain) -> { wide: true }: the screen says plan.y2022Wide instead. null -> no band (files before
// v19.1b): the screen keeps its one signed number. parts: the amount texts (1 = one number, 2 = a range); pct: whole % of each end.
export function y2022View(est, short = false) {
  const b = band2022(est);
  if (!b) return null;
  if (b.wide) return { wide: true };
  const T = short ? C.build.s4 : C.plan;
  const L = Math.round(-b.small), H = Math.round(-b.big);  // sizes of the fall in won, L <= H
  const pct = [b.pctSmall, b.pctBig];
  const one = (x) => ({ parts: [x], ...fallPieces(T.y2022May, { x }), pct });
  if (L >= 10000) {
    const x = Math.round(L / 10000), y = Math.round(H / 10000), man = (n) => fill(C.app.man, { n: nf(n) });
    return x === y ? one(man(x)) : { parts: [nf(x), man(y)], ...fallPieces(T.y2022MayRange, { small: nf(x), big: nf(y) }), pct };
  }
  if (H < 10000) {
    const won = (n) => fill(C.app.won, { n: nf(n) });
    return L === H ? one(won(L)) : { parts: [nf(L), won(H)], ...fallPieces(T.y2022May, { x: `${nf(L)}~${won(H)}` }), pct };
  }
  return { parts: [wonText(L), wonText(H)], ...fallPieces(T.y2022May, { x: `${wonText(L)}~${wonText(H)}` }), pct };
}
// The approved line cut where a narrow column may wrap, without any word of it in the code: the text before the first
// {slot} (pre), the slots with the unit glued to the last one (amount), and the rest (verb). pre + amount + " " + verb is
// exactly fill(template, vals); the screen keeps the amount and the verb each on one line.
function fallPieces(t, vals) {
  const i = t.indexOf("{"), j = t.lastIndexOf("}") + 1;
  const glued = /^\S*/.exec(t.slice(j))[0];
  const amount = fill(t.slice(i, j + glued.length), vals), verb = t.slice(j + glued.length).trim();
  return { text: fill(t, vals), pieces: [t.slice(0, i), amount, verb] };
}
// The sign follows the rounded value: −0.04 is "0.0%", never "−0.0%" (v19.1a review).
export const signedPct = (v) => { const r = Math.round(v * 10) / 10; return `${r < 0 ? "\u2212" : r > 0 ? "+" : ""}${p1(Math.abs(r))}%`; };
