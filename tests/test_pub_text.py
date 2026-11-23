# -*- coding: utf-8 -*-
"""2026-11-24 (감사 aud5): 관문의 '글자에 nan·None·null·undefined 없음' 줄 (validate_data.BAD_WORD · 바꾸지 않는 안전 규칙) 은 네 파일의 모든
글자를 봐요. 그런데 파이프라인이 스스로 그 낱말을 적어서, 오류 하나 · 나쁜 줄 하나가 발행을 멈출 수 있었어요:
  a. "발행을 멈추지 않는" 단계의 오류 글 (pxSrc.own.err · usSrc.own.err · splitsInfo.err · ownDrop.krOwn · usExtraMissing 의 까닭)
  b. Jack 의 상시 규칙의 기록 (ownDrop rows 의 까닭: 'd null' · 'role "None"' · '"NaN" (YYYY-MM-DD 날짜가 아님)')
  c. 출처의 글자 (DART 보고자가 직위에 'None' · 야후 설명의 'None of …')
고친 것 (파이프라인만 · 관문은 그대로): 우리가 만드는 오류 · 까닭 글은 그 낱말을 '빈 값' 으로 바꿔 적고 원문은 로그에 (fetch_data.pub_text ·
pub_err · own_drop_pub) · 출처 글자는 그 칸만 비우고 ownDrop.srcText 에 세요 (5칸을 넘으면 그대로 둬 관문의 그 줄이 막아요 — 새 관문 줄 없음).
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
    assert "splits, sinfo = us_splits_safe(data, [r[\"t\"] for r in out], today)" in inspect.getsource(F.fetch_us)


def test_the_whole_gate_passes_with_a_guard_error_in_the_files():
    """관문 전체: 단계가 NaN 오류로 멈춘 날의 splitsInfo · ownDrop 기록 · 미국 일정 까닭을 실은 파일 — 낱말 줄은 통과해요 (예전: 실패)."""
    cur, prev, final = good_pair()

    def boom(*a, **k):
        raise ValueError("cannot convert float NaN to integer")
    us_splits = F.us_splits
    try:
        F.us_splits = boom
        _s, info = F.us_splits_safe({}, ["AAPL"], TODAY)
    finally:
        F.us_splits = us_splits
    cur["data"]["splitsInfo"] = info
    next(s for s in cur["data"]["stocks"] if s["t"] == "AAPL")["xd"] = "NaN"
    F.own_us_dates(cur["data"])
    assert cur["data"]["ownDrop"]["usDates"]["rows"] == [["AAPL xd", '"빈 값" (YYYY-MM-DD 날짜가 아님)']]
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "PASS"
    cur["data"]["splitsInfo"] = {"err": "ValueError: cannot convert float NaN to integer"}       # 예전처럼 원문을 적으면 실패 (관문 그대로)
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
    assert "  !! 출처 글자의 관문 낱말 (야후 설명 de · DART 보고자 이름 nm · 직위 pos): disc.json 1칸 비움 — 005930 삼성전자 pos (20261030000900: …None…)" in log
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
    assert "· 출처 글자의 관문 낱말 (야후 설명 de · DART 보고자 이름 nm · 직위 pos): data.json 0칸 비움" in capsys.readouterr().out
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "000660")
    s["dk"] = "nan · 주요제품: 반도체 · KOSPI 상장"                  # 2026-10 열 밀림 사고의 칸 — 비우지 않아요 (관문이 막아요)
    F.own_src_text(cur["data"], "data.json")
    assert s["dk"].startswith("nan") and cur["data"]["ownDrop"]["srcText"]["n"] == 0
    assert row(gate(cur, prev, final), TEXT_ROW)[3] == "FAIL"


# ── 5. 배선 · 앱 ───────────────────────────────────────────────────────────
def test_main_cleans_right_before_each_write_and_no_raw_error_is_written():
    src = inspect.getsource(F.main)
    a, b, c = src.index('payload["ownDrop"][KR_OWN_DROP_KEY] = own_drop_rec(kr_drop)'), src.index("own_src_text(payload, OUT)"), \
        src.index("own_drop_pub(payload, OUT)")
    assert a < b < c < src.index("write_json(OUT, payload)")
    d, e, f = src.index("own_check_disc(disc, today)"), src.index("own_src_text(disc, OUT_DISC)"), src.index("own_drop_pub(disc, OUT_DISC)")
    assert d < e < f < src.index("write_json(OUT_DISC, disc)")
    assert 'own_drop_pub(disc, "disc.json")' in inspect.getsource(F.own_check_disc)
    assert 'own_drop_pub(payload, "data.json")' in inspect.getsource(F.own_us_dates)
    whole = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert not re.search(r'"err": str\(err\)|"err": f"\{type\(e\)\.__name__\}: \{e\}"|f"err \{str\(err\)', whole)
    assert "srcText" in F.UNITS["ownDrop"] and gate_words(F.UNITS) == []


def test_the_app_never_reads_the_error_or_record_fields():
    """'빈 값' 은 로그 · 관문 · 기록의 글에만 나가요: 앱 (src/) 은 ownDrop · srcText · usExtraMissing · 오류 칸 (pxSrc.own.err · usSrc.own.err ·
    splitsInfo.err) 을 읽지 않아요. 비운 출처 칸 (de · nm · pos) 은 원래 비어 있을 수 있는 칸이에요 (설명이 없는 종목 · DART 의 '-')."""
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
