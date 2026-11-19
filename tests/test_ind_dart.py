# -*- coding: utf-8 -*-
"""2026-11-19: 업종 글자가 없는 국내 종목을 DART 기업개황 업종 코드로 채워요 (Jack: "Later, new listings take their industry from DART's
company records." · "move the DART company-record industry mapping up"). 네트워크 없음.

픽스처 tests/fixtures/ind_dart/company_samples.json — 2026-11-19 에 받은 DART company.json 150곳 (대표자 이름 · 주소 등은 지웠어요):
  gap        11-19 발행본에서 업종 글자가 없던 보통주 57 (모두 업종 코드가 있었어요)
  sample     업종 글자가 있는 보통주 40 (시드 20261119) · prefCommons 업종 글자 없는 우선주 62의 보통주 53
  krxText    그 93곳의 KRX-DESC 업종 글자 (DART 코드 앞 3자리의 11차 이름과 띄어쓰기만 달라야 해요)
"""
import datetime as dt
import inspect
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

FX = json.load(open(os.path.join(ROOT, "tests", "fixtures", "ind_dart", "company_samples.json"), encoding="utf-8"))
NAMES = V.load_ksic_names()
TABLES = F.load_industry_tables()
KMAP, GROUPS = V.load_ksic_map()


def code_of(t):
    return FX["companies"][t]["induty_code"]


def stock(t, dk="KOSDAQ 상장 · 시가총액 200억원", s="etc", **kw):
    return dict({"t": t, "nk": FX.get("gapNames", {}).get(t, t), "cls": "kr", "s": s, "dk": dk, "etf": False}, **kw)


def sq(x):
    return x.replace(" ", "")


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


# ── 2. 계획 (순수 함수) ─────────────────────────────────────────────
def test_today_all_57_common_stocks_without_words_fill():
    """11-19 발행본에서 업종 글자가 없던 보통주 57곳 — 기록한 업종 코드로 모두 채워져요 (우선주 62 · 펀드는 그대로)."""
    gap = FX["gap"]
    stocks = [stock(t) for t in gap] + [stock(t, s="etc") for t in FX["prefGap"]] + [stock("088980", etf=True)]
    ksic = {t: code_of(t) for t in gap}
    fill, miss = F.kr_ind_dart_plan(stocks, [s["t"] for s in stocks], ksic, NAMES, TABLES["kmap"])
    assert len(gap) == 57 and sorted(fill) == sorted(gap)
    assert miss == {"pref": sorted(FX["prefGap"]), "fund": ["088980"]} and len(FX["prefGap"]) == 62
    assert fill["282620"] == ("봉제의복 제조업", "14199") and fill["376930"] == ("의료용 기기 제조업", "27112")


def test_plan_reasons_when_it_cannot_fill():
    stocks = [stock(t) for t in ("100000", "200000", "300000", "400000", "500000", "600000")] + [stock("005935")]
    ksic = {"100000": "264", "200000": "99999", "300000": "26", "500000": "  ", "600000": "58222", "005930": "264"}
    kmap = {k: v for k, v in TABLES["kmap"].items() if not "58222".startswith(k)}       # 600000: 그룹으로 이어지지 않는 코드
    fill, miss = F.kr_ind_dart_plan(stocks, [s["t"] for s in stocks] + ["999990"], ksic, NAMES, kmap)
    assert fill == {"100000": ("통신 및 방송장비 제조업", "264")}
    assert miss == {"noName": ["200000", "300000"], "noCode": ["400000", "500000"], "noGroup": ["600000"], "pref": ["005935"]}
    # 999990: 발행하지 않는 종목 (가격 이력이 짧은 새 상장 등) — 세지 않아요


def test_plan_only_looks_at_stocks_without_words():
    """no_text 에 없는 종목(KRX 글자 · 이어 쓴 글자가 있는 종목)은 계획에 들어오지 않아요."""
    stocks = [stock("100000"), stock("200000", dk="반도체 제조업 · KOSDAQ 상장")]
    fill, _ = F.kr_ind_dart_plan(stocks, ["100000"], {"100000": "264", "200000": "264"}, NAMES, TABLES["kmap"])
    assert list(fill) == ["100000"]


# ── 3. 적용 · 출처 · 로그 ─────────────────────────────────────────────
def test_apply_never_overwrites_existing_words():
    a = stock("100000")                                                  # 글자 없음 → 채워요
    b = stock("200000", dk="반도체 제조업 · 주요제품: 메모리 · KOSPI 상장", s="semi")     # KRX · 이어 쓴 글자 → 그대로
    c = stock("300000", s="build")                                        # 업종 키가 이미 있음 (지난 data.json 의 s) → 키는 그대로
    d = stock("400000", dk="알 수 없는 글")                               # 읽지 못하는 설명 → 그대로
    e = stock("500000", dk=None)                                          # 설명이 없던 종목 → 이름만
    fill = {t: ("통신 및 방송장비 제조업", "264") for t in ("100000", "200000", "300000", "400000", "500000")}
    before = json.dumps([b, d])
    done = F.kr_ind_dart_apply([a, b, c, d, e], fill)
    assert done == {"100000": "264", "300000": "264", "500000": "264"} and json.dumps([b, d]) == before
    assert a["dk"] == "통신 및 방송장비 제조업 · KOSDAQ 상장 · 시가총액 200억원" == F.kr_desc_text("통신 및 방송장비 제조업", "", "KOSDAQ", 0.02)
    assert F.kr_desc_parse(a["dk"]) == ("통신 및 방송장비 제조업", "")
    assert a["s"] == F.map_sector_kr("통신 및 방송 장비 제조업", "") == "machine"
    assert c["s"] == "build" and c["dk"].startswith("통신 및 방송장비 제조업 · ")
    assert e["dk"] == "통신 및 방송장비 제조업"
    # 주요제품만 있던 설명: 업종 이름을 앞에 (kr_desc_text 순서) · 업종 키는 주요제품까지 봐요 (KRX 와 같은 규칙)
    f = stock("600000", dk="주요제품: 반도체 · KOSDAQ 상장")
    F.kr_ind_dart_apply([f], {"600000": ("통신 및 방송장비 제조업", "264")})
    assert f["dk"] == "통신 및 방송장비 제조업 · 주요제품: 반도체 · KOSDAQ 상장" and f["s"] == "semi"


def test_records_the_source_and_logs_loudly(capsys):
    stocks = [stock("282620"), stock("376930"), stock("100000"), stock("005935"), stock("088980", etf=True)]
    ind = {"v": 1, "desc": 0, "carried": 2354, "none": 5, "newNone": 2, "asOf": "2026-11-17", "from": "KRX-DESC + prev"}
    done = F.kr_ind_dart(stocks, [s["t"] for s in stocks], {"282620": "14199", "376930": "27112"}, NAMES, TABLES["kmap"], ind)
    assert done == {"282620": "14199", "376930": "27112"}
    assert ind["dart"] == 2 and ind["dartT"] == {"282620": "14199", "376930": "27112"} and ind["left"] == 1
    assert ind["dartMiss"] == {"fund": 1, "noCode": 1, "pref": 1} and ind["from"] == "KRX-DESC + prev + DART"
    assert ind["carried"] == 2354 and ind["none"] == 5          # 예전 칸은 그대로
    out = capsys.readouterr().out
    assert "  !! 업종 DART 회사 정보로 채움 2 / 3, 못 채움 1 (DART 업종 코드 없음 1: 100000 100000)" in out
    assert "우선주 1" in out and "펀드 1" in out and "282620 기도산업 봉제의복 제조업 (14199)" in out
    # 채울 것이 없는 날: 조용한 한 줄 · from 은 그대로
    ind2 = {"from": "KRX-DESC"}
    F.kr_ind_dart([stock("100000", dk="반도체 제조업 · KOSDAQ 상장")], [], {}, NAMES, TABLES["kmap"], ind2)
    assert ind2 == {"from": "KRX-DESC", "dart": 0, "dartT": {}, "left": 0, "dartMiss": {}}
    assert "· 업종 DART 회사 정보로 채움 0 / 0, 못 채움 0" in capsys.readouterr().out


def test_a_broken_fill_never_stops_the_run(monkeypatch, capsys):
    """채우기가 고장 나도 예외 없이 그대로 발행 · 크게 남기고 관문이 경고해요 · 바꾼 종목 없음."""
    a = stock("282620")
    before = dict(a)

    def boom(*args, **kw):
        raise TypeError("고장")
    monkeypatch.setattr(F, "map_sector_kr", boom)            # 적용 단계 한가운데서 멈춰요
    ind = {"from": "KRX-DESC"}
    assert F.kr_ind_dart([a], ["282620"], {"282620": "14199"}, NAMES, TABLES["kmap"], ind) == {}
    assert a == before and ind == {"from": "KRX-DESC", "dart": 0, "dartT": {}, "left": None, "dartMiss": {}, "dartErr": "TypeError"}
    assert "  !! 업종 DART 채우기 실패 (TypeError: 고장)" in capsys.readouterr().out
    rows, rep = gate({"stocks": [a], "indSrc": dict(ind, carried=0, asOf="2026-11-19", newNone=0)})
    r = rows["국내 업종 글자 없는 종목 (경고만)"]
    assert r[3] == "WARN" and "채우기 실패 TypeError" in r[1] and not rep.failed


def test_dart_filled_words_are_not_carried_as_krx_words():
    """지난 발행본이 DART 로 채운 종목은 이어 쓰지 않아요 — 오늘도 DART 로 다시 채우고 dartT 에 남아요 (출처가 KRX 로 바뀌지 않게)."""
    prev = {"publishedAt": "2026-11-19T08:30:00+09:00", "indSrc": {"carried": 1, "asOf": "2026-11-17", "dartT": {"282620": "14199"}},
            "stocks": [{"t": "282620", "cls": "kr", "dk": "봉제의복 제조업 · KOSDAQ 상장 · 시가총액 614억원"},
                       {"t": "005930", "cls": "kr", "dk": "통신 및 방송 장비 제조업 · 주요제품: 반도체 · KOSPI 상장"}]}
    pdesc, day, bad = F.kr_prev_desc(prev)
    assert pdesc == {"005930": ("통신 및 방송 장비 제조업", "반도체")} and day == "2026-11-17" and bad == 0
    out, carried, none = F.kr_desc_carry({}, pdesc, {"282620", "005930"})
    assert carried == ["005930"] and none == ["282620"]


# ── 4. DART 호출: 새로 부르지 않아요 · 보관 · 실패 ──────────────────────────
def test_the_fill_makes_no_dart_calls(monkeypatch):
    """채우기는 fetch_ksic 가 이미 받은 코드만 써요 — 클라이언트를 받지 않고, 기업개황을 부르는 곳은 fetch_ksic 하나예요."""
    for fn in (F.kr_ind_dart, F.kr_ind_dart_plan, F.kr_ind_dart_apply):
        assert "client" not in inspect.signature(fn).parameters
    src = inspect.getsource(F)
    assert src.count(".company(") == 1 and ".company(" in inspect.getsource(F.fetch_ksic)
    main = inspect.getsource(F.main)
    assert main.index("fetch_ksic, kr, client") < main.index("kr_ind_dart(kr,") < main.index("icnt = assign_industries(")

    def boom(*a, **k):
        raise AssertionError("network")
    monkeypatch.setattr(F.requests, "get", boom)
    assert F.kr_ind_dart([stock("282620")], ["282620"], {"282620": "14199"}, NAMES, TABLES["kmap"], {}) == {"282620": "14199"}


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
    fill, miss = F.kr_ind_dart_plan([stock("376930")], ["376930"], {}, NAMES, TABLES["kmap"])
    assert fill == {} and miss == {"noCode": ["376930"]}


# ── 5. 관문 ─────────────────────────────────────────────────────────
def gate_data(fill_codes, **ind_extra):
    stocks = []
    for t, code in fill_codes.items():
        stocks.append(stock(t, dk=f"{NAMES[code[:3]]} · KOSDAQ 상장 · 시가총액 200억원", s="textile"))
    ind = {"v": 1, "desc": 0, "carried": 0, "none": len(fill_codes), "newNone": 0, "asOf": "2026-11-19", "from": "KRX-DESC + DART",
           "dart": len(fill_codes), "dartT": dict(fill_codes), "left": 0, "dartMiss": {"pref": 62, "fund": 1}}
    ind.update(ind_extra)
    return {"stocks": stocks, "indSrc": ind}


def gate(data):
    rep = V.Report()
    V.check_px_src(rep, data, dt.date(2026, 11, 19))
    return {r[0]: r for r in rep.rows}, rep


def test_gate_passes_good_dart_values_and_names_them_in_the_warning():
    rows, rep = gate(gate_data({"282620": "14199", "376930": "27112"}))
    assert rows["국내 업종 DART 로 채운 값"][3] == "PASS" and rows["국내 업종 DART 로 채운 값"][1] == "2종목"
    assert rows["국내 업종 글자 없는 종목 (경고만)"][3] == "PASS"
    assert "세지 않음: 우선주 62 · 펀드 1" in rows["국내 업종 글자 없는 종목 (경고만)"][1]
    carry = rows["국내 업종 이어 쓴 종목 (경고만)"]
    assert carry[3] == "WARN" and "DART 회사 정보로 채움 2 (282620 기도산업, 376930 노을)" in carry[1]   # 이어 쓰지 않아도 DART 로 채우면 경고
    assert not rep.failed


@pytest.mark.parametrize("break_it, why", [
    ("name", "≠ 봉제의복 제조업"), ("code", "산업분류표에 없음"), ("group", "업종 그룹 없음"), ("count", "dart 3 ≠ dartT 2"),
    ("pref", "우선주"), ("missing", "발행한 국내 주식이 아님"), ("fund", "발행한 국내 주식이 아님")])
def test_gate_fails_a_bad_dart_value(break_it, why, monkeypatch):
    data = gate_data({"282620": "14199", "376930": "27112"})
    ind, st = data["indSrc"], {s["t"]: s for s in data["stocks"]}
    if break_it == "name":
        st["282620"]["dk"] = "봉제 의복 제조업 · KOSDAQ 상장"
    elif break_it == "code":
        ind["dartT"]["282620"] = "999"
    elif break_it == "group":
        monkeypatch.setattr(V, "load_ksic_map", lambda: ({k: v for k, v in KMAP.items() if not "14199".startswith(k)}, GROUPS))
    elif break_it == "count":
        ind["dart"] = 3
    elif break_it == "pref":
        ind["dartT"]["005935"] = "264"
        ind["dart"] = 3
        data["stocks"].append(stock("005935", dk="통신 및 방송장비 제조업 · KOSPI 상장"))
    elif break_it == "missing":
        ind["dartT"]["123450"] = "264"
        ind["dart"] = 3
    else:
        st["282620"]["etf"] = True
    rows, rep = gate(data)
    assert rows["국내 업종 DART 로 채운 값"][3] == "FAIL" and why in rows["국내 업종 DART 로 채운 값"][1]
    assert any(t == "국내 업종 DART 로 채운 값이 이상해요" for t, _ in rep.details)


def test_gate_warns_when_stocks_are_still_without_words():
    rows, _ = gate(gate_data({"282620": "14199"}, left=3, dartMiss={"noCode": 2, "noName": 1, "pref": 62}))
    r = rows["국내 업종 글자 없는 종목 (경고만)"]
    assert r[3] == "WARN" and r[1].startswith("3 (DART 업종 코드 없음 2 · 산업분류표에 없는 코드 1)")
    rows, _ = gate(gate_data({"282620": "14199"}, left=None))
    assert rows["국내 업종 글자 없는 종목 (경고만)"][3] == "WARN"


def test_gate_skips_publishes_from_before_the_dart_fill():
    data = gate_data({})
    for k in ("dart", "dartT", "left", "dartMiss"):
        data["indSrc"].pop(k)
    rows, rep = gate(data)
    assert rows["국내 업종 DART 로 채운 값"][3] == "SKIP" and rows["국내 업종 글자 없는 종목 (경고만)"][3] == "SKIP"
    assert rows["국내 업종 이어 쓴 종목 (경고만)"][3] == "PASS" and "DART" not in rows["국내 업종 이어 쓴 종목 (경고만)"][1]


def test_gate_fails_when_the_table_cannot_be_read(monkeypatch):
    def broken():
        raise ValueError("깨짐")
    monkeypatch.setattr(V, "load_ksic_names", broken)
    rows, _ = gate(gate_data({"282620": "14199"}))
    assert rows["국내 업종 DART 로 채운 값"][3] == "FAIL" and "표를 읽지 못함" in rows["국내 업종 DART 로 채운 값"][1]
