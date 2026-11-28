# -*- coding: utf-8 -*-
"""한국 주식 분할 — #186 3차 리뷰 (Fable, 2026-11-28 · 막는 것 없음) 뒤에 고친 것 (새 시험 파일).

- S1: 공시를 읽는 코드가 깨지면 (결정 공시는 있는데 읽지 못함) 사건 하나에 DART 호출이 2 ~ 4 번이라 한 실행에 13 ~ 20 사건만 물어 '한 실행' 실패 줄
  (16) 에 잘 걸리지 않아요. 새 실패 줄은 Jack 이 정해요 — 경고만 하는 줄 · 크게 남기는 줄 · GitHub 경고 (새로 물은 판정 8건 이상 중 80% 이상이
  확인되지 않으면). nofile 의 까닭은 '공시 없음' 과 '공시를 읽지 못함' 을 나눠 보여요.
- S2: 마지막 확인 종가로 보인 종목 (pxd) 의 다음 창은 그 pxd 에서 · 지난 발행본에 없다가 돌아온 종목도 다음을 읽어요.
- S3: 원문을 다시 읽을 때가 된 판정은 한 번도 묻지 않은 사건을 모두 물은 뒤 남은 한도로만 · gone 은 다시 묻지 않아요.
- S4: 다시 묻지 못하면 (DART 가 멈춤 · 묻다 실패) 보관본의 판정과 그 기록을 그대로 · runNew 는 판정이 없던 사건만 세요.
- 그 밖: nocorp 는 처음 본 실행만 세요 · 안쪽 오류 길에서도 이번 실행의 다음 대기 (dq) 를 이어요.
"""
import datetime as dt
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_kr_splits as K  # noqa: E402
import test_kr_split_round2 as R2  # noqa: E402

TODAY = K.TODAY


def unread_dart(client, corp, cand, today):
    """공시를 읽는 코드가 깨진 날: 결정 공시는 있는데 읽지 못해요 — 분할은 목록 1 + 원문 1, 병합은 + 감자 목록 1."""
    client.status["000"] += 3 if cand["r"] < 1 else 2
    return {"v": "no", "code": "unread", "note": "x"}, None


def gate(info, prev=None):
    rep = R2.Rep()
    V.check_kr_split_nofile(rep, {"splits": [], "splitsKr": info, "stocks": R2.KR}, [], TODAY, prev)
    return rep.rows


# ── S1: 깨진 읽기는 경고 · 크게 · GitHub 경고 ────────────────────────────────────────────────────────────────

def test_a_broken_reader_warns_loudly_without_stopping_and_says_unread(monkeypatch):
    log = K.Log(monkeypatch)
    said = []
    monkeypatch.setattr(F, "gh_warning", lambda title, text: said.append((title, text)))
    monkeypatch.setattr(F, "kr_split_dart", unread_dart)
    monkeypatch.setattr(F, "KR_SPLIT_DART_PER_RUN", F.KR_SPLIT_ONE_MAX + 2 * 11)        # 실제 한도 50 에서 읽지 못하는 병합이면 13 ~ 15 사건쯤 (broken.py)
    _rows, info = F.kr_splits_fields(None, R2.KR, [], K.FakeDart(), TODAY, seed=R2.SEED, cmap=R2.CMAP)
    n = info["read"]["n"]
    assert n == 12
    assert n >= V.KR_SPLIT_READ_MIN and info["read"]["no"] == n == info["read"]["doc"]
    assert len(info["runNew"]) == n < V.KR_SPLIT_NOFILE_RUN_FAIL                       # 한 실행 한도에는 걸리지 않아요 (그래서 이 줄)
    rows = gate(info)
    assert rows[V.KR_NOFILE_RUN_ROW][0] == "PASS"
    assert rows[V.KR_READ_ROW][0] == "WARN" and rows[V.KR_READ_ROW][1].startswith(f"새로 물은 판정 {n}건 · 확인되지 않음 {n}건 (100%)")
    assert log.has("!! 한국 주식 분할 —", "분할을 확인하지 못했어요", "공시를 읽는 코드가 깨졌을 수 있어요") and said and "대부분" in said[0][0]
    # 기록은 '공시 없음' 이 아니라 '읽지 못함' (unread) — 비우는 것은 같아요 (안전한 쪽)
    assert {x[3] for x in info["nofile"]} == {"unread"}
    assert "공시를 읽지 못함" in rows[V.KR_NOFILE_SUM_ROW][1] and "결정 공시 없음" not in rows[V.KR_NOFILE_SUM_ROW][1]
    assert log.has("까닭별: 결정 원문을 읽지 못함")


def test_a_normal_run_does_not_warn_and_a_few_lookups_never_do(monkeypatch):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "gh_warning", lambda *a: pytest.fail("no warning expected"))
    monkeypatch.setattr(F, "kr_split_dart", R2.fake_dart(0.3))
    _rows, info = F.kr_splits_fields(None, R2.KR, [], K.FakeDart(), TODAY, seed=R2.SEED, cmap=R2.CMAP)
    assert info["read"]["n"] >= V.KR_SPLIT_READ_MIN and gate(info)[V.KR_READ_ROW][0] == "PASS"
    monkeypatch.setattr(F, "kr_split_dart", unread_dart)
    _rows, info = F.kr_splits_fields(None, R2.KR, [], K.FakeDart(), TODAY, seed=R2.SEED[:V.KR_SPLIT_READ_MIN - 1], cmap=R2.CMAP)
    assert info["read"] == {"n": V.KR_SPLIT_READ_MIN - 1, "no": V.KR_SPLIT_READ_MIN - 1, "doc": V.KR_SPLIT_READ_MIN - 1}
    assert gate(info)[V.KR_READ_ROW][0] == "PASS"
    assert F.kr_splits_carry(None, TODAY)[1]["read"] == {"n": 0, "no": 0, "doc": 0}


@pytest.mark.parametrize("bad, state", [(None, "PASS"), ({"n": "x"}, "WARN"), ("x", "PASS")])
def test_the_read_row_never_fails(bad, state):
    info = {"nofile": [], "runNew": []}
    if bad is not None:
        info["read"] = bad
    rows = gate(info)
    assert rows[V.KR_READ_ROW][0] == state


# ── S2: 마지막 확인 종가로 보인 종목 · 돌아온 종목의 거래정지 병합 ───────────────────────────────────────────────

OLD, NEW = 159224163, 15922416
HALT = [("2025-12-03", 171.0, OLD), ("2025-12-04", 171.0, OLD), ("2025-12-05", 171.0, OLD), ("2025-12-08", 171.0, OLD), ("2025-12-09", 171.0, NEW),
        ("2025-12-10", 1710.0, NEW), ("2025-12-11", 1700.0, NEW)]


def row(shr, pxd=None):
    return [{"t": "123450", "nk": "x", "cls": "kr", "cap": 1.0, "shr": shr, **({"pxd": pxd, "pxc": True} if pxd else {})}]


def steps(days):
    client = K.FakeDart()
    client.meta["corpMap"] = {"123450": "C1"}
    prev = {"pxDate": "2025-12-05", "stocks": row(OLD, "2025-12-04") + [{"t": "000020", "cls": "kr", "shr": 1.0}], "splits": []}
    got = []
    for day, krs in days:
        out = F.kr_splits_step({"splits": [], "splitsFrom": "2016-01-01"}, prev, krs, client, dt.date.fromisoformat(day), [], px_date=day,
                               daum=R2.daum_upto(day, HALT))
        i = out["splitsKr"]
        got.append([x[:2] + x[4:] for x in i["nofile"]])
        prev = {"pxDate": day, "stocks": krs + [{"t": "000020", "cls": "kr", "shr": 1.0}], "splits": out["splits"], "splitsKr": i}
    return got


def test_a_halted_merge_on_a_carried_row_is_found_when_it_trades_again(monkeypatch):
    log = K.Log(monkeypatch)
    got = steps([("2025-12-08", row(OLD, "2025-12-04")), ("2025-12-09", row(OLD, "2025-12-04")), ("2025-12-10", row(NEW)), ("2025-12-11", row(NEW))])
    assert got[:2] == [[], []] and got[2] == got[3] == [["123450", "2025-12-09", "2025-12-10"]]        # 창이 pxd 12-04 에서 시작해 A 를 봐요
    assert log.has("다음 일별 시세로 봤어요")


def test_a_halted_merge_on_a_stock_that_returns_to_the_list_is_found(monkeypatch):
    log = K.Log(monkeypatch)
    got = steps([("2025-12-08", []), ("2025-12-09", []), ("2025-12-10", row(NEW)), ("2025-12-11", row(NEW))])
    assert got[2] == got[3] == [["123450", "2025-12-09", "2025-12-10"]]
    assert log.has("지난 발행본에 없다가 돌아온 국내 종목 1")


# ── S3 · S4: 다시 묻기 ───────────────────────────────────────────────────────────────────────────────────────

def cached_no(client, t, d, code, at):
    client.entries[f"C{t}|krsplit|v2|{d}"] = {"st": "000", "at": at, "d": {"v": "no", "code": code, "note": "x"}}


def test_a_doc_re_ask_waits_for_every_event_never_asked(monkeypatch):
    K.Log(monkeypatch)
    asked = []

    def dart(client, corp, cand, today):
        asked.append(cand["t"])
        client.status["000"] += 2
        return {"v": "no", "code": "nodoc", "note": "x"}, None
    monkeypatch.setattr(F, "kr_split_dart", dart)
    big = R2.split_cand("000010", "2024-03-04")                        # 시가총액이 가장 커서 늘 먼저예요
    rest = [R2.split_cand(f"0001{i}0", f"2025-0{1 + i}-02") for i in range(6)]
    kr = K.kr_rows("000010", cap=9.0) + K.kr_rows(*[c["t"] for c in rest])
    cmap = {c["t"]: f"C{c['t']}" for c in [big] + rest}
    client = K.FakeDart()
    cached_no(client, "000010", "2024-03-04", "unread", "2026-09-01")
    monkeypatch.setattr(F, "KR_SPLIT_DART_PER_RUN", F.KR_SPLIT_ONE_MAX + 4)   # 한 번도 묻지 않은 사건 모두를 물을 한도가 없어요
    _rows, info = F.kr_splits_fields(None, kr, [], client, TODAY, seed=[big] + rest, cmap=cmap)
    assert "000010" not in asked and asked and info["wait"] > 0                  # 다시 묻지 않고 보관본의 판정 (읽지 못함) 을 써요
    assert ["000010", "2024-03-04", 5.0, "unread"] in info["nofile"]
    monkeypatch.setattr(F, "KR_SPLIT_DART_PER_RUN", 10 ** 6)                   # 한도가 남으면 맨 뒤에서 다시 물어요
    asked.clear()
    _rows, info = F.kr_splits_fields(None, kr, [], client, TODAY, seed=[big] + rest, cmap=cmap)
    assert asked[-1] == "000010" and info["wait"] == 0 and ["000010", "2024-03-04", 5.0, "nodoc"] in info["nofile"]


@pytest.mark.parametrize("how", ["down", "fails"])
def test_a_re_ask_that_cannot_be_made_keeps_the_cached_verdict_and_its_record(monkeypatch, how):
    log = K.Log(monkeypatch)
    old = R2.split_cand("000010", "2022-03-04")                        # 3년 40일보다 오래된 사건 (지난 기록으로는 이어지지 않아요)
    recent = R2.split_cand("000020", "2026-09-01")                     # 14일마다 다시 묻는 최근 사건
    client = K.FakeDart()
    cached_no(client, "000010", "2022-03-04", "unread", "2026-09-01")
    cached_no(client, "000020", "2026-09-01", "nodoc", "2026-10-01")
    if how == "down":
        client.down = "ConnectionError"
    else:
        monkeypatch.setattr(F, "kr_split_dart", lambda client, corp, cand, today: (None, ("net", "x")))
    prev = {"splits": [], "splitsKr": {"nofile": [["000010", "2022-03-04", 5.0, "unread"], ["000020", "2026-09-01", 5.0, "nodoc"]]}}
    _rows, info = F.kr_splits_fields(prev, K.kr_rows("000010", "000020"), [], client, TODAY, seed=[old, recent],
                                     cmap={"000010": "C000010", "000020": "C000020"})
    assert sorted(x[:4] for x in info["nofile"]) == [["000010", "2022-03-04", 5.0, "unread"], ["000020", "2026-09-01", 5.0, "nodoc"]]
    assert info["runNew"] == [] and info["fail"] == [] and info["wait"] == 0
    if how == "fails":
        assert log.has("다시 물으려던 판정 2건을 묻지 못해 보관본의 판정을 그대로 썼어요")


def test_run_new_counts_only_events_with_no_earlier_verdict(monkeypatch):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "kr_split_dart", R2.fake_dart(1.0))
    client = K.FakeDart()
    old = R2.split_cand("000010", "2022-03-04")
    cached_no(client, "000010", "2022-03-04", "unread", "2026-09-01")          # 다시 물을 때가 된 오래된 사건 · 직전 발행본에는 없어요
    fresh = R2.split_cand("000020", "2026-09-01")
    _rows, info = F.kr_splits_fields({"splits": [], "splitsKr": {"nofile": []}}, K.kr_rows("000010", "000020"), [], client, TODAY, seed=[old, fresh],
                                     cmap={"000010": "C000010", "000020": "C000020"})
    assert sorted(x[:2] for x in info["nofile"]) == [["000010", "2022-03-04"], ["000020", "2026-09-01"]]
    assert info["runNew"] == [["000020", "2026-09-01"]] and info["read"]["n"] == 2                  # 다시 물은 것은 새로 물은 판정이지만 새 줄은 아니에요


# ── 그 밖 ────────────────────────────────────────────────────────────────────────────────────────────────

def test_nocorp_counts_once_even_when_runs_do_not_publish(monkeypatch):
    K.Log(monkeypatch)
    cands = [R2.split_cand(f"0002{i}0", f"2026-0{1 + i}-02") for i in range(5)]
    client = K.FakeDart()
    before = {"splits": [], "splitsKr": {"nofile": [], "runNew": []}}
    news = []
    for i in range(3):                                                      # 발행하지 못한 실행들 (직전 발행본 그대로) · 보관본은 이어져요
        _rows, info = F.kr_splits_fields(before, K.kr_rows(*[c["t"] for c in cands]), [], client, TODAY + dt.timedelta(days=i), seed=cands,
                                         cmap={"999990": "C9"})
        news.append(len(info["runNew"]))
        assert info["nofileN"] == 5
    assert news == [5, 0, 0]


def test_the_inner_error_path_keeps_this_run_s_daum_queue(monkeypatch):
    K.Log(monkeypatch)
    monkeypatch.setattr(F, "_kr_splits_fields", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    prev = {"splits": [], "splitsKr": {"nofile": [], "dq": [["000030", "2026-11-01"]]}}
    _rows, info = F.kr_splits_fields(prev, K.kr_rows("000010"), [], K.FakeDart(), TODAY, dq=[["000010", "2026-11-20"]])
    assert info["src"] == "err" and info["dq"] == [["000010", "2026-11-20"], ["000030", "2026-11-01"]] and info["runNew"] == []
