# -*- coding: utf-8 -*-
"""2026-11-24 (감사 aud5): 관문의 '글자에 nan·None·null·undefined 없음' 줄 (validate_data.BAD_WORD · 바꾸지 않는 안전 규칙) 은 네 파일의 모든
글자를 봐요. 그런데 파이프라인이 스스로 그 낱말을 적어서, 오류 하나 · 나쁜 줄 하나가 발행을 멈출 수 있었어요:
  a. "발행을 멈추지 않는" 단계의 오류 글 (pxSrc.own.err · usSrc.own.err · ownDrop.krOwn · usExtraMissing 의 까닭) 과 다른 우리 기록의 까닭
     (usForeign.cut '… financialCurrency None …' · d1Base.ex '900001 nan' · 마지막 확인 종가(None) 까닭)
  b. Jack 의 상시 규칙의 기록 (ownDrop rows 의 까닭: 'd null' · 'role "None"' · '"NaN" (YYYY-MM-DD 날짜가 아님)')
  c. 출처의 글자 (DART 보고자가 직위에 'None' · 야후 설명의 'None of …')
고친 것 (파이프라인만 · 관문은 그대로): 우리가 만드는 오류 · 까닭 글은 그 낱말을 '빈 값' 으로, 키 · 주소의 물음표 뒤는 '…' 로 바꿔 적고 원문은
로그에 (fetch_data.pub_text · pub_err · own_drop_pub · 쓰기 바로 앞 pub_sweep) · 출처 글자 (de · pos — 이름 nm 은 아니에요) 는 그 칸만 비우고
ownDrop.srcText 에 세요 (5칸을 넘으면 그대로 둬 관문의 그 줄이 막아요 — 새 관문 줄 없음). splitsInfo.err 는 로그에만 가요 (발행 파일에는 noCol 만).
네트워크 없음."""
import copy
import datetime as dt
import inspect
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402
import test_v196b_data as T  # noqa: E402

TEXT_ROW = "글자에 nan·None·null·undefined 없음"
WORDS = ("nan", "NaN", "None", "null", "undefined")
TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
OCT = [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)]


def gate_words(obj):
    """관문의 그 줄과 같은 검사 (validate_data.text_values · BAD_WORD) — 걸린 곳들."""
    return [f"{p}={v[:40]}" for p, v in V.text_values(obj) if V.BAD_WORD.search(v)]


def gate(cur, prev, final):
    """관문 전체 (test_validate.check 와 같은 인자)."""
    return V.run_checks(cur, prev, final, TODAY, mode="publish", count_between=lambda a, b: 1, sessions={"dates": OCT, "src": "시험"},
                        now=NOW, hilo=hilo_of(cur, V.MUST))


def row(rep, name):
    return next(r for r in rep.rows if r[0] == name)


# ── 1. 도우미: 관문과 같은 패턴 ─────────────────────────────────────────────
def test_the_helper_uses_the_gates_own_pattern():
    assert F.GATE_BAD_WORD is V.BAD_WORD
    assert (F.GATE_BAD_WORD.pattern, F.GATE_BAD_WORD.flags) == (V.BAD_WORD.pattern, V.BAD_WORD.flags)
    assert F.PUB_BLANK == "빈 값" and not V.BAD_WORD.search(F.PUB_BLANK)


@pytest.mark.parametrize("word", WORDS)
@pytest.mark.parametrize("shape", ["{w}", "x {w} y", "시가총액 {w}억원", "값{w}", "({w})", '"{w}"', "{w}_1", "1{w}2", "칸 없음 d; d {w}",
                                   "KeyError: {w}", "{w} of [Index(['Close'])] · {w}"])
def test_each_whole_word_becomes_blank_like_the_gate_sees_it(word, shape):
    s = shape.format(w=word)
    assert V.BAD_WORD.search(s)                                  # 관문이 막는 글
    out = F.pub_text(s, say=False)
    assert out == V.BAD_WORD.sub("빈 값", s) and not V.BAD_WORD.search(out) and "빈 값" in out
    assert F.pub_text(out, say=False) == out                     # 한 번 바꾼 글은 그대로


@pytest.mark.parametrize("s", ["nanometer", "Nonesuch Corp.", "nullable", "undefinedness", "Banana", "NaNs", "xnull", "none", "NULL",
                               "NAN", "Null", "Undefined", "annual nanotech review", "삼성전자", "", "1,234.5"])
def test_words_inside_other_words_stay_as_the_gate_leaves_them(s):
    assert not V.BAD_WORD.search(s)
    assert F.pub_text(s, say=False) == s


def test_cut_first_then_clean_and_non_text():
    assert F.pub_text("nanometer", 3, say=False) == "빈 값"                      # 자른 끝이 낱말이 돼도
    assert F.pub_text("ab Nonexistent", 7, say=False) == "ab 빈 값"
    assert F.pub_text(None, say=False) == "빈 값" and F.pub_text(float("nan"), say=False) == "빈 값"
    assert F.pub_text(12, say=False) == "12"
    assert F.pub_err(ValueError("cannot convert float NaN to integer"), say=False) == "ValueError: cannot convert float 빈 값 to integer"
    assert F.pub_err(KeyError(None), say=False) == "KeyError: 빈 값"
    assert F.pub_err("TypeError: x", say=False) == "TypeError: x"
    assert F.pub_err("E: " + "a" * 400, say=False) == ("E: " + "a" * 400)[:300]
    assert F.pub_err("E: " + "a" * 400, None, say=False) == "E: " + "a" * 400


SECRET = "0123456789abcdef0123456789abcdef01234567"          # 가짜 키 (DART crtfc_key 꼴 · 40자)
DART_ERR = ("HTTPSConnectionPool(host='opendart.fss.or.kr', port=443): Max retries exceeded with url: /api/elestock.json?crtfc_key="
            + SECRET + "&corp_code=00126380 (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection>: Failed to establish'))")


@pytest.mark.parametrize("raw, want", [
    ("GET https://opendart.fss.or.kr/api/list.json?crtfc_key=" + SECRET + "&bgn_de=20261101 실패",
     "GET https://opendart.fss.or.kr/api/list.json?… 실패"),
    ("https://example.com/x?a=b", "https://example.com/x?…"),
    ("HTTP 404 for http://ecos.bok.or.kr/api/x?y=1#frag (재시도)", "HTTP 404 for http://ecos.bok.or.kr/api/x?… (재시도)"),
    ("with url: /api/list.json?crtfc_key=" + SECRET + "&page_no=1 (Caused by x)", "with url: /api/list.json?… (Caused by x)"),
    ("apikey=" + SECRET + " token=" + SECRET + " key=" + SECRET + " crtfc_key=" + SECRET, "apikey=… token=… key=… crtfc_key=…"),
    ("params {'crtfc_key': '" + SECRET + "', 'corp_code': '00126380'}", "params {'crtfc_key': '…', 'corp_code': '00126380'}"),
    ("fatal: https://x-access-token:" + SECRET + "@github.com/o/r.git", "fatal: https://…@github.com/o/r.git"),
    ("headers Authorization: Bearer " + SECRET + " sent", "headers Authorization: … sent"),
])
def test_urls_query_strings_and_keys_never_reach_the_published_text(raw, want, capsys):
    assert F.pub_text(raw) == want and SECRET not in want
    assert F.pub_text(want, say=False) == want                   # 한 번 가린 글은 그대로
    assert "원문: " + raw in capsys.readouterr().out             # 원문은 실행 로그에만 (GitHub 이 등록된 비밀은 로그에서 가려요)


def test_a_dart_style_exception_is_cut_and_hidden():
    out = F.pub_err(ConnectionError(DART_ERR), say=False)
    assert out.startswith("ConnectionError: HTTPSConnectionPool(host='opendart.fss.or.kr', port=443): Max retries exceeded with url: "
                          "/api/elestock.json?… (Caused by")
    assert SECRET not in out and "corp_code" not in out and len(out) <= 300 and not V.BAD_WORD.search(out)
    assert SECRET not in F.pub_err(ConnectionError(DART_ERR), 120, say=False)     # 잘린 키도 (자른 뒤에 가려요)
    for n in range(60, 200, 7):
        assert SECRET[:6] not in F.pub_text(DART_ERR, n, say=False), n


@pytest.mark.parametrize("s", ["TypeError: x", "KeyError: 'Close'", "ValueError: cannot convert float 빈 값 to integer", "err KeyError: 빈 값",
                               'p "1.5%"', "bd 20261031 > d 20261030", "같은 접수번호가 2번", "role \"빈 값\"", "AAPL xd",
                               "마지막 확인 종가 점검이 오류로 멈춰 뺌 (TypeError: x · usSrc.own.err)", "HTTP 503", "monkey business: 3 of 4",
                               "Max retries exceeded (Caused by ReadTimeoutError('Read timed out. (read timeout=20)'))",
                               "005930 삼성전자 · 출처 글자에 관문의 낱말 — 칸을 비움", "https://opendart.fss.or.kr/api/list.json"])
def test_a_clean_message_is_unchanged(s, capsys):
    assert F.pub_text(s) == s and F.pub_err(s) == s[:300]
    assert capsys.readouterr().out == ""


def test_the_raw_text_goes_to_the_log_only(capsys):
    assert F.pub_text("KeyError: None") == "KeyError: 빈 값"
    log = capsys.readouterr().out
    assert "원문: KeyError: None" in log
    F.pub_text("KeyError: None", say=False)
    F.pub_text("TypeError: x")
    assert capsys.readouterr().out == ""                         # 바꾼 것이 없거나 원문이 이미 로그에 있는 곳


# ── 2. a. 오류 글 (발행을 멈추지 않는 단계) ─────────────────────────────────────
NAN_ERR = "ValueError: cannot convert float NaN to integer"


def test_us_guard_writes_a_clean_error_and_keeps_the_raw_text_in_the_log(capsys):
    extra = next(t for t in F.EXTRA_US if t.isalpha())
    us = [{"t": extra, "cls": "us", "pxc": True, "pxd": "2026-11-19"}, {"t": "NVDA", "cls": "us"}]
    umeta = {"usPxDate": "2026-11-20", "usSrc": {"v": 1, "own": {"v": 1, "n": 1, "codes": [extra], "same": []}}}
    left = F.us_own_close_drop_all(us, umeta, NAN_ERR)
    assert [r["t"] for r in left] == ["NVDA"]
    assert umeta["usSrc"]["own"]["err"] == "ValueError: cannot convert float 빈 값 to integer"
    assert "빈 값" in umeta["usExtraMissing"][extra]
    assert gate_words({"usSrc": umeta["usSrc"], "usExtraMissing": umeta["usExtraMissing"]}) == []
    assert NAN_ERR in capsys.readouterr().out
    assert F.us_own_close_err(KeyError(None))["err"] == "KeyError: 빈 값"


def test_kr_guard_writes_a_clean_error_and_drop_reason(capsys):
    src = {"v": 1, "px": V.PX_SRC_FB, "date": "2026-11-18", "own": {"v": 1, "n": 1, "codes": ["400010"], "bad": {"n": 0, "rows": []}}}
    drop = []
    left = F.kr_own_close_drop_all([{"t": "400010", "cls": "kr", "pxd": "2026-11-16"}, {"t": "005930", "cls": "kr"}], src, None,
                                   "KeyError: None", drop_out=drop)
    assert [r["t"] for r in left] == ["005930"]
    assert src["own"]["err"] == "KeyError: 빈 값" and drop == [("400010", "err KeyError: 빈 값")]
    assert gate_words({"pxSrc": src, "ownDrop": {"krOwn": V.own_drop_rec(drop)}}) == []
    assert "(KeyError: None)" in capsys.readouterr().out
    assert F.kr_own_close_err(ValueError("could not convert string to float: 'None'"))["err"] == \
        "ValueError: could not convert string to float: '빈 값'"


def test_split_guard_writes_a_clean_error(monkeypatch, capsys):
    def boom(*a, **k):
        raise KeyError("None of [Index(['Close'], dtype='object')] are in the [columns]")
    monkeypatch.setattr(F, "us_splits", boom)
    splits, info = F.us_splits_safe({}, ["AAPL"], TODAY)
    assert splits is None and info["err"].startswith("KeyError: ") and "빈 값 of [Index" in info["err"] and gate_words(info) == []
    assert "원문: KeyError: \"None of [Index" in capsys.readouterr().out

    def boom2(*a, **k):                                     # 리뷰: 로그에만 가는 splitsInfo.err 도 다른 오류 칸처럼 자르고 가려요
        raise ConnectionError(DART_ERR + " None" + " x" * 600)
    monkeypatch.setattr(F, "us_splits", boom2)
    _s, info = F.us_splits_safe({}, ["AAPL"], TODAY)
    assert len(info["err"]) <= 300 and SECRET not in info["err"] and "?…" in info["err"] and gate_words(info) == []
    assert info["err"] == F.pub_err(ConnectionError(DART_ERR + " None" + " x" * 600), 300, say=False)
    log = capsys.readouterr().out
    assert SECRET in log and "x x x" in log                        # 원문 (자르지 않은 글) 은 로그에만
    assert "splits, sinfo = us_splits_safe(data, [r[\"t\"] for r in out], today)" in inspect.getsource(F.fetch_us)


def test_the_whole_gate_passes_with_a_guard_error_in_the_files():
    """관문 전체: 단계가 NaN 오류로 멈춘 날의 usSrc.own · ownDrop 기록 · 미국 일정 까닭을 실은 파일 — 낱말 줄은 통과해요 (예전: 실패)."""
    cur, prev, final = good_pair()
    cur["data"]["usSrc"] = {"v": 1, "own": F.us_own_close_err(ValueError("cannot convert float NaN to integer"))}
    assert cur["data"]["usSrc"]["own"]["err"] == "ValueError: cannot convert float 빈 값 to integer"
    next(s for s in cur["data"]["stocks"] if s["t"] == "AAPL")["xd"] = "NaN"
    F.own_us_dates(cur["data"])
    assert cur["data"]["ownDrop"]["usDates"]["rows"] == [["AAPL xd", '"빈 값" (YYYY-MM-DD 날짜가 아님)']]
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "PASS"
    cur["data"]["usSrc"]["own"]["err"] = "ValueError: cannot convert float NaN to integer"       # 예전처럼 원문을 적으면 실패 (관문 그대로)
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"


# ── 3. b. Jack 의 상시 규칙의 기록 ───────────────────────────────────────────
def test_an_own_drop_reason_with_a_null_is_written_clean_and_the_gate_warns_not_fails(capsys):
    cur, prev, final = T.good_files()
    cur["disc"]["issue"][0]["kind"] = None
    cur["disc"]["issue"][1].pop("d")
    F.own_check_disc(cur["disc"], TODAY)
    rec = cur["disc"]["ownDrop"]["issueShape"]
    assert rec["n"] == 2 and all("빈 값" in w for _k, w in rec["rows"]) and gate_words(cur["disc"]["ownDrop"]) == []
    assert any(w.startswith("칸 없음 d; d 빈 값") for _k, w in rec["rows"])
    assert V.own_rows_get(cur["disc"], "issueShape")[0] == "ok"                     # 기록 모양 그대로
    log = capsys.readouterr().out
    assert "kind null" in log and "d null" in log                                  # 원문은 로그 (_own_log)
    assert "disc.json ownDrop.issueShape: 까닭 글 2줄의 낱말" in log
    rep = gate(cur, prev, final)
    assert row(rep, TEXT_ROW)[3] == "PASS" and row(rep, T.ISSUE_ROW)[3] == "WARN", rep.table()


def test_own_drop_pub_keeps_every_record_shape_and_is_idempotent():
    doc = {"ownDrop": {"usClass": {"n": 1, "rows": [["BFB", "role \"None\""]]}, "indFill": {"n": 1, "rows": ["005930 삼성전자: nan 업종"], "err": "X"},
                       "krOwn": {"n": 1, "rows": [("400010", "err KeyError: None")]}, "odd": "nan", "empty": {"n": 0, "rows": []}}}
    F.own_drop_pub(doc, "data.json")
    once = copy.deepcopy(doc)
    F.own_drop_pub(doc, "data.json")
    assert doc == once and gate_words({k: v for k, v in doc["ownDrop"].items() if k != "odd"}) == []
    assert doc["ownDrop"]["usClass"]["rows"] == [["BFB", 'role "빈 값"']] and doc["ownDrop"]["krOwn"]["rows"] == [["400010", "err KeyError: 빈 값"]]
    assert doc["ownDrop"]["indFill"] == {"n": 1, "rows": ["005930 삼성전자: 빈 값 업종"], "err": "X"}
    assert doc["ownDrop"]["odd"] == "nan"                    # 기록이 아닌 값은 손대지 않아요 (모양은 관문이 봐요)
    assert V.own_drop_get(doc, "usClass") and V.own_drop_get(doc, "krOwn")
    for junk in (None, {}, {"ownDrop": None}, {"ownDrop": {"a": None, "b": {"rows": None}}}):
        F.own_drop_pub(junk, "x")


# ── 4. c. 출처의 글자: 그 칸만 비우고 세요 (5칸 넘으면 그대로 · 관문이 막아요) ─────────────────
API = [{"rcept_no": "20261030000999", "rcept_dt": "2026-10-30", "repror": "John Smith", "isu_exctv_rgist_at": "비등기임원", "isu_exctv_ofcps": "None",
        "isu_main_shrholdr": "-", "sp_stock_lmp_irds_cnt": "1,000", "sp_stock_lmp_rate": "0.10"}]


def disc_with_dart_rows(cur, n=1):
    e = F.parse_elestock_corp(API, "20261001")[0]
    assert e["pos"] == "None"                                           # DART 가 보낸 그대로
    base = cur["disc"]["insider"][0]
    for i in range(n):
        cur["disc"]["insider"].insert(0, dict(base, rc=f"2026103000{900 + i:04d}", d=e["d"], nm=e["nm"], pos=e["pos"], role=e["role"], q=e["q"]))


def test_a_dart_position_none_is_blanked_counted_and_logged(capsys):
    cur, prev, final = T.good_files()
    disc_with_dart_rows(cur)
    F.own_check_disc(cur["disc"], TODAY)
    F.own_src_text(cur["disc"], "disc.json")
    F.own_drop_pub(cur["disc"], "disc.json")
    r = next(x for x in cur["disc"]["insider"] if x["rc"] == "20261030000900")
    assert r["pos"] == "" and r["nm"] == "John Smith" and r["q"] == 1000                 # 그 칸만
    rec = cur["disc"]["ownDrop"]["srcText"]
    assert rec == {"n": 1, "rows": [["20261030000900 pos", "005930 삼성전자 · 출처 글자에 관문의 낱말 — 칸을 비움"]]}
    assert V.own_rows_get(cur["disc"], "srcText")[0] == "ok" and gate_words(cur["disc"]) == []
    log = capsys.readouterr().out
    assert "  !! 출처 글자의 관문 낱말 (야후 설명 de · DART 직위 pos): disc.json 1칸 비움 — 005930 삼성전자 pos (20261030000900: …None…)" in log
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "PASS"


def test_a_yahoo_summary_with_none_of_is_blanked_and_counted(capsys):
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "MSFT")
    s["de"] = F.cut_words("Acme operates three segments. None of the segments is reported separately. " + "It sells widgets. " * 30, 400)
    F.own_src_text(cur["data"], "data.json")
    assert "de" not in s and cur["data"]["ownDrop"]["srcText"]["n"] == 1
    assert cur["data"]["ownDrop"]["srcText"]["rows"][0][0] == "MSFT de"
    assert V.own_drop_get(cur["data"], "srcText") and gate_words(cur["data"]) == []
    assert "data.json 1칸 비움 — MSFT" in capsys.readouterr().out
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "PASS"


def test_five_fields_are_blanked_and_six_are_left_for_the_gate_to_stop(capsys):
    assert F.SRC_TEXT_MAX == 5 and F.SRC_TEXT_KEY == "srcText"
    cur, prev, final = T.good_files()
    disc_with_dart_rows(cur, 5)
    F.own_src_text(cur["disc"], "disc.json")
    assert cur["disc"]["ownDrop"]["srcText"]["n"] == 5 and gate_words(cur["disc"]) == []
    assert "5칸을 넘으면 비우지 않아 관문이 막아요" in capsys.readouterr().out
    cur, prev, final = T.good_files()
    disc_with_dart_rows(cur, 6)                               # 한꺼번에 많으면 우리 처리의 잘못일 수 있어요
    F.own_src_text(cur["disc"], "disc.json")
    F.own_drop_pub(cur["disc"], "disc.json")
    assert [r["pos"] for r in cur["disc"]["insider"][:6]] == ["None"] * 6                 # 비우지 않아요
    rec = cur["disc"]["ownDrop"]["srcText"]
    assert rec["n"] == 6 and all(w.endswith("그대로 둠 (관문이 막아요)") for _k, w in rec["rows"])
    log = capsys.readouterr().out
    assert "disc.json 6칸 찾음" in log and "5칸을 넘어 비우지 않고 그대로 둬요" in log
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"                              # 관문의 그 줄 그대로 (새 줄 없음)


def test_a_clean_run_records_zero_and_other_fields_are_left_to_the_gate(capsys):
    cur, prev, final = T.good_files()
    before = copy.deepcopy(cur)
    F.own_src_text(cur["data"], "data.json")
    F.own_src_text(cur["disc"], "disc.json")
    for n in ("data", "disc"):
        assert cur[n]["ownDrop"]["srcText"] == {"n": 0, "rows": []}
        cur[n]["ownDrop"].pop("srcText")
        if not cur[n]["ownDrop"] and "ownDrop" not in before[n]:
            cur[n].pop("ownDrop")
    assert cur == before
    assert "· 출처 글자의 관문 낱말 (야후 설명 de · DART 직위 pos): data.json 0칸 비움" in capsys.readouterr().out
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "000660")
    s["dk"] = "nan · 주요제품: 반도체 · KOSPI 상장"                  # 2026-10 열 밀림 사고의 칸 — 비우지 않아요 (관문이 막아요)
    F.own_src_text(cur["data"], "data.json")
    assert s["dk"].startswith("nan") and cur["data"]["ownDrop"]["srcText"]["n"] == 0
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"


# ── 4b. 리뷰 1차 (#178): 키 가리기 · 쓰기 바로 앞의 마지막 한 번 · 이름 nm ─────────────────────────
KEY = "f00dfeedcafe0123456789abcdef0123456789ab"            # 가짜 키 (환경 변수로만 · 어디에도 적지 않아요)


@pytest.mark.parametrize("raw, gone", [
    ("crtfc_key='" + SECRET + "' x", "crtfc_key='…' x"),
    ("crtfc_key = " + SECRET + " x", "crtfc_key = … x"),
    ("crtfc_key: " + SECRET, "crtfc_key: …"),
    ("params=[('crtfc_key', '" + SECRET + "'), ('page', '1')]", "params=[('crtfc_key', '…'), ('page', '1')]"),
    ("X-Api-Key: " + SECRET + " sent", "X-Api-Key: … sent"),
    ("token " + "Bearer " + SECRET, "token Bearer …"),
    ("Cookie: sid=" + SECRET + "; a=b", "Cookie: …"),
    ("ftp://u:" + SECRET + "@files.example.com/x", "ftp://…@files.example.com/x"),
    ("/api/StatisticSearch/" + SECRET + "/json/kr/1/100/817Y002", "/api/StatisticSearch/…/json/kr/1/100/817Y002"),
    ("{'crtfc_key': '" + SECRET[:20], "{'crtfc_key': '…"),                       # 잘린 뒤 반만 남은 키 (닫는 따옴표 없음)
    ("fatal: https://x-access-token:" + SECRET[:20], "fatal: https://…"),           # '@' 앞에서 잘린 주소
    ("GET /api/list.json crtfc_key " + SECRET, "GET /api/list.json crtfc_key …"),
    ("/api/x?" + SECRET, "/api/x?…"),
])
def test_more_key_forms_are_hidden(raw, gone):
    assert F.pub_text(raw, say=False) == gone and SECRET[:8] not in gone
    assert F.pub_text(gone, say=False) == gone


def test_the_env_keys_are_hidden_before_the_cut(monkeypatch, capsys):
    """DART · ECOS 키 글자 그대로를 먼저 가리고 자르니, 자른 끝에 키가 반만 남지 않아요 (이름 없는 ECOS 경로 · 아무 글 속도)."""
    monkeypatch.setenv("ECOS_API_KEY", KEY)
    monkeypatch.setenv("DART_API_KEY", KEY[::-1])
    raw = "x" * 290 + KEY + " and " + KEY[::-1]
    for n in range(280, 340):
        out = F.pub_text(raw, n, say=False)
        assert KEY[:4] not in out and KEY[::-1][:4] not in out, n
    ecos = f"HTTPSConnectionPool(host='ecos.bok.or.kr', port=443): Max retries exceeded with url: /api/Foo/{KEY}/json"
    assert F.pub_err(ConnectionError(ecos)) == "ConnectionError: " + ecos.replace(KEY, "…")
    assert KEY in capsys.readouterr().out                 # 원문은 로그에만 (GitHub 이 등록된 비밀은 가려요)


def test_long_adversarial_text_is_quick_and_the_logged_raw_text_is_capped(capsys):
    import time
    for s in ("'" + "key" * 10000, "key" * 10000, ('"' + "akey" * 20 + '" ') * 330, "http://" + "a" * 30000, "?a=" * 10000,
              "'" + "secretkey" * 3333 + "': '", "authorization: " * 2000):
        t0 = time.time()
        F.pub_text(s, say=False)
        assert time.time() - t0 < 0.5, s[:20]
    F.pub_text("None " + "y" * 20000)
    log = capsys.readouterr().out
    assert len(log) < F.PUB_LOG_MAX + 400 and "원문 20,005자" in log


def test_reason_prefixes_the_gate_and_app_read_are_untouched():
    """pub_text 는 낱말 · 키만 바꿔요 — 관문 · us_fgn_kind 가 읽는 까닭의 머리말과 정한 글은 그대로."""
    for s in [F.US_FOREIGN_CUR_WHY, V.US_FGN_NOREC_WHY, *V.US_FGN_NOCMP_WHY.values(), *V.KR_OWN_WHY.values(), *F.US_OWN_WHY.values(),
              *F.US_NOCL_KO.values()]:
        assert F.pub_text(s, say=False) == s, s
    why = F.us_foreign_cuts({"per": 10.0, "pbr": 1.0}, {"currency": "USD"}, None)["per"]     # 야후가 financialCurrency 를 주지 않은 날
    assert V.BAD_WORD.search(why)
    clean = F.pub_text(why, say=False)
    assert clean.startswith(F.US_FOREIGN_CUR_WHY) and clean.startswith(V.US_FGN_CUR_WHY) and F.us_fgn_kind("per", clean) == "currency"


def sweep_case():
    """리뷰가 재현한 길 (빌더는 그대로 · 원문 글): 외국 회사 까닭 · d1 기준가 예의 이름 · 잠시 뺀 까닭 · 오류 · ownDrop."""
    import numpy as np
    import pandas as pd
    cur, prev, final = good_pair()
    d = cur["data"]
    why = F.us_foreign_cuts({"per": 10.0}, {"currency": "USD"}, None)["per"]
    d["usForeign"] = dict(d.get("usForeign") or {}, cut=[["TM", "per", why]], kept=[["SHEL", "pbr", "1.70배 ↔ nan배"]])
    df = pd.DataFrame({"Code": ["900001"], "Name": [np.nan]})
    names = dict(zip(df["Code"].astype(str).str.strip(), df["Name"].astype(str)))
    d["d1Base"] = F.d1_base_record(None, None, None, {"900001": "noPub"}, {"noPub": [("900001", 1.0, 1.0)]}, names)
    aged = f"마지막 확인 종가({None}) 뒤 미국 거래일 {F.US_OWN_CLOSE_MAX_DAYS}일이 지나 잠시 뺌 (usSrc.own.aged)"
    d["usExtraMissing"] = {"SPY": aged}
    d["usListSym"] = {"spGone": {"ABC": aged}, "unmapped": [["sp500", "XYZ", "KeyError: None"]]}
    d["pxSrc"] = dict(d.get("pxSrc") or {}, own={"v": 1, "err": "KeyError: None", "dropEx": ["005930 nan"],
                                                  "bad": {"n": 1, "rows": [f"https://opendart.fss.or.kr/x?crtfc_key={SECRET}"]}})
    d["usSrc"] = {"v": 1, "newWait": ["NEW"], "own": {"v": 1, "err": "ValueError: NaN", "aged": [{"t": "OLD", "pxd": "2026-10-20", "why": aged}]}}
    d["splitsInfo"] = {"noCol": [], "fixed": [["CBSH", "2016-11-30", 1.05, "주식배당 — 근거 None"]]}
    d["ownDrop"] = {"usDates": {"n": 1, "rows": [["AAPL xd", '"NaN" (YYYY-MM-DD 날짜가 아님)']]}}
    return cur, prev, final


def test_the_final_sweep_cleans_every_own_record_path_and_leaves_stock_rows(capsys):
    cur, prev, final = sweep_case()
    d = cur["data"]
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"                     # 빌더 그대로 (리뷰의 재현)
    stocks = copy.deepcopy(d["stocks"])
    F.pub_sweep(d, "data.json")
    assert gate_words({k: d[k] for k in F.PUB_SWEEP_KEYS if k in d}) == [] and SECRET not in json.dumps(d, ensure_ascii=False)
    assert d["stocks"] == stocks                                                  # 종목 줄은 그대로
    assert d["usForeign"]["cut"][0][2].startswith(F.US_FOREIGN_CUR_WHY) and F.us_fgn_kind("per", d["usForeign"]["cut"][0][2]) == "currency"
    assert d["d1Base"]["ex"] == {"noPub": ["900001 빈 값"]} and d["usExtraMissing"]["SPY"].startswith("마지막 확인 종가(빈 값) 뒤")
    assert d["splitsInfo"]["fixed"][0][:3] == ["CBSH", "2016-11-30", 1.05]
    rep = gate(cur, prev, final)
    assert row(rep, TEXT_ROW)[3] == "PASS", rep.table()
    log = capsys.readouterr().out
    assert "· data.json 우리 기록 글 " in log and "usForeign.cut[0][2] (원문: 재무제표 통화를 모름 (야후 financialCurrency None" in log
    once = copy.deepcopy(d)
    F.pub_sweep(d, "data.json")
    assert d == once and "바꿀 것 없음" in capsys.readouterr().out
    cur, prev, final = sweep_case()
    next(s for s in cur["data"]["stocks"] if s["t"] == "MSFT")["nk"] = "None Corp"   # 종목의 글은 손대지 않아요 — 관문이 그대로 막아요
    F.pub_sweep(cur["data"], "data.json")
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"


def test_the_insider_name_is_never_blanked_and_the_gate_still_stops_it(capsys):
    """리뷰 1차: 화면은 '{nm} · {pos}' — 이름을 비우면 숫자만 있고 이름도 이유도 없는 줄이 돼요 (Jack 의 say-why 규칙). 이름은 이 PR 전처럼 관문이 봐요."""
    assert F.SRC_TEXT_FIELDS == (("stocks", "t", ("de",)), ("insider", "rc", ("pos",)))
    cur, prev, final = T.good_files()
    cur["disc"]["insider"][0]["nm"] = "None"
    F.own_src_text(cur["disc"], "disc.json")
    assert cur["disc"]["insider"][0]["nm"] == "None" and cur["disc"]["ownDrop"]["srcText"] == {"n": 0, "rows": []}
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"


# ── 5. 배선 · 앱 ───────────────────────────────────────────────────────────
def test_main_cleans_right_before_each_write_and_no_raw_error_is_written():
    src = inspect.getsource(F.main)
    a, b, c = src.index('payload["ownDrop"][KR_OWN_DROP_KEY] = own_drop_rec(kr_drop)'), src.index("own_src_text(payload, OUT)"), \
        src.index("pub_sweep(payload, OUT)")
    assert a < b < c < src.index("write_json(OUT, payload)")
    d, e, f = src.index("own_check_disc(disc, today)"), src.index("own_src_text(disc, OUT_DISC)"), \
        src.index('pub_sweep(disc, OUT_DISC, keys=("ownDrop",))')
    assert d < e < f < src.index("write_json(OUT_DISC, disc)")
    assert 'own_drop_pub(disc, "disc.json")' in inspect.getsource(F.own_check_disc)
    assert 'own_drop_pub(payload, "data.json")' in inspect.getsource(F.own_us_dates)
    whole = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert not re.search(r'"err": str\(err\)|"err": f"\{type\(e\)\.__name__\}: \{e\}"|f"err \{str\(err\)', whole)
    assert 'f"{type(e).__name__}: {str(e)[:200]}"' not in whole            # 리뷰: 미리 자른 글이 아니라 예외째 (자르기 전에 키를 가려요)
    for fn in (F.kr_own_close_step, F.us_own_close_step, F.main):
        assert "str(e)[:200]" not in inspect.getsource(fn), fn.__name__
    assert "srcText" in F.UNITS["ownDrop"] and gate_words(F.UNITS) == []


def test_the_app_never_reads_the_error_or_record_fields():
    """'빈 값' 은 로그 · 관문 · 기록의 글에만 나가요: 앱 (src/) 은 ownDrop · srcText · usExtraMissing · 오류 칸 (pxSrc.own.err · usSrc.own.err ·
    splitsInfo) 을 읽지 않아요 (splitsInfo 는 fixed 의 앞 세 칸만 — lots.js). 비운 출처 칸 (de · pos) 은 원래 비어 있을 수 있는 칸이에요 (설명이
    없는 종목 · DART 의 '-')."""
    hits = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "src")):
        for name in files:
            if name.endswith((".js", ".jsx")):
                text = open(os.path.join(base, name), encoding="utf-8").read()
                for pat in (r"ownDrop", r"srcText", r"usExtraMissing", r"\bown\??\.err\b", r"splitsInfo\??\.err\b", r"\[\s*[\"']err[\"']\s*\]"):
                    hits += [f"{name}: {m.group(0)}" for m in re.finditer(pat, text)]
    assert hits == []
    co = open(os.path.join(ROOT, "src", "v2", "company.js"), encoding="utf-8").read()
    assert 'nm: typeof x.nm === "string" ? x.nm : ""' in co and 'pos: typeof x.pos === "string" && x.pos !== "-" ? x.pos : ""' in co
    json.dumps(F.UNITS, allow_nan=False)
