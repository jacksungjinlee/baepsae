# -*- coding: utf-8 -*-
"""소액주주 배당 (차등배당 · Jack 2026-11-19 Q6 "a later PR, labelled as the 소액주주 rate" · 2026-11-23): 파이프라인과 관문의 경고 줄.

What the filings say (fixtures: the real DART answers of 2026-11-23 · alot_*.json the alotMatter API rows, *_sec.xml the 2025
사업보고서's '6. 배당에 관한 사항' section, cut from document.xml):
- 교보증권 (030610): the API row says only 보통주 550; the note under the table says "기타주주(최대주주 외) 550원, 최대주주 무배당을 배당하는
  차등배당" -> won.
- TPC로보틱스 (048770): the API row says 10 (stock kind '-'); the note says 차등배당 for the "일반 및 소액주주 보유 주식 7,787,204주", and
  10원 × 7,787,204 = 77,872,040원 ≈ the table's total 78백만원 -> cnt.
- 엘앤씨바이오 (290650) · 블랙야크아이앤씨 (478560): totals that do not fit the share count either, but no word of 차등배당 -> nothing.
- 남성 (004270): API rows 보통주(소액주주) 25 and 보통주(최대주주) 25 — labelled, but the same amount (not differential); the existing parse
  keeps reading the first common row (25) as before. 대동기어 (008830): one 보통주 row, nothing differential.
Only a figure the filing itself ties to the small shareholders is used, and it is the table's own dividend per share: nothing is
computed but the yield (÷ today's close). dps · dyt · dz · dvLine stay as they were (the ranking keeps dyt).
"""
import collections
import copy
import datetime as dt
import io
import json
import os
import re
import sys
import threading
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F          # noqa: E402
import validate_data as V       # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "smallholder")
DOCS = {"030610": "20260317000550", "048770": "20260319000001", "290650": "20260324000006", "478560": "20260324000048"}


def sec_xml(t):
    with open(os.path.join(FIX, f"{t}_{DOCS[t]}_sec.xml"), encoding="utf-8") as f:
        return f.read()


def doc_text(t):
    """A whole-document stand-in: a notes section whose title also has 배당 (엘앤씨바이오's '26. 배당금과 배당성향') before the real section,
    and the next section (7. 증권의 발행 …) after it — the parser must take only the real one."""
    return ('<?xml version="1.0" encoding="utf-8"?><DOCUMENT><BODY>'
            '<SECTION-1><TITLE ATOC="Y">III. 재무에 관한 사항</TITLE><SECTION-2><TITLE ATOC="Y">26. 배당금과 배당성향</TITLE>'
            '<P>주당 배당금 999원 기타주주 999원 차등</P></SECTION-2></SECTION-1>'
            '<SECTION-1><TITLE ATOC="Y">I. 회사의 개요</TITLE>' + sec_xml(t)
            + '<SECTION-2><TITLE ATOC="Y">7. 증권의 발행을 통한 자금조달에 관한 사항</TITLE><P>기타주주 12,345원 소액주주 1,234,567주</P></SECTION-2>'
            '</SECTION-1></BODY></DOCUMENT>')


def alot(t):
    with open(os.path.join(FIX, f"alot_{t}_2025.json"), encoding="utf-8") as f:
        return json.load(f)["list"]


# ── what the filings say ───────────────────────────────────────────────────────────────────────────────────────
def test_the_api_rows_do_not_name_the_small_holders_for_kyobo_and_tpc_and_the_existing_parse_is_unchanged():
    for t, d in (("030610", 550), ("048770", 10), ("290650", 50), ("478560", 325), ("004270", 25), ("008830", 40)):
        assert F.parse_dart_dividend(alot(t))["dps"] == d
    kinds = {r["stock_knd"] for r in alot("030610") if "주당" in r["se"]}
    assert not any("소액" in k for k in kinds)
    nam = [(r["stock_knd"], r["thstrm"]) for r in alot("004270") if r["se"].replace(" ", "") == "주당현금배당금(원)"]
    assert nam == [("보통주(소액주주)", "25"), ("보통주(최대주주)", "25"), ("우선주", "-")]       # 남성: labelled, not differential


def test_the_section_is_the_dividend_section_only():
    for t in DOCS:
        sec = F.small_div_section(doc_text(t))
        assert sec and "주당" in sec and "999원" not in sec and "12,345원" not in sec and "<" not in sec
    assert F.small_div_section(None) is None and F.small_div_section("") is None
    assert F.small_div_section("<TITLE>26. 배당금과 배당성향</TITLE><P>주당 1원</P>") is None


def test_facts_and_pick_on_the_real_filings():
    k = F.small_div_facts(F.small_div_section(doc_text("030610")), 2025)
    assert k["c"] is True and k["won"] == [550] and k["cnt"] == []
    assert k["qw"] == ["주1) 당기(2025년 제81기) 결산 현금배당의 1주당 배당금은 기타주주(최대주주 외) 550원, 최대주주 무배당을 배당하는 차등배당입니다."]
    assert k["skip"].get("year") == 2                                     # "2020년 이후 … 차등배당" 같은 다른 해 문장은 근거로 쓰지 않아요
    assert F.small_div_pick(k, 550, 8977e6) == ("won", None) and F.small_div_quote(k, "won") == k["qw"][0]
    assert F.small_div_pick(k, 500, 8977e6) == (None, "nofig")          # 전기 500원은 소액주주 몫으로 적힌 숫자가 아니에요
    p = F.small_div_facts(F.small_div_section(doc_text("048770")), 2025)
    assert p["c"] is True and p["won"] == [] and p["cnt"] == [7787204]
    assert p["qc"][0].startswith("당기 회사는 총발행주식수 15,697,991주 중") and p["qc"][0].endswith("차등배당을 진행할 예정입니다.")
    assert F.small_div_pick(p, 10, 78e6) == ("cnt", None)                 # 10 × 7,787,204 = 77,872,040 ≈ 78백만원
    assert F.small_div_pick(p, 10, 157e6) == (None, "nofig")              # 전기 총액이면 맞지 않아요
    assert F.small_div_pick(p, 10, None) == (None, "nofig")
    for t, d, c in (("290650", 50, 1134e6), ("478560", 325, 2832e6)):
        f = F.small_div_facts(F.small_div_section(doc_text(t)), 2025)
        assert f["c"] is False and f["won"] == f["cnt"] == [] and F.small_div_pick(f, d, c) == (None, "nodiff")
    # the same notes in another fiscal year's report name a year that is not fy: not used
    assert F.small_div_facts(F.small_div_section(doc_text("030610")), 2026)["won"] == []


def test_the_table_header_does_not_leak_into_the_note():
    """TPC로보틱스's note is a paragraph right under the table whose header reads '당기 전기 전전기': the section keeps block ends as
    line breaks, so the note is its own sentence and the header's 전기 does not reject it."""
    sec = F.small_div_section(doc_text("048770"))
    line = next(x for x in sec.split("\n") if "차등배당을 진행" in x)
    assert line.startswith("당기 회사는") and "전기" not in line


# Crafted notes the first parser accepted (#183 review, Opus and Fable), each with the table's figure it would have labelled.
# (fy 2025)
CRAFTED = [
    ("neg", "당사는 차등배당을 실시하지 않으며, 소액주주와 최대주주 모두 1주당 200원을 배당합니다.", 200, None, "nodiff"),
    ("neg2", "차등배당을 실시하지 않았습니다. 소액주주에게도 동일하게 500원을 배당합니다.", 500, None, "nodiff"),
    ("neg3", "주1) 당기에는 차등 배당을 하지 않습니다. 기타주주 1주당 550원, 최대주주 1주당 550원입니다.", 550, None, "nodiff"),
    ("unexec", "차등배당 미실시: 소액주주 1주당 300원.", 300, None, "nodiff"),
    ("past", "전기는 소액주주 500원의 차등배당이었으나 당기는 모든 주주에게 500원을 배당합니다.", 500, None, "nodiff"),
    ("past2", "전기에는 차등배당을 하였으며, 당기 배당은 소액주주 500원입니다.", 500, None, "nodiff"),
    ("year", "2024년에는 소액주주 1주당 500원의 차등배당을 하였습니다.", 500, None, "nodiff"),
    ("class", "차등배당으로 기타주주 우선주 1주당 600원, 보통주 550원을 배당합니다.", 550, None, "nofig"),
    ("class2", "차등배당으로 기타주주에게 우선주 1주당 600원, 보통주 1주당 550원을 줍니다.", 600, None, "nofig"),
    ("holder", "소액주주 보호를 위해 최대주주는 주당 100원으로 하는 차등배당을 합니다.", 100, None, "nofig"),
    ("par", "차등배당을 하며 소액주주 1주당 배당금은 액면가 500원의 10%입니다.", 500, None, "nofig"),
    ("wrong", "최대주주 400원, 소액주주 500원의 차등배당을 실시합니다.", 400, None, "nofig"),
    ("vote", "차등의결권 주식은 없어요. 소액주주 1주당 300원을 배당합니다.", 300, None, "nodiff"),
    ("many", "차등배당으로 소액주주 300원, 일반주주 350원을 배당합니다.", 300, None, "many"),
    ("cntwrong", "최대주주 지분 5,000,000주를 뺀 소액주주 보유 주식 1,000,000주에 대하여 차등배당을 합니다.", 10, 50e6, "nofig"),
    ("cntmany", "차등배당 대상은 소액주주 보유 1,000,000주와 일반주주 보유 2,000,000주입니다.", 10, 30e6, "many"),
]
GOOD = [
    ("sentence", "당기 결산 배당은 소액주주 550원, 최대주주 무배당의 차등배당입니다.", 550, None, "won"),
    ("excl", "기타주주(최대주주 및 자기주식 외) 1주당 550원을 배당하는 차등배당입니다.", 550, None, "won"),
    ("note", "주1) 당기 배당은 차등배당입니다. 기타주주 1주당 550원, 최대주주 0원.", 550, None, "won"),
    ("fy", "주1) 2025년 결산 배당은 소액주주 550원의 차등배당입니다.", 550, None, "won"),
    ("order", "차등배당: 소액주주 500원, 최대주주 400원.", 500, None, "won"),
    ("cnt", "최대주주를 제외한 일반주주 보유 주식 1,000,000주에 대하여 차등배당을 합니다.", 10, 10e6, "cnt"),
    ("both", "차등배당으로 소액주주 1,000,000주와 일반주주 2,000,000주에 10원을 배당합니다.", 10, 30e6, "won"),   # 10원이 그 몫으로 적혀 있어요
]


@pytest.mark.parametrize("name,text,d0,cash,want", CRAFTED + GOOD, ids=[c[0] for c in CRAFTED + GOOD])
def test_crafted_notes(name, text, d0, cash, want):
    f = F.small_div_facts(text, 2025)
    how, why = F.small_div_pick(f, d0, cash)
    assert (how or why) == want, (name, f)
    if how:
        assert F.small_div_quote(f, how)                    # the sentence it relied on travels with the figure


def test_report_receipt_number():
    rows = [{"report_nm": "사업보고서 (2025.12)", "rcept_no": "20260317000550"},
            {"report_nm": "[기재정정]사업보고서 (2025.12)", "rcept_no": "20260401000123"},
            {"report_nm": "반기보고서 (2026.06)", "rcept_no": "20260814000001"},
            {"report_nm": "사업보고서 (2024.12)", "rcept_no": "20250318000001"},
            {"report_nm": "사업보고서 (2025.12)", "rcept_no": "2026"},
            {"report_nm": "사업보고서 (2025.03)", "rcept_no": "20250601000009"}]
    assert F.small_div_report_rc(rows, 2025) == "20260401000123"
    assert F.small_div_report_rc(rows, 2024) == "20250318000001"
    assert F.small_div_report_rc([{"report_nm": "사업보고서 (2026.03)", "rcept_no": "20260601000001"}], 2025) is None
    assert F.small_div_report_rc([{"report_nm": "사업보고서 (2025.03)", "rcept_no": "20250601000009"}], 2025) is None   # 3월 결산: 앞 사업연도
    assert F.small_div_report_rc(None, 2025) is None


# ── share basis ────────────────────────────────────────────────────────────────────────────────────────────────
STK = {"cmo": 112869363, "cmi": 113962961}


def test_basis():
    px = "2026-11-20"
    assert F.small_div_basis({}, 2025, px, STK, 113962961) is None
    assert F.small_div_basis({"oth": [{"k": "cb", "d": "2026-05-01", "rc": "x"}]}, 2025, px, STK, 113962961) is None
    assert F.small_div_basis({"oth": [{"k": "rights", "d": "2025-03-01", "rc": "x"}]}, 2025, px, STK, 113962961) is None   # 반년보다 앞
    assert F.small_div_basis({"oth": [{"k": "rights", "d": "2025-08-01", "rc": "x"}]}, 2025, px, STK, 113962961) == "blk"
    assert F.small_div_basis({"oth": [{"k": "merger", "d": None, "rc": "x"}]}, 2025, px, STK, 113962961) == "blk"       # 날짜 모름
    assert F.small_div_basis({"sd": [{"d": "2026-02-01"}]}, 2025, px, STK, 113962961) == "blk"
    assert F.small_div_basis({"oth": [{"k": "spin", "d": "2026-02-01", "rc": "x"}]}, 2025, px, STK, 113962961) == "blk"
    ev = {"ev": [{"k": "split", "d": "2026-03-01", "r": 5.0, "rc": "y"}]}
    assert F.small_div_basis(ev, 2025, px, STK, 113962961 * 5) == "ev"
    assert F.small_div_basis({}, 2025, px, None, 113962961) == "nostk"
    assert F.small_div_basis({}, 2025, px, {"cmo": 10, "cmi": 5}, 10) == "nostk"
    assert F.small_div_basis({}, 2025, px, STK, 112869363 * 0.96) == "shr"
    assert F.small_div_basis({}, 2025, px, STK, 113962961 * 1.04) == "shr"
    assert F.small_div_basis({}, 2025, px, STK, None) == "shr"


# ── reading the report (cache, limits, failures) ──────────────────────────────────────────────────────────────
def zip_of(t):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(DOCS[t] + ".xml", doc_text(t).encode("utf-8"))
    with zipfile.ZipFile(io.BytesIO(b.getvalue())) as z:
        return {n: z.read(n) for n in z.namelist()}


class FakeClient:
    def __init__(self, lists=None, zips=None, today=dt.date(2026, 11, 23)):
        self.lock = threading.Lock()
        self.entries, self.today = {}, today
        self.no_call = self.down = self.fatal = None
        self.status = collections.Counter()
        self.lists, self.zips, self.calls = lists or {}, zips or {}, []

    def get(self, ep, params):
        self.calls.append((ep, dict(params)))
        if self.no_call:
            return None
        j = self.lists.get(params.get("corp_code"))
        if j is not None:
            self.status[str(j.get("status"))] += 1
        return copy.deepcopy(j)

    def get_zip(self, ep, params):
        self.calls.append((ep, dict(params)))
        if self.no_call:
            return None
        z = self.zips.get(params.get("rcept_no"))
        if z is not None:
            self.status["000"] += 1
        return z


def list_ok(rc):
    return {"status": "000", "list": [{"report_nm": "사업보고서 (2025.12)", "rcept_no": rc}]}


def test_doc_reads_once_and_caches():
    c = FakeClient({"00113359": list_ok(DOCS["030610"])}, {DOCS["030610"]: zip_of("030610")})
    b = [2]
    d, how = F.small_div_doc(c, "00113359", 2025, b)
    assert how == "fetched" and d["won"] == [550] and d["c"] and d["rc"] == DOCS["030610"] and b == [1]
    lp = c.calls[0][1]
    assert c.calls[0][0] == "list.json" and lp["pblntf_detail_ty"] == "A001" and lp["bgn_de"] == "20260101" and lp["last_reprt_at"] == "Y"
    assert c.entries["00113359|2025|11011|sdiv2"]["st"] == "000"
    n = len(c.calls)
    d2, how2 = F.small_div_doc(c, "00113359", 2025, b)
    assert how2 == "cache" and d2 == d and len(c.calls) == n and b == [1]
    # 90 days later it reads again (a corrected report); if that fails, the facts found before stay
    c.today = dt.date(2027, 3, 1)
    c.lists = {}
    d3, how3 = F.small_div_doc(c, "00113359", 2025, b)
    assert how3 == "cache" and d3 == d and b == [0]
    d4, how4 = F.small_div_doc(c, "00113359", 2025, b)               # the limit reached: the cached facts, no call
    assert how4 == "cache" and d4 == d


def test_doc_not_found_and_failures():
    c = FakeClient({"A": {"status": "013"}, "B": {"status": "000", "list": [{"report_nm": "반기보고서 (2026.06)", "rcept_no": "20260814000001"}]},
                    "C": list_ok("20260317000999")}, {"20260317000999": {"20260317000999.xml": b"<DOCUMENT><P>no section</P></DOCUMENT>"}})
    b = [10]
    assert F.small_div_doc(c, "A", 2025, b)[1][0] == "nf" and c.entries["A|2025|11011|sdiv2"]["st"] == "013"
    assert F.small_div_doc(c, "B", 2025, b)[1][0] == "nf"
    assert F.small_div_doc(c, "C", 2025, b)[1][0] == "nf"
    n = len(c.calls)
    assert F.small_div_doc(c, "A", 2025, b)[1][0] == "nf" and len(c.calls) == n        # 7 days: not asked again
    assert F.small_div_doc(c, "D", 2025, b)[1][0] == "fail" and "D|2025|11011|sdiv2" not in c.entries   # no answer: not written
    assert F.small_div_doc(c, "E", 2025, [0]) == (None, ("fail", F.small_div_doc(c, "E", 2025, [0])[1][1]))
    c2 = FakeClient({"X": list_ok("20260317000550")}, {})
    assert F.small_div_doc(c2, "X", 2025, [5])[1][0] == "fail"                         # the document did not come
    c3 = FakeClient({"X": list_ok("20260317000550")}, {"20260317000550": zip_of("030610")})
    c3.no_call = "same day"
    b3 = [5]
    assert F.small_div_doc(c3, "X", 2025, b3)[1][0] == "wait" and b3 == [5] and c3.calls == []   # no call, no budget, not a failure
    c3.no_call, c3.down = None, "ConnectTimeout"
    assert F.small_div_doc(c3, "X", 2025, b3)[1][0] == "fail" and b3 == [5] and c3.calls == []


def test_doc_on_a_no_call_run_uses_the_cache_whatever_its_age():
    """#183 review: a run that may not call DART (same-day re-run) never spends the limit and never turns a known answer into 조회 실패."""
    c = FakeClient({"K": list_ok(DOCS["030610"]), "A": {"status": "013"}}, {DOCS["030610"]: zip_of("030610")})
    F.small_div_doc(c, "K", 2025, [5])
    F.small_div_doc(c, "A", 2025, [5])
    c.today = dt.date(2027, 6, 1)                     # both entries expired (000 after 90 days, 013 after 7)
    c.no_call = "same day"
    n, b = len(c.calls), [5]
    assert F.small_div_doc(c, "K", 2025, b)[1] == "cache" and F.small_div_doc(c, "A", 2025, b)[1][0] == "nf"
    assert b == [5] and len(c.calls) == n
    c.no_call = None
    assert F.small_div_doc(c, "A", 2025, [0])[1][0] == "nf"                  # the limit reached: an expired 'not found' stays 'not found'
    assert F.small_div_doc(c, "A", 2025, b)[1][0] == "nf" and b == [4]       # otherwise it is asked again (013 again)


def test_doc_reads_december_reports_only():
    c = FakeClient({"M": {"status": "000", "list": [{"report_nm": "사업보고서 (2025.03)", "rcept_no": "20250601000009"}]}}, {})
    got = F.small_div_doc(c, "M", 2025, [5])
    assert got[1][0] == "nf" and "12월 결산" in got[1][1] and not any(ep == "document.xml" for ep, _ in c.calls)


def test_section_end_is_found_without_the_character_cap(monkeypatch):
    """#183 review: the 60,000-character cap applies only when the section's end cannot be found."""
    monkeypatch.setattr(F, "SMALL_DIV_SEC_MAX", 200)
    sec = F.small_div_section(doc_text("030610"))
    assert sec and "기타주주(최대주주 외) 550원" in sec                       # far beyond 200 characters of markup, still read
    cut = F.small_div_section(doc_text("030610").replace("</SECTION-2>", ""))
    assert cut is None or "550원" not in cut


# ── the stage ─────────────────────────────────────────────────────────────────────────────────────────────────
class FakeWhy:
    def __init__(self, sub, looks, stks, cmap, on=True):
        self.prove_on = on
        self.psub = {"rights": {}, "data": sub}
        self.seen = {t: (lk, [None, None, None]) for t, lk in looks.items()}
        self.stks, self.cmap = stks, cmap

    def _stk(self, corp, fy):
        if corp == "BOOM":
            raise RuntimeError("boom")
        return (self.stks.get(corp), corp not in self.stks)


def kr_row(t, nk, price, d3, shr, **kw):
    s = {"t": t, "nk": nk, "cls": "kr", "price": price, "dps": d3[0], "dps3": list(d3), "dps3a": [None, None, None],
         "dpsF": [None, None, None], "divSt": "nd", "dvLine": 3, "fy": 2025, "shr": shr}
    s.update(kw)
    return s


def scene():
    kr = [kr_row("030610", "교보증권", 7500.0, [550.0, 500.0, 250.0], 113962961),
          kr_row("048770", "TPC로보틱스", 3045.0, [10.0, 10.0, 25.0], 15697991),
          kr_row("290650", "엘앤씨바이오", 20050.0, [50.0, 50.0, 100.0], 61107168),
          kr_row("478560", "블랙야크아이앤씨", 2970.0, [325.0, 320.0, 0.0], 25830298),
          kr_row("000480", "CR홀딩스", 5000.0, [210.0, 200.0, 200.0], 46890490),
          kr_row("005930", "삼성전자", 100000.0, [1446.0, 1444.0, 1416.0], 5919637922, dyt=1.45, dz=50, divSt="same", dvLine=None,
                 dpsSmall=1, dytSmall=9.0)]                                              # 지난 행에 남은 칸은 지워요
    cmap = {"030610": "K", "048770": "T", "290650": "L", "478560": "B", "000480": "CR", "005930": "S"}
    stks = {"K": STK, "T": {"cmo": 15697991, "cmi": 15697991}, "L": {"cmo": 24386610, "cmi": 24386610},
            "B": {"cmo": 25792139, "cmi": 25830298}, "CR": {"cmo": 41256552, "cmi": 46890490}}
    looks = {"030610": {}, "048770": {}, "290650": {"ev": [{"k": "bonus", "d": "2026-04-01", "r": 2.0, "rc": "q"}]},
             "478560": {}, "000480": {"oth": [{"k": "rights", "d": "2026-06-01", "rc": "r"}]}}
    why = FakeWhy({"030610": "div", "048770": "div", "290650": "div", "478560": "div", "000480": "div", "086900": "pref0"}, looks, stks, cmap)
    c = FakeClient({"K": list_ok(DOCS["030610"]), "T": list_ok(DOCS["048770"]), "B": list_ok(DOCS["478560"])},
                   {DOCS[t]: zip_of(t) for t in ("030610", "048770", "478560")})
    extra = {"030610": {"cash3": [89.77, 81.6, 40.8]}, "048770": {"cash3": [0.78, 1.57, 3.92]}, "478560": {"cash3": [28.32, 20.93, 0.0]}}
    return kr, why, c, extra


def test_stage_sets_the_two_fields_only_where_the_filing_says_so():
    kr, why, c, extra = scene()
    before = {s["t"]: {k: s.get(k) for k in ("dps", "dps3", "dps3a", "dyt", "dz", "dvLine", "divSt")} for s in kr}
    rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    by = {s["t"]: s for s in kr}
    assert (by["030610"]["dpsSmall"], by["030610"]["dytSmall"]) == (550, 7.33)          # 550 ÷ 7,500
    assert (by["048770"]["dpsSmall"], by["048770"]["dytSmall"]) == (10, 0.33)           # 10 ÷ 3,045
    for t in ("290650", "478560", "000480", "005930"):
        assert "dpsSmall" not in by[t] and "dytSmall" not in by[t]
    assert {s["t"]: {k: s.get(k) for k in before[s["t"]]} for s in kr} == before       # dps · dyt · dz · dvLine 그대로
    assert extra["030610"]["dpsSmall"] == 550 and extra["030610"]["dytSmall"] == 7.33 and extra["048770"]["dytSmall"] == 0.33
    assert "dpsSmall" not in extra["478560"]
    assert rec["v"] == 1 and rec["cand"] == 5 and set(rec["on"]) == {"030610", "048770"}
    assert rec["on"]["030610"] == {"nk": "교보증권", "d": 550, "y": 7.33, "how": "won", "rc": DOCS["030610"],
                                   "q": "주1) 당기(2025년 제81기) 결산 현금배당의 1주당 배당금은 기타주주(최대주주 외) 550원, 최대주주 무배당을 배당하는 차등배당입니다."}
    assert rec["on"]["048770"]["how"] == "cnt" and "일반 및 소액주주 보유 주식 7,787,204주" in rec["on"]["048770"]["q"]
    assert rec["no"] == {"290650": "ev", "478560": "nodiff", "000480": "blk"} and rec["fail"] == {}
    assert rec["read"] == 3 and rec["calls"] == 6
    json.dumps(rec, allow_nan=False)


def test_stage_never_stops_the_run():
    kr, why, c, extra = scene()
    why.cmap["030610"] = "BOOM"
    rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    assert "err" in rec and rec["on"] == {} and not any("dpsSmall" in s or "dytSmall" in s for s in kr)
    assert not any("dpsSmall" in e for e in extra.values())
    kr, why, c, extra = scene()
    why.prove_on = False
    rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    assert rec["on"] == {} and rec["cand"] == 0 and "skip" in rec
    kr, _, _, extra = scene()
    rec = F.small_holder_div(kr, None, None, dt.date(2026, 11, 20), extra)
    assert rec["on"] == {} and not any("dpsSmall" in s for s in kr)


def test_stage_limit_and_no_call():
    kr, why, c, extra = scene()
    c.no_call = "같은 기준일 다시 하기"
    rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    assert rec["on"] == {} and rec["fail"] == {} and {t for t, w in rec["no"].items() if w == "nocall"} == {"030610", "048770", "478560"}
    assert c.calls == []
    kr, why, c, extra = scene()
    old = F.SMALL_DIV_PER_RUN
    try:
        F.SMALL_DIV_PER_RUN = 1
        rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    finally:
        F.SMALL_DIV_PER_RUN = old
    assert set(rec["on"]) == {"030610"} and set(rec["fail"]) == {"048770", "478560"}


def test_a_shown_yield_or_odd_row_is_left_alone():
    kr, why, c, extra = scene()
    by = {s["t"]: s for s in kr}
    by["030610"]["dyt"] = 7.33
    by["048770"]["price"] = 10.0                     # 10 ÷ 10 = 100% > 30%
    rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    assert rec["no"]["030610"] == "bad" and rec["no"]["048770"] == "big" and rec["on"] == {}


def test_one_number_and_tiny_yields():
    """#183 review (Fable S4): dpsSmall is the table's figure as it is (a fractional dividend is not rounded to a whole won) and dytSmall
    is worked from that same value, so the gate agrees; a yield under 0.005% is not published."""
    kr, why, c, extra = scene()
    by = {s["t"]: s for s in kr}
    by["030610"]["dps3"] = [550.5, 500.0, 250.0]
    by["048770"]["price"] = 300000.0                 # 10 ÷ 300,000 = 0.0033%
    c.zips[DOCS["030610"]] = {DOCS["030610"] + ".xml": doc_text("030610").replace("(최대주주 외) 550원", "(최대주주 외) 550.5원").encode("utf-8")}
    rec = F.small_holder_div(kr, why, c, dt.date(2026, 11, 20), extra)
    assert rec["no"]["048770"] == "tiny" and "dpsSmall" not in by["048770"]
    s0 = by["030610"]
    assert s0["dpsSmall"] == 550.5 and s0["dytSmall"] == round(550.5 / 7500 * 100, 2) == 7.34 and rec["on"]["030610"]["d"] == 550.5
    corp = {"companies": [{"t": t, **e} for t, e in extra.items()]}
    assert gate({"stocks": kr, "divSmall": rec}, corp, {"divSmall": rec})[3] == "PASS"
    assert F.small_div_facts("차등배당: 기타주주 550.5원", 2025)["won"] == [550.5]       # never the '5원' inside '550.5원'


def test_main_wires_the_stage_and_the_record():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    m = src[src.index("def main():"):]
    a, b, c = (m.index("apply_div_basis(kr, fin_map"), m.index("small_holder_div(kr, why, client, px_date, corp_extra)"),
               m.index("client.save()                 # 새로 받은 공시 확인이"))
    assert a < b < c
    assert '"divSmall": div_small' in m and m.index('"divSmall": div_small') < m.index("write_json(OUT, payload)")
    assert m.index("small_holder_div(") < m.index("build_corp(kr, fin_map")
    for k in ("dpsSmall", "dytSmall", "divSmall"):
        assert k in F.UNITS


# ── the gate's warning-only row ───────────────────────────────────────────────────────────────────────────────
def gate(data, corp=None, pdata=None):
    rep = V.Report()
    V.check_small_div(rep, data, corp or {"companies": []}, pdata)
    assert len(rep.rows) == 1 and rep.rows[0][0] == V.SMALL_DIV_ROW
    return rep.rows[0]


Q = "주1) 당기(2025년 제81기) 결산 현금배당의 1주당 배당금은 기타주주(최대주주 외) 550원, 최대주주 무배당을 배당하는 차등배당입니다."


def good():
    s1 = kr_row("030610", "교보증권", 7500.0, [550.0, 500.0, 250.0], 113962961, dpsSmall=550, dytSmall=7.33)
    s2 = kr_row("005930", "삼성전자", 100000.0, [1446.0, 1444.0, 1416.0], 1, dyt=1.45, dvLine=None)
    data = {"stocks": [s1, s2], "divSmall": {"v": 1, "cand": 3, "on": {"030610": {"nk": "교보증권", "d": 550, "y": 7.33, "how": "won", "rc": "x",
                                                                                "q": Q}},
                                            "no": {"290650": "ev"}, "fail": {}}}
    corp = {"companies": [{"t": "030610", "dpsSmall": 550, "dytSmall": 7.33}, {"t": "005930"}]}
    return data, corp, {"divSmall": copy.deepcopy(data["divSmall"])}


def test_gate_row_passes_and_names_the_companies():
    data, corp, prev = good()
    name, value, th, st = gate(data, corp, prev)
    assert st == "PASS" and "실음 1: 030610 교보증권 550원 7.33%" in value and "그대로 1" in value
    assert gate({"stocks": []})[3] == "PASS"                                            # 이 단계 전의 파일
    assert gate({"stocks": [], "divSmall": {"v": 1, "cand": 0, "on": {}, "no": {}, "fail": {}}})[3] == "PASS"
    row = gate({"stocks": [], "divSmall": {"v": 1, "cand": 0, "on": {}, "no": {}, "fail": {}, "skip": "배당 기준 증명이 꺼졌어요"}})
    assert row[3] == "PASS" and "건너뜀: 배당 기준 증명이 꺼졌어요" in row[1]


def test_gate_row_new_companies_and_a_lost_record_warn():
    data, corp, prev = good()
    rep = V.Report()
    V.check_small_div(rep, data, corp, {"divSmall": {"v": 1, "on": {}}})                # 지난 발행본에 없던 회사
    assert rep.rows[0][3] == "WARN" and "새로 실은 회사 1" in rep.rows[0][1]
    detail = dict(rep.details)["소액주주 배당수익률 새로 실은 회사의 근거 문장"]
    assert detail == [f"030610 교보증권: {Q}"]
    assert gate(data, corp, {"stocks": []})[3] == "WARN"                              # 지난 발행본이 이 단계 전 — 처음 실은 날도 경고
    assert gate(data, corp, None)[3] == "WARN"
    assert gate({"stocks": []}, None, prev)[3] == "WARN"                               # 지난 발행본엔 기록이 있었는데 이번엔 없음


@pytest.mark.parametrize("bend", [
    lambda d, c: d["stocks"][0].update(dpsSmall=500),                       # 배당 표와 다름
    lambda d, c: d["stocks"][0].update(dpsSmall=550.4),
    lambda d, c: d["stocks"][0].update(dytSmall=7.4),                       # ÷ 종가와 다름
    lambda d, c: d["stocks"][0].update(dytSmall="7.33"),                    # 글자
    lambda d, c: d["stocks"][0].update(dpsSmall="550"),
    lambda d, c: d["stocks"][0].update(dyt=7.33),                           # 보이는 수익률 옆
    lambda d, c: d["stocks"][0].update(dvLine=2),
    lambda d, c: d["stocks"][0].update(cls="us"),
    lambda d, c: d["stocks"][0].update(dytSmall=31.0),
    lambda d, c: d["divSmall"]["on"]["030610"].update(d=551),               # 기록과 다름
    lambda d, c: d["divSmall"]["on"]["030610"].update(q=""),                # 근거 문장 없음
    lambda d, c: d["divSmall"]["on"]["030610"].pop("q"),
    lambda d, c: d["divSmall"]["on"].update({"048770": {"nk": "TPC", "d": 10, "y": 0.33, "q": "x"}}),   # 기록에만
    lambda d, c: c["companies"][0].update(dytSmall=7.0),                    # corp.json 과 다름
    lambda d, c: c["companies"][1].update(dpsSmall=1),                      # corp.json 에만
    lambda d, c: d["divSmall"]["fail"].update({"048770": "원문 조회 실패"}),
    lambda d, c: d["divSmall"].update(err="RuntimeError: boom"),
    lambda d, c: d.update(divSmall={"v": 2}),
    lambda d, c: d.pop("divSmall"),                                         # 칸은 있는데 기록이 없음
])
def test_gate_row_only_warns(bend):
    data, corp, prev = good()
    bend(data, corp)
    assert gate(data, corp, prev)[3] == "WARN"


def test_gate_row_warns_when_the_check_itself_breaks(monkeypatch):
    def boom(*a):
        raise KeyError("x")
    monkeypatch.setattr(V, "_check_small_div", boom)
    data, corp, prev = good()
    assert gate(data, corp, prev)[3] == "WARN"


def test_the_row_is_in_the_gate_after_the_weekly_row():
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert src.index("check_v196e(rep, data, macro)  ") < src.index("check_small_div(rep, data, corp, pdata)  ")
    assert "rep.add(SMALL_DIV_ROW, False" not in src and not re.search(r"rep\.add\(SMALL_DIV_ROW, (?!True)", src)
