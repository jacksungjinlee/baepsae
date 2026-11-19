# -*- coding: utf-8 -*-
"""2026-11-19: 업종 글자가 없는 국내 종목을 DART 기업개황 업종 코드로 채워요 (Jack: "Later, new listings take their industry from DART's
company records." · "move the DART company-record industry mapping up"). ~17:45 KST (Jack): "don't show 통계청 industry names as new
groups. Map each official code to our existing industry groups … Report any codes that don't map cleanly." · 답 1 상시 규칙 (틀린 행은
되돌리고 알린 뒤 발행 · 많을 때와 틀린 숫자일 때만 막아요) · 답 2 우선주는 보통주를 따라요 · 답 3 데이터 출처 줄. 네트워크 없음.

픽스처 tests/fixtures/ind_dart/company_samples.json — 2026-11-19 에 받은 DART company.json 150곳 (대표자 이름 · 주소 등은 지웠어요):
  gap        11-19 08:30 발행본에서 업종 글자가 없던 보통주 57 (모두 업종 코드가 있었어요)
  sample     업종 글자가 있는 보통주 40 (시드 20261119) · prefCommons 업종 글자 없는 우선주 62의 보통주 53
  krxText    그 93곳의 KRX-DESC 업종 글자 (DART 코드 앞 3자리의 11차 이름과 띄어쓰기만 달라야 해요)
"""
import copy
import csv
import datetime as dt
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

FX = json.load(open(os.path.join(ROOT, "tests", "fixtures", "ind_dart", "company_samples.json"), encoding="utf-8"))
NAMES = V.load_ksic_names()
TABLES = F.load_industry_tables()
KMAP, GROUPS = V.load_ksic_map()
MAP = V.load_ksic_map_kr(names=NAMES)
SHA = V.ksic_map_kr_sha()
NODE = shutil.which("node")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


OLD_SECTORS = set(re.findall(r"^\s+(\w+):\s*\{ ko:", read("src/detail.jsx").split("const SECTORS = {", 1)[1].split("};", 1)[0], re.M))
GROUP_NAMES = {g: r["name"] for g, r in TABLES["groups"].items()}


def code_of(t):
    return FX["companies"][t]["induty_code"]


def stock(t, dk="KOSDAQ 상장 · 시가총액 200억원", s="etc", **kw):
    return dict({"t": t, "nk": FX.get("gapNames", {}).get(t, t), "cls": "kr", "s": s, "dk": dk, "etf": False}, **kw)


def grouped(stocks, ksic):
    """assign_industries 로 2.0 그룹을 붙여요 (실제 실행처럼 · 채우기 전에)."""
    F.assign_industries(stocks, TABLES, ksic, min_members=1)
    return stocks


def sq(x):
    return x.replace(" ", "")


def no_text_of(stocks):
    return [s["t"] for s in stocks if not (F.kr_desc_parse(s["dk"]) if s.get("dk") else ("", ""))[0]]


# ── 1. 한국표준산업분류 표 ────────────────────────────────────────────
def test_ksic_table_is_revision_11_with_its_source():
    head = [x for x in open(V.KSIC_NAMES_CSV, encoding="utf-8").read().splitlines() if x.startswith("#")]
    text = "\n".join(head)
    for want in ("제11차", "통계청 고시 제2024-2호", "2024-07-01", "15159306", "2026-04-30",
                 "ef9f31d66d335a32fdde5afb204920c2fe22258fc9c40cad120892a898a73619"):
        assert want in text
    assert {n: sum(1 for c in NAMES if len(c) == n) for n in range(1, 6)} == V.KSIC_LEVELS == {1: 21, 2: 77, 3: 234, 4: 501, 5: 1205}
    assert NAMES["264"] == "통신 및 방송장비 제조업" and NAMES["282"] == "일차전지 및 이차전지 제조업"
    assert NAMES["582"] == "소프트웨어 개발 및 공급업" and NAMES["011"] == "작물 재배업"     # 앞자리 0 그대로
    # 설명(dk) 을 나누는 ' · ' · '주요제품: ' 이 소분류 이름에 없어야 kr_desc_parse 가 그대로 읽어요
    assert not [n for c, n in NAMES.items() if len(c) == 3 and (" · " in n or "주요제품" in n or n.endswith("상장"))]
    assert F.load_ksic_names is V.load_ksic_names and F.IND_DART_DIGITS is V.IND_DART_DIGITS == 3
    assert F.kr_desc_parse is V.kr_desc_parse                      # 설명을 읽는 코드는 관문 파일 하나


@pytest.mark.parametrize("edit", ["head", "dup", "drop", "blank"])
def test_ksic_table_refuses_a_broken_file(tmp_path, edit):
    lines = open(V.KSIC_NAMES_CSV, encoding="utf-8").read().splitlines()
    i = next(k for k, x in enumerate(lines) if x.startswith("산업,264,"))
    if edit == "head":
        lines = [x.replace("분류,코드값,상세설명", "분류,코드,설명") for x in lines]
    elif edit == "dup":
        lines.insert(i, lines[i])
    elif edit == "drop":
        del lines[i]
    else:
        lines[i] = "산업,264,"
    p = tmp_path / "k.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        V.load_ksic_names(str(p))


def test_dart_codes_give_the_same_words_as_krx():
    """기록한 93곳: KRX 업종 글자 = DART 업종 코드 앞 3자리의 11차 이름 (띄어쓰기만 다른 19) · 업종 키도 같아요."""
    assert len(FX["krxText"]) == 93
    exact = 0
    for t, krx in FX["krxText"].items():
        name = NAMES[code_of(t)[:3]]
        assert sq(name) == sq(krx), (t, krx, name)
        exact += name == krx
        assert F.map_sector_kr(name, "") == F.map_sector_kr(krx, "")
    assert exact == 74


def test_gate_and_pipeline_use_the_same_group_rule():
    for t, c in FX["companies"].items():
        assert V.ksic_prefix_group(c["induty_code"], KMAP) == F.ksic_group(c["induty_code"], TABLES["kmap"])
    assert KMAP == TABLES["kmap"] and GROUPS == set(TABLES["groups"])


# ── 2. 11차 코드 → 우리 업종 표 (Jack: 공식 이름을 새 무리로 보이지 않아요) ─────────────────
def test_mapping_table_is_the_rules_output_and_covers_every_code():
    """data/ksic_map_kr.csv = ksic_map_kr_rows (손으로 고치지 않아요) · 11차 소분류 234개 모두 · 상태별 수."""
    rows = F.ksic_map_kr_rows(NAMES, TABLES["kmap"], TABLES["groups"])
    with open(V.KSIC_MAP_KR_CSV, encoding="utf-8") as f:
        body = [r for r in csv.reader(x for x in f.read().splitlines() if x and not x.startswith("#"))][1:]
    assert body == rows, "규칙이나 표가 바뀌었어요 — ksic_map_kr_rows 로 data/ksic_map_kr.csv 를 다시 만들고 PR 에 보여요"
    assert len(MAP) == 234 and set(MAP) == {c for c in NAMES if len(c) == 3}
    count = {st: sum(1 for v in MAP.values() if v["status"] == st) for st in V.KSIC_MAP_STATUS}
    assert count == {"ok": 117, "none": 94, "ambiguous": 13, "financial": 9, "fund": 1}
    head = "\n".join(x for x in read("data/ksic_map_kr.csv").splitlines() if x.startswith("#"))
    assert "status ok 117 · none 94 · ambiguous 13 · financial 9 · fund 1" in head


def test_every_ok_code_lands_in_existing_groups_of_both_apps():
    """ok 코드: 예전 뱁새 업종 키는 SECTORS 에 있는 키 (기타 · 금융 아님) · 2.0 그룹은 industry_groups.csv 의 그룹 · 둘이 같은 업종."""
    assert {"semi", "machine", "etc", "broker"} <= OLD_SECTORS and len(OLD_SECTORS) >= 30
    for g, keys in V.IND_SECTOR_KR.items():
        assert g in TABLES["groups"] and set(keys) <= OLD_SECTORS and "etc" not in keys, g
        assert not set(keys) & set(F.FIN_SECS) and TABLES["groups"][g]["financial"] != "yes", g
    assert set(V.IND_FIN_SECS) == set(F.FIN_SECS)
    lens = set(re.findall(r"^\s+(\w+):\s*\{ ko:", read("src/detail.jsx").split("const LENS = {", 1)[1].split("};", 1)[0], re.M))
    for c, v in MAP.items():
        if v["status"] == "ok":
            assert v["s"] in OLD_SECTORS and v["s"] in lens and v["s"] != "etc" and v["ind"], c
            assert all(g in GROUP_NAMES and v["s"] in V.IND_SECTOR_KR[g] for g in v["ind"]), c


def test_codes_that_do_not_map_cleanly():
    """보고할 코드 (예): 짝 없음 · 갈림 · 금융 · 집합 투자업 — 채우지 않아요."""
    want = {"264": ("ok", "machine", ("telecom_eq",)), "141": ("ok", "textile", ("textile",)), "292": ("ok", "machine", None),
            "108": ("none", "etc", ("food",)), "339": ("none", "etc", ("furniture",)), "761": ("none", "machine", ("services",)),
            "051": ("none", "energy", ()), "620": ("ambiguous", "elec", ("it_service",)), "473": ("ambiguous", "elec", ("retail",)),
            "467": ("ambiguous", "retail", ("energy", "trading")), "331": ("financial", "broker", ("furniture",)),
            "281": ("ok", "elec", ("power_eq",)), "204": ("ambiguous", "chem", ("cosmetics", "spchem")),
            "381": ("ambiguous", "utility", ("utility",)), "390": ("ambiguous", "utility", ("utility",)),
            "352": ("ok", "utility", ("utility",)), "320": ("none", "paper", ("furniture",)), "334": ("none", "game", ("furniture",)),
            "641": ("financial", "bank", ("bank",)), "649": ("financial", "holding", ("finance", "holding")),
            "642": ("fund", "etc", ("finance",))}
    for c, (st, s, ind) in want.items():
        assert MAP[c]["status"] == st and MAP[c]["s"] == s, (c, MAP[c])
        assert ind is None or MAP[c]["ind"] == ind, (c, MAP[c])
    assert sorted(c for c, v in MAP.items() if v["status"] == "ambiguous") == \
        ["204", "251", "381", "382", "390", "426", "465", "466", "467", "473", "476", "620", "912"]
    # 리뷰 (업종 읽는 법 LENS): 281 은 이름 규칙의 utility ('요금은 정부가 정해요') 대신 2.0 power_eq 의 대표 짝 elec
    assert F.map_sector_kr(NAMES["281"], "") == "utility" and V.KSIC_S_FIX == {"281": "elec"} and V.IND_SECTOR_KR["power_eq"][0] == "elec"
    assert "furniture" not in V.IND_SECTOR_KR and "chem" not in V.IND_SECTOR_KR["cosmetics"] and "utility" not in V.IND_SECTOR_KR["power_eq"]
    assert sorted(c for c, v in MAP.items() if v["status"] == "financial") == \
        ["331", "641", "649", "651", "652", "653", "661", "662", "846"]


@pytest.mark.parametrize("edit", ["head", "ok_etc", "ok_mismatch", "ok_fin", "name", "status"])
def test_mapping_table_refuses_a_broken_file(tmp_path, edit):
    lines = read("data/ksic_map_kr.csv").splitlines()
    i = next(k for k, x in enumerate(lines) if x.startswith("264,"))
    if edit == "head":
        lines = [x.replace("ksic,name,s,ind,status,why", "ksic,name,s,ind,status") for x in lines]
    elif edit == "ok_etc":
        lines[i] = "264,통신 및 방송장비 제조업,etc,telecom_eq,ok,"
    elif edit == "ok_mismatch":
        lines[i] = "264,통신 및 방송장비 제조업,semi,telecom_eq,ok,"
    elif edit == "ok_fin":
        lines[i] = "264,통신 및 방송장비 제조업,broker,telecom_eq,ok,"
    elif edit == "name":
        lines[i] = "264,통신 및 방송 장비 제조업,machine,telecom_eq,ok,"
    else:
        lines[i] = "264,통신 및 방송장비 제조업,machine,telecom_eq,maybe,"
    p = tmp_path / "m.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        V.load_ksic_map_kr(str(p), names=NAMES)


def test_official_names_never_become_a_group_in_either_app():
    """A.1 (2026-11-19): 설명(dk)은 회사 한 줄 설명으로만 보여요 — 무리를 짓는 곳은 예전 뱁새 s · 2.0 ind 뿐이에요."""
    v2 = "".join(read(os.path.join("src/v2", n)) for n in os.listdir(os.path.join(ROOT, "src/v2")) if n.endswith((".js", ".jsx")))
    assert not re.search(r"\.dk\b|\bdk:", v2)                                          # 2.0 은 dk 를 읽지 않아요
    old = {n: read(os.path.join("src", n)) for n in os.listdir(os.path.join(ROOT, "src")) if n.endswith((".js", ".jsx"))}
    uses = sorted((n, m.group(0)) for n, txt in old.items() for m in re.finditer(r"[\w.]*\bx\.dk\b|L\.dk\b|\bs\.x\.dk\b", txt))
    # data.js 가 읽고 · detail.jsx 는 펼친 종목의 설명 상자(x.dk 셋) · 내장 종목 표시(isCurated, s.x.dk && !s.auto) · '설명을 읽을 수 있는
    # 종목' 수(r.stock.x.dk — data.json 종목의 dk 는 늘 '… 상장 · 시가총액 …' 이 있어 채워도 수가 그대로)뿐 — 무리를 짓는 곳은 없어요
    assert uses == [("data.js", "L.dk"), ("detail.jsx", "r.stock.x.dk"), ("detail.jsx", "s.x.dk"), ("detail.jsx", "x.dk"),
                    ("detail.jsx", "x.dk"), ("detail.jsx", "x.dk")], uses
    det = old["detail.jsx"]
    assert "{x.dk && <div" in det and "lang === \"ko\" ? x.dk : x.de || x.dk" in det     # 펼친 종목의 설명 상자
    assert "const isCurated = (s) => !!(s.x && s.x.dk && !s.auto);" in det
    # 2.0 그룹 이름은 industry_groups.csv 의 이름뿐 (assign_industries) · 예전 뱁새 업종 이름은 SECTORS 뿐
    s = [stock("282620")]
    grouped(s, {"282620": "14199"})
    assert s[0]["indName"] == GROUP_NAMES["textile"]


# ── 3. 계획 (순수 함수) ─────────────────────────────────────────────
def test_the_57_stocks_of_the_0830_publish():
    """11-19 08:30 발행본에서 업종 글자가 없던 보통주 57곳 — 깔끔히 맞는 49곳만 채워요 · 8곳은 예전처럼 (우선주 · 펀드는 계획 밖)."""
    gap = FX["gap"]
    ksic = {t: code_of(t) for t in gap}
    stocks = grouped([stock(t) for t in gap] + [stock(t) for t in FX["prefGap"]] + [stock("088980", etf=True)], ksic)
    fill, miss = F.kr_ind_dart_plan(stocks, [s["t"] for s in stocks], ksic, MAP)
    assert len(gap) == 57 and len(fill) == 45
    assert miss == {"mapAmbig": ["067730", "110020", "118000", "252500", "342870", "344860", "424760"],
                    "mapNone": ["054090", "073190", "238200", "365900", "376180"], "fund": ["088980"]}
    assert fill["288620"] == (NAMES["281"], "281", "elec") and fill["237750"] == (NAMES["281"], "28123", "elec")
    assert fill["282620"] == ("봉제의복 제조업", "14199", "textile") and fill["376930"] == ("의료용 기기 제조업", "27112", "health")
    by_t = {s["t"]: s for s in stocks}
    for t, (name, code, sec) in fill.items():
        assert sec in V.IND_SECTOR_KR[by_t[t]["ind"]] and sec in OLD_SECTORS and by_t[t]["indName"] in GROUP_NAMES.values()


def test_plan_reasons_when_it_cannot_fill():
    ts = ("100000", "200000", "300000", "400000", "500000", "600000", "700000", "800000", "900000", "110000", "120000")
    ksic = {"100000": "26410", "200000": "99999", "300000": "26", "500000": "  ", "600000": "64201", "700000": "64110",
            "800000": "10800", "900000": "62010", "110000": "26410", "120000": "14199"}
    stocks = grouped([stock(t) for t in ts], ksic)
    by_t = {s["t"]: s for s in stocks}
    by_t["110000"].pop("ind")                                   # 2.0 그룹 없음 (작은 그룹 · 고정표 …)
    by_t["120000"]["ind"] = "services"                         # 고정표가 짝 없는 그룹으로
    fill, miss = F.kr_ind_dart_plan(stocks + [stock("005935")], list(ts) + ["005935", "999990"], ksic, MAP)
    assert fill == {"100000": ("통신 및 방송장비 제조업", "26410", "machine")}
    assert miss == {"noName": ["200000", "300000"], "noCode": ["400000", "500000"], "mapFund": ["600000"], "mapFin": ["700000"],
                    "mapNone": ["120000", "800000"], "mapAmbig": ["900000"], "noGroup": ["110000"]}
    # 005935 우선주 (kr_ind_pref_copy) · 999990 발행하지 않는 종목 — 세지 않아요


def test_plan_keeps_an_existing_sector_key_only_when_it_agrees():
    """업종 키가 이미 있으면 (지난 발행본의 s · 주요제품) 2.0 그룹과 같은 업종일 때만 두고 채워요."""
    ksic = {"100000": "26410", "200000": "26410"}
    stocks = grouped([stock("100000", s="elec"), stock("200000", s="food")], ksic)
    fill, miss = F.kr_ind_dart_plan(stocks, ["100000", "200000"], ksic, MAP)
    assert fill == {"100000": ("통신 및 방송장비 제조업", "26410", "elec")} and miss == {"mapAmbig": ["200000"]}


def test_plan_only_looks_at_stocks_without_words():
    """no_text 에 없는 종목(KRX 글자 · 이어 쓴 글자가 있는 종목)은 계획에 들어오지 않아요."""
    ksic = {"100000": "26410", "200000": "26410"}
    stocks = grouped([stock("100000"), stock("200000", dk="반도체 제조업 · KOSDAQ 상장")], ksic)
    fill, _ = F.kr_ind_dart_plan(stocks, ["100000"], ksic, MAP)
    assert list(fill) == ["100000"]


# ── 4. 적용 · 우선주 · 출처 · 로그 ─────────────────────────────────────
def test_apply_never_overwrites_existing_words():
    a = stock("100000")                                                  # 글자 없음 → 채워요
    b = stock("200000", dk="반도체 제조업 · 주요제품: 메모리 · KOSPI 상장", s="semi")     # KRX · 이어 쓴 글자 → 그대로
    d = stock("400000", dk="알 수 없는 글")                               # 읽지 못하는 설명 → 그대로
    e = stock("500000", dk=None)                                          # 설명이 없던 종목 → 이름만
    f = stock("600000", dk="주요제품: 반도체 · KOSDAQ 상장")              # 주요제품만 → 이름을 앞에
    fill = {t: ("통신 및 방송장비 제조업", "264", "machine") for t in ("100000", "200000", "400000", "500000", "600000")}
    before = json.dumps([b, d])
    done, undo = F.kr_ind_dart_apply([a, b, d, e, f], fill)
    assert done == {"100000": "264", "500000": "264", "600000": "264"} and json.dumps([b, d]) == before
    assert undo == {"100000": {"dk": "KOSDAQ 상장 · 시가총액 200억원", "s": "etc"}, "500000": {"dk": None, "s": "etc"},
                    "600000": {"dk": "주요제품: 반도체 · KOSDAQ 상장", "s": "etc"}}
    assert a["dk"] == "통신 및 방송장비 제조업 · KOSDAQ 상장 · 시가총액 200억원" == F.kr_desc_text("통신 및 방송장비 제조업", "", "KOSDAQ", 0.02)
    assert F.kr_desc_parse(a["dk"]) == ("통신 및 방송장비 제조업", "") and a["s"] == "machine"
    assert e["dk"] == "통신 및 방송장비 제조업" and f["dk"] == "통신 및 방송장비 제조업 · 주요제품: 반도체 · KOSDAQ 상장"
    assert f["s"] == "machine"                                            # 업종 키는 표에서 (계획이 정한 키)


def test_preferred_shares_follow_their_common_stock():
    """답 2 (Jack, 2026-11-19): 삼성전자우는 삼성전자의 업종 글자 · 업종 키 · 2.0 그룹을 따라요."""
    common = stock("005930", dk="통신 및 방송 장비 제조업 · 주요제품: 반도체 · KOSPI 상장 · 시가총액 1,138.3조원", s="semi",
                   ind="semi", indName="반도체")
    pref = stock("005935", dk="KOSPI 상장 · 시가총액 126.8조원", ind="semi", indName="반도체")
    moved = stock("000815", dk="KOSPI 상장", ind="bank", indName="은행")          # 2.0 그룹이 보통주와 다름 → 맞춰요
    c2 = stock("000810", dk="보험업 · KOSPI 상장", s="insure", ind="insurance", indName="보험")
    lone = stock("123455")                                                         # 보통주가 목록에 없음
    c3, p3 = stock("234560"), stock("234565")                                      # 보통주도 글자 없음
    c4, p4 = stock("345670", dk="반도체 제조업 · KOSDAQ 상장", s="semi", ind="semi"), stock("345675", ind="elec_parts")
    stocks = [common, pref, moved, c2, lone, c3, p3, c4, p4]
    done, miss, undo, n_ind = F.kr_ind_pref_copy(stocks, ["005935", "000815", "123455", "234565", "345675", "234560"], over={"345675": ()})
    assert done == {"005935": "005930", "000815": "000810"} and n_ind == 1
    assert miss == {"prefNoCommon": ["123455"], "prefCommonNone": ["234565"], "prefOver": ["345675"]}
    assert pref["dk"] == "통신 및 방송 장비 제조업 · KOSPI 상장 · 시가총액 126.8조원" and pref["s"] == "semi" and pref["ind"] == "semi"
    assert F.kr_desc_parse(pref["dk"]) == ("통신 및 방송 장비 제조업", "")                 # 주요제품은 보통주 것이라 옮기지 않아요
    assert moved["s"] == "insure" and moved["ind"] == "insurance" and moved["indName"] == "보험"
    assert undo["000815"] == {"dk": "KOSPI 상장", "s": "etc", "ind": "bank", "indName": "은행"}
    assert p4.get("dk") == "KOSDAQ 상장 · 시가총액 200억원" and p4["ind"] == "elec_parts"   # 고정표의 우선주는 그대로


def fill_case():
    """08:30 발행본의 갭 57곳 + 우선주 몇 곳 (그 보통주 포함) + 펀드 — kr_ind_fill 한 번."""
    ksic = {t: code_of(t) for t in FX["gap"]}
    commons = [stock("005930", dk="통신 및 방송 장비 제조업 · KOSPI 상장", s="semi"), stock("000810", dk="보험업 · KOSPI 상장", s="insure")]
    ksic.update({"005930": "26410", "000810": "65121"})
    stocks = grouped([stock(t) for t in FX["gap"]] + commons + [stock("005935"), stock("000815"), stock("088980", etf=True)], ksic)
    stocks[-1]["s"] = "broker"
    return stocks, ksic


def test_fill_records_the_source_and_logs_loudly(capsys):
    stocks, ksic = fill_case()
    ind = {"v": 1, "desc": 0, "carried": 2354, "none": 60, "newNone": 2, "asOf": "2026-11-17", "from": "KRX-DESC + prev"}
    rec = F.kr_ind_fill(stocks, no_text_of(stocks), ksic, MAP, ind, over=TABLES["over"], names=NAMES, map_sha=SHA)
    assert rec == {"n": 0, "rows": []}
    assert ind["dart"] == 45 and len(ind["dartT"]) == 45 and ind["dartT"]["282620"] == "14199" and ind["mapSha"] == SHA
    assert ind["pref"] == 2 and ind["prefT"] == {"000815": "000810", "005935": "005930"} and ind["prefInd"] == 0
    assert ind["left"] == 12 and ind["dartMiss"] == {"fund": 1, "mapAmbig": 7, "mapNone": 5} and ind["from"] == "KRX-DESC + prev + DART"
    assert ind["carried"] == 2354 and ind["none"] == 60          # 예전 칸은 그대로
    out = capsys.readouterr().out
    assert "  !! 업종 DART 회사 정보로 채움 45 / 57 · 우선주가 보통주를 따름 2 (2.0 그룹을 맞춘 우선주 0) · 그래도 업종 글자 없음 12" in out
    assert "예: 002690 동일제강 1차 철강 제조업 (24122 → steel), 005360 모나미 생활용품 도매업 (46452 → retail)" in out
    assert "  !! 업종 코드가 우리 업종에 깔끔히 맞지 않아 채우지 않은 종목 12개 (예전처럼 업종 글자 없이 · 기타): " in out
    assert "067730 로지시스 (62090 컴퓨터 프로그래밍, 시스템 통합 및 관리업 · ambiguous)" in out
    assert "238200 비피도 (108 기타 식품 제조업 · none)" in out
    assert f"· {V.IND_FILL_CHECK}: 0건 되돌림 (DART 45 · 우선주 2 확인)" in out
    # 채울 것이 없는 날 (KRX 글자가 돌아온 11-19 12:16 발행본처럼): 조용한 줄 · from 은 그대로
    ind2 = {"from": "KRX-DESC"}
    assert F.kr_ind_fill([stock("100000", dk="반도체 제조업 · KOSDAQ 상장", ind="semi")], [], {}, MAP, ind2) == {"n": 0, "rows": []}
    assert ind2 == {"from": "KRX-DESC", "dart": 0, "dartT": {}, "pref": 0, "prefT": {}, "prefInd": 0, "left": 0, "dartMiss": {}}
    assert "· 업종 DART 회사 정보로 채움 0 / 0 · 우선주가 보통주를 따름 0" in capsys.readouterr().out


def test_a_broken_fill_never_stops_the_run(monkeypatch, capsys):
    """채우기가 고장 나도 예외 없이 발행 · 채운 것을 모두 되돌리고 크게 남겨요 · 관문은 경고."""
    stocks, ksic = fill_case()
    before = copy.deepcopy(stocks)

    def boom(*a, **k):
        raise TypeError("고장")
    monkeypatch.setattr(F, "kr_ind_own_drop", boom)                # 보통주 · 우선주를 채운 뒤에 멈춰요
    ind = {"from": "KRX-DESC"}
    rec = F.kr_ind_fill(stocks, no_text_of(stocks), ksic, MAP, ind, over=TABLES["over"])
    assert rec == {"n": 0, "rows": [], "err": "TypeError"} and stocks == before
    assert ind == {"from": "KRX-DESC", "dart": 0, "dartT": {}, "pref": 0, "prefT": {}, "prefInd": 0, "left": None, "dartMiss": {},
                   "dartErr": "TypeError"}
    assert "  !! 업종 채우기 실패 (TypeError: 고장) — 채운 47종목을 되돌리고" in capsys.readouterr().out
    rows, rep = gate({"stocks": stocks, "indSrc": dict(ind, carried=0, asOf="2026-11-19", newNone=0), "ownDrop": {"indFill": rec}})
    assert rows["국내 업종 글자 없는 종목 (경고만)"][3] == "WARN" and "채우기 실패 TypeError" in rows["국내 업종 글자 없는 종목 (경고만)"][1]
    assert rows[V.IND_FILL_CHECK][3] == "WARN" and "채우기 고장 TypeError" in rows[V.IND_FILL_CHECK][1] and not rep.failed


def test_filled_words_are_not_carried_as_krx_words():
    """지난 발행본이 DART 로 채운 종목 · 보통주를 따른 우선주는 이어 쓰지 않아요 — 오늘 다시 채우고 따라요 (관문이 오늘 값을 봐요)."""
    prev = {"publishedAt": "2026-11-19T08:30:00+09:00",
            "indSrc": {"carried": 1, "asOf": "2026-11-17", "dartT": {"282620": "14199"}, "prefT": {"005935": "005930"}},
            "stocks": [{"t": "282620", "cls": "kr", "dk": "봉제의복 제조업 · KOSDAQ 상장 · 시가총액 614억원"},
                       {"t": "005935", "cls": "kr", "dk": "통신 및 방송 장비 제조업 · KOSPI 상장"},
                       {"t": "005930", "cls": "kr", "dk": "통신 및 방송 장비 제조업 · 주요제품: 반도체 · KOSPI 상장"}]}
    pdesc, day, bad = F.kr_prev_desc(prev)
    assert pdesc == {"005930": ("통신 및 방송 장비 제조업", "반도체")} and day == "2026-11-17" and bad == 0
    out, carried, none = F.kr_desc_carry({}, pdesc, {"282620", "005930", "005935"})
    assert carried == ["005930"] and none == ["005935", "282620"]


# ── 5. DART 호출: 새로 부르지 않아요 · 보관 · 실패 ──────────────────────────
def test_the_fill_makes_no_dart_calls(monkeypatch):
    """채우기는 fetch_ksic 가 이미 받은 코드만 써요 — 클라이언트를 받지 않고, 기업개황을 부르는 곳은 fetch_ksic 하나예요."""
    for fn in (F.kr_ind_fill, F.kr_ind_dart_plan, F.kr_ind_dart_apply, F.kr_ind_pref_copy, F.kr_ind_own_drop, F.corp_sector_stats):
        assert "client" not in inspect.signature(fn).parameters
    src = inspect.getsource(F)
    assert src.count(".company(") == 1 and ".company(" in inspect.getsource(F.fetch_ksic)
    main = inspect.getsource(F.main)
    # 2.0 그룹이 정해진 뒤 (계획이 그룹을 봐요) · corp.json 이 업종 키를 옮겨 쓰기 전 · data.json 기록
    fill_at = main.index("kr_ind_fill(kr,")
    assert main.index("fetch_ksic, kr, client") < main.index("icnt = assign_industries(") < fill_at < main.index("corp = build_corp(")
    assert fill_at < main.index('payload.setdefault("ownDrop", {})["indFill"] = ind_drop') < main.index("write_json(OUT, payload)")
    assert "load_ksic_map_kr(names=ksic_names)" in main and "names=ksic_names, map_sha=ksic_sha, table_err=ksic_err" in main

    def boom(*a, **k):
        raise AssertionError("network")
    monkeypatch.setattr(F.requests, "get", boom)
    stocks = grouped([stock("282620")], {"282620": "14199"})
    F.kr_ind_fill(stocks, ["282620"], {"282620": "14199"}, MAP, {})
    assert stocks[0]["dk"].startswith("봉제의복 제조업 · ")


def fake_client(tmp_path, today, answers, calls):
    c = F.DartClient("k", today=today, path=str(tmp_path / "c.json.gz"))

    def get(endpoint, params, timeout=25):
        calls.append(params["corp_code"])
        return answers.pop(0) if answers else None
    c.get = get
    return c


def test_company_record_is_kept_180_days_plus_jitter_then_refreshed(tmp_path):
    """기업개황(업종 코드)은 COMPANY_TTL_DAYS(180) + 기업마다 0~59일 보관해요 — 그 안에는 부르지 않고, 지나면 한 번 다시 받아요."""
    assert F.COMPANY_TTL_DAYS == 180
    rec = dict(FX["companies"]["282620"])
    corp = rec["corp_code"]
    jitter = int(F.hashlib.md5(corp.encode()).hexdigest(), 16) % 60
    d0, calls = dt.date(2026, 11, 19), []
    c = fake_client(tmp_path, d0, [rec], calls)
    assert c.company(corp) == {"induty": "14199"} and calls == [corp]
    c.today = d0 + dt.timedelta(days=180 + jitter - 1)
    assert c.company(corp) == {"induty": "14199"} and calls == [corp]           # 아직 보관 기간
    c.today = d0 + dt.timedelta(days=180 + jitter)
    c.get = lambda e, p, timeout=25: calls.append(p["corp_code"]) or dict(rec, induty_code="14112")
    assert c.company(corp) == {"induty": "14112"} and calls == [corp, corp]    # 지나서 다시 받았어요


@pytest.mark.parametrize("answer", [None, {"status": "013", "message": "조회된 데이타가 없습니다."}])
def test_company_failure_keeps_the_old_code_or_gives_none(tmp_path, answer):
    rec = dict(FX["companies"]["376930"])
    corp, calls = rec["corp_code"], []
    c = fake_client(tmp_path, dt.date(2026, 11, 19), [answer], calls)
    assert c.company(corp) is None                                                # 처음부터 실패 → 코드 없음 (예외 없음)
    c.entries[f"{corp}|company"] = {"st": "000", "at": "2025-01-01", "d": {"induty": "27112"}}
    c.get = lambda e, p, timeout=25: answer
    assert c.company(corp) == {"induty": "27112"}                                 # 오래된 값이라도 실패하면 그대로
    # 계획: 코드가 없는 종목은 '업종 코드 없음' 으로 세고 실행은 계속돼요 (관문은 경고만)
    fill, miss = F.kr_ind_dart_plan([stock("376930", ind="medical")], ["376930"], {}, MAP)
    assert fill == {} and miss == {"noCode": ["376930"]}


# ── 6. Jack 의 상시 규칙 (2026-11-19): 틀린 행은 되돌리고 알린 뒤 발행 ─────────────────
def filled():
    """kr_ind_fill 을 마친 상태 (데이터 · 되돌릴 값). 45곳 + 우선주 2 · 이번 표의 판 (mapSha)."""
    stocks, ksic = fill_case()
    ind = {"v": 1, "desc": 0, "carried": 0, "none": 60, "newNone": 0, "asOf": "2026-11-19", "from": "KRX-DESC"}
    fill, miss = F.kr_ind_dart_plan(stocks, no_text_of(stocks), ksic, MAP)
    done, undo = F.kr_ind_dart_apply(stocks, fill)
    pdone, _, u2, _ = F.kr_ind_pref_copy(stocks, no_text_of(stocks), TABLES["over"])
    undo.update(u2)
    ind.update({"dart": len(done), "dartT": done, "pref": len(pdone), "prefT": pdone, "prefInd": 0, "left": 12, "dartMiss": {},
                "mapSha": SHA})
    return stocks, ind, undo


def gate(data):
    rep = V.Report()
    V.check_px_src(rep, data, dt.date(2026, 11, 19))
    return {r[0]: r for r in rep.rows}, rep


def test_n_comes_from_recent_runs():
    """N = max(5, 3 × 최근 실행의 최대 되돌림) — 최근 발행본 20개 · 이 PR 의 시험 실행 모두 0 (PR 의 표)."""
    assert V.IND_FILL_MAX == 5


def test_one_bad_row_is_reverted_logged_and_the_rest_publishes(capsys):
    stocks, ind, undo = filled()
    by_t = {s["t"]: s for s in stocks}
    by_t["282620"]["s"] = "bank"                                   # 우리 단계의 실수 하나 (업종 키가 2.0 그룹과 다름)
    rec, dropped = F.kr_ind_own_drop(stocks, ind, undo, NAMES, MAP, SHA)
    assert dropped == ["282620"] and rec == {"n": 1, "rows": ["282620 기도산업: 업종 키 bank 가 2.0 그룹 textile 와 맞지 않음"]}
    assert by_t["282620"]["dk"] == "KOSDAQ 상장 · 시가총액 200억원" and by_t["282620"]["s"] == "etc"   # 채우기 전으로
    assert "282620" not in ind["dartT"] and ind["dart"] == 44 and by_t["376930"]["dk"].startswith("의료용 기기 제조업 · ")
    out = capsys.readouterr().out
    assert f"  !! {V.IND_FILL_CHECK}: 1건 되돌리고 발행 — 282620 기도산업: 업종 키 bank 가 2.0 그룹 textile 와 맞지 않음" in out
    rows, rep = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": rec}})
    r = rows[V.IND_FILL_CHECK]
    assert r[3] == "WARN" and "되돌림 1" in r[1] and not rep.failed
    assert (f"{V.IND_FILL_CHECK}: 파이프라인이 되돌린 행 1", ["282620 기도산업: 업종 키 bank 가 2.0 그룹 textile 와 맞지 않음"]) in rep.details


def test_a_reverted_common_takes_its_preferred_share_back_too():
    stocks, ind, undo = filled()
    by_t = {s["t"]: s for s in stocks}
    # 보통주를 DART 로 채운 뒤 우선주가 따랐는데 그 보통주가 틀렸어요 → 보통주를 되돌리면 우선주도 다음 확인에서 되돌려요
    by_t["282625"] = stock("282625")
    stocks.append(by_t["282625"])
    pdone, _, u2, _ = F.kr_ind_pref_copy(stocks, ["282625"], {})
    undo.update(u2)
    ind["prefT"].update(pdone)
    ind["pref"] = len(ind["prefT"])
    by_t["282620"]["dk"] = by_t["282620"]["dk"].replace("봉제의복", "봉제 의복")   # 글자만 틀림 (숫자와 상관없음)
    by_t["282625"]["dk"] = by_t["282625"]["dk"].replace("봉제의복", "봉제 의복")
    rec, dropped = F.kr_ind_own_drop(stocks, ind, undo, NAMES, MAP, SHA)
    assert dropped == ["282620", "282625"] and rec["n"] == 2
    assert by_t["282625"]["dk"] == "KOSDAQ 상장 · 시가총액 200억원" and "282625" not in ind["prefT"]
    assert V.ind_fill_bad(stocks, ind, NAMES, MAP, SHA) == []


def test_more_than_n_reverted_rows_fail_the_gate():
    stocks, ind, undo = filled()
    by_t = {s["t"]: s for s in stocks}
    for t in list(ind["dartT"])[:V.IND_FILL_MAX + 1]:
        by_t[t]["s"] = "bank"
    rec, dropped = F.kr_ind_own_drop(stocks, ind, undo, NAMES, MAP, SHA)
    assert rec["n"] == V.IND_FILL_MAX + 1 and V.ind_fill_bad(stocks, ind, NAMES, MAP, SHA) == []
    rows, rep = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": rec}})
    assert rows[V.IND_FILL_CHECK][3] == "FAIL" and "되돌림 6" in rows[V.IND_FILL_CHECK][1]
    rec["n"] = V.IND_FILL_MAX                                      # N 까지는 경고
    rows, rep = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": rec}})
    assert rows[V.IND_FILL_CHECK][3] == "WARN"


@pytest.mark.parametrize("break_it, why, num", [
    ("sector", "업종 키 bank 가 2.0 그룹 textile 와 맞지 않음", True),
    ("code", "산업분류표에 없음", True),
    ("fund", "집합 투자업", True),
    ("unclean", "깔끔히 맞지 않음 (ambiguous)", True),
    ("unclean_old_table", "채운 뒤 표가 바뀌었어요", False),
    ("pref_in_dart", "우선주 (DART 로 채우지 않아요)", True),
    ("pref_sector", "업종 키 · 2.0 그룹", True),
    ("pref_group", "업종 키 · 2.0 그룹", True),
    ("pref_common", "가 이 우선주의 보통주가 아님", True),
    ("name", "설명 업종", False),
    ("pref_words", "업종 글자", False),
    ("missing", "발행한 국내 주식이 아님", False),
    ("count", "dart 50 ≠ dartT 45", False)])
def test_a_remaining_bad_value_fails_only_when_it_shows_a_wrong_number(break_it, why, num):
    """파이프라인이 되돌리지 못한 틀린 값 (되돌리기 단계 고장): 틀린 숫자가 보이면 실패 (업종 키 · 2.0 그룹 → 업종 평균 · 중간값 ·
    EV 멀티플 · 업종별 등락), 글자 · 기록만 틀리면 경고."""
    stocks, ind, undo = filled()
    by_t = {s["t"]: s for s in stocks}
    if break_it == "sector":
        by_t["282620"]["s"] = "bank"
    elif break_it == "code":
        ind["dartT"]["282620"] = "999"
    elif break_it == "fund":
        ind["dartT"]["282620"] = "64201"
    elif break_it in ("unclean", "unclean_old_table"):          # 설명 · 짝은 맞지만 표에서 깔끔히 맞지 않는 코드 (204 기타 화학제품)
        ind["dartT"]["282620"] = "20499"
        by_t["282620"]["dk"] = by_t["282620"]["dk"].replace("봉제의복 제조업", NAMES["204"])
        if break_it == "unclean_old_table":
            ind["mapSha"] = "000000000000"                       # 그 채움은 예전 표로 했어요 (그때는 ok 였을 수 있어요)
    elif break_it == "pref_in_dart":
        ind["dartT"]["005935"] = "26410"
        ind["dartT"].pop("376930")
    elif break_it == "pref_sector":
        by_t["005935"]["s"] = "machine"
    elif break_it == "pref_group":
        by_t["005935"]["ind"] = "telecom_eq"
    elif break_it == "pref_common":
        ind["prefT"]["005935"] = "000810"
    elif break_it == "name":
        by_t["282620"]["dk"] = by_t["282620"]["dk"].replace("봉제의복", "봉제 의복")
    elif break_it == "pref_words":
        by_t["005935"]["dk"] = by_t["005935"]["dk"].replace("통신 및 방송 장비", "통신장비")
    elif break_it == "missing":
        ind["dartT"]["123450"] = "26410"
        ind["dartT"].pop("376930")
    else:
        ind["dart"] = 50
    bad = V.ind_fill_bad(stocks, ind, NAMES, MAP, SHA)
    assert len(bad) == 1 and why in bad[0]["why"] and bad[0]["num"] is num, bad
    rows, rep = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    assert rows[V.IND_FILL_CHECK][3] == ("FAIL" if num else "WARN") and why in rows[V.IND_FILL_CHECK][1]
    assert any(t == f"{V.IND_FILL_CHECK}: 남은 틀린 값" for t, _ in rep.details)


def test_gate_passes_a_clean_fill_and_names_dart_stocks_in_the_carry_row():
    stocks, ind, _ = filled()
    rows, rep = gate({"stocks": stocks, "indSrc": dict(ind, left=0), "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    assert rows[V.IND_FILL_CHECK][3] == "PASS" and rows[V.IND_FILL_CHECK][1] == "DART 45종목 · 우선주 2 · 되돌림 0"
    assert rows["국내 업종 글자 없는 종목 (경고만)"][3] == "PASS" and not rep.failed
    carry = rows["국내 업종 이어 쓴 종목 (경고만)"]
    assert carry[3] == "WARN" and "DART 회사 정보로 채움 45 (002690 동일제강, 005360 모나미" in carry[1]


def test_gate_warns_without_a_drop_record_or_a_readable_table(monkeypatch):
    stocks, ind, _ = filled()
    rows, rep = gate({"stocks": stocks, "indSrc": ind})                       # 기록 없음 (이 PR 의 첫 버전 시험 데이터)
    assert rows[V.IND_FILL_CHECK][3] == "WARN" and "되돌림 기록 없음" in rows[V.IND_FILL_CHECK][1] and not rep.failed

    def broken(**kw):
        raise ValueError("깨짐")
    monkeypatch.setattr(V, "load_ksic_map_kr", broken)
    rows, rep = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    assert rows[V.IND_FILL_CHECK][3] == "WARN" and "표를 읽지 못해 우선주 · 짝만 확인" in rows[V.IND_FILL_CHECK][1] and not rep.failed
    # 표가 없어도 우선주 확인은 해요 (리뷰 5d): 우선주의 업종 키가 보통주와 다르면 그대로 실패
    next(x for x in stocks if x["t"] == "005935")["s"] = "machine"
    rows, rep = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    assert rows[V.IND_FILL_CHECK][3] == "FAIL" and "005935" in rows[V.IND_FILL_CHECK][1]


def test_gate_warns_when_stocks_are_still_without_words():
    stocks, ind, _ = filled()
    ind.update(left=3, dartMiss={"noCode": 2, "mapAmbig": 1, "fund": 1})
    rows, _ = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    r = rows["국내 업종 글자 없는 종목 (경고만)"]
    assert r[3] == "WARN" and r[1].startswith("3 (두 업종 체계가 갈리는 코드 1 · DART 업종 코드 없음 2) · 세지 않음: 펀드 1")
    ind["left"] = None
    rows, _ = gate({"stocks": stocks, "indSrc": ind, "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    assert rows["국내 업종 글자 없는 종목 (경고만)"][3] == "WARN"


def test_old_files_keep_their_old_behaviour():
    """dartT 가 없는 발행본 (이 PR 전 · 라이브 관문 · 감시): 두 줄 모두 예전처럼 건너뛰어요."""
    data = {"stocks": [stock("282620")], "indSrc": {"v": 1, "desc": 2769, "carried": 0, "none": 63, "newNone": 1, "asOf": "2026-11-19",
                                                     "from": "KRX-DESC"}}
    rows, rep = gate(data)
    assert rows[V.IND_FILL_CHECK][3] == "SKIP" and rows["국내 업종 글자 없는 종목 (경고만)"][3] == "SKIP"
    assert rows["국내 업종 이어 쓴 종목 (경고만)"][3] == "PASS" and not rep.failed


# ── 7. 집합 투자업 · 10차 번호 ────────────────────────────────────────
def test_fund_industry_matches_both_spellings():
    """KRX 글자는 '집합투자업', 11차 표는 '집합 투자업' — 펀드 확인 로그(fetch_korea)와 채우기가 둘 다 알아봐요."""
    assert NAMES["642"] == "신탁업 및 집합 투자업" and NAMES["64201"] == "신탁업 및 집합 투자업" and F.KR_FUND_KSIC == V.IND_FUND_KSIC == "642"
    for text in ("신탁업 및 집합투자업", "신탁업 및 집합 투자업 · KOSPI 상장", "신탁업 및 집합투자업 · 주요제품: 증권투자회사 · KOSPI 상장"):
        assert F.is_fund_industry(text)
    for text in (None, "", "신탁업", "기타 금융업 · KOSPI 상장", "KOSPI 상장 · 시가총액 1조원"):
        assert not F.is_fund_industry(text)
    src = inspect.getsource(F.fetch_korea)
    assert "is_fund_industry(r.get(\"dk\"))" in src and ".startswith(KR_FUND_INDUSTRY)" not in src


def test_fund_code_is_never_filled_as_a_company(capsys):
    """업종 코드가 642 (신탁업 및 집합 투자업) 인 종목은 회사로 채우지 않고 크게 남겨요 — 펀드인지 사람이 정해요 · 관문은 경고."""
    ksic = {"100000": "64201", "200000": "64209", "300000": "642", "282620": "14199"}
    stocks = grouped([stock("100000"), stock("200000"), stock("300000"), stock("282620")], ksic)
    fill, miss = F.kr_ind_dart_plan(stocks, list(ksic), ksic, MAP)
    assert list(fill) == ["282620"] and miss == {"mapFund": ["100000", "200000", "300000"]}
    ind = {"from": "KRX-DESC"}
    rec = F.kr_ind_fill(stocks, list(ksic), ksic, MAP, ind)
    assert ind["dartT"] == {"282620": "14199"} and ind["left"] == 3 and ind["dartMiss"] == {"mapFund": 3}
    assert all(s["dk"] == "KOSDAQ 상장 · 시가총액 200억원" and s["s"] == "etc" for s in stocks[:3])
    out = capsys.readouterr().out
    assert "100000 100000 (64201 신탁업 및 집합 투자업 · fund)" in out and "KR_LISTED_FUNDS" in out
    assert not any(F.is_fund_industry(s["dk"]) for s in stocks)
    rows, rep = gate({"stocks": stocks, "indSrc": dict(ind, carried=0, asOf="2026-11-19", newNone=0), "ownDrop": {"indFill": rec}})
    r = rows["국내 업종 글자 없는 종목 (경고만)"]
    assert r[3] == "WARN" and "집합 투자업 코드 (펀드일 수 있어 채우지 않음) 3" in r[1]
    assert rows[V.IND_FILL_CHECK][3] == "PASS" and not rep.failed


def test_word_check_compares_krx_words_with_dart_names(capsys):
    """10차 번호로 남은 DART 기록은 관문이 잡지 못해요 — KRX 글자와 DART 코드가 둘 다 있는 종목을 맞춰 보고 다르면 로그로만 (막지 않아요)."""
    stocks = [stock(t, dk=f"{FX['krxText'][t]} · KOSPI 상장") for t in FX["sample"]]
    ksic = {t: code_of(t) for t in FX["sample"]}
    n, diff = F.kr_ind_word_check(stocks, ksic, NAMES)
    assert (n, diff) == (40, [])                                   # 기록한 40곳 — 띄어쓰기만 다른 것은 같다고 봐요
    odd = [stock("100000", dk="과자류 제조업 · KOSDAQ 상장"), stock("200000", dk="반도체 제조업 · KOSDAQ 상장"),
           stock("300000", dk="반도체 제조업 · KOSDAQ 상장"), stock("005935", dk="반도체 제조업 · KOSPI 상장"),
           stock("400000"), stock("500000", dk="반도체 제조업 · KOSDAQ 상장"), stock("600000", dk="반도체 제조업", etf=True)]
    k2 = {"100000": "10712", "200000": "26112", "300000": "999", "005935": "264", "400000": "264", "600000": "264"}
    n, diff = F.kr_ind_word_check(odd, k2, NAMES, skip={"200000"})
    assert n == 2 and diff == ["100000 100000: 과자류 제조업 ≠ " + NAMES["107"] + " (10712)", "300000 300000: 반도체 제조업 ≠ 표에 없음 (999)"]
    F.kr_ind_fill(grouped(odd + [stock("282620")], {"282620": "14199"}), ["282620"], dict(k2, **{"282620": "14199"}), MAP, {})
    out = capsys.readouterr().out
    assert "  !! 업종 글자 확인 (막지 않아요): KRX · 이어 쓴 업종 글자와 DART 업종 코드의 11차 소분류 이름이 다른 종목 2 / 3 (띄어쓰기 빼고)" in out
    F.kr_ind_fill(stocks, [], ksic, MAP, {})
    assert "· 업종 글자 확인 (막지 않아요): KRX · 이어 쓴 업종 글자와 DART 업종 코드의 11차 소분류 이름이 다른 종목 0 / 40 (띄어쓰기 빼고)" \
        in capsys.readouterr().out


# ── 8. 데이터 출처 (답 3) ───────────────────────────────────────────
def test_data_sources_page_credits_the_classification():
    """Jack, 2026-11-19 (답 3): "업종 분류: 통계청 한국표준산업분류" — 데이터 출처 목록은 하나 (예전 뱁새 정보 탭 · 2.0 ☰ 이 열어요)."""
    info = read("src/info.jsx")
    row = '["통계청 한국표준산업분류", "업종 분류"]'          # 이 목록의 모든 줄처럼 왼쪽 출처 · 오른쪽 받는 데이터
    assert info.count(row) == 1 and '["금융감독원 DART", "재무제표' in info
    i = info.index('<Card id="info-sources">')
    assert i < info.index(row) < info.index('<div id="info-credits"', i)
    assert 'sources: OLD_APP + "#info=sources"' in read("src/v2/routes.js")
    appr = read("docs/tasks/v18.3-approved-in-chat.md")
    assert "| 업종 분류: 통계청 한국표준산업분류 | Jack, 2026-11-19 (answer 3:" in appr
    html = read("baepsae.html")
    assert html.count('["통계청 한국표준산업분류","업종 분류"]') == 1                # 빌드한 예전 뱁새 (다시 빌드했어요)


# ── 9. 리뷰 (2026-11-19): 우선주는 비교군 · 중간값에서 빼요 · 표를 읽지 못한 날 · 바뀐 표 ───────────────
def old_bundle():
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "entry.js"), "w", encoding="utf-8") as f:
        f.write(f"export * as DT from {json.dumps(os.path.join(ROOT, 'src/detail.jsx'))};\n"
                f"export * as DJ from {json.dumps(os.path.join(ROOT, 'src/data.js'))};\n")
    r = subprocess.run([os.path.join(ROOT, "node_modules", ".bin", "esbuild"), os.path.join(tmp, "entry.js"), "--bundle", "--format=esm",
                        "--platform=node", "--jsx=automatic", "--loader:.js=jsx", "--charset=utf8", f"--outfile={tmp}/b.mjs",
                        "--log-level=error", "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
    return tmp


def today_from(main):
    """main 의 data.json 에 이 PR 의 채우기를 돌린 오늘 데이터 (우선주가 보통주를 따라요)."""
    today = copy.deepcopy(main)
    kr = [s for s in today["stocks"] if s.get("cls") == "kr"]
    F.kr_ind_fill(kr, no_text_of(kr), {}, MAP, today["indSrc"], over=TABLES["over"], names=NAMES, map_sha=SHA)
    return today


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_old_app_peers_and_medians_match_main(tmp_path):
    """리뷰 1 (2026-11-19): 예전 뱁새의 같은 섹터 비교(12곳)와 간단 점검의 업종 중간값 — 오늘 데이터(우선주가 보통주의 업종)에서도 main 의
    코드 · main 의 data.json 과 같아요. 기타만 예외: main 에서 기타였던 우선주가 기타를 떠나 그 자리를 기타 회사가 채워요 (main 의 기타 목록에서
    우선주를 뺀 것과 같아요)."""
    main = json.loads(read("data.json"))
    today = today_from(main)
    assert today["indSrc"]["pref"] >= 50
    (tmp_path / "main.json").write_text(json.dumps(main, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "today.json").write_text(json.dumps(today, ensure_ascii=False), encoding="utf-8")
    code = """
import * as B from './b.mjs'; import fs from 'fs';
const { DT, DJ } = B; console.warn = () => {};
const main = JSON.parse(fs.readFileSync(process.argv[1], 'utf8')), today = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const sm = DJ.mergeStocks(DT.BASE_STOCKS, main.stocks), sn = DJ.mergeStocks(DT.BASE_STOCKS, today.stocks);
const mainIdx = {}; sm.forEach((s) => { (mainIdx[s.s] || (mainIdx[s.s] = [])).push(s); });      // main 의 코드 그대로 (모든 종목)
const newIdx = DT.sectorIndex(sn), byT = new Map(sn.map((s) => [s.t, s]));
const out = { n: 0, same: 0, etc: 0, bad: [], prefInPeers: 0, mainPrefOutsideEtc: 0, prefMoved: 0 };
for (const s of sm) {
  if (DT.isPrefStock(s)) { if (s.s !== 'etc') out.mainPrefOutsideEtc++; continue; }
  const x = byT.get(s.t), got = DT.peersOf(newIdx, x);
  const want = s.s === 'etc' ? (mainIdx.etc || []).filter((p) => !DT.isPrefStock(p)).slice(0, DT.PEER_N) : (mainIdx[s.s] || []).slice(0, DT.PEER_N);
  out.n++; if (s.s === 'etc') out.etc++;
  if (got.some(DT.isPrefStock)) out.prefInPeers++;
  const same = x.s === s.s && got.map((p) => p.t).join() === want.map((p) => p.t).join()
    && JSON.stringify(DT.peerMedians(got)) === JSON.stringify(DT.peerMedians(want));
  if (same) out.same++; else if (out.bad.length < 5) out.bad.push(s.t);
  if (s.s !== 'etc' && JSON.stringify(DT.peerMedians(got)) !== JSON.stringify(DT.peerMedians((mainIdx[s.s] || []).slice(0, 12)))) out.bad.push('med:' + s.t);
}
out.prefMoved = sn.filter((s) => DT.isPrefStock(s) && s.s !== 'etc').length;
console.log(JSON.stringify(out));
"""
    r = subprocess.run([NODE, "--input-type=module", "-e", code, str(tmp_path / "main.json"), str(tmp_path / "today.json")],
                       cwd=old_bundle(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["n"] > 2000 and got["same"] == got["n"] and not got["bad"] and got["prefInPeers"] == 0, got
    assert got["mainPrefOutsideEtc"] == 0 and got["prefMoved"] == today["indSrc"]["pref"] and got["etc"] > 0


def test_corp_sector_medians_match_main():
    """기업분석 업종 통계 (corp.json sectors): 우선주가 보통주의 업종으로 옮겨도 중간값 · 사분위 · 성장률은 main 의 corp.json 과 같아요 —
    업종 수(n)는 우선주를 빼고, 업종 시가총액(mc)에만 우선주가 들어가요 (실제 시장 가치)."""
    corp = json.loads(read("corp.json"))
    today = today_from(json.loads(read("data.json")))
    s_of = {x["t"]: x.get("s") for x in today["stocks"] if x.get("cls") == "kr"}
    comps = [dict(c, s=s_of.get(c["t"], c["s"])) for c in copy.deepcopy(corp["companies"])]
    moved = [c for c in comps if F.is_preferred(c["t"]) and c["s"] != "etc"]
    assert len(moved) >= 50
    got, main = F.corp_sector_stats(comps), corp["sectors"]
    assert set(got) == set(main)
    for sec in main:
        for k in ("nG", "g", "rev0", "opm", "roe", "perQ", "pbrQ", "evEQ", "evRQ", "pcfQ"):
            assert got[sec][k] == main[sec][k], (sec, k)
        n_pref_main = sum(1 for c in corp["companies"] if c["s"] == sec and F.is_preferred(c["t"]))
        assert got[sec]["n"] == main[sec]["n"] - n_pref_main, sec
        cap_moved = sum(c["cap"] or 0 for c in moved if c["s"] == sec) - sum(c["cap"] or 0 for c in corp["companies"]
                                                                              if c["s"] == sec and F.is_preferred(c["t"]))
        assert abs(got[sec]["mc"] - main[sec]["mc"] - cap_moved) < 0.2, sec
    # 우선주는 업종 비교의 값이 하나도 없어요 (그래서 중간값이 움직이지 않아요) · 기업분석의 업종 비교 · 기업 비교 후보에서도 빼요
    assert all(c.get(k) in (None, [None, None, None]) for c in moved for k in ("per", "pbr", "opm", "roe", "g3", "rev", "evE", "evR", "pcf"))
    cj = read("src/corp.jsx")
    assert "data.companies.filter((x) => x.s === c.s && !isPrefCode(x.t))" in cj
    assert "x.s === base?.s && x.t !== baseT && !isPrefCode(x.t)" in cj


def test_unreadable_tables_skip_the_fill_but_not_the_preferred_shares(capsys):
    """리뷰 3: 업종 표를 읽지 못해도 하루 발행은 멈추지 않아요 — DART 로 채우지 않고(크게) 우선주는 보통주를 따라요 · 관문은 경고."""
    main = inspect.getsource(F.main)
    i = main.index("ksic_names = load_ksic_names()")
    assert "try:" in main[i - 120:i] and "except Exception as e:" in main[i:i + 400]
    stocks, ksic = fill_case()
    ind = {"from": "KRX-DESC"}
    rec = F.kr_ind_fill(stocks, no_text_of(stocks), ksic, None, ind, over=TABLES["over"], table_err="ValueError")
    assert rec == {"n": 0, "rows": []} and ind["dart"] == 0 and ind["pref"] == 2 and ind["dartErr"] == "table:ValueError"
    assert ind["dartMiss"] == {"fund": 1, "noTable": 57} and ind["left"] == 57 and "mapSha" not in ind
    assert next(x for x in stocks if x["t"] == "005935")["s"] == "semi"
    rows, rep = gate({"stocks": stocks, "indSrc": dict(ind, carried=0, asOf="2026-11-19", newNone=0), "ownDrop": {"indFill": rec}})
    assert rows[V.IND_FILL_CHECK][3] == "WARN" and "채우기 고장 table:ValueError" in rows[V.IND_FILL_CHECK][1] and not rep.failed
    r = rows["국내 업종 글자 없는 종목 (경고만)"]
    assert r[3] == "WARN" and "업종 표를 읽지 못해 채우지 않음 57" in r[1] and "채우기 실패 table:ValueError" in r[1]


def test_a_fill_made_with_an_older_table_only_warns():
    """리뷰 4: 라이브 관문이 지난 발행본을 다시 볼 때 — 그 채움이 쓴 표(indSrc.mapSha)가 지금 표와 다르면, 지금 표로 깔끔하지 않은 코드는 경고만.
    파일 안에서 틀린 것(짝 · 이름 · 집합 투자업 · 우선주)은 그대로 실패."""
    stocks, ind, _ = filled()
    by_t = {s["t"]: s for s in stocks}
    ind["dartT"]["282620"] = "20499"                                # 지금 표에서는 ambiguous (204)
    by_t["282620"]["dk"] = by_t["282620"]["dk"].replace("봉제의복 제조업", NAMES["204"])
    for sha, status in ((SHA, "FAIL"), ("000000000000", "WARN"), (None, "WARN")):
        ind2 = dict(ind, mapSha=sha) if sha else {k: v for k, v in ind.items() if k != "mapSha"}
        rows, _ = gate({"stocks": stocks, "indSrc": ind2, "ownDrop": {"indFill": {"n": 0, "rows": []}}})
        assert rows[V.IND_FILL_CHECK][3] == status, (sha, rows[V.IND_FILL_CHECK])
    by_t["282620"]["s"] = "bank"                                    # 짝이 틀리면 표와 상관없이 실패
    rows, _ = gate({"stocks": stocks, "indSrc": dict(ind, mapSha="000000000000"), "ownDrop": {"indFill": {"n": 0, "rows": []}}})
    assert rows[V.IND_FILL_CHECK][3] == "FAIL"
