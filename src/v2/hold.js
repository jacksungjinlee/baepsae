// A later publish fetched on a return to view (load.js refetchNewer) never goes on screen under a draft it could change
// (review of 2026-11-08). Swapped in under 포트폴리오 만들기's 후보 고르기, a picked candidate that dropped out of the new
// candidates vanished from the plan while the screen still counted it; under 매수 계획 (and its 샀어요 sheet) the share counts
// changed while the user was buying; under 가진 종목 넣기's 점검 a holding that left data.json was left out of the saved
// portfolio. So the new data waits:
// - while 포트폴리오 만들기 is on screen past its 기준 steps (후보 고르기 or 매수 계획, the 샀어요 sheet included: it lives
//   in 매수 계획), or while 가진 종목 넣기 is on screen;
// - while a 꼭 담을 종목 (settings.pinned) of 포트폴리오 만들기 is not in the new data.json, at any step, on screen or left
//   behind (round-2 review): the builder would leave it out without a word and still keep its place, one stock short;
// - after the user leaves them, while a draft they left behind (both are kept as the user moves around and reopen where
//   they were) would lose a stock with the new data: a pick that is no longer a candidate, a holding of 가진 종목 넣기
//   (at any of its steps) that is no longer in data.json, or 포트폴리오 만들기 no longer ready on the new data.
// The draft ends the wait when it changes: back to the 기준 steps (the picks are drawn again from the new data), started
// over, finished (기록했어요 → 홈, 매일 점검 시작하기), or edited so that nothing would be lost.
import { deckState } from "./deckcalc.js";
import { withDataShape } from "./engine.js";
import { publishText, staleNow } from "./load.js";

const STAGE = { pick: "its pick step", plan: "its plan step" };

// Would the 포트폴리오 만들기 draft keep every stock on the new data (next: a load state with status "ok")? The candidates
// are worked out the way the new data.json is read (its own data shape: engine.withDataShape, round-2 review), and the
// shape of the data on screen is back afterwards.
export function picksSurvive(builder, next) {
  if (next.missing && next.missing.length) return false;          // 포트폴리오 만들기 would not be ready on the new data
  const st = builder.settings || {};
  return withDataShape(next.data, () => {
    const ds = deckState(next, st);
    if (ds.pinned.length !== (st.pinned || []).length) return false;
    const cands = new Set(Object.values(ds.cands).flat().map((c) => c.t));
    return (builder.picks || []).every((t) => cands.has(t));
  });
}

// Would the 가진 종목 넣기 draft keep every holding on the new data?
export const draftsSurvive = (importer, next) => (importer.drafts || []).every((d) => !!next.byT.get(d.t));
// Would every 꼭 담을 종목 of the 포트폴리오 만들기 draft still be in the new data?
export const pinnedSurvive = (builder, next) => ((builder.settings && builder.settings.pinned) || []).every((t) => !!next.byT.get(t));

// ctx: { onBuild, onImport (that screen is showing), builder, importer } · next: the fetched load state.
// -> why the new data waits (a phrase for the console, after "held while"), or null when it can go on screen now.
export function holdReason(ctx, next) {
  const b = ctx.builder, im = ctx.importer;
  const stage = b && STAGE[b.stage];
  if (ctx.onBuild && stage) return "the portfolio builder is on " + stage;
  if (ctx.onImport) return "the holdings import is open";
  if (!next || next.status !== "ok") return null;
  if (b && !pinnedSurvive(b, next)) return "a stock the portfolio builder must include (pinned) is not in the new data";
  if (stage && !picksSurvive(b, next)) return "the portfolio builder draft left on " + stage + " would lose a stock with the new data";
  if (im && !draftsSurvive(im, next)) return "the holdings import draft left on its step " + (im.step + 1) + " would lose a holding with the new data";
  return null;
}

// The app's side of a return's fetch (app.jsx): a result goes on screen now, or is held while holdReason says so and goes
// on screen when check() finds nothing holding it any more. Either way it goes on screen only if the data on screen is
// still the data it was fetched for (else it is dropped, logged). A failed first load holds nothing (no draft can exist
// without data). Every step is logged with the publish and its counts.
//   getLoad(): the load state on screen · ctx(): holdReason's ctx now · put(result): put it on screen (app.jsx: adoptLoad,
//   then refreshFresh at that moment: a publish held for days goes on screen with today's stale check, never the one worked
//   out when it was fetched).
// -> { apply(result, cur): returnWatch's apply · check(): call when the screen or a draft changes; true when it put the
//      held result on screen · held(now): the held publish described for the console, or null. A held publish that is
//      itself stale by now (load.js staleNow) is dropped there, logged, and null comes back: the return fetches again under
//      the usual rules (round-2 review). }
export function publishGate({ getLoad, ctx, put }) {
  let held = null;                                                // { r, cur, why }
  const fits = (cur) => { const l = getLoad(); return !!l && !!cur && l.status === cur.status && l.data === cur.data; };
  const show = (r, cur, late) => {
    const what = publishText(r.load) + (late ? ", held until now," : "");
    if (!fits(cur)) {
      console.warn("[v2] back in view: " + what + " is not used: the data on screen changed after it was fetched");
      return false;
    }
    put(r);
    console.info("[v2] back in view: " + what + " now shows on every screen");
    return true;
  };
  return {
    apply(r, cur) {
      if (!r || !r.ok) return;
      const why = cur && cur.status === "ok" ? holdReason(ctx(), r.load) : null;
      if (why) {
        held = { r, cur, why };
        console.warn("[v2] back in view: " + publishText(r.load) + " is held while " + why
          + "; the screens keep the data they show (with its stale line) until then");
        return;
      }
      show(r, cur, false);
    },
    check() {
      if (!held || holdReason(ctx(), held.r.load)) return false;
      const h = held;
      held = null;
      return show(h.r, h.cur, true);
    },
    held(now) {
      if (!held) return null;
      const what = publishText(held.r.load) + ", held while " + held.why + ",";
      if (staleNow(held.r.load, now)) {
        held = null;
        console.warn("[v2] back in view: " + what + " is stale itself by now: dropped; this return fetches again under the usual rules");
        return null;
      }
      return what;
    },
  };
}
