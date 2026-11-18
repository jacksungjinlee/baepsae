# -*- coding: utf-8 -*-
"""v19.6b Q18 (Jack 2026-11-19 "rights board date from documents: yes"): 유상증자 줄의 bd 를 공시 원문(document.xml)의 이사회결의일(결정일)에서
읽어요 — fetch_data.parse_issue_bd · read_issue_bd · fill_issue_bd 와 관문 줄 validate_data.check_issue_bd.

고정 자료(tests/fixtures/v196b/bd)는 진짜 DART 원문의 모양을 본떠 만든 작은 원문이에요 (회사 · 숫자는 지어낸 것 · 키 없음). 본뜬 원문
(2026-11-19 에 읽어 보고 파서가 같은 날을 읽는 것을 확인했어요 · 저장소에는 넣지 않았어요):
- rights_original.xml    육일씨엔에쓰 20260826000431 — 정정 없는 첫 공시 · <TU AUNIT="DRC_DT" AUNITVALUE="20260826">2026년 08월 26일</TU>
- rights_correction.xml  뷰노 20261111000261 — 앞의 <CORRECTION> 정정 표(10-15 → 11-11) + 고친 양식(11-11)
- rights_note.xml        STX 20261013000428 — 회생계획 인가일 09-16 · 본문 문단에도 '15. 이사회결의일(결정일)' 이 나와요 (표 칸이 아님)
- rights_dots.xml        20261002000638 — 글자가 '2026.09.28'
- rights_missing.xml     더코디 20261105000548 (철회 정정) — 결의일 칸이 '-'
- rights_mismatch · rights_garbled · rights_correction_only · rights_two_dates · rights_old_html (euc-kr · 소문자 태그) — 지어낸 이상한 원문
네트워크 없음 (원문 조회는 가짜 client.get_zip)."""
import collections
import copy
import datetime as dt
import inspect
import json
import os
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "v196b", "bd")
TODAY = dt.date(2026, 11, 15)
ROW = V.ISSUE_BD_ROW


def raw(name):
    with open(os.path.join(FX, name), "rb") as f:
        return f.read()


def text(name, rc="20261111000261"):
    """원문 zip 의 파일들 → 글자 (파이프라인과 같은 dvwhy_doc_text · euc-kr 도)."""
    return F.dvwhy_doc_text({f"{rc}.xml": raw(name)}, rc)


def doc_on(day8):
    """rights_original.xml 의 결의일을 day8 (YYYYMMDD) 로 바꾼 원문 bytes."""
    s = raw("rights_original.xml").decode("utf-8")
    ko = f"{day8[:4]}년 {day8[4:6]}월 {day8[6:]}일"
    return s.replace('AUNITVALUE="20260826"', f'AUNITVALUE="{day8}"').replace("2026년 08월 26일", ko).encode("utf-8")


# ── 원문 읽기 (순수 함수) ─────────────────────────────────────────────────

@pytest.mark.parametrize("name, want", [
    ("rights_original.xml", "20260826"),
    ("rights_correction.xml", "20261111"),     # 정정 표의 정정 전 10-15 가 아니라 고친 양식의 날
    ("rights_note.xml", "20260916"),           # 본문 문단의 '15. 이사회결의일(결정일)' 은 표 칸이 아니라 읽지 않아요
    ("rights_dots.xml", "20260928"),
    ("rights_old_html.html", "20260908"),      # euc-kr · 소문자 태그 · DRC_DT 없음 · 정정 전 · 후 줄(값 둘)은 빼고 양식 줄
])
def test_date_found(name, want):
    assert F.parse_issue_bd(text(name)) == (want, None)


@pytest.mark.parametrize("name, why", [
    ("rights_missing.xml", "결의일 칸이 비었어요 ('-')"),
    ("rights_mismatch.xml", "결의일 칸의 값 20261111 와 글자 '2026년 11월 12일' 가 달라요"),
    ("rights_garbled.xml", "결의일 칸의 값 '20261345' 이 날짜가 아니에요"),
    ("rights_correction_only.xml", "원문에 이사회결의일(결정일) 칸이 없어요"),          # 정정 표만 — 정정 전 · 후 값은 읽지 않아요
    ("rights_two_dates.xml", "이사회결의일 줄이 2개인데 같은 날이 아니에요 (20261027, 20261022)"),
])
def test_date_missing_or_garbled_is_none_with_a_reason(name, why):
    assert F.parse_issue_bd(text(name)) == (None, why)


@pytest.mark.parametrize("junk", [None, "", "<DOCUMENT><BODY>", "\x00\x01PK\x03\x04 garbage", "15. 이사회결의일(결정일) 2026년 11월 11일",
                                  raw("rights_original.xml").decode("utf-8")[:1500]])
def test_garbled_documents_never_raise(junk):
    bd, why = F.parse_issue_bd(junk)
    assert bd is None and why


def test_undecodable_bytes_read_as_no_document():
    assert F.read_issue_bd(F.dvwhy_doc_text({"x.xml": b"\xff\xfe\xfa\xfb" * 10}, "20261111000261"), "20261111") == (None, "원문 없음")


def test_the_main_file_is_read_not_an_attachment():
    files = {"20261111000261.xml": raw("rights_correction.xml"), "20261111000261_00760.xml": raw("rights_dots.xml") * 3}
    assert F.read_issue_bd(F.dvwhy_doc_text(files, "20261111000261"), "20261111") == ("20261111", None)


@pytest.mark.parametrize("s, want", [
    ("2026년 11월 11일", "20261111"), ("2026 년   08 월  26일", "20260826"), ("2026-9-8", "20260908"), ("2026.09.28", "20260928"),
    ("2026.09.28.", "20260928"), ("20261111", "20261111"), ("\xa02026-11-11 ", "20261111"),
    ("2026년 11월", None), ("2026-11-11 (예정)", None), ("2026-11.11", None), ("２０２６-11-11", None), ("20261131", None), ("2026년 2월 29일", None),
    ("1999-01-01", None), ("-", None), ("", None), (None, None), ("이사회결의일 2026-11-11", None),
])
def test_a_cell_is_a_date_only_when_it_is_one_whole_date(s, want):
    assert F.issue_bd_day(s) == want


def test_date_after_the_filing_is_rejected():
    assert F.read_issue_bd(text("rights_original.xml"), "20260826") == ("20260826", None)        # 같은 날은 맞아요
    assert F.read_issue_bd(text("rights_original.xml"), "20260825") == (None, "결의일 20260826 이 공시일 20260825 뒤예요")


def test_date_more_than_a_year_before_the_filing_is_rejected():
    assert F.ISSUE_BD_MAX_YEARS == 1
    assert F.read_issue_bd(text("rights_original.xml"), "20270826") == ("20260826", None)        # 딱 1년은 맞아요
    assert F.read_issue_bd(text("rights_original.xml"), "20270827") == (None, "결의일 20260826 이 공시일 20270827 보다 1년 넘게 앞이에요")
    assert F.issue_bd_range_why("20270228", "20280229") is None                                   # 윤일 공시의 1년 전은 2월 28일
    assert F.issue_bd_range_why("20270227", "20280229")
    assert F.issue_bd_range_why("2026-08-26", "20260826") and F.issue_bd_range_why("20260826", None)


# ── fill_issue_bd (가짜 DART · 캐시) ──────────────────────────────────────

class Client:
    """DartClient 와 같은 모양의 가짜 (entries · lock · status · fatal · down · today · get_zip). 원문은 접수번호마다 bytes."""
    def __init__(self, docs=None, today=TODAY, fail=(), boom=(), fatal_on=(), entries=None):
        self.docs, self.today = dict(docs or {}), today
        self.fail, self.boom, self.fatal_on = set(fail), set(boom), set(fatal_on)
        self.entries = dict(entries or {})
        self.lock, self.status = threading.Lock(), collections.Counter()
        self.fatal = self.down = None
        self.calls = []

    def get_zip(self, endpoint, params, timeout=40):
        assert endpoint == "document.xml" and set(params) == {"rcept_no"} and timeout == F.ISSUE_BD_TIMEOUT
        rc = params["rcept_no"]
        with self.lock:
            self.calls.append(rc)
        if self.fatal:
            return None
        if rc in self.boom:
            raise RuntimeError("연결이 끊겼어요")
        if rc in self.fatal_on:
            self.status["020"] += 1
            self.fatal = ("020", "요청 제한을 초과하였습니다.")
            return None
        if rc in self.fail:
            self.status["예외"] += 1
            return None
        self.status["000"] += 1
        got = self.docs[rc]
        return dict(got) if isinstance(got, dict) else {f"{rc}.xml": got}      # dict 면 zip 안의 파일들 그대로


def irow(rc, d, kind="rights", **kw):
    r = {"rc": rc, "d": d, "t": "005930", "nk": f"회사{rc[-3:]}", "kind": kind, "bd": None, "how": "others" if kind == "rights" else None,
         "n": 1000 if kind == "rights" else None, "p": 1.5, "amt": None if kind == "rights" else 1000000000, "cor": False}
    r.update(kw)
    return r


def disc_of(rows, ok=True):
    return {"asOf": TODAY.isoformat(), "issue": rows, "issueOk": ok}


def three():
    """유상증자 셋 (원문 있음) + 철회 · 읽는 중 · CB 한 줄씩."""
    rows = [irow("20261113000111", "20261113"), irow("20261110000222", "20261110"), irow("20261020000333", "20261020"),
            irow("20261112000444", "20261112", wd=True, how=None, n=None, p=None),
            irow("20261111000555", "20261111", pend=True, how=None, n=None, p=None),
            irow("20261105000666", "20261105", kind="cb", bd="20261029")]
    docs = {"20261113000111": doc_on("20261113"), "20261110000222": doc_on("20261031"), "20261020000333": doc_on("20260915")}
    return rows, docs


def test_fill_reads_each_rights_row_once_and_caches_it(capsys):
    rows, docs = three()
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    by = {r["rc"]: r for r in rows}
    assert [by[rc]["bd"] for rc in ("20261113000111", "20261110000222", "20261020000333")] == ["20261113", "20261031", "20260915"]
    assert by["20261112000444"]["bd"] is None and by["20261111000555"]["bd"] is None     # 철회 · 읽는 중은 읽지 않아요 (bd 늘 빈 칸)
    assert by["20261105000666"]["bd"] == "20261029"                                       # 사채는 상세 API 의 결의일 그대로
    assert sorted(c.calls) == sorted(docs)
    assert c.entries == {f"{rc}|issuebd|v2": {"st": "000", "at": "2026-11-15", "d": by[rc]["bd"]} for rc in docs}
    assert (out["target"], out["read"], out["unread"], out["later"], out["fetched"], out["calls"]) == (3, 3, 0, 0, 3, 3)
    log = capsys.readouterr().out
    assert "· 유상증자 이사회 결의일(공시 원문 document.xml): 문서에서 읽음 3 / 대상 3, 못 읽음 0, 기간 밖이라 비움 0, 다음 실행으로 0" in log


def test_a_cached_hit_makes_no_call():
    rows, docs = three()
    c = Client(docs)
    F.fill_issue_bd(disc_of(rows), c, TODAY)
    rows2, _ = three()
    c2 = Client({}, today=TODAY + dt.timedelta(days=3), entries=c.entries)                 # 원문이 없어도 캐시로 끝
    out = F.fill_issue_bd(disc_of(rows2), c2, TODAY + dt.timedelta(days=3))
    assert c2.calls == [] and out["cached"] == 3 and out["read"] == 3
    assert [r["bd"] for r in rows2 if r["kind"] == "rights" and not r.get("wd") and not r.get("pend")] == ["20261113", "20261031", "20260915"]


def test_an_unreadable_document_is_cached_counted_and_never_read_again(capsys):
    rows = [irow("20261113000111", "20261113"), irow("20261110000222", "20261110"), irow("20261020000333", "20261020")]
    docs = {"20261113000111": raw("rights_missing.xml"), "20261110000222": doc_on("20261111"),      # 결의일이 공시일 뒤
            "20261020000333": raw("rights_garbled.xml")}
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert [r["bd"] for r in rows] == [None, None, None]
    assert (out["read"], out["unread"], out["limited"], out["later"]) == (0, 2, 1, 0)
    assert c.entries["20261113000111|issuebd|v2"] == {"st": "nf", "at": "2026-11-15", "d": None, "why": "결의일 칸이 비었어요 ('-')"}
    # 리뷰 2026-11-19: 공시일 뒤 결의일은 '못 읽음'이 아니에요 — 원문의 날을 그대로 적고, 쓸 때 기간을 확인해 비워요 ('기간 밖이라 비움')
    assert c.entries["20261110000222|issuebd|v2"] == {"st": "000", "at": "2026-11-15", "d": "20261111"}
    log = capsys.readouterr().out
    assert "  !! 유상증자 이사회 결의일(공시 원문 document.xml): 문서에서 읽음 0 / 대상 3, 못 읽음 2, 기간 밖이라 비움 1, 다음 실행으로 0" in log
    assert "!! 결의일을 못 읽은 유상증자 공시 2건 (bd 빈 칸 · 같은 공시는 다시 읽지 않아요): 회사111 20261113 20261113000111 (결의일 칸이 비었어요 ('-'))" in log
    assert "!! 결의일이 공시일과 맞지 않아 비운 유상증자 공시 1건" in log and "회사222 20261110 20261110000222 (결의일 20261111 이 공시일 20261110 뒤예요)" in log
    c2 = Client({}, entries=c.entries)
    rows2 = copy.deepcopy(rows)
    out2 = F.fill_issue_bd(disc_of(rows2), c2, TODAY)
    assert c2.calls == [] and (out2["unread"], out2["limited"]) == (2, 1) and [r["bd"] for r in rows2] == [None, None, None]


def test_the_per_run_budget_reads_the_newest_first_and_leaves_the_rest_for_the_next_run(monkeypatch, capsys):
    monkeypatch.setattr(F, "ISSUE_BD_PER_RUN", 2)
    rows = [irow(f"202611{d:02d}000{d:03d}", f"202611{d:02d}") for d in (3, 13, 9, 1, 11)]
    docs = {r["rc"]: doc_on(r["d"]) for r in rows}
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert sorted(c.calls) == ["20261111000011", "20261113000013"]                         # 최근 공시 둘
    assert (out["read"], out["later"], out["cap"]) == (2, 3, 3)
    assert set(c.entries) == {"20261111000011|issuebd|v2", "20261113000013|issuebd|v2"}      # 못 한 것은 캐시에 적지 않아요
    assert "  !! 유상증자 이사회 결의일(공시 원문 document.xml): 문서에서 읽음 2 / 대상 5, 못 읽음 0, 기간 밖이라 비움 0, 다음 실행으로 3" in capsys.readouterr().out
    c2 = Client(docs, entries=c.entries)
    out2 = F.fill_issue_bd(disc_of(rows), c2, TODAY)
    assert sorted(c2.calls) == ["20261103000003", "20261109000009"] and (out2["read"], out2["later"]) == (4, 1)
    c3 = Client(docs, entries=c2.entries)
    assert F.fill_issue_bd(disc_of(rows), c3, TODAY)["later"] == 0 and c3.calls == ["20261101000001"]
    assert all(r["bd"] == r["d"] for r in rows)


def test_the_time_budget_stops_new_reads(monkeypatch):
    monkeypatch.setattr(F, "ISSUE_BD_SECONDS", -1)
    rows, docs = three()
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert c.calls == [] and (out["read"], out["later"], out["time"]) == (0, 3, 3) and not c.entries


def test_a_failed_fetch_keeps_bd_blank_is_not_cached_and_is_retried():
    rows, docs = three()
    c = Client(docs, fail={"20261110000222"}, boom={"20261020000333"})
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    by = {r["rc"]: r for r in rows}
    assert by["20261113000111"]["bd"] == "20261113" and by["20261110000222"]["bd"] is None and by["20261020000333"]["bd"] is None
    assert (out["read"], out["later"], out["fail"]) == (1, 2, 2) and set(c.entries) == {"20261113000111|issuebd|v2"}
    c2 = Client(docs, entries=c.entries)
    rows2, _ = three()
    assert F.fill_issue_bd(disc_of(rows2), c2, TODAY)["read"] == 3 and sorted(c2.calls) == ["20261020000333", "20261110000222"]


def test_dart_stopping_mid_phase_never_fails_the_run(monkeypatch, capsys):
    monkeypatch.setattr(F, "ISSUE_BD_WORKERS", 1)
    rows, docs = three()
    c = Client(docs, fatal_on={"20261110000222"})
    d = disc_of(rows)
    out = F.fill_issue_bd(d, c, TODAY)
    assert d["issueOk"] is True and len(d["issue"]) == 6                                    # 줄은 그대로 · issueOk 도
    assert (out["read"], out["later"], out["stop"]) == (1, 2, 2) and c.calls == ["20261113000111", "20261110000222"]
    assert "DART 가 멈춰 2 (상태 020)" in capsys.readouterr().out


def test_a_parser_error_is_counted_not_cached(monkeypatch):
    def boom(*a, **k):
        raise ValueError("x")
    monkeypatch.setattr(F, "parse_issue_bd", boom)                       # 원문을 읽는 함수가 멈춰요
    rows, docs = three()
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert (out["err"], out["later"], out["read"]) == (3, 3, 0) and not c.entries


def test_nothing_is_read_on_a_day_the_list_failed(capsys):
    rows, docs = three()
    rows[0]["bd"] = "20261113"                                                              # 지난 발행본의 줄 · 그때의 결의일
    before = copy.deepcopy(rows)
    c = Client(docs)
    assert F.fill_issue_bd(disc_of(rows, ok=False), c, TODAY) == {"skip": True}
    assert c.calls == [] and rows == before
    assert "!! 유상증자 이사회 결의일: 오늘 주요사항 공시 목록을 받지 못해 원문을 읽지 않아요" in capsys.readouterr().out


def test_a_cached_date_outside_the_window_is_blanked_not_read_again():
    """리뷰 2026-11-19: 캐시의 날이 공시일과 맞지 않으면 그 줄의 bd 만 비워요 (원문을 다시 받지 않아요 · '기간 밖이라 비움')."""
    rows, docs = three()
    c = Client(docs, entries={"20261113000111|issuebd|v2": {"st": "000", "at": "2026-11-13", "d": "20261120"}})
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert "20261113000111" not in c.calls and rows[0]["bd"] is None and (out["limited"], out["unread"], out["read"]) == (1, 0, 2)
    assert c.entries["20261113000111|issuebd|v2"]["d"] == "20261120"                     # 캐시는 원문의 날 그대로


def test_old_keys_are_dropped_and_todays_rows_keep_theirs():
    rows, docs = three()
    rows.append(irow("20260818000777", "20260819"))                 # 접수번호 날짜는 기간 앞이지만 공시일(목록의 접수일)은 기간 안: 오늘 줄
    docs["20260818000777"] = doc_on("20260818")
    ent = {"20260818000777|issuebd|v2": {"st": "000", "at": "2026-08-19", "d": "20260818"},
           "20260801000888|issuebd|v2": {"st": "000", "at": "2026-08-01", "d": "20260801"},       # 기간 밖
           "20261001000999|issuebd|v2": {"st": "nf", "at": "2026-10-01", "d": None, "why": "x"},  # 기간 안 (오늘 줄은 아니어도 둬요)
           "20261113000111|issuebd|v0": {"st": "000", "at": "2026-11-13", "d": "20261113"},       # 다른 판
           "20261113000111|issue|v2": {"st": "000", "at": "2026-11-13", "d": {}},                 # fetch_issues 의 키 — 손대지 않아요
           "00126380|2025|11011|fin": {"st": "000", "at": "2026-11-01", "d": {}}}
    c = Client(docs, entries=ent)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert out["dropped"] == 2 and "20260818000777" not in c.calls and rows[-1]["bd"] == "20260818"
    assert set(c.entries) == {"20260818000777|issuebd|v2", "20261001000999|issuebd|v2", "20261113000111|issue|v2", "00126380|2025|11011|fin"} \
        | {f"{rc}|issuebd|v2" for rc in ("20261113000111", "20261110000222", "20261020000333")}


def test_targets_are_the_same_rows_the_gate_counts():
    rows, _ = three()
    rows += [irow("20261101000123", "20261101", wd=False, pend=False), irow("20261101000124", "20261101", wd="yes"), "junk", None]
    got = {r["rc"] for r in F.issue_bd_targets(rows)}
    assert got == {"20261113000111", "20261110000222", "20261020000333", "20261101000123", "20261101000124"}   # 참(True)만 철회 (모양은 '주요사항 공시' 줄이 봐요)
    rep = V.Report()
    V.check_issue_bd(rep, disc_of(rows))
    assert rep.rows[0][1].startswith(f"결의일 있음 0 / 대상 {len(got)}")


def test_main_reads_board_dates_after_the_issue_list_and_before_the_cache_is_saved():
    src = inspect.getsource(F.main)
    a = src.index('ph.run("주요사항 공시", fetch_issues')
    b = src.index('ph.run("유상증자 결의일", fill_issue_bd, disc, client, today)')
    assert a < b < src.index("client.save()", b)


def test_budget_numbers_are_the_stated_ones():
    """보고한 한도: 실행당 원문 100건 · 180초 · 하나 20초. 바꾸면 PR 과 RUNBOOK 의 첫 실행 어림도 고쳐요."""
    assert (F.ISSUE_BD_PER_RUN, F.ISSUE_BD_SECONDS, F.ISSUE_BD_TIMEOUT, F.ISSUE_BD_TAG) == (100, 180, 20, "issuebd|v2")
    assert F.ISSUE_BD_MAX_YEARS == 1                                  # Jack 에게 묻는 한도 (지금은 1년)
    assert "|issue|" not in "x|" + F.ISSUE_BD_TAG                    # fetch_issues 의 정리(키에 '|issue|')가 지우지 않게


def test_insider_holder_words_switch_is_on():
    """Q21 (Jack 2026-11-19 yes): 주요주주 줄의 직위에 DART 의 관계 말을 그대로 보여요."""
    assert F.INSIDER_POS_HOLDER_WORDS is True


# ── fetch_issues → fill_issue_bd → 관문 (고정 자료의 진짜 상세 응답) ──────────

def test_real_rows_get_board_dates_and_pass_the_gate(tmp_path, monkeypatch):
    import test_v196b_data as T
    monkeypatch.setattr(F, "OUT_DISC", str(tmp_path / "disc.json"))
    c = F.DartClient("k", mode="cache", today=TODAY, path=str(tmp_path / "c.json.gz"))
    c.get = T.Dart(c)
    asked = []

    def get_zip(endpoint, params, timeout=40):
        asked.append(params["rcept_no"])
        return {f"{params['rcept_no']}.xml": doc_on(by[params["rcept_no"]]["d"])}
    c.get_zip = get_zip
    out = F.fetch_issues(T.KR, T.CORP, TODAY, c)
    by = {r["rc"]: r for r in out["issue"]}
    tg = {r["rc"] for r in out["issue"] if r["kind"] == "rights" and not r.get("wd") and not r.get("pend")}
    assert len(tg) == 8 and all(by[rc]["bd"] is None for rc in tg)                       # fetch_issues 는 그대로 (유상증자 bd null)
    disc = {"asOf": TODAY.isoformat(), **out, "insider": []}
    F.fill_issue_bd(disc, c, TODAY)
    assert sorted(asked) == sorted(tg) and all(by[rc]["bd"] == by[rc]["d"] for rc in tg)
    assert all(r["bd"] is None for r in out["issue"] if r["kind"] == "rights" and r.get("wd"))
    c.save()
    data = {"asOf": TODAY.isoformat(), "stocks": [dict(s) for s in T.KR]}
    rep = V.Report()
    V.check_v196b(rep, data, disc, {s["t"]: s for s in data["stocks"]}, TODAY)
    V.check_issue_bd(rep, disc)
    got = {r[0]: r for r in rep.rows}
    assert got[T.ISSUE_ROW][3] == "PASS" and got[ROW][3] == "PASS" and got[ROW][1] == "결의일 있음 8 / 대상 8", rep.table()
    c2 = F.DartClient("k", mode="cache", today=TODAY, path=str(tmp_path / "c.json.gz"))       # 저장한 캐시로 다음 실행: 원문을 다시 안 읽어요
    asked.clear()
    c2.get_zip = get_zip
    disc2 = {"asOf": TODAY.isoformat(), **copy.deepcopy(out), "insider": []}
    for r in disc2["issue"]:
        r["bd"] = r["bd"] if r["kind"] != "rights" else None
    assert F.fill_issue_bd(disc2, c2, TODAY)["cached"] == 8 and asked == []


# ── 관문 줄 ───────────────────────────────────────────────────────────────

def gate(disc):
    rep = V.Report()
    V.check_issue_bd(rep, disc)
    assert len(rep.rows) == 1 and rep.rows[0][0] == ROW
    return rep.rows[0], rep


def test_gate_passes_when_every_rights_row_has_its_date():
    rows, _ = three()
    for r, d in zip(rows[:3], ("20261113", "20261031", "20260915")):
        r["bd"] = d
    row, rep = gate(disc_of(rows))
    assert row[3] == "PASS" and row[1] == "결의일 있음 3 / 대상 3" and not rep.details


def test_gate_warns_with_the_count_still_missing():
    rows, _ = three()
    rows[0]["bd"] = "20261113"
    row, rep = gate(disc_of(rows))
    assert row[3] == "WARN" and row[1] == "결의일 있음 1 / 대상 3 · 결의일 빈 줄 2 (원문을 아직 다 읽지 못했거나 원문에서 못 읽음)"
    assert rep.details == [("유상증자 이사회 결의일이 빈 줄", ['"회사222" "20261110" "20261110000222"', '"회사333" "20261020" "20261020000333"'])]


def test_gate_fails_a_board_date_after_the_filing():
    rows, _ = three()
    for r, d in zip(rows[:3], ("20261114", "20261031", "20260915")):
        r["bd"] = d
    row, rep = gate(disc_of(rows))
    assert row[3] == "FAIL" and "공시일 뒤 결의일 1" in row[1] and "bd 20261114 > d 20261113" in row[1]
    assert rep.details[0][0] == "유상증자 이사회 결의일이 공시일 뒤인 줄"


def test_gate_does_not_count_withdrawn_pending_or_bond_rows():
    rows = [irow("20261112000444", "20261112", wd=True), irow("20261111000555", "20261111", pend=True), irow("20261105000666", "20261105", kind="cb"),
            irow("20261105000667", "20261105", kind="bw", bd="20261110")]          # 사채의 결의일은 이 줄이 보지 않아요 (상세 API 의 값)
    row, _ = gate(disc_of(rows))
    assert row[3] == "PASS" and row[1] == "결의일 있음 0 / 대상 0"


def test_gate_skips_files_without_an_issue_section():
    for disc in ({"asOf": "2026-10-31"}, None, "x", {"issue": "x"}, {"issue": None}):
        row, _ = gate(disc)
        assert row[3] == "SKIP", disc


@pytest.mark.parametrize("junk", [[None], ["x"], [{"kind": "rights"}], [{"kind": "rights", "bd": 20261111, "d": "20261113"}],
                                  [{"kind": "rights", "bd": "20261111", "d": None}], [{"kind": ["rights"], "bd": {}}],
                                  [{"kind": "rights", "bd": "2026-11-11", "d": "20261113", "nk": None, "rc": 5}]])
def test_gate_never_crashes_on_junk(junk):
    row, _ = gate(disc_of(junk))
    assert "검사가 오류로 멈췄어요" not in row[1] and row[3] in ("PASS", "WARN")


def test_a_crash_inside_the_check_is_a_failed_row(monkeypatch):
    def boom(*a, **k):
        raise KeyError("x")
    monkeypatch.setattr(V, "_check_issue_bd", boom)
    row, _ = gate(disc_of([]))
    assert row[3] == "FAIL" and "검사가 오류로 멈췄어요: KeyError" in row[1]


def test_run_checks_has_the_row_and_old_files_only_skip_it():
    from test_validate import check
    import test_v196b_data as T
    rep = check(*good_pair())                                         # v19.6b 전 파일 (issue 없음): SKIP
    assert [r[3] for r in rep.rows if r[0] == ROW] == ["SKIP"] and ROW not in {r[0] for r in rep.failed}
    cur, prev, final = T.good_files()                                 # 유상증자 줄의 bd 가 빈 칸 (원문을 아직 못 읽은 날)
    rep = check(cur, prev, final)
    assert [r[3] for r in rep.rows if r[0] == ROW] == ["WARN"]
    cur["disc"]["issue"][0]["bd"] = "20261030"
    rep = check(cur, prev, final)
    assert [r[3] for r in rep.rows if r[0] == ROW] == ["PASS"]
    names = [r[0] for r in rep.rows]
    assert names.index(ROW) == names.index(T.US_ROW) + 1              # check_v196b 의 세 줄 바로 뒤


def test_the_published_json_has_no_new_fields():
    """bd 는 스펙의 칸 그대로예요 (새 칸 없음) — 줄의 칸 순서도 그대로."""
    rows, docs = three()
    keys = [list(r) for r in rows]
    F.fill_issue_bd(disc_of(rows), Client(docs), TODAY)
    assert [list(r) for r in rows] == keys
    json.dumps(rows, allow_nan=False)


# ── 리뷰 2026-11-19 (f5d3a54 의 세 가지) ───────────────────────────────────

def test_a_long_postponed_correction_is_cached_as_read_and_used_when_the_limit_changes(monkeypatch, capsys):
    """1. 원문의 날은 그대로 캐시하고 기간 확인은 쓸 때 해요: 오래 미룬 제3자배정 정정(결의 2024-03-04 · 정정 2026-11-06)은 오늘 '기간 밖이라
    비움', 한도를 바꾸면 원문을 다시 받지 않고 그날을 써요 (판을 올릴 필요가 없어요)."""
    rows = [irow("20261106000123", "20261106")]
    docs = {"20261106000123": doc_on("20240304")}
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert rows[0]["bd"] is None and (out["read"], out["unread"], out["limited"], out["later"]) == (0, 0, 1, 0)
    assert c.entries["20261106000123|issuebd|v2"] == {"st": "000", "at": "2026-11-15", "d": "20240304"}
    log = capsys.readouterr().out
    assert "못 읽음 0, 기간 밖이라 비움 1, 다음 실행으로 0" in log
    assert "(결의일 20240304 이 공시일 20261106 보다 1년 넘게 앞이에요)" in log and "결의일을 못 읽은" not in log
    monkeypatch.setattr(F, "ISSUE_BD_MAX_YEARS", 3)
    rows2 = copy.deepcopy(rows)
    c2 = Client({}, entries=c.entries)
    out2 = F.fill_issue_bd(disc_of(rows2), c2, TODAY)
    assert c2.calls == [] and rows2[0]["bd"] == "20240304" and (out2["read"], out2["limited"]) == (1, 0)


def test_v1_cache_keys_are_dropped_and_read_again():
    """v1 은 기간 밖 날을 nf 로 적었어요 — 판을 올려 한 번 다시 읽어요."""
    rows = [irow("20261106000123", "20261106")]
    c = Client({"20261106000123": doc_on("20261105")},
               entries={"20261106000123|issuebd|v1": {"st": "nf", "at": "2026-11-14", "d": None, "why": "결의일 20240304 이 …"}})
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert c.calls == ["20261106000123"] and rows[0]["bd"] == "20261105" and out["dropped"] == 1
    assert set(c.entries) == {"20261106000123|issuebd|v2"}


@pytest.mark.parametrize("files, why", [
    ({}, "받은 zip 이 비었어요"),
    ({"20261113000111.xml": b"\xff\xfe\xfa\xfb" * 10}, "본 파일이 비었거나 글자로 바꾸지 못했어요 (utf-8 · cp949 · euc-kr)"),
    ({"20261113000111.xml": b""}, "본 파일이 비었거나 글자로 바꾸지 못했어요 (utf-8 · cp949 · euc-kr)"),
    ({"20261113000111.xml": b"  \r\n "}, "본 파일이 비었거나 글자로 바꾸지 못했어요 (utf-8 · cp949 · euc-kr)"),
])
def test_an_empty_zip_or_an_undecodable_document_is_a_fetch_failure(files, why, capsys):
    """2. 빈 zip · 글자로 바꾸지 못한 본 파일은 받기 실패: 적지 않고 (영원한 '못 읽음'이 아니에요) 다음 실행이 다시 받아요 · !! 로 남겨요."""
    assert F.issue_doc_main(files, "20261113000111") == (None, ("fail", why))
    rows, docs = three()
    docs["20261113000111"] = files
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert rows[0]["bd"] is None and (out["fail"], out["unread"], out["later"], out["read"]) == (1, 0, 1, 2)
    assert "20261113000111|issuebd|v2" not in c.entries
    log = capsys.readouterr().out
    assert "  !! 유상증자 이사회 결의일" in log and f"조회 실패 1 (회사111 20261113 20261113000111 ({why}))" in log
    docs["20261113000111"] = doc_on("20261113")                                         # 다음 실행: 제대로 받으면 읽어요
    c2 = Client(docs, entries=c.entries)
    rows2, _ = three()
    assert F.fill_issue_bd(disc_of(rows2), c2, TODAY)["read"] == 3 and c2.calls == ["20261113000111"]


def test_without_the_main_file_no_attachment_is_read(capsys):
    """3. zip 에 본 파일 '{접수번호}.xml' 이 없으면 가장 큰 파일(첨부)을 읽지 않아요 — 첨부의 날을 결의일로 읽을 수 있어요. 원문은 바뀌지 않아서
    nf 로 적어요 (같은 이유가 로그에)."""
    att = {"20261113000111_00760.xml": doc_on("20261101"), "20261113000111_00761.xml": raw("rights_dots.xml")}
    assert F.dvwhy_doc_text(att, "20261113000111")                                       # 예전 길(가장 큰 파일)이라면 첨부를 읽었을 거예요
    why = "zip 에 본 파일(20261113000111.xml)이 없어요 (다른 파일 2개는 읽지 않아요)"
    assert F.issue_doc_main(att, "20261113000111") == (None, ("nf", why))
    rows, docs = three()
    docs["20261113000111"] = att
    c = Client(docs)
    out = F.fill_issue_bd(disc_of(rows), c, TODAY)
    assert rows[0]["bd"] is None and (out["unread"], out["read"], out["fail"]) == (1, 2, 0)
    assert c.entries["20261113000111|issuebd|v2"] == {"st": "nf", "at": "2026-11-15", "d": None, "why": why}
    assert f"회사111 20261113 20261113000111 ({why})" in capsys.readouterr().out
    c2 = Client({}, entries=c.entries)
    rows2, _ = three()
    F.fill_issue_bd(disc_of(rows2), c2, TODAY)
    assert c2.calls == [] and rows2[0]["bd"] is None


def test_the_main_file_is_found_in_a_folder_and_beside_attachments():
    files = {"doc/20261113000111.xml": doc_on("20261113"), "20261113000111_00760.xml": doc_on("20261101") * 3}
    text, bad = F.issue_doc_main(files, "20261113000111")
    assert bad is None and F.parse_issue_bd(text) == ("20261113", None)
    euc = {"20261113000111.xml": raw("rights_old_html.html")}
    text, bad = F.issue_doc_main(euc, "20261113000111")
    assert bad is None and F.parse_issue_bd(text) == ("20260908", None)
