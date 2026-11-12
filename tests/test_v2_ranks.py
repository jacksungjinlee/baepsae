# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.5b 홈 · 종목 순위 (src/v2/ranks.js) — Node 로 직접 돌려봐요.

docs/tasks/v19.5-home-lists-and-icon.md Part A 의 일곱 목록:
- 모든 목록: 시장마다 따로 · ETF · 펀드 · 우선주(한국 코드 · 미국 이름/티커) · 가격 없는 종목 · 거래대금 기준(한국 val20 · 미국 val,
  5억 미만이거나 빈 칸) 빼고 · 목록의 숫자가 빈 칸이면 빼요(0 으로 순위를 매기지 않아요) · 같은 숫자는 시가총액 큰 순 · 미국의 같은
  회사 두 종류 주식은 한 줄
- 시가총액 cap · 거래대금 val · 거래 급증(한국만, val ÷ val20 이 2배 이상이고 시가총액 3,000억원 이상, 없으면 빈 목록) ·
  기준별(카드의 기준 줄이 말하는 값, 카드의 방향, 금융회사 재무 안정은 해당 없음 → 빠짐, PBR 0 이하는 빠짐) ·
  내 기준(마지막 포트폴리오의 점수와 빼기, 깐깐함 · 한미 비중은 안 씀, '상위 x%' = 빼기 전 시장 전체에서의 백분위) ·
  배당수익률(한국은 확인한 dyt 만, 미국은 야후 dy, 재무 경고 신호) · 업종별 등락(5곳 이상, 평균은 왜 움직였나의 peerGroup 그대로)
- 칩: 일곱 개 순서, 미국에서는 거래 급증 없음, 기준 점수가 있는 포트폴리오가 없으면 내 기준 없음 · 고른 것은 이 기기에 (try/catch)
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
MODS = {"K": "src/v2/ranks.js", "E": "src/v2/engine.js", "T": "src/v2/track.js"}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/ranks.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as M from './ranks.mjs';\nconst { K, E, T } = M;\nconsole.warn = () => {}; console.info = () => {};\n"
            "const loadOf = (data, corp = []) => ({ status: 'ok', data, byT: new Map(data.stocks.map((s) => [s.t, s])), coByT: new Map(corp.map((c) => [c.t, c])) });\n"
            "const ts = (rows) => rows.map((r) => r.s.t);\n"
            + decl + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def st(t, cls="kr", **kw):
    """시험 종목: 기본은 목록에 들어가는 종목 (가격 · 시가총액 · 거래대금 기준 통과 · 오늘 변화)."""
    s = {"t": t, "nk": kw.pop("nk", t), "cls": cls, "price": 1000.0, "cap": 1.0, "val": 100.0, "d1": 0.5, "etf": False}
    if cls == "kr":
        s["val20"] = 100.0
    s.update(kw)
    return s


# ── 모든 목록의 바탕: 시장 · 우주 · 거래대금 기준 ──
def test_lists_keep_to_one_market_and_the_build_universe_over_the_trading_value_floor():
    stocks = [st("000010", cap=5.0), st("000020", cap=4.0), st("000025", cap=9.0),                 # 000025: 한국 우선주 (코드가 0 으로 안 끝나요)
              st("069500", cap=50.0, etf=True), st("000030", cap=30.0, fund=True),                # ETF · 펀드
              st("000040", cap=8.0, price=None), st("000050", cap=7.0, val20=4.9),                 # 가격 없음 · 20일 평균 5억 미만
              st("000060", cap=6.0, val20=None), st("000070", cap=3.0, val20=5.0, val=0.5),       # 20일 평균 빈 칸 · 딱 5억 (오늘 거래대금은 안 봐요)
              st("AAA", "us", cap=900.0), st("BBB", "us", cap=800.0, val=4.0),                   # 미국은 val(3개월 평균)로 기준
              st("STRC", "us", cap=700.0, nk="Strategy Inc 10% Series A Preferred Stock"),         # 미국 우선주 (이름)
              st("CCC-P", "us", cap=600.0), st("DDD", "us", cap=500.0, val=None),                # 미국 우선주 (티커) · val 빈 칸
              {"t": "153130", "nk": "채권", "cls": "bond", "price": 1.0, "cap": 99.0, "val": 999.0}]
    got = run("""const S = STOCKS;
out = { kr: ts(K.capList(S, 'kr')), us: ts(K.capList(S, 'us')), base: K.rankBase(S, 'kr').map((s) => s.t), floor: [E.LIQ_FLOOR_EOK] };""",
              STOCKS=stocks)
    assert got["floor"] == [5]
    assert got["kr"] == ["000010", "000020", "000070"], got["kr"]                 # 시가총액 큰 순, 빼야 할 것은 모두 빠짐
    assert got["us"] == ["AAA"], got["us"]
    assert sorted(got["base"]) == ["000010", "000020", "000070"]


def test_a_blank_number_is_left_out_never_ranked_as_zero_and_ties_go_by_market_cap():
    stocks = [st("000010", cap=2.0, val=50.0), st("000020", cap=None, val=900.0), st("000030", cap=3.0, val=50.0),
              st("000040", cap=1.0, val=None), st("000050", cap=0.5, val=0.0), st("000060", cap=3.0, val=50.0)]
    got = run("""out = { cap: ts(K.capList(STOCKS, 'kr')), val: ts(K.valList(STOCKS, 'kr')) };""", STOCKS=stocks)
    assert got["cap"] == ["000030", "000060", "000010", "000040", "000050"], got["cap"]      # 시가총액 빈 칸은 빠지고, 같은 값은 코드 순
    assert got["val"] == ["000020", "000030", "000060", "000010", "000050"], got["val"]      # 같은 거래대금: 시가총액 큰 순 · 0 은 숫자 · 빈 칸은 빠짐


def test_one_row_per_company_for_us_share_classes():
    stocks = [st("GOOGL", "us", nk="Alphabet Inc.", cap=4828.0, price=300.0), st("GOOG", "us", nk="Alphabet Inc.", cap=4781.6, price=297.1),
              st("FOXA", "us", nk="Fox Corporation", cap=30.0, price=60.0), st("FOX", "us", nk="Fox Corporation", cap=28.0, price=55.0),
              st("MSFT", "us", nk="Microsoft Corporation", cap=5000.0)]
    got = run("""out = ts(K.capList(STOCKS, 'us'));""", STOCKS=stocks)
    assert got == ["MSFT", "GOOGL", "FOXA", "FOX"], got          # 같은 회사(이름 · 총 주식 수 같음)는 위의 한 줄만, 주식 수가 다르면 둘 다


# ── 거래대금: 종목 탭의 '거래대금 상위 종목' 을 대신해요 ──
def test_trading_value_is_the_days_value_in_korea_and_yahoos_average_in_the_us():
    stocks = [st("000010", val=3000.0, val20=100.0), st("000020", val=200.0, val20=9000.0), st("AAA", "us", val=500.0), st("BBB", "us", val=800.0)]
    data = {"pxDate": "2026-11-11", "usPxDate": "2026-11-10", "stocks": stocks}
    got = run("""const ld = loadOf(DATA);
out = { kr: ts(K.rankRows(ld, 'kr', 'val').rows), us: ts(K.rankRows(ld, 'us', 'val').rows), fail: K.rankRows({ status: 'fail' }, 'kr', 'val') };""",
              DATA=data)
    assert got["kr"] == ["000010", "000020"] and got["us"] == ["BBB", "AAA"] and got["fail"] is None, got


# ── 거래 급증 ──
def test_surge_needs_twice_the_20_day_average_and_3000_eok_of_market_cap():
    stocks = [st("000010", val=600.0, val20=100.0, cap=0.3), st("000020", val=200.0, val20=100.0, cap=5.0),     # 6배 · 딱 3,000억 / 딱 2배
              st("000030", val=199.0, val20=100.0, cap=5.0), st("000040", val=900.0, val20=100.0, cap=0.29),    # 2배 미만 / 3,000억 미만
              st("000050", val=500.0, val20=100.0, cap=None), st("000060", val=None, val20=100.0, cap=2.0),     # 시가총액 빈 칸 / 거래대금 빈 칸
              st("000070", val=400.0, val20=100.0, cap=9.0), st("000080", val=400.0, val20=100.0, cap=2.0)]     # 같은 4배: 시가총액 큰 순
    got = run("""out = { kr: K.surgeList(STOCKS, 'kr').map((r) => [r.s.t, Math.round(r.v * 100) / 100]), us: K.surgeList(STOCKS, 'us'),
  none: K.surgeList(NONE, 'kr'), x: [K.SURGE_X, K.SURGE_CAP_JO] };""", STOCKS=stocks, NONE=[st("000010", val=150.0, val20=100.0, cap=9.0)])
    assert got["kr"] == [["000010", 6], ["000070", 4], ["000080", 4], ["000020", 2]], got["kr"]
    assert got["us"] is None and got["none"] == [] and got["x"] == [2, 0.3], got      # 미국은 없음 · 없는 날은 빈 목록(화면이 승인 문구)


# ── 기준별 ──
def test_criteria_table_follows_the_engine_cards():
    got = run("""out = { crit: K.CRIT, cards: E.CARDS.filter((c) => !c.pending).map((c) => ({ id: c.id, f: c.field, dir: c.dir, finNA: !!c.finNA })) };""")
    crit = {c["id"]: c for c in got["crit"]}
    cards = {c["id"]: c for c in got["cards"]}
    assert [c["id"] for c in got["crit"]] == ["value", "profit", "stable", "lowVol", "trend", "growth"]   # 배당 · 대형주는 자기 칩, 준비 중 카드 없음
    # 카드의 점수 필드 → 그 점수가 나온 실제 값 (fetch_data.add_percentiles: vz = 100 − pbr 백분위, lz = 100 − vol, mz = mom)
    named = {"vz": ("pbr", -1), "lz": ("vol", -1), "mz": ("mom", 1)}
    for cid, c in crit.items():
        card = cards[cid]
        f, flip = named.get(card["f"]["kr"], (card["f"]["kr"], 1))
        assert card["f"]["kr"] == card["f"]["us"], cid
        assert (c["field"], c["dir"], bool(c.get("finNA"))) == (f, card["dir"] * flip, card["finNA"]), cid
    fd = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert '"vz": 100 - pr("pbr")' in fd and '"mz": pr("mom")' in fd and '"lz": 100 - pr("vol")' in fd


def test_each_criterion_ranks_by_its_named_value_in_the_cards_direction():
    stocks = [st("000010", cap=1.0, pbr=0.5, roe=10.0, debt=50.0, vol=30.0, mom=20.0, g3=5.0),
              st("000020", cap=2.0, pbr=0.3, roe=25.0, debt=10.0, vol=20.0, mom=-5.0, g3=40.0, ind="bank"),
              st("000030", cap=3.0, pbr=0.5, roe=None, debt=80.0, vol=25.0, mom=90.0, g3=None),
              st("000040", cap=4.0, pbr=0.0, roe=12.0, debt=None, vol=None, mom=None, g3=1.0),
              st("000050", cap=5.0, pbr=-0.4, roe=-3.0, debt=0.0, vol=40.0, mom=1.0, g3=-10.0)]
    # 성장 · 수익성의 기준은 모두 통과: 매출은 그 g3 가 2년 연평균이 되게 (전전기 120억원), 자본 500억원
    corp = [{"t": x["t"], "rev": [round(120.0 * (1 + (x.get("g3") or 0) / 100) ** 2, 1), 150.0, 120.0], "eq": 500.0} for x in stocks]
    got = run("""const CO = new Map(CORP.map((c) => [c.t, c]));
out = Object.fromEntries(K.CRIT.map((c) => [c.id, ts(K.critList(STOCKS, 'kr', c.id, CO))])); out.none = K.critList(STOCKS, 'kr', 'div');""",
              STOCKS=stocks, CORP=corp)
    assert got["value"] == ["000020", "000030", "000010"], got["value"]           # PBR 낮은 순 · 같은 0.5 는 시가총액 큰 순 · 0 이하는 빠짐
    assert got["profit"] == ["000020", "000040", "000010", "000050"], got["profit"]   # ROE 높은 순 · 빈 칸 빠짐
    assert got["stable"] == ["000050", "000010", "000030"], got["stable"]         # 부채 낮은 순 · 은행(000020)은 해당 없음 → 빠짐
    assert got["lowVol"] == ["000020", "000030", "000010", "000050"], got["lowVol"]
    assert got["trend"] == ["000030", "000010", "000050", "000020"], got["trend"]
    assert got["growth"] == ["000020", "000010", "000040", "000050"], got["growth"]
    assert got["none"] is None


# ── 내 기준 ──
def _deck(i, points, exclude=None, kind="built", strict="very", mix="us"):
    return {"id": f"d{i}", "name": f"P{i}", "kind": kind, "settings": {"points": points, "strict": strict, "mix": mix, "pinned": ["000010"],
            "exclude": {"loss": False, "debt": False, "noDiv": False, "holding": False, **(exclude or {})}}}


def test_mine_uses_the_latest_portfolio_with_points_its_exclusions_but_not_its_strictness_or_mix():
    decks = [_deck(1, {"value": 5}), _deck(2, {"profit": 4, "value": 1}, {"loss": True}), _deck(3, {"divGrowth": 3}), {"id": "d4", "kind": "imported"},
             _deck(5, {})]
    # 가치 카드는 파이프라인의 vz(PBR 백분위)를 읽어요 (engine.CARDS)
    stocks = [st("000010", vz=70, roe=20.0, opm=10.0, cap=1.0), st("000020", vz=50, roe=30.0, opm=-2.0, cap=2.0),   # 000020: 영업손실 → 빼기
              st("000030", vz=20, roe=10.0, opm=3.0, cap=3.0), st("000040", vz=60, roe=None, opm=5.0, cap=4.0),     # 000040: ROE 빈 칸 → 점수 없음
              st("000050", vz=90, roe=15.0, opm=2.0, cap=5.0, val20=1.0),                                          # 000050: 거래대금 미달
              st("AAA", "us", vz=10, roe=40.0, opm=10.0), st("BBB", "us", vz=60, roe=10.0, opm=10.0)]
    got = run("""const d = K.pointsDeck(DECKS);
const pc = K.criteriaPct(STOCKS, 'kr', d.settings.points);
out = { id: d.id, none: K.pointsDeck([DECKS[2], DECKS[3], DECKS[4]]), empty: K.pointsDeck([]),
  kr: K.mineList(STOCKS, 'kr', d.settings).map((r) => [r.s.t, r.pct]), us: ts(K.mineList(STOCKS, 'us', d.settings)),
  pct: Object.fromEntries([...pc.entries()]), noSettings: K.mineList(STOCKS, 'kr', null),
  report: [K.mineUsesReport({ profit: 1 }), K.mineUsesReport({ lowVol: 3, trend: 2 }), K.mineUsesReport({ div: 1 })] };""",
              DECKS=decks, STOCKS=stocks)
    assert got["id"] == "d2" and got["none"] is None and got["empty"] is None           # 점수가 있는 마지막 포트폴리오 (준비 중 카드만 · 점수 없음은 아님)
    # 빼기(적자)는 적용, 깐깐함('very' 상위 10%)과 한미 비중('us' 미국만)은 아님, 꼭 담을 종목(000010)도 그대로 순위에
    assert [t for t, _ in got["kr"]] == ["000010", "000030"], got["kr"]
    assert got["us"] == ["AAA", "BBB"], got["us"]                                      # 한국만 정한 포트폴리오도 미국 목록이 있어요
    # '상위 x%' 는 빼기 · 거래대금 기준 전의 시장 전체(점수가 있는 종목)에서: 000020 · 000050 도 순위에 있어요, 000040 은 없어요
    assert set(got["pct"]) == {"000010", "000020", "000030", "000050"}, got["pct"]
    assert dict(got["kr"]) == {"000010": got["pct"]["000010"], "000030": got["pct"]["000030"]}
    assert got["pct"]["000020"] == 25 and got["pct"]["000030"] == 100, got["pct"]      # 총점 1등 → 상위 25% (4개 중), 꼴찌 → 100%
    assert got["noSettings"] is None and got["report"] == [True, False, True]


def test_mine_percentile_is_the_engines_own_total():
    stocks = [st(f"0000{i}0", vz=100 - 10 * i, roe=float(i * 3 % 7), debt=float(i * 13 % 11) * 10, cap=float(i)) for i in range(1, 9)] + \
             [st("000090", vz=55, roe=4.0, debt=1.0, ind="bank", cap=0.5)]
    pts = {"value": 3, "profit": 2, "stable": 5}
    got = run("""const r = E.screen(STOCKS, { points: PTS, strict: 'loose', mix: 'kr', pinned: [], exclude: {} });
const pc = K.criteriaPct(STOCKS, 'kr', PTS);
const tot = r.markets.kr.survivors.map((x) => [x.t, x.total]).sort((a, b) => a[1] - b[1]);
out = { order: tot.map(([t]) => t), pct: tot.map(([t]) => pc.get(t)), list: ts(K.mineList(STOCKS, 'kr', { points: PTS, exclude: {} })) };""",
              STOCKS=stocks, PTS=pts)
    assert len(got["order"]) == 9 and "000090" in got["order"]                          # 금융회사는 재무 안정 해당 없음: 나머지 카드로 점수
    assert got["pct"] == sorted(got["pct"], reverse=True) and got["pct"][-1] == min(got["pct"]), got   # 총점이 높을수록 '상위' 숫자가 작아요
    assert got["list"] == list(reversed(got["order"])), got["list"]


def test_chips_in_jacks_order_with_surge_korea_only_and_mine_only_with_points():
    got = run("""out = { kr: K.chipsFor('kr', true), us: K.chipsFor('us', true), noMine: K.chipsFor('kr', false), usNoMine: K.chipsFor('us', false),
  shown: [K.shownChip('surge', K.chipsFor('us', true)), K.shownChip('mine', K.chipsFor('kr', false)), K.shownChip('ind', K.chipsFor('kr', true))] };""")
    assert got["kr"] == ["cap", "val", "surge", "crit", "mine", "div", "ind"]
    assert got["us"] == ["cap", "val", "crit", "mine", "div", "ind"]
    assert got["noMine"] == ["cap", "val", "surge", "crit", "div", "ind"]
    assert got["usNoMine"] == ["cap", "val", "crit", "div", "ind"]                     # 목록이 비어도 칩은 그대로 (Jack, 2026-11-12: 빈 목록은 이유를 말해요)
    assert got["shown"] == ["cap", "cap", "ind"]                                          # 없는 칩을 골라 뒀으면 첫 칩


# ── 배당수익률 ──
def test_dividend_list_korea_verified_only_us_yahoo_and_the_warning_chip():
    stocks = [st("000010", dyt=5.1, cap=1.0), st("000020", dyt=None, dy=9.0, cap=2.0), st("000030", dyt=7.0, cap=3.0), st("000040", dyt=31.0),
              st("000050", dyt=0.0), st("AAA", "us", dy=3.2), st("BBB", "us", dy=None), st("CCC", "us", dy=40.0), st("DDD", "us", dy=6.0)]
    corp = [{"t": "000030", "fl": {"cr": 57.0}}, {"t": "000010", "fl": None}]
    got = run("""E.setDataShape({ divCheck: { v: 1 } });
const ld = loadOf({ pxDate: '2026-11-11', usPxDate: '2026-11-11', stocks: STOCKS }, CORP);
const kr = K.rankRows(ld, 'kr', 'div').rows.map((r) => [r.s.t, r.v, r.warn]);
const us = K.rankRows(ld, 'us', 'div').rows.map((r) => [r.s.t, r.v, r.warn]);
E.setDataShape({});
out = { kr, us, old: K.rankRows(ld, 'kr', 'div').rows.length };""", STOCKS=stocks, CORP=corp)
    assert got["kr"] == [["000030", 7.0, True], ["000010", 5.1, False], ["000050", 0.0, False]], got["kr"]   # 확인 못 한(빈 칸) · 30% 넘는 값은 빠짐
    assert got["us"] == [["DDD", 6.0, False], ["AAA", 3.2, False]], got["us"]                                # 미국은 야후 dy (재무 경고 신호 없음)
    assert got["old"] == 0                                                         # 분할 확인 전 파일(divCheck 없음): 한국 목록은 비어요


# ── 업종별 등락 ──
def test_industry_groups_average_exactly_like_why_it_moved():
    d = [0.4, -1.2, 2.5, 0.3, -0.1, 1.1]
    stocks = [st(f"0001{i}0", ind="semi", indName="반도체", d1=d[i], cap=float(10 - i)) for i in range(6)]
    stocks += [st(f"0002{i}0", ind="bank", indName="은행", d1=-0.5 - i * 0.1, cap=float(i + 1)) for i in range(5)]
    stocks += [st(f"0003{i}0", ind="food", indName="음식료", d1=0.2) for i in range(4)]                   # 4곳: 빠짐
    stocks += [st(f"0004{i}0", ind="etc", indName="기타", d1=3.0) for i in range(6)]                      # '기타'는 업종이 아니에요
    stocks += [st("000500", ind="semi", d1=None, cap=50.0), st("000510", ind="semi", d1=9.9, val20=1.0, cap=0.1),   # 오늘 변화 없음 / 거래대금 미달(평균엔 들어가요)
               st("000525", ind="semi", d1=9.9), st("AAA", "us", ind="semi", d1=5.0)]                     # 우선주 · 미국은 빠짐
    got = run("""const g = K.indGroups(STOCKS, 'kr');
out = { groups: g.map((x) => ({ ind: x.ind, name: x.name, n: x.n, rose: x.rose, fell: x.fell, avg: x.avg, members: x.members.map((s) => s.t) })),
  peer: g.map((x) => T.peerGroup(x.members[0], STOCKS).avg), words: g.map(K.groupWord), list: ts(K.groupList(STOCKS, 'kr', 'bank')),
  none: K.groupList(STOCKS, 'kr', 'food'), min: K.GROUP_MIN };""", STOCKS=stocks)
    assert got["min"] == 5
    g = got["groups"]
    assert [x["ind"] for x in g] == ["semi", "bank"], g                                # 평균이 높은 업종부터
    assert [x["avg"] for x in g] == got["peer"], (g, got["peer"])                    # 왜 움직였나의 업종 평균과 똑같은 수
    semi = g[0]
    assert semi["n"] == 7 and semi["name"] == "반도체" and semi["rose"] == 5 and semi["fell"] == 2, semi
    assert semi["members"][0] == "000100" and "000510" in semi["members"] and "000500" not in semi["members"], semi["members"]   # 시가총액 큰 순
    assert got["words"] == [{"up": True, "k": 5}, {"up": False, "k": 5}]             # 평균이 오르면 '{k}개 오름', 내리면 '{k}개 내림'
    assert got["list"] == ["000240", "000230", "000220", "000210", "000200"] and got["none"] is None


# ── 고른 것은 이 기기에 ──
def test_the_choice_is_remembered_on_the_device_and_survives_broken_storage():
    got = run("""
const mem = {}; let broken = false;
globalThis.localStorage = { getItem: (k) => { if (broken) throw new Error('blocked'); return k in mem ? mem[k] : null; },
  setItem: (k, v) => { if (broken) throw new Error('blocked'); mem[k] = String(v); } };
const first = K.readPick();
const saved = K.savePick({ mk: 'us', chip: 'div', crit: 'trend' });
const back = K.readPick();
const preview = K.readPick(K.PREVIEW_RANK_KEY);
const bad = K.savePick({ mk: 'jp', chip: 'cap', crit: 'value' });
mem[K.RANK_KEY] = '{"mk":"kr","chip":"hot","crit":"value"}';
const junk = K.readPick();
mem[K.RANK_KEY] = 'not json';
const notJson = K.readPick();
broken = true;
out = { first, saved, back, preview, bad, junk, notJson, blockedRead: K.readPick(), blockedSave: K.savePick({ mk: 'kr', chip: 'cap', crit: 'value' }) };""")
    first = {"mk": "kr", "chip": "cap", "crit": "value"}
    assert got["first"] == first and got["saved"] is True and got["back"] == {"mk": "us", "chip": "div", "crit": "trend"}
    assert got["preview"] == first and got["bad"] is False                             # 미리 보기는 자기 열쇠 · 틀린 값은 저장하지 않아요
    assert got["junk"] == first and got["notJson"] == first and got["blockedRead"] == first and got["blockedSave"] is False


# ── v19.5b 리뷰 1차: 칩마다 '줄이 있는지'는 가벼운 검사로 (그 목록을 다 만들지 않고) · 그 검사는 목록과 늘 같아요 ──
def test_cheap_chip_checks_agree_with_the_lists():
    d = [0.4, -1.2, 2.5, 0.3, -0.1]
    base = [st(f"0001{i}0", ind="semi", d1=d[i], cap=float(10 - i), pbr=0.5 + i, roe=10.0 + i, debt=50.0, vol=30.0, mom=5.0, g3=1.0,
               opm=5.0, vz=50, dyt=2.0 + i) for i in range(5)]
    cases = {
        "full": base + [st("AAA", "us", ind="semi", dy=3.0, pbr=2.0, roe=10.0, debt=10.0, vol=20.0, mom=1.0, g3=1.0, opm=1.0, vz=40)],
        "sparse": [st("000010", cap=None, val=None, pbr=None, roe=None, debt=None, vol=None, mom=None, g3=None, d1=None, opm=-1.0, vz=None),
                   st("000020", ind="bank", debt=None, pbr=-1.0, opm=-2.0, vz=30, roe=5.0), st("BBB", "us", val=1.0, dy=None)],
        "empty": [st("000010", val20=1.0), st("CCC", "us", val=None)],
    }
    decks = {"none": None, "value": {"settings": {"points": {"value": 3}, "exclude": {}}},
             "loss-out": {"settings": {"points": {"value": 3}, "exclude": {"loss": True}}},
             "stable-fin": {"settings": {"points": {"stable": 5}, "exclude": {}}}}
    corps = {"full": [{"t": f"0001{i}0", "rev": [153.0, 151.5, 150.0] if i else [51.0, 50.5, 50.0], "eq": 500.0 if i != 2 else 80.0} for i in range(5)],
             "sparse": [], "empty": []}
    got = run("""E.setDataShape({ divCheck: { v: 1 } });
out = {};
const STATES = ['rows', 'none', 'nodata'];
for (const [name, stocks] of Object.entries(CASES)) {
  const ld = loadOf({ pxDate: '2026-11-11', usPxDate: '2026-11-11', stocks }, CORPS[name]);
  for (const mk of ['kr', 'us']) for (const [dn, deck] of Object.entries(DECKS)) {
    const s = K.chipState(ld, mk, deck);
    const has = (chip, crit = null) => { const r = K.rankRows(ld, mk, chip, crit, deck); return r ? r.rows.length > 0 : null; };
    const bad = [];
    for (const c of ['cap', 'val', 'div', 'ind']) if (!STATES.includes(s[c]) || (s[c] === 'rows') !== has(c)) bad.push(c);
    for (const c of K.CRIT) if (!STATES.includes(s.crit[c.id]) || (s.crit[c.id] === 'rows') !== has('crit', c.id)) bad.push('crit:' + c.id);
    if ((s.mine === null) !== (deck === null) || (deck && (!STATES.includes(s.mine) || (s.mine === 'rows') !== has('mine')))) bad.push('mine');
    if (mk === 'us' ? s.surge !== null : (s.surge === 'rows') !== has('surge')) bad.push('surge');
    out[name + '/' + mk + '/' + dn] = bad;
  }
}
E.setDataShape({});""", CASES=cases, DECKS=decks, CORPS=corps)
    assert all(v == [] for v in got.values()), {k: v for k, v in got.items() if v}
    assert len(got) == 24


def test_surge_with_no_figures_is_not_none_today():
    got = run("""out = {
  rows: K.surgeState([ { t: '000010', cls: 'kr', price: 1, cap: 1, val: 300, val20: 100, etf: false } ], 'kr'),
  none: K.surgeState([ { t: '000010', cls: 'kr', price: 1, cap: 1, val: 100, val20: 100, etf: false } ], 'kr'),
  noVal: K.surgeState([ { t: '000010', cls: 'kr', price: 1, cap: 1, val: null, val20: 100, etf: false },
                        { t: '000020', cls: 'kr', price: 1, cap: 1, val20: 50, etf: false } ], 'kr'),
  us: K.surgeState([ { t: 'AAA', cls: 'us', price: 1, cap: 1, val: 300, etf: false } ], 'us') };""")
    assert got["rows"] == {"state": "rows", "n": 1, "of": 1} and got["none"] == {"state": "none", "n": 1, "of": 1}
    assert got["noVal"] == {"state": "nodata", "n": 0, "of": 2} and got["us"] is None     # 숫자가 없으면 '오늘은 없어요'가 아니에요


def test_a_market_with_nothing_over_the_floor_has_no_data_at_all():
    got = run("""const ld = loadOf({ pxDate: '2026-11-11', usPxDate: '2026-11-11', stocks: STOCKS });
out = { us: K.chipState(ld, 'us', null), kr: K.chipState(ld, 'kr', null) };""", STOCKS=[st("000010"), st("AAA", "us", val=1.0), st("BBB", "us", val=None)])
    assert got["us"]["base"] == 0 and got["kr"]["base"] == 1, got                  # 화면: 칩 없이 불러오기 실패 문구 (smoke scene_rank_r1)
    assert got["us"]["cap"] == "nodata" and set(got["us"]["crit"].values()) == {"nodata"}
    assert got["us"]["ind"] == "none"                                               # 업종별 등락은 거래대금 기준 전의 종목으로 (왜 움직였나와 같은 셈): 5곳이 안 돼요


# ── 업종 안 회사: 같은 회사의 두 종류 주식은 한 줄 · 줄의 n · k 는 peerGroup 그대로 ──
def test_group_companies_once_per_company_but_the_count_stays_peer_groups():
    stocks = [st("GOOGL", "us", nk="Alphabet Inc.", ind="internet", cap=4828.0, price=300.0, d1=1.0),
              st("GOOG", "us", nk="Alphabet Inc.", ind="internet", cap=4781.6, price=297.1, d1=1.1)]
    stocks += [st(t, "us", ind="internet", cap=float(10 - i), d1=-0.5) for i, t in enumerate(("META", "NFLX", "SPOT", "PINS"))]
    got = run("""const g = K.indGroups(STOCKS, 'us')[0];
out = { n: g.n, rose: g.rose, members: g.members.map((s) => s.t), list: K.groupList(STOCKS, 'us', 'internet').map((r) => r.s.t),
  peer: T.peerGroup(g.members[0], STOCKS).n };""", STOCKS=stocks)
    assert got["n"] == 6 == got["peer"] and got["rose"] == 2 and len(got["members"]) == 6       # 왜 움직였나와 같은 수
    assert got["list"] == ["GOOGL", "META", "NFLX", "SPOT", "PINS"], got["list"]                # 줄은 회사마다 하나


# ── 날짜 줄의 사업보고서 연도: 정말 그 연도일 때만 ──
def test_report_year_only_when_true_for_every_row():
    got = run("""const row = (t, fy) => ({ s: { t, cls: 'kr', fy } });
out = {
  kinds: [K.listReport('kr', 'crit', 'value'), K.listReport('kr', 'crit', 'profit'), K.listReport('kr', 'crit', 'stable'),
          K.listReport('kr', 'crit', 'growth'), K.listReport('kr', 'crit', 'lowVol'), K.listReport('kr', 'crit', 'trend'),
          K.listReport('kr', 'div'), K.listReport('kr', 'cap'), K.listReport('kr', 'ind'), K.listReport('us', 'div'), K.listReport('us', 'crit', 'profit')],
  mine: [K.listReport('kr', 'mine', null, { value: 5 }), K.listReport('kr', 'mine', null, { value: 3, profit: 2 }),
         K.listReport('kr', 'mine', null, { lowVol: 4, trend: 1 }), K.listReport('kr', 'mine', null, { div: 1 })],
  one: K.oneReportYear([row('000010', 2025), row('000020', 2025)]),
  two: K.oneReportYear([row('000010', 2025), row('000020', 2024)]),
  gap: K.oneReportYear([row('000010', 2025), row('000020', null)]),
  corp: K.oneReportYear([row('000010', null)], new Map([['000010', { fy: 2025 }]])),
  none: K.oneReportYear([]) };""")
    # 가치는 PBR 이 최근 분기 자본이라 사업보고서 연도를 말하지 않아요(날짜 줄은 '각 회사의 최근 분기 재무제표 기준', dateBasis). 내 기준도 가치만이면 같아요
    assert got["kinds"] == [False, True, True, True, False, False, True, False, False, False, False], got["kinds"]
    assert got["mine"] == [False, True, False, True], got["mine"]
    assert got["one"] == {"year": 2025, "years": [2025], "missing": 0}
    assert got["two"]["year"] is None and got["two"]["years"] == [2024, 2025]                  # 두 해가 섞이면 연도 없이
    assert got["gap"]["year"] is None and got["gap"]["missing"] == 1 and got["corp"]["year"] == 2025
    assert got["none"]["year"] is None


# ── 거래대금 기준 기록 · 꼭 있어야 하는 종목 ──
def test_the_floor_is_logged_and_must_haves_are_checked():
    stocks = [st("005930", cap=900.0), st("000660", cap=800.0, val20=None), st("005380", cap=50.0, val20=3.0), st("000010"),
              st("AAA", "us", val=None)]
    got = run("""const logs = []; console.warn = (m) => logs.push(String(m));
const base = K.rankBase(STOCKS, 'kr'); K.rankBase(STOCKS, 'kr'); K.rankBase(STOCKS, 'us');
const miss = K.mustMissing(STOCKS);
out = { base: base.map((s) => s.t), miss, logs };""", STOCKS=stocks)
    assert got["base"] == ["005930", "000010"]
    floor = [l for l in got["logs"] if "trading-value floor" in l]
    assert len(floor) == 2 and "left out 1 with no val20 and 1 under 5" in floor[0] and "left out 1 with no val" in floor[1], floor   # 시장마다 한 번
    assert got["miss"] == ["000660", "005380"]                                       # 데이터에 있는데 시가총액 목록에 없는 꼭 있어야 하는 종목
    assert any("must-have Korean companies missing" in l and "000660, 005380" in l for l in got["logs"]), got["logs"]


def test_the_floor_log_is_a_warning_only_when_a_floor_value_is_blank():
    """거래대금 기준이 뺀 종목 수는 평소 info 로 알리고, 기준값(val20 · val)이 빈 종목이 있을 때만 warn 이에요 (5억 미만은 규칙대로라서)."""
    stocks = [st("005930", cap=900.0), st("000010", val20=3.0), st("000020", val20=None), st("AAA", "us"), st("BBB", "us", val=2.0)]
    got = run("""const info = [], warn = []; console.info = (m) => info.push(String(m)); console.warn = (m) => warn.push(String(m));
K.rankBase(STOCKS, 'us'); K.rankBase(STOCKS, 'kr');
out = { info: info.filter((l) => l.includes('trading-value floor')), warn: warn.filter((l) => l.includes('trading-value floor')) };""",
              STOCKS=stocks)
    assert len(got["info"]) == 1 and got["info"][0].startswith("[v2] rank lists (us): 1 of 2") and "left out 0 with no val and 1 under 5" in got["info"][0], got
    assert len(got["warn"]) == 1 and got["warn"][0].startswith("[v2] rank lists (kr): 1 of 3") and "left out 1 with no val20 and 1 under 5" in got["warn"][0], got


def test_industry_groups_on_real_shaped_data_match_why_it_moved_exactly():
    """indGroups 는 업종마다 그 업종 종목만 peerGroup 에 넘겨요(빠르게): 파일 전체를 넘긴 peerGroup 과 n · 오름 · 내림 · 평균이 똑같아요."""
    got = run("""const fs = await import('fs'); const DATA = JSON.parse(fs.readFileSync(PATH, 'utf8'));
const bad = [];
let n = 0;
for (const mk of ['kr', 'us']) for (const g of K.indGroups(DATA.stocks, mk)) {
  n++;
  const p = T.peerGroup(g.members[0], DATA.stocks);
  if (!(p.ok && p.n === g.n && p.rose === g.rose && p.fell === g.fell && p.avg === g.avg)) bad.push(g.ind);
}
out = { n, bad };""", PATH=os.path.join(ROOT, "tests", "fixtures", "v2", "data.json"))
    assert got["n"] >= 10 and got["bad"] == [], got


def test_must_haves_mirror_the_gate_and_samsung_heads_the_market_cap_list():
    import validate_data
    got = run("""const fs = await import('fs'); const DATA = JSON.parse(fs.readFileSync(PATH, 'utf8'));
out = { must: K.MUST_KR, top: K.capList(DATA.stocks, 'kr').slice(0, 3).map((r) => r.s.t), miss: K.mustMissing(DATA.stocks) };""",
              PATH=os.path.join(ROOT, "tests", "fixtures", "v2", "data.json"))      # 실제 실행본에서 뽑은 시험 데이터
    assert got["must"] == list(validate_data.MUST)
    assert got["top"][0] == "005930" and got["miss"] == [], got


# ── Jack 의 결정 (2026-11-12): 성장은 시장마다 한 잣대 · 최소 크기 · 미국 가치 보조 장치 · 빈 목록의 두 이유 · 날짜 줄 · 업종 두 부분 ──
def test_korean_growth_is_the_two_year_average_on_a_base_of_100_eok_and_profit_needs_100_eok_equity():
    stocks = [st("000010", g3=50.0, roe=40.0, cap=1.0), st("000020", g3=40.0, roe=30.0, cap=2.0), st("000030", g3=30.0, roe=20.0, cap=3.0),
              st("000040", g3=20.0, roe=10.0, cap=4.0), st("000050", g3=10.0, roe=5.0, cap=5.0), st("000060", g3=5.0, roe=4.0, cap=6.0),
              st("AAA", "us", g3=60.0, roe=90.0), st("BBB", "us", g3=1.0, roe=2.0)]
    # 매출은 g3 와 맞게 (engine.growthBasis 가 2년 · 1년을 가려요)
    corp = [{"t": "000010", "rev": [225.0, 200.0, 100.0], "roeIn": {"eq": 100.0}, "eq": 99.0},     # 2년 연평균 50% · 딱 100억원: 둘 다 들어가요 (자본은 ROE 의 자본)
            {"t": "000020", "rev": [280.0, 200.0, None], "eq": 5000.0},                          # 전전기 없음: 1년 성장 40% → 성장 목록에서 빠짐
            {"t": "000030", "rev": [168.9, 150.0, 99.9], "roeIn": {"eq": 57.3}, "eq": 407.3},     # 2년 30% 지만 바탕 매출 99.9억 · ROE 자본 57.3억 (JW신약 꼴)
            {"t": "000040", "rev": [300.0, 250.0, -5.0], "eq": 150.0},                           # 전전기 음수: 1년 성장 20% · roeIn 없으면 eq
            {"t": "000050", "rev": [None, None, None], "eq": None}]                               # 외화 재무제표처럼 금액 없음 · 000060: corp 없음
    got = run("""const CO = new Map(CORP.map((c) => [c.t, c])); const logs = []; console.info = (m) => logs.push(String(m));
out = { g: ts(K.critList(STOCKS, 'kr', 'growth', CO)), p: ts(K.critList(STOCKS, 'kr', 'profit', CO)),
  gNoCorp: ts(K.critList(STOCKS, 'kr', 'growth')), us: [ts(K.critList(STOCKS, 'us', 'growth', CO)), ts(K.critList(STOCKS, 'us', 'profit'))],
  st: [K.critState(STOCKS, 'kr', 'growth', CO), K.critState(STOCKS, 'kr', 'growth', null), K.critState(STOCKS, 'kr', 'growth', new Map())],
  min: K.MIN_EOK, logs };""", STOCKS=stocks, CORP=corp)
    assert got["g"] == ["000010"], got["g"]
    assert got["p"] == ["000010", "000020", "000040"], got["p"]                    # 000030: ROE 의 자본 57.3억 · 000050: 자본 없음 · 000060: corp 없음
    assert got["gNoCorp"] == [] and got["st"] == ["rows", "nodata", "nodata"], got   # corp.json 없이는 기준을 확인할 수 없어요: 데이터 없음
    assert got["us"] == [["AAA", "BBB"], ["AAA", "BBB"]]                            # 미국은 최소 크기 없이 (데이터에 미국 매출 · 자본 금액이 아직 없어요)
    assert got["min"] == 100
    gl = [l for l in got["logs"] if "growth list" in l and "(kr)" in l]
    assert len(gl) == 2 and gl[0].endswith("leaves out oneYear 2; smallBase 1; noRevenue 2") and gl[1].endswith("noRevenue 6"), gl   # corp 와 함께 · 없이, 한 번씩


def test_the_floor_copy_says_the_same_100_eok_as_the_code():
    copy = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    assert 'growth: "매출 100억원 이상"' in copy and 'profit: "자본 100억원 이상"' in copy
    assert "export const MIN_EOK = 100;" in open(os.path.join(ROOT, "src", "v2", "ranks.js"), encoding="utf-8").read()


def test_us_value_guard_is_one_sided_and_pbr_at_or_below_0_leaves_both_markets():
    # 2026-11-11 발행본의 숫자 그대로: ERIC · KSPI 는 PBR 이 PER × ROE ÷ 100 의 1/4 보다 작아요. TSM (PBR 이 훨씬 큼) · NTES 는 남아요
    stocks = [st("ERIC", "us", per=17.1, roe=18.1, pbr=0.35, cap=46.09), st("KSPI", "us", per=7.9, roe=44.8, pbr=0.01, cap=22.745),
              st("TSM", "us", per=26.8, roe=41.9, pbr=78.88, cap=2869.0), st("NTES", "us", per=17.0, roe=20.4, pbr=15.63, cap=104.6),
              st("AES", "us", per=6.0, roe=8.7, pbr=1.86, cap=14.2), st("LOSS", "us", per=None, roe=-5.0, pbr=0.2, cap=1.0),
              st("NEG", "us", per=10.0, roe=10.0, pbr=-0.5, cap=1.0), st("ZERO", "us", per=10.0, roe=10.0, pbr=0.0, cap=1.0),
              st("000010", pbr=0.0, cap=1.0), st("000020", pbr=-1.2, cap=2.0), st("000030", pbr=0.01, per=50.0, roe=40.0, cap=3.0)]
    got = run("""const logs = []; console.info = (m) => logs.push(String(m));
out = { us: ts(K.critList(STOCKS, 'us', 'value')), kr: ts(K.critList(STOCKS, 'kr', 'value')), logs: logs.filter((l) => l.includes('value list')) };""",
              STOCKS=stocks)
    assert got["us"] == ["LOSS", "AES", "NTES", "TSM"], got["us"]                    # PER · ROE 가 없거나 음수면 확인할 수 없어 그대로
    assert got["kr"] == ["000030"], got["kr"]                                      # 한국은 보조 장치 없이 (DART 영수증), PBR 0 이하만 빠져요
    us = next(l for l in got["logs"] if "(us)" in l)
    assert "pbrFarUnder 2: ERIC, KSPI" in us and "pbrNotAbove0 2: NEG, ZERO" in us, got["logs"]
    assert any("(kr)" in l and "pbrNotAbove0 2: 000010, 000020" in l for l in got["logs"]), got["logs"]


def test_us_value_guard_removes_exactly_eric_and_kspi_from_the_2026_11_11_figures():
    """2026-11-11 발행본(미국 740종목)의 PER · ROE · PBR 에서 보조 장치에 걸리는 종목: 그날의 숫자를 옮겨 적은 표로 확인해요."""
    near = {"AES": (6.0, 8.7, 1.86), "AGNC": (5.9, 17.4, 1.14), "ERIC": (17.1, 18.1, 0.35), "KSPI": (7.9, 44.8, 0.01),
            "NTES": (17.0, 20.4, 15.63), "TSM": (26.8, 41.9, 78.88), "OMC": (10.9, 30.3, 3.92)}
    stocks = [st(t, "us", per=a, roe=b, pbr=c) for t, (a, b, c) in near.items()]
    got = run("out = ts(K.critList(STOCKS, 'us', 'value')).sort();", STOCKS=stocks)
    assert sorted(set(near) - set(got)) == ["ERIC", "KSPI"], got


def test_empty_lists_say_whether_the_data_is_missing_or_nothing_qualifies():
    stocks = [st("000010", dyt=40.0, pbr=-1.0, debt=None, ind="bank", d1=0.5, g3=None, roe=10.0, vol=20.0, vz=50, opm=-1.0),
              st("000020", dyt=None, pbr=0.0, debt=30.0, ind="bank", d1=0.3, val=None, roe=12.0, vol=25.0, vz=40, opm=-2.0),
              st("AAA", "us", dy=None, pbr=1.0, d1=None)]
    got = run("""const ld = (corp) => loadOf({ pxDate: '2026-11-11', usPxDate: '2026-11-11', stocks: STOCKS }, corp);
const deck = (points, exclude = {}) => ({ settings: { points, exclude } });
E.setDataShape({ divCheck: { v: 1 } });
const a = K.chipState(ld([{ t: '000010', rev: [1, 1, 1], eq: 500 }]), 'kr', deck({ value: 3 }, { loss: true }));
E.setDataShape({});
const b = K.chipState(ld([]), 'kr', deck({ value: 3 }));
const c = K.chipState(ld([]), 'kr', deck({ lowVol: 3, trend: 2 }));
const u = K.chipState(ld([]), 'us', null);
out = { a, b, c, u };""", STOCKS=stocks)
    a, b, c, u = got["a"], got["b"], got["c"], got["u"]
    assert a["div"] == "none" and b["div"] == "nodata", (a["div"], b["div"])         # 확인한 배당이 0–30% 밖뿐 → 들어갈 종목 없음 · 확인 전 파일 → 데이터 없음
    assert a["crit"]["value"] == "none" and a["crit"]["stable"] == "none", a["crit"]  # PBR 이 0 이하뿐 · 금융회사뿐 (해당 없음)
    assert a["crit"]["growth"] == "nodata" and a["crit"]["profit"] == "rows" and a["crit"]["lowVol"] == "rows", a["crit"]
    assert b["crit"]["profit"] == "nodata", b["crit"]                               # corp.json 이 없으면 한국 수익성의 자본을 확인할 수 없어요
    assert a["val"] == "rows" and a["surge"] == "none" and a["ind"] == "none", a     # 업종에 5곳이 안 돼요
    assert a["mine"] == "none" and b["mine"] == "rows" and c["mine"] == "nodata", (a["mine"], b["mine"], c["mine"])   # 빼기로 다 빠짐 · 추세(mom) 숫자가 없음
    assert u["base"] == 1 and u["div"] == "nodata" and u["ind"] == "nodata" and u["surge"] is None, u


def test_date_basis_quarter_for_value_and_a_value_only_mine():
    got = run("""const b = (chip, crit, pts) => K.dateBasis('kr', chip, crit, pts);
out = [b('crit', 'value'), b('crit', 'profit'), b('crit', 'stable'), b('crit', 'growth'), b('crit', 'lowVol'), b('crit', 'trend'), b('div'), b('cap'),
  b('ind'), b('mine', null, { value: 5 }), b('mine', null, { value: 3, profit: 2 }), b('mine', null, { value: 2, lowVol: 4 }),
  b('mine', null, { lowVol: 4, trend: 1 }), b('mine', null, { div: 1 }), K.dateBasis('us', 'crit', 'value'), K.dateBasis('us', 'div')];""")
    assert got == ["quarter", "report", "report", "report", None, None, "report", None, None, "quarter", "report", "quarter", None, "report", None, None], got


def test_industry_parts_rose_and_fell_five_each_by_the_shown_value():
    groups = [{"ind": f"g{i}", "avg": a} for i, a in enumerate([3.1, 2.0, 1.5, 0.9, 0.6, 0.4, 0.06, 0.04, -0.04, -0.06, -0.3, -1.0, -2.2, -2.5, -4.0])]
    got = run("""const p = K.indParts(G, 5), few = K.indParts(G.slice(0, 3), 5), down = K.indParts(G.slice(7), 5);
out = { up: p.up.map((g) => g.ind), down: p.down.map((g) => g.ind), few: [few.up.length, few.down.length], d: down.up.map((g) => g.ind) };""", G=groups)
    assert got["up"] == ["g0", "g1", "g2", "g3", "g4"] and got["down"] == ["g14", "g13", "g12", "g11", "g10"], got
    assert got["few"] == [3, 0] and got["d"] == [], got                            # '0.0%' 인 업종(g7 · g8)은 어느 쪽에도 없어요


def test_korean_value_guard_leaves_out_a_pbr_that_rounds_to_0_00():
    """Jack, 2026-11-13: 한국 가치 목록에서 0.00 으로 반올림되는 PBR(0.005 미만)은 진짜 값이 아니라서 빼요 (PBR 0 이하는 원래대로 빠져요).
    콘솔은 코드와 이름을 수와 함께 말해요. 다른 기준은 없어요 (0.07 · 0.09 는 그대로)."""
    stocks = [st("000010", nk="영영사", pbr=0.004, cap=1.0), st("000020", nk="영영오", pbr=0.005, cap=2.0), st("000030", pbr=0.0, cap=3.0),
              st("000040", pbr=-0.3, cap=4.0), st("000050", nk="앱토크롬꼴", pbr=0.07, cap=5.0), st("AAA", "us", pbr=0.004, cap=1.0)]
    got = run("""const logs = []; console.info = (m) => logs.push(String(m));
out = { kr: ts(K.critList(STOCKS, 'kr', 'value')), us: ts(K.critList(STOCKS, 'us', 'value')), min: K.KR_PBR_MIN,
  st: K.critState([STOCKS[0]], 'kr', 'value'), logs: logs.filter((l) => l.includes('value list')) };""", STOCKS=stocks)
    assert got["kr"] == ["000020", "000050"], got["kr"]                             # 0.004 빠짐 · 0.005 남음 · 0 이하 빠짐 · 0.07 남음
    assert got["us"] == ["AAA"] and got["min"] == 0.005, got                       # 미국은 이 기준 없이 (미국은 J4 보조 장치)
    assert got["st"] == "none", got["st"]                                          # 숫자는 있는데 들어갈 종목이 없어요
    kr = next(l for l in got["logs"] if "(kr)" in l)
    assert "pbrNotAbove0 2: 000030, 000040" in kr and "pbrRoundsTo0 1: 000010 영영사" in kr, got["logs"]
