# -*- coding: utf-8 -*-
"""한국 주식 분할 — #186 2차 리뷰 (Fable, 2026-11-28) 뒤에 고친 것 (새 시험 파일).

- B1: 관문의 '한 실행' 실패 줄은 이 실행이 스스로 판정해 처음 생긴 줄 (splitsKr.runNew) 만 세요 (Jack 의 말 그대로 "when many appear in one run").
  발행하지 못한 실행도 DART 보관본은 저장돼요 (워크플로의 if: always()) — '직전 발행본 뒤 새로' 를 세면 그 판정이 다음 실행에 쌓여 한 번 실패하면 다시
  통과하지 못했어요. 그 수는 경고 줄에만 보여요. 진짜로 많이 나온 실행은 여전히 실패하고, 그 판정은 보관돼 다음 실행에는 이 실행의 것이 아니에요.
- S1: 거래정지 중인 병합의 두 날이 두 실행에 걸치면 그 종목을 다음 대기 (dq) 에 남겨 다음 실행에 다음 일별 시세를 다시 봐요.
- 그 밖: DART 목록이 000 인데 목록이 없으면 판정이 아니에요 (기다림) · 오늘 DART 코드가 없는 후보는 이어 둬요 · 원문을 읽지 못한 판정은
  KR_SPLIT_DOC_RETRY_DAYS 마다 다시 물어요 (몇 건인지 크게).
팔고 빼기의 잠긴 수량 (S2) 은 tests/test_kr_split_fractions.py.
"""
import datetime as dt
import hashlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_kr_splits as K  # noqa: E402

TODAY = K.TODAY


class Rep:
    """관문의 줄만 모아요 (check_kr_split_nofile 이 부르는 것)."""

    def __init__(self):
        self.rows = {}

    def add(self, name, ok, val, rule, warn=False):
        self.rows[name] = ("PASS" if ok and not warn else "WARN" if ok else "FAIL", val)

    def skip(self, *a, **k):
        pass

    def detail(self, *a, **k):
        pass


def split_cand(t, d, r=5.0):
    return F._kr_cand(t, d, 5000.0 * r, 5000.0, 1_000_000.0, 1_000_000.0 * r, "seed")


SEED = [split_cand(f"{i:05d}0", f"20{24 + i % 2}-0{1 + i % 9}-1{i % 9}") for i in range(1, 121)]
KR = K.kr_rows(*[c["t"] for c in SEED])
CMAP = {c["t"]: f"C{c['t']}" for c in SEED}


def is_no(t, d, share):
    return int(hashlib.sha1(f"{t}|{d}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < share


def fake_dart(share):
    """사건마다 정해진 '없음' (share 의 비율) · 나머지는 시세와 같은 공시 — 한 번 묻는 데 호출 1 (없음) · 2 (있음)."""
    def ask(client, corp, cand, today):
        if is_no(cand["t"], cand["d"], share):
            client.status["000"] += 1
            return {"v": "no", "code": "nodoc", "note": "x"}, None
        client.status["000"] += 2
        return {"v": "ok", "k": "split", "r": cand["r"], "rc": "20260101000001", "dl": cand["d"], "de": None, "src": "doc"}, None
    return ask


def one_run(prev, client, today):
    rows, info = F.kr_splits_fields(prev, KR, [], client, today, seed=SEED, cmap=CMAP)
    cur = {"splits": sorted(rows), "splitsKr": info, "stocks": KR}
    rep = Rep()
    V.check_kr_split_nofile(rep, cur, [], today, prev)
    return cur, rep.rows


def since_publish(cur, prev):
    old = {(x[0], x[1]) for x in ((prev or {}).get("splitsKr") or {}).get("nofile") or []}
    return [x for x in cur["splitsKr"]["nofile"] if (x[0], x[1]) not in old]


# ── B1: 발행하지 못한 실행의 판정은 쌓이지 않아요 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("share, stopped", [(0.25, {1, 2, 3}), (0.25, {2, 3, 4, 5}), (0.3, {1, 2})])
def test_runs_that_do_not_publish_never_add_up_to_a_fail(monkeypatch, share, stopped):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "kr_split_dart", fake_dart(share))
    client = K.FakeDart()                      # 보관본 (entries) 은 실행마다 이어져요 — 발행하지 못해도 저장돼요
    prev, today, worst = None, TODAY, 0
    for i in range(1, max(stopped) + 4):
        cur, rows = one_run(prev, client, today)
        assert rows[V.KR_NOFILE_RUN_ROW][0] == "PASS", (i, rows[V.KR_NOFILE_RUN_ROW])
        assert len(cur["splitsKr"]["runNew"]) < V.KR_SPLIT_NOFILE_RUN_FAIL
        worst = max(worst, len(since_publish(cur, prev)))
        if i not in stopped:                   # 다른 까닭으로 발행하지 못한 실행은 직전 발행본이 그대로예요
            prev = cur
        today += dt.timedelta(days=1)
    assert worst >= V.KR_SPLIT_NOFILE_RUN_FAIL                     # 예전처럼 '직전 발행본 뒤 새로' 를 셌다면 실패했을 거예요


def test_a_publish_without_the_split_record_does_not_trip_the_next_run(monkeypatch):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "kr_split_dart", fake_dart(0.3))
    client, prev, today = K.FakeDart(), None, TODAY
    for _ in range(4):
        prev, _rows = one_run(prev, client, today)
        today += dt.timedelta(days=1)
    assert len(prev["splitsKr"]["nofile"]) >= V.KR_SPLIT_NOFILE_RUN_FAIL
    bare = {k: v for k, v in prev.items() if k != "splitsKr"}           # 되돌린 뒤 다시 들어온 날 · splitsKr 이 없는 발행본
    cur, rows = one_run(bare, client, today)
    assert rows[V.KR_NOFILE_RUN_ROW][0] == "PASS" and len(cur["splitsKr"]["runNew"]) < V.KR_SPLIT_NOFILE_RUN_FAIL
    assert rows[V.KR_NOFILE_SUM_ROW][0] == "WARN" and f"직전 발행본 뒤 새로 {len(since_publish(cur, bare))}건" in rows[V.KR_NOFILE_SUM_ROW][1]
    assert len(since_publish(cur, bare)) >= V.KR_SPLIT_NOFILE_RUN_FAIL


def test_a_real_burst_in_one_run_fails_and_the_next_run_does_not_count_it_again(monkeypatch):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "kr_split_dart", fake_dart(1.0))
    monkeypatch.setattr(F, "KR_SPLIT_DART_PER_RUN", 10 ** 6)
    client = K.FakeDart()
    before = {"splits": [], "stocks": KR, "splitsKr": {"nofile": [], "runNew": []}}       # 직전 발행본 (실패한 실행 뒤에도 그대로)
    cur, rows = one_run(before, client, TODAY)
    assert rows[V.KR_NOFILE_RUN_ROW][0] == "FAIL" and len(cur["splitsKr"]["runNew"]) == len(SEED) == cur["splitsKr"]["nofileN"]
    # 실패해 발행하지 못했어요 (직전 발행본 그대로) · 판정은 보관됐어요 → 다음 실행은 이 실행이 판정한 것이 없어요 (RUNBOOK 의 나가는 길)
    nxt, rows2 = one_run(before, client, TODAY + dt.timedelta(days=1))
    assert rows2[V.KR_NOFILE_RUN_ROW][0] == "PASS" and nxt["splitsKr"]["runNew"] == [] and nxt["splitsKr"]["nofileN"] == len(SEED)
    assert rows2[V.KR_NOFILE_SUM_ROW][0] == "WARN"


def test_a_re_asked_no_already_published_is_not_new(monkeypatch):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "kr_split_dart", fake_dart(1.0))
    monkeypatch.setattr(F, "KR_SPLIT_DART_PER_RUN", 10 ** 6)
    recent = [split_cand("000010", "2026-10-02")]
    prev = {"splits": [], "splitsKr": {"nofile": [["000010", "2026-10-02", 5.0, "nodoc"]]}}
    client = K.FakeDart()
    client.entries["C1|krsplit|v2|2026-10-02"] = {"st": "000", "at": "2026-10-20", "d": {"v": "no", "code": "nodoc", "note": "x"}}
    _rows, info = F.kr_splits_fields(prev, K.kr_rows("000010"), [], client, TODAY, seed=recent, cmap={"000010": "C1"})
    assert info["nofile"] == [["000010", "2026-10-02", 5.0, "nodoc"]] and info["runNew"] == []          # 14일 뒤 다시 물었지만 이미 있던 줄


def test_the_carried_record_says_this_run_judged_nothing(monkeypatch):
    K.Log(monkeypatch)
    prev = {"splits": [], "splitsKr": {"nofile": [["000010", "2026-10-02", 5.0, "nodoc"]], "runNew": [["000010", "2026-10-02"]]}}
    _rows, info = F.kr_splits_carry(prev, TODAY)
    assert info["runNew"] == [] and info["nofile"] == [["000010", "2026-10-02", 5.0, "nodoc"]]
    rep = Rep()
    V.check_kr_split_nofile(rep, {"splits": [], "splitsKr": info, "stocks": []}, [], TODAY, prev)
    assert rep.rows[V.KR_NOFILE_RUN_ROW][0] == "PASS"


# ── S1: 두 실행에 걸친 거래정지 병합 ───────────────────────────────────────────────────────────────────────────

HALT = [("2025-12-05", 171.0, 159224163), ("2025-12-08", 171.0, 159224163), ("2025-12-09", 171.0, 15922416), ("2025-12-10", 1710.0, 15922416),
        ("2025-12-11", 1710.0, 15922416)]


def daum_upto(day, rows=HALT):
    return lambda c, n: {"data": [{"date": d + " 00:00:00", "tradePrice": p, "changePrice": 0.0, "listedSharesCount": s, "prevClosingPrice": 0.0}
                                  for d, p, s in reversed(rows) if d <= day]}


def test_a_halted_merge_over_two_runs_is_kept_for_daum_and_found_on_the_price_day(monkeypatch):
    log = K.Log(monkeypatch)
    kr = lambda shr: [{"t": "123450", "nk": "x", "cls": "kr", "cap": 1.0, "shr": shr}]          # noqa: E731
    client = K.FakeDart()
    client.meta["corpMap"] = {"123450": "C1"}
    prev = {"pxDate": "2025-12-08", "stocks": kr(159224163), "splits": []}
    got = []
    for day in ("2025-12-09", "2025-12-10", "2025-12-11"):
        out = F.kr_splits_step({"splits": [], "splitsFrom": "2016-01-01"}, prev, kr(15922416), client, dt.date.fromisoformat(day), [], px_date=day,
                               daum=daum_upto(day))
        i = out["splitsKr"]
        got.append((i["dq"], [x[:2] for x in i["nofile"]]))
        prev = {"pxDate": day, "stocks": kr(15922416), "splits": out["splits"], "splitsKr": i}
    assert got[0] == ([["123450", "2025-12-08"]], [])                                       # A 의 실행: 짝이 아직 — 다음 대기에 남겨요
    assert log.has("123450 상장주식수가 2025-12-09 에", "기준가는 아직 그대로예요", "splitsKr.dq")
    assert got[1] == ([], [["123450", "2025-12-09"]]) and got[2] == ([], [["123450", "2025-12-09"]])   # B 의 실행에서 짝지어 판정 · 그 뒤 이어요
    assert prev["splitsKr"]["nofile"][0][4] == "2025-12-10"


def test_the_open_pair_closes_after_five_trading_days_without_a_reset():
    seq = [(d, p, p, float(s)) for d, p, s in HALT[:3]]
    assert F.kr_split_pair_open(seq, lo="2025-12-08", hi="2025-12-09") == "2025-12-09"
    flat = seq + [(f"2025-12-1{i}", 171.0, 171.0, 15922416.0) for i in range(5)]
    assert F.kr_split_pair_open(flat, lo="2025-12-08", hi="2025-12-19") is None               # 5거래일이 지나도 기준가가 그대로 — 닫혀요
    done = [(d, p, p, float(s)) for d, p, s in HALT]
    assert F.kr_split_pair_open(done, lo="2025-12-08", hi="2025-12-11") is None                # 짝을 찾았어요
    assert F.kr_split_pairs("123450", done, "daum", lo="2025-12-08", hi="2025-12-11")


# ── 그 밖 ────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reply", [{"status": "000"}, {"status": "000", "list": []}, {"status": "000", "list": "x"}])
def test_a_list_reply_000_without_a_list_waits_and_is_not_a_no(monkeypatch, reply):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "KR_SPLIT_OVERRIDES", {k: v for k, v in F.KR_SPLIT_OVERRIDES.items() if k[0] != "035720"})
    c = K.FakeDart(list_reply=reply)
    rows, info = F.kr_splits_fields(None, K.kr_rows("035720"), [], c, TODAY, seed=[K.cand("035720")])
    assert rows == [] and info["out"] == [] and info["nofile"] == [] and info["fail"] == [["035720", "2021-04-15", "status"]]
    assert not any("krsplit" in k for k in c.entries)


@pytest.mark.parametrize("cr", [{"status": "000"}, {"status": "000", "list": []}])
def test_a_cr_reply_000_without_a_list_waits(monkeypatch, cr):
    K.Log(monkeypatch)                                          # 알파칩스 2025-07-09 10:1 감자 (목록에는 감자결정 · crDecsn 이 모양이 틀린 000)
    c = K.alpha_dart(cr=cr)
    rows, info = F.kr_splits_fields(None, K.kr_rows("117670"), [], c, TODAY, seed=[K.cand("117670")])
    assert [p.get("pblntf_detail_ty", ep) for ep, p in c.calls] == ["I001", "B001", "crDecsn.json"]
    assert rows == [] and info["fail"] == [["117670", "2025-07-09", "status"]] and info["nofile"] == [] and not any("krsplit" in k for k in c.entries)


def test_a_candidate_without_a_dart_code_is_kept_and_counted_once(monkeypatch):
    K.Log(monkeypatch)
    c0 = F._kr_cand("000010", "2026-11-10", 25000.0, 5000.0, 1_000_000.0, 5_000_000.0, "krx")
    client = K.FakeDart()
    rows, info = F.kr_splits_fields(None, K.kr_rows("000010"), [c0], client, TODAY, seed=[], cmap={"000020": "C2"})
    assert info["out"] == [["000010", "2026-11-10", "nocorp"]] and info["runNew"] == [["000010", "2026-11-10"]]
    assert [x[:2] for x in info["pend"]] == [["000010", "2026-11-10"]]                  # 목록 파일의 창 뒤에도 코드가 생기면 물어요
    prev = {"splits": rows, "splitsKr": info}
    _rows, info2 = F.kr_splits_fields(prev, K.kr_rows("000010"), [], client, TODAY + dt.timedelta(days=30), seed=[], cmap={"000020": "C2"})
    assert info2["runNew"] == [] and [x[:2] for x in info2["pend"]] == [["000010", "2026-11-10"]] and [x[:2] for x in info2["nofile"]] == [["000010", "2026-11-10"]]
    # 코드가 생기면 물어요 (DART 가 결정 없음이라 해도 이미 있던 줄이라 새로 세지 않아요)
    _rows, info3 = F.kr_splits_fields({"splits": rows, "splitsKr": info2}, K.kr_rows("000010"), [], client, TODAY + dt.timedelta(days=31), seed=[],
                                      cmap={"000010": "C1"})
    assert info3["calls"] > 0 and info3["out"] == [["000010", "2026-11-10", "nodoc"]] and info3["runNew"] == []


@pytest.mark.parametrize("code, at, asked", [("unread", "2026-10-01", True), ("gone", "2026-10-01", True), ("pages", "2026-10-01", True),
                                             ("unread", "2026-11-15", False), ("nodoc", "2026-10-01", False)])
def test_an_unread_document_is_asked_again_on_a_slow_schedule_and_counted_loudly(monkeypatch, code, at, asked):
    log = K.Log(monkeypatch)
    old = split_cand("000010", "2024-03-04")                    # 120일보다 오래된 사건 (늦은 정정 공시로는 다시 묻지 않아요)
    client = K.FakeDart()
    client.entries["C1|krsplit|v2|2024-03-04"] = {"st": "000", "at": at, "d": {"v": "no", "code": code, "note": "x"}}
    _rows, info = F.kr_splits_fields(None, K.kr_rows("000010"), [], client, TODAY, seed=[old], cmap={"000010": "C1"})
    assert bool(client.calls) is asked
    if code in F.KR_SPLIT_DOC_RETRY and not asked:
        assert log.has("원문을 읽지 못한 판정 1", f"{F.KR_SPLIT_DOC_RETRY_DAYS}일마다 다시 물어요", "이번 실행에 다시 물음 0")
    if asked:
        assert log.has("이번 실행에 다시 물음 1") and info["out"] == [["000010", "2024-03-04", "nodoc"]]
