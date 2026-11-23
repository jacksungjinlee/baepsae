# -*- coding: utf-8 -*-
"""한국 주식 분할 · 병합 → data.json splits (2026-11-23 · Jack, Track 1 "Korean stock splits" · 새 시험 파일).

파이프라인 (fetch_data.py '한국 주식 분할'): 시세(KRX 기준가 · 상장주식수)와 DART 결정 공시(주식분할결정 · 주식병합결정 원문의 1주당 가액과
신주권상장예정일 · 주식병합으로 하는 감자결정)가 같은 배율 · 같은 상장일을 말한 사건만 실어요. 날짜는 새 주식 수로 거래가 시작된 날 (결의일 ·
효력발생일 아님). 한 출처만 말하면 싣지 않고 까닭을 남겨요. DART 가 실패해도 지난 발행본의 한국 줄은 그대로. 미국 줄은 그대로.
관문 (validate_data.check_kr_splits): 경고만 · 기존 '주식 분할 목록' 두 줄은 한국 줄을 그대로 받아요 (느슨해진 곳 없음).
2.0 (src/v2 그대로): 분할 전 기록은 수량 × r · 가격 ÷ r · 원화 금액 그대로, 기록 시트의 Appendix 1 줄.

픽스처 tests/fixtures/kr_splits: 2026-11-23 에 받은 진짜 DART 응답 (공시 원문 4 · 공시 목록 5 · 감자결정 1 — 키는 들어 있지 않아요) 과 다음(Daum)
일별 시세의 사건 날 앞뒤 줄.
"""
import collections
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_v196a_fxhist_splits as T196  # noqa: E402  (분할 관문 시험의 데이터 · 관문 실행 도우미를 그대로 써요)

FIX = os.path.join(ROOT, "tests", "fixtures", "kr_splits")
TODAY = dt.date(2026, 11, 23)
CORP = {"005930": "00126380", "035720": "00258801", "035420": "00266961", "207940": "00877059", "117670": "00605124",
        "001460": "00000001", "131090": "00402110"}
KRS = "한국 주식 분할 (splitsKr · 경고만)"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def raw(name):
    with open(os.path.join(FIX, name), "rb") as f:
        return f.read()


DAUM = fx("daum_rows.json")


def daum_events(code):
    """픽스처 다음 줄에 파이프라인의 규칙(kr_split_event)을 그대로 — [(날짜, 배율, 길)]."""
    rows = DAUM[code]
    out = []
    for a, b in zip(rows, rows[1:]):
        base = b[4] if b[4] else b[1] - b[2]
        r, how = F.kr_split_event(a[1], base, a[3], b[3])
        if r is not None:
            out.append((b[0], r, how))
    return out


def cand(code):
    """그 종목의 다음 줄 사건 하나를 후보 dict 로 (시드 줄과 같은 모양)."""
    (d, r, how), = daum_events(code)
    return {"t": code, "d": d, "r": r, "how": how, "src": "seed"}


class Log:
    def __init__(self, monkeypatch):
        self.lines = []
        monkeypatch.setattr(F, "log", lambda *a: self.lines.append(" ".join(str(x) for x in a)))

    def has(self, *words):
        return any(all(w in ln for w in words) for ln in self.lines)


class FakeDart:
    """DartClient 처럼 (get · get_zip · status · entries · lock · mode · started_empty · no_call · fatal · down · meta) — 픽스처를 돌려줘요.
    lists {(기업코드, 공시 종류): 응답} · docs {접수번호: 원문 bytes} · gone 원문이 없는 접수번호 (DART 014) · cr {기업코드: crDecsn 응답}."""

    def __init__(self, lists=None, docs=None, gone=(), cr=None, fail=False, boom=False, mode="cache", empty=False, no_call=None):
        self.lists, self.docs, self.gone, self.cr = dict(lists or {}), dict(docs or {}), set(gone), dict(cr or {})
        self.fail, self.boom = fail, boom
        self.status, self.entries, self.lock = collections.Counter(), {}, threading.Lock()
        self.mode, self.started_empty, self.no_call, self.fatal, self.down = mode, empty, no_call, None, None
        self.meta = {"corpMap": dict(CORP)}
        self.calls = []

    def get(self, ep, params):
        self.calls.append((ep, dict(params)))
        if self.boom:
            raise RuntimeError("뜻밖의 오류")
        if self.fail:
            self.status["예외"] += 1
            return None
        if ep == "list.json":
            j = self.lists.get((params["corp_code"], params["pblntf_detail_ty"]))
        elif ep == "crDecsn.json":
            j = self.cr.get(params["corp_code"])
        else:
            j = None
        if j is None:
            self.status["013"] += 1
            return {"status": "013", "message": "조회된 데이타가 없습니다."}
        self.status[str(j.get("status"))] += 1
        return j

    def get_zip(self, ep, params):
        rc = params["rcept_no"]
        self.calls.append((ep, dict(params)))
        if self.fail:
            self.status["예외"] += 1
            return None
        if rc in self.gone:
            self.status["014"] += 1
            return None
        if rc in self.docs:
            self.status["000"] += 1
            return {f"{rc}.xml": self.docs[rc]}
        self.status["예외"] += 1
        return None


def kakao_dart(**kw):
    return FakeDart(lists={("00258801", "I001"): fx("list_00258801_I001.json")}, docs={"20210225800978": raw("doc_20210225800978.xml")}, **kw)


def kr_rows(*codes, cap=1.0):
    return [{"t": t, "nk": t, "cls": "kr", "cap": cap} for t in codes]


def doc_text(rc):
    return F.dvwhy_doc_text({f"{rc}.xml": raw(f"doc_{rc}.xml")}, rc)


# ── 1. 진짜 사건 하나: 카카오 2021-04-15 5:1 액면분할 (다음 시세 × DART 원문) ──────────────────────────────────────

def test_a_real_split_end_to_end_kakao(monkeypatch):
    log = Log(monkeypatch)
    assert daum_events("035720") == [("2021-04-15", 5.0, "px")]          # 558,000원 → 기준가 112,000원 · 상장주식수 88,761,861 → 443,809,305
    c = kakao_dart()
    rows, info = F.kr_splits_fields(None, kr_rows("035720"), [], c, TODAY, seed=[cand("035720")])
    assert rows == [["035720", "2021-04-15", 5.0]] and info["new"] == rows
    assert info["rows"] == [["035720", "2021-04-15", 5.0, "split", "20210225800978", "doc"]]          # 영수증: 접수번호 · 원문
    assert info["src"] == "dart" and info["calls"] == 2 and info["out"] == [] and info["fail"] == [] and info["wait"] == 0
    assert [ep for ep, _ in c.calls] == ["list.json", "document.xml"]                                  # 목록 1 + 원문 1
    assert c.calls[0][1]["pblntf_detail_ty"] == "I001" and c.calls[0][1]["last_reprt_at"] == "Y"
    assert c.calls[0][1]["bgn_de"] == "20200927" and c.calls[0][1]["end_de"] == "20210515"           # 200일 앞 ~ 30일 뒤
    assert c.entries["00258801|krsplit|v1|2021-04-15"]["d"]["v"] == "ok"                              # 판정은 보관본에
    assert log.has("한국 주식 분할: 1건 (새로 1 · 지난 발행본 0)", "035720", "5:1 분할", "DART 새 호출 2회 (한도 50)")
    # 다음 실행: 지난 발행본에 실렸으니 다시 묻지 않고 그대로 이어요
    prev = {"splits": rows, "splitsKr": info}
    rows2, info2 = F.kr_splits_fields(prev, kr_rows("035720"), [], c, TODAY, seed=[cand("035720")])
    assert rows2 == rows and info2["new"] == [] and info2["prev"] == 1 and info2["rows"] == info["rows"] and len(c.calls) == 2
    # 같은 사건이 며칠 다른 날짜로 다시 와도 (같은 배율 · 10일 안) 새 줄이 아니에요
    rows3, _ = F.kr_splits_fields(prev, kr_rows("035720"), [{**cand("035720"), "d": "2021-04-19"}], c, TODAY, seed=[])
    assert rows3 == rows and len(c.calls) == 2


def test_the_committed_seed_is_the_pipelines_own_rule_on_real_daum_rows():
    seed = F.load_kr_split_seed()
    key = {(x["t"], x["d"]): x for x in seed}
    assert len(key) == len(seed) > 500 and all(F.kr_split_code(x["t"]) and x["d"] >= V.SPLITS_FROM for x in seed)
    assert all(x["d"] <= "2026-11-20" for x in seed)                                                  # 2026-11-21 발행본의 기준일까지
    for t, d, r, how in (("005930", "2018-05-04", 50.0, "px"), ("035720", "2021-04-15", 5.0, "px"), ("035420", "2018-10-12", 5.0, "px"),
                         ("001460", "2024-04-17", 10.0, "px"), ("131090", "2025-05-20", 0.2, "px"), ("117670", "2025-07-09", 0.1, "shr"),
                         ("000670", "2025-04-25", 10.0, "px")):
        assert key[(t, d)]["r"] == r and key[(t, d)]["how"] == how, (t, d)
        assert daum_events(t) == [(d, r, how)]                                                        # 픽스처의 진짜 줄과 같은 규칙 · 같은 답
    assert all(V.simple_ratio(x["r"]) and V.SPLIT_R[0] <= x["r"] <= V.SPLIT_R[1] and x["r"] != 1 for x in seed)   # 관문이 받는 배율만
    with open(F.KR_SPLIT_SEED_PATH, encoding="utf-8") as f:
        assert f.read().count("\n" + F.KR_SPLIT_SEED_HEAD + "\n") == 1


@pytest.mark.parametrize("line", ["005930,2018-05-04,50/1,2650000,53000,128386494,6419324700,x",     # 칸이 많음
                                  "005930,2018-05-04,10/1,2650000,53000,128386494,6419324700",       # 시세와 다른 배율
                                  "005930,2015-12-30,50/1,2650000,53000,128386494,6419324700",       # 2016 앞
                                  "AAPL,2020-08-31,4/1,500,125,100,400",                             # 미국 티커
                                  "005930,2018-05-04,50/1,2650000,2650000,128386494,128386494"])     # 사건이 아님
def test_seed_loader_refuses_a_bad_line(tmp_path, line):
    p = tmp_path / "s.csv"
    p.write_text("# x\n" + F.KR_SPLIT_SEED_HEAD + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        F.load_kr_split_seed(str(p))


# ── 2. 날짜: 새 주식 수로 거래가 시작된 날 (신주권상장예정일) — 결의일 · 효력발생일이 아니에요 ─────────────────────────────

def test_the_date_is_the_first_day_on_the_new_count_not_the_board_or_legal_date():
    byc = F.parse_kr_split_doc(doc_text("20240304800699"), "split", "20240304800699")[0]
    assert (byc["r"], byc["de"], byc["dl"]) == (10.0, "2024-04-12", "2024-04-17")                  # 결의 03-04 · 효력 04-12 · 상장 04-17
    assert daum_events("001460") == [("2024-04-17", 10.0, "px")]                                    # 04-12 ~ 16 은 거래정지 (489,500원 그대로)
    merge = F.parse_kr_split_doc(doc_text("20250310901128"), "merge", "20250310901128")[0]
    assert (merge["r"], merge["de"], merge["dl"]) == (0.2, "2025-04-29", "2025-05-20")              # 병합: 효력과 상장이 3주 떨어져요
    assert daum_events("131090") == [("2025-05-20", 0.2, "px")]
    naver = F.parse_kr_split_doc(doc_text("20180726800004"), "split", "20180726800004")[0]
    assert (naver["r"], naver["de"], naver["dl"]) == (5.0, None, "2018-10-12")                      # 2018 양식: 효력발생일 칸이 없어도 돼요
    assert daum_events("035420") == [("2018-10-12", 5.0, "px")]
    # 카카오: 효력 04-14 · 상장 04-15. 효력발생일로 온 후보는 맞지 않아요 (실으면 04-14 에 산 기록이 5배가 돼요)
    v, _ = F.kr_split_dart(kakao_dart(), "00258801", "2021-04-14", 5.0, TODAY)
    assert v["v"] == "no" and "상장 2021-04-15" in v["why"]
    v, _ = F.kr_split_dart(kakao_dart(), "00258801", "2021-04-15", 5.0, TODAY)
    assert v["v"] == "ok" and v["dl"] == "2021-04-15" and v["de"] == "2021-04-14" and v["rc"] == "20210225800978"
    v, _ = F.kr_split_dart(kakao_dart(), "00258801", "2021-04-15", 2.0, TODAY)                     # 배율이 달라도 아니에요
    assert v["v"] == "no" and "액면분할 ×5" in v["why"]


def test_capital_reduction_by_merger_is_checked_with_crdecsn_and_its_listing_date():
    # 알파칩스 2025-07-09 10:1 감자: 다시 상장하는 날 기준가는 동시호가 (앞날 790원 · 기준가 9,580원) → 주식 수만으로 후보 ('shr')
    assert daum_events("117670") == [("2025-07-09", 0.1, "shr")]
    c = FakeDart(lists={("00605124", "B001"): fx("list_00605124_B001.json")}, cr={"00605124": fx("crDecsn_00605124.json")})
    rows, info = F.kr_splits_fields(None, kr_rows("117670"), [], c, TODAY, seed=[cand("117670")])
    assert rows == [["117670", "2025-07-09", 0.1]] and info["rows"] == [["117670", "2025-07-09", 0.1, "reduce", "20250415000092", "cr"]]
    assert [p.get("pblntf_detail_ty", ep) for ep, p in c.calls] == ["I001", "B001", "crDecsn.json"]
    got, bad = F.parse_kr_split_cr(fx("crDecsn_00605124.json")["list"])
    assert got == [{"k": "reduce", "r": 0.1, "de": "2025-06-17", "dl": "2025-07-09", "rc": "20250415000092", "src": "cr"}] and bad == []
    # 소각(병합이 아님)은 사건이 아니에요
    assert F.parse_kr_split_cr([dict(fx("crDecsn_00605124.json")["list"][0], cr_mth="유상소각")]) == ([], [])


# ── 3. 한 출처만: 싣지 않고 까닭을 남겨요 ─────────────────────────────────────────────────────────────────

def test_a_market_only_event_is_left_out_with_its_reason(monkeypatch):
    # 삼성바이오로직스 2025-11-24 인적분할: 기준가 × 2/3 · 주식 수 −35% — 분할 · 병합 · 감자 결정 공시가 없어요
    log = Log(monkeypatch)
    assert daum_events("207940") == [("2025-11-24", 2 / 3, "px")]
    c = FakeDart(lists={("00877059", "I001"): fx("list_00877059_I001.json")})
    rows, info = F.kr_splits_fields(None, kr_rows("207940", cap=60.0), [], c, dt.date(2025, 12, 1), seed=[cand("207940")])
    assert rows == [] and info["new"] == [] and info["out"] == [["207940", "2025-11-24", "분할 · 병합 · 감자(주식병합) 결정 공시 없음"]]
    assert log.has("!! 한국 주식 분할 — 한 출처만 말해서 싣지 않은 사건 1", "207940")
    assert c.entries["00877059|krsplit|v1|2025-11-24"]["d"]["v"] == "no"                              # 판정을 남겨 매번 묻지 않아요


def test_when_the_two_sources_disagree_on_the_ratio_the_event_is_left_out(monkeypatch):
    # 동국홀딩스 2026-05 5:1 액면분할 (DART dvWhy 사건 · 접수 20260211801330): 다시 상장한 날 기준가가 앞날 ÷ 5 가 아니에요 (11,400원 →
    # 기준가 2,545원 = ÷ 4.48 · 주식 수 ×4.89) — 시세는 ×4.5 라고 말해서 DART 의 ×5 와 달라요 → 싣지 않고 까닭을 남겨요
    assert daum_events("001230") == [("2026-05-29", 4.5, "px")]
    Log(monkeypatch)
    c = kakao_dart()                                                     # 같은 길: 시세 ×2 · 공시 ×5 (카카오 원문)
    rows, info = F.kr_splits_fields(None, kr_rows("035720"), [], c, TODAY, seed=[{**cand("035720"), "r": 2.0}])
    assert rows == [] and info["out"] == [["035720", "2021-04-15", "공시와 다름: 액면분할 ×5 (상장 2021-04-15 · 20210225800978)"]]
    # 티비씨 2026-07-03 5:1 병합은 주식 수가 ×0.189 (단주 · 소각) 여도 기준가가 정확히 ×5 라 후보예요 (± 10%)
    assert daum_events("033830") == [("2026-07-03", 0.2, "px")]


def test_a_decision_whose_document_dart_does_not_serve_is_confirmed_from_the_list_and_the_market_only_for_px():
    # 삼성전자 2018 50:1: 마지막 정정본 원문을 DART 가 주지 않아요 (014) — 목록의 결정 하나 + 시세(기준가 · 주식 수)로 확인 (src list)
    lists = {("00126380", "I001"): fx("list_00126380_I001.json")}
    c = FakeDart(lists=lists, gone={"20180316800856"})
    rows, info = F.kr_splits_fields(None, kr_rows("005930", cap=500.0), [], c, TODAY, seed=[cand("005930")])
    assert rows == [["005930", "2018-05-04", 50.0]] and info["rows"] == [["005930", "2018-05-04", 50.0, "split", "20180316800856", "list"]]
    assert info["calls"] == 2
    # 주식 수만 말한 후보('shr')는 목록만으로 싣지 않아요 · 다른 방향(병합 후보)도 아니에요
    v, _ = F.kr_split_dart(FakeDart(lists=lists, gone={"20180316800856"}), "00126380", "2018-05-04", 50.0, TODAY, how="shr")
    assert v["v"] == "no" and "DART 014" in v["why"]
    v, _ = F.kr_split_dart(FakeDart(lists=lists, gone={"20180316800856"}), "00126380", "2018-05-04", 0.02, TODAY)
    assert v["v"] == "no"


# ── 4. DART 가 실패해도 지난 발행본의 한국 줄은 그대로 ─────────────────────────────────────────────────────────

PREV = {"splits": [["AAPL", "2020-08-31", 4.0], ["005930", "2018-05-04", 50.0], ["131090", "2025-05-20", 0.2]],
        "splitsKr": {"rows": [["005930", "2018-05-04", 50.0, "split", "20180316800856", "list"],
                              ["131090", "2025-05-20", 0.2, "merge", "20250310901128", "doc"]]}}


def test_a_dart_failure_keeps_last_publishs_korean_rows_and_says_so(monkeypatch):
    log = Log(monkeypatch)
    c = kakao_dart(fail=True)
    rows, info = F.kr_splits_fields(PREV, kr_rows("005930", "131090", "035720"), [], c, TODAY, seed=[cand("035720")])
    assert rows == [["005930", "2018-05-04", 50.0], ["131090", "2025-05-20", 0.2]] and info["new"] == []
    assert info["fail"] == [["035720", "2021-04-15", "공시 목록(I001) 조회 실패"]] and info["rows"] == sorted(PREV["splitsKr"]["rows"])
    assert "00258801|krsplit|v1|2021-04-15" not in c.entries                                           # 실패는 남기지 않아요 (다음 실행에 다시)
    assert log.has("!! 한국 주식 분할 — 조회 실패 1", "035720")
    # 공시 하나를 읽다 난 오류: 그 후보만 '맞지 않음' (매 실행 다시 멈추지 않게) · 지난 줄 그대로
    rows, info = F.kr_splits_fields(PREV, kr_rows("005930", "131090", "035720"), [], kakao_dart(boom=True), TODAY, seed=[cand("035720")])
    assert rows == [["005930", "2018-05-04", 50.0], ["131090", "2025-05-20", 0.2]] and info["src"] == "dart"
    assert info["out"] == [["035720", "2021-04-15", "공시를 읽다 오류로 멈춤 (RuntimeError: 뜻밖의 오류)"]]
    # 단계 전체의 뜻밖의 오류: 멈추지 않고 지난 줄 그대로 (src err)
    monkeypatch.setattr(F, "_kr_splits_fields", lambda *a: 1 / 0)
    rows, info = F.kr_splits_fields(PREV, kr_rows("005930", "131090", "035720"), [], kakao_dart(), TODAY, seed=[cand("035720")])
    assert rows == [["005930", "2018-05-04", 50.0], ["131090", "2025-05-20", 0.2]] and info["src"] == "err" and "ZeroDivisionError" in info["err"]
    assert info["rows"] == sorted(PREV["splitsKr"]["rows"]) and info["n"] == 2
    assert log.has("!! 한국 주식 분할: 확인하다 오류로 멈췄어요", "지난 발행본의 한국 줄 2건을 그대로")
    monkeypatch.undo()
    Log(monkeypatch)
    # 지난 줄의 종목이 오늘 목록에 없어도 이어요 (그 종목을 가진 사람이 있어요)
    rows, _ = F.kr_splits_fields(PREV, [], [], None, TODAY, seed=[])
    assert rows == [["005930", "2018-05-04", 50.0], ["131090", "2025-05-20", 0.2]]


@pytest.mark.parametrize("client, src", [(None, "off"), ("full", "cache"), ("empty", "cache"), ("same", "cache")])
def test_no_new_dart_calls_when_dart_is_off_full_empty_or_a_same_day_rerun(monkeypatch, client, src):
    Log(monkeypatch)
    c = None if client is None else kakao_dart(mode="full" if client == "full" else "cache", empty=client == "empty",
                                                no_call="같은 날 다시" if client == "same" else None)
    rows, info = F.kr_splits_fields(PREV, kr_rows("005930", "035720"), [], c, TODAY, seed=[cand("035720")])
    assert rows == PREV["splits"][1:] and info["src"] == src and info["wait"] == 1 and info["calls"] == 0
    assert c is None or c.calls == []
    if c is not None:                                                     # 보관본의 판정은 써요 (호출 없이)
        c.entries["00258801|krsplit|v1|2021-04-15"] = {"st": "000", "at": "2026-11-01", "d": {"v": "ok", "k": "split", "r": 5.0,
                                                                                            "rc": "20210225800978", "dl": "2021-04-15", "src": "doc"}}
        rows, info = F.kr_splits_fields(PREV, kr_rows("005930", "035720"), [], c, TODAY, seed=[cand("035720")])
        assert ["035720", "2021-04-15", 5.0] in rows and info["new"] == [["035720", "2021-04-15", 5.0]] and c.calls == []


def test_the_per_run_cap_biggest_stocks_first_and_retrying_a_no(monkeypatch):
    Log(monkeypatch)
    lists = {("00258801", "I001"): fx("list_00258801_I001.json"), ("00266961", "I001"): fx("list_00266961_I001.json")}
    docs = {"20210225800978": raw("doc_20210225800978.xml"), "20180726800004": raw("doc_20180726800004.xml")}
    kr = [{"t": "035720", "cls": "kr", "cap": 20.0}, {"t": "035420", "cls": "kr", "cap": 30.0}]
    c = FakeDart(lists=lists, docs=docs)
    rows, info = F.kr_splits_fields(None, kr, [], c, TODAY, seed=[cand("035720"), cand("035420")], per_run=F.KR_SPLIT_ONE_MAX)
    assert rows == [["035420", "2018-10-12", 5.0]] and info["wait"] == 1 and info["waitT"] == [["035720", "2021-04-15"]]   # 큰 종목(NAVER) 먼저
    assert info["calls"] <= F.KR_SPLIT_ONE_MAX
    rows, info = F.kr_splits_fields({"splits": rows, "splitsKr": info}, kr, [], c, TODAY, seed=[cand("035720"), cand("035420")])
    assert rows == [["035420", "2018-10-12", 5.0], ["035720", "2021-04-15", 5.0]] and info["wait"] == 0
    # 맞지 않은 판정(no)은 사건이 120일 안이면 14일 뒤에 한 번 더 물어요 (늦은 정정 공시) · 그 전 · 오래된 사건은 다시 묻지 않아요
    c2 = FakeDart()
    key = "00258801|krsplit|v1|2026-11-02"
    c2.entries[key] = {"st": "000", "at": "2026-11-05", "d": {"v": "no", "why": "결정 공시 없음"}}
    new = [{"t": "035720", "d": "2026-11-02", "r": 5.0, "how": "px", "src": "krx"}]
    F.kr_splits_fields(None, kr, new, c2, dt.date(2026, 11, 18), seed=[])
    assert c2.calls == []                                                           # 13일: 아직
    F.kr_splits_fields(None, kr, new, c2, dt.date(2026, 11, 19), seed=[])
    assert [ep for ep, _ in c2.calls][:1] == ["list.json"]                          # 14일: 다시
    c3 = FakeDart()
    c3.entries["00258801|krsplit|v1|2021-04-15"] = {"st": "000", "at": "2021-05-01", "d": {"v": "no", "why": "결정 공시 없음"}}
    _rows, info = F.kr_splits_fields(None, kr, [], c3, TODAY, seed=[cand("035720")])
    assert c3.calls == [] and info["out"] == [["035720", "2021-04-15", "결정 공시 없음"]]           # 오래된 사건: 다시 묻지 않아요


# ── 5. 미국 줄은 그대로 ───────────────────────────────────────────────────────────────────────────────

def test_us_rows_are_bit_identical(monkeypatch):
    Log(monkeypatch)
    us = ["NVDA", "AAPL", "TSLA", "WMT"]
    base = [["AAPL", "2020-08-31", 4.0], ["NVDA", "2024-06-10", 10.0], ["TSLA", "2022-08-25", 3.0], ["WMT", "2024-02-26", 3.0]]
    seed = ({}, set(), None)
    with_kr = T196.prev_data(base + [["005930", "2018-05-04", 50.0]], us=us)
    plain = T196.prev_data(base, us=us)
    a = F.splits_fields(plain, us, [], [], T196.START, T196.TODAY, seed=seed)
    b = F.splits_fields(with_kr, us, [], [], T196.START, T196.TODAY, seed=seed)
    us_b = [x for x in b["splits"] if not F.kr_split_code(x[0])]
    assert us_b == a["splits"] and {k: v for k, v in b.items() if k != "splits"} == {k: v for k, v in a.items() if k != "splits"}
    with_kr["splitsKr"] = {"rows": [["005930", "2018-05-04", 50.0, "split", "20180316800856", "list"]]}
    out = F.kr_splits_step(b, with_kr, kr_rows("005930"), kakao_dart(), T196.TODAY, [])
    assert [x for x in out["splits"] if not F.kr_split_code(x[0])] == a["splits"]                       # 같은 줄 · 같은 차례 · 같은 값
    assert json.dumps([x for x in out["splits"] if not F.kr_split_code(x[0])]) == json.dumps(a["splits"])
    assert {k: v for k, v in out.items() if k not in ("splits", "splitsKr")} == {k: v for k, v in a.items() if k != "splits"}
    assert [x for x in out["splits"] if F.kr_split_code(x[0])] == [["005930", "2018-05-04", 50.0]]
    assert F.kr_splits_step({}, with_kr, [], None, T196.TODAY, []) == {}                                # splits 칸이 없는 날은 그대로
    # 미국 티커는 한국 코드 꼴이 아니에요 (한국 상장 펀드 379800 은 한국 코드)
    assert not any(F.kr_split_code(t) for t in ("AAPL", "BRK-B", "BF-B", "U0001", "QQQ")) and F.kr_split_code("0001A0")


def test_main_wiring():
    import inspect
    main = inspect.getsource(F.main)
    i_late, i_kr, i_c1w = main.index("us_own_split_late(us, umeta, sp_fields, prev)"), main.index("sp_fields = kr_splits_step(sp_fields, prev, kr, client, today, "), \
        main.index("c1w_meta = c1w_step(stocks, ")
    assert i_late < i_kr < i_c1w < main.index("payload.update(sp_fields)") < main.index("write_json(OUT, payload)")
    assert main.index("client.save()", i_kr) > i_kr                               # 새 판정은 공시 단계 뒤 저장에 실려요
    kr = inspect.getsource(F.fetch_korea)
    assert "kr_split_cand = kr_split_cands([(px_date, listing)] + sessions, ref_events)" in kr and 'meta["_krSplitCand"] = kr_split_cand' in kr
    assert "splitsKr" in F.UNITS and not [p for p, v in V.text_values({"splitsKr": F.UNITS["splitsKr"]}) if V.BAD_WORD.search(v)]


def test_listing_file_candidates_from_kr_ref_links_breaks():
    """매일의 후보: 최근 거래일 목록 파일의 기준가 재설정(kr_ref_links) + 상장주식수 (BYC 2024-04-17 을 목록 파일 꼴로)."""
    def df(close, marcap, changes, stocks):
        return pd.DataFrame({"Code": ["001460", "000010"], "Close": [close, 1000.0], "Changes": [changes, 0.0], "Marcap": [marcap, 1000.0 * 10],
                             "Stocks": [stocks, 10]})
    files = [(dt.date(2024, 4, 17), df(42400.0, 42400.0 * 6246150, -6550.0, 6246150)),
             (dt.date(2024, 4, 16), df(489500.0, 489500.0 * 624615, 0.0, 624615))]
    _by, events = F.kr_ref_links(files, [pd.Timestamp(d) for d, _ in files])
    assert [e[0] for e in events] == ["001460"] and pd.Timestamp(events[0][1]).date() == dt.date(2024, 4, 17)
    got = F.kr_split_cands(files, events)
    assert [(x["t"], x["d"], x["r"], x["how"], x["src"]) for x in got] == [("001460", "2024-04-17", 10.0, "px", "krx")]
    # 기준가만 바뀐 날 (권리락: 주식 수 그대로) 은 후보가 아니에요
    files2 = [(dt.date(2024, 4, 17), df(24000.0, 24000.0 * 624615, -500.0, 624615)), files[1]]
    _by, ev2 = F.kr_ref_links(files2, [pd.Timestamp(d) for d, _ in files2])
    assert ev2 and F.kr_split_cands(files2, ev2) == []


@pytest.mark.parametrize("args, want", [
    ((2650000, 53000, 128386494, 6419324700), (50.0, "px")),
    ((489500, 48950, 624615, 6246150), (10.0, "px")),
    ((414000, 401000, 1842040, 1842040), (None, None)),          # 영풍 2024-12-27 배당락: 주식 수 그대로
    ((790, 9580, 61394681, 6139468), (0.1, "shr")),              # 감자: 기준가는 동시호가
    ((1000, 1000, 100, 87), (None, None)),                       # 자기주식 소각 13%: n:1 이 아니에요
    ((1000, 500, 100, 200), (2.0, "px")),
    ((1000, 2000, 100, 100), (None, None)),                      # 무상증자 권리락 (주식은 몇 주 뒤에 상장)
    ((None, 2000, 100, 50), (0.5, "shr")), ((1000, 2000, 0, 50), (None, None)), ((float("nan"), 1, 1, 2), (None, None)),
])
def test_market_event_rule(args, want):
    assert F.kr_split_event(*args) == want


# ── 관문 ────────────────────────────────────────────────────────────────────────────────────────────

def gate_pair(new_kr=(("005930", "2018-05-04", 50.0),), prev_kr=(("005930", "2018-05-04", 50.0),), info=True):
    cur, prev, final = T196.pair()
    cur["data"]["splits"] = sorted(cur["data"]["splits"] + [list(x) for x in new_kr])
    prev["data"]["splits"] = sorted(prev["data"]["splits"] + [list(x) for x in prev_kr])
    if info:
        cur["data"]["splitsKr"] = {"v": 1, "src": "dart", "n": len(new_kr), "prev": len(prev_kr), "new": [], "wait": 0, "waitT": [], "out": [],
                                   "fail": [], "calls": 0, "cap": 50,
                                   "rows": [[t, d, r, "split", "20180316800856", "list"] for t, d, r in new_kr]}
    return cur, prev, final


def test_gate_existing_split_rows_take_korean_codes_without_loosening():
    cur, prev, final = gate_pair()
    rep = T196.check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert T196.row(rep, T196.SPL)[3] == "PASS" and T196.row(rep, T196.SPC)[3] == "PASS"
    assert T196.row(rep, KRS)[3] == "PASS" and T196.row(rep, KRS)[1].startswith("1건 (새로 0 · 지난 발행본 1)")
    # 그대로 엄격해요: 오늘 목록에 없는 한국 종목의 새 줄 · 사라진 한국 줄 · 바뀐 배율 · 깨끗하지 않은 배율은 실패
    for new_kr, prev_kr, said in (((("005930", "2018-05-04", 50.0), ("999990", "2020-01-02", 5.0)), (("005930", "2018-05-04", 50.0),), "오늘 목록에 없음"),
                                  ((), (("005930", "2018-05-04", 50.0),), "사라짐"),
                                  ((("005930", "2018-05-04", 5.0),), (("005930", "2018-05-04", 50.0),), "배율 바뀜"),
                                  ((("005930", "2018-05-04", 1.253),), (), "깨끗한 분수가 아니에요")):
        rep = T196.check(*gate_pair(new_kr, prev_kr))
        assert any(said in r[1] for r in rep.failed), (said, rep.table())


@pytest.mark.parametrize("hurt, said", [
    (lambda i: i.pop("rows"), "영수증 없는 한국 줄 1: 005930 2018-05-04"),
    (lambda i: i.update(new=[["005930", "2018-05-04", 50.0]]), "오늘 새 한국 줄 1: 005930 2018-05-04 ×50"),
    (lambda i: i.update(out=[["207940", "2026-11-10", "결정 공시 없음"]]), "최근 30일 싣지 않은 사건 1: 207940 2026-11-10"),
    (lambda i: i.update(fail=[["035720", "2021-04-15", "공시 목록(I001) 조회 실패"]]), "조회 실패 1"),
    (lambda i: i.update(wait=120), "아직 묻지 못한 후보 120"),
    (lambda i: i.update(src="err", err="KeyError: x"), "!! 확인하다 오류로 멈춰"),
    (lambda i: i.update(src="off"), "DART 꺼짐"),
    (lambda i: i.update(n=3), "splitsKr.n 3 ≠ 한국 줄 1"),
])
def test_gate_korean_row_warns_only(hurt, said):
    cur, prev, final = gate_pair()
    hurt(cur["data"]["splitsKr"])
    rep = T196.check(cur, prev, final)
    r = T196.row(rep, KRS)
    assert r[3] == "WARN" and said in r[1], r
    assert not rep.failed, rep.table()


def test_gate_korean_row_old_left_out_events_do_not_warn_and_odd_values_never_fail():
    cur, prev, final = gate_pair()
    cur["data"]["splitsKr"]["out"] = [["207940", "2025-11-24", "결정 공시 없음"]]                      # 30일 넘게 지난 사건: 목록에만
    rep = T196.check(cur, prev, final)
    assert T196.row(rep, KRS)[3] == "PASS" and ("한국 주식 분할 (splitsKr) 확인할 것", ["싣지 않음 207940 2025-11-24 (결정 공시 없음)"]) in rep.details
    for odd in (None, [], "x", {"rows": "x", "new": 5, "out": [1, None], "wait": "many", "src": None}, {"rows": [[1, 2]], "n": float("nan")}):
        cur, prev, final = gate_pair()
        cur["data"]["splitsKr"] = odd
        rep = T196.check(cur, prev, final)
        assert T196.row(rep, KRS)[3] == "WARN" and not rep.failed, (odd, T196.row(rep, KRS))
    rep = V.Report()
    V.check_kr_splits(rep, {"splits": "x"}, TODAY)
    assert rep.rows[0][3] == "SKIP"
    rep = V.Report()
    V.check_kr_splits(rep, None, TODAY)                                                                # 무엇이 와도 실패하지 않아요
    assert not rep.failed


# ── 6. 2.0: 분할 전에 산 한국 종목 — 들고 있다가 팔아요 (src/v2 그대로 · Node) ──────────────────────────────────────

NODE = shutil.which("node")
_B = {}
MODS = (("L", "lots.js"), ("H", "held.js"), ("S", "store.js"), ("Rc", "records.js"))


def node(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-krsplit-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in MODS:
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/m.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    names = ", ".join(n for n, _ in MODS)
    code = (f"import {{ {names} }} from './m.mjs';\nconsole.warn = () => {{}}; console.info = () => {{}};\nlet out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


DECK = """
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deckOf = (t, nk, purchases, sales = []) => ({ id: 'd', name: 'p', createdAt: '2017-03-02', planFx: 1300,
  holdings: [{ t, nk, cls: 'kr', target: 1, rules: band(1) }], purchases, sales });
const data = { splits: [['AAPL', '2020-08-31', 4], ['005930', '2018-05-04', 50], ['131090', '2025-05-20', 0.2]] };
const view = (d, today) => L.withDataSplits({ v: 2, decks: [d] }, L.dataSplits(data).list, today).decks[0];
const env = { today: '2026-11-23' };
"""


@pytest.mark.skipif(NODE is None or not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")), reason="node · esbuild 가 없어요")
def test_2_0_reads_a_korean_record_bought_before_the_split_held_and_sold():
    got = node(DECK + """
      const buy = { id: 'p1aaaaaa', t: '005930', date: '2018-04-02', qty: 10, price: 2650000, ccy: 'KRW' };
      const d0 = deckOf('005930', '삼성전자', [buy]);
      const v0 = view(d0, '2026-11-23');
      const L0 = L.ledger(v0, '005930');
      const s = { t: '005930', cls: 'kr', price: 55000 };
      const ok = Rc.checkSale(v0, '005930', { qty: '200', price: '55000', date: '2026-11-20' }, s, env);
      const over = Rc.checkSale(v0, '005930', { qty: '501', price: '55000', date: '2026-11-20' }, s, env);
      const d1 = { ...d0, sales: [ok.rec], splits: L.splitsToStore({ ...v0, sales: [ok.rec] }, '005930') };
      const v1 = view(d1, '2026-11-23');
      const L1 = L.ledger(v1, '005930');
      out = { list: L.dataSplits(data).list, held0: H.heldUnits(v0).get('005930'), avg0: L0.avgOwn, putIn: L0.putIn.won,
        line: L.splitsFor(v0, '005930'), ok: ok.ok, rec: { qty: ok.rec.qty, price: ok.rec.price }, over: over.why,
        stored: d1.splits, problem: S.deckProblem(d1, '2026-11-23'), held1: H.heldUnits(v1).get('005930'), gain: L1.sales[0].gain,
        avg1: L1.avgOwn, removed: L1.removedWon, typed: d1.purchases[0], before: H.heldUnits(view(d0, '2018-05-03')).get('005930') };""")
    assert ["005930", "2018-05-04", 50] in [[x["t"], x["date"], x["r"]] for x in [dict(t=y["t"], date=y["date"], r=y["r"]) for y in got["list"]]]
    assert got["held0"] == 500 * 10000 and got["avg0"] == 53000 and got["putIn"] == 26_500_000          # 10주 × 50 · 2,650,000원 ÷ 50 · 원화 금액 그대로
    assert got["line"] == [{"date": "2018-05-04", "r": 50}]                                               # 기록 시트의 'split applied' 줄 (Appendix 1)
    assert got["ok"] is True and got["rec"] == {"qty": 200, "price": 55000} and got["over"] == "tooMany"
    assert got["stored"] == [{"t": "005930", "date": "2018-05-04", "r": 50}] and got["problem"] is None  # 판 기록이 분할을 함께 저장해요
    assert got["held1"] == 300 * 10000 and got["gain"] == 200 * 55000 - 200 * 53000 and got["avg1"] == 53000
    assert got["removed"] == 200 * 53000 and got["typed"]["qty"] == 10 and got["typed"]["price"] == 2650000   # 저장된 기록은 쓴 그대로
    assert got["before"] == 10 * 10000                                                                    # 오늘이 분할 전이면 분할을 적용하지 않아요 (10주)


@pytest.mark.skipif(NODE is None or not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")), reason="node · esbuild 가 없어요")
def test_2_0_a_merge_that_leaves_a_fraction_of_a_korean_share():
    """10:1 같은 병합으로 1주가 안 되는 몫이 남으면 (실제로는 회사가 현금으로 줘요 · 단주 대금), 화면은 그 몫을 그대로 들고 있다고 봐요.
    팔았어요는 한국 종목을 온 주로만 받아서 그 몫은 팔았어요로 지울 수 없어요 (Jack 에게 묻는 질문 · PR 'Choices I made')."""
    got = node(DECK + """
      const d0 = deckOf('131090', '시큐브', [{ id: 'p1aaaaaa', t: '131090', date: '2025-03-04', qty: 7, price: 900, ccy: 'KRW' }]);
      const v0 = view(d0, '2026-11-23');
      const s = { t: '131090', cls: 'kr', price: 5000 };
      out = { held: H.heldQty(v0).get('131090'), avg: L.ledger(v0, '131090').avgOwn, line: L.splitsFor(v0, '131090'),
        one: Rc.checkSale(v0, '131090', { qty: '1', price: '5000', date: '2026-11-20' }, s, env).ok,
        frac: Rc.checkSale(v0, '131090', { qty: '1.4', price: '5000', date: '2026-11-20' }, s, env).why,
        two: Rc.checkSale(v0, '131090', { qty: '2', price: '5000', date: '2026-11-20' }, s, env).why };""")
    assert got["held"] == 1.4 and got["avg"] == pytest.approx(4500) and got["line"] == [{"date": "2025-05-20", "r": 0.2}]   # 7주 ÷ 5 = 1.4주
    assert got["one"] is True and got["frac"] == "input" and got["two"] == "tooMany"


def test_the_override_table_corrects_a_korean_row_like_a_us_row(monkeypatch):
    """고정 표 (SPLIT_OVERRIDES) 의 한국 코드 줄: 배율 None 은 그 줄을 빼고 (관문은 splitsInfo.fixed 를 보고 경고만), 배율은 그 배율로."""
    Log(monkeypatch)
    table = dict(F.SPLIT_OVERRIDES)
    table[("131090", "2025-05-20")] = (None, "시험: 틀린 줄")
    table[("035720", "2021-04-15")] = (5.0, "시험: 손으로 확인한 줄")
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", table)
    rows, info = F.kr_splits_fields(PREV, kr_rows("005930", "035720"), [], None, TODAY, seed=[])
    assert rows == [["005930", "2018-05-04", 50.0], ["035720", "2021-04-15", 5.0]]
    assert ["035720", "2021-04-15", 5.0, "fixed", "SPLIT_OVERRIDES", "fixed"] in info["rows"] and not any(x[0] == "131090" for x in info["rows"])
    sp = F.merge_splits(PREV, None, ["AAPL"], [], {"noCol": []}, dt.date(2023, 11, 1), [], {"noCol": []}, [], TODAY)
    assert ["131090", "2025-05-20", None, "시험: 틀린 줄"] in sp["info"]["fixed"]                     # 관문 · 앱이 읽는 'out' 줄


def daum_json(code):
    """픽스처 다음 줄 → 다음 일별 시세 응답 모양 (최신이 앞)."""
    return {"data": [{"date": r[0] + " 00:00:00", "tradePrice": r[1], "changePrice": r[2], "listedSharesCount": r[3], "prevClosingPrice": r[4]}
                     for r in reversed(DAUM[code])]}


def test_a_gap_day_event_is_found_from_daum_when_the_share_count_moved(monkeypatch):
    """목록 파일 사이에 빠진 날 (2차 출처 날 · 받지 못한 날): 기준가 재설정을 볼 수 없어도, 지난 발행본보다 상장주식수가 10% 넘게 바뀐 종목은
    다음 일별 시세로 사건 날을 찾아요 (실행당 KR_SPLIT_DAUM_MAX 종목 · 지난 발행본의 기준일 뒤 ~ 오늘 기준일)."""
    log = Log(monkeypatch)
    prev = {"pxDate": "2021-04-12", "stocks": [{"t": "035720", "cls": "kr", "shr": 88761861}, {"t": "005930", "cls": "kr", "shr": 100}],
            "splits": [], "splitsKr": {}}
    kr = [{"t": "035720", "nk": "카카오", "cls": "kr", "cap": 20.0, "shr": 443809305}, {"t": "005930", "cls": "kr", "cap": 400.0, "shr": 105}]
    assert F.kr_split_shr_moved(prev, kr) == ["035720"]
    asked = []
    fetch = lambda c, n: (asked.append((c, n)), daum_json(c))[1]                          # noqa: E731
    got, bad = F.kr_split_daum_cands(["035720"], "2021-04-12", "2021-04-16", fetch=fetch)
    assert [(x["t"], x["d"], x["r"], x["how"], x["src"]) for x in got] == [("035720", "2021-04-15", 5.0, "px", "daum")] and bad == []
    assert F.kr_split_daum_cands(["035720"], "2021-04-15", "2021-04-16", fetch=fetch)[0] == []      # 지난 기준일까지는 이미 본 날
    assert F.kr_split_daum_cands(["035720"], "2021-04-12", "2021-04-14", fetch=fetch)[0] == []      # 오늘 기준일 뒤 (장중 줄) 는 빼요
    assert F.kr_split_daum_cands(["035720"], "2021-04-12", "2021-04-16", fetch=lambda c, n: 1 / 0)[1] == ["035720 (ZeroDivisionError: division by zero)"]
    sp = {"splits": [["AAPL", "2020-08-31", 4.0]], "splitsFrom": V.SPLITS_FROM}
    out = F.kr_splits_step(sp, prev, kr, kakao_dart(), TODAY, [], px_date="2021-04-16", daum=fetch)
    assert out["splits"] == [["035720", "2021-04-15", 5.0], ["AAPL", "2020-08-31", 4.0]] and out["splitsKr"]["cand"] == 1
    assert log.has("상장주식수가 10% 넘게 바뀐 종목 1 중 1종목을 다음 일별 시세로 봤어요 → 후보 1")


def test_an_event_after_the_stocks_price_date_waits_for_the_next_publish(monkeypatch):
    """가격은 그 종목의 가격 날짜(기준일 · 자기 날짜 pxd) 종가인데, 그 뒤 날짜의 분할을 실으면 앱이 주식 수만 바꿔요 (가치가 배율만큼 틀려요)."""
    Log(monkeypatch)
    rows, info = F.kr_splits_fields(None, kr_rows("035720"), [], kakao_dart(), TODAY, seed=[cand("035720")], px_date="2021-04-14")
    assert rows == [] and info["late"] == [["035720", "2021-04-15"]] and info["calls"] == 0
    kr = [{"t": "035720", "cls": "kr", "cap": 1.0, "pxd": "2021-04-14"}]                       # 기준일은 뒤지만 그 종목은 마지막 확인 종가에 머묾
    rows, info = F.kr_splits_fields(None, kr, [], kakao_dart(), TODAY, seed=[cand("035720")], px_date="2026-11-20")
    assert rows == [] and info["late"] == [["035720", "2021-04-15"]]
    rows, info = F.kr_splits_fields(None, kr_rows("035720"), [], kakao_dart(), TODAY, seed=[cand("035720")], px_date="2021-04-15")
    assert rows == [["035720", "2021-04-15", 5.0]] and "late" not in info
