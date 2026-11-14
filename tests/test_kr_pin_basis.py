# -*- coding: utf-8 -*-
"""국내 시계열의 공식 종가 고정 기준 (2026-11-14 · Jack: "52주 숫자부터"). (네트워크 없음)

네이버 일봉은 수정주가예요 — 분할 · 병합 · 감자 · 무상증자가 있으면 그 앞 봉을 모두 새 기준으로 고쳐 둬요. 그런데 최근 19거래일을 그날 목록 파일의
공식 종가(그날 기준)로 덮어서, 기준이 바뀐 날 앞 봉에 옛 기준 값이 들어갔어요 (에쎈테크 · 인지디스플레 5:1 병합 → 52주 최저 591 · 726원,
STX 감자 뒤 기준가 3,530 → 18,360). fetch_data 는 이제 KRX 기준가(목록 파일의 Close − Changes)로 그날과 오늘이 같은 기준인지 보고
(kr_ref_links), 바뀐 날 앞은 고치지 않아요. 확인할 수 없는 날은 상장주식수(PIN_SHR_TOL)와 값 차이(PIN_PX_TOL)로만 (pin_why_not).
자기 점검(pin_audit) · 하루 가격 제한폭 넘는 움직임(kr_jumps) · 관문 줄(check_kr_series)도 여기서 봐요.

픽스처 tests/fixtures/kr_pin_samples.json 은 2026-11-14 (KST) 에 받은 실제 자료예요: 네이버 수정주가(FinanceDataReader) 마지막 270봉과
fdr_krx_data_cache 목록 파일의 그날 행(Marcap · Stocks · Market · Close · Changes) — 기준일 2026-11-13 과 그 앞 19거래일 · 그 기간 KOSPI 거래일."""
import collections
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
from fixture_data import good_pair  # noqa: E402
from test_validate import check, failed_names  # noqa: E402

with open(os.path.join(ROOT, "tests", "fixtures", "kr_pin_samples.json"), encoding="utf-8") as _f:
    FX = json.load(_f)
PXD = dt.date.fromisoformat(FX["pxDate"])
T = pd.Timestamp
TRADE = pd.to_datetime(FX["tradeDays"])


def ser(pairs):
    return pd.Series([float(v) for _, v in pairs], index=pd.to_datetime([d for d, _ in pairs]))


# ── 실제 자료에서 파이프라인과 같은 입력 만들기 ──────────────────
def frames(code, drop=()):
    """[(날짜, 목록 DataFrame)] 오늘 → 과거 (fetch_korea 가 kr_ref_links 에 주는 모양 · 이 종목 한 행씩). drop: 행을 뺄 날짜."""
    lst = FX["listing"][code]
    out = []
    for d in [FX["pxDate"]] + FX["sessions"]:
        r = lst.get(d)
        rows = [] if (r is None or d in drop) else [dict(r, Code=code, Name=code)]
        out.append((dt.date.fromisoformat(d), pd.DataFrame(rows, columns=["Code", "Name", "Close", "Changes", "Marcap", "Stocks", "Market"])))
    return out


def real(code):
    """(네이버 원래 시계열, 오늘 공식 종가, 오늘 주식 수, 시장, off_by_day, shr_by_day, ref_by_day) — fetch_korea 와 같은 모양."""
    lst = FX["listing"][code]
    now = lst[FX["pxDate"]]
    close = F.kr_official_close(now)
    off = {T(d): ({code: F.kr_official_close(lst[d])} if lst.get(d) else {}) for d in FX["sessions"]}
    shr = {T(d): ({code: float(lst[d]["Stocks"])} if lst.get(d) else {}) for d in FX["sessions"]}
    ref, _ = F.kr_ref_links(frames(code), TRADE, {code})
    return ser(FX["naver"][code]), close, float(now["Stocks"]), now["Market"], off, shr, ref


def pipeline(code):
    """fetch_korea 의 순서 그대로: pin_close → pin_recent(주식 수 · 기준가와 함께) → pin_audit → kr_jumps.
    반환: (시계열, 고친 수, 안 고친 이유, 점검, 움직임)."""
    raw0, close, shr_now, mkt, off, shr, ref = real(code)
    raw = F.cut_at(raw0, PXD)
    px, _ = F.pin_close(raw0, PXD, close)
    kept = collections.Counter()
    px, n = F.pin_recent(px, off, code, shr, shr_now, kept=kept, ref_by_day=ref)
    return (px, n, kept, F.pin_audit(raw, px, PXD, off, shr, shr_now, code, ref_by_day=ref),
            F.kr_jumps(px, raw, F.kr_day_limit(mkt)))


def old_pin(code):
    """2026-11-14 전의 고정 (모든 최근 거래일을 그날 공식 종가로) — 자기 점검과 움직임 검사가 이걸 잡아야 해요."""
    raw0, close, shr_now, mkt, off, shr, ref = real(code)
    raw = F.cut_at(raw0, PXD)
    px, _ = F.pin_close(raw0, PXD, close)
    px = px.copy()
    for ts, m in off.items():
        v = m.get(code)
        if v and ts in px.index:
            px.loc[ts] = v
    return raw, px, off, shr, shr_now, mkt, ref


def test_rule_values_are_the_safety_rule():
    """기준값은 관문 파일에 있고 파이프라인이 그대로 읽어요 (값을 바꾸면 Jack 의 승인이 필요해요 · 안전 규칙)."""
    assert (V.PIN_PX_TOL, V.PIN_SHR_TOL, V.PIN_REF_TOL, V.KR_DAY_LIMIT, V.KONEX_DAY_LIMIT) == (0.05, 0.02, 0.30, 30.0, 15.0)
    assert (F.PIN_PX_TOL, F.PIN_SHR_TOL, F.PIN_REF_TOL, F.KR_DAY_LIMIT, F.KONEX_DAY_LIMIT) == (
        V.PIN_PX_TOL, V.PIN_SHR_TOL, V.PIN_REF_TOL, V.KR_DAY_LIMIT, V.KONEX_DAY_LIMIT)
    assert V.KR_JUMP_WHY.keys() == {"pin", "halt", "spike", "other"} and F.KR_JUMP_WHY is V.KR_JUMP_WHY
    assert V.KR_DAY_LIMIT == V.D1_MAX_KR == F.D1_MAX_KR == 30.0              # 리뷰: 같은 제한폭이 세 곳에서 따로 바뀌지 않게
    assert F.kr_day_limit("KONEX") == 15.0 and F.kr_day_limit("KOSDAQ GLOBAL") == 30.0 and F.kr_day_limit(None) == 30.0


# ── 1. KRX 기준가 연결 (kr_ref_links) ───────────────────────────
@pytest.mark.parametrize("code, when, before, after", [
    ("043340", "2026-11-06", 591, 2955),       # 에쎈테크 5:1 병합 재상장
    ("037330", "2026-11-06", 726, 3630),       # 인지디스플레 5:1 병합 재상장
    ("011810", "2026-11-06", 3530, 18360),     # STX 거래정지 중 감자 · 기준가 재평가 (5.2배 — 깨끗한 배율이 아니어도 잡아요)
    ("058820", "2026-10-27", 562, 5620),       # CMG제약 10:1 병합
    ("052400", "2026-10-29", 33950, 22700),    # 코나아이 무상증자 권리락 (주식 수는 그대로)
    ("290650", "2026-10-26", 60000, 30150),    # 엘앤씨바이오 1:1 무상증자 권리락
    ("099520", "2026-10-21", None, None),      # DGI 권리락 (기준가 0.86배 · 주식 수 그대로)
])
def test_ref_links_find_every_basis_change_in_real_files(code, when, before, after):
    by_day, events = F.kr_ref_links(frames(code), TRADE, {code})
    assert [(c, d.isoformat()) for c, d, _, _ in events] == [(code, when)], events
    if before:
        assert events[0][2:] == (before, after)
    for d in FX["sessions"]:                                       # 그 날짜 앞 봉만 '다른 기준'
        assert by_day[T(d)][code] == ("break" if d < when else "ok"), d


@pytest.mark.parametrize("code", ["005930", "247540", "003220", "128540", "496320"])
def test_ref_links_ok_on_the_same_basis(code):
    """보통 날 · 주식 수만 바뀐 날(에코프로비엠 +9%) · 시간외 큰 움직임 날(대원제약 · 에코캡) · 거래 드문 코넥스: 기준가가 이어져요."""
    by_day, events = F.kr_ref_links(frames(code), TRADE, {code})
    assert events == [] and {by_day[T(d)][code] for d in FX["sessions"]} == {"ok"}


def test_ref_links_unknown_when_a_link_cannot_be_checked():
    """빠진 행 · Changes 칸이 없는 파일 · 사이에 빠진 거래일(최종본이 아니라 건너뛴 날)은 '확인 못 함' — 그 앞 날짜는 모두 unknown."""
    code = "005930"
    by_day, _ = F.kr_ref_links(frames(code, drop=("2026-11-05",)), TRADE, {code})
    assert by_day[T("2026-11-06")][code] == "ok" and by_day[T("2026-11-05")][code] == "unknown" and by_day[T("2026-11-04")][code] == "unknown"
    fr = frames(code)
    fr[3] = (fr[3][0], fr[3][1].drop(columns=["Changes"]))         # 11-10 파일에 Changes 칸이 없음
    by_day, _ = F.kr_ref_links(fr, TRADE, {code})
    assert by_day[T("2026-11-10")][code] == "ok" and by_day[T("2026-11-09")][code] == "unknown"
    fr = [x for x in frames(code) if x[0].isoformat() != "2026-11-11"]   # 11-11 파일을 건너뜀 (KOSPI 는 거래일)
    by_day, _ = F.kr_ref_links(fr, TRADE, {code})
    assert by_day[T("2026-11-12")][code] == "ok" and by_day[T("2026-11-10")][code] == "unknown"
    assert F.kr_ref_links([], TRADE, {code}) == ({}, [])


@pytest.mark.parametrize("code, listed", [("0013Y0", "2026-10-22"), ("493410", "2026-11-12")])
def test_ref_links_new_listing_is_its_own_quiet_state(code, listed, capsys):
    """리뷰 S1: 이 기간에 새로 상장한 종목 (엠에스바이오 10-22 · 넥스아이 11-12, 실제 목록 파일)은 상장 앞 파일에 행이 없어요. 'unknown'(크게 남김)이
    아니라 'new' — 상장 앞 날은 공식 종가가 없어 고칠 봉도 없고, 상장 뒤 날은 기준가 연결대로 ('ok'). 로그는 보통 줄 · krSeries.ref.newStocks 로 세요."""
    by_day, events = F.kr_ref_links(frames(code), TRADE, {code})
    assert events == []
    for d in FX["sessions"]:
        assert by_day[T(d)][code] == ("ok" if d >= listed else "new"), d
    got = F.log_ref_links(by_day, events, {code: "새 종목"}, len(FX["sessions"]))
    assert got == {"breakStocks": 0, "unknownStocks": 0, "newStocks": 1}
    line = capsys.readouterr().out.strip()
    assert line.startswith("· KRX 기준가 연결") and "새로 상장한 종목 1 (" + code + " 새 종목" in line and "!!" not in line
    px, n, kept, bad, jumps = pipeline(code)                          # 상장 뒤 날은 보통처럼 공식 종가로 · 어긋남 0
    assert bad == [] and not kept
    raw0, close, shr_now, mkt, off, shr, ref = real(code)
    assert all(float(px.loc[ts]) == m[code] for ts, m in off.items() if m.get(code) and ts in px.index)
    assert F.pin_why_not(591.0, 2955.0, 47_500_000, 9_500_000, "new") == "basis"     # 'new' 는 확인 못 한 날처럼 (주식 수 · 값 둘 다)
    assert F.pin_why_not(100.0, 130.0, 1_000, 1_000, "new") == "far"


def test_ref_log_is_loud_only_for_unknown_or_too_many_changes(capsys):
    """기준가를 확인 못 한 종목이 있거나 기준가가 새로 정해진 종목이 REF_EVENTS_LOUD 보다 많으면 크게 (종목 수로 세요 · 한 종목에 여러 번이어도 하나)."""
    d1, d2 = T("2026-11-11"), T("2026-11-12")
    assert F.log_ref_links({d1: {"A": "unknown", "B": "ok"}, d2: {"A": "ok", "B": "ok"}}, [], {}, 2)["unknownStocks"] == 1
    assert capsys.readouterr().out.startswith("  !! KRX 기준가 연결")
    many = [(f"{i:06d}", dt.date(2026, 11, 12), 100.0, 200.0) for i in range(F.REF_EVENTS_LOUD)] * 3   # 100종목 · 300건 → 크지 않음
    got = F.log_ref_links({d1: {}}, many, {}, 2)
    out = capsys.readouterr().out
    assert got["breakStocks"] == F.REF_EVENTS_LOUD and out.startswith("· ") and f"{F.REF_EVENTS_LOUD} (300건)" in out
    F.log_ref_links({d1: {}}, many + [("999999", dt.date(2026, 11, 12), 100.0, 200.0)], {}, 2)
    assert capsys.readouterr().out.startswith("  !! ")
    assert F.log_ref_links({}, [], {}, 0) == {"breakStocks": 0, "unknownStocks": 0, "newStocks": 0}


def test_ref_links_break_beats_unknown():
    """기준가가 바뀐 날과 확인 못 한 연결이 함께 있으면 '다른 기준'으로 (가장 나쁜 쪽)."""
    code = "043340"
    by_day, _ = F.kr_ref_links(frames(code, drop=("2026-11-10",)), TRADE, {code})
    assert by_day[T("2026-11-09")][code] == "unknown" and by_day[T("2026-11-05")][code] == "break"


# ── 2. 고정 규칙 (pin_why_not · pin_recent) ─────────────────────
@pytest.mark.parametrize("case, off, bar, shr_day, shr_now, link, want", [
    ("5:1 병합 (주식 수 ×0.2) — 그날 591원 · 네이버 수정주가 2,955원", 591.0, 2955.0, 47_500_000, 9_500_000, "break", "basis"),
    ("같은 병합 · 기준가를 확인 못 한 날 — 주식 수가 막아요", 591.0, 2955.0, 47_500_000, 9_500_000, "unknown", "basis"),
    ("2:1 액면분할 (주식 수 ×2) — 그날 100,000원 · 네이버 50,000원", 100_000.0, 50_000.0, 1_000_000, 2_000_000, "unknown", "basis"),
    ("STX: 거래정지 중 감자 · 기준가 3,530 → 18,360 (주식 수 31.0M → 28.7M)", 3530.0, 18360.0, 31_017_927, 28_665_787, "unknown", "basis"),
    ("기준가가 바뀌었으면 값이 같아 보여도 고치지 않아요", 100.0, 100.0, 1_000, 1_000, "break", "basis"),
    ("전환사채 전환으로 주식 수 +1% · 넥스트레이드 차이 3% — 같은 기준이라 고쳐요 (확인 못 함)", 103.0, 100.0, 99_000_000, 100_000_000, "unknown", None),
    ("전환사채 전환 +1% · 3% (기준가 확인)", 103.0, 100.0, 99_000_000, 100_000_000, "ok", None),
    ("보통 날 (주식 수 같음 · 0.5% 차이)", 201_500.0, 200_500.0, 5_846_278_608, 5_846_278_608, "ok", None),
    ("무상증자 권리락 뒤 새 주식 상장 전 (주식 수 같음 · 1.5배) — 코나아이, 확인 못 한 날", 33_950.0, 22_634.0, 14_243_291, 14_243_291, "unknown", "far"),
    ("시간외 큰 움직임 하루 (주식 수 같음 · 20%) — 기준가 확인: 공식 종가로", 7_980.0, 9_975.0, 1_000, 1_000, "ok", None),
    ("시간외 큰 움직임 하루 (20%) — 확인 못 함: 네이버 그대로", 7_980.0, 9_975.0, 1_000, 1_000, "unknown", "far"),
    ("기준가 확인 · 주식 수 9% 다름 · 값 1% — 고쳐요 (에코프로비엠)", 101.0, 100.0, 910, 1_000, "ok", None),
    ("기준가 확인 · 주식 수 9% 다름 · 값 8% — 고치지 않아요", 108.0, 100.0, 910, 1_000, "ok", "far"),
    ("기준가 확인 · 31% 차이 — 고치지 않아요", 131.0, 100.0, 1_000, 1_000, "ok", "far"),
    ("기준가 확인 · 주식 수 모름 · 값 4% — 고쳐요", 104.0, 100.0, None, None, "ok", None),
    ("그날 주식 수 모름 (확인 못 함)", 100.0, 100.5, None, 1_000, "unknown", "shr"),
    ("오늘 주식 수 모름 (확인 못 함)", 100.0, 100.5, 1_000, 0, "unknown", "shr"),
    ("주식 수 차이 1.9% · 값 4.9% (둘 다 안)", 104.9, 100.0, 1_019, 1_000, "unknown", None),
    ("주식 수 차이 2.1% (밖)", 100.0, 100.0, 1_021, 1_000, "unknown", "basis"),
    ("값 차이 5.1% (밖)", 105.1, 100.0, 1_000, 1_000, "unknown", "far"),
])
def test_pin_why_not(case, off, bar, shr_day, shr_now, link, want):
    assert F.pin_why_not(off, bar, shr_day, shr_now, link) == want, case


def test_pin_why_not_defaults_to_unknown():
    assert F.pin_why_not(591.0, 2955.0, 47_500_000, 9_500_000) == "basis"
    assert F.pin_why_not(103.0, 100.0, 99_000_000, 100_000_000) is None


def test_pin_recent_keeps_naver_on_a_different_basis():
    """5:1 병합: 병합 앞 날(기준가가 바뀌기 전)은 네이버 수정주가 그대로, 뒤 날은 공식 종가로. 고치지 않은 날은 이유별로 세요."""
    d = pd.to_datetime(["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09"])
    px = pd.Series([2955.0, 2955.0, 2410.0, 2300.0], index=d)
    off = {d[0]: {"X": 591.0}, d[1]: {"X": 591.0}, d[2]: {"X": 2400.0}, d[3]: {"X": 2300.0}}
    shr = {d[0]: {"X": 47_500_000}, d[1]: {"X": 47_500_000}, d[2]: {"X": 9_500_000}, d[3]: {"X": 9_500_000}}
    ref = {d[0]: {"X": "break"}, d[1]: {"X": "break"}, d[2]: {"X": "ok"}, d[3]: {"X": "ok"}}
    kept = collections.Counter()
    got, n = F.pin_recent(px, off, "X", shr, 9_500_000, kept=kept, ref_by_day=ref)
    assert list(got) == [2955.0, 2955.0, 2400.0, 2300.0] and n == 1 and kept == {"basis": 2}
    assert list(px) == [2955.0, 2955.0, 2410.0, 2300.0]                     # 원본은 그대로
    kept = collections.Counter()                                             # 기준가를 확인 못 해도 주식 수가 막아요
    got, n = F.pin_recent(px, off, "X", shr, 9_500_000, kept=kept)
    assert list(got) == [2955.0, 2955.0, 2400.0, 2300.0] and kept == {"basis": 2}


def test_pin_recent_without_basis_information_still_blocks_a_far_close():
    """주식 수도 기준가도 주지 않으면 값 기준만: 3.9% 차이(넥스트레이드)는 고치고, 5배 차이(병합 앞 날)는 고치지 않아요."""
    d = pd.to_datetime(["2026-10-27", "2026-10-28"])
    px = pd.Series([181_400.0, 2955.0], index=d)
    kept = collections.Counter()
    got, n = F.pin_recent(px, {d[0]: {"X": 174_300.0}, d[1]: {"X": 591.0}}, "X", kept=kept)
    assert n == 1 and list(got) == [174_300.0, 2955.0] and kept == {"far": 1}


@pytest.mark.parametrize("code", ["043340", "037330", "011810", "058820"])
def test_real_consolidations_are_not_pinned_on_the_old_basis(code):
    """실제 자료: 병합 · 감자 앞 날의 공식 종가(옛 기준)는 들어가지 않고, 뒤 날은 모두 공식 종가예요."""
    px, n, kept, bad, jumps = pipeline(code)
    raw0, close, shr_now, mkt, off, shr, ref = real(code)
    assert bad == [] and jumps == [], (bad, jumps)
    assert kept["basis"] >= 6 and set(kept) == {"basis"}, kept
    for ts, m in off.items():
        if ts in px.index:
            want = m[code] if ref[ts][code] == "ok" else float(raw0.loc[ts])
            assert float(px.loc[ts]) == want, ts


def test_real_named_stocks_52_week_low():
    """세 종목의 52주 최저: 예전 591 · 726 · 3,530 (옛 기준 공식 종가) → 수정주가 기준."""
    want = {"043340": (2300.0, 591.0), "037330": (2940.0, 726.0), "011810": (18360.0, 3530.0)}
    for code, (lo, old_lo) in want.items():
        assert float(pipeline(code)[0].tail(252).min()) == lo, code
        assert float(old_pin(code)[1].tail(252).min()) == old_lo, code     # 예전 고정이 만든 값 (고치기 전 사이트의 숫자)


def test_real_bonus_issue_before_new_shares_list():
    """코나아이: 무상증자 권리락(10-29) 뒤 새 주식이 아직 상장 전이라 주식 수는 같아요 — 주식 수만 보면 1.5배 옛 기준 값을 넣었을 거예요.
    기준가가 막아요 (확인 못 한 날이었다면 값 기준 PIN_PX_TOL 이). 엘앤씨바이오(1:1, 새 주식 11-13 상장) · DGI(0.86배)도 같아요."""
    for code, n_before in (("052400", 8), ("290650", 5), ("099520", 2)):
        px, n, kept, bad, jumps = pipeline(code)
        assert kept == {"basis": n_before} and bad == [] and jumps == [], (code, kept)
        raw0, close, shr_now, mkt, off, shr, ref = real(code)
        first = T(FX["sessions"][-1])
        assert float(px.loc[first]) == float(raw0.loc[first])               # 네이버 수정주가 그대로
        assert F.pin_why_not(off[first][code], float(raw0.loc[first]), shr[first][code], shr_now, "unknown") in ("far", "basis")
    assert float(pipeline("290650")[0].tail(252).max()) < 60_000            # 예전: 66,800 (옛 기준 공식 종가)


def test_real_same_basis_days_are_pinned_even_with_a_share_change_or_a_big_after_hours_day():
    """기준가가 이어지면: 에코프로비엠(주식 수 +9%, 값 1% 안) · 대원제약(10-29 시간외 20%) · 에코캡(11-04 공식 472 · 네이버 555) 도 공식 종가로.
    에코캡의 52주 최저는 공식 종가 472원이에요 (네이버 봉 그대로 두면 555원)."""
    for code in ("247540", "003220", "128540", "005930"):
        px, n, kept, bad, jumps = pipeline(code)
        raw0, close, shr_now, mkt, off, shr, ref = real(code)
        assert not kept and bad == [] and jumps == [], (code, kept)
        assert all(float(px.loc[ts]) == m[code] for ts, m in off.items() if ts in px.index), code
    assert float(pipeline("128540")[0].tail(252).min()) == 472.0


def test_real_konex_stock_with_15_percent_steps_is_not_an_artefact():
    """본시스템즈 (코넥스): 17,500 → 1,176,000 원은 상한가 15% 로만 오른 진짜 기록이에요 (거래가 드물어요). 움직임 검사에 걸리지 않아요."""
    px, n, kept, bad, jumps = pipeline("496320")
    assert jumps == [] and bad == [] and real("496320")[3] == "KONEX"
    assert float(px.pct_change().abs().max()) <= 0.1500001


# ── 3. 자기 점검 (pin_audit) ────────────────────────────────────
@pytest.mark.parametrize("code", ["043340", "037330", "011810", "058820", "052400", "290650", "099520"])
def test_audit_catches_the_old_pinning(code):
    """must-fail: 예전 고정을 실제 자료에 돌리면 자기 점검이 잡아요 (관문 실패 줄의 근거)."""
    raw, old, off, shr, shr_now, mkt, ref = old_pin(code)
    bad = F.pin_audit(raw, old, PXD, off, shr, shr_now, code, ref_by_day=ref)
    assert bad and {w for _, w in bad} == {"basis"}, bad


def test_audit_rules():
    d = pd.to_datetime(["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"])
    raw = pd.Series([100.0, 100.0, 100.0, 100.0], index=d)
    off = {d[0]: {"X": 101.0}, d[1]: {"X": 50.0}, d[2]: {"X": 102.0}}
    shr = {d[0]: {"X": 1000}, d[1]: {"X": 1000}, d[2]: {"X": 1100}}
    pxd = d[3].date()
    ok = pd.Series([101.0, 100.0, 100.0, 97.0], index=d)                        # 허락된 고정 하나 · 기준일 봉(97)은 보지 않아요
    assert F.pin_audit(raw, ok, pxd, off, shr, 1000, "X") == []
    far = ok.copy(); far.iloc[1] = 50.0                                          # 같은 주식 수인데 2배 차이
    assert F.pin_audit(raw, far, pxd, off, shr, 1000, "X") == [(d[1], "far")]
    basis = ok.copy(); basis.iloc[2] = 102.0                                     # 그날 주식 수 10% 다름 (기준가 확인 못 함)
    assert F.pin_audit(raw, basis, pxd, off, shr, 1000, "X") == [(d[2], "basis")]
    assert F.pin_audit(raw, basis, pxd, off, shr, 1000, "X", ref_by_day={d[2]: {"X": "ok"}}) == []   # 기준가로 같은 기준 · 2% 차이
    assert F.pin_audit(raw, ok, pxd, off, shr, 1000, "X", ref_by_day={d[0]: {"X": "break"}}) == [(d[0], "basis")]
    odd = ok.copy(); odd.iloc[2] = 100.5                                         # 공식 종가가 아닌 값으로 바뀜
    assert F.pin_audit(raw, odd, pxd, off, shr, 1000, "X") == [(d[2], "notOfficial")]
    assert F.pin_audit(raw, ok.drop(d[1]), pxd, off, shr, 1000, "X") == [(d[1], "dropped")]
    extra = pd.concat([ok, pd.Series([100.0], index=[T("2026-11-09")])]).sort_index()
    assert F.pin_audit(raw, extra, pxd, off, shr, 1000, "X") == [(T("2026-11-09"), "added")]
    assert F.pin_audit(raw, ok, pxd, off, shr, None, "X") == [(d[0], "shr")]     # 오늘 주식 수를 모르고 기준가도 모르면 고친 봉은 어긋남


# ── 4. 하루 가격 제한폭 넘는 움직임 (kr_jumps) ─────────────────
def bars(vals, start="2026-01-02"):
    return pd.Series([float(v) for v in vals], index=pd.bdate_range(start, periods=len(vals)))


def test_jump_bounds_allow_the_limit_plus_one_nextrade_bar():
    lo, hi = F.jump_bounds(30.0)
    assert round(lo * 100, 1) == -33.3 and round(hi * 100, 1) == 36.8
    lo, hi = F.jump_bounds(15.0)
    assert round(lo * 100, 1) == -19.0 and round(hi * 100, 1) == 21.1


def test_jumps_ordinary_and_limit_moves_pass():
    px = bars([1000, 1300, 1690, 1183, 1190])                                    # 상한가 두 번 · 하한가 한 번
    assert F.kr_jumps(px, px, 30.0) == []
    px = bars([1000, 1340])                                                       # 34% — 앞 봉이 넥스트레이드 가격이면 생겨요
    assert F.kr_jumps(px, px, 30.0) == []
    assert F.kr_jumps(bars([5]), bars([5]), 30.0) == [] and F.kr_jumps(bars([]), bars([]), 30.0) == []


def test_jumps_konex_limit_is_15_percent():
    px = bars([1000, 1250, 1260])
    assert F.kr_jumps(px, px, 30.0) == []
    assert [(p, w) for _, p, w in F.kr_jumps(px, px, F.kr_day_limit("KONEX"))] == [(25.0, "other")]


def test_jump_causes():
    raw = bars([2955] * 6 + [2400, 2300, 2300, 2435])
    pinned = raw.copy(); pinned.iloc[2:6] = 591.0                                # 예전 고정: 병합 앞 날에 옛 기준 값
    got = F.kr_jumps(pinned, raw, 30.0)
    assert [(p, w) for _, p, w in got] == [(-80.0, "pin"), (306.1, "pin")]
    halt = bars([900, 904, 904, 904, 904, 1808, 1808])                            # 같은 값 이어짐(거래 없음) 뒤 재개
    assert [(p, w) for _, p, w in F.kr_jumps(halt, halt, 15.0)] == [(100.0, "halt")]
    gap = pd.Series([100.0, 400.0], index=pd.to_datetime(["2026-01-02", "2026-03-02"]))   # 네이버에 빈 날이 있는 정지
    assert [w for _, _, w in F.kr_jumps(gap, gap, 30.0)] == ["halt"]
    spike = bars([26500, 26600, 51600, 25100, 25200])                            # 하루만 튄 봉 (티이엠씨 2023-12-28)
    assert [(p, w) for _, p, w in F.kr_jumps(spike, spike, 30.0)] == [(94.0, "spike"), (-51.4, "spike")]
    other = bars([27500, 27950, 14350, 14580])                                   # 고치지 않은 사건 (진코스텍 2026-10-15)
    assert [(p, w) for _, p, w in F.kr_jumps(other, other, 30.0)] == [(-48.7, "other")]


@pytest.mark.parametrize("code", ["043340", "037330", "011810", "058820", "052400", "290650"])
def test_jumps_catch_the_old_pinning_independently(code):
    """움직임 검사는 기준가 · 주식 수를 보지 않고 네이버 원래 시계열만 봐요 — 예전 고정의 큰 기준 차이를 따로 잡아요 (경고 줄)."""
    raw, old, off, shr, shr_now, mkt, ref = old_pin(code)
    assert {w for _, _, w in F.kr_jumps(old, raw, F.kr_day_limit(mkt))} == {"pin"}


# ── 5. 파이프라인 → 관문 (krSeries) ─────────────────────────────
def series_check(bad=(), jumps=(), published=("043340", "011810", "107640")):
    pin = collections.Counter({"recent_fixed": 39613, "recent_stocks": 2318})
    kept = collections.Counter({"basis": 157, "far": 8})
    names = {"043340": ("에쎈테크", {"basis": 14})}
    return F.kr_series_check(pin, kept, names, list(bad), list(jumps), set(published), 19,
                             ref={"breakStocks": 18, "unknownStocks": 0, "newStocks": 14})


def test_series_check_shape_is_what_the_gate_reads():
    ks = series_check(jumps=[("107640", "한중엔시에스", [(T("2024-06-24"), -38.2, "spike")]),
                             ("999990", "발행 안 함", [(T("2025-01-02"), 99.0, "other")])])
    assert V.kr_series_problems(ks, PXD) == []
    assert ks["bad"] == 0 and ks["badStocks"] == [] and ks["jump"] == [["107640", "2024-06-24", -38.2, "spike"]]   # 발행하는 종목만
    assert ks["kept"] == {"basis": 157, "far": 8, "shr": 0} and ks["pinned"] == 39613 and ks["days"] == 19
    assert ks["ref"] == {"breakStocks": 18, "unknownStocks": 0, "newStocks": 14}
    json.dumps(ks, allow_nan=False)
    ks = series_check(bad=[("043340", "에쎈테크", [(T("2026-11-05"), "basis"), (T("2026-11-04"), "basis")])])
    assert ks["bad"] == 2 and ks["badStocks"] == ["043340"] and V.kr_series_problems(ks) == []


def test_fetch_korea_uses_the_checked_pin_for_every_number():
    """fetch_korea: 주식 수 · 기준가와 함께 고치고, 자기 점검과 움직임 검사를 같은 시계열로 돌리고, 결과를 data.json 에 실어요.
    (52주 · 변동성 · 베타 · 알파 · 낙폭 · 수익률 · 모멘텀은 모두 그 뒤의 px 하나로 계산해요)"""
    src = inspect.getsource(F.fetch_korea)
    i_ref = src.index('kr_ref_links([(px_date, listing)] + sessions, ks_all.index, set(listing["Code"]))')
    i_clean = src.index("px, glitch = naver_clean(px)")
    assert i_ref < i_clean < src.index("raw = cut_at(px, px_date)") < src.index("px, how = pin_close(px, px_date, close)")
    assert src.index("log_naver_clean(naver_bad)") < src.index("krs = kr_series_check(")
    i_pin = src.index("pin_recent(px, off_by_day, code, shr_by_day, shr_now.get(code), kept=kc, ref_by_day=ref_by_day)")
    i_audit = src.index("pin_audit(raw, px, px_date, off_by_day, shr_by_day, shr_now.get(code), code, ref_by_day=ref_by_day)")
    i_jump = src.index('kr_jumps(px, raw, kr_day_limit(row.get("Market")))')
    i_ret = src.index("ret = px.pct_change().dropna()")
    assert i_ref < i_pin < i_audit < i_jump < i_ret
    for use in ('"lo": float(px.tail(252).min())', '"hi": float(px.tail(252).max())', "hilo_note(code, px, rec)",
                "rec.update(perf_stats(px, rf))", 'rec["r1"] = round(float(px.iloc[-1] / px.iloc[-22] - 1) * 100, 1)'):
        assert src.rindex(use) > i_ret, use                                      # 마지막(쓰는 곳) — hilo_note 는 위에 정의도 있어요
    assert src.count("pin_recent(") == 1 and src.count("pin_close(") == 1
    assert '"krSeries": kmeta.get("krSeries")' in inspect.getsource(F.main)


# ── 6. 관문 줄 (check_kr_series) ────────────────────────────────
NAME = "국내 시계열 공식 종가 고정 자기 점검 (krSeries.bad)"
JNAME = "국내 시계열 하루 가격 제한폭 넘는 움직임 (경고만)"


def with_series(files, **kw):
    ks = {"v": 1, "days": 19, "pinned": 39613, "pinStocks": 2318, "kept": {"basis": 157, "far": 8, "shr": 0}, "keptStocks": 23,
          "bad": 0, "badStocks": [], "ref": {"breakStocks": 18, "unknownStocks": 0, "newStocks": 14}, "jump": []}
    ks.update(kw)
    files["data"]["krSeries"] = ks
    return files


def row(rep, name):
    return next(r for r in rep.rows if r[0] == name)


def test_gate_good_series_passes_both_rows():
    cur, prev, final = good_pair()
    with_series(cur), with_series(prev)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert row(rep, NAME)[3] == "PASS" and row(rep, JNAME)[3] == "PASS"
    assert row(rep, NAME)[1].startswith("걸린 봉 0 · 최근 19거래일 고친 봉 39613 (2318종목) · 기준가가 바뀐 종목 18 · 확인 못 한 종목 0 · "
                                        "새로 상장 14")


def test_gate_fails_when_a_pin_was_written_on_another_basis():
    """must-fail: 자기 점검에 걸린 봉이 있으면 (우리 코드가 다른 기준의 공식 종가를 넣음) 발행하지 않아요."""
    cur, prev, final = good_pair()
    with_series(cur, bad=14, badStocks=["005930"]), with_series(prev)
    rep = check(cur, prev, final)
    assert failed_names(rep) == {NAME}, rep.table()
    assert "걸린 봉 14 (005930 삼성전자)" in row(rep, NAME)[1]
    assert any(t.startswith("공식 종가 고정 자기 점검에 걸린") for t, _ in rep.details)


@pytest.mark.parametrize("change", [
    {"v": 2}, {"bad": True}, {"bad": -1}, {"bad": 1.0}, {"pinned": None}, {"kept": {"basis": 1, "far": 2}},
    {"kept": {"basis": 1, "far": 2, "shr": -1}}, {"badStocks": "005930"}, {"bad": 0, "badStocks": ["005930"]},
    {"bad": 2, "badStocks": []}, {"bad": 1, "badStocks": ["005930", "000660"]}, {"ref": None}, {"ref": {"breakStocks": 1}},
    {"ref": {"breakStocks": 1, "unknownStocks": 0}}, {"ref": {"breakStocks": 1, "unknownStocks": "0", "newStocks": 0}},
    {"ref": {"breakStocks": 1, "unknownStocks": 0, "newStocks": -2}}, {"jump": "없음"},
    {"jump": [["005930", "2026-10-30", 50.0, "naver"]]}, {"jump": [["005930", "2026-10-31", 50.0, "other"]]},
    {"jump": [["005930", "어제", 50.0, "other"]]}, {"jump": [["005930", "2026-10-29", "큼", "other"]]}, {"jump": [["005930", "2026-10-29", 50.0]]},
])
def test_gate_fails_on_a_wrong_shape(change):
    cur, prev, final = good_pair()
    with_series(cur, **change), with_series(prev)
    assert NAME in failed_names(check(cur, prev, final))


def test_gate_missing_record():
    """krSeries 가 없어요: 직전 발행본에 있었으면 실패 (점검이 돌지 않았어요) · 직전에도 없으면 (그 전 형식) 경고만."""
    cur, prev, final = good_pair()
    with_series(prev)
    rep = check(cur, prev, final)
    assert failed_names(rep) == {NAME}, rep.table()
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "WARN" and row(rep, JNAME)[3] == "WARN"


def test_gate_warns_and_names_beyond_limit_moves_but_publishes():
    """네이버 자체의 움직임 (고치지 않은 감자 · 하루만 튄 봉): 한 종목의 출처 문제로 모두의 발행을 막지 않아요 (Jack 2026-11-13) — 경고와 이름만."""
    cur, prev, final = good_pair()
    with_series(cur, jump=[["000660", "2026-05-08", 1446.1, "halt"], ["005930", "2023-12-28", 94.7, "spike"],
                           ["005930", "2024-01-02", -51.4, "spike"]])
    with_series(prev)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    r = row(rep, JNAME)
    assert r[3] == "WARN" and r[1].startswith("2종목: 000660 SK하이닉스 (2026-05-08 +1446.1% 거래정지 뒤 재개), 005930 삼성전자 "
                                               "(2023-12-28 +94.7% 하루만 튄 봉 · 2024-01-02 -51.4% 하루만 튄 봉)"), r


def test_gate_live_mode_reads_the_record_without_the_previous_publish():
    cur, prev, final = good_pair()
    with_series(cur, bad=3, badStocks=["005930"])
    assert NAME in failed_names(check(cur, None, final, mode="live"))
    cur, prev, final = good_pair()
    with_series(cur)
    assert not check(cur, None, final, mode="live").failed


# ── 7. 네이버 시계열의 같은 날짜 · 잘못된 값 (리뷰 S2) ─────────────
def test_naver_clean_rules():
    d = list(pd.bdate_range("2026-01-02", periods=6))
    same = pd.Series([1.0, 2, 3, 4, 5, 6, 3.0], index=pd.DatetimeIndex(d + [d[2]]))
    got, probs = F.naver_clean(same)                                 # 같은 값으로 두 번 → 하나만, 문제 아님
    assert list(got.index) == d and list(got) == [1, 2, 3, 4, 5, 6] and probs == []
    diff = pd.Series([1.0, 2, 3, 4, 5, 6, 3.5], index=pd.DatetimeIndex(d + [d[2]]))
    got, probs = F.naver_clean(diff)                                 # 다른 값으로 두 번 → 그 날짜를 빼요 (둘 다 믿지 않아요)
    assert list(got.index) == d[:2] + d[3:] and probs == [(d[2], "dup", [3.0, 3.5])]
    odd = pd.Series([1.0, float("inf"), 0.0, -1.0, 5.0, float("nan")], index=pd.DatetimeIndex(d))
    got, probs = F.naver_clean(odd)
    assert list(got) == [1.0, 5.0] and [(t, w) for t, w, _ in probs] == [(d[1], "bad"), (d[2], "bad"), (d[3], "bad"), (d[5], "bad")]
    back = pd.Series([4.0, 5.0, 6.0, 1.0, 2.0, 3.0], index=pd.DatetimeIndex(d[3:] + d[:3]))
    got, probs = F.naver_clean(back)                                 # 순서가 뒤섞여도 날짜 순으로
    assert list(got) == [1, 2, 3, 4, 5, 6] and probs == []
    clean = pd.Series([1.0, 2.0], index=pd.DatetimeIndex(d[:2]))
    got, probs = F.naver_clean(clean)
    assert got.equals(clean) and probs == []


def run_one(raw0, pxd, close, off, shr, shr_now, ref, code="X"):
    """fetch_korea.one() 의 순서 (naver_clean → pin_close → pin_recent → pin_audit → kr_jumps)."""
    px, glitch = F.naver_clean(raw0)
    raw = F.cut_at(px, pxd)
    px, _ = F.pin_close(px, pxd, close)
    px, n = F.pin_recent(px, off, code, shr, shr_now, kept=collections.Counter(), ref_by_day=ref)
    return px, glitch, F.pin_audit(raw, px, pxd, off, shr, shr_now, code, ref_by_day=ref), F.kr_jumps(px, raw, 30.0)


@pytest.mark.parametrize("dup_day", [9, 77, 78])
def test_naver_duplicate_date_never_fails_the_gate(dup_day, capsys):
    """리뷰 S2 재현: 80 봉 중 한 날짜가 1,500 과 1,009 로 두 번 (오래된 봉 · 고치는 날 · 기준일 바로 앞). 예전에는 자기 점검이 notOfficial 로 잡아
    관문이 모두의 발행을 막거나 (Jack 2026-11-13 규칙과 어긋남) 움직임 검사에서 TypeError 로 종목이 빠졌어요. 이제 그 날짜를 빼고 계산하고,
    크게 이름과 함께 남기고, 자기 점검 0 · 관문 통과."""
    d = list(pd.bdate_range("2026-01-02", periods=80))
    vals = [1000.0 + i for i in range(80)]
    raw0 = pd.Series(vals[:dup_day + 1] + [1500.0] + vals[dup_day + 1:], index=pd.DatetimeIndex(d[:dup_day + 1] + [d[dup_day]] + d[dup_day + 1:]))
    pxd = d[-1].date()
    off = {d[-3]: {"X": 1077.0}, d[-2]: {"X": 1078.0}}
    shr = {d[-3]: {"X": 1000}, d[-2]: {"X": 1000}}
    ref = {d[-3]: {"X": "ok"}, d[-2]: {"X": "ok"}}
    px, glitch, bad, jumps = run_one(raw0, pxd, 1079.0, off, shr, 1000, ref)
    assert glitch == [(d[dup_day], "dup", [vals[dup_day], 1500.0])] and bad == [] and jumps == []
    assert d[dup_day] not in px.index and not px.index.has_duplicates and len(px) == 79 and float(px.iloc[-1]) == 1079.0
    F.log_naver_clean([("X", "가상", glitch)])
    out = capsys.readouterr().out
    assert out.startswith("  !! 네이버 시계열 같은 날짜 두 번 (다른 값): 1종목") and "X 가상 (" in out
    ks = F.kr_series_check(collections.Counter({"recent_fixed": 2, "recent_stocks": 1}), collections.Counter(), {}, [], [], {"X"}, 2,
                           ref={"breakStocks": 0, "unknownStocks": 0, "newStocks": 0})
    cur, prev, final = good_pair()
    cur["data"]["krSeries"] = ks
    with_series(prev)
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "PASS", rep.table()


def test_naver_clean_quiet_line_when_nothing_found(capsys):
    F.log_naver_clean([])
    assert capsys.readouterr().out.startswith("· 네이버 시계열 점검: 같은 날짜 두 번 · 0 이하 · 무한대 값 0종목")
    F.log_naver_clean([("Y", "나", [(T("2026-01-05"), "bad", [float("inf")])])])
    assert capsys.readouterr().out.startswith("  !! 네이버 시계열 0 이하 · 무한대 값: 1종목")
