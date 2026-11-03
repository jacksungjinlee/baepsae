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


# ── 「저장한 파일에서 불러오기」: 이 앱의 「JSON 저장 (백업·공유)」 파일도, 예전 저장 상태 파일도 읽어요 (v18.4.1, Jack 2026-11-04) ──
# 전에는 앱이 저장한 파일({ holdings: [{ ticker, amountWon }], budgetWon })이 아무 말 없이 빈 포트폴리오로 열렸어요.
# 읽을 종목이 하나도 없으면 null 이에요: 앱은 '파일을 읽을 수 없어요.'만 띄우고 아무것도 바꾸지 않아요 (smoke_app.py 의 '파일 불러오기').
KNOWN_JS = "const K = new Set(['005930', '000660', 'AAPL']); const warn = []; console.warn = (m) => warn.push(String(m));"


def read_file_js(cases):
    """cases: {이름: 파일 객체} → {이름: readPortfolioFile 결과}, 그리고 console 경고들."""
    return run_metrics(KNOWN_JS + f"const cases = JSON.parse({json.dumps(json.dumps(cases, ensure_ascii=False), ensure_ascii=False)});"   # 파일처럼 JSON.parse 로
                       "const out = {}; for (const k of Object.keys(cases)) out[k] = D.readPortfolioFile(cases[k], K) ?? 'NULL';"
                       "console.log(JSON.stringify({ out, warn }));")


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_reads_the_apps_own_export_file():
    export = {"app": "Baepsae 뱁새 v12", "slot": "포트폴리오 1", "date": "2026-11-03", "dataAsOf": "2026-11-02", "notLive": [],
              "budgetWon": 25000000,
              "holdings": [{"ticker": "005930", "name": "삼성전자", "sector": "semi", "priceAssumed": 229000, "amountWon": 4500000,
                            "weightPct": 56.25, "approxShares": 19, "beta": 1.1, "volPct": 30},
                           {"ticker": "000660", "amountWon": 1505000},           # 150.5만원 (입력칸은 소수도 받아요)
                           {"ticker": "AAPL", "amountWon": 123456789}],         # 0.01만원 단위로 반올림 → 12345.68
              "profile": {"ready": True, "targetBetaMin": 0.6, "targetBetaMax": "높게", "title": "균형형", "flags": [], "zzz": 1},
              "settings": {"fx": 1400, "rf": "3%", "mktVol": 20, "junk": 5},
              "metrics": {"beta": 1.0}}
    got = read_file_js({"export": export})
    st = got["out"]["export"]
    assert st["holdings"] == [{"t": "005930", "mw": 450}, {"t": "000660", "mw": 150.5}, {"t": "AAPL", "mw": 12345.68}]
    assert st["budgetMw"] == 2500
    assert st["answers"] == {}                                   # 새로 시작하기처럼: 파일에 없는 답변은 비워요
    assert st["profile"] == {"ready": True, "targetBetaMin": 0.6, "title": "균형형", "flags": []}   # 종류가 다른 칸 · 모르는 칸은 빼요
    assert st["settings"] == {"fx": 1400, "mktVol": 20}
    assert got["warn"] == [], got["warn"]                        # 모두 읽었으면 경고 없음


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_keeps_valid_rows_and_says_how_many_it_dropped():
    rows = [{"ticker": "005930", "amountWon": 3000000},
            {"ticker": "", "amountWon": 1000000},              # 종목코드 없음
            {"ticker": "   ", "amountWon": 1000000},           # 빈칸뿐
            {"amountWon": 1000000},                            # 종목코드 칸이 없음
            {"ticker": "000660", "amountWon": 0},              # 0원
            {"ticker": "000660", "amountWon": -5},             # 음수
            {"ticker": "000660", "amountWon": "300만"},         # 숫자가 아님
            {"ticker": "000660", "amountWon": None},
            {"ticker": "000660", "amountWon": 10},             # 0.001만원 → 반올림하면 0
            None, 7, "005930",
            {"ticker": "005930", "amountWon": 2000000},        # 같은 종목이 또 나옴
            {"ticker": "999999", "name": "상장폐지된 회사", "amountWon": 2000000},   # 지금 종목 목록에 없음 → 이름과 함께 남겨요
            {"ticker": "MYCO", "amountWon": 500000},           # 직접 추가 종목(이름 없음)도 같은 식으로 남겨요
            {"ticker": "AAPL", "amountWon": 1500000}]
    got = read_file_js({"partial": {"app": "Baepsae 뱁새 v12", "budgetWon": 10000000, "holdings": rows},
                        "bad_settings": {"budgetWon": 10000000, "holdings": rows[:1], "settings": {"fx": "1400원"}, "profile": [1]}})
    bs = got["out"]["bad_settings"]
    assert "settings" not in bs and bs["profile"] == {}, bs       # 읽을 칸이 없는 설정은 건드리지 않고, 프로필은 새로 시작하기처럼
    st = got["out"]["partial"]
    assert st["holdings"] == [{"t": "005930", "mw": 300}, {"t": "999999", "mw": 200, "nk": "상장폐지된 회사"}, {"t": "MYCO", "mw": 50},
                              {"t": "AAPL", "mw": 150}], st["holdings"]
    assert st["budgetMw"] == 1000
    assert "settings" not in st                                  # 파일에 설정이 없으면 지금 설정을 그대로 써요
    assert got["warn"] == ["[뱁새] 불러온 파일의 종목 16개: 뺀 줄 12개 (종목코드·금액이 맞지 않거나 겹침) · 지금 종목 목록에 없음 2개 (저장본에는 남겨 둬요)"], got["warn"]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_refuses_files_that_would_open_an_empty_portfolio():
    cases = {
        "export_empty": {"app": "Baepsae 뱁새 v12", "budgetWon": 10000000, "holdings": []},
        "export_all_bad": {"app": "Baepsae 뱁새 v12", "budgetWon": 10000000,
                           "holdings": [{"ticker": "", "amountWon": 100000}, {"ticker": "005930", "amountWon": 0},
                                        {"ticker": "005930", "amountWon": "300만"}, {"ticker": "999999", "amountWon": 100000}]},
        # 줄은 멀쩡해도 지금 목록에 있는 종목이 하나도 없으면 빈 것처럼 보여요 → 열지 않아요
        "export_none_listed": {"app": "Baepsae 뱁새 v12", "budgetWon": 10000000,
                               "holdings": [{"ticker": "999999", "name": "없는 회사", "amountWon": 100000}, {"ticker": "888888", "amountWon": 1}]},
        "state_none_listed": {"state": {"holdings": [{"t": "999999", "mw": 100}]}},
        "export_no_rows": {"app": "Baepsae 뱁새 v12", "budgetWon": 10000000},
        "state_empty": {"state": {"schema": 10, "budgetMw": 1000, "holdings": []}},
        "bare_empty": {"holdings": [], "budgetMw": 500},
        "state_bad": {"state": {"holdings": [{"t": "005930", "mw": 0}, {"t": "", "mw": 100}, {"mw": 100}]}},
        "state_not_object": {"state": "abc"},
        "wrong_shape": {"hello": 1},
        "holdings_not_list": {"holdings": {"t": "005930", "mw": 100}},
        "list": [{"t": "005930", "mw": 100}],
        "null": None, "number": 5, "text": "005930",
    }
    got = read_file_js(cases)
    assert got["out"] == {k: "NULL" for k in cases}, got["out"]
    assert got["warn"].count("[뱁새] 불러올 종목이 없는 파일이에요: 지금 포트폴리오를 그대로 둬요") == len(cases), got["warn"]   # 말없이 거르지 않아요


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_still_reads_old_state_shaped_files():
    old = {"schema": 10, "lang": "ko", "stage": 2, "budgetMw": 1500, "answers": {"q1": 2},
           "holdings": [{"t": "005930", "mw": 500}, {"t": "000660", "mw": 300}, {"t": "999999", "mw": 50}], "checkins": [{"d": "2026-10-01"}],
           "customStocks": [{"t": "MYCO", "nk": "내 회사", "price": 1000, "custom": True}, None],
           "settings": {"fx": 1390}, "tax": {"divKr": 15.4}, "profile": {"ready": True, "targetBetaMax": 1.2},
           "stockEdits": {"005930": {"beta": 1.3}}}
    with_custom = json.loads(json.dumps(old))
    with_custom["holdings"].append({"t": "MYCO", "mw": 100})
    got = read_file_js({"wrapped": {"state": old}, "bare": old, "custom": with_custom})
    myco = {"t": "MYCO", "nk": "내 회사", "ne": "내 회사", "custom": True, "x": {}, "price": 1000}   # 직접 추가 모양으로 다듬어요
    for k in ("wrapped", "bare"):
        st = got["out"][k]
        want = {**old, "customStocks": [myco]}                            # 객체가 아닌 직접 추가 종목은 빼요
        assert st == want, (k, st)                                       # 목록에 없는 999999 도 저장본에 그대로 (예전 저장본처럼)
    assert got["out"]["custom"]["holdings"][-1] == {"t": "MYCO", "mw": 100}  # 파일에 든 직접 추가 종목은 목록에 있는 종목이에요
    drop = "[뱁새] 불러온 파일의 직접 추가 종목 2개 중 1개는 이름·종목코드·숫자가 맞지 않아 뺐어요"
    assert got["warn"] == [drop, "[뱁새] 불러온 파일의 종목 3개: 뺀 줄 0개 (종목코드·금액이 맞지 않거나 겹침) · 지금 종목 목록에 없음 1개 (저장본에는 남겨 둬요)"] * 2 \
        + [drop, "[뱁새] 불러온 파일의 종목 4개: 뺀 줄 0개 (종목코드·금액이 맞지 않거나 겹침) · 지금 종목 목록에 없음 1개 (저장본에는 남겨 둬요)"], got["warn"]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_cleans_hand_made_state_files():
    """손으로 고친 예전 모양 파일이 NaN 화면을 만들지 않아요: 예산 · 언어 · 단계 · 답변을 확인하고, 설정 · 프로필 · 세금은 칸마다 종류를 봐요."""
    h = [{"t": "005930", "mw": 500}]
    cases = {
        "junk": {"state": {"holdings": h, "budgetMw": "많이", "lang": "fr", "stage": 7, "answers": "x",
                           "settings": {"fx": "1400", "rf": 3.1, "zzz": 1}, "profile": {"ready": "yes", "targetBetaMin": 0.5, "zzz": 1},
                           "tax": {"divKr": None, "isaRate": 9.9}}},
        "negative": {"holdings": h, "budgetMw": -100, "stage": "1", "settings": {"fx": None}, "profile": "균형형", "tax": [1]},
        "missing": {"holdings": h},
        "zero_budget": {"holdings": h, "budgetMw": 0, "lang": "en", "stage": 0},
    }
    got = read_file_js(cases)
    o = got["out"]
    assert o["junk"] == {"holdings": h, "budgetMw": 1000, "stage": 1, "settings": {"rf": 3.1}, "profile": {"targetBetaMin": 0.5},
                         "tax": {"isaRate": 9.9}}, o["junk"]                                  # lang · answers 는 빠져서 지금 것 그대로
    assert o["negative"] == {"holdings": h, "budgetMw": 1000, "stage": 1}, o["negative"]     # 읽을 칸이 없는 설정 · 프로필 · 세금은 지금 것 그대로
    assert o["missing"] == {"holdings": h, "budgetMw": 1000, "stage": 1}, o["missing"]
    assert o["zero_budget"] == {"holdings": h, "budgetMw": 0, "lang": "en", "stage": 0}, o["zero_budget"]   # 예산 0(정하지 않음)은 그대로
    assert got["warn"].count("[뱁새] 불러온 파일에 예산(budgetMw)이 없거나 0 이상의 숫자가 아니라 1,000만원으로 시작해요") == 3, got["warn"]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_export_budget_falls_back_loudly():
    rows = [{"ticker": "005930", "amountWon": 3000000}]
    got = read_file_js({"neg": {"budgetWon": -1, "holdings": rows}, "text": {"budgetWon": "1000만", "holdings": rows},
                        "zero": {"budgetWon": 0, "holdings": rows}})
    assert [got["out"][k]["budgetMw"] for k in ("neg", "text", "zero")] == [1000, 1000, 0], got["out"]
    assert got["warn"].count("[뱁새] 불러온 파일에 예산(budgetWon)이 없거나 0 이상의 숫자가 아니라 1,000만원으로 시작해요") == 2, got["warn"]


# 받은 파일의 주소(Blob URL)를 바로 지우면 iOS 사파리가 받다가 실패할 수 있어요 ("WebKitBlobResource error 1").
# 지금 앱의 downloadFile 과 2.0 의 downloadRecords 모두 링크를 페이지에 붙였다 떼고, 주소는 60초 뒤에 지워요 (v18.4.1).
# 화면에서 1.5초 안에 지우지 않는지는 smoke_app.py('파일') · smoke_v2.py('아이폰')가 봐요.
def test_download_links_are_revoked_late():
    src = open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()
    body = src.split("function downloadFile(", 1)[1].split("\n}\n", 1)[0]
    assert "document.body.appendChild(a)" in body and "a.remove()" in body, body
    assert "setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS)" in body and "const REVOKE_AFTER_MS = 60000;" in src, body
    assert body.count("revokeObjectURL") == 1, body
    v2 = open(os.path.join(ROOT, "src", "v2", "store.js"), encoding="utf-8").read()
    body = v2.split("export function downloadRecords(", 1)[1].split("\n}\n", 1)[0]
    assert "setTimeout(() => URL.revokeObjectURL(url), 60000)" in body and body.count("revokeObjectURL") == 1, body


# ── 직접 추가 종목 · 종목 고침 (v18.4.1 두 번째 리뷰) ──
CUSTOM = {"t": "MYCO", "nk": "내 회사", "ne": "내 회사", "s": "semi", "price": 10000, "beta": 1.0, "vol": 35, "per": 10, "pbr": 1,
          "dy": 0, "al": 0, "custom": True, "x": {}}                    # CustomStockForm 이 만드는 모양 그대로


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_brings_back_custom_stocks_from_the_export():
    rows = [{"ticker": "005930", "name": "삼성전자", "amountWon": 3000000}, {"ticker": "MYCO", "name": "내 회사", "amountWon": 1000000}]
    got = read_file_js({"export": {"budgetWon": 10000000, "holdings": rows, "customStocks": [CUSTOM]},
                        "old_export": {"budgetWon": 10000000, "holdings": rows}})                # v18.4.1 전 파일: 정의가 없어요
    st = got["out"]["export"]
    assert st["holdings"] == [{"t": "005930", "mw": 300}, {"t": "MYCO", "mw": 100}] and st["customStocks"] == [CUSTOM], st
    old = got["out"]["old_export"]                                       # 정의 없는 직접 추가 종목은 이름과 함께 저장본에만 남아요
    assert old["holdings"][1] == {"t": "MYCO", "mw": 100, "nk": "내 회사"} and "customStocks" not in old, old


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_drops_custom_stocks_the_app_could_not_have_made():
    bad = [{"t": "NONK", "price": 1000},                                 # 이름 없음 (검색이 nk 를 읽다가 멈춰요)
           {"t": "BLANK", "nk": " ", "price": 1000}, {"t": "", "nk": "코드 없음", "price": 1000},
           {"t": "NOPX", "nk": "가격 없음"}, {"t": "TXT", "nk": "글자 가격", "price": "1000"},
           {"t": "NAN", "nk": "숫자 아님", "price": 1000, "beta": "1.2"}, {"t": "NUL", "nk": "빈 칸", "price": 1000, "vol": None},
           {"t": "SEC", "nk": "업종 숫자", "price": 1000, "s": 5}, None, "MYCO"]
    dup = {**CUSTOM, "nk": "같은 코드 두 번째"}                         # 같은 종목코드가 또 나오면 첫 번째만
    extra = {**CUSTOM, "t": "MYCO2", "cls": "us", "x": {"roe": "높음"}, "zzz": 1}     # 모르는 칸은 버리고 x 는 비워요
    rows = [{"ticker": "005930", "amountWon": 3000000}, {"ticker": "NONK", "name": "이름 없는 회사", "amountWon": 1000000}]
    got = read_file_js({
        "export": {"budgetWon": 10000000, "holdings": rows, "customStocks": [CUSTOM] + bad + [dup, extra]},
        "only_bad": {"budgetWon": 10000000, "holdings": rows[1:], "customStocks": bad},          # 남는 종목이 없으면 열지 않아요
        "state": {"holdings": [{"t": "005930", "mw": 300}, {"t": "NONK", "mw": 100}], "budgetMw": 1000, "customStocks": bad},
    })
    st = got["out"]["export"]
    assert st["customStocks"] == [CUSTOM, {k: v for k, v in extra.items() if k not in ("cls", "zzz")} | {"x": {}}], st["customStocks"]
    assert st["holdings"][1] == {"t": "NONK", "mw": 100, "nk": "이름 없는 회사"}      # 정의가 빠진 종목은 저장본에만 (화면 목록에 없음)
    assert got["out"]["only_bad"] == "NULL"
    assert got["out"]["state"]["customStocks"] == [] and got["out"]["state"]["holdings"][1] == {"t": "NONK", "mw": 100}
    assert got["warn"].count("[뱁새] 불러온 파일의 직접 추가 종목 13개 중 11개는 이름·종목코드·숫자가 맞지 않아 뺐어요") == 1, got["warn"]
    assert got["warn"].count("[뱁새] 불러온 파일의 직접 추가 종목 10개 중 10개는 이름·종목코드·숫자가 맞지 않아 뺐어요") == 2, got["warn"]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_import_keeps_only_numeric_stock_edits():
    h = [{"t": "005930", "mw": 300}]
    got = read_file_js({
        "dy_text": {"holdings": h, "budgetMw": 1000, "stockEdits": {"005930": {"dy": "x"}}},
        "mixed": {"holdings": h, "budgetMw": 1000, "stockEdits": {"005930": {"dy": 2.5, "price": "1", "zzz": 1, "beta": None},
                                                                     "000660": "x", "AAPL": [1], "__proto__": {"price": 1}}},
        "not_object": {"holdings": h, "budgetMw": 1000, "stockEdits": [1, 2]},
        "none": {"holdings": h, "budgetMw": 1000},
    })
    o = got["out"]
    assert o["dy_text"]["stockEdits"] == {} and o["mixed"]["stockEdits"] == {"005930": {"dy": 2.5}}, o
    assert o["not_object"]["stockEdits"] == {} and "stockEdits" not in o["none"], o
    assert got["warn"] == ["[뱁새] 불러온 파일의 종목 고침 중 1개는 숫자가 아니라서 뺐어요",
                           "[뱁새] 불러온 파일의 종목 고침 중 6개는 숫자가 아니라서 뺐어요",
                           "[뱁새] 불러온 파일의 종목 고침 중 1개는 숫자가 아니라서 뺐어요"], got["warn"]
    # 고침이 NaN 을 만들지 않아요: 남은 값으로 위험 수치를 셈해도 숫자예요
    m = run_metrics("const st0 = D.readPortfolioFile({ holdings: [{ t: '005930', mw: 300 }], stockEdits: { '005930': { dy: 'x', beta: '1.2' } } },"
                    " new Set(['005930'])); const S = { t: '005930', cls: 'kr', s: 'semi', beta: 1.2, vol: 33, price: 1, dy: 2,"
                    " ...(st0.stockEdits['005930'] || {}) }; const r = D.computeMetrics([h(S, 300)], 1000 * 10000, st);"
                    " console.log(JSON.stringify({ beta: r.beta, vol: r.volP, dy: S.dy }));")
    assert m == {"beta": m["beta"], "vol": m["vol"], "dy": 2} and isinstance(m["beta"], float) and isinstance(m["vol"], float), m


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_share_card_skips_holdings_missing_from_todays_list():
    got = run_metrics("const warn = []; console.warn = (m) => warn.push(String(m));"
                      "const by = { '005930': { t: '005930', nk: '삼성전자', cls: 'kr' }, AAPL: { t: 'AAPL', nk: 'Apple', cls: 'us' } };"
                      "const d = D.makeCardData([{ t: '005930', mw: 300 }, { t: 'GONE1', mw: 900, nk: '없는 회사' }, { t: 'AAPL', mw: 100 }], by, 600, null, 'ko');"
                      "console.log(JSON.stringify({ top: d.top, buckets: d.buckets.map((b) => [b.ko, Math.round(b.pct)]), warn }));")
    assert got["top"] == [{"nk": "삼성전자", "pct": 30}, {"nk": "Apple", "pct": 10}], got["top"]   # 없는 종목(900만원)은 1등이 아니라 아예 빠져요
    assert got["buckets"] == [["국내 주식", 30], ["미국 주식", 10], ["현금", 60]], got["buckets"]
    assert got["warn"] == ["[뱁새] 공유 카드: 오늘 종목 목록에 없는 종목 1개는 빼고 만들었어요"], got["warn"]
