# -*- coding: utf-8 -*-
"""S&P 500 목록을 읽지 못한 날 (2026-11-28 · run 46026291142: 위키백과가 FinanceDataReader 의 'List of S&P 500 companies' 요청을 429 로 거절해
미국 목록이 465개 → 관문이 미국 종목 수 458 · 800 → 458 로 막음) — fetch_data.py us_sp500_odd · us_sp500_prev · us_tickers (한 번 다시 읽기 ·
지난 발행본의 목록 이어 쓰기) · us_list_sym (spCarried) · fetch_us 와 validate_data.py check_us_sp_carry (새 줄 · 경고만). 네트워크 없음 · 더하기만.

규칙: ① 읽기가 멈추거나 믿을 수 없는 목록이면 잠깐 쉬고 같은 요청으로 한 번만 다시 ② 그래도 안 되면 지난 발행본의 usListSym.spTickers 를 오늘의
S&P 500 부분으로 (크게 남기고 usListSym.spCarried = {from 처음 읽은 날, why 까닭}) ③ 이어 쓴 목록을 다시 이어 써도 처음 읽은 날은 그대로
④ 처음 읽은 날부터 7일(달력 · KST)이 넘은 목록은 쓰지 않아요 (예전 그대로 → 관문의 미국 종목 수가 막아요). 위키백과의 정책을 지켜요: User-Agent 를
바꾸지 않고 다른 길로 돌아가지 않아요 (이 시험의 가짜 목록은 같은 이름으로 두 번 불렸는지만 봐요)."""
import copy
import datetime as dt
import json
import os
import sys
import types

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402

ROW = V.US_SP_CARRY_ROW
SHARE1 = f"주식 종류 티커로 들어온 미국 종목 ({', '.join(sorted(V.US_CLASS_SET))}): 목록에 있거나 빠진 이유"
SHARE2 = "미국 목록 출처 티커 (주식 종류 · 점이 지워진 꼴)"
TODAY = dt.date(2026, 11, 28)                     # 실행한 날 (KST)
US_DAY = dt.date(2026, 11, 27)                    # 미국 기준일 (가짜 S&P 500 마지막 봉)
PUB_1127 = "2026-11-27T06:41:04+09:00"            # 지난 발행본 (11-27 아침 발행 · 그날 읽은 목록)
WIKI_429 = ("429 Client Error: We suspect this request is automated: if so, please respect our robot policy. If you think you were "
            "incorrectly blocked, please contact noc@wikimedia.org reporting this message (01f0bde) for url: "
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")


class HTTPError(Exception):
    pass


WHY_2X429 = f"1차: HTTPError: {WIKI_429}"[:284] + " · 2차: 1차와 같음"     # 두 번 다 같은 429 (리뷰 #199: 두 번의 까닭을 함께)


# ── 가짜 목록 (영문 4글자 티커 · 우선주 꼴(다섯째 글자 M·N·O·P)이 아니에요) ──────────────────────────
def _letters(head, n, avoid):
    out, ab = [], "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for a in ab:
        for b in ab:
            for c in ab:
                t = head + a + b + c
                if t not in avoid:
                    out.append(t)
                if len(out) == n:
                    return out
    return out


AVOID = set(F.EXTRA_US) | set(F.US_ETFS) | set(F.US_CLASS_JOINED) | {y for y, _k in F.US_CLASS_JOINED.values()}


def sp_rows(n_plain):
    """S&P 500 목록 행 (FinanceDataReader 모양: 점이 지워진 BRKB · BFB 와 이름)."""
    return [(t, f"{t} Corp") for t in _letters("S", n_plain, AVOID)] + [("BRKB", "Berkshire Hathaway"), ("BFB", "Brown–Forman")]


def sp_yahoo(rows):
    return sorted(F.US_CLASS_JOINED[k][0] if k in F.US_CLASS_JOINED else k for k, _n in rows)


def listing(rows, nasdaq=False):
    cols = {"Symbol": [r[0] for r in rows], "Name": [r[1] for r in rows]}
    cols.update({"IndustryCode": "0", "Industry": "x"} if nasdaq else {"Sector": "x", "Industry": "x"})
    return pd.DataFrame(cols)


class FakeFDR:
    """S&P500 은 차례대로 sp (예외 또는 표) 를 돌려줘요 (다 쓰면 마지막 것). 부른 이름과 인자를 적어요."""

    def __init__(self, sp, nq):
        self.sp, self.nq, self.calls = list(sp), nq, []

    def StockListing(self, *a, **kw):
        self.calls.append((a, kw))
        if a[0] == "NASDAQ":
            return self.nq
        x = self.sp.pop(0) if len(self.sp) > 1 else self.sp[0]
        if isinstance(x, BaseException):
            raise x
        return x


def sp_calls(fdr):
    return [c for c in fdr.calls if c[0][0] == "S&P500"]


def prev_of(sp_list, us_list, published=PUB_1127, carried=None):
    """지난 발행본 data.json (필요한 칸만): 미국 종목 행 · usListSym (그날의 S&P 500 티커 · 야후 모양)."""
    u = {"read": True, "mapped": [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]], "unmapped": [], "spTickers": sorted(sp_list),
         "spGone": {}, "noPx": [], "spErr": [], "missing": {}}
    if carried is not None:
        u["spCarried"] = carried
    return {"publishedAt": published, "pxDate": "2026-11-26", "usPxDate": "2026-11-26",
            "stocks": [{"t": t, "nk": t + " Inc.", "cls": "us", "ccy": "USD", "price": 50.0, "d1": 0.3} for t in sorted(us_list)],
            "usListSym": u}


# ── 1. 순수 함수 ────────────────────────────────────────────────────────────────
def test_the_pipeline_and_gate_agree_on_the_limits():
    assert F.US_SP500_CARRY_DAYS == V.US_SP_CARRY_DAYS == 7
    assert F.US_SP500_TRIES == 2                                   # 한 번 + 다시 한 번만
    assert 0 < F.US_SP500_RETRY_PAUSE_S <= 10                      # 잠깐 (몇 초)
    assert F.US_SP500_MIN is V.US_SP500_MIN and F.US_SP500_MAX is V.US_SP500_MAX   # 예전 기준 그대로 (겹침 400 이상 · 목록 550 이하)


def test_us_sp500_odd_uses_the_same_two_numbers():
    sp = sp_yahoo(sp_rows(501))
    ref = set(sp) | {"QAAA", "QAAB"}
    assert F.us_sp500_odd(sp, ref) is None and F.us_sp500_odd(sp) is None
    assert F.us_sp500_odd(sp[:399], ref) == "목록 399곳 · 지난 발행본의 미국 목록과 겹침 399곳 (400곳 이상이어야 해요)"
    assert F.us_sp500_odd(sp[:400], ref) is None                                             # 정확히 400 은 믿어요 (fetch_us 와 같아요)
    assert F.us_sp500_odd(sp, {"QAAA"}).startswith("목록 503곳 · 지난 발행본의 미국 목록과 겹침 0곳")
    big = sp + _letters("Z", 60, AVOID)
    assert F.us_sp500_odd(big, ref) == "목록 563곳 (550곳 이하여야 해요)" and F.us_sp500_odd(big) == "목록 563곳 (550곳 이하여야 해요)"
    assert F.us_sp500_odd([]) == "티커가 하나도 없음" and F.us_sp500_odd(None) == "목록이 아님" and F.us_sp500_odd({"a": 1}) == "목록이 아님"
    assert F.us_sp500_odd(sp[:-1] + ["Apple Inc."], ref).startswith("야후 모양이 아닌 티커 1개 (Apple Inc.)")
    assert F.us_sp500_odd(sp[:-1] + [None]).startswith("야후 모양이 아닌 티커 1개")
    assert F.us_sp500_odd(sp[:10]) is None                         # 지난 발행본이 없으면 (첫 실행) 빈 · 너무 큰 목록만 걸러요


def test_us_sp500_prev_takes_the_read_day_from_the_publish_and_the_age_limit():
    sp = sp_yahoo(sp_rows(501))
    us = set(sp) | set(_letters("Q", 270, AVOID))
    c = F.us_sp500_prev(prev_of(sp, us), TODAY)
    assert c == {"tickers": sp, "from": "2026-11-27", "age": 1, "ref": frozenset(us)}
    # 그날 늦게 UTC 로 적힌 시각도 한국 날짜로 (2026-11-26T22:00Z = 11-27 07:00 KST)
    assert F.us_sp500_prev(prev_of(sp, us, published="2026-11-26T22:00:00Z"), TODAY)["from"] == "2026-11-27"
    assert F.us_sp500_prev(prev_of(sp, us, published="2026-11-27T06:41:04"), TODAY)["from"] == "2026-11-27"   # 시간대 없음 = 한국 시각
    # 7일까지는 써요 · 8일은 쓰지 않아요 (달력 날 · KST)
    assert F.us_sp500_prev(prev_of(sp, us, published="2026-11-21T06:40:00+09:00"), TODAY)["age"] == 7
    old = F.us_sp500_prev(prev_of(sp, us, published="2026-11-20T23:59:00+09:00"), TODAY)
    assert "tickers" not in old and old["why"] == "2026-11-20 에 읽은 목록이라 8일 지남 (7일까지만 이어 써요)" and old["ref"] == frozenset(us)
    fut = F.us_sp500_prev(prev_of(sp, us, published="2026-11-29T06:40:00+09:00"), TODAY)
    assert "tickers" not in fut and "보다 뒤" in fut["why"]
    for bad in (None, "", "어제", "2026-13-40T00:00:00+09:00", 20261127):
        w = F.us_sp500_prev(prev_of(sp, us, published=bad), TODAY)
        assert "tickers" not in w and "publishedAt" in w["why"], bad


def test_a_carried_list_keeps_its_first_read_day():
    """이어 쓴 목록을 다시 이어 쓰면 처음 읽은 날(spCarried.from)이 그대로예요 — 발행 시각으로 다시 세지 않아요."""
    sp = sp_yahoo(sp_rows(501))
    us = set(sp) | set(_letters("Q", 270, AVOID))
    p = prev_of(sp, us, published="2026-11-28T06:41:00+09:00", carried={"from": "2026-11-23", "why": "HTTPError: 429"})
    c = F.us_sp500_prev(p, dt.date(2026, 11, 29))
    assert c["from"] == "2026-11-23" and c["age"] == 6 and c["tickers"] == sp
    assert F.us_sp500_prev(p, dt.date(2026, 11, 30))["age"] == 7
    w = F.us_sp500_prev(p, dt.date(2026, 12, 1))                                     # 발행은 11-28 이어도 목록은 11-23 것 → 8일
    assert "tickers" not in w and w["why"].startswith("2026-11-23 에 읽은 목록이라 8일 지남")
    # spCarried 가 있는데 날짜를 읽을 수 없으면 쓰지 않아요 (발행 시각으로 날을 새로 세면 이어 쓰기가 끝없이 이어져요)
    for bad in ({"from": None}, {"from": "11-23"}, {"from": "2026-02-30"}, {}, "2026-11-23", None, ["2026-11-23"]):
        p2 = copy.deepcopy(p)
        p2["usListSym"]["spCarried"] = bad
        w = F.us_sp500_prev(p2, dt.date(2026, 11, 29))
        assert "tickers" not in w and "spCarried.from" in w["why"], bad


@pytest.mark.parametrize("change, why", [
    (lambda p: p.pop("usListSym"), "지난 발행본에 usListSym 기록이 없음"),
    (lambda p: p.update(usListSym="x"), "지난 발행본에 usListSym 기록이 없음"),
    (lambda p: p["usListSym"].update(spTickers=None), "지난 발행본도 S&P 500 목록이 없음 (spTickers 빈 값)"),
    (lambda p: p["usListSym"].pop("spTickers"), "지난 발행본도 S&P 500 목록이 없음 (spTickers 빈 값)"),
    (lambda p: p["usListSym"].update(spTickers="AAPL"), "지난 발행본의 목록을 믿을 수 없음 (목록이 아님)"),
    (lambda p: p["usListSym"].update(spTickers=p["usListSym"]["spTickers"][:50]), "지난 발행본의 목록을 믿을 수 없음 (목록 50곳 · 지난 발행본의 미국 목록과 겹침 50곳"),
    (lambda p: p["usListSym"].update(spTickers=[f"{s} Corp" for s in p["usListSym"]["spTickers"]]), "지난 발행본의 목록을 믿을 수 없음 (야후 모양이 아닌 티커 503개"),
    (lambda p: p["usListSym"].update(spTickers=p["usListSym"]["spTickers"] + _letters("Z", 60, AVOID)), "지난 발행본의 목록을 믿을 수 없음 (목록 563곳 (550곳 이하여야 해요))"),
    (lambda p: p["usListSym"].update(spTickers=p["usListSym"]["spTickers"] + p["usListSym"]["spTickers"][:3]), "지난 발행본의 목록을 믿을 수 없음 (같은 티커가 두 번 넘게 있음)"),
    (lambda p: p.update(stocks=[s for s in p["stocks"] if s["t"].startswith("Q")]), "지난 발행본의 목록을 믿을 수 없음 (목록 503곳 · 지난 발행본의 미국 목록과 겹침 0곳"),
    (lambda p: p.update(stocks=[]), "지난 발행본에 미국 종목이 없어 목록을 맞춰 볼 수 없음"),
])
def test_a_missing_or_implausible_last_list_is_not_carried(change, why):
    sp = sp_yahoo(sp_rows(501))
    p = prev_of(sp, set(sp) | set(_letters("Q", 270, AVOID)))
    change(p)
    w = F.us_sp500_prev(p, TODAY)
    assert "tickers" not in w and w["why"].startswith(why), w["why"]
    assert F.us_sp500_prev(None, TODAY) == {"why": "지난 발행본을 읽지 못함", "ref": None}


def test_a_crash_while_looking_at_the_last_list_does_not_stop_the_run(monkeypatch):
    monkeypatch.setattr(F, "us_sp500_odd", lambda *a, **k: 1 / 0)
    sp = sp_yahoo(sp_rows(501))
    w = F.us_sp500_prev_safe(prev_of(sp, set(sp)), TODAY)
    assert w == {"why": "지난 발행본의 목록을 보다가 멈춤 (ZeroDivisionError: division by zero)", "ref": None}


# ── 2. us_tickers: 한 번 다시 읽기 · 이어 쓰기 ────────────────────────────────────
NQ_ONLY = 270


def _tickers(monkeypatch, sp_seq, prev=..., today=TODAY, n_plain=501):
    rows = sp_rows(n_plain)
    sp = sp_yahoo(rows)
    nq_rows = [(t, f"{t} Corp") for t in sp[:130] if "-" not in t] + [(t, f"{t} Inc") for t in _letters("Q", NQ_ONLY, AVOID)]
    fdr = FakeFDR([listing(rows) if isinstance(x, str) and x == "ok" else x for x in sp_seq], listing(nq_rows[:400], nasdaq=True))
    monkeypatch.setitem(sys.modules, "FinanceDataReader", fdr)
    slept, lines = [], []
    monkeypatch.setattr(F.time, "sleep", slept.append)
    monkeypatch.setattr(F, "log", lines.append)
    if prev is ...:
        prev = prev_of(sp, set(sp) | {t for t, _n in nq_rows} | set(F.EXTRA_US))
    names = F.UsListNames()
    names.carry = F.us_sp500_prev_safe(prev, today)
    syms = F.us_tickers(names)
    return syms, names, fdr, slept, lines, sp


def test_a_good_read_is_used_as_before_and_nothing_is_carried(monkeypatch):
    syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, ["ok"])
    assert names.sp500 == frozenset(sp) and names.spCarried is None and slept == [] and len(sp_calls(fdr)) == 1
    assert names.sym["mapped"] == [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]] and names.sym["unmapped"] == []
    assert names["SAAA"] == "SAAA Corp" and names["BF-B"] == "Brown–Forman"
    assert not any("이어 써" in x or "다시 읽" in x for x in lines), lines
    # 지난 발행본이 없어도 같아요 (이어 쓸 목록이 있는지는 결과를 바꾸지 않아요)
    syms2, names2, *_r = _tickers(monkeypatch, ["ok"], prev=None)
    assert syms2 == syms and names2.sp500 == names.sp500 and names2.sym == names.sym and dict(names2) == dict(names)


def test_two_failed_reads_carry_the_last_list_loudly(monkeypatch):
    err = HTTPError(WIKI_429)
    syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, [err, err])
    assert len(sp_calls(fdr)) == 2 and slept == [F.US_SP500_RETRY_PAUSE_S]           # 한 번만 다시 · 잠깐 쉬고
    assert all(c == (("S&P500",), {}) for c in sp_calls(fdr))                          # 같은 요청 그대로 (다른 인자 · 다른 길 없음)
    assert names.sp500 == frozenset(sp) and set(sp) <= set(syms) and "BF-B" in syms and "BRK-B" in syms
    assert names.spCarried == {"from": "2026-11-27", "why": WHY_2X429}
    assert sum("S&P500 목록 실패: 429 Client Error" in x for x in lines) == 2           # 예전 줄 그대로 (두 번)
    loud = [x for x in lines if x.startswith("  !! S&P 500 목록을 읽지 못해 (1차: HTTPError: 429 Client Error")]
    assert len(loud) == 1 and "지난 발행본의 목록(2026-11-27 읽음 · 503종목 · 1일 전)을 썼어요" in loud[0], lines
    assert "data.json usListSym.spCarried · 관문 경고" in loud[0] and "· 2차: 1차와 같음)" in loud[0]
    assert any(x.startswith("  !! S&P 500 목록을 읽지 못했어요 (HTTPError: 429") and "초 쉬고 같은 요청으로 한 번만 다시 읽어요" in x for x in lines)
    assert names.sym["mapped"] == []                                                  # 오늘 S&P 목록에서 바꾼 티커는 없어요 (이어 쓴 티커는 이미 야후 모양)
    assert len(syms) == len(set(syms))                                                # 겹치지 않게 한 번씩


def test_a_failed_read_then_a_good_retry_is_not_a_carry(monkeypatch):
    syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, [HTTPError(WIKI_429), "ok"])
    assert len(sp_calls(fdr)) == 2 and slept == [F.US_SP500_RETRY_PAUSE_S]
    assert names.sp500 == frozenset(sp) and names.spCarried is None
    assert names.sym["mapped"] == [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]]   # 다시 읽은 목록의 기록 (두 번 적지 않아요)
    assert any(x.startswith("· S&P 500 목록을 다시 읽어 받았어요 (503곳)") for x in lines)
    assert not any("지난 발행본의 목록(" in x for x in lines)


def test_an_implausible_list_is_read_again_then_carried(monkeypatch):
    """목록 칸 이름이 바뀌어 티커 대신 회사 이름이 온 날 (us_symbol 이 거의 다 바꾸지 못해요) — 믿을 수 없는 목록이라 다시 읽고, 그래도 같으면
    이어 써요. 그 목록의 티커는 쓰지 않아요."""
    names_only = pd.DataFrame({"Security": ["Apple Inc.", "Visa", "Linde plc"] * 5})   # 'Symbol' 칸이 없어 첫 칸(회사 이름)을 읽어요
    syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, [names_only, names_only])
    assert len(sp_calls(fdr)) == 2 and slept == [F.US_SP500_RETRY_PAUSE_S]
    one = ("받은 목록 15행 · 쓸 수 있는 티커 1곳 · 야후 모양으로 바꾸지 못한 행 10 (앞: 'APPLE INC.', 'LINDE PLC', 'APPLE INC.') — "
           "목록 1곳 · 지난 발행본의 미국 목록과 겹침 0곳 (400곳 이상이어야 해요)")
    assert names.spCarried == {"from": "2026-11-27", "why": f"1차: {one} · 2차: 1차와 같음"}          # 리뷰 #199 Fable S1: 받은 행 · 바꾸지 못한 행 · 앞 값
    assert "VISA" not in syms and names.sp500 == frozenset(sp)
    loud = [x for x in lines if x.startswith("  !! S&P 500 목록을 읽었지만 쓸 수 없어 (1차: 받은 목록 15행")]
    assert len(loud) == 1 and "오늘 받은 목록 1곳은 쓰지 않았어요" in loud[0] and "지난 발행본의 목록(2026-11-27 읽음" in loud[0], lines
    assert any(x.startswith("  !! S&P 500 목록을 읽었지만 쓸 수 없어요 (받은 목록 15행") and "5초 쉬고" in x for x in lines)
    assert names.sym["unmapped"] == []                  # 쓰지 않은 목록의 행은 기록(unmapped)에 넣지 않고 · 까닭(why)과 로그에 수와 앞 값을 남겨요


def test_an_old_list_is_not_carried_and_the_run_behaves_as_before(monkeypatch):
    err = HTTPError(WIKI_429)
    for prev_pub, why in (("2026-11-20T06:40:00+09:00", "2026-11-20 에 읽은 목록이라 8일 지남 (7일까지만 이어 써요)"),
                          (None, "지난 발행본을 읽지 못함")):
        if prev_pub is None:
            syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, [err, err], prev=None)
        else:
            rows = sp_rows(501)
            prev = prev_of(sp_yahoo(rows), set(sp_yahoo(rows)) | set(_letters("Q", NQ_ONLY, AVOID)), published=prev_pub)
            syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, [err, err], prev=prev)
        assert names.sp500 is None and names.spCarried is None and "BF-B" not in syms and not set(sp) - {"BRK-B"} <= set(syms)
        assert len(sp_calls(fdr)) == 2 and slept == [F.US_SP500_RETRY_PAUSE_S]        # 다시 읽기는 이어 쓸 목록과 상관없이 해요
        loud = [x for x in lines if x.startswith("  !! S&P 500 목록을 다시 읽어도 읽지 못해 (1차: HTTPError: 429")]
        assert len(loud) == 1 and f"지난 발행본의 목록도 이어 쓸 수 없어요 ({why})" in loud[0] and "S&P 500 이 빠져요" in loud[0], lines


def test_without_a_carry_an_untrusted_list_is_used_as_before(monkeypatch):
    """이어 쓸 목록이 없을 때 (8일 지남) 믿을 수 없는 목록이 왔다면 예전처럼 그것을 써요 — 가격을 받은 뒤 fetch_us 의 겹침 검사가 믿지 않아요. 다시
    읽기가 멈춰도 먼저 받은 목록은 그대로예요."""
    rows = sp_rows(501)
    small = listing(rows[:30])
    prev = prev_of(sp_yahoo(rows), set(sp_yahoo(rows)) | set(_letters("Q", NQ_ONLY, AVOID)), published="2026-11-20T06:40:00+09:00")
    for seq in ([small, small], [small, HTTPError(WIKI_429)]):
        syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, seq, prev=prev)
        assert names.sp500 == frozenset(sp_yahoo(rows[:30])) and names.spCarried is None and set(names.sp500) <= set(syms)
        assert len(sp_calls(fdr)) == 2 and slept == [F.US_SP500_RETRY_PAUSE_S]
        head = "읽었지만 쓸 수 없어" if isinstance(seq[1], pd.DataFrame) else "한 번은 읽지 못하고 한 번은 읽었지만 쓸 수 없어"
        loud = [x for x in lines if x.startswith(f"  !! S&P 500 목록을 다시 읽어도 {head} (1차: 받은 목록 30행 · 쓸 수 있는 티커 30곳 · "
                                                 "야후 모양으로 바꾸지 못한 행 0 — 목록 30곳 · 지난 발행본의 미국 목록과 겹침 30곳")]
        assert len(loud) == 1 and "받은 목록 30곳을 예전처럼 그대로 써요" in loud[0], lines


def test_the_old_calling_shapes_still_retry_without_a_carry(monkeypatch):
    """dict 나 아무것도 넘기지 않아도 (예전 부르는 모양) 다시 읽기는 해요 · 이어 쓸 목록이 없어 예전 그대로."""
    rows = sp_rows(501)
    fdr = FakeFDR([HTTPError(WIKI_429), listing(rows)], listing([("QAAA", "Q Inc")], nasdaq=True))
    monkeypatch.setitem(sys.modules, "FinanceDataReader", fdr)
    slept = []
    monkeypatch.setattr(F.time, "sleep", slept.append)
    monkeypatch.setattr(F, "log", lambda *a: None)
    plain = {}
    syms = F.us_tickers(plain)
    assert "BF-B" in syms and plain["BF-B"] == "Brown–Forman" and slept == [F.US_SP500_RETRY_PAUSE_S] and not hasattr(plain, "spCarried")


# ── 3. fetch_us 를 가짜 야후로 (작은 목록 · 겹침 기준을 작게) ─────────────────────────
def _fake_yf(series):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"] if tickers != F.FX_TICKER else series["_spx"] * 0 + 1450.0})
        cols = {}
        for t in tickers:
            if t not in series:
                continue
            cols[(t, "Close")] = series[t]
            cols[(t, "Dividends")] = pd.Series(0.0, index=series[t].index)
            cols[(t, "Stock Splits")] = pd.Series(0.0, index=series[t].index)
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            return {"shortName": f"{self.t} Inc.", "longName": f"{self.t} Inc.", "quoteType": "EQUITY", "sector": "Technology",
                    "industry": "Software - Application", "financialCurrency": "USD", "currency": "USD", "country": "United States",
                    "marketCap": 5e10, "averageVolume": 1e6, "trailingPE": 20.0, "priceToBook": 3.0, "returnOnEquity": 0.15,
                    "longBusinessSummary": f"{self.t} makes things."}
    return types.SimpleNamespace(download=download, Ticker=Ticker)


def _fetch(tmp_path, monkeypatch, sp_seq, prev, today=TODAY, n_plain=501, n_nq=NQ_ONLY, sp_min=None, tag="a"):
    rows = sp_rows(n_plain)
    sp = sp_yahoo(rows)
    nq_rows = [(t, f"{t} Corp") for t in sp[:130] if "-" not in t] + [(t, f"{t} Inc") for t in _letters("Q", n_nq, AVOID)]
    days = pd.bdate_range(US_DAY - dt.timedelta(days=130), US_DAY)
    rnd = np.random.default_rng(3)
    series = {"_spx": pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))) * 6800, index=days)}
    for t in set(sp) | {t for t, _n in nq_rows} | set(F.EXTRA_US):
        series[t] = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))) * 100, index=days)
    fdr = FakeFDR([listing(rows) if isinstance(x, str) and x == "ok" else x for x in sp_seq], listing(nq_rows[:400], nasdaq=True))
    monkeypatch.setitem(sys.modules, "FinanceDataReader", fdr)
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: US_DAY)
    slept, lines = [], []
    monkeypatch.setattr(F.time, "sleep", slept.append)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / f"us-info-{tag}.json.gz"))
    if sp_min is not None:
        monkeypatch.setattr(F, "US_SP500_MIN", sp_min)
        monkeypatch.setattr(V, "US_SP500_MIN", sp_min)
    monkeypatch.setattr(F, "log", lines.append)
    out, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev=copy.deepcopy(prev))
    meta.pop("_index")
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(out, allow_nan=False, ensure_ascii=False)
    return out, meta, lines, sp, fdr


SMALL = {"n_plain": 21, "n_nq": 20, "sp_min": 5}       # 작은 가짜 목록 (S&P 23 · 나스닥 41) — 겹침 기준을 작게 (실제 400)


def gate_rows(meta, out, mode="publish", published="2026-11-28T00:35:00+09:00"):
    rep = V.Report()
    data = {"usListSym": meta["usListSym"], "publishedAt": published, "stocks": out}
    V.check_us_share_class(rep, data, out, mode)
    V.check_us_sp_carry(rep, data)
    return {r[0]: r for r in rep.rows}


def _prev_from(out, meta, published):
    """이번 실행의 결과를 다음 실행의 '지난 발행본' 으로 (발행 파일이 쓰는 칸만)."""
    sweep = {"usListSym": copy.deepcopy(meta["usListSym"])}
    F.pub_sweep(sweep, "시험")                                                     # 발행 앞 청소를 지나도 그대로예요
    return {"publishedAt": published, "usPxDate": US_DAY.isoformat(), "pxDate": "2026-11-27", "stocks": copy.deepcopy(out),
            "usListSym": sweep["usListSym"]}


def test_fetch_us_on_a_carry_day_records_it_and_the_gate_warns_with_the_date(tmp_path, monkeypatch):
    err = HTTPError(WIKI_429)
    good_out, good_meta, _l, sp, _f = _fetch(tmp_path, monkeypatch, ["ok"], None, tag="g")
    prev = _prev_from(good_out, good_meta, PUB_1127)
    out, meta, lines, sp, fdr = _fetch(tmp_path, monkeypatch, [err, err], prev, tag="c")
    u = meta["usListSym"]
    assert u["spCarried"] == {"from": "2026-11-27", "why": WHY_2X429}
    assert u["spTickers"] == sp and u["read"] is True and u["mapped"] == [] and u["missing"] == {}
    assert {k: v for k, v in u.items() if k not in ("spCarried", "mapped")} == {k: v for k, v in good_meta["usListSym"].items() if k != "mapped"}
    assert meta["usForeign"]["sp500"] == good_meta["usForeign"]["sp500"] and meta["usForeign"]["sp500"]["ok"] is True
    assert sorted(r["t"] for r in out) == sorted(r["t"] for r in good_out)          # 같은 미국 목록이 나가요
    assert any(x.startswith("· S&P 500 목록 503곳 · 오늘 미국 목록과 겹침") and x.endswith("지난 발행본에서 이어 쓴 2026-11-27 목록이에요")
               for x in lines), [x for x in lines if "S&P 500 목록" in x]
    # 발행 앞 청소(pub_sweep)를 지나도 기록 그대로 · 관문의 낱말 줄이 찾는 낱말 없음
    doc = {"usListSym": copy.deepcopy(u)}
    F.pub_sweep(doc, "시험")
    assert doc["usListSym"] == u and doc["ownDrop"]["sweep"]["n"] == 0
    rows = gate_rows(meta, out)
    assert rows[ROW][3] == "WARN" and rows[ROW][1].startswith("지난 발행본의 S&P 500 목록을 이어 씀: 2026-11-27 읽음 (발행일 2026-11-28 까지 1일) · 503종목")
    assert "오늘의 목록을 쓰지 못한 까닭: 1차: HTTPError: 429 Client Error" in rows[ROW][1]
    assert rows[SHARE1][3] == "PASS" and rows[SHARE2][3] == "PASS"                    # 다른 줄은 보통 날처럼
    assert gate_rows(meta, out, "live")[ROW][3] == "WARN"
    # 보통 날의 기록에는 칸이 없어요 · 관문 줄은 통과
    assert "spCarried" not in good_meta["usListSym"]
    g = gate_rows(good_meta, good_out)
    assert g[ROW][1:] == ("이어 쓰지 않음 (그날 읽은 목록)", V.US_SP_CARRY_RULE, "PASS")


def test_fetch_us_with_a_good_read_is_unchanged_by_the_last_publish(tmp_path, monkeypatch):
    """읽기가 되면 지난 발행본이 있든 없든 결과가 같아요 (이어 쓴 기록 없음 · 다시 읽지 않음)."""
    a_out, a_meta, a_lines, _sp, a_fdr = _fetch(tmp_path, monkeypatch, ["ok"], None, tag="n1", **SMALL)
    prev = _prev_from(a_out, a_meta, PUB_1127)
    b_out, b_meta, b_lines, _sp, b_fdr = _fetch(tmp_path, monkeypatch, ["ok"], prev, tag="n2", **SMALL)
    assert b_meta["usListSym"] == a_meta["usListSym"] and "spCarried" not in b_meta["usListSym"]
    assert sorted(r["t"] for r in b_out) == sorted(r["t"] for r in a_out)
    assert len(sp_calls(a_fdr)) == len(sp_calls(b_fdr)) == 1


def test_a_chained_carry_keeps_the_first_read_day_and_stops_after_7_days(tmp_path, monkeypatch):
    err = HTTPError(WIKI_429)
    out0, meta0, *_r = _fetch(tmp_path, monkeypatch, ["ok"], None, tag="d0", **SMALL)
    prev = _prev_from(out0, meta0, PUB_1127)                                        # 11-27 에 읽은 목록
    froms = []
    for i, day in enumerate([dt.date(2026, 11, 28) + dt.timedelta(days=k) for k in range(7)]):
        out, meta, lines, sp, _f = _fetch(tmp_path, monkeypatch, [err, err], prev, today=day, tag=f"d{i + 1}", **SMALL)
        froms.append(meta["usListSym"].get("spCarried", {}).get("from"))
        prev = _prev_from(out, meta, f"{day.isoformat()}T06:41:00+09:00")
    assert froms == ["2026-11-27"] * 7                                              # 11-28 ~ 12-04: 처음 읽은 날 그대로 (1 ~ 7일)
    out, meta, lines, sp, _f = _fetch(tmp_path, monkeypatch, [err, err], prev, today=dt.date(2026, 12, 5), tag="d8", **SMALL)
    u = meta["usListSym"]
    assert "spCarried" not in u and u["spTickers"] is None and "BF-B" not in {r["t"] for r in out}
    assert u["missing"] == {"BF-B": "S&P 500 목록을 읽지 못해 요청하지 않음"}       # 예전 그대로
    assert any("2026-11-27 에 읽은 목록이라 8일 지남 (7일까지만 이어 써요)" in x for x in lines)
    assert gate_rows(meta, out)[ROW][1:] == ("이어 쓰지 않음 (그날 S&P 500 목록 없음 — 미국 종목 수 줄들이 봐요)", V.US_SP_CARRY_RULE, "PASS")


def test_a_missing_bf_b_on_a_carry_day_names_the_carried_list():
    u = F.us_list_sym({"mapped": [], "unmapped": []}, frozenset({"AAPL"}), True, {"AAPL"}, {"AAPL"}, {},
                      carried={"from": "2026-11-27", "why": "HTTPError: 429"})
    assert u["missing"]["BF-B"] == "이어 쓴 S&P 500 목록(2026-11-27 읽음)에 없음 (지수에서 빠졌는지 확인)"
    assert u["spCarried"] == {"from": "2026-11-27", "why": "HTTPError: 429"}
    assert "spCarried" not in F.us_list_sym({"mapped": [], "unmapped": []}, None, False, set(), set(), {}, carried={"from": "2026-11-27", "why": "x"})


def test_a_carried_list_that_fails_the_priced_overlap_is_recorded_and_not_trusted(tmp_path, monkeypatch):
    """리뷰 #199: 이어 쓴 목록이 오늘 가격을 받은 미국 목록과 US_SP500_MIN 곳 아래로 겹치면 (sp_ok 거짓) 예전의 '믿지 못한 날' 그대로예요 —
    spCarried · spTickers 는 적고, spGone · noPx · spErr 는 빈 값, usForeign.sp500.ok 거짓, 로그가 이어 쓴 목록이라고 말해요. 이어 쓸 목록은
    us_sp500_prev_safe 를 바꿔 넣어 만들어요 (오늘 가격이 있는 티커 3곳 + 가격이 없는 티커 30곳)."""
    err = HTTPError(WIKI_429)
    carried = sorted(["SAAA", "SAAB", "SAAC"] + _letters("Z", 30, AVOID))
    monkeypatch.setattr(F, "us_sp500_prev_safe", lambda prev, today: {"tickers": carried, "from": "2026-11-27", "age": 1, "ref": None})
    out, meta, lines, sp, _f = _fetch(tmp_path, monkeypatch, [err, err], None, tag="o1", **SMALL)
    u = meta["usListSym"]
    assert u["spCarried"] == {"from": "2026-11-27", "why": WHY_2X429} and u["spTickers"] == carried
    assert u["spGone"] is None and u["noPx"] is None and u["spErr"] is None
    assert meta["usForeign"]["sp500"] == {"n": 33, "inList": 3, "ok": False}
    assert u["missing"] == {"BF-B": "이어 쓴 S&P 500 목록(2026-11-27 읽음)에 없음 (지수에서 빠졌는지 확인)"}
    assert any(x.startswith("  !! S&P 500 목록을 쓸 수 없어요 (목록 33곳 · 오늘 미국 목록과 겹침 3곳 · 지난 발행본에서 이어 쓴 2026-11-27 목록 — 겹침 5곳 이상")
               for x in lines), [x for x in lines if "S&P 500 목록" in x]
    rows = gate_rows(meta, out)
    assert rows[ROW][3] == "WARN" and rows[ROW][1].startswith("지난 발행본의 S&P 500 목록을 이어 씀: 2026-11-27 읽음 (발행일 2026-11-28 까지 1일) · 33종목")
    assert rows[SHARE2][3] != "FAIL" and "S&P 500 목록을 믿지 못한 날 (빠진 종목을 세지 않음)" in rows[SHARE2][1]
    assert rows[SHARE1][3] == "WARN"                                                 # BF-B 가 빠짐 (이유와 함께 · 경고만)


def test_a_same_day_rerun_carries_a_list_read_that_day(monkeypatch):
    """나이 0 (같은 날 다시 도는 실행이 그날 아침 발행본의 목록을 이어 씀) 도 써요."""
    sp = sp_yahoo(sp_rows(501))
    us = set(sp) | set(_letters("Q", NQ_ONLY, AVOID)) | set(F.EXTRA_US)
    p = prev_of(sp, us, published="2026-11-28T06:41:00+09:00")
    assert F.us_sp500_prev(p, TODAY)["age"] == 0
    err = HTTPError(WIKI_429)
    syms, names, fdr, slept, lines, sp2 = _tickers(monkeypatch, [err, err], prev=p)
    assert names.spCarried["from"] == "2026-11-28" and names.sp500 == frozenset(sp)
    assert any("지난 발행본의 목록(2026-11-28 읽음 · 503종목 · 0일 전)을 썼어요" in x for x in lines)


def test_one_failed_and_one_unusable_read_say_both(monkeypatch):
    """리뷰 #199 (Opus): 두 번의 까닭을 모두 적어요 · 머리말이 사실대로 ('한 번은 읽지 못하고 한 번은 읽었지만 쓸 수 없어')."""
    names_only = pd.DataFrame({"Security": ["Apple Inc.", "Visa"]})
    syms, names, fdr, slept, lines, sp = _tickers(monkeypatch, [HTTPError(WIKI_429), names_only])
    why = names.spCarried["why"]
    second = " · 2차: 받은 목록 2행 · 쓸 수 있는 티커 1곳 · 야후 모양으로 바꾸지 못한 행 1 (앞: 'APPLE INC.') — 목록 1곳"
    assert why.startswith("1차: HTTPError: 429 Client Error") and second in why, why
    assert len(why) <= F.US_SP500_WHY_MAX
    assert any(x.startswith("  !! S&P 500 목록을 한 번은 읽지 못하고 한 번은 읽었지만 쓸 수 없어 (1차: HTTPError") for x in lines), lines
    # 이어 쓴 기록의 글은 관문의 낱말 줄을 지나요 ('nan' 같은 원래 값이 와도)
    bad = pd.DataFrame({"Security": ["nan", "None Corp", "null"]})
    syms, names, *_r = _tickers(monkeypatch, [bad, bad])
    assert not V.BAD_WORD.search(names.spCarried["why"]), names.spCarried["why"]


@pytest.mark.parametrize("seq, title", [("carry", F.US_SP500_CARRY_TITLE), ("none", F.US_SP500_NONE_TITLE), ("ok", None)])
def test_a_github_warning_of_its_own_reaches_the_morning_check(monkeypatch, capsys, seq, title):
    """리뷰 #199 (둘 다): 관문의 알림은 종류마다 10개까지라 관문 줄이 밀려날 수 있어요. 데이터 수집 단계가 GitHub Actions 에서만 따로 한 줄을 내요 —
    이어 쓴 날 · 이어 쓰지 못한 날 한 줄씩, 보통 날은 없음. 메시지의 % 는 %25 로."""
    err = HTTPError(WIKI_429)
    prev = ... if seq != "none" else None
    for env in (None, "true"):
        if env:
            monkeypatch.setenv("GITHUB_ACTIONS", env)
        else:
            monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        capsys.readouterr()
        _tickers(monkeypatch, ["ok"] if seq == "ok" else [err, err], prev=prev)
        out = [x for x in capsys.readouterr().out.splitlines() if x.startswith("::")]
        if env is None or title is None:
            assert out == [], out
            continue
        lead = "S&P 500 목록을 읽지 못해" if seq == "carry" else "S&P 500 목록을 다시 읽어도 읽지 못해"
        assert len(out) == 1 and out[0].startswith(f"::warning title={title}::{lead}"), out
        assert "%0A" not in out[0] and "List_of_S%2526P_500_" in out[0] and "%26P" not in out[0].replace("%2526P", "")
        if seq == "carry":
            assert "2026-11-27 에 읽은 지난 발행본의 목록 503종목을 썼어요 (1일 전 · 7일까지만 이어 써요" in out[0]
        else:
            assert "지난 발행본의 목록도 이어 쓸 수 없어요 (지난 발행본을 읽지 못함)" in out[0]


# ── 4. 미국 종목 수: 이어 쓰면 보통 날처럼 800 곁으로 ───────────────────────────────
def test_with_a_carried_list_the_us_count_is_back_near_800(tmp_path, monkeypatch):
    """실제 크기의 가짜 목록 (S&P 500 503 · 나스닥 상위 400 중 S&P 밖 270 · EXTRA_US). 11-28 처럼 두 번 다 429 면: 이어 쓴 날은 보통 날과 같은
    수가 나가고 관문의 '미국 종목 수' 두 줄이 통과해요. 이어 쓸 수 없는 날(8일 지남)은 예전처럼 S&P 500 이 빠져 두 줄이 막아요."""
    err = HTTPError(WIKI_429)
    good_out, good_meta, *_r = _fetch(tmp_path, monkeypatch, ["ok"], None, tag="k0")
    n_good = V.us_px_count({"stocks": good_out})[0]
    assert 780 <= n_good <= 840, n_good
    prev = _prev_from(good_out, good_meta, PUB_1127)
    out, meta, *_r = _fetch(tmp_path, monkeypatch, [err, err], prev, tag="k1")
    rep = V.Report()
    V.check_us_counts(rep, {"stocks": out}, prev)
    rows = {r[0]: r for r in rep.rows}
    assert V.us_px_count({"stocks": out})[0] == n_good
    assert rows["미국 종목 수"][3] == "PASS" and rows["미국 종목 수 변화"][3] == "PASS", rows
    old = copy.deepcopy(prev)
    old["publishedAt"] = "2026-11-20T06:40:00+09:00"
    out2, meta2, *_r = _fetch(tmp_path, monkeypatch, [err, err], old, tag="k2")
    rep = V.Report()
    V.check_us_counts(rep, {"stocks": out2}, prev)
    rows = {r[0]: r for r in rep.rows}
    assert V.us_px_count({"stocks": out2})[0] < V.US_MIN and rows["미국 종목 수"][3] == "FAIL" and rows["미국 종목 수 변화"][3] == "FAIL"
    assert "spCarried" not in meta2["usListSym"]


# ── 5. 관문 줄: 경고만 · 실패 없음 ─────────────────────────────────────────────────
CARRIED = {"from": "2026-11-27", "why": f"HTTPError: {WIKI_429}"}


def _row(data):
    rep = V.Report()
    V.check_us_sp_carry(rep, data)
    assert len(rep.rows) == 1 and not rep.failed
    return rep.rows[0]


def _data(**u):
    base = {"read": True, "mapped": [], "unmapped": [], "spTickers": sp_yahoo(sp_rows(501)), "spGone": {}, "noPx": [], "spErr": [], "missing": {}}
    base.update(u)
    return {"publishedAt": "2026-11-28T00:35:00+09:00", "usListSym": base}


def test_the_gate_row_names_the_list_and_its_date():
    r = _row(_data(spCarried=CARRIED))
    assert r[0] == ROW and r[3] == "WARN" and r[2] == V.US_SP_CARRY_RULE
    assert r[1].startswith("지난 발행본의 S&P 500 목록을 이어 씀: 2026-11-27 읽음 (발행일 2026-11-28 까지 1일) · 503종목 · 오늘의 목록을 쓰지 못한 까닭: "
                           "HTTPError: 429 Client Error")
    assert _row(_data())[1:] == ("이어 쓰지 않음 (그날 읽은 목록)", V.US_SP_CARRY_RULE, "PASS")
    assert _row(_data(spTickers=None))[3] == "PASS"
    assert _row({"publishedAt": "2026-11-28T00:35:00+09:00"})[3] == "SKIP"
    old = _row(_data(spCarried={"from": "2026-11-19", "why": "x"}))
    assert old[3] == "WARN" and "7일 넘은 목록 (파이프라인은 이어 쓰지 않아야 해요 — 확인 필요)" in old[1] and "(발행일 2026-11-28 까지 9일)" in old[1]


@pytest.mark.parametrize("data", [
    None, [], "x", {}, {"usListSym": None}, {"usListSym": []}, {"usListSym": {"spCarried": "2026-11-27"}},
    {"usListSym": {"spCarried": ["2026-11-27"]}}, {"usListSym": {"spCarried": {}}}, {"usListSym": {"spCarried": {"from": 3, "why": None}}},
    {"usListSym": {"spCarried": {"from": "2026-11-27", "why": ["a"]}, "spTickers": "AAPL"}, "publishedAt": 5},
    {"usListSym": {"spCarried": {"from": "2026-11-30", "why": "x"}}, "publishedAt": "2026-11-28T00:35:00+09:00"},
    {"usListSym": {"spCarried": {"from": "2026-02-30", "why": "x"}}, "publishedAt": "어제"},
    {"usListSym": {"spCarried": {"from": "2026-11-27", "why": "x" * 5000}, "spTickers": list(range(3))}, "publishedAt": "2026-11-28T00:35:00"},
])
def test_the_gate_row_never_fails(data):
    r = _row(data)
    assert r[0] == ROW and r[3] in ("PASS", "WARN", "SKIP")


def test_the_gate_row_warns_when_its_own_check_crashes(monkeypatch):
    monkeypatch.setattr(V, "_iso_day", lambda s: 1 / 0)
    r = _row(_data(spCarried=CARRIED))
    assert r[3] == "WARN" and r[1] == "검사가 멈췄어요: ZeroDivisionError: division by zero"


def test_the_row_runs_in_the_gate_and_changes_no_other_row():
    """run_checks 에 이 줄이 있어요. 같은 파일에 이어 쓴 기록만 더하면 이 줄만 경고로 바뀌고 다른 줄은 모두 그대로예요."""
    cur, prev, final = good_pair()

    def run(c):
        rep = V.run_checks(c, prev, final, dt.date(2026, 10, 31), mode="publish", count_between=lambda a, b: 1,
                           sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                           now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
        return {r[0]: r for r in rep.rows}
    base = run(cur)
    assert base[ROW][3] == "SKIP"                                                   # 시험 데이터에는 usListSym 이 없어요
    us = [s["t"] for s in cur["data"]["stocks"] if s.get("cls") == "us"]
    for c_rec, want in ((None, "PASS"), (CARRIED, "WARN")):
        c = copy.deepcopy(cur)
        u = {"read": True, "mapped": [], "unmapped": [], "spTickers": sorted(us[:450]), "spGone": {}, "noPx": [], "spErr": [], "missing": {}}
        if c_rec:
            u["spCarried"] = c_rec
        c["data"]["usListSym"] = u
        rows = run(c)
        assert rows[ROW][3] == want, rows[ROW]
        if c_rec:
            assert "2026-11-27 읽음" in rows[ROW][1]
            plain = copy.deepcopy(cur)
            plain["data"]["usListSym"] = {k: v for k, v in u.items() if k != "spCarried"}
            other = run(plain)
            assert {k: v for k, v in rows.items() if k != ROW} == {k: v for k, v in other.items() if k != ROW}


# ── 6. 관문 줄: 직전 발행본과 따로 맞춰 봄 (리뷰 #199 Opus) · spCarried: null ──────────────────────────
def _prow(data, pdata):
    rep = V.Report()
    V.check_us_sp_carry(rep, data, pdata)
    assert len(rep.rows) == 1 and not rep.failed
    return rep.rows[0]


def _pdata(published="2026-11-27T06:41:04+09:00", carried=...):
    p = {"publishedAt": published, "usListSym": {"spTickers": ["AAPL"]}}
    if carried is not ...:
        p["usListSym"]["spCarried"] = carried
    return p


@pytest.mark.parametrize("cur_from, pdata, part", [
    ("2026-11-27", _pdata(), "직전 발행본의 발행일 2026-11-27 와 맞춰 봄 (같음)"),
    ("2026-11-26", _pdata(), "직전 발행본의 발행일 2026-11-27 와 맞춰 봄 (그보다 앞)"),
    ("2026-11-28", _pdata(), "처음 읽은 날 2026-11-28 이 직전 발행본의 발행일 2026-11-27 보다 뒤 — 날짜가 새로 매겨졌을 수 있어요 (7일 한도 확인 필요)"),
    ("2026-11-23", _pdata(carried={"from": "2026-11-23", "why": "x"}), "직전 발행본의 spCarried.from 2026-11-23 와 맞춰 봄 (같음)"),
    ("2026-11-27", _pdata(carried={"from": "2026-11-23", "why": "x"}),
     "처음 읽은 날 2026-11-27 이 직전 발행본의 spCarried.from 2026-11-23 보다 뒤 — 날짜가 새로 매겨졌을 수 있어요"),
    ("2026-11-27", _pdata(published="2026-11-26T22:00:00Z"), "직전 발행본의 발행일 2026-11-27 와 맞춰 봄 (같음)"),
    ("2026-11-27", _pdata(carried=None), "직전 발행본과 맞춰 보지 못함 (직전 발행본의 spCarried 모양이 잘못됨)"),
    ("2026-11-27", _pdata(published="어제"), "직전 발행본과 맞춰 보지 못함 (직전 발행본의 publishedAt 을 읽지 못함)"),
    ("2026-11-27", {"publishedAt": "2026-11-27T06:41:04+09:00"}, "직전 발행본과 맞춰 보지 못함 (직전 발행본에 usListSym 이 없음)"),
    ("2026-11-27", None, None),                                                       # 사이트 점검 (직전 발행본 없이): 맞춰 보지 않아요
])
def test_the_gate_row_cross_checks_the_first_read_day_with_the_previous_publish(cur_from, pdata, part):
    r = _prow(_data(spCarried={"from": cur_from, "why": "HTTPError: 429"}), pdata)
    assert r[3] == "WARN", r
    if part is None:
        assert "직전 발행본" not in r[1], r[1]
    else:
        assert part in r[1], r[1]


def test_the_cross_check_never_fails_even_when_it_crashes(monkeypatch):
    monkeypatch.setattr(V, "us_sp_carry_prev_day", lambda p: 1 / 0)
    r = _prow(_data(spCarried=CARRIED), _pdata())
    assert r[3] == "WARN" and "직전 발행본과 맞춰 보다가 멈췄어요 (ZeroDivisionError" in r[1] and r[1].startswith("지난 발행본의 S&P 500 목록을 이어 씀: 2026-11-27")
    assert _prow(_data(), _pdata())[3] == "PASS"                                       # 이어 쓰지 않은 날은 맞춰 보지 않아요
    for bad in (None, [], "x", {"usListSym": "x"}, {"usListSym": {"spCarried": "2026"}}):
        assert _prow(_data(spCarried=CARRIED), bad)[3] == "WARN"


def test_an_explicit_null_is_malformed_in_the_gate_as_in_the_pipeline():
    """리뷰 #199 (Opus): spCarried: null 은 파이프라인이 이어 쓰지 않는 모양 (test_a_carried_list_keeps_its_first_read_day) — 관문도 통과가 아니라
    '모양이 잘못됨' 경고예요. 칸이 아예 없으면 통과 그대로."""
    r = _row(_data(spCarried=None))
    assert r[1:] == ("spCarried 모양이 잘못됨 (null)", V.US_SP_CARRY_RULE, "WARN")
    assert _row(_data())[3] == "PASS"
    sp = sp_yahoo(sp_rows(501))
    p = prev_of(sp, set(sp))
    p["usListSym"]["spCarried"] = None
    w = F.us_sp500_prev(p, TODAY)
    assert "tickers" not in w and "spCarried.from" in w["why"]


def test_run_checks_passes_the_previous_publish_to_the_cross_check():
    cur, prev, final = good_pair()
    us = [s["t"] for s in cur["data"]["stocks"] if s.get("cls") == "us"]
    rec = {"read": True, "mapped": [], "unmapped": [], "spTickers": sorted(us[:450]), "spGone": {}, "noPx": [], "spErr": [], "missing": {}}
    prev = copy.deepcopy(prev)
    prev["data"]["usListSym"] = copy.deepcopy(rec)                                   # 직전 발행본: 그날 읽은 목록 (10-31 발행)
    c = copy.deepcopy(cur)
    c["data"]["usListSym"] = {**rec, "spCarried": {"from": "2026-11-01", "why": "HTTPError: 429"}}   # 직전 발행일보다 뒤 → 새로 매겨졌을 수 있음
    for mode, seen in (("publish", True), ("live", False)):
        rep = V.run_checks(c, prev, final, dt.date(2026, 10, 31), mode=mode, count_between=lambda a, b: 1,
                           sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                           now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
        row = {r[0]: r for r in rep.rows}[ROW]
        assert row[3] == "WARN" and ("날짜가 새로 매겨졌을 수 있어요" in row[1]) is seen, (mode, row)
