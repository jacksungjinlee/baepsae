# -*- coding: utf-8 -*-
"""2026-11-19 (Jack, verbatim): "The 129 unconfirmed stocks: stop showing "이 종목의 데이터를 찾지 못했어요." Show each stock's last
confirmed close with its own date (the existing own-close mechanism), plus "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
It must never sit under today's date label without that line."

여기서 보는 것 (네트워크 없음 · 더한 시험만):
- 파이프라인: 2차 출처 날에 확인 못 한 국내 종목을 지난 발행본의 마지막 확인 종가로 (fetch_data.kr_own_close_carry) — 기준일 종가로 있던
  종목 → pxd = 그 발행본의 pxDate · 이미 pxd 로 있던 종목 → 같은 가격 · 같은 pxd · 나이 상한(KR_OWN_CLOSE_MAX_DAYS) 넘음 · 지난 발행본에
  없음 · 같은 기준일 → 싣지 않아요 · d1 은 없어요 · 그 가격으로 만든 숫자(PER · PBR · corp.json · EV)는 그 가격으로 · 1차 출처 날에는 국내
  pxd 가 생기지 않아요 · 파일을 쓰기 직전 관문과 같은 함수로 거르고 크게 남겨요 (Jack 의 규칙 2026-11-19)
- 관문: 국내 pxd 줄 (미국 pxd 줄과 같은 실패만) · 마지막 확인 종가 줄 (경고만) · 기록된 종목은 pxDate 공식 종가와 맞춰 보는 줄에서 빠지고
  (kr_own_codes) · 기록되지 않은 종목은 빠지지 않아요 · 빈 d1 의 이유
- 앱: 2.0 (stocklist · format · cofmt · rules · pf) 과 예전 뱁새 (fixnote) 가 Jack 의 줄을 그대로 쓰는지 · 미국 pxd 는 예전 그대로
"""
import collections
import copy
import datetime as dt
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

JACK = "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
D13, D16, D17, D18 = "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18"
KDAYS = ["2026-11-06", "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", D13, D16, D17, D18]     # KOSPI 거래일 (금 · 월 ~ 수)


def kr(t, nk=None, **kw):
    s = {"t": t, "nk": nk or ("종목" + t), "ne": nk or ("종목" + t), "cls": "kr", "s": "etc", "price": 5000.0, "vol": 30.0, "beta": 1.0,
         "al": 1.0, "betaSE": 0.05, "betaN": 700, "cap": 0.05, "val": 3.0, "val20": 2.5, "lo": 4000.0, "hi": 6000.0, "etf": False,
         "shr": 10000000, "r1": 1.0, "r3": 2.0, "r36": 3.0, "dk": "업종 · KOSDAQ 상장 · 시가총액 500억원", "sh": 0.3, "mdd": -40.0,
         "hit": 50, "mom": 10.0, "d1": 0.5, "per": 25.0, "pbr": 1.2, "dyt": 1.0, "dz": 50, "pz": 10, "vz": 20, "mz": 30, "qz": 40, "lz": 50}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def prev_file(stocks, px=D16, jump=None):
    return {"pxDate": px, "stocks": stocks, "krSeries": {"v": 1, "jump": jump or []}}


# ── 1. 파이프라인: 마지막 확인 종가로 싣기 ───────────────────────────────────────────────
def test_carried_from_a_confirmed_previous_publish_keeps_its_price_and_dates_it():
    p = kr("111110", "가나다", price=7300.0, cap=0.073, d1=-1.2, noTrade=None, d1Why=None)
    carried, jumps, drop = F.kr_own_close_carry(prev_file([p]), {"111110": ("가나다", "conf")}, dt.date(2026, 11, 18), KDAYS)
    assert drop == {} and jumps == {} and len(carried) == 1
    r = carried[0]
    assert r["pxd"] == D16 and r["price"] == 7300.0 and r["cap"] == 0.073          # 그 발행본의 가격 · 그 날짜 (오늘 값은 하나도 없어요)
    assert "d1" not in r and not {"d1Why", "noTrade", "ntD1"} & set(r)           # 오늘 변화는 없어요 (미국 pxd 와 같아요)
    assert set(r) <= set(F.KR_OWN_KEYS) | {"pxd"}                                  # 재무 · 배당 · 점수는 오늘 다시 만들어요 (그 가격으로)
    assert not {"per", "pbr", "dyt", "dz", "pz", "vz", "mz", "qz", "lz"} & set(r)
    for k in ("vol", "beta", "lo", "hi", "r1", "r3", "r36", "sh", "mdd", "hit", "mom", "dk", "val", "val20", "shr"):
        assert r[k] == p[k], k                                                      # 그 종가까지 자른 시계열로 그날 만든 숫자 그대로


def test_a_chain_keeps_the_same_price_and_pxd_never_redated():
    p = kr("222220", price=1234.0, d1=None, pxd=D13)                                # 지난 발행본도 이미 마지막 확인 종가 (11-13)
    carried, _, drop = F.kr_own_close_carry(prev_file([p], px=D16), {"222220": ("x", "mkt")}, dt.date(2026, 11, 18), KDAYS)
    assert drop == {} and carried[0]["pxd"] == D13 and carried[0]["price"] == 1234.0


def test_too_old_no_previous_and_same_day_stay_dropped():
    old = kr("333330", d1=None, pxd="2026-11-06")                                   # 그 뒤 거래일 8일 (5일 넘음)
    same = kr("444440")                                                             # 지난 발행본도 오늘과 같은 기준일
    days = KDAYS
    c1, _, d1 = F.kr_own_close_carry(prev_file([old], px=D16), {"333330": ("a", "conf"), "555550": ("b", "mkt")}, dt.date(2026, 11, 18), days)
    assert c1 == [] and d1 == {"333330": "old", "555550": "none"}
    assert V.kr_own_age("2026-11-06", D18, days) == 8 and V.kr_own_age(D16, D18, days) == 2
    c2, _, d2 = F.kr_own_close_carry(prev_file([same], px=D18), {"444440": ("c", "conf")}, dt.date(2026, 11, 18), days)
    assert c2 == [] and d2 == {"444440": "same"}                                    # 오늘 확인 못 한 값을 오늘 날짜로 싣지 않아요
    # 정확히 5일 = 실어요 · 6일 = 빼요 (KR_OWN_CLOSE_MAX_DAYS = 5 · Jack 의 늦은 데이터 점검 창과 같아요)
    assert V.KR_OWN_CLOSE_MAX_DAYS == 5
    five = kr("666660", d1=None, pxd="2026-11-11")
    six = kr("777770", d1=None, pxd="2026-11-10")
    c3, _, d3 = F.kr_own_close_carry(prev_file([five, six], px=D16), {"666660": ("", "conf"), "777770": ("", "conf")}, dt.date(2026, 11, 18), days)
    assert [r["t"] for r in c3] == ["666660"] and d3 == {"777770": "old"}


def test_bad_previous_values_and_price_history_marks():
    bad = [kr("100010", d1=None, pxd="2026/11/13"), kr("100020", price=None), kr("100030", d1=None, pxd=D16)]   # pxd = 그 발행본 pxDate 는 안 돼요
    c, _, d = F.kr_own_close_carry(prev_file(bad, px=D16), {x["t"]: ("", "conf") for x in bad}, dt.date(2026, 11, 18), KDAYS)
    assert c == [] and d == {"100010": "bad", "100020": "bad", "100030": "bad"}
    # 과거 주가 기록 오류 표시: 지난 krSeries.jump 의 움직임과 함께 옮겨요 (오늘 관문이 표시와 움직임을 맞춰 봐요) · 움직임이 없으면 싣지 않아요
    pb = kr("200010", pxBad="2026-05-08", pxBadF=list(V.PX_BAD_ALWAYS), vol=None, beta=None)
    nj = kr("200020", pxBad="2026-05-08", pxBadF=list(V.PX_BAD_ALWAYS))
    j = [["200010", "2026-05-08", 45.0, "halt"]]
    c, jumps, d = F.kr_own_close_carry(prev_file([pb, nj], jump=j), {"200010": ("", "mkt"), "200020": ("", "mkt")}, dt.date(2026, 11, 18), KDAYS)
    assert [r["t"] for r in c] == ["200010"] and c[0]["pxBad"] == "2026-05-08" and "vol" not in c[0]
    assert jumps == {"200010": j} and d == {"200020": "jump"}


def test_unconfirmed_list_and_reasons():
    full = pd.DataFrame({"Code": ["005930", "496320", "011810", "12345"], "Name": ["삼성전자", "본시스템즈", "STX", "x"],
                         "Market": ["KOSPI", "KONEX", "KOSPI", "KOSPI"]})
    got = F.kr_unconfirmed(full, {"005930"})
    assert got == {"496320": ("본시스템즈", "mkt"), "011810": ("STX", "conf")}     # 코넥스 = 두 번째 출처 없음 · 그 밖 = 확인 못 함
    assert F.kr_unconfirmed(None, set()) == {}


def test_derived_numbers_use_the_carried_close(capsys):
    rec = {"t": "123450", "nk": "가", "cls": "kr", "price": 5000.0, "cap": 0.05, "shr": 10000000, "pxd": D16}
    fin = {"123450": {"rev": [100.0, 90.0, 80.0], "op": [10.0, 9.0, 8.0], "ni": [20.0, 18.0, 16.0], "eq": 400.0, "ocf": 30.0, "dep": 5.0,
                      "bor": 10.0, "cash": 5.0, "ca": 50.0, "cl": 20.0, "fs": "OFS", "fy": 2025}}
    F.fill_multiples([rec], fin)
    assert rec["per"] == round(5000.0 / rec["eps"], 1) and rec["pbr"] == round(5000.0 / rec["bps"], 2)   # PER · PBR 은 그 종가로
    c = F.build_corp([dict(rec)], fin, "2026-11-19", pref_caps={})["companies"][0]
    assert c["price"] == 5000.0 and c["cap"] == 0.05 and c["pxd"] == D16 and c.get("evE") is not None   # EV 는 그 시가총액으로
    # 오늘 종가의 상장 우선주가 있는 회사: 회사 시가총액이 두 날짜를 섞어요 → EV · P/CF 를 비우고 evNo ownPx
    c2 = F.build_corp([dict(rec)], fin, "2026-11-19", pref_caps={"12345": 0.01})["companies"][0]
    assert c2["evNo"] == "ownPx" and not {"evE", "evR", "pcf"} & {k for k, v in c2.items() if v is not None}
    assert "ownPx" in capsys.readouterr().out
    # 마지막 확인 종가가 아닌 종목은 예전 그대로
    plain = dict(rec)
    plain.pop("pxd")
    c3 = F.build_corp([plain], fin, "2026-11-19", pref_caps={"12345": 0.01})["companies"][0]
    assert "pxd" not in c3 and c3.get("evNo") is None and c3.get("evE") is not None


def test_normal_day_has_no_korean_pxd():
    src = inspect.getsource(F.fetch_korea)
    # 확인 못 한 종목 목록 · 싣기는 2차 출처 날에만 (1차 출처 날에는 목록이 비고 싣는 단계가 돌지 않아요)
    assert 'unconf = kr_unconfirmed(full_list, set(listing["Code"])) if px_src["px"] == PX_SRC_FB else {}' in src
    assert re.search(r'if px_src\["px"\] == PX_SRC_FB:\n\s+have = \{r\["t"\] for r in out\}\n\s+carried, cjumps, cdrop = kr_own_close_carry', src)
    # 발행 직전 점검: 1차 출처 날의 국내 pxd 는 관문과 같은 함수가 빼요 (2차 출처 날이 아님)
    kr_ = [kr("005930"), kr("300000", d1=None, pxd=D16)]
    src_ = {"v": 1, "px": V.PX_SRC_LISTING, "date": D18}
    out = F.kr_own_close_final(kr_, src_, prev_file([kr("300000")]), KDAYS)
    assert [s["t"] for s in out] == ["005930"]
    # pxSrc.n 은 pxDate 종가로 실은 종목만 세요
    assert F.px_src_final({"px": V.PX_SRC_FB}, [kr("1"), kr("2", d1=None, pxd=D16), {"cls": "us"}])["n"] == {V.PX_SRC_FB: 1}


def own_rec(codes, unconf=None):
    return {"v": 1, "max": 5, "n": len(codes), "codes": sorted(codes), "unconf": unconf if unconf is not None else len(codes),
            "drop": {}, "dropEx": [], "bad": {"n": 0, "rows": []}}


def fb_data(stocks, codes, px=D18):
    return {"pxDate": px, "pxSrc": {"v": 1, "px": V.PX_SRC_FB, "date": px, "own": own_rec(codes),
                                    "fb": {"n": 3000, "conf": 2900, "noDaum": 0, "bad": 0, "noYahoo": 0, "diff": 0}}, "stocks": stocks}


def test_pipeline_drops_a_bad_row_loudly_and_publishes_the_rest(capsys):
    """Jack 의 규칙 (2026-11-19): 우리 처리의 한 줄이 틀리면 그 줄을 빼고 크게 남기고 나머지는 발행해요 — 관문과 같은 함수로."""
    prev = prev_file([kr("400010", price=100.0), kr("400020", price=200.0)])
    good, wrong = kr("400010", price=100.0, d1=None, pxd=D16), kr("400020", price=999.0, d1=None, pxd=D16)   # 지난 발행본 가격과 다름
    src = fb_data([], ["400010", "400020"])["pxSrc"]
    krs = {"hidden": ["400020"]}
    out = F.kr_own_close_final([kr("005930"), good, wrong], src, prev, KDAYS, krs=krs)
    assert [s["t"] for s in out] == ["005930", "400010"]
    assert src["own"]["codes"] == ["400010"] and src["own"]["n"] == 1 and src["own"]["bad"]["n"] == 1 and krs["hidden"] == []
    log = capsys.readouterr().out
    assert "!! 마지막 확인 종가 점검 (관문과 같은 함수): 1종목 빼고 발행" in log and "400020" in log
    # 그 기록을 관문이 경고로 보여요 (실패 아님)
    d = fb_data(out, ["400010"])
    d["pxSrc"]["own"] = src["own"]
    rep = V.Report()
    V.check_kr_own_close(rep, d, None, prev)
    rows = {r[0]: r for r in rep.rows}
    assert rows["국내 자기 가격 날짜 (pxd)"][3] == "PASS"
    assert rows["국내 마지막 확인 종가 (pxSrc.own · 경고만)"][3] == "WARN" and "파이프라인이 거른 종목 1" in rows["국내 마지막 확인 종가 (pxSrc.own · 경고만)"][1]
    # 깨끗한 실행: · 줄
    F.kr_own_close_final(out, d["pxSrc"], prev, KDAYS)
    assert "· 마지막 확인 종가 점검 (관문과 같은 함수): 0종목 빼고 발행" in capsys.readouterr().out


def test_log_and_record_shape_the_gate_reads(capsys):
    carried = [dict(kr("500010", "에이"), pxd=D16), dict(kr("500020", "비"), pxd=D13)]
    for r in carried:
        r.pop("d1")
    rec = F.log_kr_own_close(carried, {"500030": "none", "500040": "old"}, {"500010": ("에이", "conf"), "500020": ("비", "mkt"),
                                                                            "500030": ("씨", "mkt"), "500040": ("디", "conf")}, {})
    out = capsys.readouterr().out
    assert "!! 국내 종가 미확인 4종목" in out and "마지막 확인 종가로 실음 2종목 (pxd 2026-11-16 1 · 2026-11-13 1)" in out
    assert "!! 마지막 확인 종가로도 싣지 못한 국내 종목 2" in out and "500030 씨 (지난 발행본에 없음" in out
    assert rec["n"] == 2 and rec["codes"] == ["500010", "500020"] and rec["unconf"] == 4 and rec["drop"] == {"none": 1, "old": 1}
    assert V.kr_own_rec({"pxSrc": {"own": rec}}) is rec
    json.dumps(rec, allow_nan=False)


# ── 2. 관문 ───────────────────────────────────────────────────────────────
def gate_rows(data, pdata=None, macro=None):
    rep = V.Report()
    V.check_kr_own_close(rep, data, macro, pdata)
    return {r[0]: (r[1], r[3]) for r in rep.rows}


PXD_ROW, OWN_ROW = "국내 자기 가격 날짜 (pxd)", "국내 마지막 확인 종가 (pxSrc.own · 경고만)"
MACRO = {"idxHist": {"KOSPI": {"rows": [[d, 4000.0] for d in KDAYS]}}}


def test_gate_accepts_a_recorded_korean_pxd_and_leaves_it_out_of_the_pxdate_price_checks():
    prev = prev_file([kr("600010", price=100.0), kr("005930")])
    own = kr("600010", price=100.0, d1=None, pxd=D16)
    data = fb_data([kr("005930", price=194700.0), own], ["600010"])
    rows = gate_rows(data, prev, MACRO)
    assert rows[PXD_ROW] == ("1종목 (2026-11-16 1종목)", "PASS") and rows[OWN_ROW][1] == "PASS", rows
    assert V.kr_own_codes(data) == {"600010"}
    assert "600010" not in V.px_alt_pick(data)                     # 관문 표본에서 빠져요 (그날 가격이 아니에요)
    alt = {"date": dt.date(2026, 11, 18), "mode": "publish", "closes": {}, "asked": 7, "got": 7, "meta": 0, "disagree": [], "mustMissing": [], "err": []}
    data["pxSrc"]["fb"]["conf"] = 1                                # 확인된 종목 1 = pxDate 종가로 실은 종목 1 (마지막 확인 종가 종목은 세지 않아요)
    ok, why = V.px_alt_confirms(data, alt, dt.date(2026, 11, 18), None, today=dt.date(2026, 11, 19),
                                now=dt.datetime(2026, 11, 19, 7, 0, tzinfo=V.KST), special={})
    assert ok, why
    assert V.kr_no_trade_problems({**data, "d1Blank": {k: 0 for k in V.D1_WHY} | {"seen": True, "odd": [], "must": []}}) == []


def test_gate_korean_pxd_on_a_normal_day_is_not_exempt_and_warns():
    data = {"pxDate": D18, "pxSrc": {"v": 1, "px": V.PX_SRC_LISTING, "date": D18}, "stocks": [kr("700010", d1=None, pxd=D16)]}
    rows = gate_rows(data, None, MACRO)
    assert rows[PXD_ROW][1] == "PASS" and rows[OWN_ROW][1] == "WARN" and "2차 출처 날이 아님" in rows[OWN_ROW][0]
    assert V.kr_own_codes(data) == set()                           # 빠지지 않아요: pxDate 의 가격으로 보고 가격 줄들이 맞춰 봐요
    assert "700010" in V.px_alt_pick({**data, "stocks": data["stocks"] + [kr(t) for t in V.MUST]})


def test_gate_fails_only_what_the_us_pxd_row_fails():
    for bad in (kr("800010", d1=None, pxd=D18), kr("800010", d1=None, pxd="2026-11-19"), kr("800010", d1=None, pxd="11/16"),
                kr("800010", d1=0.4, pxd=D16)):
        rows = gate_rows(fb_data([bad], ["800010"]))
        assert rows[PXD_ROW][1] == "FAIL", (bad, rows)            # 미국 pxd 줄과 같은 실패: 날짜가 아니거나 pxDate 보다 앞이 아님 · d1 과 같이 있음
    # 그 밖은 경고만 (새 실패 조건 없음): 기록에 없음 · 나이 상한 · 지난 발행본과 다름 · 표시가 같이 있음
    prev = prev_file([kr("800020", price=50.0)], px=D16)
    cases = [(fb_data([kr("800020", price=50.0, d1=None, pxd=D16)], []), prev, "pxSrc.own 에 적힌 종목이 아님"),
             (fb_data([kr("800020", price=50.0, d1=None, pxd="2026-11-06")], ["800020"]), None, "5일 넘음"),
             (fb_data([kr("800020", price=51.0, d1=None, pxd=D16)], ["800020"]), prev, "지난 발행본의 마지막 확인 종가"),
             (fb_data([kr("800020", price=50.0, d1=None, pxd=D16, noTrade=True)], ["800020"]), prev, "d1Why · noTrade")]
    for data, pdata, word in cases:
        rows = gate_rows(data, pdata, MACRO)
        assert rows[PXD_ROW][1] == "PASS" and rows[OWN_ROW][1] == "WARN" and word in rows[OWN_ROW][0], (word, rows)


def test_gate_old_files_and_files_without_korean_pxd_are_unchanged():
    old = {"pxDate": D16, "stocks": [kr("005930"), {"t": "AAPL", "cls": "us", "price": 1.0, "pxd": "2026-11-11"}]}
    rows = gate_rows(old, None, MACRO)
    assert rows == {PXD_ROW: ("없음 (모두 기준일 종가)", "PASS"), OWN_ROW: ("없음 (모두 기준일 종가)", "PASS")}
    assert V.kr_own_codes(old) == set()
    # 빈 d1 은 예전처럼 이유가 있어야 해요 (pxd 가 없는 국내 종목)
    d = {"pxDate": D18, "stocks": [kr("900010", d1=None)], "d1Blank": {k: 0 for k in V.D1_WHY} | {"seen": True, "odd": [], "must": []}}
    assert V.kr_no_trade_problems(d) == ["900010 d1 이 빈 칸인데 이유(d1Why)가 없어요"]
    d["stocks"][0]["pxd"] = D18                                  # pxDate 와 같은 pxd 는 이유가 아니에요
    assert V.kr_no_trade_problems(d) == ["900010 d1 이 빈 칸인데 이유(d1Why)가 없어요"]


def test_run_checks_price_match_leaves_out_recorded_carries_only():
    src = inspect.getsource(V.run_checks)
    assert "inl = [s for s in kr if s.get(\"t\") in cl and s.get(\"t\") not in own]" in src
    assert "own_ok = kr_own_codes(data, pdata, kr_days_of(macro))" in src and "own=own_ok" in src
    assert "check_kr_own_close(rep, data, macro, pdata)" in src
    vs = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert ("pick_data = kr_own_pick_data(cur[\"data\"], (prev or {}).get(\"data\") if mode == \"publish\" else None, kr_days_of(cur.get(\"macro\")))"
            in vs and "alt = http_px_alt(pick_data, pxd," in vs)


def test_only_a_clean_carry_is_left_out_of_the_pxdate_price_checks():
    """기록에 있어도 지난 발행본의 가격 · 날짜와 다르거나 나이 상한을 넘으면 빠지지 않아요 (pxDate 의 가격으로 맞춰 봐요 — 새 실패 조건 없이)."""
    prev = prev_file([kr("610010", price=100.0), kr("610020", price=100.0)], px=D16)
    data = fb_data([kr("610010", price=100.0, d1=None, pxd=D16), kr("610020", price=120.0, d1=None, pxd=D16),
                    kr("610030", price=9.0, d1=None, pxd="2026-11-06")], ["610010", "610020", "610030"])
    assert V.kr_own_codes(data) == {"610010", "610020", "610030"}                  # 지난 발행본 · 거래일을 모르면 기록 · 모양만
    assert V.kr_own_codes(data, prev, KDAYS) == {"610010"}                         # 가격이 다름 · 나이 상한 넘음 → pxDate 의 가격으로 봐요
    full = {**data, "stocks": data["stocks"] + [kr(t) for t in V.MUST]}
    pd_ = V.kr_own_pick_data(full, prev, KDAYS)
    pick = V.px_alt_pick(pd_)
    assert "610010" not in pick and {"610020", "610030"} <= set(pick)               # 관문 표본: 맞게 실린 종목만 빠져요
    assert pd_["pxSrc"]["own"]["codes"] == ["610010"] and data["pxSrc"]["own"]["codes"] == ["610010", "610020", "610030"]   # 사본만 바꿔요
    clean = fb_data([kr("610010", price=100.0, d1=None, pxd=D16)], ["610010"])
    assert V.kr_own_pick_data(clean, prev, KDAYS) is clean and V.kr_own_pick_data({"stocks": []}) == {"stocks": []}


# ── 3. 앱 (Node) ───────────────────────────────────────────────────────────
NODE = shutil.which("node")
_B = {}
MODS = {"D": "src/data.js", "L": "src/v2/stocklist.js", "R": "src/v2/rules.js", "CF": "src/v2/cofmt.js", "F": "src/v2/format.js",
        "LD": "src/v2/load.js", "C": "src/copy/v2.js", "P": "src/v2/pf.js", "FX": "src/fixnote.jsx"}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/own.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as M from './own.mjs';\nconst { D, L, R, CF, F, LD, P, FX } = M; const CP = M.C.C;\n"
            "const WARN = []; console.warn = (m) => WARN.push(String(m));\n" + decl + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out === undefined ? null : out));\n")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def us(t, **kw):
    s = {"t": t, "nk": t + " Inc.", "cls": "us", "price": 100.0, "d1": 0.5}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


needs_node = pytest.mark.skipif(NODE is None, reason="node 가 없어요")


@needs_node
def test_app_copy_is_jacks_line_in_both_apps():
    got = run("out = { k: CP.app.krOwnClose, o: CP.app.ownClose, fx: FX.FIX_KR_OWN_CLOSE, fo: FX.FIX_OWN_CLOSE };")
    assert got["k"] == JACK and got["fx"] == JACK                   # 2.0 · 예전 뱁새 같은 글자
    assert got["o"] == got["fo"] == "{names} 가격은 {md} 종가예요."
    detail = open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()
    assert 'const T_OWN_CLOSE = { ko: "{names} 가격은 {md} 종가예요."' in detail and "FIX_KR_OWN_CLOSE.replace(\"{date}\"" in detail


@needs_node
def test_app_groups_korean_stocks_by_their_own_market_date_and_names_them():
    rows = [kr("011810", "STX", d1=None, pxd=D16), us("AAPL", pxd=D16, d1=None), kr("005930", "삼성전자"), kr("094800", "맵스리얼티", d1=None, pxd=D16),
            kr("496320", "본시스템즈", d1=None, pxd=D13), kr("011810", "STX", d1=None, pxd=D16), kr("100000", "같은날", d1=None, pxd=D17)]
    got = run("out = { g: L.ownCloses({ status: 'ok', data: { pxDate: '2026-11-18', usPxDate: '2026-11-17' } }, ROWS),"
              " us: L.ownCloses({ status: 'ok', data: { pxDate: '2026-11-18', usPxDate: '2026-11-17' } }, ROWS.filter((s) => s.cls === 'us')),"
              " txt: F.ownCloseText(L.ownCloses({ status: 'ok', data: { pxDate: '2026-11-18', usPxDate: '2026-11-17' } }, ROWS)) };", ROWS=rows)
    # 국내 pxd 는 pxDate 와 견줘요: usPxDate(11-17)와 같은 날짜여도 이름이 나와요 · 미국 묶음은 예전 모양 그대로
    assert got["g"] == [{"date": D17, "ts": ["100000"], "kr": True, "names": ["같은날"]},
                        {"date": D16, "ts": ["AAPL"]},
                        {"date": D16, "ts": ["011810", "094800"], "kr": True, "names": ["STX", "맵스리얼티"]},
                        {"date": D13, "ts": ["496320"], "kr": True, "names": ["본시스템즈"]}], got["g"]
    assert got["us"] == [{"date": D16, "ts": ["AAPL"]}]
    assert got["txt"] == ("같은날 가격은 11월 17일 종가예요. 오늘 종가를 확인하지 못해서 11월 17일 종가를 보여 드려요. "
                          "AAPL 가격은 11월 16일 종가예요. "
                          "STX, 맵스리얼티 가격은 11월 16일 종가예요. 오늘 종가를 확인하지 못해서 11월 16일 종가를 보여 드려요. "
                          "본시스템즈 가격은 11월 13일 종가예요. 오늘 종가를 확인하지 못해서 11월 13일 종가를 보여 드려요."), got["txt"]


@needs_node
def test_app_single_stock_line_and_us_unchanged():
    got = run("""
const load = { status: 'ok', data: { pxDate: '2026-11-18', usPxDate: '2026-11-17' } };
out = { kr: CF.krOwnCloseText(load, A), plain: CF.krOwnCloseText(load, B), us: CF.krOwnCloseText(load, U), date: CF.priceDate(load, A),
  close: CF.closeLine(load, A), usClose: CF.closeLine(load, U), loading: CF.krOwnCloseText({ status: 'loading' }, A),
  old: [FX.krOwnCloseText(A, null), FX.krOwnCloseText({ t: 'C', pxd: '2026-11-16' }, '2026-11-18'), FX.krOwnCloseText(U, null),
        FX.krOwnCloseText(B, '2026-11-18'), FX.krOwnCloseListText([{ t: '094800', nk: '맵스리얼티', pxd: '2026-11-16' }, { t: '005930', nk: '삼성전자' }])] };""",
              A=kr("094800", "맵스리얼티", d1=None, pxd=D16), B=kr("005930", "삼성전자"), U=us("AAPL", pxd=D16, d1=None))
    line = JACK.replace("{date}", "11월 16일")
    assert got["kr"] == line and got["plain"] is None and got["us"] is None and got["loading"] is None
    assert got["date"] == D16 and got["close"] == "11월 16일 종가"     # 그 종목의 날짜 (오늘 날짜가 아니에요)
    assert got["old"] == [line, line, None, None, "맵스리얼티 가격은 11월 16일 종가예요. " + line]


@needs_node
def test_app_daily_check_and_import_date_use_the_korean_own_date():
    got = run("""
const S = [A, B];
const ctx = { state: { ok: true }, byT: new Map(S.map((s) => [s.t, s])), coByT: new Map(), fx: 1300, pxDate: '2026-11-18', usPxDate: '2026-11-16' };
const deck = { id: 'd', name: 'deck', createdAt: '2026-10-01',
  holdings: S.map((s) => ({ t: s.t, nk: s.nk, cls: 'kr', kind: 'core', target: 0.5, rules: [] })),
  purchases: S.map((s) => ({ t: s.t, date: '2026-10-01', qty: 1, price: 100, ccy: 'KRW' })) };
const ev = R.evaluateDeck(deck, ctx);
const load = { status: 'ok', data: { pxDate: '2026-11-18', usPxDate: '2026-11-16', fx: 1300, stocks: S }, byT: ctx.byT };
const rec = P.importedRecord({ drafts: [{ t: A.t, mode: 'amount', amountWon: 1000000 }, { t: B.t, mode: 'amount', amountWon: 1000000 }], load,
  settings: {}, id: 'x', name: 'x', today: '2026-11-19' });
out = { h: ev.holdings.map((x) => [x.t, x.d1, x.pxd, x.bigMove]), g: L.ownCloseGroups(ev.holdings, null), dates: rec.imported.map((x) => [x.t, x.date, x.close]) };""",
              A=kr("094800", "맵스리얼티", d1=-9.0, pxd=D16), B=kr("005930", "삼성전자", d1=-9.0))
    # pxd 가 usPxDate(11-16)와 같아도 국내 종목은 pxDate 와 견줘서 그 날짜를 실어요 · 오늘 변화 · 큰 움직임은 없어요
    assert got["h"] == [["094800", None, D16, False], ["005930", -9.0, None, True]], got["h"]
    assert got["g"] == [{"date": D16, "ts": ["094800"], "kr": True, "names": ["맵스리얼티"]}]
    assert got["dates"] == [["094800", D16, 5000.0], ["005930", D18, 5000.0]]     # 금액으로 넣은 종목의 날짜 = 그 가격의 날짜


@needs_node
def test_app_load_report_names_korean_carries_separately():
    got = run("""
WARN.splice(0); LD.logDates(D1); const w = WARN.splice(0);
out = w.filter((m) => !/staleAfter|nextPub/.test(m));""",
              D1={"pxDate": D18, "usPxDate": D17, "staleAfter": "2026-11-20T16:47:00+09:00", "nextPub": "2026-11-20",
                  "stocks": [kr("094800", d1=None, pxd=D16), us("AAPL", pxd=D16, d1=None), kr("005930")]})
    assert len(got) == 2, got
    assert got[0].startswith("[v2] 1 Korean stocks at their last confirmed close before 2026-11-18") and "094800 2026-11-16" in got[0]
    assert got[1].startswith("[v2] 1 of 1 US stocks at an earlier close than 2026-11-17") and "AAPL 2026-11-16" in got[1]
