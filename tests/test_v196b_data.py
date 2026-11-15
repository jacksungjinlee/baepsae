# -*- coding: utf-8 -*-
"""v19.6b 데이터 (Part B.1 · 오늘 볼 것): disc.json issue (유상증자 · CB · BW 결정) · insider role · data.json 미국 ed · xd · 관문 세 줄.

고정 자료(tests/fixtures/v196b)는 2026-11-15 의 진짜 응답이에요 (키 없음): DART list.json 주요사항보고서 한 쪽(줄 일부) · piicDecsn ·
cvbdIsDecsn · bdwtIsDecsn (회사 · 종류마다 2015년부터) · elestock 행 일부 · 야후 get_info 의 날짜 칸 (Ticker.calendar 값도 같이 적었어요).
네트워크 없음."""
import collections
import copy
import datetime as dt
import gzip
import json
import math
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "v196b")
TODAY = dt.date(2026, 11, 15)
# 종목코드 → DART 기업코드 (공개 고유번호 · 2026-11-15 corpCode.xml)
CORP = {"191410": "00843900", "079190": "00479705", "067390": "00409681", "178320": "00838005", "336260": "01412725",
        "338220": "01344202", "180060": "00874937", "224060": "00530413", "179530": "01022902"}
EP_KIND = {"piicDecsn.json": "rights", "cvbdIsDecsn.json": "cb", "bdwtIsDecsn.json": "bw"}
SPEC_KEYS = ["rc", "d", "t", "nk", "kind", "bd", "how", "n", "p", "amt", "cor"]


def fx(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


LIST = fx("list_b001.json")
NAMES = {it["stock_code"]: it["corp_name"] for it in LIST["list"] if it["stock_code"]}
KR = [{"t": t, "nk": NAMES.get(t, t), "cls": "kr", "price": 1000.0} for t in CORP]


def detail(kind, t):
    return fx(f"detail_{kind}_{t}.json")


def api_row(kind, t, rc):
    return next(r for r in detail(kind, t)["list"] if r["rcept_no"] == rc)


class Dart:
    """가짜 DART: list.json 은 고정 자료 한 쪽, 상세 API 는 회사 · 종류마다 고정 자료. 부른 것을 적어요. client.get 자리에 끼워요."""
    def __init__(self, client, page=None, details=None, list_fail=False, detail_fail=()):
        self.client, self.calls = client, []
        self.page = copy.deepcopy(LIST if page is None else page)
        self.details = details or {}
        self.list_fail, self.detail_fail = list_fail, set(detail_fail)

    def __call__(self, endpoint, params, timeout=25):
        self.calls.append((endpoint, dict(params)))
        if endpoint == "list.json":
            bgn = (self.client.today - dt.timedelta(days=F.DISC_DAYS - 1)).strftime("%Y%m%d")       # 지분공시와 같은 90일 (11-15 → 08-18)
            assert params["pblntf_ty"] == "B" and params["pblntf_detail_ty"] == "B001" and params["bgn_de"] == bgn
            if self.list_fail:
                return None
            self.client.status["000"] += 1
            return copy.deepcopy(self.page)
        kind = EP_KIND[endpoint]
        assert params["bgn_de"] == F.ISSUE_DETAIL_FROM == "20150101" and params["end_de"] == self.client.today.strftime("%Y%m%d")
        t = next(t for t, c in CORP.items() if c == params["corp_code"])
        if (kind, t) in self.detail_fail:
            return None
        self.client.status["000"] += 1
        got = self.details.get((kind, t))
        return copy.deepcopy(got) if got is not None else detail(kind, t)

    def detail_calls(self):
        return [(EP_KIND[e], next(t for t, c in CORP.items() if c == p["corp_code"])) for e, p in self.calls if e != "list.json"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """fetch_issues 를 돌리는 판: 지난 disc.json(없음 또는 prev) · DART 캐시 파일 · 오늘."""
    disc_path = tmp_path / "disc.json"
    monkeypatch.setattr(F, "OUT_DISC", str(disc_path))
    state = {"cache": str(tmp_path / "c.json.gz")}

    def run(prev=None, today=TODAY, **kw):
        if prev is not None:
            disc_path.write_text(json.dumps(prev, ensure_ascii=False), encoding="utf-8")
        c = F.DartClient("k", mode="cache", today=today, path=state["cache"])
        d = Dart(c, **kw)
        c.get = d
        out = F.fetch_issues(KR, CORP, today, c)
        c.save()
        return out, d, c
    return run


def by_rc(rows):
    return {r["rc"]: r for r in rows}


# ── 이름 · 방식 · 칸 읽기 (진짜 응답) ─────────────────────────────────────

@pytest.mark.parametrize("name, want", [
    ("주요사항보고서(유상증자결정)", ("rights", False, False)),
    ("[기재정정]주요사항보고서(유상증자결정)", ("rights", True, False)),
    ("[첨부정정]주요사항보고서(전환사채권발행결정)", ("cb", True, True)),
    ("주요사항보고서(신주인수권부사채권발행결정)", ("bw", False, False)),
    ("주요사항보고서(교환사채권발행결정)", (None, False, False)),        # 교환사채: 새 주식이 없어 이번 범위 밖
    ("주요사항보고서(유무상증자결정)", (None, False, False)),            # 범위 밖 (보고에 적었어요)
    ("주요사항보고서(자기전환사채만기전취득결정)", (None, False, False)),
    ("주요사항보고서(회사합병결정)", (None, False, False)),
    ("[기재정정]주요사항보고서(유상증자결정)철회", (None, True, False)),  # 철회 공시 자체
    ("주요사항보고서(종속회사의주요경영사항)(유상증자결정)", (None, False, False)),
])
def test_issue_kind_reads_report_names(name, want):
    assert F.issue_kind(name) == want


@pytest.mark.parametrize("text, want", [("주주배정증자", "holders"), ("주주배정후 실권주 일반공모", "holders"), ("주주우선공모증자", "holders"),
                                        ("제3자배정증자", "others"), ("제3자 배정증자", "others"), ("일반공모증자", "others"),
                                        ("기타", None), ("", None), (None, None), ("-", None)])
def test_issue_how_follows_the_spec(text, want):
    assert F.issue_how(text) == want


def test_parse_issue_detail_on_real_rows():
    # 더코디 제3자배정: 보통주 106,022주 ÷ 증자 전 5,160,722주 = 2.05%
    d, bad = F.parse_issue_detail(api_row("rights", "224060", "20261111000265"), "rights")
    assert d == {"bd": None, "how": "others", "n": 106022, "p": 2.05, "amt": None} and bad == []
    # 뷰노 주주배정 (보통주 6,300,000주)
    d, _ = F.parse_issue_detail(api_row("rights", "338220", "20261111000261"), "rights")
    assert d["how"] == "holders" and d["n"] == 6300000 and d["p"] == 44.99
    # 탑선: 정정 공시의 칸이 모두 '-' (DART 상세 API) → 숫자는 null, 짐작하지 않아요
    d, bad = F.parse_issue_detail(api_row("rights", "180060", "20261113000550"), "rights")
    assert d == {"bd": None, "how": "others", "n": None, "p": None, "amt": None} and bad == ["n", "p"]
    # 애드바이오텍 CB: 이사회결의일 '2026년 10월 29일' · 권면총액 1,000,000,000원 · 주식총수 대비 3.11%
    d, bad = F.parse_issue_detail(api_row("cb", "179530", "20261112000003"), "cb")
    assert d == {"bd": "20261029", "how": None, "n": None, "p": 3.11, "amt": 1000000000} and bad == []
    # 두산퓨얼셀 BW: 이사회결의일 2026-10-13 · 1,000억원 · 2.72%
    d, _ = F.parse_issue_detail(api_row("bw", "336260", "20261111000278"), "bw")
    assert d == {"bd": "20261013", "how": None, "n": None, "p": 2.72, "amt": 100000000000}
    # 유상증자 API 에는 이사회결의일 칸이 없어요 (bd 는 늘 null — 보고한 멈춤 항목)
    assert "bddd" not in api_row("rights", "224060", "20261111000265")


def test_parse_issue_detail_counts_preferred_shares_and_refuses_text():
    row = {"nstk_ostk_cnt": "-", "nstk_estk_cnt": "1,000,000", "bfic_tisstk_ostk": "9,000,000", "bfic_tisstk_estk": "1,000,000",
           "ic_mthn": "제3자배정증자"}
    assert F.parse_issue_detail(row, "rights")[0]["n"] == 1000000 and F.parse_issue_detail(row, "rights")[0]["p"] == 10.0
    row["bfic_tisstk_ostk"] = "약 9백만"                       # 읽지 못하는 글자 → p 는 null (n 은 읽었어요)
    d, bad = F.parse_issue_detail(row, "rights")
    assert d["n"] == 1000000 and d["p"] is None and bad == ["p"]
    d, bad = F.parse_issue_detail({"bddd": "2026-13-45", "bd_fta": "-", "ovis_fta": "50,000,000", "cvisstk_tisstk_vs": "0"}, "cb")
    assert d["bd"] is None and d["amt"] is None and d["p"] is None and bad == ["bd", "p", "amt"]   # 해외 발행(원화 금액 없음)도 null


def test_a_tiny_issue_keeps_a_positive_ratio():
    """새 주식 100주 ÷ 5,000만주 = 0.0002% — 둘째 자리로 반올림하면 0 이 돼 '없음'처럼 보이고 관문이 실패해요. 유효숫자 둘로 남겨요."""
    row = {"nstk_ostk_cnt": "100", "nstk_estk_cnt": "-", "bfic_tisstk_ostk": "50,000,000", "bfic_tisstk_estk": "-", "ic_mthn": "제3자배정증자"}
    d, bad = F.parse_issue_detail(row, "rights")
    assert d["p"] == 0.0002 and bad == []
    assert F.parse_issue_detail({"bddd": "2026년 10월 29일", "bd_fta": "100", "cvisstk_tisstk_vs": "0.001"}, "cb")[0]["p"] == 0.001
    assert not V.issue_row_problems({"rc": "20261030000111", "d": "20261030", "t": "005930", "nk": "삼성전자", "kind": "rights", "bd": None,
                                     "how": "others", "n": 100, "p": 0.0002, "amt": None, "cor": False}, dt.date(2026, 10, 31))


# ── fetch_issues: 처음 실행 · 정정 · 캐시 · 한도 · 실패 ─────────────────────

# 2026-11-15 고정 자료에서 결정의 마지막 판 (상세 API 가 결정마다 주는 접수번호 중 목록 기간 안의 것) — 손으로 확인했어요:
WANT = {
    "20261113000550": ("180060", "rights", True),    # 탑선 기재정정 (상세 API 의 칸이 모두 '-')
    "20261112000003": ("179530", "cb", True), "20261112000002": ("179530", "cb", True), "20261112000001": ("179530", "cb", True),
    "20261111000278": ("336260", "bw", True),
    "20261111000265": ("224060", "rights", True), "20261111000245": ("224060", "rights", True),
    "20261105000548": ("224060", "rights", True), "20261029000482": ("224060", "rights", True),
    "20261111000261": ("338220", "rights", True),
    "20261109000003": ("178320", "cb", True), "20261106000481": ("178320", "cb", False),
    "20260901000219": ("178320", "cb", True), "20260901000180": ("178320", "cb", True),
    "20260824000337": ("178320", "cb", False), "20260824000325": ("178320", "cb", False),
    "20261106000297": ("067390", "cb", True), "20261106000290": ("067390", "cb", True),
    "20261106000274": ("067390", "cb", True), "20261106000249": ("067390", "cb", True),
    "20260901000170": ("191410", "rights", True), "20260826000431": ("191410", "rights", False),
}


def test_first_run_gives_one_row_per_decision(env, capsys):
    out, d, c = env()
    rows = out["issue"]
    assert out["issueOk"] is True
    assert {r["rc"]: (r["t"], r["kind"], r["cor"]) for r in rows} == {k: (t, k2, cor) for k, (t, k2, cor) in WANT.items()}
    assert all(list(r) == SPEC_KEYS for r in rows)                                 # 스펙의 칸 그대로, 그 차례로
    assert [r["d"] for r in rows] == sorted((r["d"] for r in rows), reverse=True)  # 최신순
    assert sorted(d.detail_calls()) == sorted({(k, t) for t, k, _ in WANT.values()} | {("cb", "079190")})   # 쌍마다 한 번
    r = by_rc(rows)
    assert r["20261106000481"]["d"] == "20261109"            # 공시일은 목록의 접수일 (접수번호 앞자리 1106 이 아니에요)
    assert r["20261111000265"]["nk"] == "더코디" and r["20261111000265"]["n"] == 106022 and r["20261111000265"]["bd"] is None
    log = capsys.readouterr().out
    assert "주요사항 공시: 유상증자 8 · CB 13 · BW 1 (정정 18), 숫자 못 읽음 2" in log    # 탑선 · 더코디 1105 (칸이 모두 '-')
    assert "목록 밖 회사 1" in log                          # 비상장 회사의 유상증자결정


def test_same_board_date_decisions_stay_separate(env):
    """Part B.1 의 '같은 회사 · 종류 · bd = 한 결정' 규칙은 쓰지 않아요: 서진시스템은 2026-08-24 이사회에서 CB 를 여럿 정했어요 (금액이 다른 별개 결정)."""
    r = by_rc(env()[0]["issue"])
    same = sorted((x["amt"], x["rc"]) for x in r.values() if x["t"] == "178320" and x["bd"] == "20260824")
    assert same == [(32500000000, "20260824000337"), (37500000000, "20260901000180"), (62500000000, "20260901000219"),
                    (67500000000, "20260824000325")]
    assert {x["rc"] for x in r.values() if x["t"] == "178320" and x["bd"] == "20261106"} == {"20261106000481", "20261109000003"}


def test_attachment_only_corrections_keep_the_earlier_filing(env):
    """첨부정정은 본문이 그대로라 상세 API 가 앞 판 접수번호를 줘요. 목록의 '정' 표시만으로 빼면 결정이 사라져요 (육일씨엔에쓰 08-26)."""
    rows = env()[0]["issue"]
    mine = sorted((x["rc"], x["n"], x["cor"]) for x in rows if x["t"] == "191410")
    assert mine == [("20260826000431", 2305918, False), ("20260901000170", 1999999, True)]
    assert not [x for x in rows if x["t"] == "079190"]       # 케스피온: 2026-01 결정의 첨부정정뿐 — 기간 안에 결정 줄이 없어요


def test_old_decisions_corrected_in_the_window_keep_their_board_date(env):
    """아스트: 2024년 CB 네 건을 2026-11-06 에 정정 — 상세 API 를 2015년부터 물어서 찾아요. d 는 정정일, bd 는 그때 이사회결의일."""
    rows = [x for x in env()[0]["issue"] if x["t"] == "067390"]
    assert sorted((x["bd"], x["amt"]) for x in rows) == [("20240304", 50000000000), ("20240304", 52500000000),
                                                       ("20240329", 25000000000), ("20240329", 30000000000)]
    assert {x["d"] for x in rows} == {"20261106"} and all(x["cor"] for x in rows)


def test_second_run_the_same_day_calls_no_details(env):
    first, _, _ = env()
    again, d, c = env()
    assert again == first and d.detail_calls() == []
    keys = [k for k in c.entries if k.endswith("|" + F.ISSUE_TAG)]
    st = collections.Counter(c.entries[k]["st"] for k in keys)
    assert st["000"] == len(WANT) and st["nh"] > 0 and st["nf"] == 0


def test_full_mode_uses_the_saved_details(env, tmp_path):
    env()
    c = F.DartClient("k", mode="full", today=TODAY, path=str(tmp_path / "c.json.gz"))
    d = Dart(c)
    c.get = d
    assert len(F.fetch_issues(KR, CORP, TODAY, c)["issue"]) == len(WANT) and d.detail_calls() == []


def test_a_new_correction_replaces_the_old_version(env):
    """새 기재정정이 오면 그 (회사, 종류)만 다시 불러요. 상세 API 가 새 판을 주면 옛 판은 nh 로 바뀌고 줄에서 빠져요."""
    env()
    page = copy.deepcopy(LIST)
    old = next(it for it in page["list"] if it["rcept_no"] == "20261112000003")
    old["rm"] = "정"
    page["list"].insert(0, dict(old, rcept_no="20261116000001", rcept_dt="20261116", rm="", report_nm="[기재정정]주요사항보고서(전환사채권발행결정)"))
    det = detail("cb", "179530")
    row = next(r for r in det["list"] if r["rcept_no"] == "20261112000003")
    row.update(rcept_no="20261116000001", bd_fta="1,500,000,000")
    out, d, c = env(today=dt.date(2026, 11, 16), page=page, details={("cb", "179530"): det})
    r = by_rc(out["issue"])
    assert d.detail_calls() == [("cb", "179530")]
    assert "20261112000003" not in r and r["20261116000001"]["amt"] == 1500000000 and r["20261116000001"]["d"] == "20261116"
    assert c.entries["20261112000003|" + F.ISSUE_TAG]["st"] == "nh"


def test_a_latest_filing_missing_from_details_is_retried_the_next_day(env, capsys):
    det = detail("bw", "336260")
    det["list"] = [r for r in det["list"] if r["rcept_no"] != "20261111000278"]
    out, _, c = env(details={("bw", "336260"): det})
    r = by_rc(out["issue"])["20261111000278"]
    assert (r["bd"], r["p"], r["amt"]) == (None, None, None) and r["kind"] == "bw"      # 공시는 보여요 · 숫자는 null
    assert c.entries["20261111000278|" + F.ISSUE_TAG]["st"] == "nf"
    assert "마지막 판인데 상세에 없음 1건 (다음 날 다시)" in capsys.readouterr().out
    _, d, _ = env(details={("bw", "336260"): det})
    assert d.detail_calls() == []                                                       # 같은 날은 다시 묻지 않아요
    out, d, _ = env(today=dt.date(2026, 11, 16))
    assert d.detail_calls() == [("bw", "336260")] and by_rc(out["issue"])["20261111000278"]["amt"] == 100000000000


def test_the_per_run_cap_leaves_numbers_blank_and_says_so(env, monkeypatch, capsys):
    monkeypatch.setattr(F, "ISSUE_PER_RUN", 2)
    out, d, _ = env()
    assert len(d.detail_calls()) == 2
    assert d.detail_calls() == [("rights", "180060"), ("cb", "179530")]      # 가장 최근 공시가 있는 쌍부터
    rows = by_rc(out["issue"])
    assert rows["20260824000325"]["amt"] is None and rows["20260824000325"]["cor"] is False   # 아직 못 읽은 결정: 줄은 있어요, 숫자는 null
    assert "20260826000431" not in rows      # 아직 못 읽은 쌍의 '정' 표시 공시는 결정 줄인지 몰라 넣지 않아요 (다음 실행이 읽어요)
    assert "실행당 한도(2)에 닿아 다음 실행으로 7쌍" in capsys.readouterr().out
    out, d, _ = env()
    assert len(d.detail_calls()) == 2 and len(out["issue"]) < len(WANT)
    calls = [len(env()[1].detail_calls()) for _ in range(4)]       # 9쌍 = 2 + 2 + 2 + 2 + 1 (실행 다섯 번)
    assert calls == [2, 2, 1, 0]
    out, d, _ = env()
    assert sorted(by_rc(out["issue"])) == sorted(WANT) and d.detail_calls() == []


def test_a_failed_detail_call_is_not_saved(env):
    out, _, c = env(detail_fail={("cb", "067390")})
    r = by_rc(out["issue"])
    assert all(r[k]["amt"] is None for k in ("20261106000297", "20261106000249")) and out["issueOk"] is True
    assert "20261106000297|" + F.ISSUE_TAG not in c.entries
    out, d, _ = env()
    assert d.detail_calls() == [("cb", "067390")] and by_rc(out["issue"])["20261106000297"]["amt"] == 25000000000


PREV = {"asOf": "2026-11-14", "issueOk": True, "issue": [
    {"rc": "20261113000550", "d": "20261113", "t": "180060", "nk": "탑선", "kind": "rights", "bd": None, "how": "others", "n": None,
     "p": None, "amt": None, "cor": True},
    {"rc": "20260801000001", "d": "20260801", "t": "180060", "nk": "탑선", "kind": "rights", "bd": None, "how": "others", "n": 5,
     "p": 1.0, "amt": None, "cor": False}]}       # 기간 밖 (90일 전)


@pytest.mark.parametrize("how", ["none", "status", "count", "pages"])
def test_list_failure_keeps_last_runs_rows(env, monkeypatch, capsys, how):
    page = copy.deepcopy(LIST)
    kw = {}
    if how == "none":
        kw["list_fail"] = True
    elif how == "status":
        page = {"status": "800", "message": "시스템 점검"}
    elif how == "count":
        page["total_count"] = "많음"
    else:
        page["total_count"] = 99999
        monkeypatch.setattr(F, "ISSUE_MAX_PAGES", 1)
    out, d, _ = env(prev=PREV, page=page, **kw)
    assert out == {"issue": PREV["issue"][:1], "issueOk": False}
    assert d.detail_calls() == []
    assert "!! 주요사항 공시 목록(list.json B001)을 받지 못해 지난 발행본의 1건을 그대로 둬요 (최근 공시 2026-11-13 · issueOk false)" \
        in capsys.readouterr().out


def test_list_failure_without_a_previous_file_gives_an_empty_failed_list(env):
    assert env(list_fail=True)[0] == {"issue": [], "issueOk": False}


def test_a_quiet_window_is_a_valid_empty_list(env):
    out, d, _ = env(prev=PREV, page={"status": "013", "message": "조회된 데이타가 없습니다."})
    assert out == {"issue": [], "issueOk": True} and d.detail_calls() == []


def test_withdrawn_filings_are_left_out(env):
    page = copy.deepcopy(LIST)
    for it in page["list"]:
        if it["rcept_no"] == "20261111000278":
            it["rm"] = "철"
    out, _, _ = env(page=page)
    assert "20261111000278" not in by_rc(out["issue"])


def test_cache_entries_leave_with_the_window(env, tmp_path):
    env()
    c = F.DartClient("k", mode="cache", today=TODAY, path=str(tmp_path / "c.json.gz"))
    c.entries["20260601000001|" + F.ISSUE_TAG] = {"st": "000", "at": "2026-06-01", "d": {}}
    c.save()
    _, _, c2 = env()
    assert "20260601000001|" + F.ISSUE_TAG not in c2.entries and "20261111000278|" + F.ISSUE_TAG in c2.entries


def test_rows_write_as_strict_json(env, tmp_path):
    out, _, _ = env()
    p = tmp_path / "x.json"
    assert F.write_json(str(p), {"issue": out["issue"]}) == 0
    back = V.strict_loads(p.read_text(encoding="utf-8"), "x.json")["issue"]
    assert back == out["issue"]
    assert all(isinstance(r["n"], int) for r in back if r["n"] is not None)
    assert all(isinstance(r["amt"], int) for r in back if r["amt"] is not None)


def test_a_run_without_dart_writes_an_empty_failed_issue_list():
    d = F.empty_disc(TODAY)
    assert d["issue"] == [] and d["issueOk"] is False and d["listOk"] is False and d["asOf"] == "2026-11-15"


def test_the_run_estimate_keeps_the_pinned_numbers():
    """전체 DART 실행 어림(dart_full_estimate)은 그대로예요 (test_v191b_data 가 고정) — 주요사항 호출은 따로 로그에 적어요."""
    assert F.DART_DISC_MAX == 1430 and F.ISSUE_PER_RUN == 150 and F.ISSUE_EST_PAGES == 25


# ── insider: 직위 '-' 와 역할 (role) ─────────────────────────────────────

ELE = fx("elestock_rows.json")["list"]


def test_insider_pos_and_role_from_real_rows():
    got = collections.Counter(F.insider_pos_role(r) for r in ELE)
    assert got[("10%이상주주", "주요주주")] == 2 + 8                          # 이지스밸류플러스리츠 · 손오공 (직위 '-')
    assert got[("사실상지배주주", "주요주주")] == 2
    assert all(role == "임원" for (pos, role) in got if pos in ("상무", "사내이사", "대표이사", "이사"))
    both = [r for r in ELE if r["isu_exctv_ofcps"] != "-" and r["isu_main_shrholdr"] != "-"]
    assert both and all(F.insider_pos_role(r) == (r["isu_exctv_ofcps"], "임원") for r in both)   # 삼성전자 상무 + 10%이상주주 → 임원
    assert F.insider_pos_role({"isu_exctv_rgist_at": "비등기임원", "isu_exctv_ofcps": "-", "isu_main_shrholdr": "-"}) == ("", "임원")
    assert F.insider_pos_role({"isu_exctv_rgist_at": "-", "isu_exctv_ofcps": " - ", "isu_main_shrholdr": ""}) == ("", None)
    assert F.insider_pos_role({}) == ("", None)


def test_parse_elestock_corp_carries_role():
    rows = F.parse_elestock_corp(ELE, "20200101")
    assert rows and all(r["role"] in ("임원", "주요주주", None) and r["pos"] != "-" for r in rows)


def test_insider_fix_roles_refreshes_earlier_rows_and_blanks_dashes():
    rows = [{"rc": "A", "pos": "-", "q": 1}, {"rc": "B", "pos": "-", "q": 1}, {"rc": "C", "pos": "상무", "q": 1, "role": "임원"},
            {"rc": "D", "pos": "－", "q": 1}]
    n = F.insider_fix_roles(rows, {"A": ("10%이상주주", "주요주주")})
    assert [(r["pos"], r["role"]) for r in rows] == [("10%이상주주", "주요주주"), ("", None), ("상무", "임원"), ("", None)]
    assert n == {"fresh": 1, "dash": 2, "unknown": 2}


class DiscDart:
    """가짜 DART (지분공시): 임원 · 주요주주 보고 회사 하나 · elestock 은 진짜 행 (이지스밸류플러스리츠 334890)."""
    def __init__(self):
        self.rows = [r for r in ELE if r["corp_name"] == "이지스밸류플러스리츠"]
        self.down = None

    def get(self, endpoint, params):
        if endpoint == "list.json":
            return {"status": "000", "total_count": 1, "list": [{"report_nm": "임원ㆍ주요주주특정증권등소유상황보고서", "flr_nm": "x",
                                                                 "corp_code": "C1"}]}
        if endpoint == "elestock.json":
            return {"status": "000", "list": copy.deepcopy(self.rows)}
        return None

    def raise_if_fatal(self):
        pass


def test_fetch_disclosures_fixes_rows_from_earlier_runs(tmp_path, monkeypatch, capsys):
    dd = DiscDart()
    known = dd.rows[0]
    prev = {"insider": [{"rc": known["rcept_no"], "d": known["rcept_dt"].replace("-", ""), "t": "334890", "nk": "이지스밸류플러스리츠",
                         "pos": "-", "q": 1, "amt": 0.1},
                        {"rc": "20261101000001", "d": "20261101", "t": "334890", "nk": "이지스밸류플러스리츠", "pos": "-", "q": 2}],
            "nps": []}
    p = tmp_path / "disc.json"
    p.write_text(json.dumps(prev, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(F, "OUT_DISC", str(p))
    kr = [{"t": "334890", "nk": "이지스밸류플러스리츠", "cls": "kr", "s": "reit", "cap": 1.0, "price": 4000.0}]
    out = F.fetch_disclosures(kr, {"334890": "C1"}, dt.date(2026, 11, 15), dd)
    r = by_rc(out["insider"])
    assert (r[known["rcept_no"]]["pos"], r[known["rcept_no"]]["role"]) == ("10%이상주주", "주요주주")   # 지난 실행의 줄도 고쳐요
    assert (r["20261101000001"]["pos"], r["20261101000001"]["role"]) == ("", None)                   # 오늘 응답에 없는 줄: '-' → '' · 모름
    new = [x for rc, x in r.items() if rc not in (known["rcept_no"], "20261101000001")]
    assert new and all(x["role"] == "주요주주" and x["pos"] == "10%이상주주" for x in new)
    assert all(x["pos"] != "-" for x in out["insider"])
    assert "내부자 역할(role): 임원 0 · 주요주주" in capsys.readouterr().out


# ── 미국 일정: ed · xd ───────────────────────────────────────────────────

YF = fx("yahoo_info.json")


@pytest.mark.parametrize("t, ed, xd", [("AAPL", None, "2026-11-12"),      # 실적 발표일이 추정 → 빈 칸
                                        ("KO", "2026-10-27", "2026-12-01"),  # 확정 (지난 날짜 — 앱이 오늘 이후만 보여요)
                                        ("JNJ", "2027-01-26", "2026-11-24"),
                                        ("O", "2026-11-02", "2026-11-30"),
                                        ("TSLA", None, None)])               # 추정 · 배당 없음
def test_us_event_dates_match_yahoo_calendar(t, ed, xd):
    assert F.us_event_dates(YF["info"][t]) == (ed, xd, [])
    cal = YF["calendar"][t]
    assert cal.get("Ex-Dividend Date") == xd
    assert ed is None or cal["Earnings Date"] == ed


def test_ex_dividend_is_the_utc_date_not_new_york():
    """야후의 날짜만 칸은 0시 UTC — 뉴욕 시각으로 바꾸면 하루 앞 날짜가 돼요 (KO 2026-12-01 이 11-30 으로)."""
    v = YF["info"]["KO"]["exDividendDate"]
    assert dt.datetime.fromtimestamp(v, F.US_NY).date().isoformat() == "2026-11-30"
    assert F.us_event_dates({"exDividendDate": v})[1] == "2026-12-01"


@pytest.mark.parametrize("info, want", [
    ({"isEarningsDateEstimate": False, "earningsTimestampStart": 1800970200}, ("2027-01-26", None, [])),
    ({"earningsTimestampStart": 1800970200}, (None, None, [])),                                       # 확정 표시 없음 → 모름
    ({"isEarningsDateEstimate": 0, "earningsTimestampStart": 1800970200}, (None, None, [])),          # false 가 아니면 모름
    ({"isEarningsDateEstimate": False, "earningsTimestampStart": 1800970200, "earningsTimestampEnd": 1801315800}, (None, None, [])),  # 기간
    ({"isEarningsDateEstimate": False, "earningsTimestampStart": 1800970200, "earningsTimestampEnd": 1800970200}, ("2027-01-26", None, [])),
    ({"isEarningsDateEstimate": False, "earningsTimestampStart": "soon"}, (None, None, ["earningsTimestampStart"])),
    ({"isEarningsDateEstimate": False, "earningsTimestampStart": float("nan")}, (None, None, ["earningsTimestampStart"])),
    ({"exDividendDate": 1796083200 + 3600}, (None, None, ["exDividendDate"])),                        # 0시 UTC 가 아님 → 모양이 바뀐 것
    ({"exDividendDate": -86400}, (None, None, ["exDividendDate"])),
    ({"exDividendDate": float("inf")}, (None, None, ["exDividendDate"])),
    ({"exDividendDate": 1e300}, (None, None, ["exDividendDate"])),
    (None, (None, None, [])), ([], (None, None, [])),
])
def test_us_event_dates_refuse_anything_unclear(info, want):
    assert F.us_event_dates(info) == want


def test_apply_us_info_sets_and_clears_the_dates():
    rec = {"t": "KO", "price": 70.0, "ed": "2020-01-01", "xd": "2020-01-01"}
    info = dict(YF["info"]["KO"], shortName="Coca-Cola")
    assert F.apply_us_info(rec, info, 70.0, 1400.0, today=TODAY)
    assert (rec["ed"], rec["xd"]) == ("2026-10-27", "2026-12-01")
    assert F.apply_us_info(rec, dict(YF["info"]["TSLA"], shortName="Tesla"), 70.0, 1400.0, today=TODAY)
    assert "ed" not in rec and "xd" not in rec                       # 모르면 칸 없음 (예전 값이 남지 않아요)


def test_us_info_keys_grow_without_a_schema_change():
    assert {"earningsTimestampStart", "earningsTimestampEnd", "isEarningsDateEstimate", "exDividendDate"} <= set(F.US_INFO_KEYS)
    assert F.US_INFO_SCHEMA == 3 and not {"earningsTimestampStart", "exDividendDate"} & set(F.US_INFO_STICKY)   # 날짜는 옛 값을 쓰지 않아요
    assert "ed" in F.UNITS and "xd" in F.UNITS


# ── 관문: 세 줄 (pass · warn · fail · 모양이 이상한 값) ──────────────────────

ISSUE_ROW = "주요사항 공시 (issue · 유상증자 · CB · BW)"
ROLE_ROW = "임원 · 주요주주 역할 (insider role)"
US_ROW = "미국 일정 (ed 실적 발표일 · xd 배당락일)"


def good_files():
    """좋은 네 파일 (fixture_data) + 새 칸: 고정 자료의 진짜 줄 모양을 good_pair 의 종목 · 날짜(asOf 2026-10-31)로 옮겨요."""
    cur, prev, final = good_pair()
    rows = [{"rc": "20261030000111", "d": "20261030", "t": "005930", "nk": "삼성전자", "kind": "rights", "bd": None, "how": "others",
             "n": 106022, "p": 2.05, "amt": None, "cor": True},
            {"rc": "20261029000222", "d": "20261029", "t": "000660", "nk": "SK하이닉스", "kind": "cb", "bd": "20261029", "how": None, "n": None,
             "p": 3.11, "amt": 1000000000, "cor": False},
            {"rc": "20261013000333", "d": "20261013", "t": "005380", "nk": "현대차", "kind": "bw", "bd": "20240304", "how": None, "n": None,
             "p": 2.72, "amt": 100000000000, "cor": True}]
    cur["disc"].update({"issue": rows, "issueOk": True,
                        "insider": [{"rc": "20261030000444", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "가", "pos": "상무",
                                     "role": "임원", "q": 10},
                                    {"rc": "20261030000445", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "나", "pos": "10%이상주주",
                                     "role": "주요주주", "q": -5},
                                    {"rc": "20261030000446", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "다", "pos": "",
                                     "role": None, "q": 1}]})
    for i, s in enumerate(x for x in cur["data"]["stocks"] if x["cls"] == "us"):
        if i % 3 == 0:
            s["xd"] = "2026-11-24"
        if i % 4 == 0:
            s["ed"] = "2027-01-26"
    return cur, prev, final


def rows_of(cur, today=dt.date(2026, 10, 31)):
    rep = V.Report()
    by = {s.get("t"): s for s in cur["data"].get("stocks", []) if isinstance(s, dict)} if isinstance(cur["data"], dict) else {}
    V.check_v196b(rep, cur["data"], cur["disc"], by, today)
    return {r[0]: r for r in rep.rows}, rep


def status(cur, name):
    return rows_of(cur)[0][name][3]


def test_gate_rows_pass_on_good_files():
    got, rep = rows_of(good_files()[0])
    assert [got[n][3] for n in (ISSUE_ROW, ROLE_ROW, US_ROW)] == ["PASS", "PASS", "PASS"], rep.table()
    assert got[ISSUE_ROW][1].startswith("유상증자 1 · CB 1 · BW 1 (정정 2 · 숫자 없는 줄 0)")
    assert got[ROLE_ROW][1] == "임원 1 · 주요주주 1 · 없음 1 / 3줄"


def test_gate_rows_only_warn_on_files_from_before_v196b():
    """머지 직후 배포(--live)와 감시가 보는 사이트 파일에는 새 칸이 없어요 — 경고만 (실패면 배포가 막혀요)."""
    cur, _, _ = good_pair()
    cur["disc"]["insider"] = [{"rc": "20261030000444", "d": "20261030", "t": "005930", "pos": "-", "q": 1}]
    got, _ = rows_of(cur)
    assert [got[n][3] for n in (ISSUE_ROW, ROLE_ROW, US_ROW)] == ["WARN", "WARN", "WARN"]
    assert "role 칸이 없는 줄 1" in got[ROLE_ROW][1] and "직위가 '-' 인 줄 1" in got[ROLE_ROW][1]


@pytest.mark.parametrize("mutate, word", [
    (lambda c: c["disc"].update(issueOk=False), "issueOk false"),
    (lambda c: c["disc"].update(issue=[]), "0건"),
    (lambda c: c["disc"]["issue"][0].update(p=3500.0), "3,000% 넘는 줄 1개"),
    (lambda c: c["disc"]["issue"].append(dict(c["disc"]["issue"][1], rc="20261028000555", t="999990", p=None, amt=None, bd=None)),
     "오늘 국내 목록에 없는 종목 1곳 (999990)"),
    (lambda c: [r.update(n=None, p=None, amt=None) for r in c["disc"]["issue"][:1]], "숫자가 하나도 없는 줄 1 / 3"),
])
def test_gate_issue_row_warns_but_never_blocks(mutate, word):
    cur = good_files()[0]
    mutate(cur)
    got, _ = rows_of(cur)
    assert got[ISSUE_ROW][3] == "WARN" and word in got[ISSUE_ROW][1], got[ISSUE_ROW]


BAD_ISSUE = [
    ("rc", "2026103000011"), ("rc", 20261030000111), ("rc", "20991030000111"), ("rc", None),
    ("d", "2026-10-30"), ("d", "20261131"), ("d", "20261101"), ("d", "20260801"), ("d", 20261030), ("d", "２０２６１０３０"),
    ("t", ""), ("t", 5930), ("nk", None), ("kind", "eb"), ("kind", ["rights"]),
    ("bd", "2026-10-29"), ("bd", "20261399"), ("how", "holder"), ("how", True), ("n", 0), ("n", -5), ("n", 1.5), ("n", True), ("n", "5"),
    ("p", 0), ("p", -1.0), ("p", "3.11"), ("p", float("nan")), ("p", float("inf")), ("p", {}), ("cor", "true"), ("cor", None), ("cor", 1),
]


@pytest.mark.parametrize("key, val", BAD_ISSUE)
def test_gate_issue_row_fails_on_a_malformed_value(key, val):
    cur = good_files()[0]
    cur["disc"]["issue"][0][key] = val                        # 0번 줄은 유상증자
    got, rep = rows_of(cur)
    assert got[ISSUE_ROW][3] == "FAIL", (key, val, got[ISSUE_ROW])
    assert any(t == "주요사항 공시 (issue) 모양이 틀린 줄" for t, _ in rep.details)


@pytest.mark.parametrize("row, key, val", [(0, "amt", 5), (1, "how", "others"), (1, "n", 100), (1, "amt", 0), (1, "amt", "1,000")])
def test_gate_issue_row_fails_on_fields_of_the_wrong_kind(row, key, val):
    cur = good_files()[0]
    cur["disc"]["issue"][row][key] = val
    assert status(cur, ISSUE_ROW) == "FAIL"


@pytest.mark.parametrize("mutate", [
    lambda c: c["disc"]["issue"].append(dict(c["disc"]["issue"][0])),          # 같은 접수번호 두 번
    lambda c: c["disc"].update(issue={"a": 1}),
    lambda c: c["disc"].update(issue=None),
    lambda c: c["disc"].update(issueOk="yes"),
    lambda c: c["disc"].pop("issueOk"),
    lambda c: c["disc"]["issue"].append("20261030000999"),
    lambda c: c["disc"]["issue"][0].pop("cor"),
])
def test_gate_issue_row_fails_on_a_broken_list(mutate):
    cur = good_files()[0]
    mutate(cur)
    assert status(cur, ISSUE_ROW) == "FAIL"


def test_gate_issue_window_follows_the_file_date_not_the_gate_day():
    """감시(--live)는 발행이 멈춘 뒤 며칠 지나 볼 수 있어요: 기간은 disc.json asOf 로 셉니다."""
    cur = good_files()[0]
    rep = V.Report()
    V.check_v196b(rep, cur["data"], cur["disc"], {s["t"]: s for s in cur["data"]["stocks"]}, dt.date(2027, 3, 1))
    assert {r[0]: r[3] for r in rep.rows}[ISSUE_ROW] == "PASS"


@pytest.mark.parametrize("mutate", [
    lambda c: c["disc"]["insider"][0].update(role="임원 "),
    lambda c: c["disc"]["insider"][0].update(role="officer"),
    lambda c: c["disc"]["insider"][0].update(role=["임원"]),
    lambda c: c["disc"]["insider"][0].update(role=1),
    lambda c: c["disc"]["insider"].append([1, 2]),
    lambda c: c["disc"].update(insider={"x": 1}),
    lambda c: c["disc"].pop("insider"),
])
def test_gate_role_row_fails_on_a_wrong_value(mutate):
    cur = good_files()[0]
    mutate(cur)
    assert status(cur, ROLE_ROW) == "FAIL"


@pytest.mark.parametrize("key, val", [("ed", "2027/01/26"), ("ed", "2027-02-30"), ("xd", 1796083200), ("xd", True), ("ed", ["2027-01-26"]),
                                      ("xd", {"d": 1}), ("ed", "2027-01-26T00:00")])
def test_gate_us_dates_fail_on_a_malformed_value(key, val):
    cur = good_files()[0]
    next(s for s in cur["data"]["stocks"] if s["cls"] == "us")[key] = val
    assert status(cur, US_ROW) == "FAIL"


def test_gate_us_dates_belong_to_us_stocks_only_and_far_dates_warn():
    cur = good_files()[0]
    next(s for s in cur["data"]["stocks"] if s["t"] == "005930")["xd"] = "2026-12-30"
    assert status(cur, US_ROW) == "FAIL"
    cur = good_files()[0]
    next(s for s in cur["data"]["stocks"] if s["cls"] == "us")["ed"] = "2028-06-01"
    got, _ = rows_of(cur)
    assert got[US_ROW][3] == "WARN" and "400일 넘게 뒤 1개" in got[US_ROW][1]
    cur = good_files()[0]
    for s in cur["data"]["stocks"]:
        s.pop("ed", None)
    got, _ = rows_of(cur)
    assert got[US_ROW][3] == "WARN" and "실적 발표일이 하나도 없음" in got[US_ROW][1]
    cur = good_files()[0]
    next(s for s in cur["data"]["stocks"] if s["cls"] == "us")["ed"] = ""          # 빈 글자 = 빈 칸
    assert status(cur, US_ROW) == "PASS"


JUNK = [None, True, 0, -1, 1.5, float("nan"), float("inf"), "", "x", "-", "20261030", [], [None], {}, {"a": None}, [[[]]], {"rc": {}}]


def test_gate_never_crashes_on_any_value():
    """관문이 멈추면 발행이 막혀요 — 어디에 무슨 값이 와도 세 줄은 늘 나와요 (틀리면 실패 줄로)."""
    rnd = random.Random(196)
    base = good_files()[0]
    paths = [("disc",), ("disc", "issue"), ("disc", "issueOk"), ("disc", "insider"), ("disc", "asOf"), ("data",), ("data", "stocks"),
             ("data", "asOf")]
    for i in range(400):
        cur = copy.deepcopy(base)
        for _ in range(rnd.randint(1, 4)):
            pick = rnd.random()
            disc = cur["disc"] if isinstance(cur["disc"], dict) else {}
            if pick < 0.35:
                r = rnd.choice(disc["issue"]) if isinstance(disc.get("issue"), list) and disc["issue"] else None
                if isinstance(r, dict):
                    r[rnd.choice(SPEC_KEYS + ["zz"])] = rnd.choice(JUNK)
            elif pick < 0.55:
                ins = disc.get("insider")
                if isinstance(ins, list) and ins and isinstance(ins[0], dict):
                    ins[rnd.randrange(len(ins))][rnd.choice(["role", "pos", "rc"])] = rnd.choice(JUNK)
            elif pick < 0.75:
                us = [s for s in cur["data"].get("stocks", []) if isinstance(s, dict)][:900] if isinstance(cur["data"], dict) else []
                if us:
                    rnd.choice(us)[rnd.choice(["ed", "xd", "cls", "t"])] = rnd.choice(JUNK)
            else:
                path = rnd.choice(paths)
                if len(path) == 1:
                    cur[path[0]] = rnd.choice(JUNK)
                elif isinstance(cur[path[0]], dict):
                    cur[path[0]][path[1]] = rnd.choice(JUNK)
        rep = V.Report()
        data = cur["data"]
        by = {s.get("t"): s for s in data.get("stocks", []) if isinstance(s, dict) and isinstance(s.get("t"), str)} \
            if isinstance(data, dict) and isinstance(data.get("stocks"), list) else {}
        V.check_v196b(rep, data, cur["disc"], by, dt.date(2026, 10, 31))
        names = [r[0] for r in rep.rows]
        assert names == [ISSUE_ROW, ROLE_ROW, US_ROW], (i, names)
        assert not any("검사가 오류로 멈췄어요" in r[1] for r in rep.rows), (i, rep.table())


def test_a_crash_inside_a_check_is_a_failed_row_not_a_stopped_gate(monkeypatch):
    def boom(*a, **k):
        raise KeyError("x")
    monkeypatch.setattr(V, "_check_issue", boom)
    got, _ = rows_of(good_files()[0])
    assert got[ISSUE_ROW][3] == "FAIL" and "검사가 오류로 멈췄어요: KeyError" in got[ISSUE_ROW][1]
    assert got[ROLE_ROW][3] == "PASS" and got[US_ROW][3] == "PASS"


def test_run_checks_has_the_three_rows_and_they_add_no_failure():
    from test_validate import check
    cur, prev, final = good_files()
    rep = check(cur, prev, final)
    names = [r[0] for r in rep.rows]
    assert {ISSUE_ROW, ROLE_ROW, US_ROW} <= set(names)
    assert not {ISSUE_ROW, ROLE_ROW, US_ROW} & {r[0] for r in rep.failed}, rep.table()
    rep = check(*good_pair())                                   # 예전 모양 (새 칸 없음): 새 줄은 경고만
    assert not {ISSUE_ROW, ROLE_ROW, US_ROW} & {r[0] for r in rep.failed}
    assert {ISSUE_ROW, US_ROW} <= {r[0] for r in rep.warned}


def test_real_published_first_run_rows_pass_the_gate(env):
    """고정 자료로 만든 진짜 줄(fetch_issues 출력)이 관문을 통과해요 (같은 날 asOf · 오늘 국내 목록에 그 종목들)."""
    out, _, _ = env()
    disc = {"asOf": TODAY.isoformat(), **out, "insider": []}
    data = {"asOf": TODAY.isoformat(), "stocks": [dict(s) for s in KR]}
    rep = V.Report()
    V.check_v196b(rep, data, disc, {s["t"]: s for s in data["stocks"]}, TODAY)
    row = {r[0]: r for r in rep.rows}[ISSUE_ROW]
    assert row[3] == "PASS" and row[1].startswith("유상증자 8 · CB 13 · BW 1 (정정 18 · 숫자 없는 줄 2)"), row
    assert math.isclose(100.0 * 2 / len(WANT), 9.09, abs_tol=0.01)          # 2 / 22 = 9.1% < 10% (경고 아님)
