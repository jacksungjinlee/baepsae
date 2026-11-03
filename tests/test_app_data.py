# -*- coding: utf-8 -*-
"""src/data.js (앱의 데이터 읽기) — Node 로 직접 돌려봐요. 따옴표 안의 'NaN' 글자는 그대로 두고,
따옴표 밖의 NaN·Infinity 만 null 로 고쳐야 해요 (미국 기업 설명에 그런 낱말이 들어갈 수 있어서)."""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")


def run_js(body):
    code = "import * as D from './src/data.js';\n" + body
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_repair_only_outside_strings():
    raw = '{"a":NaN,"b":[1,Infinity,-Infinity],"de":"NaN and Infinity are words here \\" NaN","c":{"d":NaN}}'
    out = run_js(f"const r = D.repairJsonText({json.dumps(raw)}); console.log(JSON.stringify({{n: r.n, v: JSON.parse(r.text)}}));")
    assert out["n"] == 4   # a · Infinity · -Infinity · d (글자 안의 NaN·Infinity 는 세지 않아요)
    assert out["v"] == {"a": None, "b": [1, None, None], "de": 'NaN and Infinity are words here " NaN', "c": {"d": None}}


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_clean_json_is_untouched():
    raw = '{"nk":"삼성전자","x":[1.5,-2,"Infinity"]}'
    out = run_js(f"const r = D.repairJsonText({json.dumps(raw)}); console.log(JSON.stringify({{n: r.n, same: r.text === {json.dumps(raw)}}}));")
    assert out == {"n": 0, "same": True}


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_freshness_counts_from_published_at():
    out = run_js(
        "const now = Date.parse('2026-11-06T10:00:00+09:00');"
        "console.log(JSON.stringify(["
        "D.freshness('2026-10-30', '2026-10-31T09:30:00+09:00', 'ko', now),"
        "D.freshness('2026-10-30', '2026-11-03T09:30:00+09:00', 'ko', now),"
        "D.freshness('2026-10-30', '2026-11-03T09:30:00+09:00', 'en', now),"
        "D.freshness('2026-10-30', null, 'ko', now)]));")
    assert out[0] == {"md": "10월 30일", "days": 6, "stale": True}     # 발행 6일 전 → 멈춤
    assert out[1] == {"md": "10월 30일", "days": 3, "stale": False}    # 긴 연휴: 가격 날짜는 오래돼도 발행은 3일 전
    assert out[2]["md"] == "Oct 30"
    assert out[3]["stale"] is False and out[3]["days"] is None


# ── mergeStocks: 내장 목록에 없는 종목에 숫자를 지어내지 않아요 (PR #4 리뷰 3번) ──
@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_auto_stocks_keep_blanks_and_flag_missing_risk_inputs():
    base = [{"t": "005930", "nk": "삼성전자", "ne": "Samsung", "s": "semi", "price": 78000, "beta": 1.1, "vol": 30,
             "per": 14, "pbr": 1.4, "dy": 1.8, "al": -6}]
    live = [
        {"t": "005930", "price": 225000, "beta": 1.2, "vol": 33, "per": None, "pbr": 2.1, "dy": None},
        {"t": "111111", "nk": "새종목", "cls": "kr", "price": 5000, "beta": 0.9, "vol": 40, "per": None, "pbr": None, "dy": None},
        {"t": "222222", "nk": "베타없음", "cls": "kr", "price": 7000, "beta": None, "vol": 35},
        {"t": "333333", "nk": "변동성없음", "cls": "kr", "price": 7000, "beta": 1.0, "vol": None},
        {"t": "444444", "nk": "가격없음", "cls": "kr", "price": None, "beta": 1.0, "vol": 30},
    ]
    code = (f"const warn = []; console.warn = (m) => warn.push(m);"
            f"const out = D.mergeStocks({json.dumps(base, ensure_ascii=False)}, {json.dumps(live, ensure_ascii=False)});"
            "console.log(JSON.stringify({out, warn}));")
    got = run_js(code)
    by = {s["t"]: s for s in got["out"]}
    assert set(by) == {"005930", "111111", "222222", "333333"}, by.keys()   # 가격이 없는 종목만 빼요
    n = by["111111"]
    assert n["live"] is True and n["beta"] == 0.9 and n["vol"] == 40 and not n.get("noRisk")
    assert n["per"] is None and n["pbr"] is None and n["dy"] is None        # 0 이 아니라 빈 칸 → 화면에 '–'
    for t in ("222222", "333333"):                                          # 이미 담은 종목이 사라지지 않게 목록에 둬요
        x = by[t]
        assert x["noRisk"] is True and x["beta"] is None and x["vol"] is None and x["live"] is True and x["price"] == 7000
    s = by["005930"]
    assert s["price"] == 225000 and s["per"] is None and s["dy"] is None and s["live"] is True
    assert any("가격이 없어" in w and "444444" in w for w in got["warn"]), got["warn"]
    assert any("위험 계산에서 빼는 종목 2개" in w for w in got["warn"]), got["warn"]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_merge_without_live_data_marks_everything_not_live():
    base = [{"t": "005930", "nk": "삼성전자", "price": 78000, "beta": 1.1, "vol": 30}]
    got = run_js(f"console.log(JSON.stringify(D.mergeStocks({json.dumps(base, ensure_ascii=False)}, null)));")
    assert got[0]["live"] is False


# ── 위험 수치: 베타·변동성 없는 종목 (Jack 결정 2026-11-01) ─────────────────
def run_metrics(body):
    """src/detail.jsx 를 묶어서 computeMetrics 를 Node 로 직접 불러요 (React 는 밖에 둬요)."""
    import tempfile
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "detail.mjs")
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, "src/detail.jsx", "--bundle", "--format=esm", "--platform=node", "--external:react",
                        "--external:react-dom", "--loader:.jsx=jsx", "--jsx=automatic", f"--outfile={out}", "--log-level=warning"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
    code = ("import * as D from './detail.mjs'; const st = D.DEFAULT_SETTINGS;"
            "const h = (s, mw) => ({ t: s.t, mw, won: mw * 10000, stock: s });"
            "const pick = (m) => m.empty ? { blind: !!m.riskBlind, all: !!m.allNoRisk, pct: +m.noRiskPct.toFixed(1),"
            " w: (m.rows || []).map((r) => +r.wInv.toFixed(3)) }"
            " : { beta: +m.beta.toFixed(9), volP: +m.volP.toFixed(9), expRet: +m.expRet.toFixed(9), pct: +m.noRiskPct.toFixed(1) };"
            + body)
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=tmp, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


STOCKS_JS = ("const S = { t: '005930', cls: 'kr', s: 'semi', beta: 1.2, vol: 33, price: 1, dy: 2 };"
             "const X = { t: 'X', cls: 'kr', s: 'bank', beta: null, vol: null, price: 1, dy: null };"
             "const B = { t: 'B', cls: 'bond', s: 'bond', beta: 0.05, vol: 6, price: 1, dy: 3 };"
             "const U = { t: 'U', cls: 'us', s: 'tech', beta: 1.1, vol: 28, price: 1, dy: 1 };")


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_missing_risk_data_is_assumed_to_move_like_its_own_class():
    got = run_metrics(STOCKS_JS + "const M = (hs) => pick(D.computeMetrics(hs, 1000 * 10000, st));"
                      "console.log(JSON.stringify({ a: M([h(S, 500)]), b: M([h(S, 300), h(X, 200)]),"
                      " mix: M([h(S, 300), h(B, 300), h(X, 200)]), mixRef: M([h(S, 500), h(B, 300)]),"
                      " full: M([h(S, 300), h(B, 300), h(U, 200)]) }));")
    a, b = dict(got["a"]), dict(got["b"])
    assert b.pop("pct") == 40 and a.pop("pct") == 0 and a == b          # 200만원은 삼성전자처럼 움직인다고 봐요
    m, ref = dict(got["mix"]), dict(got["mixRef"])
    assert m.pop("pct") == 25 and ref.pop("pct") == 0 and m == ref      # 한국 주식 몫은 채권이 아니라 한국 주식으로
    assert got["full"]["pct"] == 0 and got["full"]["beta"] > 0           # 자료가 다 있으면 그대로 (NaN 아님)


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_more_than_half_without_data_shows_no_risk_numbers():
    got = run_metrics(STOCKS_JS + "const M = (hs) => pick(D.computeMetrics(hs, 1000 * 10000, st));"
                      "console.log(JSON.stringify({ half: M([h(S, 100), h(X, 200)]), exact: M([h(S, 200), h(X, 200)]),"
                      " all: M([h(X, 300)]), exactFloat: M([h(S, 300), h(X, 100), h({ ...X, t: 'X2' }, 200)]) }));")
    assert got["half"] == {"blind": True, "all": False, "pct": 66.7, "w": [0.333, 0.667]}   # 비중은 그대로 보여요
    assert "beta" in got["exact"] and got["exact"]["pct"] == 50.0       # 딱 절반은 계산 (절반 '넘으면' 안 함)
    # 소수점 오차가 나는 딱 절반 (300 + 100 + 200, 예산 1000): 비중을 더하면 50.000000000000014 가 돼요
    assert "beta" in got["exactFloat"] and got["exactFloat"]["pct"] == 50.0, got["exactFloat"]
    assert got["all"]["blind"] and got["all"]["all"] and got["all"]["w"] == [1.0]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_checkin_ignores_old_snapshots_saved_with_nan():
    # v17.5 전 점검은 위험 수치가 NaN 이라 null 로 저장됐어요. 그것과 비교하면 안 돼요 (소스에서 확인)
    src = open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()
    body = src.split("function CheckinCard", 1)[1].split("\nfunction ", 1)[0]
    assert "find(valid)" in body and "checkins[checkins.length - 1]" not in body


# ── v18.5 (Jack 2026-11-03): 오늘 데이터에 없는 보유 종목 ─────────────────
@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_missing_holdings_are_named_and_left_out_of_the_share_card():
    got = run_metrics(STOCKS_JS + "const by = { '005930': S, U: U };"
                      "const hs = [{ t: 'STRC', mw: 200 }, { t: '005930', mw: 300 }, { t: 'U', mw: 100 }, { t: '000660', mw: 50 },"
                      " { t: 'GOOGM', mw: 10, nk: '저장된 이름' }, { mw: 5 }, null];"
                      "const miss = D.missingHoldings(hs, by); const card = D.makeCardData(hs, by, 100, null, 'ko');"
                      "console.log(JSON.stringify({ miss: miss.map((h) => h.t), ko: D.missingLine('ko', miss), en: D.missingLine('en', miss),"
                      " none: D.missingLine('ko', D.missingHoldings([{ t: '005930', mw: 1 }], by)),"
                      " top: card.top.map((x) => x.nk), buckets: card.buckets.map((b) => [b.ko, +b.pct.toFixed(1)]), note: card.note, alts: card.noteAlts,"
                      " cleanNote: D.makeCardData([{ t: '005930', mw: 300 }], by, 700, null, 'ko').note }));")
    # 코드가 없는 줄({ mw: 5 })과 null 은 종목이 아니라서 세지 않아요. 이름: 저장된 이름 → 내장 목록(SK하이닉스) → 코드 그대로,
    # 그 뒤에 금액 (앱의 만원 표기 · 영어는 앱의 ₩ 표기 — 영어 금액 모양은 PENDING JACK)
    assert got["miss"] == ["STRC", "000660", "GOOGM"]
    assert got["ko"] == "오늘 데이터에 없는 종목 3개(STRC 200만원, SK하이닉스 50만원, 저장된 이름 10만원)는 빼고 계산했어요."
    assert got["en"] == "Left out 3 stock(s) not in today's data (STRC ₩2,000,000, SK Hynix ₩500,000, 저장된 이름 ₩100,000)."
    assert got["none"] is None and got["cleanNote"] is None
    # 공유 카드: 빠진 종목은 국내 주식으로도 TOP 으로도 세지 않아요 (300 + 100 + 현금 100 = 500)
    assert got["top"] == ["005930", "U"] and got["buckets"] == [["국내 주식", 60.0], ["미국 주식", 20.0], ["현금", 20.0]], got
    assert got["note"] == got["ko"]                                       # 카드에도 같은 안내 한 줄
    # 카드에 두 줄로 안 들어갈 때 쓸 문장: 이름만 줄이고 개수·문장은 그대로
    assert got["alts"] == ["오늘 데이터에 없는 종목 3개(STRC 200만원, SK하이닉스 50만원, …)는 빼고 계산했어요.",
                           "오늘 데이터에 없는 종목 3개(STRC 200만원, …)는 빼고 계산했어요."], got["alts"]


# ── v18.5 B안: 베타를 수익률로 바꾸는 프로필 문장 (Jack 2026-11-03) ─────────────────
ANS_A = {"goal": "retire", "horizon": 20, "share": 10, "emergency": 12, "target": 4, "style": ["long"], "crash": ["hold"],
         "exp": ["krstock"], "checking": "monthly", "fear": ["none"], "account": "normal", "interest": ["index"]}
ANS_B = {"goal": "grow", "horizon": 1, "share": 100, "emergency": 0, "target": 15, "style": ["ret"], "crash": ["sellall"],
         "exp": ["newbie"], "checking": "daily", "fear": ["loss"], "account": "normal", "interest": ["semi"]}
BETA_RET = {"ko": ["%라서, 베타", "기대하기 어려운 수치", "정도면 충분해요"],
            "en": ["goal, aim for beta", "is hard to expect from the risk you can carry", "goal only needs about beta"]}


ANS_R = {"goal": "house", "horizon": 20, "share": 100, "emergency": 0, "target": 8, "style": ["long"], "crash": ["sellsome"],
         "exp": ["lev"], "checking": "daily", "fear": ["loss"], "account": "normal", "interest": ["index"]}   # 리뷰 답


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_profile_lines_that_turn_beta_into_returns_are_hidden_but_the_rest_stays():
    # scoreProfile(a, lang) = 지금 앱 (SHOW_ER 끔), scoreProfile(a, lang, true) = 예전 앱이 만들어 저장한 프로필
    got = run_metrics(f"const A = {json.dumps(ANS_A)}, B = {json.dumps(ANS_B)}, R = {json.dumps(ANS_R)}; const out = {{}};"
                      "const lines = (p) => [p.summary, ...p.tips, ...p.flags];"
                      "const tg = (p) => [p.targetBetaMin, p.targetBetaMax, p.targetVolMaxPct];"
                      "for (const lang of ['ko', 'en']) for (const [k, a] of [['A', A], ['B', B], ['R', R]]) {"
                      " const now = D.scoreProfile(a, lang), old = D.scoreProfile(a, lang, true), shown = D.shownProfile(old);"
                      " out[lang + k] = { now: lines(now), old: lines(old), shown: lines(shown), nowFlags: now.flags, oldFlags: old.flags,"
                      " nTips: [old.tips.length, shown.tips.length], nFlags: [old.flags.length, shown.flags.length],"
                      " tNow: tg(now), tOld: tg(old), tShown: tg(shown), tShownNow: tg(D.shownProfile(now)),"
                      " tEdited: tg(D.shownProfile({ ...old, targetBetaMax: 1.25 })) }; }"
                      "console.log(JSON.stringify(out));")
    for lang in ("ko", "en"):
        a, b, r = got[lang + "A"], got[lang + "B"], got[lang + "R"]
        words = BETA_RET[lang]
        # 예전 앱이 만든 문장 틀과 거르는 틀이 맞는지: 예전 프로필엔 있고(A: 요약·팁, B: 요약·경고), 걸러 보이면 없어요
        assert words[0] in a["old"][0] and any(words[2] in x for x in a["old"]), a["old"]
        assert words[0] in b["old"][0] and any(words[1] in x for x in b["old"]), b["old"]
        for x in (a, b, r):
            for key in ("now", "shown"):                                   # 지금 만든 프로필에는 아예 없어요
                assert not [w for w in words for line in x[key] if w in line], (key, x[key])
            end = "기준이 돼요." if lang == "ko" else "binds."
            assert x["now"][0].endswith(end) and x["shown"][0] == x["now"][0], (x["now"][0], x["shown"][0])
        assert a["nTips"][1] == a["nTips"][0] - 1 and b["nFlags"][1] == b["nFlags"][0] - 1
        # 목표 베타·변동성 상한: 감당 능력만으로 (A: 목표 연 4% 로 낮췄던 0.2–0.45 · ≤16% → 0.9–1.4 · ≤29%)
        assert a["tOld"] == [0.2, 0.45, 16] and a["tNow"] == [0.9, 1.4, 29], (a["tOld"], a["tNow"])
        assert a["tShown"] == a["tNow"] and a["tShownNow"] == a["tNow"]   # 예전에 저장된 값도 화면에선 감당 능력 기준
        assert b["tNow"] == b["tOld"] == [0.3, 0.7, 13]                    # 감당 능력이 더 낮으면 원래도 같은 값
        assert a["tEdited"] == [0.2, 1.25, 16]                              # 직접 고친 값은 그대로
        # 리뷰: 경고 자리(3개)를 '기대하기 어려운 수치'가 차지해 '비상금이 먼저예요'가 밀려났었어요 → 이제는 보여요
        cushion = "비상금이 먼저예요" if lang == "ko" else "fund the cushion first"
        assert any(cushion in f for f in r["nowFlags"]), r["nowFlags"]
        assert not any(cushion in f for f in r["oldFlags"]) and any(words[1] in f for f in r["oldFlags"]), r["oldFlags"]
