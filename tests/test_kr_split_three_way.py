# -*- coding: utf-8 -*-
"""한국 주식 분할: 세 확인 · 공시로 확인하지 못한 분할 (2026-11-27 · Jack 의 답 4 · 11 · 새 시험 파일 · #186 다시 짓기).

Jack, 2026-11-27 (그대로):
- 답 4: "#186: yes, as long as the filing text is cross-checked against the change in share count and the price jump on the effective date."
- 답 11: "A split without a filing stops the publish only for a must-have stock (삼성전자, NAVER, 카카오) or when many appear in one run.
  Any other stock gets its affected numbers blanked with '주식 수가 크게 바뀌었는데, 공시로 확인하지 못해서 이 숫자는 비워 두었어요.'"

파이프라인 (fetch_data.py kr_split_checks · kr_split_market_whole · mark_split_nofile) 과 관문 (validate_data.py check_kr_split_nofile ·
kr_split_receipt_ok) 을 봐요:
1. 세 확인 — 공시의 상장예정일 = 그 날 (dl) · 그날 상장주식수 (shr) · 그날 기준가 (px). 하나라도 빠지면 싣지 않아요 · 영수증이 세 확인의 이름과 값을 적어요.
2. 삼성전자 2018 고정 줄: 표에 적은 시세 근거가 같은 세 확인을 지나야 실려요.
3. 공시로 확인하지 못한 분할 — 필수 종목은 관문 실패 · 하루에 5건 이상 새로 나오면 실패 · 그 밖의 종목은 계산 창에 든 숫자를 비워요.
4. 한 번 실은 줄은 빼지 않아요 (예전 규칙 그대로) · 미국 줄은 그대로.
앱 쪽 (2.0 의 줄 · 예전 뱁새) 은 tests/test_kr_split_nofile_app.py, 팔았어요의 몫은 tests/test_kr_split_fractions.py.
"""
import copy
import datetime as dt
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_kr_splits as K  # noqa: E402  (픽스처 · 가짜 DART · 후보 도우미를 그대로 써요)
import test_v196a_fxhist_splits as T196  # noqa: E402

TODAY = K.TODAY
JACK_LINE = "주식 수가 크게 바뀌었는데, 공시로 확인하지 못해서 이 숫자는 비워 두었어요."


@pytest.fixture(autouse=True)
def _dart_path_for_naver_and_kakao(monkeypatch):
    """2026-11-28 (1차 리뷰 Fable S4 · 조정자 8): NAVER 2018-10-12 · 카카오 2021-04-15 는 고정 줄이 됐어요 (KR_SPLIT_OVERRIDES · 2026-11-23 에 읽은
    원문의 숫자를 적어 둠). 이 파일의 시험은 그 두 사건의 진짜 원문 픽스처로 DART 길을 보니, 시험 안에서는 그 두 고정 줄을 빼요 (고정 줄 자체는
    tests/test_kr_split_round1.py 가 봐요)."""
    monkeypatch.setattr(F, "KR_SPLIT_OVERRIDES", {k: v for k, v in F.KR_SPLIT_OVERRIDES.items() if k[0] not in ("035420", "035720")})


def naver_dart(**kw):
    return K.FakeDart(lists={("00266961", "I001"): K.fx("list_00266961_I001.json")}, docs={"20180726800004": K.raw("doc_20180726800004.xml")}, **kw)


# ── 1. 세 확인: 영수증이 이름과 값을 적어요 ──────────────────────────────────────────────────────────────

def test_a_published_row_names_its_three_checks_in_its_receipt(monkeypatch):
    K.Log(monkeypatch)
    rows, info = F.kr_splits_fields(None, K.kr_rows("035420"), [], naver_dart(), TODAY, seed=[K.cand("035420")])
    assert rows == [["035420", "2018-10-12", 5.0]]
    rec = info["rows"][0]
    assert rec[:6] == ["035420", "2018-10-12", 5.0, "split", "20180726800004", "doc"]
    assert rec[6] == {"dl": "2018-10-12", "shr": 5.0, "px": round(704000 / 141000, 6), "rule": "split"}    # 공시 상장일 · 주식 수 ×5.000 · 기준가 ÷ 4.993
    assert V.kr_split_receipt_ok(rec)                                                                   # 관문이 같은 선으로 다시 봐요 (경고 줄)
    # 병합 (감자결정 · 동시호가 기준가): rule auction
    _rows, info = F.kr_splits_fields(None, K.kr_rows("117670"), [], K.alpha_dart(), TODAY, seed=[K.cand("117670")])
    assert info["rows"][0][6]["rule"] == "auction" and V.kr_split_receipt_ok(info["rows"][0])
    # 관문의 영수증 확인: 한 칸이라도 틀리면 경고 줄에 이름이 나와요 (실패는 아니에요)
    for bad in ({**rec[6], "dl": "2018-10-11"}, {**rec[6], "shr": 4.0}, {**rec[6], "px": 4.0}, {**rec[6], "rule": "auction"}, None):
        assert not V.kr_split_receipt_ok(rec[:6] + ([bad] if bad else []))
    assert V.kr_split_receipt_ok(["035720", "2021-04-15", 5.0, "fixed", "SPLIT_OVERRIDES", "fixed"])  # SPLIT_OVERRIDES 로 고친 줄은 여섯 칸


@pytest.mark.parametrize("what, patch, code", [
    ("공시 없음", None, "nodoc"),
    ("공시의 상장일이 그 날이 아님", {"d": "2021-04-14"}, "diff"),
    ("주식 수가 공시의 배율과 다름 (×2)", {"sb": 88761861 * 2.0, "base": 279000.0}, "shr"),
    ("기준가가 공시의 배율과 다름 (주식 수는 ×5)", {"base": 140000.0}, "px"),
])
def test_each_missing_signal_rejects_the_row(monkeypatch, what, patch, code):
    """카카오 2021-04-15 5:1 의 진짜 공시와 시세에서 하나씩 빼요: 공시 · 공시 상장일 · 주식 수 · 기준가."""
    K.Log(monkeypatch)
    c = K.FakeDart() if patch is None else K.kakao_dart()
    cand = K.cand("035720") if patch is None else {**K.cand("035720"), **patch}
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720", "000040"), [], c, TODAY, seed=[cand])
    assert rows == [] and info["new"] == [], what
    assert info["out"] == [["035720", cand["d"], code]], (what, info["out"])
    assert code in F.KR_SPLIT_OUT_WHY


def test_the_three_checks_one_by_one():
    c = K.cand("035720")
    ok, bad = F.kr_split_checks(5.0, c, "2021-04-15")
    assert bad is None and ok == {"dl": "2021-04-15", "shr": 5.0, "px": 4.982143, "rule": "split"}
    assert F.kr_split_checks(5.0, c, "2021-04-14") == (None, "date")
    assert F.kr_split_checks(5.0, c, None) == (None, "date")
    assert F.kr_split_checks(4.0, c, "2021-04-15")[1] == "shr"                         # 주식 수 ×5 ≠ ×4 (± 10% 밖)
    assert F.kr_split_checks(5.0, {**c, "base": 140000.0}, "2021-04-15")[1] == "px"     # 558,000 ÷ 140,000 = ×3.99
    assert F.kr_split_checks(5.0, {**c, "base": None}, "2021-04-15")[1] == "px"         # 기준가를 모르면 확인하지 못해요
    # 분할: 주식 수는 ± 10% (영풍 ×10.37) · 기준가는 ± 1%
    assert F.kr_split_checks(10.0, {"d": "x", "close": 1000.0, "base": 100.0, "sa": 100.0, "sb": 1037.0}, "x")[0] is not None
    assert F.kr_split_checks(10.0, {"d": "x", "close": 1000.0, "base": 100.0, "sa": 100.0, "sb": 1120.0}, "x")[1] == "shr"
    assert F.kr_split_checks(10.0, {"d": "x", "close": 1000.0, "base": 102.0, "sa": 100.0, "sb": 1000.0}, "x")[1] == "px"
    # 병합: 주식 수는 정확히 (± 1%) · 기준가는 동시호가 (배율의 ½ ~ 2배 · 10% 넘게 움직임)
    m = {"d": "x", "close": 790.0, "base": 9580.0, "sa": 61394681.0, "sb": 6139468.0}       # 알파칩스 10:1 감자
    assert F.kr_split_checks(0.1, m, "x")[0]["rule"] == "auction"
    assert F.kr_split_checks(0.1, {**m, "sb": 6139468.0 * 1.05}, "x")[1] == "shr"          # 병합은 주식 수가 정확해야 해요
    assert F.kr_split_checks(0.1, {**m, "base": 790.0}, "x")[1] == "px"                    # 거래정지 날 줄: 기준가 그대로
    assert F.kr_split_checks(0.1, {**m, "base": 3000.0}, "x")[1] == "px"                   # ÷ 10 의 ½ 보다 작게 (×3.8)
    assert F.kr_split_checks(0.1, {**m, "base": 16000.0}, "x")[1] == "px"                  # ÷ 10 의 2배 넘게
    assert F.kr_split_checks(0.1, {**m, "base": 15700.0}, "x")[0] is not None              # 2배 안


def test_a_cached_ok_verdict_that_now_fails_a_market_check_is_not_published(monkeypatch):
    """보관본의 판정 (예전 규칙의 'ok') 도 실을 때마다 세 확인을 다시 해요 — 그날 기준가가 공시의 배율과 맞지 않으면 싣지 않아요 (DART 호출 없이)."""
    K.Log(monkeypatch)
    c = K.FakeDart()
    c.entries["00258801|krsplit|v2|2021-04-15"] = K.ok_verdict(5.0)
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720"), [], c, TODAY, seed=[{**K.cand("035720"), "base": 140000.0}])
    assert rows == [] and info["out"] == [["035720", "2021-04-15", "px"]] and c.calls == []
    c.entries["00258801|krsplit|v2|2021-04-15"] = K.ok_verdict(5.0, dl="2021-04-16")             # 판정의 상장일이 그 날이 아니면
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720"), [], c, TODAY, seed=[K.cand("035720")])
    assert rows == [] and info["out"] == [["035720", "2021-04-15", "diff"]]


def test_a_market_candidate_needs_both_market_signals():
    # 주식 수가 정확히 1:n 이어도 그날 기준가가 움직이지 않으면 (거래정지 날 줄) 후보가 아니에요 — 시드에서 뺀 13줄의 모양
    assert F.kr_split_event(171, 171, 159224163, 15922416) == (None, None)
    assert F.kr_split_event(790, 9580, 61394681, 6139468) == (0.1, "auc")
    assert F.kr_split_event(1000, 5000, 100, 20) == (0.2, "px")                        # 병합도 기준가가 정확히 앞날 ÷ 배율이면 'px'
    assert F.kr_split_event(1000, 1000, 100, 200) == (None, None)                      # 무상증자 새 주식 상장일 (기준가 그대로)
    # 시드: 모든 줄이 오늘의 규칙을 지나요 (불러올 때 다시 해요) · 11-27 에 뺀 13줄 중 7줄은 여전히 없어요 (6줄은 두 날 규칙으로 돌아왔어요:
    # tests/test_kr_split_round1.py)
    seed = F.load_kr_split_seed()
    assert len(seed) == 586 and {x["how"] for x in seed} == {"px", "auc", "pair"}
    gone = {("101140", "2023-10-23"), ("007700", "2021-05-21"), ("001230", "2023-06-16"), ("017650", "2020-07-08"), ("036630", "2025-04-04"),
            ("036630", "2025-11-12"), ("900260", "2022-12-29")}
    assert not gone & {(x["t"], x["d"]) for x in seed}
    for x in seed:
        if x["r"] < 1 and F.kr_split_whole(x["sb"] / x["sa"]) is not None:
            assert F.kr_split_market_checks(x["r"], x["close"], x["base"], x["sa"], x["sb"])[0] is not None, (x["t"], x["d"])


# ── 2. 삼성전자 2018 고정 줄: 시세 근거를 적고 같은 세 확인 ──────────────────────────────────────────────────

def test_the_samsung_2018_fixed_rows_carry_their_market_evidence_and_pass_the_same_checks(monkeypatch):
    log = K.Log(monkeypatch)
    seed = {(x["t"], x["d"]): x for x in F.load_kr_split_seed()}
    for t in ("005930", "005935"):
        ev = F.KR_SPLIT_OVERRIDE_EVIDENCE[(t, "2018-05-04")]
        x = seed[(t, "2018-05-04")]
        assert (ev["close"], ev["base"], ev["sa"], ev["sb"]) == (x["close"], x["base"], x["sa"], x["sb"])   # 시드의 다음 줄과 같은 숫자
        assert ev["dl"] == "2018-05-04" and ev["rc"] == "20180316800856"
        chk, bad = F.kr_split_checks(50.0, {"d": "2018-05-04", **ev}, ev["dl"])
        assert bad is None and chk == {"dl": "2018-05-04", "shr": 50.0, "px": 50.0, "rule": "split"}
    assert {k for k, v in F.KR_SPLIT_OVERRIDES.items() if v[0] is not None} <= set(F.KR_SPLIT_OVERRIDE_EVIDENCE)
    rows, info = F.kr_splits_fields(None, K.kr_rows("005930", "005935"), [], None, TODAY, seed=[])
    assert rows == [["005930", "2018-05-04", 50.0], ["005935", "2018-05-04", 50.0]]
    assert all(V.kr_split_receipt_ok(r) and r[6]["doc"] == "list" for r in info["rows"])
    # 근거가 세 확인을 지나지 못하면 새로 싣지 않고 크게 (이미 실은 줄은 그대로)
    bad = dict(F.KR_SPLIT_OVERRIDE_EVIDENCE)
    bad[("005930", "2018-05-04")] = {**bad[("005930", "2018-05-04")], "base": 2650000.0}
    monkeypatch.setattr(F, "KR_SPLIT_OVERRIDE_EVIDENCE", bad)
    rows, _ = F.kr_splits_fields(None, K.kr_rows("005930", "005935"), [], None, TODAY, seed=[])
    assert rows == [["005935", "2018-05-04", 50.0]]
    assert log.has("!! 한국 주식 분할: KR_SPLIT_OVERRIDES 의 005930 2018-05-04 ×50", "세 확인을 지나지 못해요 (px)")
    prev = {"splits": [["005930", "2018-05-04", 50.0]], "splitsKr": {"rows": [["005930", "2018-05-04", 50.0, "fixed", "KR_SPLIT_OVERRIDES", "fixed"]]}}
    rows, _ = F.kr_splits_fields(prev, K.kr_rows("005930", "005935"), [], None, TODAY, seed=[])
    assert ["005930", "2018-05-04", 50.0] in rows                                                     # 한 번 실은 줄은 빼지 않아요


# ── 3. 공시로 확인하지 못한 분할 ─────────────────────────────────────────────────────────────────────────

def nodoc_dart():
    return K.FakeDart()                                     # 수시공시 목록이 비어요 (013) → 결정 공시 없음


def seed_split(t, d, r=5.0):
    """주식 수 ×r 정확히 · 기준가 ÷ r 정확히인 분할 후보 (시드 모양)."""
    return F._kr_cand(t, d, 5000.0 * r, 5000.0, 1_000_000.0, 1_000_000.0 * r, "seed")


def test_an_exact_market_split_without_a_confirming_filing_is_listed_with_its_code(monkeypatch):
    K.Log(monkeypatch)
    kr = K.kr_rows("000010", "000020", "000030")
    cmap = {"000010": "C1", "000020": "C2", "000030": "C3"}
    snap = {**seed_split("000030", "2026-11-02"), "sb": 1_000_000.0 * 4.6, "base": 5000.0 * 5 / 4.6}    # 깨끗한 배율이지만 주식 수가 정확하지 않아요
    rows, info = F.kr_splits_fields(None, kr, [], nodoc_dart(), TODAY, seed=[seed_split("000010", "2026-11-02"), seed_split("000020", "2025-03-04", 0.2), snap],
                                    cmap=cmap)
    assert rows == []
    assert info["nofile"] == [["000010", "2026-11-02", 5.0, "nodoc"], ["000020", "2025-03-04", 0.2, "nodoc"]] and info["nofileN"] == 2
    assert F.kr_split_market_whole(snap) is None                                            # 주식 수가 정확하지 않은 사건은 이 목록이 아니에요
    # 공시가 있는데 그날 시세와 맞지 않아도 (확인해 주는 공시가 없어요) · DART 기업코드가 없어도
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720", "000040"), [], K.kakao_dart(), TODAY,
                                    seed=[{**K.cand("035720"), "sb": 88761861 * 2.0, "base": 279000.0}, seed_split("000040", "2026-10-01")],
                                    cmap={"035720": "00258801"})
    assert info["nofile"] == [["000040", "2026-10-01", 5.0, "nocorp"], ["035720", "2021-04-15", 2.0, "shr"]]


def test_a_confirmed_or_fixed_or_published_event_is_never_listed(monkeypatch):
    K.Log(monkeypatch)
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720", "005930"), [], K.kakao_dart(), TODAY, seed=[K.cand("035720")] + F.load_kr_split_seed())
    assert ["035720", "2021-04-15", 5.0] in rows and ["005930", "2018-05-04", 50.0] in rows and info["nofile"] == []


def test_the_list_is_carried_while_the_event_is_not_judged_and_leaves_when_it_is_confirmed(monkeypatch):
    K.Log(monkeypatch)
    prev = {"splits": [], "splitsKr": {"nofile": [["000010", "2026-11-02", 5.0, "nodoc"], ["000020", "2016-03-02", 5.0, "nodoc"],
                                                  ["000099", "2026-11-02", 5.0, "nodoc"], ["000030", "2026-11-03", 5.0, "bad code"], "x"]}}
    kr = K.kr_rows("000010", "000020", "000030")
    # DART 꺼짐 (판정을 읽지 못함): 지난 발행본의 줄을 그대로 — 오늘 목록에 없는 종목의 줄도 (1차 리뷰 B1) · 시계열보다 오래된 사건 · 모양이 틀린 줄은 빼요
    _rows, info = F.kr_splits_fields(prev, kr, [], None, TODAY, seed=[seed_split("000010", "2026-11-02")])
    assert info["nofile"] == [["000099", "2026-11-02", 5.0, "nodoc"], ["000010", "2026-11-02", 5.0, "nodoc"]]
    # 단계 전체가 멈춰도 (src err) 그대로
    monkeypatch.setattr(F, "_kr_splits_fields", lambda *a: 1 / 0)
    _rows, info = F.kr_splits_fields(prev, kr, [], None, TODAY, seed=[])
    assert info["src"] == "err" and info["nofile"] == [["000010", "2026-11-02", 5.0, "nodoc"], ["000099", "2026-11-02", 5.0, "nodoc"]]
    monkeypatch.undo()
    K.Log(monkeypatch)
    # 정정 공시로 확인되면 빠져요 (오늘 판정: ok)
    c = K.FakeDart()
    c.entries["C1|krsplit|v2|2026-11-02"] = K.ok_verdict(5.0, "20261001000001", "split", "2026-11-02")
    rows, info = F.kr_splits_fields(prev, kr, [], c, TODAY, seed=[seed_split("000010", "2026-11-02")], cmap={"000010": "C1"})
    assert rows == [["000010", "2026-11-02", 5.0]] and info["nofile"] == [["000099", "2026-11-02", 5.0, "nodoc"]]   # 오늘 목록에 없는 종목의 줄은 그대로


def test_mark_split_nofile_blanks_the_numbers_of_the_windows_that_hold_the_event(monkeypatch):
    log = K.Log(monkeypatch)
    full = {k: 1.0 for k in V.PX_BAD_DATA}
    stocks = [{"t": t, "nk": t, "cls": "kr", "price": 1000.0, **full} for t in ("000010", "000020", "000030", "000040", "000050", "035720", "000060")]
    stocks.append({"t": "AAPL", "cls": "us", **full})
    stocks[5]["spNo"] = "2020-01-01"                                                       # 어제 표시는 오늘 다시 정해요
    cut = {"y": "2025-11-20", "q": "2026-08-25", "m": "2026-10-23", "s": "2023-10-10"}
    cuts = {t: cut for t in ("000010", "000020", "000030", "000040", "035720")}
    nofile = [["000010", "2026-11-02", 5.0, "nodoc"],                                      # 22봉 안: 모두
              ["000020", "2026-05-08", 5.0, "nodoc"],                                      # 252봉 안 · 64봉 밖: 52주 · 1년 · 추세 + 시계열 전체
              ["000030", "2024-01-19", 5.0, "diff"],                                       # 252봉 밖: 시계열 전체만 (52주는 보여요)
              ["000040", "2023-01-02", 5.0, "nodoc"],                                      # 시계열보다 앞: 비울 숫자가 없어요
              ["000050", "2026-11-02", 0.2, "nocorp"],                                     # 창을 모름 (마지막 확인 종가로 실은 종목): 모두
              ["035720", "2026-11-02", 5.0, "nodoc"],                                      # 필수 종목: 비우지 않아요 (관문이 막아요)
              ["AAPL", "2026-11-02", 5.0, "nodoc"]]
    got = F.mark_split_nofile(stocks, nofile, cuts)
    by = {s["t"]: s for s in stocks}
    assert got["hidden"] == ["000010", "000020", "000030", "000050"] and got["must"] == ["035720"] and got["before"] == ["000040"]
    assert got["noCut"] == ["000050"]
    assert by["000010"]["spNoF"] == list(V.PX_BAD_DATA) and by["000050"]["spNoF"] == list(V.PX_BAD_DATA)
    yf = [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS or k in V.PX_BAD_WIN["y"]]
    assert by["000020"]["spNoF"] == yf and by["000030"]["spNoF"] == [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS]
    for t in ("000010", "000020", "000030", "000050"):
        assert all(k not in by[t] for k in by[t]["spNoF"]) and by[t]["spNo"] == [x[1] for x in nofile if x[0] == t][0]
        assert not V.px_bad_fields_problems(t, by[t]["spNoF"], by[t]["spNo"], dt.date(2026, 11, 20))   # 과거 주가 기록 오류와 같은 창 규칙
    assert by["000030"]["hi"] == 1.0 and by["000030"]["r1"] == 1.0                         # 52주 · 1개월은 그대로
    assert "spNo" not in by["035720"] and "spNo" not in by["000040"] and "spNo" not in by["AAPL"] and by["035720"]["vol"] == 1.0
    assert log.has("!! 공시로 확인하지 못한 분할로 숫자를 비운 국내 종목: 4", "필수 종목은 비우지 않아요", "035720")
    # 과거 주가 기록 오류 표시(pxBad)도 있는 종목: pxBadF 를 두 목록의 합으로 (관문의 그 줄이 받아요)
    s = {"t": "000070", "cls": "kr", **{k: v for k, v in full.items() if k not in V.PX_BAD_ALWAYS}, "pxBad": "2024-01-19",
         "pxBadF": [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS]}
    F.mark_split_nofile([s], [["000070", "2026-11-02", 5.0, "nodoc"]], {"000070": cut})
    assert s["spNoF"] == list(V.PX_BAD_DATA) and s["pxBadF"] == list(V.PX_BAD_DATA) and "hi" not in s


def test_build_corp_carries_the_mark_with_the_blanked_numbers():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    i = src.index("def build_corp(")
    body = src[i:src.index("\ndef ", i + 10)]
    assert 'row["spNo"] = s["spNo"]' in body and 'row["spNoF"] = list(s.get("spNoF") or [])' in body
    # main: 한국 분할 단계 바로 뒤 · 점수(add_percentiles) · corp.json 보다 먼저
    m = src[src.index("def main():"):]
    assert m.index("mark_split_nofile(kr, nf, kmeta.get(\"_winAll\") or {})") < m.index("add_percentiles(kr)") < m.index("corp = build_corp(")
    assert m.index("kr_splits_step(sp_fields, prev, kr, client") < m.index("mark_split_nofile(kr, nf")


# ── 3b. 관문: 필수 종목 · 하루에 많이 (실패) · 비움 (경고) ─────────────────────────────────────────────────

def gate_with(nofile, prev_nofile=None, mark=None, prev_info=True, run_new=()):
    cur, prev, final = K.gate_pair()
    cur["data"]["splitsKr"]["nofile"] = nofile
    cur["data"]["splitsKr"]["nofileN"] = len(nofile)
    cur["data"]["splitsKr"]["runNew"] = [list(x[:2]) for x in run_new]
    if prev_info:
        prev["data"]["splitsKr"] = {"nofile": prev_nofile or []}
    for t, d, fl in mark or []:
        s = next(x for x in cur["data"]["stocks"] if x["t"] == t)
        for k in fl:
            s.pop(k, None)
        s["spNo"], s["spNoF"] = d, list(fl)
        c = next((x for x in cur["corp"]["companies"] if x["t"] == t), None)
        if c is not None:
            c.update({k: None for k in V.PX_BAD_CORP if k in fl}, spNo=d, spNoF=list(fl))
    return T196.check(cur, prev, final)


def a_kr_stock():
    cur, _p, _f = K.gate_pair()
    return next(s["t"] for s in cur["data"]["stocks"] if s.get("cls") == "kr" and s["t"] not in V.KR_SPLIT_MUST and s.get("vol") is not None
                and s.get("hi") is not None and any(c["t"] == s["t"] for c in cur["corp"]["companies"]))


@pytest.mark.parametrize("t", ["005930", "035420", "035720", "000660"])
def test_gate_fails_for_a_must_have_stock(t):
    rep = gate_with([[t, "2026-10-27", 5.0, "nodoc"]])
    assert [r[0] for r in rep.failed] == [V.KR_NOFILE_MUST_ROW], rep.table()
    assert t in T196.row(rep, V.KR_NOFILE_MUST_ROW)[1]
    assert set(("005930", "035420", "035720")) <= set(V.KR_SPLIT_MUST) and set(V.MUST) <= set(V.KR_SPLIT_MUST)
    # 오래된 사건이어도 (필수 종목의 분할은 날짜와 상관없이 기록을 틀리게 해요)
    rep = gate_with([[t, "2016-05-02", 5.0, "gone"]])
    assert [r[0] for r in rep.failed] == [V.KR_NOFILE_MUST_ROW]


def test_gate_fails_when_many_appear_in_one_run():
    """1차 리뷰 뒤 (조정자 5 · Jack 의 말 "when many appear in one run") · 2차 리뷰 B1: 이 실행이 스스로 판정해 처음 생긴 nofile 줄 (splitsKr.runNew) 이
    KR_SPLIT_NOFILE_RUN_FAIL 건 이상이면 실패 — 사건 날짜와 상관없이. 직전 발행본 뒤 새로 생긴 줄 (발행하지 못한 실행의 판정이 보관본에서 다시 실린 것도)
    은 경고 줄에만 보여요."""
    n = V.KR_SPLIT_NOFILE_RUN_FAIL
    many = [[f"9{i:04d}0", f"20{16 + i % 10}-0{1 + i % 9}-1{i % 9}", 0.2, "nodoc"] for i in range(n)]
    rep = gate_with(many, run_new=many)
    assert [r[0] for r in rep.failed] == [V.KR_NOFILE_RUN_ROW], rep.table()
    assert T196.row(rep, V.KR_NOFILE_RUN_ROW)[1].startswith(f"이 실행이 새로 판정 {n}건")
    assert T196.row(rep, V.KR_NOFILE_SUM_ROW)[3] == "WARN" and f"이 실행이 새로 판정 {n}건 · 직전 발행본 뒤 새로 {n}건" in T196.row(rep, V.KR_NOFILE_SUM_ROW)[1]
    assert not gate_with(many, run_new=many[:-1]).failed                                     # 한 건 모자라면 통과
    # 2차 리뷰 B1: 직전 발행본 뒤 새로 n 건이어도 이 실행이 판정한 것이 아니면 (발행하지 못한 실행들의 판정 · 다시 실은 발행본) 통과하고 경고만
    rep = gate_with(many)
    assert not rep.failed and T196.row(rep, V.KR_NOFILE_RUN_ROW)[1] == "이 실행이 새로 판정 0건", rep.table()
    assert T196.row(rep, V.KR_NOFILE_SUM_ROW)[3] == "WARN" and f"직전 발행본 뒤 새로 {n}건" in T196.row(rep, V.KR_NOFILE_SUM_ROW)[1]
    rep = gate_with(many, prev_info=False)                                                  # 직전 발행본에 splitsKr 이 없어도 (되돌린 뒤 다시 들어온 날)
    assert not rep.failed, rep.table()
    # runNew 가 없거나 모양이 틀리면 실패 (이 실행의 수를 몰라요)
    for bad in (None, "x", {"a": 1}):
        cur, prev, final = K.gate_pair()
        cur["data"]["splitsKr"].update(nofile=many[:1], nofileN=1)
        if bad is None:
            cur["data"]["splitsKr"].pop("runNew")
        else:
            cur["data"]["splitsKr"]["runNew"] = bad
        rep = T196.check(cur, prev, final)
        assert [r[0] for r in rep.failed] == [V.KR_NOFILE_RUN_ROW] and "splitsKr.runNew" in T196.row(rep, V.KR_NOFILE_RUN_ROW)[1], rep.table()
    cur, prev, final = K.gate_pair()                                                          # 직전 발행본이 없어도 이 실행의 수로 봐요
    cur["data"]["splitsKr"].update(nofile=many, runNew=[x[:2] for x in many])
    rep = V.run_checks(cur, None, final, T196.TODAY, mode="publish", count_between=lambda a, b: 1, sessions=T196.SESSIONS, now=T196.NOW,
                       hilo=T196.hilo_of(cur, V.MUST))
    assert T196.row(rep, V.KR_NOFILE_RUN_ROW)[3] == "FAIL"
    assert V.KR_SPLIT_NOFILE_RUN_FAIL == 16


def test_gate_passes_a_blanked_non_must_have_stock_and_warns_when_a_number_is_left():
    t = a_kr_stock()
    fl = list(V.PX_BAD_DATA)
    rep = gate_with([[t, "2026-10-27", 5.0, "nodoc"]], mark=[(t, "2026-10-27", fl)])
    assert not rep.failed, rep.table()
    assert T196.row(rep, V.KR_NOFILE_HIDE_ROW)[3] == "PASS" and T196.row(rep, V.KR_NOFILE_MUST_ROW)[3] == "PASS"
    assert T196.row(rep, V.KR_NOFILE_RUN_ROW)[3] == "PASS"
    # 비우지 않았거나 · 한 칸이 남았거나 · 표시만 있으면: 경고 (실패 줄로 할지는 Jack 이 정해요)
    for nofile, mark, said in (([[t, "2026-10-27", 5.0, "nodoc"]], None, "비우지 않음"),
                               ([[t, "2026-10-27", 5.0, "nodoc"]], [(t, "2026-10-27", [k for k in fl if k != "vol"])], "spNoF 에 시계열 전체 칸이 빠짐"),
                               ([], [(t, "2026-10-27", fl)], "nofile 의 날짜가 아니에요")):
        rep = gate_with(nofile, mark=mark)
        assert not rep.failed and T196.row(rep, V.KR_NOFILE_HIDE_ROW)[3] == "WARN", rep.table()
        assert said in T196.row(rep, V.KR_NOFILE_HIDE_ROW)[1], (said, T196.row(rep, V.KR_NOFILE_HIDE_ROW))


def test_gate_rows_on_files_without_the_list_and_on_odd_values():
    cur, prev, final = K.gate_pair(info=False)                                     # 이 PR 전 파일 (사이트의 --live): 확인할 목록이 없어요
    rep = T196.check(cur, prev, final)
    assert not rep.failed and T196.row(rep, V.KR_NOFILE_MUST_ROW)[3] == "PASS" and T196.row(rep, V.KR_NOFILE_RUN_ROW)[3] == "PASS"
    for odd in ([None, [1, 2], ["005930"], "x", [["000010", 5, None, None]]], "not a list"):
        rep = gate_with(odd) if isinstance(odd, list) else None
        if rep is not None:
            fails = [r[0] for r in rep.failed]
            assert fails in ([], [V.KR_NOFILE_MUST_ROW]), rep.table()                 # 모양이 틀려도 필수 종목 코드는 잡아요
            assert (fails == [V.KR_NOFILE_MUST_ROW]) == any(isinstance(x, list) and x and x[0] == "005930" for x in odd)
    cur, prev, final = K.gate_pair()
    cur["data"]["splitsKr"]["nofile"] = "x"
    rep = T196.check(cur, prev, final)
    assert [r[0] for r in rep.failed] == [V.KR_NOFILE_MUST_ROW] and "모양이 잘못됐어요" in T196.row(rep, V.KR_NOFILE_MUST_ROW)[1]


def test_the_pipeline_and_the_gate_use_the_same_must_have_list_and_run_limit():
    assert F.KR_SPLIT_MUST is V.KR_SPLIT_MUST and F.KR_SPLIT_NOFILE_RUN_FAIL == V.KR_SPLIT_NOFILE_RUN_FAIL == 16
    assert V.KR_SPLIT_MUST[:3] == ("005930", "035420", "035720")
    assert V.KR_SPLIT_RC_AUCTION == F.KR_SPLIT_AUCTION_BAND and V.KR_SPLIT_RC_PX_TOL == F.KR_SPLIT_PX_TOL
    assert V.KR_SPLIT_RC_SHR_TOL == F.KR_SPLIT_SHR_TOL and V.KR_SPLIT_RC_EXACT_TOL == F.KR_SPLIT_EXACT_TOL
    approved = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    assert f'spNo: "{JACK_LINE}"' in approved


def test_one_run_of_all_no_answers_trips_the_run_limit_and_a_normal_run_does_not(monkeypatch):
    """한 실행의 DART 한도 안에서 모든 조회가 '결정 없음' 이면 (읽기가 깨진 날) 그 실행에 새로 생긴 줄이 한도를 넘어 관문이 막아요 (모의 채우기의 첫
    실행 26 과 같은 모양) · 확인되는 실행은 0."""
    K.Log(monkeypatch)
    seed = [seed_split(f"0{i:04d}0", f"2025-0{1 + i % 9}-1{i % 9}") for i in range(40)]
    kr = K.kr_rows(*[x["t"] for x in seed])
    cmap = {x["t"]: f"C{x['t']}" for x in seed}
    _rows, info = F.kr_splits_fields(None, kr, [], nodoc_dart(), TODAY, seed=seed, cmap=cmap)
    assert info["calls"] <= F.KR_SPLIT_DART_PER_RUN and info["nofileN"] >= V.KR_SPLIT_NOFILE_RUN_FAIL
    assert len(info["runNew"]) == info["nofileN"]                                                # 모두 이 실행이 새로 판정했어요
    c = K.FakeDart()
    for x in seed:
        c.entries[f"C{x['t']}|krsplit|v2|{x['d']}"] = K.ok_verdict(5.0, "20260101000001", "split", x["d"])
    _rows, info2 = F.kr_splits_fields(None, kr, [], c, TODAY, seed=seed, cmap=cmap)
    assert info2["nofileN"] == 0 and len(info2["new"]) == 40 and info2["runNew"] == []


# ── 4. 한 번 실은 줄은 빼지 않아요 · 미국 줄은 그대로 ───────────────────────────────────────────────────────

def test_a_published_row_is_never_dropped_even_when_it_would_not_pass_todays_checks(monkeypatch):
    K.Log(monkeypatch)
    prev = {"splits": [["AAPL", "2020-08-31", 4.0], ["000010", "2026-11-02", 5.0]],
            "splitsKr": {"rows": [["000010", "2026-11-02", 5.0, "split", "20261001000001", "doc"]]}}        # 세 확인 칸이 없는 예전 영수증
    for client in (None, nodoc_dart(), K.kakao_dart(fail=True)):
        rows, info = F.kr_splits_fields(prev, K.kr_rows("000010"), [], client, TODAY, seed=[{**seed_split("000010", "2026-11-02"), "base": 1.0}],
                                        cmap={"000010": "C1"})
        assert rows == [["000010", "2026-11-02", 5.0]] and info["nofile"] == []
    # 관문의 예전 줄 '주식 분할 목록 변화' 가 사라진 한국 줄을 막아요 (그대로)
    rep = T196.check(*K.gate_pair(new_kr=(), prev_kr=(("005930", "2018-05-04", 50.0),)))
    assert any("사라짐" in r[1] for r in rep.failed), rep.table()


def test_us_rows_and_us_stocks_are_untouched(monkeypatch):
    K.Log(monkeypatch)
    sp = {"splits": [["AAPL", "2020-08-31", 4.0], ["NVDA", "2024-06-10", 10.0]], "splitsFrom": V.SPLITS_FROM, "splitsAsOf": "2026-11-20",
          "splitsSrc": "yahoo", "splitsInfo": {"gap": []}}
    before = copy.deepcopy(sp)
    out = F.kr_splits_step(sp, None, K.kr_rows("000010"), nodoc_dart(), TODAY, [seed_split("000010", "2026-11-02")])
    assert [x for x in out["splits"] if not F.kr_split_code(x[0])] == before["splits"]
    assert {k: out[k] for k in before} == {**before, "splits": out["splits"]} and sp == before
    us = {"t": "AAPL", "cls": "us", "vol": 30.0, "hi": 200.0}
    F.mark_split_nofile([us], [["AAPL", "2026-11-02", 5.0, "nodoc"]], {"AAPL": {"y": "2025-01-01", "s": "2023-01-01"}})
    assert us == {"t": "AAPL", "cls": "us", "vol": 30.0, "hi": 200.0}
