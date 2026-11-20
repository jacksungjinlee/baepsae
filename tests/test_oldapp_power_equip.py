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


# ── 리뷰 (2026-11-20): 가운뎃점 꼴 · 실행마다 남기는 줄 · 지난 공시 줄의 업종 키 ─────────────────
DOTS = ["·", "ㆍ", "・", "•", "‧", "∙", "･", "."]


@pytest.mark.parametrize("dot", DOTS, ids=[hex(ord(d)) for d in DOTS])
def test_any_middle_dot_in_the_281_name_still_lands_in_elec(dot):
    for spaced in (True, False):
        sep = f" {dot} " if spaced else dot
        name = f"전동기, 발전기 및 전기 변환{sep}공급{sep}제어 장치 제조업"
        assert F.map_sector_kr_raw(name, "") == "utility" and F.map_sector_kr(name, "") == "elec", name
        assert F.map_sector_kr(name, "송배전용금구류,변압기") == "elec" and F.map_sector_kr(name, "반도체 및 디스플레이 모션시스템") == "semi"
    assert F.sector_name_key("전동기,\u00a0발전기 및 전기 변환ㆍ공급ㆍ제어 장치 제조업") == F.sector_name_key(NAMES["281"])
    for gap in ("\u3000", "\t", "\u00a0", "  "):                 # 전각 칸 · 탭 · 줄바꿈 없는 칸 · 두 칸
        name = f"전동기,{gap}발전기{gap}및{gap}전기{gap}변환ㆍ공급ㆍ제어{gap}장치{gap}제조업"
        assert F.sector_name_key(name) == F.sector_name_key(NAMES["281"]) and F.map_sector_kr(name, "") == "elec", repr(gap)
    assert F.map_sector_kr("절연선\u3000및\t케이블 제조업", "전력선,통신케이블") == "elec"
    assert F.map_sector_kr("구조용 금속제품, 탱크 및 증기발생기 제조업", "") == F.map_sector_kr_raw("구조용 금속제품, 탱크 및 증기발생기 제조업", "")


def test_raw_rule_is_the_old_rule_everywhere_else():
    """map_sector_kr_raw 는 고치기 전의 규칙 그대로 (이 파일의 raw_key 와 같아요) · map_sector_kr 은 그 위에 utility → elec 만."""
    for c, name in NAMES.items():
        if len(c) == 3:
            for prod in ("", "전력선", "도시가스", "반도체"):
                assert F.map_sector_kr_raw(name, prod) == raw_key(name, prod), (c, prod)


def kr(t, nk, s, ind, dk):
    return {"t": t, "nk": nk, "cls": "kr", "s": s, "ind": ind, "dk": dk}


def test_run_log_counts_the_moved_makers_and_shouts_when_one_is_left_in_utility():
    dk = KRX_281 + " · 주요제품: 변압기, 고압차단기, 회전기, 배전반 등 · KOSPI 상장 · 시가총액 15.0조원"
    odd = "전동기, 발전기 및 전기 변환 / 공급 / 제어 장치 제조업 · 주요제품: 변압기 · KOSPI 상장 · 시가총액 1.0조원"   # 다른 꼴의 글자
    stocks = [kr("267260", "HD현대일렉트릭", "elec", "power_eq", dk),
              kr("298040", "효성중공업", "elec", "power_eq", KRX_281 + " · KOSPI 상장 · 시가총액 16.7조원"),
              kr("336260", "두산퓨얼셀", "elec", "power_eq", KRX_281 + " · 주요제품: 연료전지 · KOSPI 상장 · 시가총액 1.7조원"),   # 규칙이 옮긴 게 아님
              kr("33626K", "두산퓨얼셀1우", "elec", "power_eq", KRX_281 + " · KOSPI 상장 · 시가총액 607억원"),                  # 우선주는 세지 않아요
              kr("015760", "한국전력", "utility", "utility", "전기업 · 주요제품: 전력자원개발,발전,송전,전력용기자재확보 · KOSPI 상장 · 시가총액 16.2조원"),
              {"t": "AAPL", "cls": "us", "s": "utility", "ind": "power_eq"}]
    moved, stuck = F.power_eq_sector_report(stocks)
    assert moved == [("267260", "HD현대일렉트릭"), ("298040", "효성중공업")] and stuck == []
    lines = F.power_eq_sector_lines(moved, stuck)
    assert len(lines) == 1 and lines[0].startswith("· 예전 뱁새 업종: 전력기기 · 전선 제조사 2종목을") and "HD현대일렉트릭 · 효성중공업" in lines[0]
    stocks.append(kr("999990", "가상전기", "utility", "power_eq", odd))
    moved, stuck = F.power_eq_sector_report(stocks)
    assert len(moved) == 2 and stuck == [("999990", "가상전기", "전동기, 발전기 및 전기 변환 / 공급 / 제어 장치 제조업")]
    lines = F.power_eq_sector_lines(moved, stuck)
    assert len(lines) == 2 and lines[1].startswith("  !! 2.0 업종이 전력기기·전선(power_eq)인데 예전 뱁새 업종이 전기·가스·환경(utility)인 국내 종목 1: 999990 가상전기")
    assert F.power_eq_sector_lines([], [])[0].startswith("· 예전 뱁새 업종: 전력기기 · 전선 제조사 0종목을")


def test_the_main_run_logs_the_report_after_industries_are_set():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    main = src[src.index("    ind_drop = kr_ind_fill(kr,"):]
    assert main.index("power_eq_sector_lines(*power_eq_sector_report(kr))") < main.index("build_corp(kr,")
    assert main.index("power_eq_sector_lines(*power_eq_sector_report(kr))") < main.index("fetch_disclosures, kr,")


def test_carried_disclosure_rows_take_todays_sector():
    info = {"298040": {"t": "298040", "s": "elec"}, "005930": {"t": "005930", "s": "semi"}, "000001": {"t": "000001"},
            "000002": {"t": "000002", "s": "etc"}}
    rows = [{"rc": "R1", "t": "298040", "s": "utility"}, {"rc": "R2", "t": "298040", "s": "utility"},     # 진짜 → 진짜: 바꿔요
            {"rc": "R3", "t": "005930", "s": "semi"}, {"rc": "R4", "t": "005930", "s": "etc"},             # 기타 → 진짜: 바꿔요
            {"rc": "R5", "t": "123450", "s": "chem"},              # 오늘 데이터에 없는 종목: 그대로
            {"rc": "R6", "t": "000001", "s": "bio"},               # 오늘 업종이 비었어요 (기타): 진짜 업종은 그대로
            {"rc": "R7", "t": "005930"},                           # 업종 키가 없던 줄: 오늘 값
            {"rc": "R8", "t": "000002", "s": "etc"}, {"rc": "R9", "t": "000002"}]   # 기타 → 기타 · 없음 → 기타
    ch, kept = F.disc_rows_sector_now(rows, info)
    assert [r.get("s") for r in rows] == ["elec", "elec", "semi", "semi", "chem", "bio", "semi", "etc", "etc"]
    assert ch == {("utility", "elec"): 2, ("etc", "semi"): 1, (None, "semi"): 1, (None, "etc"): 1} and kept == {"bio": 1}
    lines = F.disc_sector_lines("내부자 거래", ch, kept)
    assert lines[0].startswith("· 내부자 거래 지난 줄 5건의 업종 키를 오늘 종목 값으로 바꿈 (utility→elec 2") and "없음→semi 1" in lines[0]
    assert lines[1] == "  !! 내부자 거래 지난 줄 1건은 오늘 업종이 기타(etc)라 원래 업종 키를 그대로 둬요 (오늘 업종 글자가 빈 종목 · bio 1)"
    assert F.disc_sector_lines("국민연금", *F.disc_rows_sector_now([], info)) == ["· 국민연금 지난 줄 0건의 업종 키를 오늘 종목 값으로 바꿈"]


def test_a_blank_industry_day_keeps_real_sectors_in_carried_rows():
    """업종 글자가 빈 날 (모든 종목 etc): 진짜 업종이 있던 줄은 그대로 · 기타였던 줄은 기타 · 한 줄도 기타로 내려가지 않아요."""
    rows = [{"t": "298040", "s": "elec"}, {"t": "005930", "s": "semi"}, {"t": "035420", "s": "etc"}, {"t": "000660", "s": "semi"}]
    info = {r["t"]: {"t": r["t"], "s": "etc"} for r in rows}
    ch, kept = F.disc_rows_sector_now(rows, info)
    assert [r["s"] for r in rows] == ["elec", "semi", "etc", "semi"] and not ch and kept == {"semi": 2, "elec": 1}
    assert F.disc_sector_lines("내부자 거래", ch, kept)[1].startswith("  !! 내부자 거래 지난 줄 3건은 오늘 업종이 기타(etc)라")
    info = {r["t"]: {"t": r["t"]} for r in rows}            # 업종 키가 아예 없는 날도 같아요
    assert F.disc_rows_sector_now(rows, info)[1] == {"semi": 2, "elec": 1}


class FakeDart:
    """가짜 DART: 공시 목록을 받지 못한 날 (지난 발행본의 줄을 그대로 이어 써요)."""
    down = None

    def get(self, endpoint, params):
        return None

    def raise_if_fatal(self):
        pass


def test_fetch_disclosures_moves_carried_rows_of_moved_makers(monkeypatch, tmp_path, capsys):
    """지난 disc.json 에 utility 로 남은 효성중공업 내부자 줄 · 국민연금 줄 → 오늘 종목의 elec (공시·수급 탭이 한 회사를 두 업종에 세지 않게)."""
    import datetime as dt
    import json
    prev = {"asOf": "2026-11-19", "newest": "2026-11-18", "listOk": True,
            "insider": [{"rc": "R1", "d": "20261110", "t": "298040", "nk": "효성중공업", "s": "utility", "q": -10, "role": "임원"},
                        {"rc": "R2", "d": "20261105", "t": "267260", "nk": "HD현대일렉트릭", "s": "etc", "q": 5, "role": "임원"},
                        {"rc": "R3", "d": "20261101", "t": "123450", "nk": "오늘없음", "s": "chem", "q": 1, "role": "임원"}],
            "nps": [{"d": "20261108", "t": "010120", "nk": "LS ELECTRIC", "s": "utility", "cap": 18.1, "rt": 7.1, "chg": 0.2}]}
    p = tmp_path / "disc.json"
    p.write_text(json.dumps(prev, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(F, "OUT_DISC", str(p))
    stocks = [{"t": t, "nk": nk, "cls": "kr", "s": "elec", "cap": 10.0, "price": 1.0}
              for t, nk in (("298040", "효성중공업"), ("267260", "HD현대일렉트릭"), ("010120", "LS ELECTRIC"))]
    out = F.fetch_disclosures(stocks, {"298040": "C1", "267260": "C2", "010120": "C3"}, dt.date(2026, 11, 20), FakeDart())
    assert [(r["rc"], r["s"]) for r in out["insider"]] == [("R1", "elec"), ("R2", "elec"), ("R3", "chem")]
    assert [(r["t"], r["s"]) for r in out["nps"]] == [("010120", "elec")]
    log = capsys.readouterr().out
    assert "· 내부자 거래 지난 줄 2건의 업종 키를 오늘 종목 값으로 바꿈 (" in log and "utility→elec 1" in log and "etc→elec 1" in log
    assert "· 국민연금 지난 줄 1건의 업종 키를 오늘 종목 값으로 바꿈 (utility→elec 1)" in log and "그대로 둬요 (오늘 업종 글자가" not in log
