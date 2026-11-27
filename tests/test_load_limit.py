# -*- coding: utf-8 -*-
"""2.0's first data load gives up after 60 s (PR #201 review, 2026-11-28) — run in Node.

Before: load.js loadAll, the live page's first load (main.jsx), had no time limit. A connection that never answered and
never failed kept every screen on the loading state (관심 종목, 연말에 확인할 숫자 … showed only their titles: no cards and
no message) for as long as the browser kept the request open. disc.json already gave up after 60 s (loadDisc).

src/v2/load.js loadFirst: loadAll with one 60 s budget (FIRST_LOAD_TIMEOUT_MS = REFETCH_TIMEOUT_MS, the limit of disc.json
and of a return's fetch). Once it passes, every request still out is stopped (AbortController), so a late answer never
arrives; data.json or corp.json stopped -> the load-failure state, as a network error ("no answer in N s" in the console);
macro.json stopped alone -> the data goes on without it, as when it fails. A load inside the limit is unchanged.
The screens are checked by tests/smoke_v2.py scene_load_limit (a stall longer than the limit, and an answer just under it).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")
_B = {}
NOW = "2026-11-10T17:00:00+09:00"
PUB = "2026-11-10T16:55:00+09:00"


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-loadlimit-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write(f"export * as LD from {json.dumps(os.path.join(ROOT, 'src', 'v2', 'load.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/loadlimit.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# A fake site: SITE['./name.json'] = { body, after } — answered `after` ms after the request (0: at once), or never (hang).
# A browser's fetch rejects with the signal's reason when the signal aborts, before or after the headers (the body read too);
# this one does the same. Every request is recorded: its options, whether its signal was aborted, whether it answered.
HARNESS = """
import * as M from './loadlimit.mjs';
const { LD } = M;
const WARN = [], INFO = [];
console.warn = (m) => WARN.push(String(m));
console.info = (m) => INFO.push(String(m));
const REQ = [];
let SITE = {};
const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
globalThis.fetch = (url, opts) => {
  const rec = { url, cache: opts && opts.cache, signal: !!(opts && opts.signal), aborted: false, answered: false };
  REQ.push(rec);
  const sig = opts && opts.signal;
  const x = SITE[url];
  return new Promise((res, rej) => {
    if (sig) sig.addEventListener('abort', () => { rec.aborted = true; rej(sig.reason); });
    if (!x) { rec.answered = true; res({ ok: false, status: 404, text: async () => 'not found' }); return; }
    if (x.hang) return;
    const answer = () => {
      if (sig && sig.aborted) return;                       // stopped: this answer never reaches the page
      rec.answered = true;
      res({ ok: true, status: 200, text: async () => x.body });
    };
    if (x.after) setTimeout(answer, x.after); else answer();
  });
};
const serve = (files) => { SITE = {}; for (const [n, v] of Object.entries(files)) SITE['./' + n] = v; };
const at = (iso) => Date.parse(iso);
const summary = (l) => (l && l.status === 'ok' ? { status: l.status, pub: l.data.publishedAt, stocks: l.data.stocks.length,
  companies: l.corp.companies.length, macro: !!l.macro } : l);
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


def files(after=None, hang=()):
    """The three files of one publish as the fake site serves them: each `after` ms late ({name: ms}), or never (hang)."""
    stocks = [{"t": f"00{i:04d}", "nk": f"K{i}", "cls": "kr", "price": 10000.0, "d1": 0.5, "etf": False, "ind": "machine",
               "indName": "기계"} for i in range(3)]
    body = {"data.json": {"asOf": PUB[:10], "pxDate": "2026-11-10", "usPxDate": "2026-11-10", "fxDate": "2026-11-10", "fx": 1350.0,
                          "publishedAt": PUB, "nextPub": "2026-11-11", "staleAfter": "2026-11-11T16:47:00+09:00", "stocks": stocks},
            "corp.json": {"pxDate": "2026-11-10", "publishedAt": PUB, "companies": [{"t": "000000", "fy": 2025}]},
            "macro.json": {"publishedAt": PUB, "curve": None}}
    out = {}
    for n, v in body.items():
        out[n] = {"body": json.dumps(v, ensure_ascii=False), "after": (after or {}).get(n, 0)}
        if n in hang:
            out[n]["hang"] = True
    return out


def test_a_stalled_data_json_gives_up_at_the_limit_as_a_load_failure():
    got = run("""
serve(SITE_FILES);
const t0 = Date.now();
const r = await LD.loadFirst(at(NOW), { timeoutMs: 80 });
const took = Date.now() - t0;
out = { r, took, req: REQ, warn: WARN };""", SITE_FILES=files(hang=("data.json",)), NOW=NOW)
    assert got["r"] == {"status": "fail"}, got["r"]                       # the state every screen shows the load-failure message for
    assert 70 <= got["took"] < 5000, got["took"]                          # at the limit, not before it
    req = {x["url"]: x for x in got["req"]}
    assert sorted(req) == ["./corp.json", "./data.json", "./macro.json"], got["req"]
    assert all(x["signal"] and x["cache"] == "no-store" for x in got["req"]), got["req"]
    assert req["./data.json"]["aborted"] is True and req["./data.json"]["answered"] is False, req   # really stopped
    assert req["./corp.json"]["answered"] is True and req["./macro.json"]["answered"] is True, req
    # the reason, as a network error's: resolveLoad's console line
    assert got["warn"] == ["[v2] load failed: data.json: no answer in 0 s"], got["warn"]


def test_a_late_answer_never_arrives_after_the_failure():
    """A data.json that would answer after the limit (120 ms, limit 60 ms): the request is stopped at the limit, so the
    answer is never delivered, and the one result is the failure (app.jsx puts it on screen once)."""
    got = run("""
serve(SITE_FILES);
let results = 0;
const r = await LD.loadFirst(at(NOW), { timeoutMs: 60 }).then((x) => { results += 1; return x; });
await sleep(250);                                                     // well past when the answer would have come
out = { r, results, req: REQ, warn: WARN };""", SITE_FILES=files(after={"data.json": 120}), NOW=NOW)
    assert got["r"] == {"status": "fail"} and got["results"] == 1, got
    d = next(x for x in got["req"] if x["url"] == "./data.json")
    assert d["aborted"] is True and d["answered"] is False, d
    assert got["warn"] == ["[v2] load failed: data.json: no answer in 0 s"], got["warn"]


def test_a_stalled_corp_json_is_a_failure_and_a_stalled_macro_json_alone_goes_on_without_it():
    got = run("""
serve(CORP_HANGS);
const c = await LD.loadFirst(at(NOW), { timeoutMs: 60 });
const cw = WARN.splice(0);
serve(MACRO_HANGS);
const m = await LD.loadFirst(at(NOW), { timeoutMs: 60 });
out = { c, cw, m: summary(m), mw: WARN.filter((x) => x.includes('macro.json')), req: REQ };""",
              CORP_HANGS=files(hang=("corp.json",)), MACRO_HANGS=files(hang=("macro.json",)), NOW=NOW)
    assert got["c"] == {"status": "fail"} and got["cw"] == ["[v2] load failed: corp.json: no answer in 0 s"], got
    # macro.json alone: exactly as when it fails to load today (resolveLoad: on without it, features that need it hidden)
    assert got["m"] == {"status": "ok", "pub": PUB, "stocks": 3, "companies": 1, "macro": False}, got["m"]
    assert got["mw"] == ["[v2] macro.json not loaded: no answer in 0 s (features that need it stay hidden)"], got["mw"]


def test_a_slow_load_under_the_limit_is_unchanged_and_the_timer_is_cleared():
    """Every file answers late (data.json 120 ms, corp.json 90 ms) but inside the limit (400 ms): the same state as loadAll
    with no limit, no failure or stop logged, and nothing is stopped afterwards (the timer is cleared)."""
    got = run("""
serve(SLOW);
const t0 = Date.now();
const r = await LD.loadFirst(at(NOW), { timeoutMs: 400 });
const took = Date.now() - t0;
await sleep(500);                                                     // past the limit: nothing is stopped later
const limited = REQ.splice(0);
const plain = await LD.loadAll(at(NOW));
const same = JSON.stringify({ ...r, byT: [...r.byT], coByT: [...r.coByT], aged: [...r.aged] })
  === JSON.stringify({ ...plain, byT: [...plain.byT], coByT: [...plain.coByT], aged: [...plain.aged] });
out = { r: summary(r), took, limited, plainReq: REQ, same, warn: WARN };""",
              SLOW=files(after={"data.json": 120, "corp.json": 90}), NOW=NOW)
    assert got["r"] == {"status": "ok", "pub": PUB, "stocks": 3, "companies": 1, "macro": True}, got["r"]
    assert 110 <= got["took"] < 400, got["took"]
    assert all(x["signal"] and not x["aborted"] and x["answered"] for x in got["limited"]), got["limited"]
    assert got["same"] is True, got                                       # the state is loadAll's own
    assert all(not x["signal"] for x in got["plainReq"]), got["plainReq"]     # loadAll itself: no signal of its own
    # the console: the same lines for both (resolveLoad's own, about this small file's fields), no failure and no stop
    half = len(got["warn"]) // 2
    assert got["warn"][:half] == got["warn"][half:] and not any("load failed" in x or "no answer" in x for x in got["warn"]), got["warn"]


def test_the_shipped_limit_is_60_seconds_and_the_live_page_uses_it():
    got = run("""
serve(SITE_FILES);
const delays = [];
const real = globalThis.setTimeout;
globalThis.setTimeout = (f, ms) => { if (ms >= 1000) delays.push(ms); return real(f, ms >= 1000 ? 0 : ms); };   // the limit, fired at once
const r = await LD.loadFirst(at(NOW));
globalThis.setTimeout = real;
out = { r, delays, limit: LD.FIRST_LOAD_TIMEOUT_MS, refetch: LD.REFETCH_TIMEOUT_MS, warn: WARN };""",
              SITE_FILES=files(hang=("data.json",)), NOW=NOW)
    assert got["limit"] == 60000 and got["refetch"] == 60000 and got["delays"] == [60000], got
    assert got["r"] == {"status": "fail"} and got["warn"] == ["[v2] load failed: data.json: no answer in 60 s"], got
    src = open(os.path.join(ROOT, "src", "v2", "load.js"), encoding="utf-8").read()
    assert re.findall(r"^export const FIRST_LOAD_TIMEOUT_MS = .*$", src, flags=re.M) == ["export const FIRST_LOAD_TIMEOUT_MS = REFETCH_TIMEOUT_MS;"]
    assert re.findall(r"^export const REFETCH_TIMEOUT_MS = .*$", src, flags=re.M) == ["export const REFETCH_TIMEOUT_MS = 60000;"]
    main = open(os.path.join(ROOT, "src", "v2", "main.jsx"), encoding="utf-8").read()
    assert main.count("load: () => loadFirst(),") == 1 and "loadAll" not in main, "the live page's first load must be loadFirst"
    prev = open(os.path.join(ROOT, "src", "v2", "main-preview.jsx"), encoding="utf-8").read()
    assert "loadFirst" not in prev and "loadAll" not in prev                 # the preview fetches nothing (unchanged)


def test_without_abort_controller_the_load_is_loadall_as_before():
    """As loadWithin: no AbortController, no limit (every browser that runs app.html has one: its bundle uses ??)."""
    got = run("""
serve(SITE_FILES);
delete globalThis.AbortController;
const r = await LD.loadFirst(at(NOW), { timeoutMs: 10 });
out = { r: summary(r), req: REQ };""", SITE_FILES=files(after={"data.json": 40}), NOW=NOW)
    assert got["r"]["status"] == "ok" and all(not x["signal"] for x in got["req"]), got
