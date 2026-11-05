# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.0c 의 순수 함수들 — Node 로 직접 돌려봐요.

- 주소(src/v2/routes.js): #home · #portfolio · #stocks · #market · #about · #portfolio/build · #home/why, 없는 주소는 #home
- 예전 뱁새 바로가기(src/deeplink.js): #macro · #disc · #corp=코드 · #info=glossary|sources 만, 나머지는 아무것도 안 해요
- 거래대금 상위 종목(stocklist.js popularLists): 한국 · 미국 따로, data.json popular 의 순서 그대로, 펀드 빼고, 목록마다 날짜
- 시장 네 칸(marketTiles): 코스피 · S&P 500 은 마지막 두 종가로 변화, 국고채 3년 · 원/달러는 수준만 (변화를 지어내지 않아요),
  칸마다 자기 날짜, 값이나 날짜가 없으면 값도 없음('–')
- 찾기(searchStocks) · 내 포트폴리오 종목(myStocks) · 예전에 저장한 기본 이름(legacy.js, 보여 줄 때만) · 포트폴리오에서 빼기
  (store.withoutHolding: 그 종목 하나만) · 최근 본 종목(recent.js) · 아이폰 사파리(store.iphoneSafari, 홈 화면 앱 안에서는 아님)
- 빠진 종목 문장의 {names} (tracking.jsx missingNames): '이름 금액', 미국은 티커 (예전 뱁새와 같은 꼴 'STRC 200만원')
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
_B = {}
MODS = {"L": "src/v2/stocklist.js", "R": "src/v2/routes.js", "D": "src/deeplink.js", "G": "src/v2/legacy.js", "S": "src/v2/store.js",
        "Q": "src/v2/recent.js", "V": "src/v2/tracking.jsx", "C": "src/copy/v2.js"}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/lists.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as T from './lists.mjs';\nconst { L, R, D, G, S, Q, V } = T; const CP = T.C.C;\n"
            "const loadOf = (data, macro = null) => ({ status: 'ok', data, macro, byT: new Map(data.stocks.map((s) => [s.t, s])) });\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def st(t, nk, cls="kr", **kw):
    s = {"t": t, "nk": nk, "ne": kw.pop("ne", nk), "cls": cls, "price": 1000.0, "d1": 0.5, "etf": False, "cap": 1.0}
    s.update(kw)
    return s


# ── 주소 ──
def test_routes_know_the_four_tabs_about_and_the_two_sub_screens():
    got = run("""out = Object.fromEntries(H.map((h) => [h, R.parseHash(h)]));""",
              H=["", "#", "#home", "#portfolio", "#stocks", "#market", "#about", "#portfolio/build", "#home/why", "#home/build",
                 "#stocks/x", "#portfolio/build/2", "#today", "#deck", "#search", "#ABOUT", "#about/x"])
    ok = lambda tab, sub=None: {"tab": tab, "sub": sub, "about": False, "known": True}
    assert got["#home"] == ok("home") and got["#portfolio"] == ok("portfolio") and got["#stocks"] == ok("stocks") and got["#market"] == ok("market")
    assert got["#portfolio/build"] == ok("portfolio", "build") and got["#home/why"] == ok("home", "why")
    assert got["#about"] == {"tab": None, "sub": None, "about": True, "known": True}
    for h in ("", "#"):
        assert got[h] == {"tab": "home", "sub": None, "about": False, "known": False, "empty": True}, h    # 주소 없음 → #home
    for h in ("#home/build", "#stocks/x", "#portfolio/build/2", "#today", "#deck", "#search", "#ABOUT", "#about/x"):
        assert got[h] == {"tab": "home", "sub": None, "about": False, "known": False}, h                  # 모르는 주소 → #home
    links = run("""out = { ...R.OLD_LINKS, corp: R.OLD_LINKS.corp('005930'), hash: R.hashOf('portfolio', 'build'), old: R.OLD_APP };""")
    # CV link (2026-11-05): every link into the old app carries the 2.0 marker ?from=app before its # (src/links.js OLD_APP)
    assert links == {"macro": "./baepsae.html?from=app#macro", "disc": "./baepsae.html?from=app#disc",
                     "glossary": "./baepsae.html?from=app#info=glossary", "sources": "./baepsae.html?from=app#info=sources",
                     "corp": "./baepsae.html?from=app#corp=005930", "hash": "#portfolio/build", "old": "./baepsae.html?from=app"}


def test_the_old_app_reads_only_its_own_deep_links():
    got = run("""out = Object.fromEntries(H.map((h) => [h, D.readDeepLink(h)]));""",
              H=["#macro", "#disc", "#corp=005930", "#corp=AAPL", "#info=glossary", "#info=sources", "", "#about", "#corp=",
                 "#corp=005930/x", "#corp=<script>", "#info=terms", "#macro/1", "#MACRO", "#corp=1234567890123"])
    assert got["#macro"] == {"tab": "macro"} and got["#disc"] == {"tab": "disc"}
    assert got["#corp=005930"] == {"tab": "corp", "corp": "005930"} and got["#corp=AAPL"] == {"tab": "corp", "corp": "AAPL"}
    assert got["#info=glossary"] == {"tab": "info", "info": "glossary"} and got["#info=sources"] == {"tab": "info", "info": "sources"}
    for h in ("", "#about", "#corp=", "#corp=005930/x", "#corp=<script>", "#info=terms", "#macro/1", "#MACRO", "#corp=1234567890123"):
        assert got[h] is None, h
    shell = open(os.path.join(ROOT, "src", "shell.jsx"), encoding="utf-8").read()
    assert 'import { readDeepLink } from "./deeplink.js"' in shell and "window.history.replaceState(window.history.state, \"\"" in shell
    assert "useState(takeDeepLink)" in shell and "navPush" in shell.split("function takeDeepLink", 1)[0]   # 바로가기는 기록을 쌓지 않아요


# ── 거래대금 상위 종목 ──
def test_popular_lists_are_split_by_market_in_the_pipelines_order_without_funds():
    stocks = [st("000660", "SK하이닉스"), st("005930", "삼성전자"), st("069500", "KODEX 200", etf=True), st("000270", "기아"),
              st("NVDA", "NVIDIA Corporation", "us"), st("SPY", "SPDR S&P 500", "us", etf=True), st("AAPL", "Apple Inc.", "us")]
    data = {"pxDate": "2026-11-02", "usPxDate": "2026-10-31", "stocks": stocks,
            "popular": ["000660", "069500", "005930", "GONE", "000270", "SPY", "NVDA", "AAPL"]}
    got = run("""out = { two: L.popularLists(loadOf(DATA), 2), all: L.popularLists(loadOf(DATA)), none: L.popularLists(loadOf({ ...DATA, popular: [] })),
      missing: L.popularLists(loadOf({ ...DATA, popular: undefined })), fail: L.popularLists({ status: 'fail' }) };
      for (const k of ['two', 'all']) out[k] = { kr: out[k].kr.map((s) => s.t), us: out[k].us.map((s) => s.t), krDate: out[k].krDate, usDate: out[k].usDate };""",
              DATA=data)
    assert got["two"] == {"kr": ["000660", "005930"], "us": ["NVDA", "AAPL"], "krDate": "2026-11-02", "usDate": "2026-10-31"}, got["two"]
    assert got["all"]["kr"] == ["000660", "005930", "000270"] and got["all"]["us"] == ["NVDA", "AAPL"], got["all"]
    assert got["none"] is None and got["missing"] is None and got["fail"] is None


# ── 시장 네 칸 ──
def rows(*xs):
    return [[d, v] for d, v in xs]


def test_market_tiles_show_two_changes_and_two_levels_each_with_its_own_date():
    data = {"pxDate": "2026-11-02", "fx": 1325.5, "fxDate": "2026-11-02", "stocks": [st("000660", "SK하이닉스")]}
    macro = {"idxHist": {"KOSPI": {"asOf": "2026-11-02", "rows": rows(("2026-10-30", 5730.74), ("2026-11-02", 5859.08))},
                         "SP500": {"asOf": "2026-10-31", "rows": rows(("2026-10-30", 7580.07), ("2026-10-31", 7541.4))}},
             "curve": {"tenors": [1, 2, 3, 5], "now": [3.59, 3.72, 3.74, 3.89], "ago": [2.4, 2.6, 2.7, 2.8], "date": "2026-11-01"}}
    got = run("""
const base = L.marketTiles(loadOf(DATA, MACRO));
const noMacro = L.marketTiles(loadOf(DATA, null));
const bad = L.marketTiles(loadOf({ ...DATA, fx: null }, { ...MACRO, idxHist: { KOSPI: { rows: [['2026-11-02', 5859.08], ['2026-10-30', 5730.74]] },
  SP500: { rows: [['2026-11-02', 7541.4]] } }, curve: { ...MACRO.curve, date: null } }));
const noFxDate = L.marketTiles(loadOf({ ...DATA, fxDate: undefined }, MACRO));
out = { base, noMacro, bad, noFxDate, fail: L.marketTiles({ status: 'fail' }) };""", DATA=data, MACRO=macro)
    b = {x["id"]: x for x in got["base"]}
    assert [x["id"] for x in got["base"]] == ["kospi", "sp500", "kr3y", "usdkrw"]
    assert b["kospi"]["value"] == 5859.08 and abs(b["kospi"]["change"] - (5859.08 / 5730.74 - 1) * 100) < 1e-9 and b["kospi"]["date"] == "2026-11-02"
    assert b["sp500"]["value"] == 7541.4 and b["sp500"]["change"] < 0 and b["sp500"]["date"] == "2026-10-31"     # 미국은 자기 날짜
    assert b["kr3y"] == {"id": "kr3y", "kind": "rate", "value": 3.74, "date": "2026-11-01", "why": None, "change": None}  # 수준만
    assert b["usdkrw"] == {"id": "usdkrw", "kind": "fx", "value": 1325.5, "change": None, "date": "2026-11-02", "why": None}
    n = {x["id"]: x for x in got["noMacro"]}
    for k in ("kospi", "sp500", "kr3y"):
        assert n[k]["value"] is None and n[k]["date"] is None and n[k]["why"] == "macro", (k, n[k])
    assert n["usdkrw"]["value"] == 1325.5                                         # 원/달러는 data.json 에서
    x = {t["id"]: t for t in got["bad"]}
    assert x["kospi"]["value"] is None and x["kospi"]["why"] == "rows", x["kospi"]       # 날짜 순서가 틀린 기록은 쓰지 않아요
    assert x["sp500"]["value"] == 7541.4 and x["sp500"]["change"] is None, x["sp500"]   # 종가가 하나면 변화 없음
    assert x["kr3y"]["value"] is None and x["usdkrw"]["value"] is None, x                # 날짜가 없거나 값이 없으면 '–'
    assert {t["id"]: t["value"] for t in got["noFxDate"]}["usdkrw"] is None
    assert all(t["value"] is None and t["change"] is None for t in got["fail"])


# ── 찾기 · 내 포트폴리오 종목 ──
def test_search_puts_exact_codes_and_names_first_and_keeps_funds():
    stocks = [st("005930", "삼성전자", cap=400.0), st("005935", "삼성전자우", cap=40.0), st("009150", "삼성전기", cap=20.0),
              st("028260", "삼성물산", cap=None), st("069500", "KODEX 200", etf=True), st("AAPL", "Apple Inc.", "us", cap=500.0),
              st("APP", "AppLovin", "us", cap=100.0), st("BND", "Bond Fund", "bond")]
    got = run("""const ld = loadOf({ stocks: STOCKS });
out = { sam: L.searchStocks(ld, '삼성').map((s) => s.t), exact: L.searchStocks(ld, '삼성전자').map((s) => s.t), code: L.searchStocks(ld, '0059').map((s) => s.t),
  app: L.searchStocks(ld, 'app').map((s) => s.t), kodex: L.searchStocks(ld, 'kodex').map((s) => s.t), bond: L.searchStocks(ld, 'bond'),
  empty: L.searchStocks(ld, '   '), two: L.searchStocks(ld, '삼성', 2).length, fail: L.searchStocks({ status: 'fail' }, '삼성') };""", STOCKS=stocks)
    assert got["sam"] == ["005930", "005935", "009150", "028260"], got["sam"]     # 시가총액 큰 순, 빈 칸은 맨 뒤
    assert got["exact"] == ["005930", "005935"] and got["code"] == ["005930", "005935"], got
    assert got["app"] == ["APP", "AAPL"], got["app"]                              # 같은 코드가 먼저
    assert got["kodex"] == ["069500"] and got["bond"] == [] and got["empty"] == [] and got["two"] == 2 and got["fail"] == []


def test_my_stocks_lists_each_bought_stock_once():
    decks = [{"id": "a", "holdings": [{"t": "005930", "nk": "삼성전자(저장)"}, {"t": "000270", "nk": "기아"}, {"t": "GONE", "nk": "사라진 회사", "cls": "kr"}],
              "purchases": [{"t": "005930", "qty": 1}, {"t": "GONE", "qty": 2}]},
             {"id": "b", "holdings": [{"t": "005930", "nk": "삼성전자"}, {"t": "AAPL", "nk": "Apple"}], "purchases": [{"t": "005930", "qty": 3}, {"t": "AAPL", "qty": 1}]}]
    got = run("""out = L.myStocks(DECKS, loadOf({ stocks: STOCKS })).map((x) => [x.t, x.nk, x.cls, !!x.s]);""", DECKS=decks,
              STOCKS=[st("005930", "삼성전자"), st("AAPL", "Apple Inc.", "us")])
    assert got == [["005930", "삼성전자", "kr", True], ["GONE", "사라진 회사", "kr", False], ["AAPL", "Apple Inc.", "us", True]], got


# ── 예전에 저장한 기본 이름 · 포트폴리오에서 빼기 ──
def test_names_saved_before_v19_0c_are_shown_with_the_new_word_only():
    got = run("""out = Object.fromEntries(N.map((n) => [n, G.shownName(n)]));""",
              N=["배당 생활비 덱", "꾸준한 고배당 덱", "내 덱", "내 덱 2", "나의 덱", "배당 생활비", "배당 생활비 포트폴리오", "덱"])
    assert got["배당 생활비 덱"] == "배당 생활비 포트폴리오" and got["꾸준한 고배당 덱"] == "꾸준한 고배당 포트폴리오"
    assert got["내 덱"] == "포트폴리오"
    for n in ("내 덱 2", "나의 덱", "배당 생활비", "배당 생활비 포트폴리오", "덱"):     # 직접 적은 이름은 그대로 (정확히 같을 때만)
        assert got[n] == n, n


def test_remove_takes_out_one_stock_of_one_portfolio_and_nothing_else():
    data = {"v": 1, "decks": [
        {"id": "a", "name": "A", "holdings": [{"t": "STRC", "nk": "Strategy"}, {"t": "005930", "nk": "삼성전자"}],
         "purchases": [{"t": "STRC", "qty": 2, "price": 100, "date": "2026-10-01", "ccy": "USD", "fx": 1300},
                       {"t": "005930", "qty": 1, "price": 50000, "date": "2026-10-01", "ccy": "KRW"}],
         "confirms": [{"t": "STRC", "rule": "divCut", "fy": 2025, "a": 2, "b": 1, "answer": "cut", "at": "2026-10-02"}]},
        {"id": "b", "name": "B", "holdings": [{"t": "STRC", "nk": "Strategy"}], "purchases": [{"t": "STRC", "qty": 1, "price": 100, "date": "2026-10-01", "ccy": "USD"}]}]}
    got = run("""const n = S.withoutHolding(DATA, 'a', 'STRC');
out = { n, valid: S.validStore(n, '2026-11-03'), same: S.withoutHolding(DATA, 'a', 'NOPE'), noDeck: S.withoutHolding(DATA, 'z', 'STRC'),
  last: S.withoutHolding(S.withoutHolding(DATA, 'a', 'STRC'), 'a', '005930'), untouched: JSON.stringify(DATA) === ORIG };""",
              DATA=data, ORIG=json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    a = got["n"]["decks"][0]
    assert [h["t"] for h in a["holdings"]] == ["005930"] and [p["t"] for p in a["purchases"]] == ["005930"] and a["confirms"] == [], a
    assert got["n"]["decks"][1] == data["decks"][1] and got["valid"] is True and got["untouched"] is True   # 다른 포트폴리오 · 원본은 그대로
    assert got["same"] is None and got["noDeck"] is None
    assert got["last"]["decks"][0]["holdings"] == [] and len(got["last"]["decks"]) == 2      # 포트폴리오는 남아요 (종목 0개)


def test_missing_line_names_each_stock_with_its_money_put_in():
    got = run("""out = { two: V.missingNames([{ t: 'STRC', nk: 'Strategy Inc', cls: 'us', cost: 2000000 }, { t: '005930', nk: '삼성전자', cls: 'kr', cost: 1234567 }]),
      noCost: V.missingNames([{ t: '000660', nk: 'SK하이닉스', cls: 'kr', cost: null }]), noName: V.missingNames([{ t: '000660', cls: 'kr', cost: 50000 }]),
      line: T.C.fill(CP.missing.line, { n: 1, names: V.missingNames([{ t: 'STRC', cls: 'us', cost: 2000000 }]) }) };""")
    assert got["two"] == "STRC 200만원, 삼성전자 123만원", got["two"]             # 미국은 티커, 한국은 이름 · 만원
    assert got["noCost"] == "SK하이닉스" and got["noName"] == "000660 5만원", got
    assert got["line"] == "오늘 데이터에 없는 종목 1개(STRC 200만원)는 빼고 계산했어요.", got["line"]   # 예전 뱁새와 같은 문장 · 같은 꼴


# ── 최근 본 종목 ──
def test_recently_viewed_keeps_eight_codes_newest_first_and_survives_broken_storage():
    got = run("""
const mem = {}; let broken = false;
globalThis.localStorage = { getItem: (k) => { if (broken) throw new Error('blocked'); return k in mem ? mem[k] : null; },
  setItem: (k, v) => { if (broken) throw new Error('blocked'); mem[k] = String(v); } };
for (const t of ['A', 'B', 'C', 'A', 'D', 'E', 'F', 'G', 'H', 'I']) Q.addRecent(t);
const list = Q.readRecent();
const preview = Q.addRecent('P', Q.PREVIEW_RECENT_KEY);
mem[Q.RECENT_KEY] = '{"not":"a list"}';
const junk = Q.readRecent();
mem[Q.RECENT_KEY] = JSON.stringify(['ok', 5, null, 'x'.repeat(30), 'ok2']);
const mixed = Q.readRecent();
broken = true;
out = { list, preview, live: JSON.parse(mem[Q.RECENT_KEY]).length, junk, mixed, blockedRead: Q.readRecent(), blockedAdd: Q.addRecent('Z') };""")
    assert got["list"] == ["I", "H", "G", "F", "E", "D", "A", "C"], got["list"]   # 최신이 먼저, 8개, 같은 종목은 한 번
    assert got["preview"] == ["P"] and got["live"] == 5, got                       # 미리 보기는 자기 열쇠
    assert got["junk"] == [] and got["mixed"] == ["ok", "ok2"] and got["blockedRead"] == [] and got["blockedAdd"] == ["Z"], got


# ── 아이폰 홈 화면 안내: 아이폰 사파리에서만 ──
SAFARI = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"


def test_the_home_screen_hint_is_for_iphone_safari_only():
    uas = {
        "safari": SAFARI,
        "ipod": SAFARI.replace("(iPhone;", "(iPod touch;"),
        "chrome-ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.6723.90 Mobile/15E148 Safari/604.1",
        "firefox-ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/132.0 Mobile/15E148 Safari/605.1.15",
        "kakao": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 KAKAOTALK 10.8.5",
        "naver": SAFARI + " NAVER(inapp; search; 2000; 12.10.1)",
        "ipad": SAFARI.replace("iPhone; CPU iPhone OS", "iPad; CPU OS"),
        "android": "Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    }
    got = run("""out = Object.fromEntries(Object.entries(UAS).map(([k, ua]) => [k, S.iphoneSafari({ userAgent: ua }, false)]));
out.standaloneNav = S.iphoneSafari({ userAgent: UAS.safari, standalone: true }, false);
out.standaloneMedia = S.iphoneSafari({ userAgent: UAS.safari }, true);""", UAS=uas)
    assert got["safari"] is True and got["ipod"] is True, got
    for k in ("chrome-ios", "firefox-ios", "kakao", "naver", "ipad", "android", "mac"):
        assert got[k] is False, k
    assert got["standaloneNav"] is False and got["standaloneMedia"] is False      # 홈 화면 앱 안에서는 안 보여요
