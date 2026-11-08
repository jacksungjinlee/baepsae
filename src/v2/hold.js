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
import { publishText, staleNow, REFETCH_GAP_MS } from "./load.js";
import { discDate } from "./company.js";

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

// The line on the screen of a draft (Jack, 2026-11-08, approved: "새 데이터가 들어왔어요. 이 화면을 저장하거나 나가면 새
// 데이터로 바뀌어요.", in place of the stale line "N일째 갱신이 멈췄어요", which is not true while a later publish waits):
// a later publish is held (publishGate) and this screen is why. ctx: holdReason's ctx now · next: the held load state.
// -> "build" on 포트폴리오 만들기's 후보 고르기 or 매수 계획 (the 샀어요 sheet lives there), "import" on 가진 종목 넣기 (any of
// its steps), else null: nothing held, another screen, or saving this screen's work would not end the wait (the other
// draft holds it too: the line would promise what saving here cannot do). Saving ends the draft (기록했어요 → 홈 and 매일
// 점검 시작하기 start the next one fresh), so the publish goes on screen unless the other draft would still hold it.
// Leaving keeps the draft: the publish then goes on screen when the draft keeps every stock on the new data (holdReason).
export function heldOn(ctx, next) {
  if (!ctx || !next || next.status !== "ok" || !holdReason(ctx, next)) return null;
  const b = ctx.builder;
  const screen = ctx.onBuild && b && STAGE[b.stage] ? "build" : ctx.onImport ? "import" : null;
  if (!screen) return null;
  const saved = screen === "build" ? { builder: null, importer: ctx.importer } : { builder: ctx.builder, importer: null };
  return holdReason(saved, next) ? null : screen;
}

// The disc.json state that goes on screen with a publish (app.jsx put; the merge with v19.3e, where 홈 loads disc.json
// itself for 오늘 볼 것's filings and its "오늘은 할 일이 없어요" waits for them): never an older disc.json beside newer data.
// d: app.jsx's disc state · fetched: the disc.json data fetched with the publish (all or none), or null · pub: its publishedAt.
// -> the disc fetched with it; the one on screen when it is already this publish's (or there is none yet, or none at all:
// the preview); otherwise "idle", so it loads again from the site when a screen needs it (the filings wait meanwhile: 홈
// says nothing is quiet before they are checked), logged.
export function discAfter(d, fetched, pub) {
  if (!d || d.status === "none") return d;
  if (fetched) return { status: "ok", data: fetched };
  if (d.status === "idle") return d;
  if (d.status === "ok" && d.data && Date.parse(d.data.publishedAt || "") === Date.parse(pub || "")) return d;
  console.info("[v2] back in view: disc.json " + (d.status === "ok" ? "on screen is from " + (d.data && d.data.publishedAt)
    : d.status === "loading" ? "was still loading" : "had not loaded") + ", not from the publish of " + pub + ": it loads again from the site");
  return { status: "idle" };
}
// A disc.json loaded again after a publish went on screen (discAfter) that is older than that publish is not shown beside it
// (app.jsx: the filings show the load-failure message instead). -> true when it may be shown.
export const discFits = (data, pub) => !pub || !(Date.parse((data && data.publishedAt) || "") < Date.parse(pub));
// Such a disc.json (app.jsx keeps { status: "fail", older: the time it came }) is tried once more (delta review): the site
// may still serve an old copy for a few minutes after a deploy (or the phone its offline copy). On the first return to view
// at least REFETCH_GAP_MS after it came, and only once for each publish put on screen (retried: app.jsx resets it then).
export const discRetryDue = (d, now, retried) => !retried && !!d && d.status === "fail" && Number.isFinite(d.older)
  && Number.isFinite(now) && now - d.older >= REFETCH_GAP_MS;
// The same rule on every load, not only after a return's fetch (#90 review follow-up, 2026-11-08): a first load can get a
// disc.json from an older publish (the site's CDN serving an old copy just after a deploy, or the phone's offline copy).
// Under 4 days old it reads as current (company.discDate), and 홈 could say "오늘은 할 일이 없어요" from it. Such a file
// is not shown beside the data on screen: the load-failure message and the one more try (discRetryDue), as after a fetch.
// One that is stale by its own rule already says so ("{md} 기준 · {n}일째 갱신이 멈췄어요") and keeps that line.
// data: disc.json's data · load: the load state on screen · now: ms. -> true when it must not be shown as it is.
export function discBehind(data, load, now = Date.now()) {
  if (!data || !load || load.status !== "ok" || load.preview || !load.data) return false;
  if (discFits(data, load.data.publishedAt)) return false;
  const d = discDate(data, now);
  return !!d && !d.stale;
}

// The app's side of a return's fetch (app.jsx): a result goes on screen now, or is held while holdReason says so and goes
// on screen when check() finds nothing holding it any more. Either way it goes on screen only if the data on screen is
// still the data it was fetched for (else it is dropped, logged). A failed first load holds nothing (no draft can exist
// without data). Every step is logged with the publish and its counts.
//   getLoad(): the load state on screen · ctx(): holdReason's ctx now · put(result): put it on screen (app.jsx: adoptLoad,
//   then refreshFresh at that moment: a publish held for days goes on screen with today's stale check, never the one worked
//   out when it was fetched) · onHold(load | null) (optional): told whenever the held publish changes (app.jsx: the line
//   on the draft's screen, heldOn), null once nothing is held (put on screen, dropped, or stale itself).
// -> { apply(result, cur): returnWatch's apply · check(): call when the screen or a draft changes; true when it put the
//      held result on screen · held(now): the held publish described for the console, or null. A held publish that is
//      itself stale by now (load.js staleNow) is dropped there, logged, and null comes back: the return fetches again under
//      the usual rules (round-2 review). }
export function publishGate({ getLoad, ctx, put, onHold }) {
  let held = null;                                                // { r, cur, why }
  const tell = (l) => { if (onHold) { try { onHold(l); } catch (e) { console.warn("[v2] back in view: " + ((e && e.message) || e)); } } };
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
          + "; the screens keep the data they show (with its stale line, or on the draft's screen the line that new data waits) until then");
        tell(r.load);
        return;
      }
      show(r, cur, false);
    },
    check() {
      if (!held || holdReason(ctx(), held.r.load)) return false;
      const h = held;
      held = null;
      tell(null);
      return show(h.r, h.cur, true);
    },
    held(now) {
      if (!held) return null;
      const what = publishText(held.r.load) + ", held while " + held.why + ",";
      if (staleNow(held.r.load, now)) {
        held = null;
        tell(null);
        console.warn("[v2] back in view: " + what + " is stale itself by now: dropped; this return fetches again under the usual rules");
        return null;
      }
      return what;
    },
  };
}
