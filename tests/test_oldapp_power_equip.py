# -*- coding: utf-8 -*-
"""2026-11-20 (Jack, "3. Yes"): "Old app, power-equipment makers. 25 of them (효성중공업, HD현대일렉트릭, LS ELECTRIC and others) sit in
전기·가스·환경. They show its line "요금은 정부가 정해요…", which is wrong for them. Move them to 전기전자 in a small separate PR?"

예전 뱁새 업종 키(s)는 KRX 업종 글자 + 주요제품에 fetch_data.map_sector_kr 의 키워드 규칙을 넣어 정해요. 전동기 · 발전기 제조업(KSIC 281)의
업종 글자에 '발전기' 가 있어 utility 키워드 '발전' 에 걸리고, 전선 회사(283)는 주요제품의 '전력선' 이 '전력' 에 걸렸어요. 이제 2.0 이
전력기기·전선(power_eq)으로 묶는 11차 소분류(281 · 283 · 284 · 289)의 업종 글자면 utility 대신 elec (전자·전기장비)이에요.
아래 27곳은 2026-11-20 발행본(pxDate 11-19)에서 utility 였던 회사의 업종 글자 · 주요제품 그대로예요 (281 25곳 + 283 2곳). 네트워크 없음.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

NAMES = V.load_ksic_names()
TABLES = F.load_industry_tables()
MAP = V.load_ksic_map_kr(names=NAMES)
KRX_281 = "전동기, 발전기 및 전기 변환 · 공급 · 제어 장치 제조업"     # KRX 글자 (11차 이름과 띄어쓰기만 달라요)
KRX_TEXT = {"281": KRX_281, "283": "절연선 및 케이블 제조업"}

# (종목코드, 이름, KSIC 소분류, 주요제품) — 2026-11-20 발행본에서 예전 뱁새 업종이 utility 였던 전력기기 · 전선 회사 전부
MOVED = [
    ("0008Z0", "에스엔시스", "281", "파워솔루션, 에코솔루션, 운항제어솔루션, MRO 솔루션"),
    ("0011T0", "채비", "281", "전기차 충전 서비스, 전기차 충전기"),
    ("007610", "선도전기", "281", "수배전반,중전기기 제조,도매/전기공사"),
    ("010120", "LS ELECTRIC", "281", "고압기기,저압기기,변압기,배전반,PLC,인버터,빌딩설비,공조기,건축배관,자동화기기 제조,동가공"),
    ("025540", "한국단자", "281", "전기변환장치(광커넥터,통신용콘넥터,정밀압착단자설계) 제조,무역(수출)"),
    ("027040", "서울전자통신", "281", "전자변성기, 무역업(트랜스포머자재)"),
    ("032820", "우리기술", "281", "시스템사업, 정보통신사업"),
    ("033100", "제룡전기", "281", "송배전용금구류,변압기"),
    ("037030", "파워넷", "281", "전력변환장치"),
    ("043200", "파루", "281", "온습도 조절기(에어쿨), 무인방제기(야호)"),
    ("048430", "유라테크", "281", "점화코일, 스파크플러그"),
    ("058610", "에스피지", "281", "소형 Geared Motor"),
    ("062040", "산일전기", "281", "유입, 몰드, 주상, 건식 변압기 등"),
    ("065710", "서호전기", "281", "항만크레인,구동전기장치"),
    ("068240", "다원시스", "281", "핵융합 전원장치, 플라즈마 전원장치, 태양광 CVD 전원장치, 산업용 특수정류기"),
    ("107640", "한중엔시에스", "281", "수냉식 냉각시스템 ESS Parts, 공랭식 ESS Module Parts, EV Module 및 내연기관 Parts"),
    ("119850", "지엔씨에너지", "281", "비상발전기, 소형열병합발전설비, 바이오가스발전설비"),
    ("160190", "하이젠알앤엠", "281", "전동기 및 발전기 (범용모터, 서보모터)"),
    ("189860", "서전기전", "281", "수배전반, 전력기기, 전기공사"),
    ("199820", "제일일렉트릭", "281", "PCB Assay, 배선기구, 분전반 등"),
    ("237750", "피앤씨테크", "281", "배전자동화단말장치"),
    ("267260", "HD현대일렉트릭", "281", "변압기, 고압차단기, 회전기, 배전반 등"),
    ("273640", "와이엠텍", "281", "계전기(EV Relay)"),
    ("298040", "효성중공업", "281", ""),
    ("388050", "지투파워", "281", "수·배전반, 태양광발전시스템, 인버터(PCS)"),
    ("000500", "가온전선", "283", "전력선,통신케이블 제조,도매,수출입"),
    ("001440", "대한전선", "283", "전력선,통신케이블,적산계기,스텐레스압연제품,광케이블,초고압선,알루미늄 제조,도매/전기공사"),
]

# 같은 업종 글자지만 주요제품으로 utility 보다 앞 키에 먼저 걸린 회사 — 그대로예요 (2026-11-20 발행본)
KEPT = [
    ("336260", "두산퓨얼셀", "281", "연료전지", "elec"),
    ("047310", "파워로직스", "281", "2차전지 보호회로 및 배터리팩, 카메라모듈", "battery"),
    ("153890", "져스텍", "281", "반도체 및 디스플레이 모션시스템", "semi"),
    ("053160", "프리엠스", "281", "건설장비용 전장품,제어기", "machine"),
    ("217590", "티엠씨", "283", "선박용케이블, 해양용케이블, 전력용케이블, 광케이블 등", "ship"),
    ("475430", "키스트론", "283", "전자부품용 와이어, 케이블용 와이어 등", "elec"),
    ("103590", "일진전기", "283", "", "etc"),
]

# 진짜 전기 · 가스 · 증기 · 폐기물 회사 (KSIC 35 · 38) — utility 그대로 (2026-11-20 발행본의 업종 글자 · 주요제품)
UTILITIES = [
    ("015760", "한국전력", "전기업", "전력자원개발,발전,송전,전력용기자재확보"),
    ("005090", "SGC에너지", "전기업", "증기, 전기, REC(신재생에너지공급인증서)"),
    ("036460", "한국가스공사", "연료용 가스 제조 및 배관공급업", "액화천연가스 공급,제조,도매,개발"),
    ("004690", "삼천리", "연료용 가스 제조 및 배관공급업", "도시가스 공급/부동산 임대"),
    ("071320", "지역난방공사", "증기, 냉·온수 및 공기조절 공급업", "집단에너지공급 및 전기,증기 생산,판매"),
    ("060150", "인선이엔티", "폐기물 처리업", "건축폐기물처리"),
    ("067900", "와이엔텍", "폐기물 처리업", "사업장폐기물중간및최종처리,전문건설,골재제조"),
]


def raw_key(sector_text, product_text=""):
    """고치기 전의 규칙 (SECTOR_RULES 키워드만) — 이 시험의 회사들이 정말 utility 키워드에 걸렸던 회사인지 보려고."""
    blob = f"{sector_text} {product_text}".replace(" ", "")
    return next((k for k, words in F.SECTOR_RULES for w in words if w in blob), "etc")


def test_the_27_were_utility_and_now_are_elec():
    assert len(MOVED) == 27 and len({t for t, *_ in MOVED}) == 27
    assert sum(1 for x in MOVED if x[2] == "281") == 25 and sum(1 for x in MOVED if x[2] == "283") == 2
    for t, nk, ksic, prod in MOVED:
        assert raw_key(KRX_TEXT[ksic], prod) == "utility", (t, nk)
        assert F.map_sector_kr(KRX_TEXT[ksic], prod) == "elec", (t, nk)


@pytest.mark.parametrize("t,nk,ksic,prod", MOVED, ids=[x[0] for x in MOVED])
def test_each_power_equipment_maker_lands_in_elec(t, nk, ksic, prod):
    """한 곳씩: KRX 글자 그대로 · 11차 이름(띄어쓰기 다름) · 띄어쓰기 없는 글자 모두 elec — 예전 뱁새 '전자·전기장비'."""
    name = NAMES[ksic]
    for sec in (KRX_TEXT[ksic], name, name.replace(" ", "")):
        assert F.map_sector_kr(sec, prod) == "elec", (t, nk, sec)
    assert "elec" in V.IND_SECTOR_KR["power_eq"] and F.ksic_group(ksic, TABLES["kmap"]) == "power_eq"


@pytest.mark.parametrize("t,nk,ksic,prod,want", KEPT, ids=[x[0] for x in KEPT])
def test_same_codes_with_an_earlier_key_keep_it(t, nk, ksic, prod, want):
    assert F.map_sector_kr(KRX_TEXT[ksic], prod) == want == raw_key(KRX_TEXT[ksic], prod), (t, nk)


@pytest.mark.parametrize("t,nk,sec,prod", UTILITIES, ids=[x[0] for x in UTILITIES])
def test_real_utilities_stay_utility(t, nk, sec, prod):
    assert F.map_sector_kr(sec, prod) == "utility", (t, nk)


def test_ksic_35_to_39_names_never_become_elec():
    """전기 · 가스 · 증기 · 수도 · 하수 · 폐기물 · 환경 정화 (11차 35–39) 이름은 어떤 주요제품과도 elec 으로 바뀌지 않아요."""
    codes = [c for c in NAMES if len(c) == 3 and c[:2] in ("35", "36", "37", "38", "39")]
    assert codes == sorted(codes) and len(codes) == 9
    for c in codes:
        for prod in ("", "전력", "발전설비", "도시가스", "폐기물처리", "환경설비", "증기"):
            assert F.map_sector_kr(NAMES[c], prod) == raw_key(NAMES[c], prod) != "elec", (c, prod)
    for c in ("352", "353", "360", "381", "382", "390"):
        assert F.map_sector_kr(NAMES[c], "") == "utility", c


def test_the_list_is_exactly_the_power_eq_codes():
    """SECTOR_ELEC_NOT_UTILITY = 2.0 이 전력기기·전선(power_eq)으로 묶는 11차 소분류 이름 (띄어쓰기 없이) — 표가 바뀌면 같이 바뀌어야 해요."""
    want = sorted(NAMES[c].replace(" ", "") for c in NAMES if len(c) == 3 and F.ksic_group(c, TABLES["kmap"]) == "power_eq")
    assert sorted(F.SECTOR_ELEC_NOT_UTILITY) == want and len(want) == 4
    assert {c for c in NAMES if len(c) == 3 and NAMES[c].replace(" ", "") in F.SECTOR_ELEC_NOT_UTILITY} == {"281", "283", "284", "289"}
    assert "utility" not in V.IND_SECTOR_KR["power_eq"]


def test_only_utility_results_of_those_names_change():
    """모든 11차 소분류 이름 × 여러 주요제품: 결과가 바뀌는 건 '그 넷의 이름 + utility' 뿐이고, 그때는 elec."""
    prods = ("", "전력선", "비상발전기", "환경설비", "증기", "반도체", "2차전지", "건설장비", "도시가스", "선박용케이블", "연료전지")
    n = 0
    for c, name in NAMES.items():
        if len(c) != 3:
            continue
        for prod in prods:
            raw, got = raw_key(name, prod), F.map_sector_kr(name, prod)
            if name.replace(" ", "") in F.SECTOR_ELEC_NOT_UTILITY and raw == "utility":
                assert got == "elec", (c, prod)
                n += 1
            else:
                assert got == raw, (c, prod, raw, got)
    assert n > 0


def test_mapping_table_row_281_follows_the_rule_and_still_is_not_filled():
    """data/ksic_map_kr.csv 는 규칙의 결과예요: 281 의 예전 뱁새 키는 elec. DART 로 새 상장사를 채우는 건 Jack 의 답에 없어서 그대로 안 채워요
    (ambiguous · 상태별 수는 그대로)."""
    assert MAP["281"]["s"] == "elec" and MAP["281"]["status"] == "ambiguous" and MAP["281"]["ind"] == ("power_eq",)
    assert "281" in V.KSIC_LENS_MISFIT and "elec" in MAP["281"]["why"] and "Jack" in MAP["281"]["why"]
    assert (MAP["283"]["s"], MAP["283"]["status"]) == ("etc", "none") and (MAP["284"]["s"], MAP["284"]["status"]) == ("etc", "none")
    assert (MAP["289"]["s"], MAP["289"]["status"]) == ("elec", "ok")


def test_the_stock_row_uses_the_rule_with_both_texts():
    """업종 글자가 있는 국내 종목의 업종 키는 KRX 업종 글자 + 주요제품으로 이 규칙을 불러요 · 업종 표(ksic_map_kr_rows)도 같은 규칙이에요.
    (업종 글자 없는 우선주는 보통주의 키를 따라요 — kr_ind_pref_copy.)"""
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert src.count("map_sector_kr(sec_txt, prod_txt)") == 1 and src.count('map_sector_kr(names[c], "")') == 1


def test_old_app_has_a_reading_line_for_elec_and_keeps_the_utility_line():
    """옮긴 회사는 '전자·전기장비' 의 업종 읽는 법을 보여요. utility 의 줄은 그대로 (진짜 유틸리티에 맞는 줄이에요). 새 문구 없음."""
    src = open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()
    assert 'elec:       { ko: "전자·전기장비"' in src and 'utility:    { ko: "전기·가스·환경"' in src
    lens = src.split("const LENS = {", 1)[1].split("};", 1)[0]
    assert re.search(r"^\s+elec:\s*\{ ko:", lens, re.M)
    assert 'utility:  { ko: "요금은 정부가 정해요. 실적보다 정책·규제 방향이 주가를 움직여요."' in lens
