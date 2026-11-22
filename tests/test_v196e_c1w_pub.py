# -*- coding: utf-8 -*-
"""v19.6e 5차 (Jack, 2026-11-22 · 그대로): "Better option: take a Korean stock's "last week's close" from our own published data for that
day. Every close we've published since the outage was confirmed by two sources. Use Naver only for a stock missing from our own data, and
then with the (c) footnote … Leave a stock out only if neither exists."

여기서 보는 것 (네트워크 없음 · 새 파일 · 예전 시험은 그대로):
1. 실제 발행본 (data 브랜치 db341a0 · 618f128 · f0e9aa9 · b3d41f3 · 5f1d9d1 의 14종목) 과 실제 목록 파일로 11-16 ~ 11-20 주를 날마다 정확히
   확인해요: 11-17 · 11-19 는 지난 발행본 종가, 11-18 은 11-18 발행본의 d1 로 본 11-17 종가 범위. 작은 재설정도 범위 밖이면 비워요.
2. 자기 가격 날짜 (pxd) · 거래 없음 행은 쓰지 않아요 · 기준일마다 그날의 마지막 발행본 · 가격 출처가 공식 종가 목록이 아닌 발행본은 쓰지 않아요.
3. 발행본이 같은 날 최종본 목록 파일과 다르면 그 종목을 비워요 (확인 단계 · 모든 종목) · 크게 남겨요.
4. 지난 발행본을 읽지 못하면 크게 남기고 오늘 받은 자료만으로 (실행은 이어가요) · git 실패 · 시간 초과 · 이상한 값.
5. 그 주 앞 마지막 거래일에 최종본 목록 파일이 없으면 그날 발행본의 종가 · 상장주식수로.
6. 네이버는 지난 발행본에 없는 종목에만 (c1wv nv) — 발행본에 있는 종목은 네이버 자료가 있어도 쓰지 않아요.
7. 진짜 git (이 폴더 밖 임시 저장소 · file://) 으로 data 브랜치 읽기 · 관문 줄 (경고만) · 로그 줄.
"""
import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import fixture_data as FD  # noqa: E402

D = dt.date
HOL = F.load_market_holidays()
FX2 = os.path.join(ROOT, "tests", "fixtures", "kr_two_source")
FXG = os.path.join(ROOT, "tests", "fixtures", "d1_after_gap")
FXP = os.path.join(ROOT, "tests", "fixtures", "c1w_pub")
D13, D16, D17, D18, D19, D20 = (D(2026, 11, d) for d in (13, 16, 17, 18, 19, 20))
TD = [pd.Timestamp(d) for d in (D13, D16, D17, D18, D19, D20)]
PUB_DAYS = ("2026-11-13", "2026-11-16", "2026-11-18", "2026-11-19")
KNX = {"496320"}


def _lf(d, n):
    return F.parse_listing_csv(open(os.path.join(d, f"krx_{n}.csv"), encoding="utf-8").read())


def week_files():
    """그 주 그대로 (실제 파일): 11-13 · 11-16 최종본 · 11-17 (15:29) · 11-18 (14:52) · 11-19 (14:52) 장중 파일 · 11-20 최종본."""
    sessions = [(D16, _lf(FX2, "2026-11-16_2211")), (D13, _lf(FX2, "2026-11-13_2158"))]
    nonfinal = {D17: _lf(FX2, "2026-11-17_1529"), D18: _lf(FX2, "2026-11-18_1452"), D19: _lf(FXG, "2026-11-19_1452")}
    return sessions, nonfinal, _lf(FXG, "2026-11-20_2323")


def raw_pub(day):
    return json.load(open(os.path.join(FXP, f"pub_{day}.json"), encoding="utf-8"))


def pubs(edit=None, days=PUB_DAYS):
    """c1w_pub_step 이 넘기는 모양 {날짜: c1w_pub_rows}. edit(날짜, data.json) 로 발행본을 고쳐 볼 수 있어요."""
    out = {}
    for d in days:
        js = raw_pub(d)
        if edit:
            edit(d, js)
        rows, why = F.c1w_pub_rows(js, D.fromisoformat(d))
        assert why is None, (d, why)
        out[d] = dict(rows, sha=f"sha{d[-2:]}", at=js.get("publishedAt"))
    return out


def codes_of(df):
    return sorted(set(df["Code"].astype(str).str.strip()))


def rescue(pub, codes=None, naver=None, nonfinal=None, sessions=None, prev=None):
    s, nf, f20 = week_files()
    return F.kr_c1w_rescue(D20, D13, TD, s if sessions is None else sessions, f20, nf if nonfinal is None else nonfinal, prev, naver or {},
                           codes or codes_of(f20), knx=KNX, ndays=(2, 10), pub=pub)


def _row(js, t):
    return next(x for x in js["stocks"] if x["t"] == t)


def _set(df, code, **kw):
    df = df.astype({k: float for k in kw})
    i = df.index[df["Code"] == code][0]
    for k, v in kw.items():
        df.at[i, k] = v
    return df


# ── 1. 실제 발행본으로 그 주를 날마다 정확히 ─────────────────────────────────────────────────
def test_published_closes_settle_the_gap_week_exactly():
    """11-17 기준가 (장중 파일) = 11-16 최종본 종가 · 11-18 기준가 (장중 파일) 가 11-18 발행본 d1 로 본 11-17 종가 범위 안 · 11-19 기준가 (장중
    파일) = 11-18 발행본 종가 · 11-20 기준가 (최종본) = 11-19 발행본 종가 → 9종목 'pub'. 유니온머티리얼 (실제 5:1 병합 11-16) 은 재설정 ·
    11-19 발행본에 없는 종목 (금양 거래 없음 · STX · 바이오비쥬 두 출처 다름 · 코넥스 본시스템즈) 은 기준일 연결을 확인 못 해 비워요."""
    res = rescue(pubs())
    ok = {c for c, v in res.items() if v == ("pub", None)}
    assert ok == {"000660", "005380", "005930", "012450", "0126Z0", "015760", "035420", "090460", "105560"}, res
    assert res["047400"] == ("base", None)
    assert {c for c, v in res.items() if v == ("blank", "pxLink")} == {"001570", "011810", "489460", "496320"}
    # 4차 그대로 (지난 발행본 하나 · 11-19) 였다면 11-18 · 11-19 의 앞 거래일 종가가 없어 모두 네이버로 가야 했어요 (네이버 자료 없음 → 빈 칸)
    s, nf, f20 = week_files()
    old = F.kr_c1w_rescue(D20, D13, TD, s, f20, nf, raw_pub("2026-11-19"), {}, sorted(ok), knx=KNX, ndays=(2, 10))
    assert set(old.values()) == {("blank", "noNaver")}
    # 실제 값: 11-18 발행본의 삼성전자 194,700 · d1 2.31 → 11-17 종가 190,300 ~ 190,319 · 11-18 장중 파일의 기준가 190,400 ← 그날 종가
    js = raw_pub("2026-11-18")
    p, g = _row(js, "005930")["price"], _row(js, "005930")["d1"]
    lo, hi = p / (1 + (g + F.C1W_PUB_D1_HALF) / 100), p / (1 + (g - F.C1W_PUB_D1_HALF) / 100)
    b = F._c1w_frame_vals(week_files()[1][D18])["005930"][1]
    assert lo - 1 <= b <= hi + 1 and hi - lo < 20, (lo, hi, b)


def test_the_d1_range_is_what_settles_the_day_without_a_publish():
    """11-17 발행본은 없어요 (실제 data 브랜치). 11-18 발행본의 d1 을 지우면 11-18 의 연결은 확인 못 한 날이 돼요 → 지난 발행본에 없는 날이라
    네이버로 (자료 없음 → 빈 칸)."""
    def no_d1(d, js):
        if d == "2026-11-18":
            for x in js["stocks"]:
                x.pop("d1", None)
    res = rescue(pubs(no_d1), codes=["005930", "000660"])
    assert res == {"005930": ("blank", "noNaver"), "000660": ("blank", "noNaver")}


def test_a_small_reset_outside_the_published_range_is_a_reset():
    """11-18 기준가가 d1 로 본 11-17 종가 범위 (±0.005%p + 1원) 밖이면 'break' → 재설정으로 비워요. 0.1% 작은 권리락도 (범위 폭 약 19원)."""
    s, nf, f20 = week_files()
    base = F._c1w_frame_vals(nf[D18])["005930"][1]
    for k, want in ((1.001, ("base", None)), (0.999, ("base", None)), (1.0, ("pub", None))):
        nf2 = dict(nf)
        cl = float(nf[D18].loc[nf[D18]["Code"] == "005930", "Close"].iloc[0])
        nf2[D18] = _set(nf[D18], "005930", Changes=cl - round(base * k))
        assert rescue(pubs(), codes=["005930"], nonfinal=nf2)["005930"] == want, k


def test_published_d1_must_agree_with_a_known_close_of_that_day():
    """그 앞 날 종가를 다른 자료 (최종본 목록 파일) 로도 알면 다음 거래일 발행본의 d1 범위 안이어야 해요 — 11-16 발행본의 d1 을 1%p 바꾸면
    11-13 최종본 종가가 그 범위 밖 → 그날은 conflict (비움)."""
    def bad(d, js):
        if d == "2026-11-16":
            _row(js, "005930")["d1"] += 1.0
    assert rescue(pubs(bad), codes=["005930"]) == {"005930": ("blank", "conflict")}


# ── 2. 쓰는 행 · 쓰는 발행본 ─────────────────────────────────────────────────────────────
def test_a_carried_row_or_a_no_trade_row_is_never_used():
    """자기 가격 날짜 (pxd · 마지막 확인 종가로 실은 행) 와 거래 없음 (noTrade) 행은 그날 확인된 종가가 아니에요 (kr_prev_pub_closes 와 같은 규칙)."""
    js = raw_pub("2026-11-19")
    _row(js, "005930")["pxd"] = "2026-11-18"
    rows, why = F.c1w_pub_rows(js, D19)
    assert why is None and "005930" not in rows["close"] and "005930" not in rows["d1"] and "005930" not in rows["shr"]
    assert "001570" not in rows["close"] and rows["skip"] == 2           # 금양: noTrade
    assert rows["close"]["000660"] == 1183000.0 and rows["d1"]["000660"] == 3.41
    res = rescue(pubs(lambda d, j: _row(j, "005930").update(pxd="2026-11-18") if d == "2026-11-19" else None), codes=["005930", "000660"])
    assert res == {"005930": ("blank", "pxLink"), "000660": ("pub", None)}
    # 가격 출처가 공식 종가 목록이 아닌 발행본 (지난 data.json 으로 만든 목록) · 다른 날의 발행본은 쓰지 않아요
    js2 = raw_pub("2026-11-19")
    js2["listSrc"] = "prev-data.json"
    assert F.c1w_pub_rows(js2, D19) == (None, "src")
    assert F.c1w_pub_rows(raw_pub("2026-11-19"), D18) == (None, "day")


def _commits(*items):
    """[(sha, KST 커밋 시각 'MM-DD HH:MM', blob, data.json)] → c1w_pub_pick 의 commits · load."""
    store = {}
    cs = []
    for sha, when, blob, js in items:
        cs.append((sha, dt.datetime.strptime(f"2026-{when}", "%Y-%m-%d %H:%M").replace(tzinfo=F.KST) if when else None, blob))
        store[blob] = js
    reads = []

    def load(sha, blob):
        reads.append(sha)
        js = store[blob]
        if isinstance(js, Exception):
            raise js
        return js, 1000
    return cs, load, reads


def test_pick_takes_the_latest_publish_per_day_and_stops_early():
    latest, older = raw_pub("2026-11-19"), raw_pub("2026-11-19")
    _row(older, "005930")["price"] = 1.0                      # 같은 기준일의 앞선 발행본 — 쓰지 않아요
    cs, load, reads = _commits(("c20", "11-21 06:41", "b20", raw_pub("2026-11-20")), ("c19b", "11-20 08:33", "b19b", latest),
                               ("c19a", "11-20 06:40", "b19a", older), ("c19z", "11-20 06:00", "b19a", older),       # 같은 blob → 한 번만
                               ("c18", "11-19 12:16", "b18", raw_pub("2026-11-18")), ("cx", "11-19 08:00", "bx", ValueError("깨진 JSON")),
                               ("c16", "11-17 06:40", "b16", raw_pub("2026-11-16")), ("c13", "11-15 15:59", "b13", raw_pub("2026-11-13")),
                               ("c12", "11-13 07:00", "b12", {"pxDate": "2026-11-12", "stocks": []}))
    out = F.c1w_pub_pick(cs, load, D13, D20, TD)
    assert sorted(out["days"]) == list(PUB_DAYS) and out["want"] == ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]
    assert out["days"]["2026-11-19"]["sha"] == "c19b" and out["days"]["2026-11-19"]["close"]["005930"] == 196900.0
    assert out["stop"] == "older" and "c12" not in reads and reads.count("c19a") + reads.count("c19z") == 1 and out["dup"] == 1
    assert out["bad"] == [("cx", "json")] and out["read"] == 7
    # 커밋 날짜가 그 주 앞 마지막 거래일보다 앞이면 멈춰요 (발행본의 기준일은 커밋 날짜보다 늦지 않아요) · 상한
    cs, load, reads = _commits(("c13", "11-12 23:59", "b13", raw_pub("2026-11-13")))
    assert F.c1w_pub_pick(cs, load, D13, D20, TD)["stop"] == "time" and reads == []
    cs, load, reads = _commits(("c20", "11-21 06:41", "b20", raw_pub("2026-11-20")), ("c19", "11-20 08:33", "b19", latest))
    assert F.c1w_pub_pick(cs, load, D13, D20, TD, max_read=1)["stop"] == "cap" and reads == ["c20"]
    # 그날의 마지막 발행본을 쓸 수 없으면 (가격 출처) 더 앞 발행본도 쓰지 않아요
    bad = raw_pub("2026-11-19")
    bad["listSrc"] = "prev-data.json"
    cs, load, reads = _commits(("c19b", "11-20 08:33", "b1", bad), ("c19a", "11-20 06:40", "b2", latest))
    out = F.c1w_pub_pick(cs, load, D13, D20, TD)
    assert "2026-11-19" not in out["days"] and out["unusable"] == {"2026-11-19": ("c19b", "src")}


# ── 3. 발행본과 최종본 목록 파일이 다르면 ─────────────────────────────────────────────────────
def test_a_publish_that_disagrees_with_a_final_file_blanks_that_stock():
    """11-13 발행본의 삼성전자를 100원 다르게: 확인 단계 (모든 종목 · 목록 파일끼리 'ok' 인 종목도) 가 pubDiff 로 찾고 c1w_apply 가 비워요 ·
    kr_c1w_rescue 안에서도 그날 자료끼리 다름 (conflict). d1 범위가 그 앞 날 최종본 종가와 다른 것도 (11-16 발행본의 d1 → 11-13)."""
    s, _nf, _f = week_files()

    def off(d, js):
        if d == "2026-11-13":
            _row(js, "005930")["price"] += 100
        if d == "2026-11-16":
            _row(js, "000660")["d1"] += 0.5
    pub = pubs(off)
    diff = F.c1w_pub_diff(s, pub, D13, D20, TD)
    assert sorted(diff) == ["000660", "005930"] and diff["005930"] == "2026-11-13 발행 206,100 · 파일 206,000", diff
    assert diff["000660"].startswith("2026-11-13 발행 등락률로 ") and diff["000660"].endswith(" · 파일 1,216,000")
    assert F.c1w_pub_diff(s, pubs(), D13, D20, TD) == {}
    assert rescue(pub, codes=["005930"]) == {"005930": ("blank", "conflict")}
    lines = []
    kw = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"005930": 206000.0, "005380": 269500.0},
          "shr": {"005930": 5846278608, "005380": 204757766}, "ref": {"005930": "ok", "005380": "ok"}, "src": "listing", "rows": 2,
          "gap": [], "rescue": {}, "pubDiff": diff, "pubHist": {"need": "gap"}}
    st = [{"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 183100.0, "shr": 5846278608},
          {"t": "005380", "nk": "현대차", "cls": "kr", "price": 255000.0, "shr": 204757766}]
    meta, info = F.c1w_apply(st, kw, None, HOL)
    assert "c1w" not in st[0] and st[1]["c1w"] == 269500.0
    assert meta["c1wSrc"]["link"] == {"pubDiff": 1} and meta["c1wSrc"]["pub"] == 0 and meta["c1wSrc"]["listing"] == 1
    old = F.log
    try:
        F.log = lines.append
        F.log_c1w(info)
    finally:
        F.log = old
    assert ("  !! c1w 지난 발행본 종가 ↔ 같은 날 최종본 목록 파일: 다른 종목 2 (비움) — 005930 삼성전자 (2026-11-13 발행 206,100 · 파일 206,000)"
            in lines), lines


# ── 4. 읽지 못하면 크게 · 오늘 받은 자료만으로 ─────────────────────────────────────────────
def _kw(file=False):
    s, _nf, f20 = week_files()
    ss = [x for x in s if not (file and x[0] == D13)]
    ref, _ = F.kr_ref_links([(D20, f20)] + ss, TD, set(codes_of(f20)))
    kw = F.kr_week_closes(D20, TD, ss, ref)
    return kw, ss, ref


def test_missing_history_falls_back_loudly(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    kw, s, ref = _kw()
    assert F.c1w_pub_need(kw) == "gap" and kw["gap"] == ["2026-11-17", "2026-11-18", "2026-11-19"]
    for reader, key in ((lambda *a: {"fail": "fetch", "err": "fatal: unable to access 'https://x-access-token:abc@github.com/o/r/'"}, "fetch"),
                        (lambda *a: 1 / 0, "err"), (lambda *a: "이상한 값", "err")):
        lines.clear()
        kw2, pub = F.c1w_pub_step(copy.deepcopy(kw), D20, TD, s, ref, reader=reader)
        assert pub == {} and kw2["pubHist"]["fail"] == key and kw2["pubHist"]["need"] == "gap"
        assert lines[-1].startswith(f"  !! c1w 지난 발행본 (data 브랜치) 을 읽지 못했어요 — {F.C1W_PUB_FAIL_KO[key]}"), lines
        assert "그 주에 최종본 목록 파일이 없는 날이 있어요 (2026-11-17, 2026-11-18, 2026-11-19) → 오늘 받은 자료만으로 확인해요" in lines[-1]
        assert "abc" not in lines[-1]                                 # 주소의 사용자 정보는 가려요
    # 그다음 단계는 예전처럼 (지난 발행본 하나 · 장중 파일 · 네이버) — 실행은 이어가요
    _s, nf, f20 = week_files()
    out = F.kr_c1w_rescue_step(kw2, D20, TD, s, f20, nf, raw_pub("2026-11-19"), {}, knx=KNX, daum={"v": 1, "days": [], "kk": {}}, pub=pub)
    assert out["pubDiff"] == {} and out["rescueSrc"]["hist"] == [] and out["rescue"]["005930"] == ("blank", "noNaver")
    st = [{"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 183100.0, "shr": 5846278608}]
    meta, _info = F.c1w_apply(st, out, None, HOL)
    assert "c1w" not in st[0] and meta["c1wSrc"]["pub"] == 0
    json.dumps(meta, allow_nan=False)
    # 단계 안 어디서 멈춰도 (로그 줄까지) 실행은 이어가요
    lines.clear()
    monkeypatch.setattr(F, "log_c1w_pub", lambda *a: 1 / 0)
    kw3, pub3 = F.c1w_pub_step(copy.deepcopy(kw), D20, TD, s, ref, reader=lambda *a: {"days": pubs()})
    assert pub3 == {} and kw3["pubHist"]["fail"] == "err" and lines[-1].startswith("  !! c1w 지난 발행본 단계가 멈췄어요 (ZeroDivisionError")


def test_no_history_is_read_in_a_normal_week(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    kw = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {}, "shr": {}, "ref": {}, "src": "listing", "rows": 0, "gap": []}
    called = []
    kw2, pub = F.c1w_pub_step(kw, D20, TD, [], {}, reader=lambda *a: called.append(a))
    assert called == [] and pub == {} and kw2["pubHist"] == {"need": None}
    assert lines == ["· c1w 지난 발행본: 읽지 않아요 (그 주 날마다 최종본 목록 파일이 있어요)"]
    assert F.c1w_pub_step({"date": None, "why": "noDay"}, D20, TD, [], {}, reader=lambda *a: called.append(a))[1] is None and called == []


def test_the_git_reader_never_raises_and_hides_credentials(monkeypatch, tmp_path):
    """가짜 git: 주소를 모름 · fetch 실패 (사용자 정보 가림) · 시간 초과 — 모두 fail 로 (예외 없음) · 임시 폴더는 지워요."""
    made = []

    def mk(prefix=None):
        made.append(str(tmp_path / f"c1w-pub-{len(made)}"))
        os.makedirs(made[-1])
        return made[-1]
    monkeypatch.setattr(F.tempfile, "mkdtemp", mk)
    calls = []

    def run(fetch_rc=1, get_url=1):
        def f(cmd, **kw):
            calls.append(cmd)
            assert cmd[0] == "git" and kw.get("timeout") == F.C1W_PUB_TIMEOUT and kw["env"]["GIT_TERMINAL_PROMPT"] == "0"
            if cmd[1:3] == ["remote", "get-url"]:
                return subprocess.CompletedProcess(cmd, get_url, "https://github.com/o/r\n" if get_url == 0 else "", "")
            if cmd[1] == "fetch":
                if fetch_rc == "timeout":
                    raise subprocess.TimeoutExpired(cmd, F.C1W_PUB_TIMEOUT)
                return subprocess.CompletedProcess(cmd, fetch_rc, "", "fatal: unable to access 'https://u:secret@github.com/o/r/': 403")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return f
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert F.c1w_pub_git(D13, D20, TD, run=run())["fail"] == "url"
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    out = F.c1w_pub_git(D13, D20, TD, run=run())
    assert out["fail"] == "fetch" and "secret" not in out["err"] and "://***@github.com" in out["err"]
    fetch = next(c for c in calls if c[1] == "fetch")
    assert fetch[2:] == ["-q", "--no-tags", "--filter=blob:none", f"--depth={F.C1W_PUB_DEPTH}", "origin", "+refs/heads/data:refs/heads/data"]
    assert ["git", "remote", "add", "origin", "https://github.com/o/r"] in calls
    assert F.c1w_pub_git(D13, D20, TD, run=run("timeout", 0))["fail"] == "fetch"
    assert made and not any(os.path.exists(p) for p in made)


# ── 5. 그 주 앞 마지막 거래일에 최종본 목록 파일이 없으면 ──────────────────────────────────────────
def test_wkfrom_without_a_final_file_uses_the_published_close(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    kw, s, ref = _kw(file=True)
    assert kw["why"] == "file" and F.c1w_pub_need(kw) == "file"
    pub = pubs()
    kw2, got = F.c1w_pub_step(copy.deepcopy(kw), D20, TD, s, ref, reader=lambda *a: {"days": pub, "want": list(PUB_DAYS), "read": 4,
                                                                                         "commits": 9, "stop": "older"})
    assert got is not None and kw2["why"] is None and kw2["src"] == "pub" and kw2["pubSha"] == "sha13"
    assert kw2["close"]["005930"] == 206000.0 and kw2["shr"]["005930"] == 5846278608 and set(kw2["ref"].values()) == {"unknown"}
    assert "001570" not in kw2["close"]                              # 그날 거래 없음 → 쓰지 않아요 (그날 종가 없음 → 빈 칸)
    _s, nf, f20 = week_files()
    out = F.kr_c1w_rescue_step(kw2, D20, TD, s, f20, nf, None, {}, knx=KNX, daum={"v": 1, "days": [], "kk": {}}, pub=got)
    assert out["rescue"]["005930"] == ("pub", None) and "047400" not in out["rescue"]    # 유니온머티리얼: 11-13 거래 없음 → 그날 종가 없음
    st = [{"t": t, "nk": t, "cls": "kr", "price": 1.0, "shr": kw2["shr"].get(t, 1)} for t in ("005930", "000660", "047400", "001570")]
    meta, info = F.c1w_apply(st, out, None, HOL)
    assert [s_.get("c1w") for s_ in st] == [206000.0, 1216000.0, None, None]
    assert meta["wkFrom"] == "2026-11-13" and meta["c1wSrc"]["pub"] == 2 and meta["c1wSrc"]["blank"] == {"none": 2}
    F.log_c1w(info)
    assert any("국내 2 / 4 (wkFrom 2026-11-13 · 그날 최종본 목록 파일이 없어 지난 발행본 sha13 의 종가 (" in x for x in lines), lines
    # 그날 발행본도 없으면 예전처럼 한국 주식 모두 빈 칸 (크게)
    lines.clear()
    kw3, _p = F.c1w_pub_step(copy.deepcopy(kw), D20, TD, s, ref,
                             reader=lambda *a: {"days": pubs(days=PUB_DAYS[1:]), "want": ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18",
                                                                                       "2026-11-19"]})
    assert kw3["why"] == "file" and kw3["pubHist"]["need"] == "file"
    assert lines[-1].startswith("  !! c1w 지난 발행본 (data 브랜치 · 기준일마다 그날의 마지막 발행본 · 그 주 앞 마지막 거래일에 최종본 목록 파일이 없어요")
    assert "2026-11-13 발행본 없음 (그날 종가가 c1w 예요 · 한국 주식 c1w 모두 빈 칸)" in lines[-1]
    assert "2026-11-17 발행본 없음 (다음 거래일 발행본의 등락률로 그날 종가 범위 10종목)" in lines[-1]


# ── 6. 네이버는 지난 발행본에 없는 종목에만 ─────────────────────────────────────────────────
def _naver(codes):
    """네이버 일봉 대신 (시험용): 최종본 날은 공식 종가, 장중 파일 날은 그 파일의 값."""
    s, nf, f20 = week_files()
    nv = {c: {} for c in codes}
    for d, df in list(s) + [(D20, f20)]:
        for c, v in F._official_map(df).items():
            if c in nv:
                nv[c][d.isoformat()] = v
    for d, df in nf.items():
        for c, v in zip(df["Code"].astype(str).str.strip(), df["Close"]):
            if c in nv:
                nv[c][d.isoformat()] = float(v)
    return nv


def test_naver_only_for_stocks_missing_from_the_publishes():
    codes = ["005930", "000660", "005380"]
    nv = _naver(codes)

    def drop(d, js):                                             # 삼성전자가 11-18 발행본에 없고 11-19 발행본의 d1 도 없어요 (지난 발행본에 없는 날)
        if d == "2026-11-18":
            js["stocks"] = [x for x in js["stocks"] if x["t"] != "005930"]
        if d == "2026-11-19":
            _row(js, "005930").pop("d1")
            _row(js, "005930")["d1Why"] = "prev"
    res = rescue(pubs(drop), codes=codes, naver=nv)
    assert res["005930"][0] == "naver" and res["000660"] == ("pub", None) and res["005380"] == ("pub", None), res
    # 발행본에 다 있는데 그날 KRX 기준가가 없으면 네이버로 가지 않아요 (noBase) — 네이버 자료가 있어도
    s, nf, f20 = week_files()
    nf2 = dict(nf)
    nf2[D18] = nf[D18][nf[D18]["Code"] != "000660"]
    res2 = rescue(pubs(), codes=codes, naver=nv, nonfinal=nf2)
    assert res2["000660"] == ("blank", "noBase") and res2["005930"] == ("pub", None)
    # c1w_apply: 네이버로 확인한 행만 c1wv nv · c1wSrc 에 pub 와 naver
    kw = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {c: 100.0 for c in codes}, "shr": {c: 10 for c in codes},
          "ref": {c: "unknown" for c in codes}, "src": "listing", "rows": 3, "gap": ["2026-11-17"], "rescue": res, "pubHist": {"need": "gap"},
          "pubDiff": {}}
    st = [{"t": c, "nk": c, "cls": "kr", "price": 101.0, "shr": 10} for c in codes]
    meta, _info = F.c1w_apply(st, kw, None, HOL)
    assert [s_.get("c1wv") for s_ in st] == ["nv", None, None] and all(s_.get("c1w") == 100.0 for s_ in st)
    assert meta["c1wSrc"] == {"v": 1, "listing": 0, "krx": 0, "pub": 2, "naver": 1, "blank": {}, "link": {}}


# ── 7. 진짜 git · 관문 · 로그 ───────────────────────────────────────────────────────────────
def _git(*a, cwd=None, env=None):
    r = subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, capture_output=True,
                       text=True, env={**os.environ, **(env or {})}, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")
def test_reads_a_real_data_branch_through_a_partial_fetch(tmp_path):
    """이 폴더 밖 임시 저장소 (file://) 의 data 브랜치: 커밋 · 트리만 받고 data.json 은 필요한 커밋만. 기준일마다 마지막 발행본 · 11-12 커밋은 읽지
    않아요 (11-13 을 찾은 뒤 11-17 보다 앞 기준일이라 멈춤)."""
    src = tmp_path / "src"
    _git("init", "-q", "-b", "data", str(src))
    _git("config", "uploadpack.allowFilter", "true", cwd=src)
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=src)
    older = raw_pub("2026-11-19")
    _row(older, "005930")["price"] = 1.0
    seq = [("2026-11-13T07:00:00+09:00", {"pxDate": "2026-11-12", "listSrc": "fdr_krx_data_cache", "stocks": []}),
           ("2026-11-15T15:59:00+09:00", raw_pub("2026-11-13")), ("2026-11-17T06:40:00+09:00", raw_pub("2026-11-16")),
           ("2026-11-19T12:16:00+09:00", raw_pub("2026-11-18")), ("2026-11-20T06:40:00+09:00", older),
           ("2026-11-20T08:33:00+09:00", raw_pub("2026-11-19")), ("2026-11-21T06:41:00+09:00", raw_pub("2026-11-20"))]
    for when, js in seq:
        (src / "data.json").write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
        _git("add", "data.json", cwd=src)
        _git("commit", "-q", "-m", "데이터 갱신", cwd=src, env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
    out = F.c1w_pub_git(D13, D20, TD, url=(src.as_uri()), tmp=str(tmp_path / "dst"))
    assert out["fail"] is None and out["commits"] == 7, out
    assert sorted(out["days"]) == list(PUB_DAYS) and out["days"]["2026-11-19"]["close"]["005930"] == 196900.0
    assert out["read"] == 6 and out["stop"] == "older" and out["bytes"] > 0
    assert F.c1w_pub_git(D13, D20, TD, url=(tmp_path / "nope").as_uri(), tmp=str(tmp_path / "dst2"))["fail"] == "fetch"


def _gate_one(data, macro):
    rep = V.Report()
    V.check_v196e(rep, data, macro)
    r = [x for x in rep.rows if x[0] == V.C1W_ROW]
    assert len(r) == 1
    return r[0]


def test_gate_counts_published_closes():
    cur, _, _ = FD.good_pair()
    d = cur["data"]
    d["wkFrom"], d["usWkFrom"] = "2026-10-23", "2026-10-23"
    for s in d["stocks"]:
        if V.c1w_group(s) and not V.c1w_own_date(s):
            s["c1w"] = round(s["price"] / 1.01, 2)
    n = sum(1 for s in d["stocks"] if V.c1w_group(s) == "kr" and s.get("c1w") is not None)
    d["c1wSrc"] = {"v": 1, "listing": n - 300, "krx": 0, "pub": 300, "naver": 0, "blank": {}, "link": {}}
    r = _gate_one(d, cur["macro"])
    assert r[3] == "PASS" and f"(wkFrom 2026-10-23 · 목록 {n - 300:,} · KRX 0 · 지난 발행본 300 · 네이버 0)" in r[1], r
    d["c1wSrc"]["pub"] = 299
    r = _gate_one(d, cur["macro"])
    assert r[3] == "WARN" and f"c1wSrc (목록 {n - 300:,} + KRX 0 + 지난 발행본 299 + 네이버 0) 가 종목과 다름" in r[1], r
    d["c1wSrc"]["pub"] = "300"
    assert "c1wSrc 모양이 틀림" in _gate_one(d, cur["macro"])[1]


def test_logs_show_the_evidence_per_day(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    kw, s, ref = _kw()
    res = {"days": pubs(), "want": ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"], "read": 8, "bytes": 21_600_000,
           "commits": 28, "dup": 0, "stop": "older", "sec": 8.2, "fail": None, "unusable": {}, "bad": []}
    kw2, pub = F.c1w_pub_step(copy.deepcopy(kw), D20, TD, s, ref, reader=lambda *a: res)
    assert lines[-1] == ("· c1w 지난 발행본 (data 브랜치 · 기준일마다 그날의 마지막 발행본 · 그 주에 최종본 목록 파일이 없는 날이 있어요: 2026-11-17, "
                         "2026-11-18, 2026-11-19): 2026-11-13 sha13 10종목 (뺀 행 4) · 2026-11-16 sha16 11종목 (뺀 행 3) · 2026-11-17 발행본 없음 "
                         "(다음 거래일 발행본의 등락률로 그날 종가 범위 10종목) · 2026-11-18 sha18 10종목 (뺀 행 1) · 2026-11-19 sha19 10종목 (뺀 행 1) — "
                         "커밋 28개 · 읽은 발행본 8개 (data.json 21.6MB · 8.2s · 멈춤 older)"), lines[-1]
    _s, nf, f20 = week_files()
    out = F.kr_c1w_rescue_step(kw2, D20, TD, s, f20, nf, None, {}, knx=KNX, daum={"v": 1, "days": [], "kk": {}}, pub=pub)
    st = [{"t": c, "nk": c, "cls": "kr", "price": 1.0, "shr": out["shr"].get(c, 1)} for c in codes_of(f20)]
    meta, info = F.c1w_apply(st, out, None, HOL)
    assert meta["c1wSrc"]["pub"] == 9 and meta["c1wSrc"]["link"] == {"pxLink": 3}            # 바이오비쥬는 11-13 파일에 행이 없어요 (none)
    assert meta["c1wSrc"]["blank"] == {"none": 1, "base": 1, "link": 3}
    lines.clear()
    F.log_c1w(info)
    assert any("다른 자료로 확인해 실음 9 (KRX 기준가로 날마다 0 · 지난 발행본 종가와 KRX 기준가로 9 · 네이버 수정주가로 0)" in x for x in lines), lines
    assert any(x.startswith("· c1w 기준가 연결 자료: 장중 목록 파일 2026-11-17, 2026-11-18, 2026-11-19 · 지난 발행본 2026-11-13, 2026-11-16, "
                            "2026-11-18, 2026-11-19 · ") for x in lines), lines
    assert "· c1w 지난 발행본 종가 ↔ 같은 날 최종본 목록 파일: 다른 종목 0 (비움)" in lines
    json.dumps(meta, allow_nan=False)
