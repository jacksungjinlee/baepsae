"""2026-11-21: 직전 거래일 파일이 최종본이 아닌 날의 d1 — KRX 기준가 × 지난 발행본 종가 (fetch_data.kr_d1_base_day).

사고 (시험 실행 44783218618 · 11-21 02:33 KST): 자원봉사 캐시가 11-16 에 멈춰 11-17 · 18 · 19 는 2차 출처(다음 × 야후)로 발행했어요
(11-20 06:40 발행 · pxDate 11-19 · pxSrc daum+yahoo). 캐시에 11-20 최종본(23:23 KST 커밋)이 생겨 11-20 은 1차 출처 날이 됐지만,
11-17 ~ 19 파일의 마지막 커밋은 모두 장 마감 전 (11-19 14:52 · 수능일 마감 16:30) 이라 직전 거래일 파일을 쓸 수 없어 국내 d1 이 0.0% →
'필수 종목 d1' 실패 → 발행이 멈췄어요.

fixtures/d1_after_gap (진짜 파일에서 이 시험에 필요한 행만 그대로 옮겼어요 · 2026-11-21):
- krx_2026-11-20_2323.csv: 캐시의 11-20 최종본 (FinanceData/fdr_krx_data_cache data/listing/krx/2026-11-20.csv) 14행
- krx_2026-11-19_1452.csv: 캐시의 11-19 파일 (마지막 커밋 11-19 14:52 KST — 장중 값 · 최종본 아님) 같은 14행
- pub_2026-11-19.json: 11-20 06:40 발행본 (data.json · pxDate 11-19 · daum+yahoo) 의 머리 칸과 그 종목들의 행
  (496320 코넥스 · 011810 STX · 489460 바이오비쥬는 그 발행본에 없어요 — 11-19 에 두 출처가 다르거나 확인하지 못한 종목)
그 앞 날짜는 fixtures/kr_two_source 의 11-13 · 11-16 최종본과 11-17 · 11-18 장중 파일을 써요.
진짜 파일 전체로 다시 돌린 결과 (11-20 최종본 2,878행 중 처리하는 2,500종목 × 11-20 06:40 발행본): 확인 2,371 / 2,500 · 다름 0 ·
지난 발행본에 없음 88 · 그날 확인된 종가가 아님 41 (모두 11-20 에도 거래 없음) · d1 2,370 (94.8%) · 빈 칸 거래 없음 71 · prev 59 ·
확인한 d1 이 KRX 의 등락률(ChagesRatio)과 모두 같음."""
import copy
import datetime as dt
import inspect
import json
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "d1_after_gap")
FX2 = os.path.join(ROOT, "tests", "fixtures", "kr_two_source")
D13, D16, D17, D18, D19, D20 = (dt.date(2026, 11, d) for d in (13, 16, 17, 18, 19, 20))
TRADE_DAYS = [pd.Timestamp(d) for d in (D13, D16, D17, D18, D19, D20)]
MUST = list(V.MUST)


def csv_file(path):
    return F.parse_listing_csv(open(path, encoding="utf-8").read())


def cur20():
    return csv_file(os.path.join(FX, "krx_2026-11-20_2323.csv"))


def pub19():
    return json.load(open(os.path.join(FX, "pub_2026-11-19.json"), encoding="utf-8"))


FILES = {D19: lambda: csv_file(os.path.join(FX, "krx_2026-11-19_1452.csv")),
         D18: lambda: csv_file(os.path.join(FX2, "krx_2026-11-18_1452.csv")),
         D17: lambda: csv_file(os.path.join(FX2, "krx_2026-11-17_1529.csv")),
         D16: lambda: csv_file(os.path.join(FX2, "krx_2026-11-16_2211.csv")),
         D13: lambda: csv_file(os.path.join(FX2, "krx_2026-11-13_2158.csv"))}
COMMITS = {D19: dt.datetime(2026, 11, 19, 14, 52, tzinfo=F.KST), D18: dt.datetime(2026, 11, 18, 14, 52, tzinfo=F.KST),
           D17: dt.datetime(2026, 11, 17, 15, 29, tzinfo=F.KST), D16: dt.datetime(2026, 11, 16, 22, 11, tzinfo=F.KST),
           D13: dt.datetime(2026, 11, 13, 21, 58, tzinfo=F.KST)}


def run_day(cur, pub, px_date=D20, files=FILES, commits=COMMITS):
    """fetch_korea 의 d1 부분을 그대로 (같은 순서 · 같은 함수): 앞선 거래일 파일 → 직전 거래일 → 파일로 d1 → 쓸 수 없으면 기준가 × 지난 발행본 →
    거래 없음 · 이유. 반환: dict."""
    sessions, notes, prev_final = F.kr_recent_sessions(px_date, lambda d: files[d]() if d in files else None, commits.get, n=4,
                                                       special=F.load_krx_special_sessions())
    want_prev = F.kr_prev_session(px_date, [t for t in TRADE_DAYS if t.date() <= px_date])
    ok_prev = F.prev_session_ok(sessions, prev_final, want_prev)
    d1, v20, _ = F.kr_d1_val20(cur, sessions, ok_prev)
    base_ok, rec = None, None
    if not ok_prev and want_prev is not None:
        d1, base_ok, rec = F.kr_d1_base_day(cur, pub, want_prev)
    # 시험 파일은 14행 중 3행이 거래 없음이라 (진짜 파일 71 / 2,500) '10% 넘음(many)' 보호를 이 시험에서만 풀어요 — 같은 함수 · 같은 규칙
    nt, unseen, odd, must = F.kr_no_trade_plan(cur, max_share=1.0)
    assert unseen is None
    out, why, ntm, cnt = F.kr_d1_split(cur, sessions, ok_prev, d1, nt, base_ok=base_ok)
    return {"sessions": sessions, "notes": notes, "prev_final": prev_final, "want_prev": want_prev, "ok_prev": ok_prev,
            "d1": out, "why": why, "nt": ntm, "cnt": cnt, "rec": rec, "base_ok": base_ok, "v20": v20}


def krx_ratio(cur):
    return {str(c).strip(): float(r) for c, r in zip(cur["Code"], cur["ChagesRatio"])}


# ── 1. 11-20 모양 그대로: 직전 파일이 최종본이 아니어도 필수 종목이 d1 을 받아요 ─────────────
def test_replay_11_20_must_haves_get_d1():
    cur = cur20()
    r = run_day(cur, pub19())
    # 그날 그대로: 11-19 · 18 · 17 파일은 최종본이 아니라 건너뛰고 직전 파일은 11-16 → 파일로는 d1 을 낼 수 없어요
    assert r["want_prev"] == D19 and not r["prev_final"] and not r["ok_prev"]
    assert [d for d, _ in r["sessions"]][:1] == [D16]
    assert any("직전 거래일 2026-11-19 파일의 마지막 커밋이 11-19 14:52 KST" in n for n in r["notes"])
    rec = r["rec"]
    assert rec["day"] == "2026-11-19" and rec["pub"] == "2026-11-19" and rec["why"] is None
    assert rec["ok"] == 10 and rec["diff"] == 0 and rec["noBase"] == 0
    assert rec["noPub"] == 3 and rec["notConf"] == 1                  # 코넥스 496320 · STX · 바이오비쥬 · 금양 (11-19 거래 없음)
    ratio = krx_ratio(cur)
    for c in MUST:
        assert r["d1"][c] == pytest.approx(ratio[c], abs=0.005), c       # KRX 자기 등락률과 같아요 (삼성전자 −7.01%)
        assert c not in r["why"]
    assert r["d1"]["005930"] == -7.01
    assert r["why"]["489460"] == "prev"                                 # 11-19 에 두 출처가 달라 발행하지 않은 종목 → 추측하지 않아요
    assert r["why"]["001570"] == r["why"]["011810"] == r["why"]["496320"] == "noTrade"
    loud, txt = F.d1_base_note(rec)
    assert loud and txt.startswith("d1: 직전 거래일 최종본이 없어 KRX 기준가 × 지난 발행본 종가로 확인 10 / 14 · 다름 0 · 지난 발행본에 없음 3")
    assert "489460 바이오비쥬" in txt and "001570 금양" in txt
    json.dumps(rec, allow_nan=False)


def test_before_this_change_every_d1_was_blank():
    """같은 날, 기준가 길 없이 (예전 코드): 모두 prev → 관문 '필수 종목 d1' 실패."""
    cur = cur20()
    r = run_day(cur, pub19())
    nt = F.kr_no_trade_plan(cur, max_share=1.0)[0]
    out, why, _, cnt = F.kr_d1_split(cur, r["sessions"], r["ok_prev"], {}, nt)
    assert out == {} and cnt["prev"] == 11 and cnt["noTrade"] == 3


def gate_rows(cur, prev, final):
    rep = V.run_checks(cur, prev, final, dt.date(2026, 10, 31), mode="publish", count_between=lambda a, b: 1,
                       sessions={"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)],
                                 "src": "시험"},
                       now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=hilo_of(cur, V.MUST))
    return rep, {row[0]: row for row in rep.rows}


def test_gate_must_have_d1_row_passes_with_the_replayed_values():
    r = run_day(cur20(), pub19())
    cur, prev, final = good_pair()
    for s in cur["data"]["stocks"]:
        if s["t"] in MUST:
            s["d1"] = r["d1"][s["t"]]
    rep, rows = gate_rows(cur, prev, final)
    assert rows["필수 종목 d1"][3] == "PASS", rep.table()
    assert not rep.failed, rep.table()
    # 예전 모습 (필수 종목 d1 이 빈 칸 · d1Why prev) → 그 줄이 실패해요
    bad = copy.deepcopy(cur)
    for s in bad["data"]["stocks"]:
        if s["t"] in MUST:
            s.pop("d1", None)
            s["d1Why"] = "prev"
    rep2, rows2 = gate_rows(bad, prev, final)
    assert rows2["필수 종목 d1"][3] == "FAIL"


# ── 2. 확인되지 않으면 빈 칸 (추측하지 않아요) ─────────────────────────────────────
def test_base_reset_is_blank_with_a_reason():
    """KRX 가 기준가를 새로 정한 날 (예: 5:1 분할 — 기준가 53,500 ≠ 지난 발행본 267,500): 빈 칸 · d1Why prev · d1Base.diff 에 이름과 두 값."""
    cur = cur20()
    i = cur.index[cur["Code"] == "005380"][0]
    cur.loc[i, ["Close", "Changes", "Marcap", "Stocks"]] = [51000, -2500, 51000 * 203466492 * 5, 203466492 * 5]
    r = run_day(cur, pub19())
    assert "005380" not in r["d1"] and r["why"]["005380"] == "prev"
    assert r["rec"]["diff"] == 1 and r["rec"]["ex"]["diff"] == ["005380 현대차 267,500→53,500"]
    assert "다름: 005380 현대차 267,500→53,500" in F.d1_base_note(r["rec"])[1]
    # 한 원만 달라도 빈 칸 (원 단위까지 같아야 해요)
    cur = cur20()
    i = cur.index[cur["Code"] == "005930"][0]
    cur.loc[i, "Changes"] = -13801
    r = run_day(cur, pub19())
    assert "005930" not in r["d1"] and r["rec"]["ex"]["diff"] == ["005930 삼성전자 196,900→196,901"]


def test_previous_publish_on_another_day_leaves_d1_blank_as_before():
    pub = pub19()
    pub["pxDate"] = "2026-11-18"
    pub["pxSrc"]["date"] = "2026-11-18"
    r = run_day(cur20(), pub)
    assert r["d1"] == {} and r["base_ok"] is None
    assert set(r["why"].values()) == {"prev", "noTrade"} and all(r["why"][c] == "prev" for c in MUST)
    assert r["rec"]["why"] == "day" and r["rec"]["ok"] == 0 and r["rec"]["n"] == 14
    loud, txt = F.d1_base_note(r["rec"])
    assert loud and "지난 발행본의 가격 날짜가 직전 거래일이 아니에요" in txt and "d1 을 비워요 14종목" in txt
    # 지난 발행본이 없어도 같아요
    r = run_day(cur20(), None)
    assert r["d1"] == {} and r["rec"]["why"] == "none"


@pytest.mark.parametrize("edit", [
    lambda p: p.update(listSrc="prev-data.json"),                    # 지난 data.json 으로 만든 목록 (공식 종가 아님)
    lambda p: p["pxSrc"].update(px="naver"),
    lambda p: p["pxSrc"].update(date="2026-11-18"),
    lambda p: p.update(pxSrc="daum+yahoo"),
])
def test_previous_publish_from_an_unknown_source_is_not_used(edit):
    pub = pub19()
    edit(pub)
    r = run_day(cur20(), pub)
    assert r["d1"] == {} and r["rec"]["why"] == "src"


def test_carry_and_no_trade_rows_are_not_a_confirmed_close():
    """지난 발행본의 행이 자기 가격 날짜(pxd · #159 의 이어 쓴 값)를 달았거나 거래 없음이면 그날 확인된 종가가 아니에요 → 빈 칸."""
    pub = pub19()
    for s in pub["stocks"]:
        if s["t"] == "005930":
            s["pxd"] = "2026-11-18"
    r = run_day(cur20(), pub)
    assert "005930" not in r["d1"] and r["why"]["005930"] == "prev" and r["rec"]["notConf"] == 2
    closes, skip, why = F.kr_prev_pub_closes(pub, D19)
    assert why is None and {"005930", "001570"} <= skip and "005930" not in closes
    # 같은 코드가 두 번이면 어느 값인지 몰라요
    pub = pub19()
    pub["stocks"].append(dict(pub["stocks"][0], price=1.0))
    closes, skip, _ = F.kr_prev_pub_closes(pub, D19)
    assert pub["stocks"][0]["t"] in skip and pub["stocks"][0]["t"] not in closes
    # 미국 · 펀드 행은 보지 않아요
    pub = pub19()
    pub["stocks"] += [{"t": "AAPL", "cls": "us", "price": 1.0}, {"t": "069500", "cls": "kr", "fund": True, "price": 1.0}]
    closes, _, _ = F.kr_prev_pub_closes(pub, D19)
    assert "AAPL" not in closes and "069500" not in closes


def test_confirmed_base_beyond_30_percent_is_range_not_prev():
    cur = cur20().astype({"Close": float, "Changes": float, "Marcap": float})
    i = cur.index[cur["Code"] == "047400"][0]                         # 지난 발행본 2,775원 · 기준가 2,530 + 245 = 2,775
    up = 2775 * 1.35
    cur.loc[i, ["Close", "Changes", "Marcap"]] = [up, up - 2775, up * float(cur.loc[i, "Stocks"])]
    r = run_day(cur, pub19())
    assert "047400" not in r["d1"] and r["why"]["047400"] == "range" and "047400" in r["base_ok"]
    # 30% 안 (+29.98%) 은 남아요
    cur = cur20().astype({"Close": float, "Changes": float, "Marcap": float})
    cur.loc[i, ["Close", "Changes", "Marcap"]] = [3607, 832, 3607 * float(cur.loc[i, "Stocks"])]
    r = run_day(cur, pub19())
    assert r["d1"]["047400"] == pytest.approx(29.98, abs=0.01)


def test_missing_base_is_blank():
    cur = cur20()
    cur.loc[cur["Code"] == "000660", "Changes"] = float("nan")
    r = run_day(cur, pub19())
    assert "000660" not in r["d1"] and r["rec"]["noBase"] == 1 and r["why"]["000660"] == "prev"


# ── 3. 보통 날은 예전 그대로 ─────────────────────────────────────────────────
def test_normal_day_is_unchanged_and_both_methods_agree():
    """11-16 (직전 11-13 최종본): 파일로 낸 d1 이 예전 그대로이고, 기준가 길은 쓰이지 않아요. 같은 날 기준가 길로 냈다면 값도 같아요."""
    cur = csv_file(os.path.join(FX2, "krx_2026-11-16_2211.csv"))
    r = run_day(cur, pub19(), px_date=D16)
    assert r["ok_prev"] and r["rec"] is None and r["base_ok"] is None
    sessions = r["sessions"]
    d1, _, _ = F.kr_d1_val20(cur, sessions, True)
    nt = F.kr_no_trade_plan(cur, max_share=1.0)[0]
    assert F.kr_d1_split(cur, sessions, True, d1, nt) == F.kr_d1_split(cur, sessions, True, d1, nt, base_ok=None)
    assert r["d1"] == F.kr_d1_split(cur, sessions, True, d1, nt)[0] and r["d1"]
    # 11-13 최종본의 공식 종가를 '지난 발행본'으로: 11-16 의 KRX 기준가와 원 단위까지 같아 같은 d1 이 나와요. 진짜 기준가 재설정 하나 —
    # 유니온머티리얼 5:1 병합 (11-13 공식 종가 746 · 11-16 기준가 3,730): 파일 길은 ±30% 밖(range), 기준가 길은 다름(diff) — 둘 다 빈 칸
    prev13 = F._official_map(sessions[0][1])
    pub = {"pxDate": "2026-11-13", "listSrc": F.KR_LIST_SRC_CACHE, "pxSrc": {"px": V.PX_SRC_LISTING, "date": "2026-11-13"},
           "stocks": [{"t": c, "cls": "kr", "price": p} for c, p in prev13.items()]}
    bd1, base_ok, rec = F.kr_d1_base_day(cur, pub, D13)
    assert rec["diff"] == 1 and rec["ex"]["diff"] == ["047400 유니온머티리얼 746→3,730"] and rec["ok"] == 12
    assert r["why"]["047400"] == "range" and "047400" not in bd1 and "047400" not in r["d1"]
    assert {c: v for c, v in bd1.items() if c not in nt} == r["d1"]


def test_pipeline_calls_the_base_path_only_when_the_previous_file_cannot_be_used():
    src = inspect.getsource(F.fetch_korea)
    assert "if not ok_prev and want_prev is not None:\n            d1_map, base_ok, d1_base = kr_d1_base_day(listing, prev, want_prev)" in src
    assert "kr_d1_split(listing, sessions, ok_prev, d1_map, no_trade, base_ok=base_ok)" in src
    assert 'meta["d1Base"] = d1_base' in src
    assert 'payload["d1Base"] = kmeta["d1Base"]' in inspect.getsource(F.main)
    assert "d1Base" in F.UNITS and "d1Base" in F.UNITS["d1Why"]
    # 관문의 d1Why 목록은 그대로 (새 이유 키는 d1Base 에만)
    assert V.D1_WHY == ("noTrade", "range", "new", "prev")
