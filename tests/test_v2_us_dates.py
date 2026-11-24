# -*- coding: utf-8 -*-
"""뱁새 2.0: 미국 종목의 '오늘'은 뉴욕 날짜예요 (audit 2.1 · 2.2, 2026-11-24) — Node 에서 시계를 고정해 돌려봐요.

- 2.1 달러 기록 (샀어요 · 팔았어요 · 배당 받았어요 · 매수 계획의 샀어요): 한국 자정이 지난 미국 장(겨울 23:30~06:00 KST)에 적으면
  한국 날짜는 뉴욕의 내일이에요. 양식은 뉴욕 날짜로 열리고, 그 날짜(안내 줄 "미국 주식은 미국 현지 날짜로 적어 주세요."가 묻는 날짜)는
  환율 기록이 아직 그날을 모를 때 오늘 환율(data.json fx)로 저장돼요 (main 은 rateNotYet 으로 거절했어요). 환율 기록에 그날이 있으면
  (다음 날 아침) 그 줄 — main 과 같아요. 한국 날짜까지는 예전처럼 적을 수 있어요. 분할은 기록 날짜(미국 거래일)로 읽어요: 한국 날짜가
  분할일이면 뉴욕 날짜로 적은 매수는 분할 전이에요.
- 원화 기록은 같은 시계에서 main 과 똑같아요 (usToday 가 없을 때와 결과가 같아요).
- 2.2 오늘 볼 것 · 다가오는 일정: 미국 실적 발표 · 배당락일(미국 현지 날짜)은 뉴욕 자정까지 남아요 (main 은 한국 자정에 뺐어요).
고정 시계: 겨울 평일 01:00 · 05:30 KST, 여름(서머타임) 01:00 · 05:30 KST, 미국 휴일(추수감사절), 한국 날짜에 분할이 있는 날.
기대값은 손으로 (뉴욕 날짜는 Python zoneinfo 로도) 셌어요. 기기 시간대가 달라도 같아요 (TZ 여러 개로 돌려요).
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
from zoneinfo import ZoneInfo

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
_B = {}
KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
ZONES = ("Asia/Seoul", "UTC", "America/New_York", "America/Los_Angeles", "Pacific/Kiritimati")


def run(body, tz="Asia/Seoul"):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-usdates-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("Fm", "format.js"), ("Rc", "records.js"), ("H", "held.js"), ("L", "lots.js"), ("Lk", "look.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { Fm, Rc, H, L, Lk } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    env = {**os.environ, "TZ": tz}
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


FAKE = """
const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = () => {}; console.info = () => {};
const RealNow = Date.now;
const at = (iso) => { const t = Date.parse(iso); Date.now = () => t; return t; };   // only "now" moves (the smoke tests' way)
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deckOf = (extra = {}) => ({ id: 'd1', name: '배당 생활비 포트폴리오', createdAt: '2026-06-01', planFx: 1300,
  holdings: [{ t: '005930', nk: '삼성전자', target: 0.5, rules: band(0.5) }, { t: 'AAPL', nk: 'Apple Inc.', target: 0.5, rules: band(0.5) }],
  purchases: [{ id: 'p1aaaaaa', t: '005930', qty: 10, price: 200000, date: '2026-06-02', ccy: 'KRW' }, { id: 'p2aaaaaa', t: 'AAPL', qty: 3, price: 300, date: '2026-06-02', ccy: 'USD', fx: 1300 }],
  ...extra });
const S5930 = { t: '005930', nk: '삼성전자', cls: 'kr', price: 225000 };
const SAAPL = { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', ccy: 'USD', price: 344.63 };
// the app's load state for rateEnv: fresh data, today's fx, and the history as the last publish before the clock had it
const loadOf = (asOf, { stale = false, fx = 1340.7 } = {}) => ({ status: 'ok', data: { fx, fxDate: asOf },
  macro: { fxHist: { asOf, final: true, rows: [['2016-01-04', 1172.5], ['2026-06-30', 1380.0], ['2026-07-13', 1375.2], ['2026-11-19', 1330.0], ['2026-11-20', 1336.2],
    ['2026-11-23', 1345.9], ['2026-11-25', 1351.5]].filter(([d]) => d <= asOf) } }, fresh: { stale } });
const noId = (r) => { if (r && r.rec) { const { id, ...rest } = r.rec; return { ...r, rec: rest }; } return r; };
"""

# (clock, the last history day the publishes before it had, New York's date, Korea's date)
CLOCKS = [
    ("2026-11-24T01:00:00+09:00", "2026-11-20", "2026-11-23", "2026-11-24"),   # winter Tuesday 01:00 KST = Monday 11:00 EST (US session open)
    ("2026-11-24T05:30:00+09:00", "2026-11-20", "2026-11-23", "2026-11-24"),   # winter 05:30 KST = 15:30 EST (still open)
    ("2026-07-15T01:00:00+09:00", "2026-07-13", "2026-07-14", "2026-07-15"),   # summer Wednesday 01:00 KST = Tuesday 12:00 EDT
    ("2026-07-15T05:30:00+09:00", "2026-07-13", "2026-07-14", "2026-07-15"),   # summer 05:30 KST = 16:30 EDT (just closed)
    ("2026-11-27T01:00:00+09:00", "2026-11-25", "2026-11-26", "2026-11-27"),   # Thanksgiving in New York (no US trading), Friday in Korea
]


def test_today_in_new_york_follows_daylight_saving_and_never_runs_ahead_of_korea():
    """format.todayNy = Python zoneinfo's New York date at every hour of 2026 and 2027 (both daylight-saving changes each year), in five
    device time zones; todayKst unchanged (the shared helper gives Korea's date as before); New York's date is never after Korea's."""
    start = dt.datetime(2026, 1, 1, 0, 30, tzinfo=dt.timezone.utc)
    hours = [start + dt.timedelta(hours=h) for h in range(0, 2 * 365 * 24, 1)]
    want = [[(h.astimezone(NY)).date().isoformat(), (h.astimezone(KST)).date().isoformat()] for h in hours]
    t0 = int(start.timestamp() * 1000)
    for tz in ZONES:
        got = run(f"out = []; for (let h = 0; h < {len(hours)}; h++) {{ const t = {t0} + h * 3600000; out.push([Fm.todayNy(t), Fm.todayKst(t)]); }}", tz=tz)
        assert got == want, tz
    assert all(ny <= kr for ny, kr in want)
    # the edges by hand: New York's midnight is 14:00 KST in winter and 13:00 KST in summer (both change days of 2026 included)
    edges = {"2026-11-24T13:59:00+09:00": "2026-11-23", "2026-11-24T14:00:00+09:00": "2026-11-24",
             "2026-07-15T12:59:00+09:00": "2026-07-14", "2026-07-15T13:00:00+09:00": "2026-07-15",
             "2026-03-09T12:59:00+09:00": "2026-03-08", "2026-03-09T13:00:00+09:00": "2026-03-09",     # EDT from 03-08
             "2026-11-01T12:59:00+09:00": "2026-10-31", "2026-11-01T13:00:00+09:00": "2026-11-01",     # still EDT at New York's 11-01 midnight
             "2026-11-02T13:59:00+09:00": "2026-11-01", "2026-11-02T14:00:00+09:00": "2026-11-02"}     # EST from 11-01 02:00
    got = run(f"const e = {json.dumps(list(edges))}; out = e.map((x) => {{ at(x); return Fm.todayNy(); }});")
    assert got == list(edges.values()), got


def test_a_dollar_record_after_korean_midnight_opens_on_the_new_york_date_and_saves_with_todays_rate():
    """At each clock: the form's date (records.recordToday) is New York's; buying, selling and a dividend on that date (typed or left
    blank) save with today's rate, data.json fx. main refused it ("notYet", rec.rateNotYet): the same call without usToday still does.
    Korea's date can still be typed (today's rate, as before). Stale data: the today line (rec.noTodayRate), never "notYet"."""
    got = run(f"""
      out = {json.dumps(CLOCKS)}.map(([clock, asOf]) => {{
        const t = at(clock);
        const today = Fm.todayKst(), us = Fm.todayNy();
        const env = Rc.rateEnv(loadOf(asOf), today, us), mainEnv = Rc.rateEnv(loadOf(asOf), today);
        const deck = deckOf();
        const buy = (date, e = env) => noId(Rc.checkPurchase(deck, 'AAPL', {{ qty: '2', price: '', date }}, SAAPL, e));
        return {{ clock, today, us, formDay: Rc.recordToday(env, true), wonDay: Rc.recordToday(env, false),
          blank: buy(''), typedUs: buy(us), typedKr: buy(today), mainUs: buy(us, mainEnv),
          sell: noId(Rc.checkSale(deck, 'AAPL', {{ qty: '1', price: '350', date: us }}, SAAPL, env)),
          sellBlank: noId(Rc.checkSale(deck, 'AAPL', {{ qty: '1', price: '350', date: '' }}, SAAPL, env)),
          div: noId(Rc.checkDiv(deck, 'AAPL', {{ amount: '1.25', date: '' }}, SAAPL, env)),
          stale: Rc.rateFor(us, Rc.rateEnv(loadOf(asOf, {{ stale: true }}), today, us)),
          dayBefore: Rc.rateFor(new Date(Date.parse(us + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10), env) }};
      }});
      Date.now = RealNow;""")
    for (clock, asof, ny, kr), g in zip(CLOCKS, got):
        assert [g["today"], g["us"], g["formDay"], g["wonDay"]] == [kr, ny, ny, kr], g
        ok = lambda date, qty=2: {"ok": True, "rec": {"t": "AAPL", "date": date, "qty": qty, "price": 344.63, "ccy": "USD", "fx": 1340.7}}  # noqa: E731
        assert g["blank"] == ok(ny) and g["typedUs"] == ok(ny), g
        assert g["typedKr"] == ok(kr), g                                                   # Korea's date: today's rate, as on main
        assert g["mainUs"] == {"ok": False, "why": "rate", "field": "date", "rate": "notYet"}, g   # main's refusal (the audit's finding)
        sale = {"t": "AAPL", "qty": 1, "price": 350, "date": ny, "ccy": "USD", "fx": 1340.7}
        assert g["sell"] == {"ok": True, "rec": sale} and g["sellBlank"] == {"ok": True, "rec": sale}, g
        assert g["div"] == {"ok": True, "rec": {"t": "AAPL", "amount": 1.25, "ccy": "USD", "date": ny, "fx": 1340.7}}, g
        assert g["stale"] == {"ok": False, "why": "today"}, g
        # the day before New York's (after the history's last day, not today anywhere): still "notYet", as on main
        assert g["dayBefore"] == ({"ok": False, "why": "notYet"} if asof < (dt.date.fromisoformat(ny) - dt.timedelta(days=1)).isoformat()
                                  else {"ok": True, "fx": {"2026-11-20": 1336.2, "2026-07-13": 1375.2, "2026-11-25": 1351.5}[asof]}), g


def test_the_morning_after_a_new_york_dated_record_keeps_the_rate_of_its_day_as_on_main():
    """09:00 KST: New York's date is still yesterday's in Korea and the 06:40 publish has that day's Seoul close in the history. A record
    on that date takes that row (as main does for the same typed date), not data.json fx. After New York's midnight (14:00 KST in
    winter) both dates are the same day: today's rate, as on main. Every date from 2016 to Korea's today: the rate with usToday equals
    main's except on New York's today when the history does not have it."""
    got = run("""
      const one = (clock, asOf) => {
        at(clock);
        const today = Fm.todayKst(), us = Fm.todayNy();
        const env = Rc.rateEnv(loadOf(asOf), today, us), mainEnv = Rc.rateEnv(loadOf(asOf), today);
        const days = [];
        for (let d = Date.parse('2015-12-25T00:00:00Z'); ; d += 86400000) { const x = new Date(d).toISOString().slice(0, 10); if (x > today) break; days.push(x); }
        const differ = days.filter((d) => JSON.stringify(Rc.rateFor(d, env)) !== JSON.stringify(Rc.rateFor(d, mainEnv)));
        return { today, us, onUs: Rc.rateFor(us, env), mainOnUs: Rc.rateFor(us, mainEnv), differ, n: days.length,
          bad: ['', '2026-02-30', 'x'].map((d) => [Rc.rateFor(d, env), Rc.rateFor(d, mainEnv)]) };
      };
      out = { morning: one('2026-11-24T09:00:00+09:00', '2026-11-23'), night: one('2026-11-24T01:00:00+09:00', '2026-11-20'),
        afternoon: one('2026-11-24T15:00:00+09:00', '2026-11-23'), summer: one('2026-07-15T05:30:00+09:00', '2026-07-13') };
      Date.now = RealNow;""")
    m = got["morning"]
    assert [m["today"], m["us"]] == ["2026-11-24", "2026-11-23"]
    assert m["onUs"] == m["mainOnUs"] == {"ok": True, "fx": 1345.9} and m["differ"] == [], m      # the history's row of 11-23
    assert got["night"]["differ"] == ["2026-11-23"] and got["night"]["onUs"] == {"ok": True, "fx": 1340.7}
    assert got["night"]["mainOnUs"] == {"ok": False, "why": "notYet"}
    a = got["afternoon"]
    assert a["today"] == a["us"] == "2026-11-24" and a["onUs"] == a["mainOnUs"] == {"ok": True, "fx": 1340.7} and a["differ"] == []
    assert got["summer"]["differ"] == ["2026-07-14"]
    for k in got:
        assert got[k]["n"] > 3800 and all(x == y for x, y in got[k]["bad"]), k


def test_a_split_on_the_korean_date_counts_the_new_york_dated_purchase_before_it():
    """01:00 KST 11-24: 10 AAPL bought in New York's 11-23 session, before a 10-for-1 split whose first day on the new count is 11-24
    (data.json splits are US trading dates). Left blank, the purchase is dated 11-23 (main: 11-24), so once the split is published it
    counts 100 shares (main's date: 10). A split listed on the Korean date already (never by the pipeline, which lists a split from its
    first bar) puts today's close on another basis for the New York date: the price must be typed (closeIsDefault, the same rule main
    applies to any date before a split). A split on New York's date itself: the record is already on the new count (factor 1)."""
    got = run("""
      at('2026-11-24T01:00:00+09:00');
      const today = Fm.todayKst(), us = Fm.todayNy();
      const env = Rc.rateEnv(loadOf('2026-11-20'), today, us), mainEnv = Rc.rateEnv(loadOf('2026-11-20'), today);
      const deck = deckOf({ holdings: [{ t: 'AAPL', nk: 'Apple Inc.', target: 1, rules: band(1) }], purchases: [] });
      const mine = noId(Rc.checkPurchase(deck, 'AAPL', { qty: '10', price: '250', date: '' }, SAAPL, env)).rec;
      const theirs = noId(Rc.checkPurchase(deck, 'AAPL', { qty: '10', price: '250', date: '' }, SAAPL, mainEnv)).rec;
      const later = (rec, date) => (H.heldUnits({ purchases: [{ id: 'p9aaaaaa', ...rec }], [H.VIEW_SPLITS]: [{ t: 'AAPL', date, r: 10 }] }).get('AAPL') || 0) / H.UNIT;
      const listed = { ...deck, [H.VIEW_SPLITS]: [{ t: 'AAPL', date: '2026-11-24', r: 10 }] };
      out = { mine, theirs, after: [later(mine, '2026-11-24'), later(theirs, '2026-11-24')], onUsDay: later(mine, '2026-11-23'),
        closeNy: Rc.closeIsDefault(listed, 'AAPL', us, today), closeKr: Rc.closeIsDefault(listed, 'AAPL', today, today),
        noPrice: Rc.checkPurchase(listed, 'AAPL', { qty: '10', price: '', date: '' }, SAAPL, env),
        typed: noId(Rc.checkPurchase(listed, 'AAPL', { qty: '10', price: '250', date: '' }, SAAPL, env)) };
      Date.now = RealNow;""")
    assert got["mine"] == {"t": "AAPL", "date": "2026-11-23", "qty": 10, "price": 250, "ccy": "USD", "fx": 1340.7}
    assert got["theirs"] == {"t": "AAPL", "date": "2026-11-24", "qty": 10, "price": 250, "ccy": "USD", "fx": 1340.7}   # main's date
    assert got["after"] == [100, 10] and got["onUsDay"] == 10
    assert got["closeNy"] is False and got["closeKr"] is True
    assert got["noPrice"] == {"ok": False, "why": "noPrice", "field": "price"}
    assert got["typed"]["ok"] is True and got["typed"]["rec"]["date"] == "2026-11-23"


def test_won_records_at_the_same_clocks_are_exactly_as_on_main():
    """Korean stocks (and 379800-like won listings with cls "us": the currency decides, never cls) at every clock: the form's date is
    Korea's, and every check gives exactly what main's env (no usToday) gives, for a blank date, Korea's date, New York's date and a
    past date. A dollar record's checks on a date that is not New York's today are unchanged too."""
    got = run(f"""
      const S379 = {{ t: '379800', nk: 'KODEX 미국S&P500', cls: 'us', price: 21000 }};
      const deck = deckOf({{ holdings: [...deckOf().holdings, {{ t: '379800', nk: 'KODEX 미국S&P500', cls: 'us', target: 0, rules: band(0.1) }}],
        purchases: [...deckOf().purchases, {{ id: 'p3aaaaaa', t: '379800', qty: 5, price: 20000, date: '2026-06-02', ccy: 'KRW' }}] }});
      out = {json.dumps(CLOCKS)}.map(([clock, asOf]) => {{
        at(clock);
        const today = Fm.todayKst(), us = Fm.todayNy();
        const env = Rc.rateEnv(loadOf(asOf), today, us), mainEnv = Rc.rateEnv(loadOf(asOf), today);
        const diffs = [];
        const same = (label, f) => {{ const a = JSON.stringify(noId(f(env))), b = JSON.stringify(noId(f(mainEnv))); if (a !== b) diffs.push([label, a, b]); return JSON.parse(a); }};
        const rows = [];
        for (const [t, s] of [['005930', S5930], ['379800', S379]]) {{
          for (const date of ['', today, us, '2026-06-30', '2026-07-14', '2026-11-23']) {{
            rows.push(same(`buy ${{t}} ${{date}}`, (e) => Rc.checkPurchase(deck, t, {{ qty: '3', price: '', date }}, s, e)));
            rows.push(same(`sell ${{t}} ${{date}}`, (e) => Rc.checkSale(deck, t, {{ qty: '1', price: '', date }}, s, e)));
            rows.push(same(`div ${{t}} ${{date}}`, (e) => Rc.checkDiv(deck, t, {{ amount: '3610', date }}, s, e)));
          }}
        }}
        for (const date of ['2026-06-30', '2026-07-13', '2026-11-20', '2026-11-25', today])
          if (date !== us) rows.push(same(`buy AAPL ${{date}}`, (e) => Rc.checkPurchase(deck, 'AAPL', {{ qty: '1', price: '300', date }}, SAAPL, e)));
        return {{ today, diffs, wonDay: Rc.recordToday(env, Rc.recordCcy(deck, '379800', S379) === 'USD'), ccy379: Rc.recordCcy(deck, '379800', S379),
          blankDates: rows.filter((r) => r.ok && r.rec.ccy === 'KRW').map((r) => r.rec.date) }};
      }});
      Date.now = RealNow;""")
    for (clock, _, _, kr), g in zip(CLOCKS, got):
        assert g["diffs"] == [], (clock, g["diffs"])
        assert g["ccy379"] == "KRW" and g["wonDay"] == kr, g
        assert kr in g["blankDates"] and g["blankDates"].count(kr) >= 6, g             # a blank or Korea-dated won record: Korea's date


def test_today_look_keeps_a_us_event_until_new_york_midnight():
    """다가오는 일정: NVDA's earnings date 11-24 (US local) is still on the card at 00:01 and 06:00 KST on 11-25 (main dropped it at
    00:00 KST, hours before the after-close release at 06:20 KST), until 13:59 KST (23:59 in New York); gone at 14:00 KST. Summer: until
    12:59 KST. The window is New York's today to 7 days on. Every other card (issue, insider, 국민연금) still reads Korea's date: the model
    is the same as with usToday = Korea's date except for the dates rows."""
    got = run("""
      const deck = { id: 'd1', name: '포트폴리오', createdAt: '2026-06-01', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
        holdings: [{ t: 'NVDA', nk: 'NVIDIA', cls: 'us' }, { t: 'AAPL', nk: 'Apple Inc.', cls: 'us' }], purchases: [],
        imported: [{ t: 'NVDA', nk: 'NVIDIA', ccy: 'USD', qty: 3 }, { t: 'AAPL', nk: 'Apple Inc.', ccy: 'USD', qty: 2 }] };
      const store = { data: { v: 2, decks: [deck] } };
      const loadOf2 = (stocks) => ({ status: 'ok', preview: true, data: { stocks }, byT: new Map(stocks.map((s) => [s.t, s])), fresh: { stale: false, days: 0 } });
      const rows = (clock, stocks) => { const now = at(clock); const m = Lk.lookModel(loadOf2(stocks), store, null, Fm.todayKst(), now);
        const k = Lk.lookModel(loadOf2(stocks), store, null, Fm.todayKst(), now, Fm.todayKst());
        const { dates: d1, ...rest1 } = m, { dates: d2, ...rest2 } = k;
        return { rows: m.dates.map((r) => [r.t, r.kind, r.date]), mainRows: d2.map((r) => [r.t, r.kind, r.date]), restSame: JSON.stringify(rest1) === JSON.stringify(rest2) }; };
      const win = [{ t: 'NVDA', nk: 'NVIDIA', cls: 'us', ed: '2026-11-24', xd: '2026-12-02' }, { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', ed: '2026-12-01', xd: '2026-11-23' }];
      const sum = [{ t: 'NVDA', nk: 'NVIDIA', cls: 'us', ed: '2026-07-14' }, { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', xd: '2026-07-21' }];
      out = {
        win: ['2026-11-24T23:59:00+09:00', '2026-11-25T00:01:00+09:00', '2026-11-25T06:00:00+09:00', '2026-11-25T13:59:00+09:00', '2026-11-25T14:00:00+09:00']
          .map((c) => [c, rows(c, win)]),
        sum: ['2026-07-15T00:30:00+09:00', '2026-07-15T12:59:00+09:00', '2026-07-15T13:00:00+09:00'].map((c) => [c, rows(c, sum)]),
        // dateRows itself is unchanged (이번 주 정리 · 다음 주 passes its own dates)
        direct: Lk.dateRows(new Map(win.map((s) => [s.t, s])), { held: new Set(['NVDA', 'AAPL']), watched: new Set(), all: new Set(['NVDA', 'AAPL']) }, '2026-11-24').map((r) => [r.t, r.kind, r.date]),
      };
      Date.now = RealNow;""")
    w = dict(got["win"])
    # 11-24 23:59 KST = 09:59 EST 11-24: window 11-24..12-01 (AAPL xd 11-23 is past in New York; NVDA xd 12-02 is 8 days on)
    assert w["2026-11-24T23:59:00+09:00"]["rows"] == [["NVDA", "earn", "2026-11-24"], ["AAPL", "earn", "2026-12-01"]]
    for c in ("2026-11-25T00:01:00+09:00", "2026-11-25T06:00:00+09:00", "2026-11-25T13:59:00+09:00"):
        assert w[c]["rows"] == [["NVDA", "earn", "2026-11-24"], ["AAPL", "earn", "2026-12-01"]], (c, w[c])
        assert w[c]["mainRows"] == [["AAPL", "earn", "2026-12-01"], ["NVDA", "xd", "2026-12-02"]], (c, w[c])   # main: dropped at 00:00 KST
    assert w["2026-11-25T14:00:00+09:00"]["rows"] == [["AAPL", "earn", "2026-12-01"], ["NVDA", "xd", "2026-12-02"]]
    s = dict(got["sum"])
    assert s["2026-07-15T00:30:00+09:00"]["rows"] == s["2026-07-15T12:59:00+09:00"]["rows"] == [["NVDA", "earn", "2026-07-14"], ["AAPL", "xd", "2026-07-21"]]
    assert s["2026-07-15T13:00:00+09:00"]["rows"] == [["AAPL", "xd", "2026-07-21"]]
    assert all(v["restSame"] for _, v in got["win"] + got["sum"])
    assert got["direct"] == [["NVDA", "earn", "2026-11-24"], ["AAPL", "earn", "2026-12-01"]]
