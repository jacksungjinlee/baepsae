# -*- coding: utf-8 -*-
"""An old page brought back into view fetches the files once (Jack, 2026-11-08, Q9: "Old page brought back into view: yes,
fetch once. If that fails, show the existing stale or failed message.") — run in Node.

src/v2/load.js:
- staleNow: stale by the rule at this moment (data.json staleAfter passed, its 4-day backstop, or corp.json's 4-day rule);
  never for the preview, a load in progress or a failed load
- refetchNewer: data.json first (no-store, the same checks as the first load); nothing more when it fails or is not a later
  publish; else corp.json and macro.json (+ disc.json when the page shows it). All files from one later publish, or none:
  a failure, an unreadable file, a file from another publish or no later publish keeps the data on screen. Logged with counts.
- returnWatch: at most one fetch per return to view (hidden -> visible, or pageshow from the back-forward cache), never
  two at once, only when stale, no retries
- app.jsx / main.jsx wiring: live page only (the preview never fetches)
- sw.js: the data files go to the network first with the page's request (its no-store) passed through unchanged
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")
_B = {}
MODS = {"D": "src/data.js", "LD": "src/v2/load.js", "E": "src/v2/engine.js", "R": "src/v2/rules.js"}

# The page's clock in these tests: Tuesday 2026-11-10 17:00 KST.
NOW = "2026-11-10T17:00:00+09:00"
OLD_PUB = "2026-11-07T06:40:00+09:00"        # Saturday's publish; the next one was due Tuesday (staleAfter 16:47)
NEW_PUB = "2026-11-10T16:55:00+09:00"        # Tuesday's publish, late but on the site now


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()                 # conftest.py collects pytest's temp folders and removes them at the end
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/refetch.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


# A fake site: SITE[path] = { status, body } (body: text) or { throw: message }. Every fetch is recorded with its options.
HARNESS = """
import * as M from './refetch.mjs';
const { D, LD, E, R } = M;
const WARN = [], INFO = [];
console.warn = (m) => WARN.push(String(m));
console.info = (m) => INFO.push(String(m));
const CALLS = [];
let SITE = {};
globalThis.fetch = async (url, opts) => {
  CALLS.push({ url, cache: opts && opts.cache });
  const x = SITE[url];
  if (!x) return { ok: false, status: 404, text: async () => 'not found' };
  if (x.throw) throw new Error(x.throw);
  return { ok: x.status === 200, status: x.status, text: async () => x.body };
};
const serve = (files) => { SITE = {}; for (const [n, v] of Object.entries(files)) SITE['./' + n] = typeof v === 'string' ? { status: 200, body: v } : (v && (v.throw || v.status)) ? v : { status: 200, body: JSON.stringify(v) }; };
const ok = (d) => ({ ok: true, data: d, error: null });
const at = (iso) => Date.parse(iso);
const loadOf = (f, now) => LD.resolveLoad({ data: ok(f.data), corp: ok(f.corp), macro: f.macro ? ok(f.macro) : { ok: false, error: 'x' } }, at(now));
"""


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = HARNESS + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def stock(t, cls="kr", **kw):
    s = {"t": t, "nk": "K" + t, "cls": cls, "price": 10000.0, "d1": 0.5, "etf": False, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return s


def publish(pub, px, stale_after=None, next_pub=None, n=3, div_check=False):
    """The four files of one publish (the pipeline writes one publishedAt into all of them)."""
    data = {"asOf": pub[:10], "pxDate": px, "usPxDate": px, "fxDate": px, "fx": 1350.0, "publishedAt": pub,
            "nextPub": next_pub, "staleAfter": stale_after, "stocks": [stock(f"00{i:04d}") for i in range(n)]}
    if div_check:
        data["divCheck"] = {"same": 0}
    return {"data": data,
            "corp": {"pxDate": px, "publishedAt": pub, "companies": [{"t": "000000", "fy": 2025}, {"t": "000001", "fy": 2025}]},
            "macro": {"publishedAt": pub, "curve": None},
            "disc": {"asOf": pub[:10], "publishedAt": pub, "newest": px, "listOk": True, "insider": [{"t": "000000", "q": 10}], "nps": []}}


def old_files(**kw):
    return publish(OLD_PUB, "2026-11-06", stale_after="2026-11-10T16:47:00+09:00", next_pub="2026-11-10", **kw)


def new_files(**kw):
    return publish(NEW_PUB, "2026-11-10", stale_after="2026-11-11T16:47:00+09:00", next_pub="2026-11-11", **kw)


def site(files, **over):
    """The fake site's files: {name.json: object | raw text | {status} | {throw}}."""
    out = {k + ".json": v for k, v in files.items()}
    out.update(over)
    return out


# ── staleNow: the rule at this moment ──
def test_stale_now_follows_the_rule_of_the_moment():
    f = old_files()
    no_after = publish("2026-11-05T06:40:00+09:00", "2026-11-04")              # no staleAfter: the 4-day rule
    four = publish("2026-11-06T17:30:00+09:00", "2026-11-06")
    far = publish("2026-11-05T06:40:00+09:00", "2026-11-04", stale_after="2026-12-31T16:47:00+09:00", next_pub="2026-12-31")
    got = run("""
const L = loadOf(F, '2026-11-10T09:00:00+09:00');
const corpOld = { ...L, corp: { ...L.corp, publishedAt: '2026-11-05T06:40:00+09:00' } };
out = {
  before: LD.staleNow(L, at('2026-11-10T16:47:00+09:00')), after: LD.staleNow(L, at('2026-11-10T16:47:01+09:00')),
  backstop: LD.staleNow(loadOf(NA, NOW), at(NOW)), fourDays: LD.staleNow(loadOf(FOUR, NOW), at(NOW)),
  farAfter: LD.staleNow(loadOf(FAR, NOW), at(NOW)),
  corpOld: LD.staleNow(corpOld, at('2026-11-10T09:00:00+09:00')), corpDay: R.dayState(corpOld, at('2026-11-10T09:00:00+09:00')).why,
  preview: LD.staleNow({ ...L, preview: true }, at(NOW)), loading: LD.staleNow({ status: 'loading' }, at(NOW)),
  fail: LD.staleNow({ status: 'fail' }, at(NOW)), none: LD.staleNow(null, at(NOW)),
  freshKept: L.fresh.stale,
};""", F=f, NA=no_after, FOUR=four, FAR=far, NOW=NOW)
    assert got["before"] is False and got["after"] is True, got           # staleAfter passed (n >= 1)
    assert got["backstop"] is True and got["fourDays"] is False, got      # 5 days after the publish: stale; 3.98 days: not yet
    assert got["farAfter"] is True, got                                   # the 4-day backstop stays when staleAfter is far away
    assert got["corpOld"] is True and got["corpDay"] == "stale", got      # corp.json's 4-day rule, as the 홈 band reads it
    assert not any(got[k] for k in ("preview", "loading", "fail", "none")), got
    assert got["freshKept"] is False                                      # staleNow reads the clock; it changes nothing


# ── refetchNewer: a later publish, all files from it ──
def test_a_later_publish_is_swapped_in_whole_and_logged_with_counts():
    got = run("""
const cur = loadOf(OLD, NOW);
serve(SITE_NEW);
const r = await LD.refetchNewer(cur, null, at(NOW));
out = { ok: r.ok, pub: r.load.data.publishedAt, px: r.load.data.pxDate, corpPub: r.load.corp.publishedAt, macro: !!r.load.macro,
  fresh: r.load.fresh, status: r.load.status, n: r.load.byT.size, co: r.load.coByT.size, disc: r.disc, calls: CALLS, warn: WARN, info: INFO,
  curStale: LD.staleNow(cur, at(NOW)), nowStale: LD.staleNow(r.load, at(NOW)), day: R.dayState(r.load, at(NOW)) };""",
              OLD=old_files(), SITE_NEW=site(new_files()), NOW=NOW)
    assert got["ok"] is True and got["status"] == "ok" and got["pub"] == NEW_PUB and got["px"] == "2026-11-10", got
    assert got["corpPub"] == NEW_PUB and got["macro"] is True and got["n"] == 3 and got["co"] == 2 and got["disc"] is None, got
    assert got["curStale"] is True and got["nowStale"] is False and got["fresh"]["stale"] is False and got["day"] == {"ok": True}, got
    # data.json first, then corp.json and macro.json; each once, no-store (as the first load); no disc.json (not on screen)
    assert got["calls"] == [{"url": "./data.json", "cache": "no-store"}, {"url": "./corp.json", "cache": "no-store"},
                            {"url": "./macro.json", "cache": "no-store"}], got["calls"]
    info = " | ".join(got["info"])
    assert f"published {OLD_PUB}" in info and f"the publish of {NEW_PUB}" in info and "3 stocks, 2 companies" in info, info
    assert "data.json, corp.json, macro.json" in info and "now shows on every screen" in info, info
    assert not [w for w in got["warn"] if "kept" in w], got["warn"]


def test_disc_json_comes_too_when_the_page_shows_it():
    got = run("""
const cur = loadOf(OLD, NOW);
serve(SITE_NEW);
const r = await LD.refetchNewer(cur, OLD.disc, at(NOW));
const urls = CALLS.map((c) => c.url); CALLS.length = 0;
serve(SITE_MIXED);
const m = await LD.refetchNewer(cur, OLD.disc, at(NOW));
const urlsM = CALLS.map((c) => c.url); CALLS.length = 0;
serve(SITE_NODISC);
const g = await LD.refetchNewer(cur, OLD.disc, at(NOW));
out = { ok: r.ok, disc: r.disc, urls, info: INFO, m: m.ok, mw: m.why, urlsM, g: g.ok, gw: g.why, warn: WARN };""",
              OLD=old_files(), NOW=NOW, SITE_NEW=site(new_files()),
              SITE_MIXED=site(new_files(), **{"disc.json": old_files()["disc"]}),
              SITE_NODISC=site(new_files(), **{"disc.json": {"status": 503}}))
    assert got["ok"] is True and got["disc"]["publishedAt"] == NEW_PUB and got["disc"]["newest"] == "2026-11-10", got
    assert sorted(got["urls"]) == ["./corp.json", "./data.json", "./disc.json", "./macro.json"] and got["urls"][0] == "./data.json", got
    assert "1 insider and 0 NPS disclosures" in " | ".join(got["info"]), got["info"]
    assert got["m"] is False and "different publishes" in got["mw"] and f"disc.json {OLD_PUB}" in got["mw"], got     # never half-new
    assert got["g"] is False and "disc.json: HTTP 503" in got["gw"] and "3 / 4 files loaded" in got["gw"], got
    assert len(got["urlsM"]) == 4


# ── refetchNewer: anything else keeps the data on screen ──
@pytest.mark.parametrize("label,site_over,why,fetched", [
    ("offline", {"data.json": {"throw": "Failed to fetch"}}, "data.json: Failed to fetch", ["./data.json"]),
    ("404", {"data.json": {"status": 404}}, "data.json: HTTP 404", ["./data.json"]),
    ("unreadable", {"data.json": '{"pxDate": "2026-11-10", "stocks": ['}, "data.json: ", ["./data.json"]),
    ("old format", {"data.json": {"pxDate": "2026-11-10", "stocks": [{"t": "000000"}]}}, "data.json: ", ["./data.json"]),
    ("same publish", "OLD", "no later publish on the site", ["./data.json"]),
    ("earlier publish", "EARLIER", "no later publish on the site", ["./data.json"]),
    ("corp fails", {"corp.json": {"status": 500}}, "corp.json: HTTP 500 (2 / 3 files loaded; none is used)", ["./data.json", "./corp.json", "./macro.json"]),
    ("macro unreadable", {"macro.json": "{nope"}, "macro.json: ", ["./data.json", "./corp.json", "./macro.json"]),
    ("corp from the old publish", "MIXED", "the files are from different publishes", ["./data.json", "./corp.json", "./macro.json"]),
    ("macro without a time", {"macro.json": {"publishedAt": "soon", "curve": None}}, "the files are from different publishes",
     ["./data.json", "./corp.json", "./macro.json"]),
])
def test_anything_but_a_whole_later_publish_keeps_the_data_on_screen(label, site_over, why, fetched):
    old, new = old_files(), new_files()
    if site_over == "OLD":
        files = site(old)
    elif site_over == "EARLIER":
        files = site(publish("2026-11-06T06:40:00+09:00", "2026-11-05"))
    elif site_over == "MIXED":
        files = site(new, **{"corp.json": old["corp"]})
    else:
        files = site(new, **site_over)
    got = run("""
const cur = loadOf(OLD, NOW);
const shape = E.exactData();
serve(SITE_FILES);
const r = await LD.refetchNewer(cur, null, at(NOW));
out = { r, calls: CALLS.map((c) => c.url), warn: WARN, info: INFO, shape: E.exactData() === shape, stillStale: LD.staleNow(cur, at(NOW)) };""",
              OLD=old, NOW=NOW, SITE_FILES=files)
    assert got["r"]["ok"] is False and why in got["r"]["why"], (label, got["r"])
    assert "load" not in got["r"] and got["calls"] == fetched, (label, got["calls"])        # data.json first: nothing more when it is not new
    warn = [w for w in got["warn"] if "back in view" in w]
    assert len(warn) == 1 and f"published {OLD_PUB}" in warn[0] and "kept the data on screen (its stale line stays)" in warn[0], (label, warn)
    assert why in warn[0] and not got["info"], (label, warn, got["info"])
    assert got["shape"] is True and got["stillStale"] is True, label


def test_the_data_shape_follows_what_is_on_screen():
    """The engine reads the data on screen one way (engine.setDataShape; resolveLoad sets it from the file it reads). A
    data.json that passes its check but cannot be read (a stock that is null) never changes it; a good later publish
    changes it only when its state goes on screen (adoptLoad), never while the old data is still shown."""
    new = new_files(div_check=True)
    new["data"]["stocks"].append(None)
    got = run("""
const cur = loadOf(OLD, NOW);
const before = E.exactData();
serve(SITE_FILES);
const r = await LD.refetchNewer(cur, null, at(NOW));
const after = E.exactData();
serve(SITE_GOOD);
const g = await LD.refetchNewer(cur, null, at(NOW));
const fetched = E.exactData();
const shown = LD.adoptLoad(g.load);
out = { before, after, r, g: g.ok, exact: g.load.exact, fetched, same: shown === g.load, adopted: E.exactData(), warn: WARN };""",
              OLD=old_files(), NOW=NOW, SITE_FILES=site(new), SITE_GOOD=site(new_files(div_check=True)))
    assert got["before"] is False and got["after"] is False, got
    assert got["r"]["ok"] is False and "the new files could not be read" in got["r"]["why"], got["r"]
    assert got["g"] is True and got["exact"] is True and got["fetched"] is False, got    # fetched, not shown yet: the old way
    assert got["same"] is True and got["adopted"] is True, got                            # on screen: read its own way


def test_a_first_load_with_mixed_publishes_is_mended_and_never_stepped_back():
    """A first load during a deploy can show data.json and corp.json from two publishes. A later publish is one later than
    the oldest file on screen and not older than any: the same publish as the newer file on screen mends the mix; one
    between the two (a step back for data.json) is not used."""
    old, new = old_files(), new_files()
    mid = publish("2026-11-09T06:40:00+09:00", "2026-11-09")
    got = run("""
const mixed = LD.resolveLoad({ data: ok(NEW.data), corp: ok(OLD.corp), macro: ok(NEW.macro) }, at(NOW));
serve(SITE_NEW);
const a = await LD.refetchNewer(mixed, null, at(NOW));
serve(SITE_MID);
const b = await LD.refetchNewer(mixed, null, at(NOW));
serve(SITE_NEW);
const c = await LD.refetchNewer(mixed, OLD.disc, at(NOW));
const allOld = LD.resolveLoad({ data: ok(OLD.data), corp: ok(OLD.corp), macro: ok(OLD.macro) }, at(NOW));
serve(SITE_MID);
const d = await LD.refetchNewer(allOld, NEW.disc, at(NOW));
serve(SITE_NEW);
const e = await LD.refetchNewer(allOld, NEW.disc, at(NOW));
out = { a: a.ok, corp: a.ok && a.load.corp.publishedAt, b: b.ok, bw: b.why, c: c.ok, d: d.ok, dw: d.why, e: e.ok };""",
              OLD=old, NEW=new, NOW=NOW, SITE_NEW=site(new), SITE_MID=site(mid))
    assert got["a"] is True and got["corp"] == NEW_PUB, got             # the same publish as data.json on screen: corp.json mended
    assert got["b"] is False and "no later publish" in got["bw"], got   # 11-09 is older than data.json on screen (11-10)
    assert got["c"] is True, got                                        # disc.json on screen from Saturday too: mended with the rest
    assert got["d"] is False and "no later publish" in got["dw"], got   # 11-09 is older than disc.json on screen (11-10): no step back
    assert got["e"] is True, got                                        # 11-10, the publish of disc.json on screen: the rest catches up


def test_nothing_newer_than_everything_on_screen_is_no_later_publish():
    """Every file on screen from one publish and the site still on it: no later publish (data.json only was fetched)."""
    got = run("""
const cur = loadOf(NEW, '2026-11-12T17:00:00+09:00');
serve(SITE_NEW);
const r = await LD.refetchNewer(cur, NEW.disc, at('2026-11-12T17:00:00+09:00'));
out = { ok: r.ok, why: r.why, calls: CALLS.map((c) => c.url) };""", NEW=new_files(), SITE_NEW=site(new_files()))
    assert got["ok"] is False and "no later publish" in got["why"] and got["calls"] == ["./data.json"], got


def test_a_later_publish_that_is_itself_late_still_replaces_the_older_one():
    late = publish("2026-11-09T06:40:00+09:00", "2026-11-09", stale_after="2026-11-10T09:00:00+09:00", next_pub="2026-11-10")
    got = run("""
const cur = loadOf(OLD, NOW);
serve(SITE_FILES);
const r = await LD.refetchNewer(cur, null, at(NOW));
out = { ok: r.ok, pub: r.load.data.publishedAt, stale: r.load.fresh.stale, info: INFO };""", OLD=old_files(), NOW=NOW, SITE_FILES=site(late))
    assert got["ok"] is True and got["pub"] == "2026-11-09T06:40:00+09:00" and got["stale"] is True, got
    assert "stale by its own rule too: the stale line stays" in " | ".join(got["info"]), got["info"]


# ── returnWatch: one fetch per return to view ──
WATCH = """
const log = [];
let load = loadOf(OLD, NOW), clock = at(NOW), disc = null, gate = null;
const results = [];
const w = LD.returnWatch({ hidden: HIDDEN, getLoad: () => load, getDisc: () => disc, now: () => clock,
  refetch: (cur, d) => { log.push({ pub: cur.data.publishedAt, disc: d && d.publishedAt }); return gate ? gate.p : Promise.resolve({ ok: false, why: 'x' }); },
  apply: (r, cur) => { results.push({ ok: r.ok, for: cur.data.publishedAt }); if (THROW) throw new Error('boom'); } });
const hold = () => { let res; const p = new Promise((ok) => { res = ok; }); gate = { p, res }; };
const tick = () => new Promise((ok) => setTimeout(ok, 0));
"""


def watch(body, hidden=False, throw=False):
    return run(WATCH + body, OLD=old_files(), NOW=NOW, HIDDEN=hidden, THROW=throw)


def test_only_a_return_to_view_fetches_and_only_once():
    got = watch("""
const a = w.show();                                  // shown without having been hidden (focus, a stray event): no fetch
w.hide(); const b = w.show(); await tick();          // a return: one fetch
const c = w.show();                                  // the second event of the same return (pageshow after visibilitychange)
w.hide(); w.hide(); const d = w.show(); await tick(); // hidden twice, back once: one more fetch
out = { a, b: !!b, c, d: !!d, log, results };""")
    assert got["a"] is None and got["b"] is True and got["c"] is None and got["d"] is True, got
    assert len(got["log"]) == 2 and got["results"] == [{"ok": False, "for": OLD_PUB}] * 2, got


def test_a_page_that_starts_hidden_fetches_on_its_first_view():
    got = watch("const a = w.show(); await tick(); out = { a: !!a, log };", hidden=True)
    assert got["a"] is True and len(got["log"]) == 1


def test_never_two_fetches_at_once_and_no_retry_storm():
    got = watch("""
hold();
w.hide(); const p = w.show();
w.hide(); const q = w.show(); w.hide(); const r = w.show();      // returns while the fetch is out: nothing more
await tick();
const during = log.length;
gate.res({ ok: false, why: 'offline' }); await p;
const after = log.length;
await tick(); await tick();
const later = log.length;                                         // a failed fetch is not retried on its own
gate = null; w.hide(); w.show(); await tick();                    // the next return fetches again (one per return)
out = { during, after, later, q, r, final: log.length, results };""")
    assert got["during"] == 1 and got["after"] == 1 and got["later"] == 1 and got["q"] is None and got["r"] is None, got
    assert got["final"] == 2 and len(got["results"]) == 2, got


def test_fresh_data_is_never_fetched_again():
    got = watch("""
clock = at('2026-11-10T09:00:00+09:00');                           // before staleAfter (16:47): fresh
w.hide(); const a = w.show(); await tick();
clock = at(NOW);                                                   // past staleAfter, but this return was already used
const b = w.show();
w.hide(); const c = w.show(); await tick();                        // a new return, now stale: one fetch
out = { a, b, c: !!c, log };""")
    assert got["a"] is None and got["b"] is None and got["c"] is True and len(got["log"]) == 1, got


def test_the_disc_on_screen_is_passed_and_failures_are_logged_not_thrown():
    got = watch("""
disc = OLD.disc;
w.hide(); await w.show();
const failing = LD.returnWatch({ hidden: true, getLoad: () => load, getDisc: () => null, now: () => clock,
  refetch: () => { throw new Error('network gone'); }, apply: (r) => results.push(r) });
const r2 = await failing.show();
w.hide(); await w.show();                                          // apply throws: logged, nothing escapes
out = { log, results, r2, warn: WARN };""", throw=True)
    assert got["log"][0] == {"pub": OLD_PUB, "disc": OLD_PUB}, got["log"]
    assert got["r2"] == {"ok": False, "why": "network gone"} and {"ok": False, "why": "network gone"} in got["results"], got
    warn = " | ".join(got["warn"])
    assert "the fetch stopped (network gone)" in warn and "kept the data on screen" in warn, warn
    assert "the fetched files were not applied (boom)" in warn, warn


def test_a_stopped_watch_fetches_nothing_and_applies_nothing():
    got = watch("""
hold();
w.hide(); const p = w.show();
w.stop();
gate.res({ ok: true }); await p;
w.hide(); const q = w.show();
out = { log, results, q };""")
    assert len(got["log"]) == 1 and got["results"] == [] and got["q"] is None, got


def test_preview_and_failed_loads_never_fetch():
    got = watch("""
load = { ...load, preview: true }; w.hide(); const a = w.show();
load = { status: 'fail' }; w.hide(); const b = w.show();
load = { status: 'loading' }; w.hide(); const c = w.show();
out = { a, b, c, log };""")
    assert got["a"] is None and got["b"] is None and got["c"] is None and got["log"] == [], got


# ── wiring: the live page only ──
def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


def test_the_live_page_wires_the_return_to_view_and_the_preview_does_not():
    app, main, prev = read("src/v2/app.jsx"), read("src/v2/main.jsx"), read("src/v2/main-preview.jsx")
    assert "refetch: (cur, disc) => refetchNewer(cur, disc)" in main
    assert "refetch" not in prev and "refetchNewer" not in prev            # the preview fetches nothing
    assert "if (!liveData || !source.refetch) return undefined;" in app
    for ev in ('document.addEventListener("visibilitychange", onVis)', 'window.addEventListener("pagehide", onHide)',
               'window.addEventListener("pageshow", onBack)', 'document.removeEventListener("visibilitychange", onVis)',
               'window.removeEventListener("pagehide", onHide)', 'window.removeEventListener("pageshow", onBack)'):
        assert app.count(ev) == 1, ev
    assert "if (e && e.persisted) w.show();" in app                         # pageshow counts only from the back-forward cache
    assert app.count("returnWatch(") == 1 and "w.stop();" in app
    assert app.count("setLoad(adoptLoad(r.load));") == 1                    # the new state goes on screen with its own data shape


# ── service worker: the fetch reaches the network ──
SW = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const BASE = 'https://jack.example/baepsae/';
const listeners = {};
let store = [], online = true;
const seen = [];
const self = { addEventListener: (t, f) => { listeners[t] = f; }, location: { origin: 'https://jack.example' }, skipWaiting() {}, clients: { claim: async () => {} } };
const caches = {
  open: async () => ({ put: async (req, res) => { store = store.filter((e) => e.url !== req.url); store.push({ url: req.url, body: res.body }); } }),
  match: async (req) => { const hit = store.find((e) => e.url === (typeof req === 'string' ? new URL(req, BASE).href : req.url)); return hit ? { body: hit.body } : undefined; },
  keys: async () => [], delete: async () => true,
};
const fetch = async (req) => { seen.push({ url: req.url, cache: req.cache, same: req === LAST }); if (!online) throw new Error('offline');
  return { ok: true, type: 'basic', body: 'net ' + new URL(req.url).pathname, clone() { return { body: this.body }; } }; };
const Response = { error: () => ({ body: 'ERROR' }) };
let LAST = null;
new Function('self', 'caches', 'fetch', 'Response', 'URL', src)(self, caches, fetch, Response, URL);
async function get(path) {
  let p = null;
  LAST = { method: 'GET', url: new URL(path, BASE).href, mode: 'cors', cache: 'no-store' };
  listeners.fetch({ request: LAST, respondWith: (x) => { p = x; } });
  const r = await p; await new Promise((ok) => setTimeout(ok, 0));
  return r ? r.body : 'NOTHING';
}
(async () => {
  const out = { first: [], again: [] };
  for (const n of ['data.json', 'corp.json', 'macro.json', 'disc.json']) out.first.push(await get(n));
  store = store.map((e) => ({ ...e, body: 'OLD ' + e.url }));       // an older copy in the cache
  for (const n of ['data.json', 'corp.json', 'macro.json', 'disc.json']) out.again.push(await get(n));
  store = store.map((e) => ({ ...e, body: 'CACHED ' + e.url }));
  online = false;
  out.off = await get('data.json');
  out.seen = seen;
  console.log(JSON.stringify(out));
})();
"""


def test_the_service_worker_sends_the_data_files_to_the_network_with_no_store():
    r = subprocess.run([NODE, "-e", SW, os.path.join(ROOT, "sw.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    names = ["data.json", "corp.json", "macro.json", "disc.json"]
    assert got["first"] == got["again"] == [f"net /baepsae/{n}" for n in names], got    # network first, an older cached copy is not used
    assert len(got["seen"]) == 9 and all(s["cache"] == "no-store" and s["same"] for s in got["seen"]), got["seen"]   # the page's own request
    assert got["off"] == "CACHED https://jack.example/baepsae/data.json", got["off"]   # offline: the cached copy (not a later publish: kept out)
