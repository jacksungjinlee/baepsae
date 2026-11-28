# -*- coding: utf-8 -*-
"""한국 무상증자 → data.json splits 의 새 종류 (2026-11-28 · Jack 2026-11-27 답 11 "무상증자 is the next PR right after #186, not later" · 새 시험 파일).

Jack 의 답 4 (그대로): "yes, as long as the filing text is cross-checked against the change in share count and the price jump on the effective date."
무상증자는 두 날이에요: 권리락 날 (KRX 기준가 = 앞날 종가 ÷ m · 주식 수 그대로) · 몇 주 뒤 신주 상장일 (주식 수 × m · 기준가 그대로). 세 확인
(fetch_data.kr_bonus_checks): 공시 (신주상장예정일 = 상장일 · 신주배정기준일이 그 권리락 날의 기준일) · 권리락 기준가 (± 1%) · 상장일 주식 수 (± 1%).
m = 1 + 새 주식 ÷ 증자 전 주식 (공시의 두 수 · 자기주식도 세어요) · 줄의 배율 r = 1 + x (주주 한 사람의 1주당 신주 수) — 자기주식은 받지 않아서 m ≤ r.
줄의 날짜 = 권리락 날 (그날부터 주가가 새 기준). 싣는 스위치 KR_BONUS_ROWS_ON 은 꺼져 있어요 (기록 시트의 분할 줄이 무상증자에는 맞지 않아요 — PR 의 질문).

픽스처: tests/fixtures/kr_bonus (2026-11-28 에 받은 진짜 DART 응답 · 키 없음 · 다음 일별 시세의 사건 앞뒤 줄) · tests/fixtures/dvwhy · v196b 의 진짜 결정.
"""
import collections
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
TODAY = dt.date(2026, 11, 28)
CORP = {"084010": "00113225", "183300": "00997812", "020400": "00191287", "262840": "01146822", "356860": "00920379", "290650": "01181515",
        "220100": "01053540", "480370": "01210677", "462350": "01700587", "086280": "00360595", "196170": "00989619", "472850": "01806951",
        "425040": "01301252", "000500": "00104768", "950220": "00000950", "000010": "00000010"}
# 진짜 결정: (종목) → (목록 픽스처, {API: 픽스처})
REAL = {"084010": ("dvwhy/084010_list_B001.json", {"fricDecsn.json": "dvwhy/084010_fricDecsn.json"}),
        "183300": ("dvwhy/183300_list_B001.json", {"fricDecsn.json": "dvwhy/183300_fricDecsn.json"}),
        "020400": ("dvwhy/020400_list_B001.json", {"fricDecsn.json": "dvwhy/020400_fricDecsn.json"}),
        "262840": ("dvwhy/262840_list_B001.json", {"fricDecsn.json": "dvwhy/262840_fricDecsn.json"}),
        "356860": ("dvwhy/356860_list_B001.json", {"pifricDecsn.json": "dvwhy/356860_pifricDecsn.json"}),
        "290650": ("kr_bonus/290650_list_B001.json", {"pifricDecsn.json": "v196b/detail_pifric_290650.json"}),
        "220100": ("kr_bonus/220100_list_B001.json", {"pifricDecsn.json": "v196b/detail_pifric_220100.json"}),
        "480370": ("kr_bonus/480370_list_B001.json", {"fricDecsn.json": "kr_bonus/480370_fricDecsn.json"}),
        "462350": ("kr_bonus/462350_list_B001.json", {"fricDecsn.json": "kr_bonus/462350_fricDecsn.json", "pifricDecsn.json": "kr_bonus/462350_pifricDecsn.json"}),
        "086280": ("kr_bonus/086280_list_B001.json", {"fricDecsn.json": "kr_bonus/086280_fricDecsn.json"}),
        "196170": ("kr_bonus/196170_list_B001.json", {"fricDecsn.json": "kr_bonus/196170_fricDecsn.json"}),
        "472850": ("kr_bonus/472850_list_B001.json", {"fricDecsn.json": "kr_bonus/472850_fricDecsn.json"}),
        "425040": ("kr_bonus/425040_list_B001.json", {"fricDecsn.json": "kr_bonus/425040_fricDecsn.json"}),
        "000500": ("kr_bonus/000500_list_B001.json", {"fricDecsn.json": "kr_bonus/000500_fricDecsn.json"})}


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


DAUM = fx("kr_bonus/daum_rows.json")
SEED = F.load_kr_bonus_seed()


def seq(code):
    """다음 줄 → kr_bonus_pairs 의 [(날짜, 종가, 기준가, 상장주식수)] (기준가 = 전일 종가 칸, 없으면 종가 − 전일 대비)."""
    out = []
    for d, tp, pc, ch, sh in DAUM[code]:
        base = pc if pc else (tp - ch if tp is not None and ch is not None else None)
        out.append((d, tp, base, sh))
    return out


def seed_of(code, d=None):
    xs = [c for c in SEED if c["t"] == code and (d is None or c["d"] == d)]
    assert xs, (code, d)
    return dict(xs[0])


class Log:
    def __init__(self, monkeypatch):
        self.lines = []
        monkeypatch.setattr(F, "log", lambda *a: self.lines.append(" ".join(str(x) for x in a)))

    def has(self, *words):
        return any(all(w in ln for w in words) for ln in self.lines)


class FakeDart:
    """DartClient 처럼 (get · status · entries · lock · mode · started_empty · no_call · fatal · down · meta). lists {기업코드: B001 목록} ·
    api {(기업코드, 끝점): 응답} · fail 모든 호출이 None (연결 실패) · reply {끝점: 그 응답} (상태 시험)."""

    def __init__(self, lists=None, api=None, fail=False, reply=None, mode="cache", empty=False, no_call=None):
        self.lists, self.api, self.fail, self.reply = dict(lists or {}), dict(api or {}), fail, dict(reply or {})
        self.status, self.entries, self.lock = collections.Counter(), {}, threading.Lock()
        self.mode, self.started_empty, self.no_call, self.fatal, self.down = mode, empty, no_call, None, None
        self.meta = {"corpMap": dict(CORP)}
        self.calls = []

    def get(self, ep, params):
        self.calls.append((ep, dict(params)))
        if self.fail:
            self.status["예외"] += 1
            return None
        if ep in self.reply:
            j = self.reply[ep]
            self.status[str(j.get("status"))] += 1
            return dict(j)
        j = self.lists.get(params["corp_code"]) if ep == "list.json" and params.get("pblntf_detail_ty") == "B001" else self.api.get((params["corp_code"], ep))
        if j is None:
            self.status["013"] += 1
            return {"status": "013", "message": "조회된 데이타가 없습니다."}
        self.status[str(j.get("status"))] += 1
        return j

    def get_zip(self, ep, params):
        self.status["예외"] += 1
        return None


def real_dart(*codes, **kw):
    lists, api = {}, {}
    for t in codes:
        lst, eps = REAL[t]
        lists[CORP[t]] = fx(lst)
        for ep, f in eps.items():
            api[(CORP[t], ep)] = fx(f)
    return FakeDart(lists=lists, api=api, **kw)


def kr_rows(*codes, cap=1.0, pxd=None):
    return [{"t": t, "nk": t, "cls": "kr", "cap": cap, **({"pxd": pxd} if pxd else {})} for t in codes]


# ── 1. 시세 규칙: 진짜 다음 줄에서 두 날 ────────────────────────────────────────────────────────────────────────────────────
def test_market_pairs_on_real_daum_rows():
    """대한제강 2026-01-05 권리락 (19,600 → 기준가 13,070 · ÷ 1.4996) → 01-26 상장 (22,914,397 → 34,371,596 · × 1.5000) · 코미코 · 티엘비 (07-17 제헌절 휴장 —
    기준일 07-20 의 권리락은 07-16) · 이노스페이스 2025-11 (유무상증자: 11-28 유상 몫 상장은 건너뛰고 12-11 무상 몫 상장 × 1.5)."""
    got = {c: F.kr_bonus_pairs(c, seq(c), "daum") for c in ("084010", "183300", "356860", "462350", "480370")}
    x = got["084010"]
    assert [(c["d"], c["dl"], c["n1"], c["n2"]) for c in x] == [("2026-01-05", "2026-01-26", "2026-01-06", "2026-01-07")]
    assert x[0]["close"] == 19600 and x[0]["base"] == 13070 and x[0]["sa"] == 22914397 and x[0]["sb"] == 34371596
    assert [(c["d"], c["dl"]) for c in got["183300"]] == [("2026-05-26", "2026-06-15")]
    assert [(c["d"], c["n1"]) for c in got["356860"]] == [("2026-07-16", "2026-07-20")]
    assert [(c["d"], c["dl"]) for c in got["462350"]] == [("2025-11-20", "2025-12-11"), ("2026-06-18", "2026-07-09")]
    assert [(c["d"], c["dl"]) for c in got["480370"]] == [("2026-02-27", "2026-03-27")]          # 상장 전날 자기주식 소각 (주식 수 −1%) 도 건너뛰어요


def test_market_rule_refuses_rights_issue_and_same_day_events():
    """주주배정 유상증자 (950220 · 권리락 ÷ 1.16 → 상장 × 1.66: 둘이 맞지 않아요) 는 후보가 아니에요. 하루짜리 (기준가와 주식 수가 같은 날) 는 #186 의 일이에요."""
    assert F.kr_bonus_pairs("950220", seq("950220"), "daum") == []
    rows = [("2026-01-02", 1000.0, 1000.0, 100.0), ("2026-01-05", 500.0, 500.0, 200.0), ("2026-01-06", 500.0, 500.0, 200.0)]
    assert F.kr_bonus_pairs("000010", rows, "daum") == []                                    # 앞날 종가 1,000 · 기준가 500 · 주식 수 × 2 가 같은 날
    assert F.kr_bonus_market(1000, 500, 100, 203) is not None and F.kr_bonus_market(1000, 500, 100, 205) is None   # ± 2%
    assert F.kr_bonus_market(1100, 1000, 100, 110) is None                                   # 10% 이하 (작은 무상증자 · 주식배당은 '그대로' — SHARE_SAME)


def test_window_lo_hi_and_krx_list_path():
    """다음 창 (지난 발행본 뒤 ~ 오늘): 상장일이 창 안이면 권리락 날은 창 앞이어도 돼요. 목록 파일 길 (kr_bonus_cands) 도 같은 사건을 찾고, 그 사이 거래일
    파일이 빠졌으면 멈춰요 (상장일을 몰라요)."""
    s = seq("084010")
    assert [c["d"] for c in F.kr_bonus_pairs("084010", s, "daum", lo="2026-01-20", hi="2026-01-27")] == ["2026-01-05"]
    assert F.kr_bonus_pairs("084010", s, "daum", lo="2026-01-26", hi="2026-01-27") == []      # 지난 실행이 이미 봤어요
    import pandas as pd
    files = [(d, pd.DataFrame({"Code": ["084010"], "Stocks": [sh], "Close": [tp], "Changes": [ch]})) for d, tp, pc, ch, sh in reversed(DAUM["084010"])]
    ev = [("084010", "2026-01-05", 19600.0, 13070.0)]
    days = [r[0] for r in DAUM["084010"]]
    got = F.kr_bonus_cands(files, ev, days)
    assert [(c["d"], c["dl"], c["src"]) for c in got] == [("2026-01-05", "2026-01-26", "krx")]
    holes = [f for f in files if f[0] != "2026-01-15"]
    assert F.kr_bonus_cands(holes, ev, days) == []


def test_seed_file_reruns_the_rule_and_refuses_a_bad_line(tmp_path):
    """시드 144줄 (2023-10-19 ~ · 진짜 다음 줄) 은 줄마다 시세 규칙을 다시 지나요. 한 줄이라도 틀리면 파일을 통째로 받지 않아요."""
    assert len(SEED) == 144 and all(c["d"] >= "2023-10-19" and c["src"] == "seed" for c in SEED)
    lines = open(F.KR_BONUS_SEED_PATH, encoding="utf-8").read().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("084010,"))
    bad = list(lines)
    bad[i] = bad[i].replace(",13070,", ",19000,")                                          # 기준가가 움직이지 않은 날
    p = tmp_path / "s.csv"
    p.write_text("\n".join(bad) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        F.load_kr_bonus_seed(str(p))


# ── 2. 세 확인: 진짜 결정 15건 모두 지나요 · 하나씩 틀리면 그 확인이 막아요 ────────────────────────────────────────────────────────
REAL_EVENTS = [("084010", "2026-01-05", 1.6616554), ("183300", "2026-05-26", 2.0), ("020400", "2026-04-10", 2.0), ("262840", "2024-04-18", 2.0),
               ("356860", "2026-07-16", 2.0), ("290650", "2026-10-26", 2.0), ("220100", "2026-09-17", 1.2), ("480370", "2026-02-27", 3.0),
               ("462350", "2025-11-20", 1.5), ("462350", "2026-06-18", 1.2), ("086280", "2024-07-12", 2.0), ("196170", "2026-08-05", 1.3),
               ("472850", "2026-01-02", 1.780175), ("425040", "2024-01-02", 2.0), ("000500", "2026-06-30", 1.8)]


@pytest.mark.parametrize("code,d,r", REAL_EVENTS)
def test_three_checks_pass_on_every_real_filing(code, d, r):
    """기준가의 비 ÷ m − 1: −0.575% (씨케이솔루션) ~ +0.003% · 상장일 주식 수 ÷ m − 1: 0 (씨케이솔루션 +0.661%, 상장 전날 자기주식 소각) — 선 ± 1%."""
    c = seed_of(code, d)
    v, why = F.kr_bonus_dart(real_dart(code), CORP[code], c, TODAY)
    assert why is None and v["v"] == "ok" and v["r"] == r, (v, why)
    chk, bad = F.kr_bonus_checks(v, c)
    assert bad is None and chk["rule"] == "bonus" and chk["dx"] == d and chk["dl"] == c["dl"]
    assert abs(chk["px"] / chk["m"] - 1) <= 0.006 and abs(chk["shr"] / chk["m"] - 1) <= 0.007
    assert chk["m"] <= r + 1e-9                                                              # 자기주식은 새 주식을 받지 않아요 (m ≤ r)


def _ev(code, d):
    c = seed_of(code, d)
    v, _ = F.kr_bonus_dart(real_dart(code), CORP[code], c, TODAY)
    return c, {k: v[k] for k in ("k", "src", "rc", "x", "r", "n", "b", "dr", "dl")}


def test_each_check_refuses():
    c, e = _ev("183300", "2026-05-26")                                   # 코미코 x 1 · m 1.96405
    assert F.kr_bonus_checks(e, c)[1] is None
    assert F.kr_bonus_checks(e, {**c, "base": c["base"] * 1.011})[1] == "px"          # 권리락 기준가가 1% 넘게 달라요
    assert F.kr_bonus_checks(e, {**c, "sb": c["sa"] * 1.94})[1] == "shr"               # 상장일 주식 수가 1% 넘게 적어요
    assert F.kr_bonus_checks(e, {**c, "sb": c["sa"] * 1.99})[1] == "shr"               # 많아요
    assert F.kr_bonus_checks({**e, "dl": "2026-06-16"}, c)[1] == "date"                # 공시의 상장예정일이 그날이 아니에요
    assert F.kr_bonus_checks({**e, "dr": "2026-05-28"}, c)[1] == "date"                # 기준일이 그 권리락 날의 기준일이 아니에요 (하루 늦음)
    assert F.kr_bonus_checks({**e, "dr": "2026-05-26"}, c)[1] == "date"                # 권리락 날 자체
    assert F.kr_bonus_checks({**e, "r": 2.5}, c)[1] == "diff"                          # r ≠ 1 + x
    assert F.kr_bonus_checks({**e, "x": 3.0, "r": 4.0}, c)[1] == "diff"                # 자기주식 몫 1 − 0.964 ÷ 3 = 68% > 50% (잘못 읽은 공시)
    assert F.kr_bonus_checks({**e, "n": e["b"] * 1.2}, c)[1] == "diff"                 # 새 주식이 x × 증자 전 주식보다 많아요 (자기주식 < 0)


def test_non_whole_ratio_is_the_filings_exact_r():
    """대한제강 x 0.6616554 (발행주식의 0.5 를 자기주식이 아닌 주식에만) → r 1.6616554 (배당 기준 증명과 같은 값 · 반올림하지 않아요) · m 1.5 ·
    폰드그룹 x 0.780175 → r 1.780175. 둘 다 깨끗한 분수가 아니에요 (관문의 깨끗한 배율 줄)."""
    _c, e = _ev("084010", "2026-01-05")
    assert e["r"] == 1.6616554 and e["x"] == 0.6616554 and abs(1 + e["n"] / e["b"] - 1.5) < 1e-7
    _c, e2 = _ev("472850", "2026-01-02")
    assert e2["r"] == 1.780175
    assert not F.split_is_clean(e["r"]) and not V.simple_ratio(e["r"]) and not F.split_is_clean(e2["r"])
    assert F.split_is_clean(1.3) and F.split_is_clean(1.2) and V.simple_ratio(1.8)


def test_rights_and_bonus_issue_reads_only_the_bonus_part():
    """유무상증자 (pifricDecsn): 무상 몫 (fric_*) 만 사건이에요 — 이노스페이스 2025-11: 유상 4,300,000 주 (청약한 사람만) · 무상 x 0.5 → r 1.5 (증자 전
    주식 13,716,694 = 유상 뒤) · 티엘비 · 엘앤씨바이오 · 퓨쳐켐 도 무상 몫의 기준일 · 상장일로 확인. 유상 몫은 줄이 되지 않아요."""
    ev, bad = F.parse_kr_bonus(fx("kr_bonus/462350_pifricDecsn.json")["list"], pre="fric_")
    assert bad == [] and [(e["r"], e["n"], e["b"], e["dr"], e["dl"], e["src"]) for e in ev] == [(1.5, 6858347.0, 13716694.0, "2025-11-21", "2025-12-11", "pifric")]
    v, _ = F.kr_bonus_dart(real_dart("462350"), CORP["462350"], seed_of("462350", "2025-11-20"), TODAY)
    assert v["src"] == "pifric" and v["rc"] == "20251106000107"
    # 우선주 (기타주식) 는 그 칸으로: 이노스페이스 0.5
    ep, _ = F.parse_kr_bonus(fx("kr_bonus/462350_pifricDecsn.json")["list"], pre="fric_", pref=True)
    assert [(e["x"], e["n"], e["b"]) for e in ep] == [(0.5, 745430.0, 1490860.0)]
    # 유상 몫과 무상 몫의 권리락이 같은 날이면 기준가가 둘을 함께 반영해 px 가 맞지 않아요 → 싣지 않아요
    c, e = _ev("462350", "2025-11-20")
    assert F.kr_bonus_checks(e, {**c, "base": c["close"] / 1.62})[1] == "px"


def test_dart_answers_and_failures():
    """DART 가 실제로 답한 것만 판정 (#186 과 같아요): 결정 없음 → nodoc · 목록에 있는데 API 013 → unread · 다른 상장일 → diff. 연결 실패 · 020 · 800 ·
    000 인데 빈 목록은 판정이 아니에요 (기다림 — 절대 '없음' 이 아니에요). 철회한 결정은 빼요."""
    c = seed_of("183300", "2026-05-26")
    corp = CORP["183300"]
    lst = fx("dvwhy/183300_list_B001.json")
    no_bonus = {**lst, "list": [x for x in lst["list"] if "무상증자" not in x["report_nm"]]}
    assert F.kr_bonus_dart(FakeDart(lists={corp: no_bonus}), corp, c, TODAY)[0]["code"] == "nodoc"
    assert F.kr_bonus_dart(FakeDart(lists={corp: lst}), corp, c, TODAY)[0]["code"] == "unread"          # fricDecsn 이 013
    v, _ = F.kr_bonus_dart(real_dart("183300"), corp, {**c, "dl": "2026-06-16"}, TODAY)
    assert v["v"] == "no" and v["code"] == "diff"
    for kw in ({"fail": True}, {"reply": {"list.json": {"status": "020"}}}, {"reply": {"list.json": {"status": "800"}}},
               {"reply": {"list.json": {"status": "000", "list": []}}}, {"reply": {"fricDecsn.json": {"status": "900"}}},
               {"reply": {"fricDecsn.json": {"status": "000", "list": []}}}):
        cl = real_dart("183300", **kw)
        v, why = F.kr_bonus_dart(cl, corp, c, TODAY)
        assert v is None and why[0] in ("net", "status"), (kw, v, why)
    wd = {**lst, "list": [dict(x, rm="철") if "무상증자" in x["report_nm"] else x for x in lst["list"]]}     # DART 비고 '철' = 철회된 결정
    cl = real_dart("183300")
    cl.lists[corp] = wd
    assert F.kr_bonus_dart(cl, corp, c, TODAY)[0]["code"] == "nodoc"


# ── 3. 단계: 줄 · 영수증 · 스위치 · 한도 · 발행을 막는 줄에 넣지 않음 ──────────────────────────────────────────────────────────
def _fields(client, bseed, kr=None, prev=None, per_run=None, today=TODAY, px="2026-11-27"):
    return F.kr_splits_fields(prev, kr or kr_rows(*{c["t"] for c in bseed}), [], client, today, seed=[], per_run=per_run, px_date=px, bseed=bseed)


def test_switch_off_confirms_but_publishes_no_row(monkeypatch):
    """스위치 꺼짐 (지금): 세 확인이 맞아도 splits 에 싣지 않아요 (held 'off') · 영수증은 splitsKr.bonus.rec 에 · nofile · runNew 에 들지 않아요."""
    Log(monkeypatch)
    assert F.KR_BONUS_ROWS_ON is False
    rows, info = _fields(real_dart("183300", "084010"), [seed_of("183300", "2026-05-26"), seed_of("084010", "2026-01-05")])
    b = info["bonus"]
    assert rows == [] and info["new"] == [] and info["nofile"] == [] and info["runNew"] == []
    assert sorted((x[0], x[1], x[3]) for x in b["held"]) == [("084010", "2026-01-05", "odd"), ("183300", "2026-05-26", "off")]
    assert {(x[0], x[3], x[5]) for x in b["rec"]} == {("183300", "bonus", "fric"), ("084010", "bonus", "fric")}
    assert all(V.kr_split_receipt_ok(x) for x in b["rec"])
    assert b["read"] == {"n": 2, "no": 0} and b["calls"] == 4 and info["calls"] == 4


def test_switch_on_publishes_clean_ratios_only(monkeypatch):
    """스위치를 켜면 (Jack 이 기록 줄을 승인한 뒤 · 다음 PR) 깨끗한 배율의 줄만 [코드, 권리락 날, r] 로 실려요 · 영수증은 splitsKr.rows 에. 깨끗하지 않은 r
    (대한제강 ×1.6616554) 은 관문의 '주식 분할 목록 (splits)' 깨끗한 배율 줄이 발행을 막아서 그대로 held 'odd'."""
    Log(monkeypatch)
    monkeypatch.setattr(F, "KR_BONUS_ROWS_ON", True)
    global CL1
    CL1 = real_dart("183300", "084010", "196170")
    rows, info = _fields(CL1,
                         [seed_of("183300", "2026-05-26"), seed_of("084010", "2026-01-05"), seed_of("196170", "2026-08-05")])
    assert rows == [["183300", "2026-05-26", 2.0], ["196170", "2026-08-05", 1.3]] and info["new"] == rows
    assert [(x[0], x[3]) for x in info["bonus"]["held"]] == [("084010", "odd")]
    rec = {(x[0], x[1]): x for x in info["rows"]}
    assert rec[("183300", "2026-05-26")][3:6] == ["bonus", "20260522000156", "fric"] and V.kr_split_receipt_ok(rec[("183300", "2026-05-26")])
    # 다음 실행: 지난 발행본의 줄 · 영수증이 그대로 이어져요 (보관본의 판정 · DART 호출 없음)
    prev = {"splits": rows, "splitsKr": info}
    cl2 = real_dart("183300", "084010", "196170")
    cl2.entries = dict(CL1.entries)
    rows2, info2 = _fields(cl2, [seed_of("183300", "2026-05-26"), seed_of("084010", "2026-01-05"), seed_of("196170", "2026-08-05")], prev=prev)
    assert rows2 == rows and info2["new"] == [] and sorted(info2["rows"]) == sorted(info["rows"]) and cl2.calls == []


def test_no_filing_is_logged_never_nofile_never_runnew(monkeypatch):
    """공시로 확인하지 못한 권리락 (결정 없음 · 맞지 않음): 줄 없음 · 숫자도 비우지 않음 (nofile · spNo 없음) · runNew · 필수 종목 줄에 넣지 않아요 · 크게 남겨요."""
    log = Log(monkeypatch)
    corp = CORP["183300"]
    lst = fx("dvwhy/183300_list_B001.json")
    cl = FakeDart(lists={corp: {**lst, "list": [x for x in lst["list"] if "무상증자" not in x["report_nm"]]}})
    rows, info = _fields(cl, [seed_of("183300", "2026-05-26")])
    assert rows == [] and info["nofile"] == [] and info["runNew"] == [] and info["nofileN"] == 0
    assert info["bonus"]["out"] == [["183300", "2026-05-26", "nodoc"]] and info["bonus"]["read"] == {"n": 1, "no": 1}
    assert info["read"] == {"n": 0, "no": 0, "doc": 0}                    # 분할의 '대부분 확인하지 못함' 경고 줄에도 세지 않아요
    assert log.has("!!", "한국 무상증자 — 공시로 확인하지 못한 권리락 1", "발행을 막는 줄에 넣지 않아요")


def test_dart_error_waits_and_is_never_a_no(monkeypatch):
    """DART 오류 (연결 · 한도 · 800) 는 판정이 아니에요: 보관하지 않고 다음 실행에 다시 (오늘 찾은 후보는 bonus.pend 에 이어 둬요)."""
    Log(monkeypatch)
    c = {**seed_of("183300", "2026-05-26"), "src": "daum"}
    cl = real_dart("183300", fail=True)
    rows, info = F.kr_splits_fields(None, kr_rows("183300"), [c], cl, TODAY, seed=[], px_date="2026-11-27", bseed=[])
    b = info["bonus"]
    assert rows == [] and b["out"] == [] and b["fail"] == [["183300", "2026-05-26", "net"]] and not any("krbonus" in k for k in cl.entries)
    assert b["pend"] == [F.kr_bonus_row_of(c)]
    again = F.kr_prev_bonus({"splitsKr": info})
    assert [(x["t"], x["d"], x["src"]) for x in again] == [("183300", "2026-05-26", "pend")]


def test_budget_is_shared_with_splits(monkeypatch):
    """한 실행의 50회를 함께 써요: 물을 무상증자 후보가 있으면 분할은 50 − 15 = 35 까지 · 무상증자는 남은 것을 · 합은 50 을 넘지 않아요. 무상증자 후보가
    없으면 분할은 예전처럼 50."""
    Log(monkeypatch)
    split_seed = [F._kr_cand(f"1{i:05d}", "2024-03-04", 10000, 2000, 1000, 5000, "seed") for i in range(40)]
    assert all(split_seed)

    class Both(FakeDart):
        def get(self, ep, params):
            if ep == "list.json" and params.get("pblntf_detail_ty") == "I001":
                self.calls.append((ep, dict(params)))
                self.status["013"] += 1
                return {"status": "013"}
            return super().get(ep, params)
    corp = dict(CORP, **{f"1{i:05d}": f"9{i:07d}" for i in range(40)})
    kr = kr_rows(*[c["t"] for c in split_seed], "183300", "084010", "196170")

    def run(bseed):
        cl = Both(lists={CORP[t]: fx(REAL[t][0]) for t in ("183300", "084010", "196170")},
                  api={(CORP[t], ep): fx(f) for t in ("183300", "084010", "196170") for ep, f in REAL[t][1].items()})
        cl.meta["corpMap"] = corp
        return F.kr_splits_fields(None, kr, [], cl, TODAY, seed=split_seed, px_date="2026-11-27", bseed=bseed)[1]
    with_b = run([seed_of("183300", "2026-05-26"), seed_of("084010", "2026-01-05"), seed_of("196170", "2026-08-05")])
    without = run([])
    assert without["calls"] <= 50 and without["bonus"]["calls"] == 0 and without["calls"] > 35
    assert with_b["calls"] <= 50 and with_b["bonus"]["calls"] == 6 and with_b["calls"] - with_b["bonus"]["calls"] <= 35


def test_no_bonus_input_leaves_split_results_unchanged(monkeypatch):
    """무상증자 후보가 없으면 #186 의 결과가 그대로예요 (bonus 칸만 더해져요)."""
    Log(monkeypatch)
    sp = [F._kr_cand("000010", "2026-11-02", 10000, 2000, 1000, 5000, "seed")]

    def run(**kw):
        cl = FakeDart()
        cl.meta["corpMap"] = {"000010": "00000010"}
        rows, info = F.kr_splits_fields(None, kr_rows("000010"), [], cl, TODAY, seed=sp, px_date="2026-11-27", **kw)
        return rows, {k: v for k, v in info.items() if k != "bonus"}
    assert run() == run(bseed=[])


def test_late_listing_waits_for_the_stock_price_date(monkeypatch):
    """종목이 자기 날짜(pxd · 마지막 확인 종가)에 머물러 있으면 그 날짜 뒤의 상장일은 다음 발행에 (late · 이어 둬요)."""
    Log(monkeypatch)
    c = {**seed_of("183300", "2026-05-26"), "src": "daum"}
    rows, info = F.kr_splits_fields(None, kr_rows("183300", pxd="2026-06-01"), [c], real_dart("183300"), TODAY, seed=[], px_date="2026-11-27", bseed=[])
    assert info["bonus"]["late"] == [["183300", "2026-05-26"]] and info["bonus"]["calls"] == 0 and len(info["bonus"]["pend"]) == 1


def test_carry_keeps_bonus_candidates_when_the_step_stops(monkeypatch):
    Log(monkeypatch)
    prev = {"splits": [], "splitsKr": {"bonus": {"pend": [F.kr_bonus_row_of(seed_of("183300", "2026-05-26")), ["bad"]]}}}
    rows, info = F.kr_splits_carry(prev, TODAY)
    assert info["bonus"]["src"] == "err" and info["bonus"]["pend"] == [F.kr_bonus_row_of(seed_of("183300", "2026-05-26"))]


def test_main_turns_bonus_on_and_the_krx_path_is_wired():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    m = src[src.index("def main("):]
    assert "kr_splits_step(sp_fields, prev, kr, client, today, kmeta.get(\"_krSplitCand\"), px_date=kmeta.get(\"pxDate\"), bonus=True)" in m
    assert "kr_bonus_cands([(px_date, listing)] + sessions, ref_events, ks_all.index)" in src


def test_daum_step_finds_a_bonus_and_does_not_hold_its_listing_day(monkeypatch):
    """kr_splits_step(bonus=True): 상장주식수가 지난 발행본보다 10% 넘게 바뀐 종목의 다음 줄에서 무상증자 두 날을 찾아요 · 그 상장일 (대동금속 2026-05-07
    × 2.000 — 깨끗한 비) 을 '짝이 아직인 거래정지 병합' 으로 다음 대기 (dq) 에 남기지 않아요. bonus=False (기본 · #186 그대로) 는 남겨요."""
    log = Log(monkeypatch)
    rows = [r for r in DAUM["020400"] if r[0] <= "2026-05-07"]
    prev = {"pxDate": "2026-05-06", "stocks": [{"t": "020400", "cls": "kr", "shr": 3189166}]}
    kr = [{"t": "020400", "nk": "대동금속", "cls": "kr", "cap": 1.0, "shr": 6378332}]
    fetch = lambda c, n: {"data": [{"date": d + " 00:00:00", "tradePrice": tp, "prevClosingPrice": pc, "changePrice": ch, "listedSharesCount": sh}
                                   for d, tp, pc, ch, sh in rows]}     # noqa: E731
    sp = {"splits": [], "splitsFrom": "2016-01-01"}
    out = F.kr_splits_step(sp, prev, kr, real_dart("020400"), dt.date(2026, 5, 8), [], px_date="2026-05-07", daum=fetch, bonus=True, bseed=[])
    info = out["splitsKr"]
    assert info["dq"] == [] and [(x[0], x[1], x[3]) for x in info["bonus"]["held"]] == [("020400", "2026-04-10", "off")]
    assert not log.has("기준가는 아직 그대로예요")
    off = F.kr_splits_step(sp, prev, kr, real_dart("020400"), dt.date(2026, 5, 8), [], px_date="2026-05-07", daum=fetch)
    assert off["splitsKr"]["bonus"]["held"] == [] and off["splitsKr"]["dq"] == [["020400", "2026-05-06"]]
    assert log.has("기준가는 아직 그대로예요")


def test_receipt_cleaner_keeps_the_bonus_fields():
    c, e = _ev("183300", "2026-05-26")
    chk = F.kr_bonus_checks(e, c)[0]
    assert F.kr_split_chk_clean(chk) == chk and F.kr_split_chk_clean({**chk, "note": "None"}) == chk
    assert F.kr_split_chk_clean({k: v for k, v in chk.items() if k != "dr"}) is None


# ── 4. 관문: 깨끗한 파일 PASS · 틀린 영수증 WARN · 실패 없음 ──────────────────────────────────────────────────────────────────
class Rep:
    def __init__(self):
        self.rows, self.details = [], []

    def add(self, name, ok, val, rule, warn=False):
        self.rows.append((name, ok, warn, val))

    def skip(self, name, why):
        self.rows.append((name, True, False, why))

    def detail(self, title, items):
        self.details.append((title, items))


def _gate(info, rows=()):
    rep = Rep()
    V.check_kr_splits(rep, {"splits": [list(x) for x in rows], "splitsKr": info}, TODAY)
    return [x for x in rep.rows if x[0] == V.KR_SPLITS_ROW][0], rep


def _clean_info(monkeypatch, on=False):
    Log(monkeypatch)
    monkeypatch.setattr(F, "KR_BONUS_ROWS_ON", on)
    return _fields(real_dart("183300", "196170"), [seed_of("183300", "2026-05-26"), seed_of("196170", "2026-08-05")])


def test_gate_passes_a_clean_file_and_warns_on_a_bad_receipt(monkeypatch):
    rows, info = _clean_info(monkeypatch, on=True)
    row, _ = _gate(info, rows)
    assert row[1] is True and row[2] is False, row                   # PASS (경고 없음)
    bad = json.loads(json.dumps(info))
    k = next(i for i, x in enumerate(bad["rows"]) if x[0] == "183300")
    for change in ({"px": 1.9}, {"shr": 2.05}, {"dl": "2026-05-26"}, {"dr": "2026-06-20"}, {"x": 0.5}, {"m": 1.05}):
        b2 = json.loads(json.dumps(bad))
        b2["rows"][k][6].update(change)
        row, _ = _gate(b2, rows)
        assert row[1] is True and row[2] is True and "세 확인" in row[3], (change, row)
    b3 = json.loads(json.dumps(bad))
    del b3["rows"][k][6]["px"]
    assert _gate(b3, rows)[0][2] is True


def test_gate_warns_on_held_receipts_failures_and_recent_no_but_never_fails(monkeypatch):
    rows, info = _clean_info(monkeypatch)
    row, rep = _gate(info, rows)
    assert row[1] is True and row[2] is False and "확인했지만 싣지 않은 무상증자 2" in row[3]
    assert any("무상증자 싣지 않음 183300 2026-05-26" in i for _t, items in rep.details for i in items)
    for change in ({"failN": 1, "fail": [["183300", "2026-11-20", "net"]]}, {"out": [["183300", "2026-11-20", "nodoc"]], "outN": 1}):
        b = json.loads(json.dumps(info))
        b["bonus"].update(change)
        row, _ = _gate(b, rows)
        assert row[1] is True and row[2] is True, (change, row)
    b = json.loads(json.dumps(info))
    b["bonus"]["rec"][0][6]["px"] = 1.0
    assert _gate(b, rows)[0][2] is True
    b["bonus"] = "x"
    assert _gate(b, rows)[0][1] is True and _gate(b, rows)[0][2] is True
    old = json.loads(json.dumps(info))
    del old["bonus"]
    assert _gate(old, rows)[0][2] is False                           # 무상증자 전 파일은 그대로


def test_gate_splits_list_row_refuses_a_non_simple_ratio_so_odd_stays_held():
    """관문 '주식 분할 목록 (splits)' (실패 줄 · 바꾸지 않았어요): 깨끗하지 않은 배율의 새 줄은 실패 — 그래서 'odd' 는 스위치를 켜도 싣지 않아요."""
    assert not V.simple_ratio(1.6616554) and V.simple_ratio(2.0) and V.simple_ratio(1.3)


# ── 5. 2.0 기록 (Node): 권리락 날 앞 · 그날 · 뒤 · 권리락과 상장 사이 · 원화 그대로 · 몫 팔기 ───────────────────────────────────────────
NODE = shutil.which("node")
MODS = (("L", "src/v2/lots.js"), ("H", "src/v2/held.js"), ("Rc", "src/v2/records.js"))
_B = {}


def node(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-krbonus-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in MODS:
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/m.mjs", "--log-level=error", "--loader:.js=jsx",
                            "--charset=utf8", "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { L, H, Rc } from './m.mjs';\nconsole.warn = () => {}; console.info = () => {};\n" + DECK + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# 알테오젠 196170 2026-08-05 권리락 (x 0.3 → r 1.3) · 상장 08-26 · 대한제강 084010 2026-01-05 (r 1.6616554) — 스위치를 켜면 실릴 줄 그대로
DECK = """
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deckOf = (t, purchases, sales = []) => ({ id: 'd', name: 'p', createdAt: '2024-01-02', planFx: 1300,
  holdings: [{ t, nk: t, cls: 'kr', target: 1, rules: band(1) }], purchases, sales });
const data = { splits: [['196170', '2026-08-05', 1.3], ['084010', '2026-01-05', 1.6616554]] };
const view = (d, today = '2026-11-28') => L.withDataSplits({ v: 2, decks: [d] }, L.dataSplits(data).list, today).decks[0];
const env = { today: '2026-11-28' };
const buy = (t, date, qty, price, id = 'p' + date.replace(/-/g, '')) => ({ id, t, date, qty, price, ccy: 'KRW' });
const sell = (d, qty, price, date) => Rc.checkSale(d, d.holdings[0].t, { qty, price, date }, { t: d.holdings[0].t, cls: 'kr', price }, env);
"""


@pytest.mark.skipif(NODE is None or not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")), reason="node · esbuild 가 없어요")
def test_records_before_on_after_and_between_the_ex_day():
    """권리락 날 (08-05) 앞에 산 100주 → 130주 (단가 ÷ 1.3 · 원화 그대로) · 그날 · 그 뒤 · 권리락과 상장(08-26) 사이에 산 주식은 그대로 (새 주식을 받지
    않아요) · 상장 뒤도 그대로."""
    got = node("""
      const q = (date) => H.heldQty(view(deckOf('196170', [buy('196170', date, 100, 390000)]))).get('196170');
      const lg = (date) => { const g = L.ledger(view(deckOf('196170', [buy('196170', date, 100, 390000)])), '196170'); return [g.held / H.UNIT, Math.round(g.putIn.won)]; };
      out = { before: q('2026-08-04'), on: q('2026-08-05'), between: q('2026-08-12'), listing: q('2026-08-26'), after: q('2026-09-01'),
              costBefore: lg('2026-08-04'), costBetween: lg('2026-08-12') };
    """)
    assert got["before"] == 130 and got["on"] == 100 and got["between"] == 100 and got["listing"] == 100 and got["after"] == 100
    assert got["costBefore"] == [130, 39000000] and got["costBetween"] == [100, 39000000]   # 넣은 돈 3,900만원 그대로 (단가 ÷ 1.3 = 300,000원)


@pytest.mark.skipif(NODE is None or not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")), reason="node · esbuild 가 없어요")
def test_part_shares_from_a_bonus_are_sellable_in_ten_thousandths():
    """99주 × 1.3 = 128.7주 · 7주 × 1.6616554 = 11.6315878주 (1/10,000주로 11.6316): 팔았어요가 그 몫을 받아요 (#186 의 fracHeld · fracSaleOk) ·
    판 금액 = 수량 × 가격 · 원가 + 남은 원가 = 넣은 돈."""
    got = node("""
      const a = view(deckOf('196170', [buy('196170', '2026-08-04', 99, 390000)]));
      const b = view(deckOf('084010', [buy('084010', '2026-01-02', 7, 19600)]));
      const r = (x) => (x.ok ? { ok: true, qty: x.rec.qty } : { ok: false, why: x.why });
      out = { qa: H.heldQty(a).get('196170'), qb: H.heldQty(b).get('084010'), frac: [Rc.fracSaleOk(a, '196170', '2026-11-27'), Rc.fracSaleOk(b, '084010', '2026-11-27')],
              partA: r(sell(a, '0.7', '300000', '2026-11-27')), allA: r(sell(a, '128.7', '300000', '2026-11-27')),
              partB: r(sell(b, '0.6316', '10000', '2026-11-27')), five: r(sell(b, '0.63159', '10000', '2026-11-27')),
              costB: [Math.round(L.ledger(b, '084010').putIn.won)] };
    """)
    assert got["qa"] == 128.7 and abs(got["qb"] - 11.6316) < 1e-9 and got["frac"] == [True, True]
    assert got["partA"] == {"ok": True, "qty": 0.7} and got["allA"] == {"ok": True, "qty": 128.7} and got["partB"] == {"ok": True, "qty": 0.6316}
    assert got["five"]["ok"] is False and got["costB"] == [137200]                    # 7 × 19,600원 그대로


def test_switch_pinned_off_until_jack_approves_a_bonus_line():
    """기록 시트의 분할 줄 (C.rec.split "{date}에 주식 1주가 {r}주로 나뉘었어요. 그 전 기록은 나뉜 기준으로 맞춰 계산했어요.") 은 무상증자에 맞지 않아요
    (주식이 나뉘지 않고 새 주식을 받아요 · 새 주식은 권리락 날이 아니라 상장일에 들어와요) — 스위치를 켜는 PR 이 무상증자 줄과 함께 이 고정을 바꿔요."""
    assert F.KR_BONUS_ROWS_ON is False
    copy = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    assert '"{date}에 주식 1주가 {r}주로 나뉘었어요. 그 전 기록은 나뉜 기준으로 맞춰 계산했어요."' in copy


def test_a_bonus_error_never_stops_the_split_step(monkeypatch):
    """무상증자 쪽의 오류 (우리 코드) 는 분할 단계를 멈추지 않아요: 분할 줄 · 판정은 그대로 · 무상증자는 지난 발행본의 후보를 이어요 (src err · 관문 경고)."""
    log = Log(monkeypatch)
    sp = [F._kr_cand("000010", "2026-11-02", 10000, 2000, 1000, 5000, "seed")]
    prev = {"splits": [], "splitsKr": {"bonus": {"pend": [F.kr_bonus_row_of(seed_of("183300", "2026-05-26"))]}}}

    def boom(*a, **k):
        raise KeyError("x")
    monkeypatch.setattr(F, "_kr_bonus_fields", boom)
    cl = FakeDart()
    rows, info = F.kr_splits_fields(prev, kr_rows("000010", "183300"), [], cl, TODAY, seed=sp, px_date="2026-11-27", bseed=[seed_of("183300", "2026-05-26")])
    assert info["src"] == "dart" and info["out"] == [["000010", "2026-11-02", "nodoc"]]          # 분할은 그대로 판정했어요
    assert info["bonus"]["src"] == "err" and info["bonus"]["pend"] == prev["splitsKr"]["bonus"]["pend"]
    assert log.has("!! 한국 무상증자: 확인하다 오류로 멈췄어요")
    row, _ = _gate(info, rows)
    assert row[1] is True and row[2] is True and "무상증자 확인이 오류로 멈춰" in row[3]
    monkeypatch.setattr(F, "_kr_bonus_todo", boom)
    rows2, info2 = F.kr_splits_fields(prev, kr_rows("000010", "183300"), [], FakeDart(), TODAY, seed=sp, px_date="2026-11-27", bseed=[])
    assert info2["src"] == "dart" and info2["bonus"]["src"] == "err" and info2["calls"] >= 1
