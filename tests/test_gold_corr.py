# -*- coding: utf-8 -*-
"""Track 2 감사 3.5 (2026-11-24) — 국제 금값(GC=F) 다운로드 하나가 시장 가정을 모두 지우지 않게 (fetch_data.market_assumptions,
관문 validate_data.check_mkt_settings).

예전 (main 00ac1e3): 금값이 None 이면 'mt' 열이 없어서 `if len(j) > MIN_DAYS and "mt" in j.columns:` 가 금과 상관없는 한국 · 미국
변동성 · 한국 ↔ 미국 상관계수 · 채권 값까지 10칸을 모두 건너뛰었고, 로그는 '시장 가정 계산에 쓸 날이 N일뿐' 이라는 틀린 이유를 적었어요.

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 시험은 그대로):
- 모두 있으면 예전 코드(아래 old_block, main 00ac1e3 그대로)와 같은 값 · 같은 칸 순서 (여러 난수 · us_vol_krw 있음/없음)
- 채권이 없으면 예전과 같아요 (예전에도 금 · 한국 · 미국 6칸)
- 금이 없거나 비면: 한국 · 미국 · 채권 6칸은 계산 (한국 · 미국 · 채권이 함께 있는 날로) · 금 4칸은 빠짐 · 로그에 진짜 이유와 칸 이름
- 금 · 채권이 모두 없으면 한국 · 미국 3칸
- 날이 모자라면: 한국 · 미국부터 모자라면 아무 칸도 없음 + 진짜 이유 · 금만 짧으면 금 칸만 빠짐 · 넷이 함께 있는 날만 모자라면 짧은 쪽 하나
- 금 열이 이상해 오류가 나도 한국 · 미국 칸은 계산 · 계산한 값이 NaN · 범위 밖이면 그 칸만 빠지고 이유 (JSON 에 NaN 없음)
- main 이 이 함수를 부르고 예전 조건이 남지 않았어요
- 관문: 한 줄 · 경고만 (빠진 칸 이름 · 지난 발행본에는 있던 칸 · 숫자가 아닌 값 · 검사 오류도 경고) — 발행 · 사이트 점검 모두 실패 없음
"""
import inspect
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402

KEYS = ("mktVol", "usVol", "mtVol", "rhoKrUs", "rhoKrMt", "rhoUsMt", "bdVol", "rhoKrBd", "rhoUsBd", "rhoMtBd")
GOLD = ("mtVol", "rhoKrMt", "rhoUsMt", "rhoMtBd")
BOND = ("bdVol", "rhoKrBd", "rhoUsBd", "rhoMtBd")
KRUS = ("mktVol", "usVol", "rhoKrUs")
LEFT = "빼요 (예전 뱁새는 그 칸에 기본값을 써요 · 2.0 은 기본값을 쓰지 않아요)"      # 뺀 칸 줄의 끝 (로그만 · 화면 글 아님)


def old_block(kr_bench, us_bench, fx, gold_usd, bd_ret, px_date, us_vol_krw):
    """main 00ac1e3 의 fetch_data.main 시장 가정 계산 그대로 (비교용 · log 대신 줄 목록 · settings 는 rf 없이)."""
    settings, lines = {}, []
    fxr = fx.pct_change()
    us_krw = us_bench + fxr.reindex(us_bench.index).fillna(0)
    cols = [kr_bench.rename("kr"), us_krw.rename("us")]
    if gold_usd is not None:
        cols.append((gold_usd.pct_change() + fxr.reindex(gold_usd.index).fillna(0)).dropna().rename("mt"))
    if bd_ret is not None:
        cols.append(bd_ret.rename("bd"))
    j = F.cut_at(pd.concat(cols, axis=1).dropna(), px_date)
    if len(j) > F.MIN_DAYS and "mt" in j.columns:
        c = j.corr()
        settings.update({
            "mktVol": F.ann_vol(j["kr"].values),
            "usVol": us_vol_krw or F.ann_vol(j["us"].values),
            "mtVol": F.ann_vol(j["mt"].values),
            "rhoKrUs": round(float(c.loc["kr", "us"]), 2),
            "rhoKrMt": round(float(c.loc["kr", "mt"]), 2),
            "rhoUsMt": round(float(c.loc["us", "mt"]), 2),
        })
        if "bd" in j.columns:
            settings.update({
                "bdVol": F.ann_vol(j["bd"].values),
                "rhoKrBd": round(float(c.loc["kr", "bd"]), 2),
                "rhoUsBd": round(float(c.loc["us", "bd"]), 2),
                "rhoMtBd": round(float(c.loc["mt", "bd"]), 2),
            })
        lines.append(f"· 시장 가정 계산 완료 ({len(j):,}일, ~{px_date}): {settings}")
    else:
        lines.append(f"  !! 시장 가정 계산에 쓸 날이 {len(j)}일뿐 — 기본값을 써요")
    return settings, lines


def inputs(seed=1, n=800, gold=True, bond=True):
    """3년 남짓 (평일 n 일) 의 가짜 입력: 한국 · 미국은 서로 다른 휴장일 · 환율과 금은 가격 · 채권은 수익률 (일부 날 빠짐).
    한국 ↔ 미국 · 금 ↔ 미국 은 조금씩 같이 움직이게 (상관계수가 0 이 아니게). px_date 는 마지막 날보다 이틀 앞 (cut_at 이 뒤를 잘라요)."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2023-06-01", periods=n)
    common = rng.normal(0, 0.008, n)
    kr = pd.Series(common + rng.normal(0, 0.012, n), index=days).drop(days[rng.choice(n, 25, replace=False)])
    us = pd.Series(0.5 * common + rng.normal(0, 0.009, n), index=days).drop(days[rng.choice(n, 20, replace=False)])
    fx = pd.Series(1300 * np.exp(np.cumsum(rng.normal(0, 0.004, n))), index=days).drop(days[rng.choice(n, 10, replace=False)])
    g = pd.Series(1900 * np.exp(np.cumsum(0.3 * us.reindex(days).fillna(0).values + rng.normal(0, 0.009, n))), index=days)
    g = g.drop(days[rng.choice(n, 15, replace=False)])
    bd = pd.Series(rng.normal(0, 0.003, n) - 0.1 * common, index=days).drop(days[rng.choice(n, 12, replace=False)])
    return dict(kr_bench=kr, us_bench=us, fx=fx, gold_usd=g if gold else None, bd_ret=bd if bond else None,
                px_date=days[-3].date())


def frame(i, cols):
    """한국 · 미국(원화) + cols 열이 모두 있는 날 (px_date 까지) — 시험이 따로 계산하는 표."""
    fxr = i["fx"].pct_change()
    parts = [i["kr_bench"].rename("kr"), (i["us_bench"] + fxr.reindex(i["us_bench"].index).fillna(0)).rename("us")]
    if "mt" in cols:
        g = i["gold_usd"]
        parts.append((g.pct_change() + fxr.reindex(g.index).fillna(0)).dropna().rename("mt"))
    if "bd" in cols:
        parts.append(i["bd_ret"].rename("bd"))
    return F.cut_at(pd.concat(parts, axis=1).dropna(), i["px_date"])


def expect(i, cols, us_vol_krw=None):
    j = frame(i, cols)
    c = j.corr()
    r = lambda a, b: round(float(c.loc[a, b]), 2)
    out = {"mktVol": F.ann_vol(j["kr"].values), "usVol": us_vol_krw or F.ann_vol(j["us"].values), "rhoKrUs": r("kr", "us")}
    if "mt" in cols:
        out.update(mtVol=F.ann_vol(j["mt"].values), rhoKrMt=r("kr", "mt"), rhoUsMt=r("us", "mt"))
    if "bd" in cols:
        out.update(bdVol=F.ann_vol(j["bd"].values), rhoKrBd=r("kr", "bd"), rhoUsBd=r("us", "bd"))
    if "mt" in cols and "bd" in cols:
        out["rhoMtBd"] = r("mt", "bd")
    return {k: out[k] for k in KEYS if k in out}, len(j)


def run(i, us_vol_krw=None):
    return F.market_assumptions(i["kr_bench"], i["us_bench"], i["fx"], i["gold_usd"], i["bd_ret"], i["px_date"], us_vol_krw)


def run_old(i, us_vol_krw=None):
    return old_block(i["kr_bench"], i["us_bench"], i["fx"], i["gold_usd"], i["bd_ret"], i["px_date"], us_vol_krw)


def no_nan(d):
    json.dumps(d, allow_nan=False)
    return all(isinstance(v, float) and np.isfinite(v) for v in d.values())


# ── 1. 모두 있으면 예전과 똑같아요 ─────────────────────────────
@pytest.mark.parametrize("seed", [1, 2, 3, 11, 42])
@pytest.mark.parametrize("us_vol_krw", [None, 19.3])
def test_all_present_is_exactly_the_old_output(seed, us_vol_krw):
    i = inputs(seed)
    new, lines = run(i, us_vol_krw)
    old, old_lines = run_old(i, us_vol_krw)
    assert list(new.items()) == list(old.items())              # 같은 값 · 같은 칸 순서 (data.json 에 쓰는 순서)
    assert tuple(new) == KEYS and no_nan(new)
    n = len(frame(i, ("mt", "bd")))
    assert lines == [f"· 시장 가정 계산 완료 ({n:,}일, ~{i['px_date']}): 10 / 10칸 — {new}"]
    assert old_lines[0].startswith(f"· 시장 가정 계산 완료 ({n:,}일, ~{i['px_date']}): ")      # 같은 표 (같은 날 수)
    assert all(-1 <= new[k] <= 1 for k in KEYS if k.startswith("rho")) and new["rhoKrUs"] != 0 and new["rhoUsMt"] != 0


def test_the_old_block_here_is_mains_old_code():
    """비교에 쓰는 old_block 이 정말 예전 main 의 코드인지: 예전 조건 · 식이 그대로 있어요 (main 에서는 빠졌어요 — 아래 시험)."""
    src = inspect.getsource(old_block)
    assert 'if len(j) > F.MIN_DAYS and "mt" in j.columns:' in src
    assert '"usVol": us_vol_krw or F.ann_vol(j["us"].values),' in src
    assert "시장 가정 계산에 쓸 날이" in src


@pytest.mark.parametrize("seed", [1, 5])
def test_bond_missing_is_also_the_old_output(seed):
    """채권 대표 시계열이 없는 날은 예전에도 금 · 한국 · 미국 6칸을 계산했어요 — 같은 값 · 같은 순서 · 채권 4칸만 빠졌다고 로그에."""
    i = inputs(seed, bond=False)
    new, lines = run(i)
    old, _ = run_old(i)
    assert list(new.items()) == list(old.items()) and tuple(new) == ("mktVol", "usVol", "mtVol", "rhoKrUs", "rhoKrMt", "rhoUsMt")
    assert lines[0].startswith("  !! 시장 가정 일부만 계산 (") and "6 / 10칸" in lines[0]
    assert lines[1:] == [f"  !! 시장 가정: 채권 대표 시계열(148070)을 받지 못해 채권 관련 4칸(bdVol · rhoKrBd · rhoUsBd · rhoMtBd)은 {LEFT}"]


# ── 2. 금값을 받지 못해도 나머지는 계산해요 ─────────────────────
@pytest.mark.parametrize("gold", [None, "empty"])
def test_gold_missing_keeps_korea_us_and_bond(gold):
    i = inputs(7)
    i["gold_usd"] = None if gold is None else pd.Series([], dtype=float)
    new, lines = run(i, 19.3)
    want, n = expect(i, ("bd",), 19.3)
    assert new == want and tuple(new) == ("mktVol", "usVol", "rhoKrUs", "bdVol", "rhoKrBd", "rhoUsBd") and no_nan(new)
    assert not set(GOLD) & set(new) and set(KRUS) <= set(new) and new["usVol"] == 19.3
    assert run_old(i, 19.3)[0] == {}                                      # 예전: 10칸 모두 빠졌어요
    assert lines[0] == f"  !! 시장 가정 일부만 계산 ({n:,}일, ~{i['px_date']}): 6 / 10칸 — {new}"
    assert lines[1:] == [f"  !! 시장 가정: 국제 금값(GC=F)을 받지 못해 금 관련 4칸(mtVol · rhoKrMt · rhoUsMt · rhoMtBd)은 {LEFT}"]
    assert not any("일뿐" in x for x in lines)                            # 날 수가 아니라 금값이 이유예요


def test_gold_and_bond_missing_keeps_korea_us():
    i = inputs(8, gold=False, bond=False)
    new, lines = run(i)
    want, n = expect(i, ())
    assert new == want and tuple(new) == KRUS and no_nan(new)
    assert lines == [
        f"  !! 시장 가정 일부만 계산 ({n:,}일, ~{i['px_date']}): 3 / 10칸 — {new}",
        f"  !! 시장 가정: 국제 금값(GC=F)을 받지 못해 금 관련 3칸(mtVol · rhoKrMt · rhoUsMt)은 {LEFT}",
        f"  !! 시장 가정: 채권 대표 시계열(148070)을 받지 못해 채권 관련 3칸(bdVol · rhoKrBd · rhoUsBd)은 {LEFT}",
        f"  !! 시장 가정: 국제 금값(GC=F)을 받지 못해 · 채권 대표 시계열(148070)을 받지 못해 금·채권 관련 1칸(rhoMtBd)은 {LEFT}",
    ]


# ── 3. 날이 모자라면 진짜 이유와 함께 ─────────────────────────
def test_too_few_korea_us_days_gives_no_key_and_the_true_reason():
    i = inputs(9, n=240)
    new, lines = run(i)
    n = len(frame(i, ()))
    assert n <= F.MIN_DAYS and new == {} and run_old(i)[0] == {}
    assert lines == [f"  !! 시장 가정: 한국(KOSPI) · 미국(S&P 500) 수익률이 함께 있는 날이 {n:,}일뿐이라 ({F.MIN_DAYS}일 넘게 필요) "
                     f"10칸 모두 {LEFT}"]


def test_short_gold_leaves_out_only_the_gold_keys():
    """금값이 최근 120일만 왔어요: 예전에는 표 전체가 120일 남짓이라 10칸 모두 빠졌어요 ('날이 N일뿐'). 이제 금 칸만 빠져요."""
    i = inputs(10)
    i["gold_usd"] = i["gold_usd"].iloc[-120:]
    new, lines = run(i)
    want, n = expect(i, ("bd",))
    ng = len(frame(i, ("mt",)))
    assert ng <= F.MIN_DAYS and new == want and not set(GOLD) & set(new) and no_nan(new)
    old, old_lines = run_old(i)
    assert old == {} and "시장 가정 계산에 쓸 날이" in old_lines[0]
    assert lines[1:] == [f"  !! 시장 가정: 국제 금값(GC=F)이 한국 · 미국과 함께 있는 날이 {ng:,}일뿐이라 ({F.MIN_DAYS}일 넘게 필요) 금 관련 "
                         f"4칸(mtVol · rhoKrMt · rhoUsMt · rhoMtBd)은 {LEFT}"]


def test_gold_and_bond_each_long_enough_but_not_together():
    """금은 앞쪽 520일 · 채권은 뒤쪽 500일 — 하나씩은 넉넉하지만 넷이 함께 있는 날은 모자라요: 날이 더 적은 채권을 빼고 금으로 계산해요."""
    i = inputs(12)
    i["gold_usd"] = i["gold_usd"].iloc[:520]
    i["bd_ret"] = i["bd_ret"].iloc[-500:]
    assert len(frame(i, ("mt", "bd"))) <= F.MIN_DAYS < min(len(frame(i, ("mt",))), len(frame(i, ("bd",))))
    nb = len(frame(i, ("bd",)))
    assert len(frame(i, ("mt",))) > nb
    new, lines = run(i)
    want, _n = expect(i, ("mt",))
    assert new == want and tuple(new) == ("mktVol", "usVol", "mtVol", "rhoKrUs", "rhoKrMt", "rhoUsMt") and no_nan(new)
    four = len(frame(i, ("mt", "bd")))
    assert lines[1:] == [f"  !! 시장 가정: 금 · 채권 · 한국 · 미국이 모두 함께 있는 날이 {four:,}일뿐이라 ({F.MIN_DAYS}일 넘게 필요) 날이 더 "
                         f"적은 채권 대표 시계열(148070)({nb:,}일)을 빼서 채권 관련 4칸(bdVol · rhoKrBd · rhoUsBd · rhoMtBd)은 {LEFT}"]


# ── 4. 이상한 값 ───────────────────────────────────────────
def test_a_broken_gold_series_does_not_stop_the_rest():
    """금 열을 원화 수익률로 바꾸다 오류가 나도 (숫자가 아닌 값) 한국 · 미국 · 채권 칸은 계산하고 오류를 이유로 적어요."""
    i = inputs(13)
    i["gold_usd"] = pd.Series(["x"] * 300, index=i["gold_usd"].index[:300])
    new, lines = run(i)
    want, _n = expect(i, ("bd",))
    assert new == want and not set(GOLD) & set(new)
    assert len(lines) == 2 and lines[1].startswith("  !! 시장 가정: 국제 금값(GC=F)을 표에 넣다가 오류가 나 (TypeError: ")
    assert lines[1].endswith(f"금 관련 4칸(mtVol · rhoKrMt · rhoUsMt · rhoMtBd)은 {LEFT}")


def test_nan_or_out_of_range_values_are_left_out_with_the_reason():
    """채권 수익률이 모두 0: 변동성 0 (ann_vol 이 None) · 상관계수 NaN — 예전에는 null 로 썼어요. 이제 칸을 넣지 않고 이유를 적어요 (JSON 에 NaN 없음)."""
    i = inputs(14)
    i["bd_ret"] = pd.Series(0.0, index=i["bd_ret"].index)
    with np.errstate(all="ignore"):
        new, lines = run(i)
    assert tuple(new) == ("mktVol", "usVol", "mtVol", "rhoKrUs", "rhoKrMt", "rhoUsMt") and no_nan(new)
    assert lines[1:] == [f"  !! 시장 가정: 계산한 값이 숫자가 아니거나 범위를 벗어나 4칸(bdVol · rhoKrBd · rhoUsBd · rhoMtBd)은 {LEFT}"]


# ── 5. main 이 이 함수를 불러요 ─────────────────────────────
def test_main_uses_the_function_and_the_old_condition_is_gone():
    src = inspect.getsource(F.main)
    assert "market_assumptions(kr_bench, us_bench, fx, gold_usd, bd_ret, px_date, us_vol_krw)" in src
    assert "settings.update(mkt)" in src
    assert '"mt" in j.columns' not in src and "시장 가정 계산에 쓸 날이" not in src
    assert F.MKT_KEYS is V.MKT_KEYS and tuple(V.MKT_KEYS) == KEYS        # 칸 목록은 관문 파일 한 곳 (같은 순서)


# ── 6. 관문: 경고만 ────────────────────────────────────────
def row(rep):
    got = [r for r in rep.rows if r[0] == V.MKT_ROW]
    assert len(got) == 1, rep.rows
    return got[0]


def full():
    return {k: 1.0 for k in KEYS}


def test_gate_row_passes_when_all_ten_are_numbers():
    rep = V.Report()
    V.check_mkt_settings(rep, {"settings": {"rf": 3.8, **full()}}, {"settings": full()})
    assert row(rep) == (V.MKT_ROW, "10칸 모두 있음", row(rep)[2], "PASS") and not rep.failed


def test_gate_row_names_missing_keys_and_those_the_previous_publish_had():
    st = {k: v for k, v in full().items() if k not in GOLD}
    rep = V.Report()
    V.check_mkt_settings(rep, {"settings": st}, {"settings": full()})
    r = row(rep)
    assert r[3] == "WARN" and not rep.failed
    assert r[1] == ("빠짐 4 / 10칸: mtVol · rhoKrMt · rhoUsMt · rhoMtBd (지난 발행본에는 있던 칸 4: mtVol · rhoKrMt · rhoUsMt · rhoMtBd) "
                    "— 실행 로그의 '시장 가정' 줄에 이유")
    rep = V.Report()                                                    # 사이트 점검 (지난 발행본 없음) · 지난 발행본에도 없던 칸
    V.check_mkt_settings(rep, {"settings": st}, None)
    assert row(rep)[3] == "WARN" and "지난 발행본" not in row(rep)[1] and row(rep)[1].startswith("빠짐 4 / 10칸: mtVol")


@pytest.mark.parametrize("bad", [None, "36.8", True, float("nan"), float("inf"), [1.0]])
def test_gate_row_counts_a_non_number_as_missing(bad):
    rep = V.Report()
    V.check_mkt_settings(rep, {"settings": {**full(), "rhoKrUs": bad}}, None)
    assert row(rep)[3] == "WARN" and row(rep)[1].startswith("빠짐 1 / 10칸: rhoKrUs") and not rep.failed


@pytest.mark.parametrize("data", [{}, {"settings": None}, {"settings": [1]}, None, "x"])
def test_gate_row_on_odd_files_warns_never_fails(data):
    rep = V.Report()
    V.check_mkt_settings(rep, data, {"settings": "odd"})
    assert row(rep)[3] == "WARN" and row(rep)[1].startswith("빠짐 10 / 10칸") and not rep.failed


def test_gate_row_crash_is_a_warning(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("시험")
    monkeypatch.setattr(V, "_check_mkt_settings", boom)
    rep = V.Report()
    V.check_mkt_settings(rep, {"settings": full()}, None)
    assert row(rep) == (V.MKT_ROW, "검사가 오류로 멈췄어요: RuntimeError", "오류 없이 끝나야 함 (경고만 · 발행을 막지 않아요)", "WARN")
    assert not rep.failed


@pytest.mark.parametrize("mode", ["publish", "live"])
def test_gate_row_in_run_checks_warns_only(mode):
    """발행 관문과 사이트 점검 모두 한 줄 · 빠진 칸이 있어도 실패 줄은 늘지 않아요 (다른 줄은 그대로)."""
    import datetime as dt
    from fixture_data import hilo_of
    cur, prev, final = good_pair()
    today = dt.date(2026, 10, 31)
    now = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
    sessions = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}

    def go(c, p):
        return V.run_checks(c, p if mode == "publish" else None, final, today, mode=mode, count_between=lambda a, b: 1,
                            sessions=sessions, now=now, hilo=hilo_of(c, V.MUST))
    prev["data"]["settings"].update(full())
    cur["data"]["settings"].update(full())
    base = go(cur, prev)
    assert row(base)[3] == "PASS"
    for k in GOLD:
        del cur["data"]["settings"][k]
    rep = go(cur, prev)
    assert row(rep)[3] == "WARN" and ("지난 발행본에는 있던 칸 4" in row(rep)[1]) == (mode == "publish")
    assert [r for r in rep.rows if r[0] != V.MKT_ROW] == [r for r in base.rows if r[0] != V.MKT_ROW]
    assert {r[0] for r in rep.failed} == {r[0] for r in base.failed}
