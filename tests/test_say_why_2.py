# -*- coding: utf-8 -*-
"""say-why, second round (Jack, 2026-11-08) — run in Node.

1. 새 데이터가 만들던 것 밑에서 기다릴 때 (hold.js heldOn · publishGate onHold): 후보 고르기 · 매수 계획 · 가진 종목 넣기 화면은
   '새 데이터가 들어왔어요. 이 화면을 저장하거나 나가면 새 데이터로 바뀌어요.' (app.heldNew) 를 멈춤 문구 대신 보여요. 그 화면 때문에
   기다릴 때만, 저장해도 나가도 정말 들어올 때만, 기다리는 발행이 그 자체로 멈춘 것이 아닐 때만. 기다리는 발행이 없으면 절대 없어요.
   화면에 들어가면 줄도 사라져요. ☰ 메뉴와 PC 왼쪽 메뉴의 날짜 줄은 그대로예요 (Jack 이 아직 정하지 않았어요).
2. 내 점수 칸의 회사 수 (engine.companyCount · meterCompanies): 한 회사의 두 주식(미국 GOOG · GOOGL 같은 주식 종류)은 한 회사.
   이름이 같고 (cap ÷ price) 로 본 전체 주식 수가 같을 때만. 종목 수(조건에 맞는 종목 {n}개)는 그대로 종목을 세요.
   회사 페이지의 '업종 {n}개 회사' 줄들도 회사를 세요 (company.pbrStrip · indMedian · roePbrMap 의 co).
3. 점검의 미국 배당 줄 (pf.dividendYear): '미국 종목은 최근 배당을 1년치로 환산한 값이에요.' 는 배당을 아는 미국(달러) 종목이 합계에
   들어갔을 때만. 배당 정보가 없는 미국 종목은 '배당 정보가 없는 미국 종목 {n}개는 빼고 계산했어요.' (rpt.divUsGone), 0원 줄과 겹치지 않게.
6. 공시 파일 (hold.js discBehind · load.js loadDisc): 화면의 데이터보다 이른 발행의 disc.json 이 아직 4일이 안 돼 지금 것처럼 읽히면
   처음 열 때도 보여 주지 않아요 (불러오기 실패 문구와 한 번 더). loadDisc 는 60초 (REFETCH_TIMEOUT_MS) 뒤에 그만둬요: 실패예요.
화면은 tests/smoke_v2.py scene_say_why_2 가 봐요 (320 · 390 · 홈은 1280 도).
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
MODS = {"D": "src/data.js", "LD": "src/v2/load.js", "E": "src/v2/engine.js", "H": "src/v2/hold.js", "K": "src/v2/company.js",
        "P": "src/v2/pf.js", "DC": "src/v2/deckcalc.js"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
NOW = "2026-11-10T17:00:00+09:00"
OLD_PUB = "2026-11-07T06:40:00+09:00"
NEW_PUB = "2026-11-10T16:55:00+09:00"
HELD = "새 데이터가 들어왔어요. 이 화면을 저장하거나 나가면 새 데이터로 바뀌어요."
US_GONE = "배당 정보가 없는 미국 종목 {n}개는 빼고 계산했어요."


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-saywhy2-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/saywhy2.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


HARNESS = """
import * as M from './saywhy2.mjs';
import { readFileSync } from 'fs';
const { D, LD, E, H, K, P, DC } = M;
const WARN = [], INFO = [];
console.warn = (m) => WARN.push(String(m));
console.info = (m) => INFO.push(String(m));
const ok = (d) => ({ ok: true, data: d, error: null });
const at = (iso) => Date.parse(iso);
const fx = (n) => JSON.parse(readFileSync(FIX + '/' + n + '.json', 'utf8'));
"""


def run(body, **data):
    data.setdefault("FIX", FIX)
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = HARNESS + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


def copy():
    from copytrace import copy_strings  # noqa: E402
    return copy_strings()[0]


# ── 1. the line on the draft's screen ──
HOLD = """
const F = { data: fx('data'), corp: fx('corp'), macro: fx('macro') };
for (const k of ['data', 'corp', 'macro']) F[k].publishedAt = OLD_PUB;
const L0 = LD.resolveLoad({ data: ok(F.data), corp: ok(F.corp), macro: ok(F.macro) }, at(NOW));
const st = E.applyDeck(E.defaultSettings(), 'income');
const ds = DC.deckState(L0, st);
const picks = DC.defaultPicks(ds);
const without = (t) => { const d = { ...F.data, publishedAt: NEW_PUB, stocks: F.data.stocks.filter((s) => s.t !== t) };
  return LD.resolveLoad({ data: ok(d), corp: ok({ ...F.corp, publishedAt: NEW_PUB }), macro: ok({ ...F.macro, publishedAt: NEW_PUB }) }, at(NOW)); };
const same = without('NONE');
const krPick = picks.find((t) => L0.byT.get(t).cls === 'kr');
const lost = without(krPick);
const bPick = { step: 3, stage: 'pick', settings: st, picks };
const bPlan = { ...bPick, stage: 'plan' };
const bSteps = { ...bPick, stage: 'steps', picks: null };
const im0 = { step: 0, drafts: [{ t: '005930' }, { t: krPick }] }, im2 = { ...im0, step: 2 }, imNone = { step: 0, drafts: [] };
"""


def hold_run(body):
    return run(HOLD + body, OLD_PUB=OLD_PUB, NEW_PUB=NEW_PUB, NOW=NOW)


def test_the_line_shows_on_the_screen_the_publish_waits_for_and_nowhere_else():
    """The line says "저장하거나 나가면": it shows only where saving and leaving would both let the held publish in, and
    never for a held publish that is stale itself (fresh-eyes review, 2026-11-08)."""
    got = hold_run("""
const O = (ctx, next, now = at(NOW)) => H.heldOn(ctx, next, now);
const pinned = (b) => ({ ...b, settings: { ...st, pinned: [krPick] } });
const imLost = { step: 0, drafts: [{ t: '005930' }, { t: krPick }] };
out = {
  pick: O({ onBuild: true, builder: bPick }, same), plan: O({ onBuild: true, builder: bPlan }, same),
  imp0: O({ onImport: true, importer: im0 }, same), imp2: O({ onImport: true, importer: im2, builder: bSteps }, same),
  impEmpty: O({ onImport: true, importer: imNone }, same),
  // leaving would not let it in (the draft left behind would lose a stock): no line, the stale words stay
  pickLost: O({ onBuild: true, builder: bPick }, lost), planLost: O({ onBuild: true, builder: bPlan }, lost),
  importLost: O({ onImport: true, importer: imLost }, lost), importLost2: O({ onImport: true, importer: im2 }, lost),
  pickPinned: O({ onBuild: true, builder: pinned(bPick) }, lost), planPinned: O({ onBuild: true, builder: pinned(bPlan) }, lost),
  // not the draft's screen: the stale line stays there
  steps: O({ onBuild: true, builder: bSteps }, same), stepsPinned: O({ onBuild: true, builder: pinned(bSteps) }, lost),
  away: O({ builder: bPick }, lost), awayImp: O({ importer: im2 }, lost),
  // nothing held, or nothing that could go on screen
  noNext: O({ onBuild: true, builder: bPick }, null), failNext: O({ onBuild: true, builder: bPick }, { status: 'fail' }), noCtx: O(null, same),
  // the other draft holds it too
  buildButImport: O({ onBuild: true, builder: bPlan, importer: im2 }, lost),
  importButBuild: O({ onImport: true, importer: im0, builder: bPick }, lost),
  importButPinned: O({ onImport: true, importer: im0, builder: pinned(bSteps) }, lost),
  // the other draft left behind keeps everything: the line shows
  buildImpSame: O({ onBuild: true, builder: bPlan, importer: im2 }, same),
  // v19.3d2 (#94): a row added by name (no code) is never lost by new data, so it never keeps the line away
  named: O({ onImport: true, importer: { step: 0, drafts: [{ key: 'n1', t: null, name: '비상장 회사', mode: 'amount', amount: '100' }, { t: '005930' }] } }, lost),
  namedOnly: O({ onImport: true, importer: { step: 2, drafts: [{ key: 'n1', t: null, name: '비상장 회사', mode: 'amount', amount: '100' }] } }, lost),
  namedLost: O({ onImport: true, importer: { step: 0, drafts: [{ key: 'n1', t: null, name: '비상장 회사', mode: 'amount', amount: '100' }, { t: krPick }] } }, lost),
  namedPlan: O({ onBuild: true, builder: bPlan, importer: { step: 0, drafts: [{ key: 'n1', t: null, name: '비상장 회사', mode: 'amount', amount: '100' }] } }, same),
  // the held publish is stale itself by now: not new data, no line (it is fresh at NOW, stale weeks later)
  staleHeld: O({ onBuild: true, builder: bPick }, same, at('2026-11-30T10:00:00+09:00')),
  staleNow: LD.staleNow(same, at('2026-11-30T10:00:00+09:00')), freshNow: LD.staleNow(same, at(NOW)),
  staleImport: O({ onImport: true, importer: im0 }, same, at('2026-11-30T10:00:00+09:00')),
};""")
    assert got["pick"] == "build" and got["plan"] == "build", got
    assert got["imp0"] == "import" and got["imp2"] == "import" and got["impEmpty"] == "import", got
    for k in ("pickLost", "planLost", "importLost", "importLost2", "pickPinned", "planPinned", "steps", "stepsPinned", "away", "awayImp",
              "noNext", "failNext", "noCtx", "buildButImport", "importButBuild", "importButPinned", "staleHeld", "staleImport"):
        assert got[k] is None, (k, got)
    assert got["buildImpSame"] == "build", got
    assert got["named"] == "import" and got["namedOnly"] == "import" and got["namedLost"] is None and got["namedPlan"] == "build", got
    assert got["staleNow"] is True and got["freshNow"] is False, got


def test_the_gate_tells_the_app_when_a_publish_is_held_and_when_it_is_not():
    """onHold(load) when a publish is held, onHold(null) when it goes on screen, is dropped as stale, or is not used."""
    got = hold_run("""
let shown = L0, ctx = { onBuild: true, builder: bPick };
const told = [];
const tell = (l) => told.push(l ? l.data.publishedAt : null);
const g = H.publishGate({ getLoad: () => shown, ctx: () => ctx, put: (r) => { shown = r.load; }, onHold: tell });
g.apply({ ok: false, why: 'x' }, L0);                                       // nothing fetched: nothing told
const t0 = told.length;
g.apply({ ok: true, load: same, disc: null }, L0);                          // held on the pick step
const t1 = told.slice();
g.check();                                                                  // still held: nothing new
const t2 = told.length;
ctx = { onBuild: false, builder: bSteps };
const put = g.check();                                                      // goes on screen: null
const t3 = told.slice();
// held, then the data on screen changes: dropped, null
shown = L0; ctx = { onImport: true, importer: im2 };
g.apply({ ok: true, load: same, disc: null }, shown);
shown = { ...L0, data: { ...L0.data } }; ctx = {};
const dropped = g.check();
const t4 = told.slice();
// held, then stale itself by now: dropped by held(now), null
shown = L0; ctx = { onImport: true, importer: im2 };
g.apply({ ok: true, load: same, disc: null }, shown);
const gone = g.held(at('2026-11-30T10:00:00+09:00'));
const t5 = told.slice();
// a throwing listener is logged and changes nothing
const g2 = H.publishGate({ getLoad: () => L0, ctx: () => ({ onBuild: true, builder: bPick }), put: () => {}, onHold: () => { throw new Error('boom'); } });
g2.apply({ ok: true, load: same, disc: null }, L0);
// without a listener (as before)
const g3 = H.publishGate({ getLoad: () => L0, ctx: () => ({ onBuild: true, builder: bPick }), put: () => {} });
g3.apply({ ok: true, load: same, disc: null }, L0);
out = { t0, t1, t2, put, t3, dropped, t4, gone, t5, held3: !!g3.held(at(NOW)), warn: WARN };""")
    assert got["t0"] == 0 and got["t1"] == [NEW_PUB] and got["t2"] == 1, got
    assert got["put"] is True and got["t3"] == [NEW_PUB, None], got
    assert got["dropped"] is False and got["t4"] == [NEW_PUB, None, NEW_PUB, None], got
    assert got["gone"] is None and got["t5"] == [NEW_PUB, None, NEW_PUB, None, NEW_PUB, None], got
    assert got["held3"] is True and any("back in view: boom" in w for w in got["warn"]), got


def test_the_app_wires_the_line_for_the_screen_only():
    app, ui, nav, rep = read("src/v2/app.jsx"), read("src/v2/ui.jsx"), read("src/v2/nav.jsx"), read("src/v2/report.jsx")
    assert "onHold: (l) => setHeldNext(l)," in app and app.count("const [heldNext, setHeldNext] = useState(null);") == 1
    # worked out with the clock, only when the screen, a draft or the held publish changes (review: not every render)
    assert "const heldHere = useMemo(() => !!heldNext && !loc.about" in app
    assert "&& !!heldOn({ onBuild: inBuild, onImport: inImport, builder, importer }, heldNext, Date.now())," in app
    assert "[heldNext, heldTick, inBuild, inImport, builder, importer, loc.about]);" in app
    # and again when the held publish's own stale check can change
    assert "const wait = nextFreshCheck(heldNext, Date.now());" in app and "}, [heldNext, heldTick]);" in app
    # the screen only: the ☰ menu (MenuSheet) and the PC left menu (SideMenu) are outside the provider
    assert app.count("<HeldContext.Provider value={heldHere}>") == 1 and app.count("</HeldContext.Provider>") == 1
    inner = app.split("<HeldContext.Provider value={heldHere}>", 1)[1].split("</HeldContext.Provider>", 1)[0]
    assert inner.strip() == "<ErrorBoundary key={screenKey} name={tab} pad={ownBar ? undefined : pad}>{screen}</ErrorBoundary>", inner
    assert "export const HeldContext = createContext(false);" in ui
    dl = ui.split("export function DateLine(", 1)[1].split("\n}\n", 1)[0]
    assert "const wait = useHeld();" in dl and "{stale && !wait && <span>{staleText(fresh.days)}</span>}" in dl
    assert '{wait && <span data-ui-v2="held-line"' in dl and "{C.app.heldNew}</span>}" in dl and "brief" not in dl
    assert "brief" not in nav and "useHeld" not in nav and "HeldContext" not in nav       # the menus' date lines as before
    assert "const held = useHeld();" in rep and "{held ? C.app.heldNew : fill(C.rpt.stale," in rep
    assert copy()["app"]["heldNew"] == HELD


# ── 2. one company, two listings ──
def us(t, nk, cap, price, **kw):
    s = {"t": t, "nk": nk, "ne": nk, "cls": "us", "ccy": "USD", "price": price, "cap": cap, "etf": False, "val": 1000.0, "vol": 25.0,
         "beta": 1.0, "vz": 50, "lz": 50, "mz": 50, "roe": 15.0, "debt": 60.0, "g3": 5.0, "dy": 2.0, "opm": 10.0, "pbr": 2.0,
         "ind": "internet", "indName": "인터넷"}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def kr(t, nk, **kw):
    s = {"t": t, "nk": nk, "ne": nk, "cls": "kr", "price": 10000.0, "cap": 5.0, "etf": False, "val20": 100.0, "vol": 30.0, "beta": 1.0,
         "vz": 50, "lz": 50, "mz": 50, "roe": 10.0, "debt": 80.0, "g3": 5.0, "dps": 300.0, "opm": 8.0, "pbr": 1.0, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


# 2026-11-08 live data (cap in 조원 at 1,356.3원, price in $): Yahoo gives each class the whole company's cap at its own price
PAIRS = [us("GOOG", "Alphabet Inc.", 4734.488, 283.93), us("GOOGL", "Alphabet Inc.", 4748.662, 284.78),
         us("FOX", "Fox Corporation", 34.04, 59.5, ind="entertainment"), us("FOXA", "Fox Corporation", 38.125, 66.64, ind="entertainment"),
         us("NWS", "News Corporation", 21.13, 28.96, ind="entertainment"), us("NWSA", "News Corporation", 19.255, 26.39, ind="entertainment")]
OTHERS = [us("HON", "Honeywell International Inc.", 59.0, 186.0, ind="machine"), us("HONA", "Honeywell Aerospace Inc.", 29.5, 93.0, ind="machine"),
          us("TWIN", "Twin Name Corp", 10.0, 50.0), us("TWIM", "Twin Name Corp", 30.0, 50.0),           # same name, 3x the shares: two companies
          us("NCAP", "Alphabet Inc.", None, 283.0), us("AAPL", "Apple Inc.", 6748.311, 342.37, ind="elec"),
          kr("000010", "같은이름"), kr("000020", "같은이름")]


def test_two_share_classes_of_one_company_count_once_and_nothing_else_merges():
    got = run("""
const by = Object.fromEntries([...PAIRS, ...OTHERS].map((s) => [s.t, s]));
const same = (a, b) => E.sameCompany(by[a], by[b]);
out = {
  pairs: [same('GOOG', 'GOOGL'), same('FOX', 'FOXA'), same('NWS', 'NWSA'), same('GOOGL', 'GOOG')],
  apart: [same('HON', 'HONA'), same('TWIN', 'TWIM'), same('GOOG', 'NCAP'), same('000010', '000020'), same('GOOG', 'FOX'), same('GOOG', 'AAPL')],
  self: same('AAPL', 'AAPL'),
  spaces: E.sameCompany(by.GOOG, { ...by.GOOGL, t: 'X', nk: '  alphabet   INC. ' }),
  edge: [E.sameCompany(by.GOOG, { ...by.GOOGL, t: 'Y', cap: by.GOOG.cap / by.GOOG.price * by.GOOGL.price * 1.0049 }),
         E.sameCompany(by.GOOG, { ...by.GOOGL, t: 'Z', cap: by.GOOG.cap / by.GOOG.price * by.GOOGL.price * 1.0051 })],
  count: [E.companyCount(PAIRS), E.companyCount(OTHERS), E.companyCount([...PAIRS, ...OTHERS]), E.companyCount([]), E.companyCount(null),
          E.companyCount([PAIRS[0], PAIRS[0]])],
};""", PAIRS=PAIRS, OTHERS=OTHERS)
    assert got["pairs"] == [True, True, True, True], got
    assert got["apart"] == [False] * 6 and got["self"] is True and got["spaces"] is True, got
    assert got["edge"] == [True, False], got                                         # within 0.5% of the share count, not beyond
    # PAIRS: 3 companies · OTHERS: 8 listings, 8 companies · together: NCAP shares a name with GOOG but has no cap: apart
    assert got["count"] == [3, 8, 11, 0, 0, 1], got


def test_the_meter_counts_companies_and_the_stock_count_stays_stocks():
    stocks = PAIRS + OTHERS + [kr("000030", "가나"), kr("000040", "다라")]
    got = run("""
const S = (o) => ({ ...E.defaultSettings(), ...o });
const m = (o) => { const r = E.screen(STOCKS, S(o)); return { stocks: E.meterCount(r), co: E.meterCompanies(r), poolCo: r.poolCo, pool: r.pool,
  mk: Object.fromEntries(Object.entries(r.markets).map(([k, x]) => [k, [x.pool, x.poolCo]])) }; };
out = { usPool: m({ mix: 'us' }), both: m({ mix: 'k55' }), krOnly: m({ mix: 'kr' }),
  usPts: m({ mix: 'us', points: { value: 5 }, strict: 'loose' }), pinned: m({ mix: 'us', pinned: ['GOOG'] }),
  note: E.shareClassNote(STOCKS), again: E.shareClassNote(STOCKS) === E.shareClassNote(STOCKS), warn: WARN };""", STOCKS=stocks)
    # US: 12 listings (HON · HONA, TWIN · TWIM and NCAP stay apart; 3 pairs merged) = 9 companies; Korea never merges
    assert got["usPool"]["stocks"] == {"pool": True, "n": 12} and got["usPool"]["co"] == {"pool": True, "n": 9}, got
    assert got["usPool"]["poolCo"] == 9 and got["usPool"]["pool"] == 12, got
    assert got["both"]["stocks"]["n"] == 16 and got["both"]["co"]["n"] == 13 and got["both"]["mk"] == {"kr": [4, 4], "us": [12, 9]}, got
    assert got["krOnly"]["co"] == {"pool": True, "n": 4} and got["krOnly"]["stocks"] == {"pool": True, "n": 4}, got
    assert got["usPts"]["stocks"] == {"pool": False, "n": 12} and got["usPts"]["co"] == {"pool": False, "n": 9}, got
    assert got["pinned"]["stocks"]["n"] == 11 and got["pinned"]["co"]["n"] == 9, got    # GOOG pinned (not in the pool): GOOGL is still Alphabet
    assert sorted(map(sorted, got["note"]["one"])) == [["FOX", "FOXA"], ["GOOG", "GOOGL"], ["NWS", "NWSA"]], got["note"]
    assert sorted(map(sorted, got["note"]["apart"])) == [["GOOG", "NCAP"], ["GOOGL", "NCAP"], ["TWIM", "TWIN"]], got["note"]
    assert got["again"] is True
    one = [w for w in got["warn"] if w.startswith("[v2] one company, two listings")]
    apart = [w for w in got["warn"] if w.startswith("[v2] same name but not the same share count")]
    assert len(one) == 1 and "GOOG = GOOGL" in one[0] and "FOX = FOXA" in one[0] and "NWS = NWSA" in one[0], got["warn"]
    assert len(apart) == 1 and "TWIN · TWIM" in apart[0] and "GOOG · NCAP" in apart[0] and "counted as separate companies" in apart[0], got["warn"]


def test_the_fixture_merges_alphabet_and_the_meter_shows_one_less_than_the_list():
    """The test data (tests/fixtures/v2/data.json) has GOOG and GOOGL: one company. The meter's pool before any 기준 (default
    mix, both markets) counts Alphabet once; the stock count keeps both."""
    got = run("""
const d = fx('data');
const S = (o) => ({ ...E.defaultSettings(), ...o });
const r = E.screen(d.stocks, S({}));
out = { note: E.shareClassNote(d.stocks), stocks: E.meterCount(r).n, co: E.meterCompanies(r).n, poolCo: r.poolCo,
  goog: r.markets.us ? r.markets.us.pool : null };""")
    assert got["note"] == {"one": [["GOOG", "GOOGL"]], "apart": []}, got["note"]
    assert got["co"] == got["stocks"] - 1 == got["poolCo"], got


def test_the_company_page_counts_companies_in_the_lines_that_say_company():
    grp = [us(f"P{i}", f"Peer {i}", 10.0 + i, 50.0, pbr=1.0 + 0.2 * i, roe=5.0 + i, per=10.0 + i) for i in range(5)]
    grp += [us("GOOG", "Alphabet Inc.", 4734.488, 283.93, pbr=8.0, roe=30.0, per=25.0),
            us("GOOGL", "Alphabet Inc.", 4748.662, 284.78, pbr=8.02, roe=30.0, per=25.1)]
    got = run("""
const G = GRP, goog = G[5], p0 = G[0];
const strip = K.pbrStrip(goog, G), stripP = K.pbrStrip(p0, G), map = K.roePbrMap(goog, G), mapP = K.roePbrMap(p0, G);
const per = K.indMedian(G, (x) => x.per);
const kr = K.pbrStrip(KRS[0], KRS);
out = { strip: [strip.n, strip.co, strip.dots.length], stripP: [stripP.n, stripP.co], map: [map.n, map.co, map.pts.length], mapP: [mapP.n, mapP.co],
  per: [per.n, per.co], kr: [kr.n, kr.co] };""", GRP=grp, KRS=[kr(f"0000{i}0", "같은이름", pbr=1.0 + i * 0.1) for i in range(6)])
    assert got["strip"] == [7, 6, 7] and got["stripP"] == [7, 6], got            # the dots stay one per listing
    assert got["map"] == [7, 6, 7] and got["mapP"] == [7, 6], got                 # GOOGL is GOOG's own company on its map
    assert got["per"] == [7, 6] and got["kr"] == [6, 6], got
    cot = read("src/v2/cotabs.jsx")
    assert "fill(V.strip, { n: st.co })" in cot and "fill(V.stripAria, { ind: s.indName, n: st.co," in cot
    assert cot.count("compareN(st.co, per != null ? perCo(perMed) : null)") == 2 and "fill(M.aria, { ind: s.indName, n: m.co," in cot
    for bad in ("fill(V.strip, { n: st.n })", "n: st.n, x:", "compareN(st.n", "n: m.n, roe"):
        assert bad not in cot, bad


def test_build_uses_the_company_count_where_the_words_say_company():
    b = read("src/v2/build.jsx")
    assert "const co = meterCompanies(ds.res);" in b and "{nf(co.n)}</b>{rp[1]}" in b and "{co.n === 0 ? s1.remainNone" in b
    assert "fill(C.app.count, { count: nf(ds.res.poolCo) })" in b and "fill(C.app.count, { count: nf(ds.res.pool) })" not in b
    assert "const n = meterCompanies(ds.res).n;" in b
    # the bottom bar says 종목: it keeps the stock count
    assert "{fill(C.app.count, { count: nf(meterCount(ds.res).n) })}" in b and "matchSummary" in b
    c = copy()
    assert c["build"]["matchSummary"] == "조건에 맞는 종목" and "회사" in c["build"]["s1"]["remain"] and "회사" in c["guide"]["s2"][0]


# ── 3. 점검's US dividend lines ──
def drow(s, qty=1, value=1000000.0):
    return {"key": s["t"], "t": s["t"], "nk": s["nk"], "s": s, "qty": qty, "value": value}


def test_the_us_dividend_line_needs_a_known_us_dividend_and_the_missing_ones_are_named_once():
    known = us("AAPL", "Apple Inc.", 6748.311, 342.37, dy=0.32)
    gone = us("NODY", "No Dividend Inc.", 10.0, 50.0, dy=None)
    gone2 = us("NODZ", "No Dividend Two Inc.", 10.0, 40.0, dy=None)
    krs = kr("005930", "삼성전자", dps=None)
    kodex = {"t": "379800", "nk": "KODEX 미국S&P500", "cls": "us", "ccy": None, "dy": None, "etf": True, "fund": True, "price": 22415.0}
    cases = {
        "known": [known], "gone": [gone], "both": [known, gone, gone2], "kr": [krs], "kodex": [kodex],
        "mixed": [known, gone, krs, kodex],
    }
    got = run("""
const view = (ss) => ({ rows: ss.map((s) => ({ key: s.t, s, qty: 1, value: 1000000 })) });
const named = { rows: [{ key: 'x', s: null, qty: 1, value: null, nk: '이름만' }, { key: 'AAPL', s: KNOWN, qty: 1, value: 1000000 }] };
out = Object.fromEntries(Object.entries(CASES).map(([k, ss]) => { const d = P.dividendYear(view(ss), 1356.3, new Map());
  return [k, { us: d.us, usGone: d.usGone, unknown: d.unknown, won: Math.round(d.won) }]; }));
const n = P.dividendYear(named, 1356.3, new Map());
out.named = { us: n.us, usGone: n.usGone, unknown: n.unknown };""", CASES=cases, KNOWN=known)
    assert got["known"] == {"us": True, "usGone": 0, "unknown": 0, "won": 3200}, got
    assert got["gone"] == {"us": False, "usGone": 1, "unknown": 0, "won": 0}, got          # the old rule said us: true here
    assert got["both"] == {"us": True, "usGone": 2, "unknown": 0, "won": 3200}, got
    assert got["kr"]["us"] is False and got["kr"]["usGone"] == 0 and got["kr"]["unknown"] == 1, got
    assert got["kodex"] == {"us": False, "usGone": 0, "unknown": 1, "won": 0}, got       # a won-priced KRX fund is not a US holding
    assert got["mixed"] == {"us": True, "usGone": 1, "unknown": 2, "won": 3200}, got
    assert got["named"] == {"us": True, "usGone": 0, "unknown": 1}, got                  # a holding added by name: the 0원 line


def test_the_report_shows_the_lines_by_those_rules():
    rep = read("src/v2/report.jsx")
    div = rep.split("function Dividends(", 1)[1].split("\n}\n", 1)[0]
    assert '{d.us && <Note data-ui-v2="report-div-us">{C.rpt.divUs}</Note>}' in div
    assert '{d.usGone > 0 && <Note data-ui-v2="report-div-us-gone">{fill(C.rpt.divUsGone, { n: d.usGone })}</Note>}' in div
    assert div.index("C.rpt.divUs}") < div.index("C.rpt.divUsGone") < div.index("C.plan.divUnknown")
    assert copy()["rpt"]["divUsGone"] == US_GONE


# ── 6. disc.json ──
def disc(pub, newest="2026-11-10", list_ok=True):
    return {"asOf": pub[:10], "publishedAt": pub, "newest": newest, "listOk": list_ok, "insider": [], "nps": []}


def test_an_older_disc_json_that_reads_as_current_is_not_shown_on_any_load():
    got = run("""
const F = { data: fx('data'), corp: fx('corp'), macro: fx('macro') };
for (const k of ['data', 'corp', 'macro']) F[k].publishedAt = NEW_PUB;
const L = LD.resolveLoad({ data: ok(F.data), corp: ok(F.corp), macro: ok(F.macro) }, at(NOW));
const t = at(NOW);
out = {
  older: H.discBehind(OLDER, L, t), same: H.discBehind(SAME, L, t), newer: H.discBehind(NEWER, L, t),
  oldStale: H.discBehind(SIX_DAYS, L, t), listStopped: H.discBehind(LIST_STOPPED, L, t),
  preview: H.discBehind(OLDER, { ...L, preview: true }, t), loading: H.discBehind(OLDER, { status: 'loading' }, t),
  fail: H.discBehind(OLDER, { status: 'fail' }, t), none: H.discBehind(null, L, t),
  noTime: [H.discBehind({ ...OLDER, publishedAt: 'x' }, L, t), LD.CHECKS.disc({ ...OLDER, publishedAt: 'x' })],
  // the same older file read on the day it turns stale by its own rule: the date line ('…일째 갱신이 멈췄어요') takes over
  laterDay: H.discBehind(OLDER, L, at('2026-11-12T08:00:00+09:00')),
};""", NEW_PUB=NEW_PUB, NOW=NOW, OLDER=disc(OLD_PUB), SAME=disc(NEW_PUB), NEWER=disc("2026-11-10T18:00:00+09:00"),
              SIX_DAYS=disc("2026-11-04T06:40:00+09:00"), LIST_STOPPED=disc(OLD_PUB, list_ok=False))
    assert got["older"] is True and got["same"] is False and got["newer"] is False, got
    assert got["oldStale"] is False and got["listStopped"] is False, got
    assert not any(got[k] for k in ("preview", "loading", "fail", "none")), got
    assert got["noTime"] == [False, False], got                                       # no readable time: never loaded (CHECKS.disc)
    assert got["laterDay"] is False, got


def test_the_app_checks_disc_json_against_the_data_on_every_load():
    app = read("src/v2/app.jsx")
    assert 'const discOld = disc.status === "ok" && discBehind(disc.data, load);' in app
    assert 'const discView = useMemo(() => (discOld ? { status: "fail" } : disc), [discOld, disc]);' in app
    assert 'setDisc((d) => (d === disc ? { status: "fail", older: Date.now() } : d));' in app and "}, [discOld, disc]);" in app
    # the screens get the checked state; the loader and the return watch keep the state itself
    assert "disc={discView} nav={coNav} />" in app and "welcome={welcome} disc={discView} />" in app
    assert "disc={disc}" not in app


def test_load_disc_gives_up_after_the_refetch_limit():
    got = run("""
const calls = [];
let mode = 'hang';
globalThis.fetch = async (url, opts) => {
  calls.push({ url, cache: opts && opts.cache, signal: !!(opts && opts.signal) });
  if (mode === 'hang') return new Promise((res, rej) => { opts.signal.addEventListener('abort', () => rej(opts.signal.reason)); });
  return { ok: true, status: 200, text: async () => JSON.stringify(DISC) };
};
const t0 = Date.now();
const hung = await LD.loadWithin('./disc.json', LD.CHECKS.disc, 50);
const took = Date.now() - t0;
mode = 'ok';
const fine = await LD.loadWithin('./disc.json', LD.CHECKS.disc, 50);
// loadDisc itself: the limit is REFETCH_TIMEOUT_MS (setTimeout is caught to read its delay, then fired at once)
const delays = [];
const real = globalThis.setTimeout;
globalThis.setTimeout = (f, ms) => { delays.push(ms); return real(f, 0); };
mode = 'hang';
const viaDisc = await LD.loadDisc();
globalThis.setTimeout = real;
out = { hung, took, fine: fine.ok, calls, delays, viaDisc, limit: LD.REFETCH_TIMEOUT_MS };""", DISC=disc(NEW_PUB))
    assert got["hung"] == {"ok": False, "data": None, "error": "no answer in 0 s"}, got
    assert got["took"] < 5000 and got["fine"] is True, got
    assert all(c["signal"] and c["cache"] == "no-store" and c["url"] == "./disc.json" for c in got["calls"]), got["calls"]
    assert got["limit"] == 60000 and 60000 in got["delays"], got
    assert got["viaDisc"]["ok"] is False and got["viaDisc"]["error"] == "no answer in 60 s", got
    assert "export function loadDisc()" in read("src/v2/load.js")
    assert 'return loadWithin("./disc.json", CHECKS.disc, REFETCH_TIMEOUT_MS);' in read("src/v2/load.js")
