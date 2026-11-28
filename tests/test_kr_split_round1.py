# -*- coding: utf-8 -*-
"""한국 주식 분할 — #186 1차 리뷰 (Opus · Fable, 2026-11-28) 뒤에 고친 것 (새 시험 파일).

- B1 (Fable) = S3 (Opus): 오늘 목록에 없는 종목의 '공시로 확인하지 못한 분할' (nofile) · 이어 둔 후보 (pend) 는 그대로 이어요 (오래되거나 확인될
  때만 빠져요) — 다음에 그 종목이 다시 들어오면 숫자가 그대로 비어요. 단계 전체가 멈춰도 (안 · 밖) 지난 발행본의 splitsKr 을 이어요.
- S1 (Opus): 거래정지 중인 병합 — 주식 수의 날과 기준가의 날이 5거래일 안 (043220 2025-12-09 · 12-10): 두 날로 짝지어 한 후보 · 공시의
  상장예정일은 둘 중 하나 · 영수증이 두 날과 어느 날인지 적어요 · 시드에 6줄이 돌아오고 182400 이 더해져요.
- S4 (Fable): DART 의 오류 · 시간 넘김 · 빈 답 · 한도는 '맞지 않음' 판정이 되지 않아요 (기다림) · NAVER 2018 · 카카오 2021 은 적어 둔 원문의
  숫자로 고정 줄 (첫 실행의 DART 답에 기대지 않아요).
- 그 밖: 우선주는 판정을 따로 보관해요 · 2:5 · 5:2 도 nofile · 배율 있는 한국 SPLIT_OVERRIDES 줄도 세 확인 (N3) · 관문의 '이어짐' · '이번 실행' 줄.
팔았어요의 몫 (S4 Opus · Fable 의 날짜 순서) 은 tests/test_kr_split_fractions.py, 한 실행 한도는 tests/test_kr_split_three_way.py.
"""
import datetime as dt
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_kr_splits as K  # noqa: E402
import test_v196a_fxhist_splits as T196  # noqa: E402

TODAY = K.TODAY
# 043220 티에스넥스젠의 다음 일별 시세 (수정하지 않은 값 · 2025-12-08 ~ 12-12): 12-09 주식 수 ÷ 10 (값 그대로 · 거래정지) · 12-10 기준가 1,710
HALT = [("2025-12-08", 171.0, 171.0, 159224163.0), ("2025-12-09", 171.0, 171.0, 15922416.0), ("2025-12-10", 1710.0, 1710.0, 15922416.0),
        ("2025-12-11", 1710.0, 1710.0, 15922416.0), ("2025-12-12", 1710.0, 1710.0, 15922416.0)]


def nodoc():
    return K.FakeDart()


def krx_cand(t, d, r=5.0):
    return F._kr_cand(t, d, 5000.0 * r, 5000.0, 1_000_000.0, 1_000_000.0 * r, "krx")


# ── B1: 오늘 목록에 없는 종목의 줄 ─────────────────────────────────────────────────────────────────────────────

def test_an_absent_stock_keeps_its_entries_and_is_blanked_again_when_it_returns(monkeypatch):
    K.Log(monkeypatch)
    cmap = {"000010": "C1"}
    day0 = dt.date(2026, 12, 2)
    c = nodoc()
    _r, info0 = F.kr_splits_fields(None, K.kr_rows("000010"), [krx_cand("000010", "2026-12-01")], c, day0, seed=[], cmap=cmap)
    assert info0["nofile"] == [["000010", "2026-12-01", 5.0, "nodoc"]] and [x[:2] for x in info0["pend"]] == [["000010", "2026-12-01"]]
    prev = {"splits": [], "splitsKr": info0}
    # 99일 뒤 한 실행 동안 그 종목이 목록에 없어요 (다른 종목만) — 그대로 이어요
    _r, info1 = F.kr_splits_fields(prev, K.kr_rows("000020"), [], c, day0 + dt.timedelta(days=99), seed=[], cmap=cmap)
    assert info1["nofile"] == info0["nofile"] and [x[:2] for x in info1["pend"]] == [["000010", "2026-12-01"]]
    # 다시 들어와요: 줄이 그대로 · 숫자를 비워요
    _r, info2 = F.kr_splits_fields({"splits": [], "splitsKr": info1}, K.kr_rows("000010"), [], c, day0 + dt.timedelta(days=100), seed=[], cmap=cmap)
    assert info2["nofile"] == info0["nofile"]
    s = {"t": "000010", "cls": "kr", **{k: 1.0 for k in V.PX_BAD_DATA}}
    got = F.mark_split_nofile([s], info2["nofile"], {"000010": {"y": "2026-03-01", "q": "2026-12-20", "m": "2027-02-10", "s": "2024-01-02"}})
    assert got["hidden"] == ["000010"] and s["spNo"] == "2026-12-01" and "vol" not in s and "hi" not in s
    # 시계열이 닿는 날(3년 40일)보다 오래되면 빠져요
    far = day0 + dt.timedelta(days=F.KR_SPLIT_NOFILE_KEEP_DAYS + 2)
    _r, info3 = F.kr_splits_fields({"splits": [], "splitsKr": info1}, K.kr_rows("000020"), [], c, far, seed=[], cmap=cmap)
    assert info3["nofile"] == [] and info3["pend"] == []


def test_the_error_paths_carry_everything_loudly(monkeypatch):
    log = K.Log(monkeypatch)
    prev = {"splits": [["005930", "2018-05-04", 50.0]],
            "splitsKr": {"rows": [["005930", "2018-05-04", 50.0, "fixed", "KR_SPLIT_OVERRIDES", "fixed"]],
                         "nofile": [["000099", "2026-11-02", 5.0, "nodoc"], ["000010", "2026-11-03", 0.2, "nocorp", "2026-11-05"]],
                         "pend": [["000099", "2026-11-02", 25000.0, 5000.0, 1000000.0, 5000000.0],
                                  ["000010", "2026-11-03", 171.0, 1710.0, 100.0, 10.0, "2026-11-05"]], "dq": [["000030", "2026-11-10"]]}}
    monkeypatch.setattr(F, "_kr_splits_fields", lambda *a: 1 / 0)
    rows, info = F.kr_splits_fields(prev, K.kr_rows("005930"), [], None, TODAY, seed=[])          # 000099 · 000010 은 오늘 목록에 없어요
    assert rows == [["005930", "2018-05-04", 50.0]] and info["src"] == "err"
    assert info["nofile"] == prev["splitsKr"]["nofile"] and info["pend"] == prev["splitsKr"]["pend"] and info["dq"] == prev["splitsKr"]["dq"]
    assert log.has("!! 한국 주식 분할: 지난 발행본에서 그대로 이었어요", "공시로 확인하지 못한 분할 2", "이어 둔 후보 2")
    # 밖의 멈춤 (kr_splits_step 이 오류): main 이 지난 발행본의 splitsKr 을 이어요
    sp = {"splits": [["AAPL", "2020-08-31", 4.0]], "splitsFrom": V.SPLITS_FROM}
    out = F.kr_splits_step_carry(sp, prev, TODAY)
    assert out["splits"] == [["005930", "2018-05-04", 50.0], ["AAPL", "2020-08-31", 4.0]] and out["splitsKr"]["nofile"] == prev["splitsKr"]["nofile"]
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    m = src[src.index("def main():"):]
    i = m.index("sp_fields = kr_splits_step(sp_fields, prev, kr, client")
    assert "sp_fields = kr_splits_step_carry(sp_fields, prev, today)" in m[i:i + 600]
    assert "except Exception:\n            pass" not in src[src.index("def kr_splits_carry("):src.index("def _kr_splits_fields(")]   # N4: 조용히 넘기지 않아요


# ── S1: 거래정지 중인 병합 (두 날) ─────────────────────────────────────────────────────────────────────────────

def test_a_halted_merge_pairs_the_share_day_with_the_price_day():
    got = F.kr_split_pairs("043220", HALT, "daum")
    assert [(x["t"], x["d"], x["dp"], x["r"], x["how"]) for x in got] == [("043220", "2025-12-09", "2025-12-10", 0.1, "pair")]
    assert (got[0]["close"], got[0]["base"], got[0]["sa"], got[0]["sb"]) == (171.0, 1710.0, 159224163.0, 15922416.0)
    # 기준가가 5거래일 안에 다시 정해지지 않으면 · 그 사이 주식 수가 또 바뀌면 · 기준가가 배율과 다르게 움직이면 짝이 아니에요
    late = HALT[:2] + [(f"2025-12-1{i}", 171.0, 171.0, 15922416.0) for i in range(5)] + [("2025-12-17", 1710.0, 1710.0, 15922416.0)]
    assert F.kr_split_pairs("043220", late, "daum") == []
    moved = HALT[:2] + [("2025-12-10", 1710.0, 1710.0, 31844832.0)]
    assert F.kr_split_pairs("043220", moved, "daum") == []
    wrong = HALT[:2] + [("2025-12-10", 500.0, 500.0, 15922416.0)]
    assert F.kr_split_pairs("043220", wrong, "daum") == []
    # 하루짜리 사건 (그날 기준가도 움직임) 은 짝으로 다시 세지 않아요
    assert F.kr_split_pairs("117670", [("2025-07-08", 790.0, 790.0, 61394681.0), ("2025-07-09", 9000.0, 9580.0, 6139468.0)], "daum") == []


def test_the_daily_sources_find_the_pair(monkeypatch):
    # KRX 목록 파일: 12-10 의 기준가 재설정 (kr_ref_links) · 12-09 에 주식 수만 ÷ 10
    def df(close, changes, stocks):
        return pd.DataFrame({"Code": ["043220", "000010"], "Close": [close, 1000.0], "Changes": [changes, 0.0], "Marcap": [close * stocks, 1000.0 * 10],
                             "Stocks": [stocks, 10]})
    files = [(dt.date(2025, 12, 10), df(1710.0, 0.0, 15922416)), (dt.date(2025, 12, 9), df(171.0, 0.0, 15922416)),
             (dt.date(2025, 12, 8), df(171.0, 0.0, 159224163))]
    _by, events = F.kr_ref_links(files, [pd.Timestamp(d) for d, _ in files])
    got = F.kr_split_cands(files, events)
    assert [(x["t"], x["d"], x.get("dp"), x["r"], x["src"]) for x in got] == [("043220", "2025-12-09", "2025-12-10", 0.1, "krx")]
    # 다음 일별 시세 (목록 파일이 없던 날)
    rows = {"data": [{"date": d + " 00:00:00", "tradePrice": c, "changePrice": 0.0, "listedSharesCount": s, "prevClosingPrice": 0.0}
                     for d, c, _b, s in reversed(HALT)]}
    got, seen, bad, stop = F.kr_split_daum_cands([("043220", "2025-12-05")], "2025-12-12", fetch=lambda c, n: rows)
    assert [(x["t"], x["d"], x.get("dp"), x["r"], x["src"]) for x in got] == [("043220", "2025-12-09", "2025-12-10", 0.1, "daum")]


@pytest.mark.parametrize("dl, row_date, on", [("2025-12-09", "2025-12-09", "shr"), ("2025-12-10", "2025-12-10", "px")])
def test_the_filing_matches_either_day_and_the_receipt_says_which(monkeypatch, dl, row_date, on):
    K.Log(monkeypatch)
    cand = F.kr_split_pairs("043220", HALT, "krx")[0]
    c = K.FakeDart()
    c.entries["C1|krsplit|v2|2025-12-09"] = K.ok_verdict(0.1, "20251101000001", "merge", dl)
    rows, info = F.kr_splits_fields(None, K.kr_rows("043220"), [cand], c, TODAY, seed=[], cmap={"043220": "C1"})
    assert rows == [["043220", row_date, 0.1]]
    chk = info["rows"][0][6]
    assert chk == {"dl": dl, "shr": 0.1, "px": 0.1, "rule": "auction", "dShr": "2025-12-09", "dPx": "2025-12-10", "dlOn": on}
    assert V.kr_split_receipt_ok(info["rows"][0]) and F.kr_split_chk_clean(chk) == chk


def test_a_filing_for_neither_day_leaves_a_paired_entry_without_a_filing(monkeypatch):
    K.Log(monkeypatch)
    cand = F.kr_split_pairs("043220", HALT, "krx")[0]
    c = K.FakeDart()
    c.entries["C1|krsplit|v2|2025-12-09"] = K.ok_verdict(0.1, "20251101000001", "merge", "2026-01-20")   # 거래 재개일에 상장 (둘 다 아님)
    rows, info = F.kr_splits_fields(None, K.kr_rows("043220"), [cand], c, dt.date(2025, 12, 20), seed=[], cmap={"043220": "C1"})
    assert rows == [] and info["out"] == [["043220", "2025-12-09", "diff"]]
    assert info["nofile"] == [["043220", "2025-12-09", 0.1, "diff", "2025-12-10"]]                   # 다섯째 칸: 기준가의 날
    # 이어 두는 후보도 두 날을 그대로 (일곱째 칸)
    assert info["pend"] == [["043220", "2025-12-09", 171.0, 1710.0, 159224163.0, 15922416.0, "2025-12-10"]]
    pend, _dq = F.kr_prev_pend({"splitsKr": info})
    assert pend[0]["dp"] == "2025-12-10" and pend[0]["how"] == "pair"
    # 숫자 비우기는 늦은 날 (기준가의 날) 로 창을 봐요 · 관문의 비움 줄이 그 날짜를 받아요
    s = {"t": "043220", "cls": "kr", **{k: 1.0 for k in V.PX_BAD_DATA}}
    F.mark_split_nofile([s], info["nofile"], {"043220": {"y": "2025-03-01", "q": "2025-08-20", "m": "2025-12-10", "s": "2023-01-02"}})
    assert s["spNo"] == "2025-12-10" and "r1" not in s


def test_the_seed_gets_back_the_paired_lines():
    seed = {(x["t"], x["d"]): x for x in F.load_kr_split_seed()}
    back = {("000300", "2026-01-14"): "2026-01-15", ("009310", "2026-05-11"): "2026-05-12", ("011000", "2026-07-21"): "2026-07-22",
            ("041590", "2025-05-23"): "2025-05-26", ("043220", "2025-12-09"): "2025-12-10", ("074610", "2025-12-29"): "2025-12-30",
            ("182400", "2025-07-22"): "2025-07-23"}
    for k, dp in back.items():
        assert seed[k]["how"] == "pair" and seed[k]["dp"] == dp and F.kr_split_market_whole(seed[k]) == seed[k]["r"], k
    assert sum(1 for x in seed.values() if x.get("dp")) == 7
    with open(F.KR_SPLIT_SEED_PATH, encoding="utf-8") as f:
        head = f.read()
    assert "\n" + F.KR_SPLIT_SEED_HEAD + "\n" in head and F.KR_SPLIT_SEED_HEAD.endswith(",price_date")


# ── S4: DART 의 오류는 판정이 아니에요 · NAVER · 카카오 고정 줄 ─────────────────────────────────────────────────

class Boom(K.FakeDart):
    def get(self, ep, params):
        self.calls.append((ep, dict(params)))
        raise TimeoutError("read timed out")


@pytest.mark.parametrize("make, code", [
    (lambda: K.kakao_dart(fail=True), "net"),                                   # 연결 · 시간 넘김: client.get 이 None
    (lambda: K.FakeDart(list_reply={"status": "020", "message": "요청 제한 초과"}), "status"),   # 한도
    (lambda: K.FakeDart(list_reply={"status": "800"}), "status"),               # 점검
    (lambda: K.FakeDart(list_reply={}), "status"),                              # 빈 답 (상태 없음)
    (lambda: K.FakeDart(list_reply={"status": None}), "status"),
    (lambda: K.kakao_dart(said={"20210225800978": "900"}), "status"),            # 원문 대신 오류 상태
    (lambda: K.kakao_dart(said={"20210225800978": "예외"}), "net"),              # 원문을 받지 못함
    (lambda: Boom(), "err"),                                                    # 우리 쪽에서 난 예외
])
def test_a_dart_error_timeout_empty_reply_or_throttle_never_becomes_a_no(monkeypatch, make, code):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "KR_SPLIT_OVERRIDES", {k: v for k, v in F.KR_SPLIT_OVERRIDES.items() if k[0] != "035720"})
    c = make()
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720"), [], c, TODAY, seed=[K.cand("035720")])
    assert rows == [] and info["out"] == [] and info["nofile"] == [], info
    assert info["fail"] == [["035720", "2021-04-15", code]]
    assert not any("krsplit" in k for k in c.entries)                           # 보관하지 않아요 (다음 실행에 다시)
    rep = T196.check(*gate_with_info(info))
    assert T196.row(rep, V.KR_NOFILE_MUST_ROW)[3] == "PASS"


def gate_with_info(info):
    cur, prev, final = K.gate_pair()
    cur["data"]["splitsKr"] = {**cur["data"]["splitsKr"], "fail": info["fail"], "failN": len(info["fail"]), "nofile": info["nofile"]}
    return cur, prev, final


def test_naver_2018_and_kakao_2021_are_fixed_rows_from_the_filing_text_read_on_11_23():
    for (t, d), rc in ((("035420", "2018-10-12"), "20180726800004"), (("035720", "2021-04-15"), "20210225800978")):
        ev = F.KR_SPLIT_OVERRIDE_EVIDENCE[(t, d)]
        doc, _why = F.parse_kr_split_doc(K.doc_text(rc), "split", rc)
        assert ev["doc"] == "copy" and ev["rc"] == rc and ev["r"] == doc["r"] == F.KR_SPLIT_OVERRIDES[(t, d)][0] and ev["dl"] == doc["dl"] == d
        x = next(s for s in F.load_kr_split_seed() if (s["t"], s["d"]) == (t, d))
        assert (ev["close"], ev["base"], ev["sa"], ev["sb"]) == (x["close"], x["base"], x["sa"], x["sb"])
    # 빈 판정 보관본 · DART 꺼짐에서도 실려요 (DART 에 묻지 않아요) — 필수 종목이 첫 실행의 답으로 막히지 않아요
    c = K.FakeDart()
    rows, info = F.kr_splits_fields(None, K.kr_rows("035420", "035720"), [], c, TODAY, seed=F.load_kr_split_seed())
    assert rows == [["035420", "2018-10-12", 5.0], ["035720", "2021-04-15", 5.0]] and c.calls == [] and info["nofile"] == []
    assert all(r[6]["doc"] == "copy" and V.kr_split_receipt_ok(r) for r in info["rows"])


def test_the_preferred_share_keeps_its_own_verdict(monkeypatch):
    K.Log(monkeypatch)
    c = K.FakeDart()
    c.entries["C1|krsplit|v2|2025-03-04"] = {"st": "000", "at": "2026-11-20", "d": {"v": "no", "code": "shr", "note": "보통주의 시세와 다름"}}
    pref = krx_cand("000015", "2025-03-04")
    rows, info = F.kr_splits_fields(None, K.kr_rows("000015"), [pref], c, TODAY, seed=[], cmap={"000010": "C1"})
    assert info["out"] == [["000015", "2025-03-04", "nodoc"]] and c.calls                       # 보통주의 '맞지 않음' 을 쓰지 않고 물어요
    assert "C1|krsplit|v2|2025-03-04|000015" in c.entries


def test_two_five_and_five_two_count_as_without_a_filing():
    for r in (2.5, 0.4):
        c = F._kr_cand("000010", "2026-03-02", 5000.0 * r, 5000.0, 1000000.0, 1000000.0 * r, "krx")
        assert F.kr_split_market_whole(c) == r
    assert F.kr_split_share_clean(4.6) is None and F.kr_split_share_clean(4.3) is None and F.kr_split_share_clean(0.8347) == 5 / 6
    assert F.kr_split_share_clean(1.05) is None                                   # 10% 안의 변화는 사건이 아니에요


def test_a_korean_split_overrides_row_with_a_ratio_needs_the_three_checks(monkeypatch):
    log = K.Log(monkeypatch)
    table = dict(F.SPLIT_OVERRIDES)
    table[("000010", "2025-03-04")] = (5.0, "시험: 근거 없는 고정 줄")
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", table)
    rows, _info = F.kr_splits_fields(None, K.kr_rows("000010"), [], None, TODAY, seed=[])
    assert rows == [] and log.has("SPLIT_OVERRIDES 의 000010 2025-03-04 ×5", "세 확인을 지나지 못해요 (noEvidence)")
    ev = dict(F.KR_SPLIT_OVERRIDE_EVIDENCE)
    ev[("000010", "2025-03-04")] = {"close": 25000.0, "base": 5000.0, "sa": 100.0, "sb": 500.0, "dl": "2025-03-04", "rc": "20250101000001"}
    monkeypatch.setattr(F, "KR_SPLIT_OVERRIDE_EVIDENCE", ev)
    rows, info = F.kr_splits_fields(None, K.kr_rows("000010"), [], None, TODAY, seed=[])
    assert rows == [["000010", "2025-03-04", 5.0]] and V.kr_split_receipt_ok(info["rows"][0]) and info["rows"][0][4] == "SPLIT_OVERRIDES"


# ── 관문: 이어짐 · 이번 실행 (경고만) ──────────────────────────────────────────────────────────────────────

def keep_gate(today_nofile, prev_nofile, kr=()):
    cur, prev, final = K.gate_pair(new_kr=(("005930", "2018-05-04", 50.0),) + tuple(kr))
    if today_nofile is None:
        cur["data"].pop("splitsKr")
    else:
        cur["data"]["splitsKr"]["nofile"] = today_nofile
    prev["data"]["splitsKr"] = {"nofile": prev_nofile}
    return T196.check(cur, prev, final)


def test_the_gate_warns_when_a_record_vanishes_without_a_reason():
    e = ["000660", "2026-10-01", 5.0, "nodoc"]
    rep = keep_gate([], [e])
    assert not [r for r in rep.failed if r[0] == V.KR_NOFILE_KEEP_ROW] and T196.row(rep, V.KR_NOFILE_KEEP_ROW)[3] == "WARN"
    assert "까닭 없이 사라진 줄 1: 000660 2026-10-01" in T196.row(rep, V.KR_NOFILE_KEEP_ROW)[1]
    rep = keep_gate(None, [e])                                                     # 오늘 파일에 목록이 아예 없어요
    assert T196.row(rep, V.KR_NOFILE_KEEP_ROW)[3] == "WARN" and "splitsKr.nofile 이 없어요" in T196.row(rep, V.KR_NOFILE_KEEP_ROW)[1]
    assert T196.row(rep, V.KR_NOFILE_MUST_ROW)[3] == "PASS"                        # 실패 줄로 하지 않아요 (Jack 에게 묻는 것)
    assert T196.row(keep_gate([e], [e]), V.KR_NOFILE_KEEP_ROW)[3] == "PASS"         # 이어졌어요
    old = ["000660", "2022-01-03", 5.0, "nodoc"]                                   # 3년 40일보다 오래됨
    assert T196.row(keep_gate([], [old]), V.KR_NOFILE_KEEP_ROW)[3] == "PASS"


def test_the_run_row_shows_the_new_total_and_the_blanked_count():
    rep = keep_gate([["000660", "2026-10-01", 5.0, "nodoc"], ["000020", "2026-10-02", 5.0, "nodoc"]], [["000660", "2026-10-01", 5.0, "nodoc"]])
    row = T196.row(rep, V.KR_NOFILE_SUM_ROW)
    assert row[3] == "WARN" and row[1].startswith("이 실행이 새로 판정 0건 · 직전 발행본 뒤 새로 1건 · 전체 2건 (결정 공시 없음 2) · 숫자를 비운 종목 0")
    rep = keep_gate([["000660", "2026-10-01", 5.0, "nodoc"]], [["000660", "2026-10-01", 5.0, "nodoc"]])
    assert T196.row(rep, V.KR_NOFILE_SUM_ROW)[3] == "PASS"
