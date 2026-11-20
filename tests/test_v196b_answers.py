# -*- coding: utf-8 -*-
"""v19.6b 데이터 · Jack 의 답 (2026-11-19, 그대로): "7. a) Include 유무상증자, marked as such. b) Same-class basis: new shares against
existing shares of the same kind (20.58% for 육일씨엔에쓰). c) "임원·주요주주". d) Yes."

a) 유무상증자 결정(pifricDecsn)도 줄로 — kind rights + bonus: true · n · p · how 는 유상 몫(piic_) · bd 는 상세 API 의 fric_bddd.
b) 유상증자의 n · p 는 같은 종류끼리 (cls common | other · 보통주와 기타주식을 함께 내면 n2 · p2).
c) 임원이면서 주요주주인 사람의 role 은 '임원·주요주주'.

고정 자료: tests/fixtures/v196b/detail_pifric_290650.json (엘앤씨바이오) · detail_pifric_220100.json (퓨쳐켐) — 2026-11-19 의 진짜
pifricDecsn 응답 (키 없음). 육일씨엔에쓰 · 대양금속 · 뷰노의 숫자는 2026-11-15 의 진짜 piicDecsn 줄. 네트워크 없음."""
import copy
import datetime as dt
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_v196b_data as T  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "v196b")
TODAY = T.TODAY


def fx(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


def pifric(t, rc):
    return next(r for r in fx(f"detail_pifric_{t}.json")["list"] if r["rcept_no"] == rc)


def gate_rows(disc, stocks):
    data = {"asOf": TODAY.isoformat(), "stocks": stocks}
    rep = V.Report()
    V.check_v196b(rep, data, disc, {s["t"]: s for s in stocks}, TODAY)
    V.check_issue_bd(rep, disc)
    return {r[0]: r for r in rep.rows}, rep


# ── b) 같은 종류끼리 n · p ────────────────────────────────────────────────

def test_the_spec_example_six_one_cns_is_20_58_percent():
    """육일씨엔에쓰 2026-08-26: 새 보통주 2,305,918 ÷ 증자 전 보통주 11,204,255 = 20.58% (모든 주식으로 나누면 17.26%)."""
    d, bad = F.parse_issue_detail(T.api_row("rights", "191410", "20260826000431"), "rights")
    assert (d["cls"], d["n"], d["p"], bad) == ("common", 2305918, 20.58, [])
    assert "n2" not in d                                                     # 기타주식은 내지 않았어요 (증자 전 기타주식 2,153,446 은 있어요)


def test_other_shares_only_are_divided_by_other_shares():
    # 대양금속 2015-12-28 (진짜 줄): 새 기타주식 12,750,000 ÷ 증자 전 기타주식 1,200,000 = 1,062.5%
    row = {"nstk_ostk_cnt": "-", "nstk_estk_cnt": "12,750,000", "bfic_tisstk_ostk": "12,317,933", "bfic_tisstk_estk": "1,200,000",
           "ic_mthn": "제3자배정증자"}
    d, bad = F.parse_issue_detail(row, "rights")
    assert (d["cls"], d["n"], d["p"], bad) == ("other", 12750000, 1062.5, [])
    # 뷰노 2023-01-31 (진짜 줄): 처음 내는 기타주식 1,690,042 — 증자 전 기타주식이 없어 비율은 null (못 읽은 것은 아니에요)
    row = {"nstk_ostk_cnt": "-", "nstk_estk_cnt": "1,690,042", "bfic_tisstk_ostk": "11,379,656", "bfic_tisstk_estk": "-",
           "ic_mthn": "제3자배정증자"}
    d, bad = F.parse_issue_detail(row, "rights")
    assert (d["cls"], d["n"], d["p"], bad) == ("other", 1690042, None, [])


def test_common_and_other_together_give_n2_and_p2():
    row = {"nstk_ostk_cnt": "1,000,000", "nstk_estk_cnt": "500,000", "bfic_tisstk_ostk": "10,000,000", "bfic_tisstk_estk": "2,000,000",
           "ic_mthn": "주주배정증자"}
    d, bad = F.parse_issue_detail(row, "rights")
    assert (d["cls"], d["n"], d["p"], d["n2"], d["p2"], bad) == ("common", 1000000, 10.0, 500000, 25.0, [])
    row["bfic_tisstk_estk"] = "-"                                            # 증자 전 기타주식 0 → p2 null
    d, _ = F.parse_issue_detail(row, "rights")
    assert (d["n2"], d["p2"]) == (500000, None)
    row["bfic_tisstk_estk"] = "약 2백만"                                     # 읽지 못함 → p2 null · 못 읽은 칸으로 세요
    d, bad = F.parse_issue_detail(row, "rights")
    assert d["p2"] is None and bad == ["p2"]


@pytest.mark.parametrize("ostk, estk, want", [
    ("1.5", "-", (None, None, None, ["n", "p"])),          # 소수 → 읽지 못함 (셋 다 null)
    ("-", "-", (None, None, None, ["n", "p"])),            # 둘 다 없음
    ("0", "0", (None, None, None, ["n", "p"])),
    ("abc", "100", (None, None, None, ["n", "p"])),
    ("-1,000", "-", (None, None, None, ["n", "p"])),
])
def test_unreadable_counts_stay_null(ostk, estk, want):
    d, bad = F.parse_issue_detail({"nstk_ostk_cnt": ostk, "nstk_estk_cnt": estk, "bfic_tisstk_ostk": "1,000", "bfic_tisstk_estk": "-"},
                                  "rights")
    assert (d["cls"], d["n"], d["p"], bad) == want


def test_real_rows_from_fetch_issues_use_the_same_class(tmp_path, monkeypatch):
    out, _, _ = run(tmp_path, monkeypatch)
    r = {x["rc"]: x for x in out["issue"]}
    assert (r["20260826000431"]["cls"], r["20260826000431"]["n"], r["20260826000431"]["p"]) == ("common", 2305918, 20.58)
    assert all(x["cls"] in ("common", None) for x in out["issue"] if x["kind"] == "rights")
    assert all("cls" not in x for x in out["issue"] if x["kind"] != "rights")
    assert all(x["cls"] is None for x in out["issue"] if x["kind"] == "rights" and (x.get("wd") or x.get("pend")))


# ── a) 유무상증자 ─────────────────────────────────────────────────────────

def test_rights_plus_bonus_reads_the_paid_part_and_its_board_date():
    # 엘앤씨바이오 2026-10-12 정정: 유상 몫 보통주 3,700,000 ÷ 26,969,704 = 13.72% · 주주배정후 실권주 일반공모 · 이사회결의일 2026-07-31
    d, bad = F.parse_issue_detail(pifric("290650", "20261012000188"), "pifric")
    assert (d["bd"], d["how"], d["cls"], d["n"], d["p"], d["amt"], d["blank"], bad) == \
        ("20260731", "holders", "common", 3700000, 13.72, None, False, [])
    # 퓨쳐켐 2026-09-01: 보통주 3,389,830 ÷ 보통주 22,427,420 = 15.11% (기타주식 53,485 는 나누지 않아요 — 7b) · 결의일 2026-05-29
    d, bad = F.parse_issue_detail(pifric("220100", "20260901000041"), "pifric")
    assert (d["bd"], d["cls"], d["n"], d["p"], bad) == ("20260529", "common", 3389830, 15.11, [])
    assert F.issue_kind("[기재정정]주요사항보고서(유무상증자결정)") == ("pifric", True, False)
    assert F.ISSUE_EP["pifric"] == "pifricDecsn.json" and F.ISSUE_KO["pifric"] == "유무상증자"


def test_a_withdrawn_rights_plus_bonus_is_marked_like_a_rights_issue():
    row = dict(pifric("290650", "20261012000188"))
    for k in F.ISSUE_WD_KEYS["pifric"]:
        row[k] = "-"
    d, bad = F.parse_issue_detail(row, "pifric")
    assert d["blank"] is True and d["n"] is None and bad == ["n", "p"]
    f = {"rc": "20261012000188", "d": "20261012", "corp": "01181515", "t": "290650", "kind": "pifric", "cor": True, "att": False,
         "sup": False}
    rows = F.issue_rows([f], {f["rc"]: ("000", d)}, {"290650": {"nk": "엘앤씨바이오"}})
    assert rows == [{"rc": "20261012000188", "d": "20261012", "t": "290650", "nk": "엘앤씨바이오", "kind": "rights", "bd": None, "how": None,
                     "n": None, "p": None, "amt": None, "cor": True, "cls": None, "bonus": True, "wd": True}]


def run(tmp_path, monkeypatch, extra=True):
    """fetch_issues 를 test_v196b_data 의 고정 자료 + 엘앤씨바이오(유무상증자)로 돌려요 (가짜 DART · 네트워크 없음)."""
    monkeypatch.setattr(F, "OUT_DISC", str(tmp_path / "disc.json"))
    if extra:
        monkeypatch.setitem(T.EP_KIND, "pifricDecsn.json", "pifric")
        monkeypatch.setitem(T.CORP, "290650", "01181515")
    kr = T.KR + ([{"t": "290650", "nk": "엘앤씨바이오", "cls": "kr", "price": 1000.0}] if extra else [])
    c = F.DartClient("k", mode="cache", today=TODAY, path=str(tmp_path / "c.json.gz"))
    d = T.Dart(c)
    c.get = d
    return F.fetch_issues(kr, T.CORP, TODAY, c), d, c


def test_fetch_issues_includes_rights_plus_bonus_marked_as_such(tmp_path, monkeypatch, capsys):
    out, d, c = run(tmp_path, monkeypatch)
    rows = {r["rc"]: r for r in out["issue"]}
    r = rows["20261012000188"]
    assert r == {"rc": "20261012000188", "d": "20261012", "t": "290650", "nk": "엘앤씨바이오", "kind": "rights", "bd": "20260731",
                 "how": "holders", "n": 3700000, "p": 13.72, "amt": None, "cor": True, "cls": "common", "bonus": True}
    assert ("pifric", "290650") in d.detail_calls()
    assert sum(1 for x in out["issue"] if x.get("bonus")) == 1 and len(out["issue"]) == len(T.WANT) + 1
    assert c.entries["20261012000188|issue|v4"]["st"] == "000" and F.ISSUE_TAG == "issue|v4"
    log = capsys.readouterr().out
    assert "주요사항 공시: 유상증자 12 · CB 14 · BW 1 (정정 22), 숫자 못 읽음 0" in log and "유무상증자(bonus) 1" in log
    assert "목록 밖 회사 1" in log                                           # 엘앤씨바이오가 이제 목록 안
    # 결의일: 유무상증자는 상세 API 의 날 (원문을 읽지 않아요) — 같은 기간 확인
    disc = {"asOf": TODAY.isoformat(), **out, "insider": []}
    asked = []
    c.get_zip = lambda e, p, timeout=40: asked.append(p["rcept_no"]) or {f"{p['rcept_no']}.xml": T_doc(rows[p["rcept_no"]]["d"])}
    res = F.fill_issue_bd(disc, c, TODAY)
    assert "20261012000188" not in asked and r["bd"] == "20260731" and res["api"] == 1
    assert "유무상증자 상세 API 1" in capsys.readouterr().out
    got, rep = gate_rows(disc, [dict(s) for s in T.KR] + [{"t": "290650", "nk": "엘앤씨바이오", "cls": "kr", "price": 1000.0}])
    assert got[T.ISSUE_ROW][3] == "PASS" and "유무상증자 1" in got[T.ISSUE_ROW][1], rep.table()
    assert got[V.ISSUE_BD_ROW][3] == "PASS" and got[V.ISSUE_BD_ROW][1] == "결의일 있음 9 / 대상 9", rep.table()


def T_doc(day8):
    """결의일이 day8 인 작은 유상증자결정 원문 (test_v196b_issue_bd 의 고정 자료 모양)."""
    import test_v196b_issue_bd as B
    return B.doc_on(day8)


@pytest.mark.parametrize("api_bd, want_bd, limited, read_doc", [
    ("20260731", "20260731", 0, False),
    ("20230731", None, 1, False),           # 1년 넘게 앞 (Jack 7d) — 비우고 '기간 밖이라 비움'
    ("20261013", "20261013", 0, False),     # 공시일 뒤 — 여기서는 쓰고, 쓰기 앞의 own_check_disc 가 비워요 (Jack 의 상시 규칙 · test_v196b_own_rule)
    (None, "20261001", 0, True),            # 상세 API 에 결의일이 없으면 원문을 읽어요
])
def test_rights_plus_bonus_board_date_window(api_bd, want_bd, limited, read_doc):
    import test_v196b_issue_bd as B
    row = B.irow("20261012000188", "20261012", bd=api_bd, bonus=True, cls="common")
    c = B.Client({"20261012000188": B.doc_on("20261001")})
    out = F.fill_issue_bd(B.disc_of([row]), c, TODAY)
    assert row["bd"] == want_bd and out["limited"] == limited and (c.calls == ["20261012000188"]) == read_doc


# ── 관문: 새 칸의 모양 (새 검사 · 실패) ─────────────────────────────────────

def good_row(**kw):
    r = {"rc": "20261030000111", "d": "20261030", "t": "005930", "nk": "삼성전자", "kind": "rights", "bd": None, "how": "others",
         "n": 1000, "p": 2.0, "amt": None, "cor": False, "cls": "common"}
    r.update(kw)
    return r


BASE = dt.date(2026, 10, 31)


@pytest.mark.parametrize("row", [
    good_row(), good_row(cls="other"), good_row(cls="other", p=None), good_row(n2=500, p2=25.0), good_row(n2=500, p2=None),
    good_row(bonus=True), good_row(bonus=True, bd="20261029"), good_row(n=None, p=None, cls=None),
    good_row(n=None, p=None, how=None, cls=None, wd=True, cor=True), good_row(n=None, p=None, how=None, cls=None, pend=True),
    {"rc": "20261029000222", "d": "20261029", "t": "000660", "nk": "SK하이닉스", "kind": "cb", "bd": "20261029", "how": None, "n": None,
     "p": 3.11, "amt": 1000000000, "cor": False},
])
def test_gate_accepts_the_new_fields(row):
    assert V.issue_row_problems(row, BASE) == []


@pytest.mark.parametrize("row, word", [
    (good_row(cls="preferred"), "cls"), (good_row(cls=1), "cls"), (good_row(cls=None), "n 이 있는데 cls 가 없어요"),
    ({k: v for k, v in good_row().items() if k != "cls"}, "n 이 있는데 cls 가 없어요"),
    (good_row(n2=500, p2=25.0, cls="other"), "n2"), (good_row(n2=0, p2=None), "n2"), (good_row(n2=1.5, p2=None), "n2"),
    (good_row(n2=500, p2=0), "p2"), (good_row(n2=500, p2="25"), "p2"), (good_row(p2=3.0), "n2"),
    (good_row(bonus=False), "bonus"), (good_row(bonus="true"), "bonus"),
    ({"rc": "20261029000222", "d": "20261029", "t": "000660", "nk": "SK하이닉스", "kind": "cb", "bd": "20261029", "how": None, "n": None,
      "p": 3.11, "amt": 1000000000, "cor": False, "bonus": True}, "bonus"),
    ({"rc": "20261029000222", "d": "20261029", "t": "000660", "nk": "SK하이닉스", "kind": "cb", "bd": "20261029", "how": None, "n": None,
      "p": 3.11, "amt": 1000000000, "cor": False, "cls": "common"}, "cls"),
    (good_row(n=None, p=None, how=None, cls="common", wd=True, cor=True), "wd 인데 cls"),
    (good_row(n=None, p=None, how=None, cls=None, pend=True, n2=5, p2=1.0), "pend 인데 n2,p2"),
])
def test_gate_fails_a_malformed_new_field(row, word):
    probs = V.issue_row_problems(row, BASE)
    assert probs and any(word in p for p in probs), probs


# ── c) 임원·주요주주 ──────────────────────────────────────────────────────

def test_an_officer_who_is_also_a_major_holder_gets_the_exact_both_role():
    assert F.INSIDER_BOTH == "임원·주요주주" == "임원·주요주주"   # 가운뎃점 U+00B7 · 띄어쓰기 없음
    r = {"isu_exctv_rgist_at": "비등기임원", "isu_exctv_ofcps": "상무", "isu_main_shrholdr": "10%이상주주"}
    assert F.insider_pos_role(r) == ("상무", "임원·주요주주")
    assert F.insider_pos_role(dict(r, isu_exctv_ofcps="-")) == ("10%이상주주", "임원·주요주주")   # 등기 · 비등기임원 표시만 있어도 임원 (직위가 없으면 관계 말)
    assert F.insider_pos_role(dict(r, isu_main_shrholdr="-")) == ("상무", "임원")
    assert F.insider_pos_role(dict(r, isu_exctv_ofcps="-", isu_exctv_rgist_at="-")) == ("10%이상주주", "주요주주")
    both = [x for x in T.ELE if x["isu_exctv_ofcps"] != "-" and x["isu_main_shrholdr"] != "-"]
    assert len(both) == 3 and {F.insider_pos_role(x)[1] for x in both} == {"임원·주요주주"}    # 고정 자료에 든 삼성전자의 진짜 행 3개 (11-15 전체 8개 중)


def test_fix_roles_keeps_the_both_role_and_the_gate_accepts_only_the_exact_text():
    rows = [{"rc": "20261030000444", "pos": "상무", "role": "임원·주요주주"}, {"rc": "20261030000445", "pos": "상무", "role": "임원 · 주요주주"}]
    F.insider_fix_roles(rows, {})
    assert [r["role"] for r in rows] == ["임원·주요주주", None]                 # 다른 모양은 모르는 것 (짐작하지 않아요)
    cur = T.good_files()[0]
    cur["disc"]["insider"].append({"rc": "20261030000447", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "라", "pos": "상무",
                                   "role": "임원·주요주주", "q": 3})
    got, _ = T.rows_of(cur)
    assert got[T.ROLE_ROW][3] == "PASS" and got[T.ROLE_ROW][1] == "임원 1 · 주요주주 1 · 임원·주요주주 1 · 없음 1 / 4줄"
    for bad in ("임원 · 주요주주", "임원/주요주주", "임원·주요주주 ", "주요주주·임원"):
        cur["disc"]["insider"][-1]["role"] = bad
        assert T.rows_of(cur)[0][T.ROLE_ROW][3] == "FAIL", bad


def test_the_role_field_is_not_read_by_either_app_yet():
    """insider 의 role 은 아직 어느 화면도 읽지 않아요 (B.2 카드가 읽어요) — 그래서 이 PR 의 「새 문구」에는 화면 글자가 없어요. ('임원·주요주주'
    라는 말 자체는 이미 승인된 공시 탭 · 내부자 거래 제목에 있어요 — role 과 상관없어요.) 소개 페이지의 m.role (만든 사람의 역할)만 있어요."""
    import re
    hits = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "src")):
        for name in files:
            if name.endswith((".js", ".jsx")):
                with open(os.path.join(base, name), encoding="utf-8") as f:
                    text = f.read()
                hits += [(name, m) for m in re.findall(r"[A-Za-z_$]+\.role\b|\[[\'\"]role[\'\"]\]", text)]
    assert hits == [("about.jsx", "m.role")], hits


def test_the_cache_tag_moved_so_old_rows_are_read_again(tmp_path, monkeypatch):
    """7b 는 n · p 를 바꿔요 — issue|v2 로 읽은 줄은 한 번 다시 읽어요 (지난 판의 키는 지워요)."""
    out, d, c = run(tmp_path, monkeypatch, extra=False)
    c.entries["20260826000431|issue|v2"] = {"st": "000", "at": "2026-11-15", "d": {"n": 4459364, "p": 33.4}}
    c.save()
    out2, d2, c2 = run(tmp_path, monkeypatch, extra=False)
    assert "20260826000431|issue|v2" not in c2.entries and d2.detail_calls() == []
    assert {r["rc"]: r["p"] for r in out2["issue"]}["20260826000431"] == 20.58


def test_rows_stay_json_clean():
    rows = [good_row(n2=500, p2=25.0, bonus=True)]
    json.dumps(copy.deepcopy(rows), allow_nan=False)


# ── 리뷰 2026-11-19 (0b5e1b8): 빈 비율의 이유 · 없는 칸은 0 이 아님 · p2 도 큰 비율 경고 ─────────────

@pytest.mark.parametrize("v, want", [(None, None), ("", None), ("  ", None), ("-", 0), ("－", 0), ("0", 0), ("1,000", 1000),
                                     ("1.5", None), ("-5", None), ("abc", None), (" 2,153,446 ", 2153446)])
def test_a_missing_or_blank_count_is_unreadable_not_zero(v, want):
    assert F._issue_count(v) == want


def test_a_missing_pre_issue_count_is_null_with_its_own_reason():
    # 기타주식만 낸 줄인데 '증자 전 기타주식' 칸이 없음 → p null · 이유 unread (예전: 칸이 없으면 0 으로 읽어 '없어서 비율 없음')
    row = {"nstk_ostk_cnt": "-", "nstk_estk_cnt": "1,690,042", "bfic_tisstk_ostk": "11,379,656", "ic_mthn": "제3자배정증자"}
    d, bad = F.parse_issue_detail(row, "rights")
    assert (d["cls"], d["n"], d["p"], d["pwhy"], bad) == ("other", 1690042, None, {"p": "unread"}, ["p"])
    row["bfic_tisstk_estk"] = "-"                                            # 진짜 0 (DART 의 '-') → 이유 zero · 못 읽은 것이 아님
    d, bad = F.parse_issue_detail(row, "rights")
    assert (d["p"], d["pwhy"], bad) == (None, {"p": "zero"}, [])
    row["bfic_tisstk_estk"] = ""                                             # 빈 글자도 읽지 못한 것
    assert F.parse_issue_detail(row, "rights")[0]["pwhy"] == {"p": "unread"}
    # 새 주식 수 칸이 없으면 0 이 아니라 읽지 못함 (셋 다 null)
    d, bad = F.parse_issue_detail({"nstk_ostk_cnt": "1,000", "bfic_tisstk_ostk": "10,000", "bfic_tisstk_estk": "-"}, "rights")
    assert (d["cls"], d["n"], d["p"], bad) == (None, None, None, ["n", "p"])
    d, _ = F.parse_issue_detail(T.api_row("rights", "191410", "20260826000431"), "rights")
    assert "pwhy" not in d                                                   # 비율이 있으면 이유 칸도 없어요


def _with(row_kw):
    det = copy.deepcopy(T.detail("rights", "191410"))
    for r in det["list"]:
        if r["rcept_no"] == "20260826000431":
            r.update(row_kw)
    return det


def _run_with(tmp_path, monkeypatch, det):
    monkeypatch.setattr(F, "OUT_DISC", str(tmp_path / "disc.json"))
    c = F.DartClient("k", mode="cache", today=TODAY, path=str(tmp_path / "c.json.gz"))
    c.get = T.Dart(c, details={("rights", "191410"): det})
    return F.fetch_issues(T.KR, T.CORP, TODAY, c)


@pytest.mark.parametrize("before, zero, unread, loud", [("-", 1, 0, False), ("약 5만", 0, 1, True), (None, 0, 1, True)])
def test_a_null_p2_is_counted_and_logged_with_its_reason(tmp_path, monkeypatch, capsys, before, zero, unread, loud):
    kw = {"nstk_estk_cnt": "500,000", "bfic_tisstk_estk": before}
    det = _with({k: v for k, v in kw.items() if v is not None})
    if before is None:
        for r in det["list"]:
            if r["rcept_no"] == "20260826000431":
                del r["bfic_tisstk_estk"]                                    # 칸이 아예 없음
    out = _run_with(tmp_path, monkeypatch, det)
    r = {x["rc"]: x for x in out["issue"]}["20260826000431"]
    assert (r["cls"], r["n"], r["p"], r["n2"], r["p2"]) == ("common", 2305918, 20.58, 500000, None)
    log = capsys.readouterr().out
    assert (f"보통주와 기타주식을 함께 낸 유상증자 1 (n2 · p2 — p2 없음: 증자 전 기타주식이 없어 {zero} · 증자 전 기타주식 수를 읽지 못해 "
            f"{unread})") in log
    line = next(x for x in log.splitlines() if "주요사항 공시: 유상증자" in x)
    assert line.startswith("  !! ") == loud and (f"숫자 못 읽음 {unread}" in line)
    assert "pwhy" not in r                                                   # 이유는 캐시와 로그에만 (줄에는 싣지 않아요)


@pytest.mark.parametrize("before, zero, unread", [("-", 1, 0), ("abc", 0, 1)])
def test_an_other_only_row_names_why_its_ratio_is_blank(tmp_path, monkeypatch, capsys, before, zero, unread):
    det = _with({"nstk_ostk_cnt": "-", "nstk_estk_cnt": "2,305,918", "bfic_tisstk_estk": before})
    out = _run_with(tmp_path, monkeypatch, det)
    r = {x["rc"]: x for x in out["issue"]}["20260826000431"]
    assert (r["cls"], r["n"], r["p"]) == ("other", 2305918, None)
    log = capsys.readouterr().out
    assert (f"기타주식만 낸 유상증자 1 (비율 없음: 증자 전 기타주식이 없어 {zero} · 증자 전 기타주식 수를 읽지 못해 {unread})") in log
    assert f"숫자 못 읽음 {unread}" in log


def test_gate_warns_on_a_large_p2_too():
    cur = T.good_files()[0]
    cur["disc"]["issue"][0].update(n2=500, p2=3500.0)
    got, _ = T.rows_of(cur)
    assert got[T.ISSUE_ROW][3] == "WARN" and "3,000% 넘는 줄 1개 (삼성전자 3,500.00% (p2)" in got[T.ISSUE_ROW][1], got[T.ISSUE_ROW]
    cur["disc"]["issue"][0].update(p=3200.0)                                 # 한 줄에 둘 다 — 줄은 하나로 세요
    got, _ = T.rows_of(cur)
    assert "3,000% 넘는 줄 1개 (삼성전자 3,200.00% · 3,500.00% (p2)" in got[T.ISSUE_ROW][1]
    cur["disc"]["issue"][0].update(p=2.05, p2=25.0)
    assert T.rows_of(cur)[0][T.ISSUE_ROW][3] == "PASS"
