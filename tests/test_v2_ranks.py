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
    got = run("""out = Object.fromEntries(K.CRIT.map((c) => [c.id, ts(K.critList(STOCKS, 'kr', c.id))])); out.none = K.critList(STOCKS, 'kr', 'div');""",
              STOCKS=stocks)
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
    got = run("""out = { kr: K.chipsFor('kr', true), us: K.chipsFor('us', true), noMine: K.chipsFor('kr', false), empty: K.chipsFor('us', false, ['div']),
  shown: [K.shownChip('surge', K.chipsFor('us', true)), K.shownChip('mine', K.chipsFor('kr', false)), K.shownChip('ind', K.chipsFor('kr', true))] };""")
    assert got["kr"] == ["cap", "val", "surge", "crit", "mine", "div", "ind"]
    assert got["us"] == ["cap", "val", "crit", "mine", "div", "ind"]
    assert got["noMine"] == ["cap", "val", "surge", "crit", "div", "ind"]
    assert got["empty"] == ["cap", "val", "crit", "ind"]
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
