# -*- coding: utf-8 -*-
"""과거 주가 병합 보정 (2026-11-24 · Jack, Track 1 item 4: "repair the broken price history for the 18 stocks (old share
consolidations)"). (네트워크 없음)

네이버 수정주가가 고치지 않은 옛 주식 수 사건 (병합 · 감자 · 분할 · 무상증자) 의 앞 봉을, 두 출처 이상으로 확인한 배율로 고쳐요
(fetch_data.KR_PX_REPAIRS · kr_px_repair). 고친 종목은 하루 움직임 검사(kr_jumps)에 더 걸리지 않아 krSeries.jump 에서 빠지고, #128 이 비운
숫자가 돌아와요. 화면이 그 까닭을 말할 승인된 줄이 없어서 스위치(KR_PX_REPAIR_ON)는 꺼 두고 무엇을 고칠지만 계산해요 — 여기 시험은 두 쪽 다 봐요.

REAL 의 봉은 2026-11-24 (KST) 에 받은 네이버 일봉 (FinanceDataReader · 파이프라인이 받는 그 시계열) 의 사건 앞뒤 몇 봉이에요."""
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
from test_validate import check  # noqa: E402

T = pd.Timestamp
ROW = "국내 과거 주가 병합 보정 (krSeries.adj · 경고만)"
MARKET = {"001465": "KOSPI", "003060": "KOSPI", "007460": "KOSPI", "009310": "KOSPI", "012170": "KOSPI", "012210": "KOSDAQ",
          "110790": "KOSDAQ", "227420": "KONEX", "311060": "KONEX", "331660": "KONEX", "425040": "KOSDAQ", "472850": "KOSDAQ"}
REAL = {   # (종목, 사건 날짜): 네이버 일봉 (2026-11-24 받음) — 시작 봉 (없으면 사건) 앞 3봉부터 사건 뒤 2봉까지
    ("001465", "2024-04-17"): [("2024-04-12", 198900), ("2024-04-15", 198900), ("2024-04-16", 198900), ("2024-04-17", 17100), ("2024-04-18", 16440),
                               ("2024-04-19", 15800)],
    ("003060", "2026-05-08"): [("2026-05-04", 251), ("2026-05-06", 251), ("2026-05-07", 251), ("2026-05-08", 3480), ("2026-05-11", 2900),
                               ("2026-05-12", 3770)],
    ("007460", "2026-05-08"): [("2026-05-04", 293), ("2026-05-06", 293), ("2026-05-07", 293), ("2026-05-08", 4530), ("2026-05-11", 4000),
                               ("2026-05-12", 5200)],
    ("009310", "2026-05-11"): [("2026-05-06", 1065), ("2026-05-07", 1065), ("2026-05-08", 1065), ("2026-05-11", 5330), ("2026-05-12", 5330),
                               ("2026-05-13", 5330)],
    ("012170", "2025-03-06"): [("2025-02-28", 230), ("2025-03-04", 230), ("2025-03-05", 230), ("2025-03-06", 2065), ("2025-03-07", 1704),
                               ("2025-03-10", 1604)],
    ("012170", "2026-08-28"): [("2026-08-25", 748), ("2026-08-26", 748), ("2026-08-27", 748), ("2026-08-28", 3705), ("2026-08-31", 3125),
                               ("2026-09-01", 3045)],
    ("012210", "2025-04-24"): [("2025-04-21", 1998), ("2025-04-22", 1998), ("2025-04-23", 1998), ("2025-04-24", 3865), ("2025-04-25", 3860),
                               ("2025-04-28", 3945)],
    ("110790", "2023-10-20"): [("2023-10-17", 18960), ("2023-10-18", 18960), ("2023-10-19", 18960), ("2023-10-20", 9450), ("2023-10-23", 9080),
                               ("2023-10-24", 8800)],
    ("227420", "2024-01-19"): [("2024-01-16", 904), ("2024-01-17", 904), ("2024-01-18", 904), ("2024-01-19", 1808), ("2024-01-22", 1808),
                               ("2024-01-23", 1808)],
    ("311060", "2024-01-25"): [("2024-01-22", 7810), ("2024-01-23", 8000), ("2024-01-24", 8270), ("2024-01-25", 4755), ("2024-01-26", 5200),
                               ("2024-01-29", 5500)],
    ("331660", "2026-05-06"): [("2026-04-29", 16450), ("2026-04-30", 16450), ("2026-05-04", 16450), ("2026-05-06", 3385), ("2026-05-07", 3485),
                               ("2026-05-08", 3585)],
    ("425040", "2024-01-02"): [("2023-12-22", 25000), ("2023-12-26", 25450), ("2023-12-27", 26500), ("2023-12-28", 51600), ("2024-01-02", 25100),
                               ("2024-01-03", 23900), ("2024-01-04", 23100)],
    ("472850", "2026-01-02"): [("2025-12-24", 5592), ("2025-12-26", 5530), ("2025-12-29", 5609), ("2025-12-30", 10060), ("2026-01-02", 5300),
                               ("2026-01-05", 5240), ("2026-01-06", 5170)],
}
PXD = dt.date(2026, 11, 20)


def ser(pairs):
    return pd.Series([float(v) for _, v in pairs], index=pd.to_datetime([d for d, _ in pairs]))


def bars(vals, start="2026-01-05"):
    return pd.Series([float(v) for v in vals], index=pd.bdate_range(start, periods=len(vals)))


def days(px, i):
    return px.index[i].date().isoformat()


# ── 0. 스위치 ─────────────────────────────────────────────────
def test_switch_is_off_until_jack_approves_the_line():
    """KR_PX_REPAIR_ON 은 꺼져 있어요 (#182 리뷰): 고친 과거 주가로 만든 숫자는 화면이 그 까닭을 말해야 하는데 승인된 줄이 없어요.
    켜는 PR (Jack 이 줄을 승인한 뒤 · 화면 PR) 이 이 줄을 True 로 바꾸고 PR 의 '안전 규칙 변경' 에 적어요 — 그 PR 에는 되돌리는 방법도 Jack 과
    정해 둬야 해요 (켠 뒤 끄면 고친 12종목이 한꺼번에 다시 숨겨져 '새로 생긴 과거 주가 기록 오류 종목 수' 줄 (10종목) 이 발행을 막아요 · RUNBOOK)."""
    assert F.KR_PX_REPAIR_ON is False


# ── 1. 표 ─────────────────────────────────────────────────────
def test_table_entries_are_well_formed():
    """사건마다: 배율은 0 보다 크고 1 이 아닌 유한한 값 · 종류는 관문과 같은 목록 · 시작 봉은 사건 앞 · 근거가 있어요. 고치지 않는 표와 겹치지 않아요.
    관문(kr_px_adj_problems)이 받는 모양으로 기록돼요."""
    assert len(F.KR_PX_REPAIRS) == 13 and len({c for c, _ in F.KR_PX_REPAIRS}) == 12
    for (c, d), (f, frm, kind, src) in F.KR_PX_REPAIRS.items():
        assert len(c) == 6 and dt.date.fromisoformat(d) <= PXD, (c, d)
        assert isinstance(f, float) and f > 0 and abs(f - 1) > 1e-9, (c, d)
        assert kind in V.KR_PX_ADJ_KIND and isinstance(src, str) and len(src) > 20, (c, d)
        assert frm is None or dt.date.fromisoformat(frm) < dt.date.fromisoformat(d), (c, d)
        assert (c, d) not in F.KR_PX_NOFIX
    for (c, d), (why, note) in F.KR_PX_NOFIX.items():
        assert why in F.KR_PX_NOFIX_KO and why != "new" and note, (c, d)
    assert F.KR_PX_ADJ_KIND is V.KR_PX_ADJ_KIND and F.KR_PX_ADJ_SKIP is V.KR_PX_ADJ_SKIP and set(V.KR_PX_ADJ_QUIET) <= set(V.KR_PX_ADJ_SKIP)


def test_exact_double_after_a_halt_is_not_enough_on_its_own():
    """121890 에스디시스템 (2023-10-23): 기준가 1,478 = 전날 739 × 2 정확히, 고친 뒤 첫날 +30% (제한폭 안) — 그래도 주식 수는 그대로이고 야후에도
    분할 기록이 없어요. 거래 재개 시초가의 상한 (200%) 이 정확한 비율처럼 보인 것이라, 배율 하나만으로는 받아들이지 않아요 (표에 없어요)."""
    assert ("121890", "2023-10-23") in F.KR_PX_NOFIX and not any(c == "121890" for c, _ in F.KR_PX_REPAIRS)
    px = ser([("2023-10-18", 739), ("2023-10-19", 739), ("2023-10-20", 739), ("2023-10-23", 1921), ("2023-10-24", 1890)])
    assert F.kr_jumps(px, px, 30.0) and F.kr_px_repair(px, "121890", PXD, 30.0) == (px, [], [])
    # 같은 봉이라도 표에 적으면 고쳐져요 — 그래서 표에는 두 출처로 확인한 사건만 넣어요
    got, fx, sk = F.kr_px_repair(px, "121890", PXD, 30.0, table={("121890", "2023-10-23"): (2.0, None, "merge", "가상")})
    assert [x["d"] for x in fx] == ["2023-10-23"] and not F.kr_jumps(got, got, 30.0)


@pytest.mark.parametrize("key", sorted(REAL))
def test_each_table_entry_fits_the_real_naver_bars(key):
    """표의 사건마다 실제 네이버 봉에서: 원래는 하루 움직임 검사에 걸리고, 고치면 그 자리의 움직임이 없어지고, 곱한 값은 원 단위로 원래 × 배율."""
    c, d = key
    f, frm, kind, _ = F.KR_PX_REPAIRS[key]
    lim = F.kr_day_limit(MARKET[c])
    raw = ser(REAL[key])
    table = {key: F.KR_PX_REPAIRS[key]}
    assert F.kr_jumps(raw, raw, lim)
    got, fx, sk = F.kr_px_repair(raw, c, PXD, lim, table=table)
    assert sk == [] and len(fx) == 1 and fx[0]["d"] == d and fx[0]["f"] == f and fx[0].get("from") == frm, (fx, sk)
    assert F.kr_jumps(got, got, lim) == [], F.kr_jumps(got, got, lim)
    lo = T(frm) if frm else raw.index[0]
    for t, v in raw.items():
        want = F._won(v * f) if lo <= t < T(d) else v
        assert got.loc[t] == want, (t, got.loc[t], want)
    assert fx[0]["n"] == int(((raw.index >= lo) & (raw.index < T(d))).sum())


def test_known_values():
    """근거에 적은 값 그대로: 001465 198,900 → 19,890 (KRX 기준가) · 003060 251 → 3,765 · 425040 12-28 봉 51,600 → 25,800 (KRX 기준가) ·
    472850 12-30 봉 10,060 → 5,660 (KRX 기준가) · 012170 두 사건이 겹친 봉은 × 50."""
    def fix(key):
        c = key[0]
        return F.kr_px_repair(ser(REAL[key]), c, PXD, F.kr_day_limit(MARKET[c]), table={key: F.KR_PX_REPAIRS[key]})[0]
    assert fix(("001465", "2024-04-17")).loc[T("2024-04-16")] == 19890.0
    assert fix(("003060", "2026-05-08")).loc[T("2026-05-07")] == 3765.0
    g = fix(("425040", "2024-01-02"))
    assert g.loc[T("2023-12-28")] == 25800.0 and g.loc[T("2023-12-27")] == 26500.0          # 네이버가 이미 고친 앞 봉은 그대로
    g = fix(("472850", "2026-01-02"))
    assert g.loc[T("2025-12-30")] == 5660.0 and g.loc[T("2025-12-29")] == 5609.0
    both = ser(REAL[("012170", "2025-03-06")] + REAL[("012170", "2026-08-28")])
    got, fx, sk = F.kr_px_repair(both, "012170", PXD, 30.0)
    assert [x["d"] for x in fx] == ["2025-03-06", "2026-08-28"] and sk == []
    assert got.loc[T("2025-03-05")] == 230 * 50 and got.loc[T("2025-03-06")] == 2065 * 5 and got.loc[T("2026-08-27")] == 748 * 5
    assert got.loc[T("2026-08-28")] == 3705
    # 두 창을 이어 붙인 가상 시계열이라 그 이음매 (2025-03-10 → 2026-08-25) 말고는 움직임이 없어요
    assert [t for t, _, _ in F.kr_jumps(got, got, 30.0)] == [T("2026-08-25")]


# ── 2. 날마다 다시 확인 (kr_px_repair 의 까닭) ───────────────────
TAB = {("X", "2026-01-12"): (10.0, None, "merge", "가상 10주 → 1주")}


def merged(fixed_by_naver=False):
    """2026-01-05 부터 10봉: 앞 5봉 100 근처, 2026-01-12 (6번째) 부터 10주 → 1주 병합 뒤 1,000 근처 (네이버가 고쳤으면 앞 봉도 1,000 근처)."""
    pre = [100, 101, 99, 100, 102] if not fixed_by_naver else [1000, 1010, 990, 1000, 1020]
    return bars(pre + [1015, 1030, 1000, 990, 1005])


def test_repairs_a_merge_and_is_idempotent():
    raw = merged()
    got, fx, sk = F.kr_px_repair(raw, "X", PXD, 30.0, table=TAB)
    assert fx == [{"t": "X", "d": "2026-01-12", "f": 10.0, "k": "merge", "n": 5, "src": "가상 10주 → 1주"}] and sk == []
    assert list(got.values) == [1000, 1010, 990, 1000, 1020, 1015, 1030, 1000, 990, 1005] and got.index.equals(raw.index)
    assert F.kr_jumps(raw, raw, 30.0) and F.kr_jumps(got, got, 30.0) == []
    # 두 번 곱하지 않아요: 이미 고친 시계열 (또는 네이버가 고친 시계열) 은 'same' 으로 건너뛰고 그대로 돌려줘요
    for again in (got, merged(fixed_by_naver=True)):
        g2, fx2, sk2 = F.kr_px_repair(again, "X", PXD, 30.0, table=TAB)
        assert g2 is again and fx2 == [] and sk2 == [("2026-01-12", "same")]


def test_other_codes_are_untouched():
    raw = merged()
    assert F.kr_px_repair(raw, "Y", PXD, 30.0, table=TAB) == (raw, [], [])
    assert F.kr_px_repair(raw, "005930", PXD, 30.0) == (raw, [], [])        # 실제 표에도 없는 종목


@pytest.mark.parametrize("case,want", [
    ("after", "after"),        # 사건이 기준일 뒤
    ("old", "old"),            # 사건이 시계열의 첫 봉 (창 밖으로 나가는 중) — 조용히
    ("gone", "old"),           # 사건이 시계열보다 앞
    ("nobar", "nobar"),        # 그날 봉이 없음
    ("still", "still"),        # 곱해도 첫날이 제한폭 밖 (감자 뒤 재상장 시초가가 높았을 때 — 304840 같은 경우)
    ("short", "nobar"),        # 봉이 하나뿐
])
def test_skip_reasons(case, want):
    raw = merged()
    pxd, table = PXD, TAB
    if case == "after":
        pxd = dt.date(2026, 1, 9)
    elif case == "old":
        raw = raw[raw.index >= T("2026-01-12")]
    elif case == "gone":
        raw = raw[raw.index > T("2026-01-12")]
    elif case == "nobar":
        raw = raw.drop(T("2026-01-12"))
    elif case == "still":
        table = {("X", "2026-01-12"): (5.0, None, "merge", "가상")}
    elif case == "short":
        raw = raw.iloc[:1]
    got, fx, sk = F.kr_px_repair(raw, "X", pxd, 30.0, table=table)
    assert got is raw and fx == [] and sk == [("2026-01-12", want)]


def test_partial_range_and_its_both_edges():
    """네이버가 앞 봉은 고쳤는데 한 봉만 빠뜨린 경우 (425040 · 472850): 시작 봉부터만 곱하고, 두 경계가 모두 맞아야 해요."""
    raw = bars([500, 505, 510, 1030, 500, 495, 490])           # 4번째 봉 (2026-01-08) 만 옛 기준
    tab = {("X", "2026-01-09"): (0.5, "2026-01-08", "bonus", "가상 권리락")}
    got, fx, sk = F.kr_px_repair(raw, "X", PXD, 30.0, table=tab)
    assert list(got.values) == [500, 505, 510, 515, 500, 495, 490] and fx[0]["n"] == 1 and fx[0]["from"] == "2026-01-08" and sk == []
    # 네이버가 앞 봉도 고치지 않았으면 (시계열이 표를 적을 때와 달라졌어요) — 시작 경계는 이미 안이지만 곱하면 밖이라 'still' (크게)
    raw2 = bars([1000, 1010, 1020, 1030, 500, 495, 490])
    assert F.kr_px_repair(raw2, "X", PXD, 30.0, table=tab)[1:] == ([], [("2026-01-09", "still")])
    # 시작 봉이 사건과 같거나 뒤 · 시계열 안인데 그 봉이 없음 → nobar
    for frm in ("2026-01-09", "2026-01-12"):
        assert F.kr_px_repair(raw, "X", PXD, 30.0, table={("X", "2026-01-09"): (0.5, frm, "bonus", "가상")})[2] == [("2026-01-09", "nobar")]
    assert F.kr_px_repair(raw.drop(T("2026-01-07")), "X", PXD, 30.0,
                          table={("X", "2026-01-09"): (0.5, "2026-01-07", "bonus", "가상")})[2] == [("2026-01-09", "nobar")]


@pytest.mark.parametrize("cut", ["2026-01-08", "2026-01-09"])
def test_partial_range_when_the_window_starts_at_or_after_the_first_bar(cut):
    """#182 리뷰: 창이 시작 봉에서 (또는 그 뒤에서) 시작하면 시작 경계는 창 밖이에요 — 처음부터 사건 앞까지 곱하고 사건 경계만 봐요 (크게 남기지
    않아요 · 425040 은 2027년 2월쯤 · 472850 은 2029년쯤 이렇게 돼요). 사건이 첫 봉이 되면 'old' (조용히)."""
    raw = bars([500, 505, 510, 1030, 1040, 500, 495, 490])     # 2026-01-08 · 01-09 두 봉이 옛 기준, 사건 01-12
    tab = {("X", "2026-01-12"): (0.5, "2026-01-08", "bonus", "가상 권리락")}
    win = raw[raw.index >= T(cut)]
    got, fx, sk = F.kr_px_repair(win, "X", PXD, 30.0, table=tab)
    n = int((win.index < T("2026-01-12")).sum())
    assert sk == [] and fx[0]["n"] == n and list(got.values[:n]) == [F._won(v * 0.5) for v in win.values[:n]] and F.kr_jumps(got, got, 30.0) == []
    assert F.kr_px_repair(raw[raw.index >= T("2026-01-12")], "X", PXD, 30.0, table=tab)[2] == [("2026-01-12", "old")]


def test_conflicting_events_change_nothing():
    """사건마다 따로는 맞지만 함께 곱하면 경계가 어긋나면 그 종목은 하나도 고치지 않아요 ('conflict' · 크게)."""
    raw = bars([100, 100, 100, 200, 100, 100])
    tab = {("X", "2026-01-08"): (2.0, None, "merge", "가상 A"), ("X", "2026-01-09"): (0.5, "2026-01-08", "bonus", "가상 B")}
    got, fx, sk = F.kr_px_repair(raw, "X", PXD, 30.0, table=tab)
    assert got is raw and fx == [] and sorted(sk) == [("2026-01-08", "conflict"), ("2026-01-09", "conflict")]


def test_konex_limit_is_used():
    """코넥스 (±15%): 고친 뒤 첫날 +15% 는 안 · 같은 시계열에 코스닥 제한폭을 쓰면 원래 움직임도 … 경계는 kr_jumps 와 같은 jump_bounds."""
    raw = ser(REAL[("311060", "2024-01-25")])
    got, fx, _ = F.kr_px_repair(raw, "311060", PXD, F.kr_day_limit("KONEX"))
    assert fx and F.kr_jumps(got, got, F.kr_day_limit("KONEX")) == []
    lo, hi = F.jump_bounds(F.kr_day_limit("KONEX"))
    assert lo <= 4755 / 4135 - 1 <= hi


# ── 3. 기록 · 로그 (kr_px_adj_step) ─────────────────────────────
def rep_rows():
    out = []
    for key in sorted(REAL):
        c = key[0]
        _, fx, sk = F.kr_px_repair(ser(REAL[key]), c, PXD, F.kr_day_limit(MARKET[c]), table={key: F.KR_PX_REPAIRS[key]})
        out.append((c, "이름" + c, fx, sk))
    merged_rows = collections.OrderedDict()
    for c, nm, fx, sk in out:
        r = merged_rows.setdefault(c, [c, nm, [], []])
        r[2] += fx
        r[3] += sk
    return [tuple(r) for r in merged_rows.values()]


# 2026-11-21 발행본 (pxDate 2026-11-20) 의 krSeries.jump 그대로 (20종목 · 24줄) + 표 밖의 가상 종목 하나
JUMP_OFF = [["001465", "2024-04-17", -91.4, "halt"], ["003060", "2026-05-08", 1286.5, "halt"], ["007460", "2026-05-08", 1446.1, "halt"],
            ["007610", "2026-04-29", 116.7, "halt"], ["009310", "2026-05-11", 400.5, "halt"], ["012170", "2025-03-06", 797.8, "halt"],
            ["012170", "2026-08-28", 395.3, "halt"], ["012210", "2025-04-24", 93.4, "halt"], ["107640", "2024-06-24", -38.2, "spike"],
            ["110790", "2023-10-20", -50.2, "halt"], ["121890", "2023-10-23", 159.9, "halt"], ["206950", "2024-03-15", 21.5, "halt"],
            ["206950", "2026-04-07", 38.2, "halt"], ["210120", "2026-10-12", 51.1, "other"], ["227420", "2024-01-19", 100.0, "halt"],
            ["229500", "2024-05-29", -57.5, "halt"], ["250030", "2026-10-15", -48.7, "other"], ["304840", "2026-11-20", 182.7, "halt"],
            ["311060", "2024-01-25", -42.5, "other"], ["331660", "2026-05-06", -79.4, "halt"], ["425040", "2023-12-28", 94.7, "spike"],
            ["425040", "2024-01-02", -51.4, "spike"], ["472850", "2025-12-30", 79.4, "spike"], ["472850", "2026-01-02", -47.3, "spike"]]


def test_record_when_off(capsys):
    rows = rep_rows()
    pub = {c for c, *_ in rows} | {j[0] for j in JUMP_OFF}
    adj = F.kr_px_adj_step(rows, pub, JUMP_OFF, {"007610": "선도전기"}, on=False)
    out = capsys.readouterr().out
    assert adj["on"] is False and len(adj["fix"]) == 13 and adj["skip"] == []
    assert V.kr_px_adj_problems(adj, PXD) == [] and json.dumps(adj, allow_nan=False, ensure_ascii=False)
    assert out.startswith("· 과거 주가 병합 보정 (KR_PX_REPAIR_ON 꺼짐 — ") and "켜면 고칠 종목 12 (13건)" in out
    # #182 리뷰: 425040 · 472850 의 시작 봉 움직임 (2023-12-28 · 2025-12-30) 도 그 사건이 고쳐요 — 남는 종목은 8 (10 이 아니에요)
    assert "001465 이름001465 2024-04-17 ×0.1" in out and "켜도 숨긴 채 남는 종목 8 (" in out and "아직 확인하지 않은" not in out
    for part in ("주식 수 사건이 아닌 진짜 움직임 5: 007610 선도전기, 107640, 121890, 206950, 250030", "네이버 봉 하나가 공식 종가와 다름 1: 210120",
                 "배율을 말하는 출처가 하나뿐 1: 229500", "고쳐도 첫날이 하루 가격 제한폭 밖 1: 304840"):
        assert part in out, part
    assert "표에 있는데" not in out                           # 표의 12종목 모두 보정 단계에 닿았어요
    F.kr_px_adj_step(rows, pub | {"999990"}, JUMP_OFF + [["999990", "2025-01-02", 60.0, "other"]], on=False)
    assert "켜도 숨긴 채 남는 종목 9 (" in (out := capsys.readouterr().out) and "아직 확인하지 않은 움직임 1: 999990" in out
    # 발행하지 않는 종목은 싣지 않아요
    assert F.kr_px_adj_step(rows, {"001465"}, [], on=False)["fix"] == [x for x in adj["fix"] if x["t"] == "001465"]


def test_record_when_on_and_loud_skips(capsys):
    rows = rep_rows()
    pub = {c for c, *_ in rows}
    adj = F.kr_px_adj_step(rows, pub, [["007610", "2026-04-29", 116.7, "halt"]], on=True)
    out = capsys.readouterr().out
    assert adj["on"] is True and out.startswith("· 과거 주가 병합 보정 (KR_PX_REPAIR_ON 켜짐): 고친 종목 12 (13건 · 숨김에서 빠짐 12)")
    assert "숨긴 채 남는 종목 1 (주식 수 사건이 아닌 진짜 움직임 1: 007610)" in out
    # 표의 사건이 오늘 시계열과 맞지 않으면 크게 ('same' · 'after' · 'old' 는 조용히)
    quiet = F.kr_px_adj_step([("X", "가", [], [("2026-01-02", "same"), ("2026-01-03", "old")])], {"X"}, [], on=True)
    assert capsys.readouterr().out.startswith("· ") and quiet["skip"] == [["X", "2026-01-02", "same"], ["X", "2026-01-03", "old"]]
    tab = {("X", "2026-01-02"): (2.0, None, "merge", "가상")}
    loud = F.kr_px_adj_step([("X", "가", [], [("2026-01-02", "still")])], {"X"}, [["X", "2026-01-02", 80.0, "halt"]], on=True, table=tab)
    out = capsys.readouterr().out
    assert out.startswith("  !! ") and "표의 사건을 건너뜀 1: X 가 2026-01-02 고쳐도 하루 가격 제한폭 밖" in out
    assert "숨긴 채 남는 종목 1 (고쳐도 첫날이 하루 가격 제한폭 밖 1: X 가)" in out and V.kr_px_adj_problems(loud) == []


@pytest.mark.parametrize("on", [False, True])
@pytest.mark.parametrize("why", ["nobar", "conflict"])
def test_a_skipped_event_keeps_its_own_reason(why, on, capsys):
    """#182 리뷰: 건너뛴 표의 사건 (nobar · conflict) 은 남는 까닭도 그 까닭이에요 ('고쳐도 제한폭 밖' 이 아니라) · 크게."""
    tab = {("X", "2026-01-02"): (2.0, None, "merge", "가상")}
    F.kr_px_adj_step([("X", "가", [], [("2026-01-02", why)])], {"X"}, [["X", "2026-01-02", 80.0, "halt"]], on=on, table=tab)
    out = capsys.readouterr().out
    assert out.startswith("  !! ") and f"(표의 사건을 고치지 못함 ({V.KR_PX_ADJ_SKIP[why]}) 1: X 가)" in out and "고쳐도 첫날이" not in out


def test_a_table_stock_that_never_reached_the_repair_is_named(capsys):
    """#182 리뷰: 표에 있는데 오늘 보정 단계에 닿지 않은 종목 (목록에 없음 · 시세를 받지 못함) 과 발행하지 않는 종목을 이름으로 (조용히)."""
    tab = {("X", "2026-01-02"): (2.0, None, "merge", "가상"), ("Y", "2026-01-02"): (2.0, None, "merge", "가상"),
           ("Z", "2026-01-02"): (2.0, None, "merge", "가상")}
    F.kr_px_adj_step([("X", "가", [], []), ("Z", "다", [], [])], {"X"}, [], on=False, table=tab)
    out = capsys.readouterr().out
    assert out.startswith("· ") and "표에 있는데 오늘 보지 못한 종목 1 (목록에 없거나 시세를 받지 못함): Y" in out
    assert "표에 있는데 발행하지 않는 종목 1: Z" in out


def test_one_stocks_repair_error_rehides_only_that_stock(monkeypatch, capsys):
    """#182 리뷰 (Fable S2): 켜졌을 때 한 종목의 보정이 오류로 멈추면 그 종목만 고치지 않은 시계열 (예전처럼 숨겨요) · 건너뜀 'err' · 크게 —
    다른 종목은 그대로 고쳐요. kr_px_repair_step 이 fetch_korea.one() 이 종목마다 부르는 그 함수예요."""
    real = F.kr_px_repair

    def boom(px, code, *a, **k):
        if code == "007460":
            raise ValueError("가상 오류")
        return real(px, code, *a, **k)
    monkeypatch.setattr(F, "kr_px_repair", boom)
    got = {}
    for key in (("003060", "2026-05-08"), ("007460", "2026-05-08"), ("001465", "2024-04-17")):
        raw = ser(REAL[key])
        got[key[0]] = (raw, *F.kr_px_repair_step(raw, key[0], "이름", PXD, MARKET[key[0]], on=True))
    out = capsys.readouterr().out
    assert "  !! 과거 주가 보정 오류 007460 이름 (ValueError: 가상 오류) — 이 종목만 고치지 않아요" in out
    raw, px, rec = got["007460"]
    assert px is raw and rec == ("007460", "이름", [], [("", "err")]) and F.kr_jumps(px, px, 30.0)
    for c in ("003060", "001465"):
        raw, px, rec = got[c]
        assert px is not raw and len(rec[2]) == 1 and F.kr_jumps(px, px, 30.0) == []
    F.kr_px_adj_step([r for _, _, r in got.values()], {"003060", "007460", "001465"}, [["007460", "2026-05-08", 1446.1, "halt"]], on=True)
    out = capsys.readouterr().out
    assert out.startswith("  !! ") and "고친 종목 2 (2건 · 숨김에서 빠짐 2)" in out and "표의 사건을 고치지 못함 (보정 단계 오류) 1: 007460" in out
    # 꺼져 있으면 오류가 없어도 받은 그대로, 표 밖의 종목은 기록 없이 그대로
    raw = ser(REAL[("003060", "2026-05-08")])
    assert F.kr_px_repair_step(raw, "003060", "이름", PXD, "KOSPI", on=False)[0] is raw
    assert F.kr_px_repair_step(raw, "005930", "삼성전자", PXD, "KOSPI", on=True) == (raw, None)


# ── 4. fetch_korea 안의 자리 ──────────────────────────────────
def test_fetch_korea_repairs_before_every_number_only_when_on():
    """보정은 naver_clean 바로 뒤 · 공식 종가 고정 · 자기 점검 · c1w · 움직임 검사 · 모든 숫자보다 먼저, 스위치가 켜졌을 때만 그 시계열을 써요.
    기록은 krSeries 를 만든 바로 뒤 · 숫자를 비우기(mark_px_bad) 전에 (오류가 나도 숫자는 그대로 · 기록만 비워요)."""
    src = inspect.getsource(F.fetch_korea)
    i_clean = src.index("px, glitch = naver_clean(px)")
    i_rep = src.index('px, rrec = kr_px_repair_step(px, code, str(row["Name"]), px_date, row.get("Market"))')
    assert i_clean < i_rep < src.index("raw = cut_at(px, px_date)") < src.index("px, how = pin_close(px, px_date, close)")
    assert src.count("kr_px_repair_step(") == 1 and "kr_px_repair(" not in src
    step = inspect.getsource(F.kr_px_repair_step)
    assert "return (rpx if (rfix and on) else px), (code, name, rfix, rskip)" in step and "except Exception" in step
    i_ks = src.index("krs = kr_series_check(")
    i_adj = src.index('krs["adj"] = kr_px_adj_step(px_rep, {r["t"] for r in out}, krs.get("jump"), {r["t"]: r.get("nk") for r in out})')
    assert i_ks < i_adj < src.index("mark_px_bad(out, krs, win_cut)")
    assert isinstance(F.KR_PX_REPAIR_ON, bool)


@pytest.mark.parametrize("on", [False, True])
def test_one_stock_like_fetch_korea(on, monkeypatch):
    """fetch_korea.one() 의 순서 그대로 (naver_clean → 보정 → 공식 종가 고정 → 움직임 검사 → 숫자 · 숨김): 켜면 003060 의 움직임이 없어지고 숨김에서
    빠져 52주가 돌아와요. 꺼 두면 예전 그대로 (움직임 · 숨김)."""
    monkeypatch.setattr(F, "KR_PX_REPAIR_ON", on)
    pre = [251.0] * 40
    post = [3480, 2900, 3770, 4900, 4400, 4200, 4100, 4000, 3900, 3800] * 3
    px0 = pd.Series(pre + [float(v) for v in post], index=pd.bdate_range("2026-03-27", periods=70))
    pxd = px0.index[-1].date()
    px, _ = F.naver_clean(px0)
    rpx, rfix, rskip = F.kr_px_repair(px, "003060", pxd, F.kr_day_limit("KOSPI"),
                                      table={("003060", px0.index[40].date().isoformat()): (15.0, None, "merge", "가상")})
    if rfix and F.KR_PX_REPAIR_ON:
        px = rpx
    raw = F.cut_at(px, pxd)
    px, how = F.pin_close(px, pxd, 3800.0)
    jm = F.kr_jumps(px, raw, F.kr_day_limit("KOSPI"))
    rec = {"t": "003060", "cls": "kr", "nk": "가", "lo": float(px.tail(252).min()), "hi": float(px.tail(252).max()),
           "vol": F.ann_vol(px.pct_change().dropna().values)}
    ks = {"jump": [["003060", t.date().isoformat(), p, w] for t, p, w in jm]}
    F.mark_px_bad([rec], ks, {"003060": {w: px.index[0].date().isoformat() for w in V.PX_BAD_WIN}})
    if on:
        assert jm == [] and "pxBad" not in rec and ks["hidden"] == [] and float(px.iloc[39]) == 251 * 15
        assert rec["lo"] == 2900.0 and rec["hi"] == 4900.0
    else:
        assert [w for _, _, w in jm] == ["halt"] and rec["pxBad"] and "lo" not in rec and ks["hidden"] == ["003060"]


# ── 5. 관문 줄 (경고만) ─────────────────────────────────────────
def gate(adj=None, jump=None, drop=False):
    cur, prev, final = good_pair()
    ks = {"v": 1, "days": 19, "pinned": 0, "pinStocks": 0, "kept": {"basis": 0, "far": 0, "shr": 0}, "keptStocks": 0, "bad": 0, "badStocks": [],
          "ref": {"breakStocks": 0, "unknownStocks": 0, "newStocks": 0}, "jump": jump or []}
    if not drop:
        ks["adj"] = adj
    cur["data"]["krSeries"] = ks
    prev["data"]["krSeries"] = {k: v for k, v in ks.items() if k != "adj"}
    rep = check(cur, prev, final)
    return rep, next(r for r in rep.rows if r[0] == ROW)


FIX = {"t": "005930", "d": "2024-04-17", "f": 0.1, "k": "split", "n": 126, "src": "가상 근거"}


def test_gate_row_passes_and_names_each_repair():
    rep, r = gate({"on": True, "fix": [FIX, dict(FIX, t="000660", d="2026-01-02", f=5660 / 10060, k="bonus", n=1, **{"from": "2025-12-30"})],
                   "skip": [["005380", "2026-01-05", "same"]]})
    assert r[3] == "PASS" and r[1].startswith("켜짐 · 고친 2종목 2건: 005930 삼성전자 2024-04-17 ×0.1, 000660 SK하이닉스 2026-01-02 ×0.5626 (2025-12-30부터)")
    assert ("과거 주가를 고친 국내 종목 (새 기준 첫 날 · 앞 봉에 곱한 배율)", ["005930 삼성전자 2024-04-17 ×0.1",
                                                                    "000660 SK하이닉스 2026-01-02 ×0.5626 (2025-12-30부터)"]) in rep.details
    rep, r = gate({"on": False, "fix": [FIX], "skip": []})
    assert r[3] == "PASS" and r[1].startswith("꺼짐 (숫자는 예전처럼 · 화면의 이유 줄을 기다려요) · 켜면 고칠 1종목 1건: 005930")
    assert not any(t.startswith("과거 주가를 고친") for t, _ in rep.details)
    _, r = gate(drop=True)
    assert r[3] == "PASS" and r[1] == "krSeries.adj 없음 (2026-11-24 전 형식)"


@pytest.mark.parametrize("adj", [
    None, [], {"fix": [], "skip": []}, {"on": "yes", "fix": [], "skip": []}, {"on": True, "fix": {}, "skip": []},
    {"on": True, "fix": [], "skip": {}}, {"on": True, "fix": [dict(FIX, f=1.0)], "skip": []}, {"on": True, "fix": [dict(FIX, f=-2)], "skip": []},
    {"on": True, "fix": [dict(FIX, f="0.1")], "skip": []}, {"on": True, "fix": [dict(FIX, k="other")], "skip": []},
    {"on": True, "fix": [dict(FIX, n=0)], "skip": []}, {"on": True, "fix": [dict(FIX, src="")], "skip": []},
    {"on": True, "fix": [dict(FIX, d="2027-01-04")], "skip": []}, {"on": True, "fix": [dict(FIX, **{"from": "2024-04-17"})], "skip": []},
    {"on": True, "fix": [FIX, FIX], "skip": []}, {"on": True, "fix": [], "skip": [["005930", "2024-04-17", "naver"]]},
    {"on": True, "fix": [], "skip": [["005930", "2024-04-17"]]},
    # #182 리뷰: 관문을 멈추던 모양 (TypeError · OverflowError) — 이제 모양 경고
    {"on": True, "fix": [dict(FIX, k=["merge"])], "skip": []}, {"on": True, "fix": [dict(FIX, k={"merge": 1})], "skip": []},
    {"on": True, "fix": [], "skip": [["005930", "2024-04-17", ["same"]]]}, {"on": True, "fix": [], "skip": [["005930", "2024-04-17", {"a": 1}]]},
    {"on": True, "fix": [dict(FIX, f=10 ** 400)], "skip": []}, {"on": True, "fix": [dict(FIX, d=["2024-04-17"])], "skip": []},
    {"on": True, "fix": [dict(FIX, t=["005930"])], "skip": []}, {"on": True, "fix": [dict(FIX, **{"from": ["2024-01-02"]})], "skip": []},
    {"on": True, "fix": ["005930"], "skip": []},
])
def test_gate_row_warns_never_fails_on_a_wrong_shape(adj):
    rep, r = gate(adj)
    assert r[3] == "WARN" and r[1].startswith("모양: ") and ROW not in {x[0] for x in rep.failed}


def test_gate_row_never_stops_the_gate(monkeypatch):
    """#182 리뷰: 경고만 하는 줄은 어떤 오류로도 관문을 멈추지 않아요 — run_checks 가 그 오류를 이 줄의 경고로 바꿔요."""
    def boom(*a, **k):
        raise RuntimeError("가상 오류")
    monkeypatch.setattr(V, "check_kr_px_adj", boom)
    rep, r = gate({"on": True, "fix": [FIX], "skip": []})
    assert r[3] == "WARN" and r[1].startswith("확인하다 오류 (RuntimeError: 가상 오류)") and ROW not in {x[0] for x in rep.failed}
    assert ROW == V.KR_PX_ADJ_ROW


def test_gate_row_warns_when_a_repair_did_not_clear_or_a_verified_factor_no_longer_fits():
    rep, r = gate({"on": True, "fix": [FIX], "skip": []}, jump=[["005930", "2024-04-17", -91.4, "halt"]])
    assert r[3] == "WARN" and "고쳤는데 숨긴 채 남음 1: 005930 삼성전자 (2024-04-17)" in r[1] and ROW not in {x[0] for x in rep.failed}
    # #182 리뷰: 다른 날짜의 움직임이어도 (네이버가 일부만 다시 고쳐 오래된 보정이 두 번 곱해진 봉) 경고
    _, r = gate({"on": True, "fix": [FIX], "skip": []}, jump=[["005930", "2023-11-02", 99.0, "other"]])
    assert r[3] == "WARN" and "고쳤는데 숨긴 채 남음 1: 005930 삼성전자 (2023-11-02)" in r[1]
    rep, r = gate({"on": True, "fix": [], "skip": [["005930", "2024-04-17", "still"], ["000660", "2025-01-02", "old"]]})
    assert r[3] == "WARN" and r[1].endswith("표의 사건을 건너뜀 1: 005930 삼성전자 2024-04-17 고쳐도 하루 가격 제한폭 밖")
    _, r = gate({"on": False, "fix": [FIX], "skip": []}, jump=[["005930", "2024-04-17", -91.4, "halt"]])
    assert r[3] == "PASS"                     # 꺼져 있으면 움직임이 남는 게 맞아요
