# -*- coding: utf-8 -*-
"""2026-11-20 (Jack, "5. Yes"): 2차 출처 날의 이른 발행 보류 (tools/publish_hold.py · update-data.yml 단계 id hold).

Jack 이 승인한 제안 (그대로): "Backup days, hold an early publish. Before 08:00 KST on a backup day, publish only when confirmed closes
reach at least 97% of the last publish's count. Today that means about 80 or fewer missing. Otherwise the run stops and the next one
tries again. From 08:00, publish what we have; the rest show their last close with your line."

- 규칙은 hold_decision 한 곳 (모드 · KST 시각 · 오늘 확인 수 · 직전 발행본 확인 수): 08:00 전 · 딱 97% · 08:00 부터 · 1차 출처 날 ·
  직전 수를 모를 때 · 러너의 UTC 시계.
- '확인' = 코스피 · 코스닥의 두 출처 확인 (pxSrc.fb.conf − 코넥스 fb.knx.kept · #158) — 마지막 확인 종가로 실은 종목(pxSrc.own · pxd · #159)은
  세지 않아요. 직전 발행본이 1차 출처 날이면 기준은 그 파일의 공식 종가가 있는 코스피 · 코스닥 종목 수.
- fetch_data 의 진짜 집계 길(kr_fb_confirm → kr_second_source · px_src_counts → px_src_final)로 만든 기록을 그대로 읽어요 (계약 시험).
- 워크플로: 결정은 한 단계(hold)에서 한 번, 보류면 발행 두 단계만 건너뛰어요 (커밋 · data 브랜치 푸시 · 배포 없음), 실행은 초록
  (감시에는 중립: 경보를 열지도 닫지도 않아요 · watchdog.is_held_run), already_published.py 는 발행 안 됨으로 봐요.
"""
import datetime as dt
import json
import os
import stat
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import already_published as A          # noqa: E402
import fetch_data as F                 # noqa: E402
import publish_hold as P               # noqa: E402
import watchdog as W                   # noqa: E402

WF = os.path.join(ROOT, ".github", "workflows", "update-data.yml")
KST = dt.timezone(dt.timedelta(hours=9))
FB, LISTING = P.PX_SRC_FB, "listing"
HOLD_STEP = "이른 발행 보류 확인 (2차 출처 날 · 08:00 KST 전 · 직전 발행본의 97%)"
PUBLISH = ("커밋 & 푸시", "data 브랜치에 올리기")
GATE = "발행 관문 (validate_data.py)"
IF_PUBLISH = "${{ !inputs.dry_run && steps.hold.outputs.hold != 'true' }}"


def kst(y, m, d, hh, mm, ss=0):
    return dt.datetime(y, m, d, hh, mm, ss, tzinfo=KST)


def fb_data(px, conf, noYahoo=6, mkt=107, diff=25, own=None, stocks=None, n=None, knx_kept=None):
    """2차 출처 날 data.json 의 필요한 부분. 기본값은 2026-11-19 발행본의 실제 수 (목록 2,878 · 확인 2,740 · 코넥스 107 · 야후 없음 6 · 다름 25).
    conf 는 코스피 · 코스닥 확인 수. knx_kept 를 주면 #158 모양: fb.conf = conf + knx_kept, fb.knx 가 붙어요 (n · mkt 는 그대로 — 코넥스는 mkt 에)."""
    fb = {"n": n if n is not None else conf + mkt + noYahoo + diff, "conf": conf, "mkt": mkt, "noDaum": 0, "bad": 0, "noYahoo": noYahoo,
          "diff": diff, "yMeta": 1, "diffEx": [], "must": [], "cut": {"s": 600, "daum": 0, "yahoo": 0, "fill": 0}}
    if knx_kept is not None:                  # fetch_data.px_src_counts (#158) 와 같은 모양
        fb["conf"] = conf + knx_kept
        fb["knx"] = {"n": 107, "conf": knx_kept + 2, "kept": knx_kept, "capOut": 2, "floor": 120000000000, "noNaver": 3, "bad": 0,
                     "noYahoo": 60, "diff": 15, "yMeta": 0, "diffEx": [], "anchor": "2026-11-16", "adj": 0, "noAnchor": 2, "adjEx": [],
                     "left": [], "cut": {"s": 600, "yahoo": 0, "fill": 0, "naver": 0}}
    src = {"v": 1, "px": FB, "date": px, "days": {px: FB}, "fb": fb, "must": [], "chk": None, "n": {FB: 2475}}
    if own is not None:
        src["own"] = own
    return {"pxDate": px, "usPxDate": px, "pxSrc": src, "stocks": stocks or [{"t": "005930", "cls": "kr", "px": 50000}]}


def kr_stock(t, price=10000.0, market="KOSPI", **kw):
    return {"t": t, "cls": "kr", "price": price, "dk": f"업종 · 주요제품: 무엇 · {market} 상장 · 시가총액 1.0조원", **kw}


def normal_day(px, n_kk, n_konex=0, extra=(), with_src=True):
    """1차 출처 날 발행본 (with_src=False 면 pxSrc 가 생기기 전 파일 — 11-17 발행본처럼)."""
    stocks = [kr_stock(f"{i:06d}", market="KOSDAQ GLOBAL" if i % 7 == 0 else ("KOSDAQ" if i % 2 else "KOSPI")) for i in range(n_kk)]
    stocks += [kr_stock(f"8{i:05d}", market="KONEX") for i in range(n_konex)] + list(extra)
    stocks += [{"t": "AAPL", "cls": "us", "price": 200.0}]
    d = {"pxDate": px, "usPxDate": px, "stocks": stocks}
    if with_src:
        d["pxSrc"] = {"v": 1, "px": LISTING, "date": px, "days": {}, "fb": None, "must": [], "chk": None, "n": {LISTING: len(stocks) - 1}}
    return d


def listing_data(px):
    return {"pxDate": px, "usPxDate": px, "stocks": [{"t": "005930", "cls": "kr"}],
            "pxSrc": {"v": 1, "px": LISTING, "date": px, "days": {}, "fb": None, "must": [],
                      "chk": {"src": "yahoo", "n": 98, "same": 98, "none": 2, "diff": []}, "n": {LISTING: 2475}}}


# ── 규칙 (hold_decision) ─────────────────────────────────────
def test_the_97_percent_line_matches_the_approved_example():
    # Jack 의 말 "Today that means about 80 or fewer missing": 11-19 발행본 확인 2,740 → 선 2,658 (82종목까지 모자라도 발행)
    assert P.share_line(2740) == 2658 and 2740 - P.share_line(2740) == 82
    assert P.HOLD_SHARE_PCT == 97 and P.HOLD_BEFORE == dt.time(8, 0)


@pytest.mark.parametrize("hh,mm,ss", [(0, 5, 0), (3, 47, 0), (6, 41, 0), (6, 43, 0), (7, 59, 59)])
def test_before_eight_a_short_run_holds(hh, mm, ss):
    d = P.hold_decision(FB, kst(2026, 11, 21, hh, mm, ss), 2526, 2740)          # 11-19 밤 같은 수: 약 240종목 확인 못 함
    assert d.hold is True and d.loud is True
    for part in ("2,526", "2,658", "2,740", "97%", "모자람 132", f"{hh:02d}:{mm:02d} KST", "08:00 전", "다음 실행"):
        assert part in d.why, (part, d.why)


def test_exactly_97_percent_publishes_and_one_less_holds():
    assert 2619 * 100 == 2700 * 97                                               # 딱 97%
    assert P.hold_decision(FB, kst(2026, 11, 21, 7, 0), 2619, 2700).hold is False
    assert P.hold_decision(FB, kst(2026, 11, 21, 7, 0), 2618, 2700).hold is True
    # 나눗셈이 떨어지지 않을 때는 올림: 2,740 × 97% = 2,657.8 → 2,658 부터 발행
    assert P.hold_decision(FB, kst(2026, 11, 21, 7, 0), 2658, 2740).hold is False
    assert P.hold_decision(FB, kst(2026, 11, 21, 7, 0), 2657, 2740).hold is True
    # 더 많이 확인되면 당연히 발행 (직전보다 많아도)
    assert P.hold_decision(FB, kst(2026, 11, 21, 7, 0), 2800, 2740).hold is False


@pytest.mark.parametrize("hh,mm", [(8, 0), (8, 17), (10, 53), (13, 37), (14, 47), (23, 59)])
def test_from_eight_publish_what_we_have(hh, mm):
    d = P.hold_decision(FB, kst(2026, 11, 21, hh, mm), 2000, 2740)
    assert d.hold is False and d.loud is False and "08:00 KST 부터는 있는 대로 발행" in d.why and "2,000" in d.why


def test_the_kst_clock_decides_not_the_runners_utc_clock():
    utc = dt.timezone.utc
    assert P.hold_decision(FB, dt.datetime(2026, 11, 20, 21, 41, tzinfo=utc), 2526, 2740).hold is True     # = 11-21 06:41 KST
    assert P.hold_decision(FB, dt.datetime(2026, 11, 20, 22, 59, tzinfo=utc), 2526, 2740).hold is True     # = 07:59 KST
    assert P.hold_decision(FB, dt.datetime(2026, 11, 20, 23, 0, tzinfo=utc), 2526, 2740).hold is False     # = 08:00 KST
    assert P.hold_decision(FB, dt.datetime(2026, 11, 21, 3, 0, tzinfo=utc), 2526, 2740).hold is False      # UTC 03:00 = 12:00 KST
    with pytest.raises(ValueError):
        P.hold_decision(FB, dt.datetime(2026, 11, 21, 6, 41), 2526, 2740)                                  # 시간대 없는 시각은 받지 않아요


@pytest.mark.parametrize("mode", [LISTING, None, "", "daum", "Daum+Yahoo"])
def test_a_normal_day_never_holds(mode):
    d = P.hold_decision(mode, kst(2026, 11, 21, 3, 47), 10, 2740)
    assert d.hold is False and d.loud is False and "2차 출처 날이 아니에요" in d.why
    # 1차 출처(KRX 목록 최종본) 날의 data.json 은 확인 수도 없어요 (fb 없음)
    assert P.fb_confirmed(listing_data("2026-11-20"))[0] is None


def test_no_previous_count_never_holds_and_says_why():
    for today, prev in ((2526, None), (None, 2740), (None, None)):
        d = P.hold_decision(FB, kst(2026, 11, 21, 6, 41), today, prev)
        assert d.hold is False and d.loud is True and "보류하지 않아요" in d.why and "비교가 없다고 발행을 막지 않아요" in d.why


@pytest.mark.parametrize("prev,note", [
    (None, "git show HEAD:data.json → 종료 코드 128"),                           # 못 읽음
    ("listing", "git HEAD:data.json"),                                            # 1차 출처 날인데 가격 있는 종목이 없음
    ("nofb", "git HEAD:data.json"),
    ("odd", "git HEAD:data.json"),                                                # 칸이 비었음
    ("datemismatch", "git HEAD:data.json"),
])
def test_unreadable_or_incomparable_previous_publish_never_holds(prev, note):
    cur = fb_data("2026-11-20", 2526)
    p = {"listing": listing_data("2026-11-19"), "nofb": {**fb_data("2026-11-19", 2740)}, "odd": fb_data("2026-11-19", 2740),
         "datemismatch": fb_data("2026-11-19", 2740), None: None}[prev]
    if prev == "nofb":
        p["pxSrc"] = {**p["pxSrc"], "fb": None}
    if prev == "odd":
        p["pxSrc"]["fb"].pop("noYahoo")
    if prev == "datemismatch":
        p["pxSrc"]["date"] = "2026-11-18"
    d, lines = P.evaluate(cur, "data.json", p, note, kst(2026, 11, 21, 6, 41))
    assert d.hold is False and d.loud is True
    assert P.last_count(p)[0] is None
    prev_line = next(ln for ln in lines if "직전 발행본:" in ln)
    assert prev_line.startswith("!! ") and note in prev_line                      # 왜 비교하지 못했는지 크게 남겨요


def test_evaluate_holds_on_the_real_numbers_of_a_blank_close_night():
    d, lines = P.evaluate(fb_data("2026-11-20", 2526, noYahoo=220), "data.json", fb_data("2026-11-19", 2740), "git HEAD:data.json",
                          kst(2026, 11, 21, 6, 41))
    assert d.hold is True
    assert any("코스피 · 코스닥 두 출처 확인 2,526 / 목록 2,878" in ln for ln in lines)
    assert any("코스피 · 코스닥 두 출처 확인 2,740 / 목록 2,878" in ln for ln in lines)
    d, _ = P.evaluate(fb_data("2026-11-20", 2738, noYahoo=8), "data.json", fb_data("2026-11-19", 2740), "git HEAD:data.json",
                      kst(2026, 11, 21, 7, 20))
    assert d.hold is False                                                        # 야후가 채운 뒤 (06:40 쯤부터)


def test_carried_closes_never_count_as_confirmed():
    """#159 가 들어오면 확인 못 한 종목을 마지막 확인 종가로 실어요 (pxSrc.own · 종목의 pxd). 그 종목은 두 출처 확인이 아니에요."""
    carried = [{"t": f"9{i:05d}", "cls": "kr", "px": 1000, "pxd": "2026-11-19"} for i in range(129)]
    own = {"v": 1, "n": 129, "codes": [s["t"] for s in carried], "max": 5}
    cur = fb_data("2026-11-20", 2600, noYahoo=145, own=own, stocks=[{"t": "005930", "cls": "kr", "px": 50000}, *carried])
    cur["pxSrc"]["n"] = {FB: 2346, "own": 129}                                    # 발행 수가 바뀌어도 상관없어요
    assert P.fb_confirmed(cur)[0] == 2600
    d, _ = P.evaluate(cur, "data.json", fb_data("2026-11-19", 2740), "git HEAD:data.json", kst(2026, 11, 21, 6, 41))
    assert d.hold is True and "2,600" in d.why                                    # 2,600 + 129 = 2,729 ≥ 2,658 이지만 실은 종목은 세지 않아요
    # 누가 실은 종목을 conf 에 더하면 칸이 맞지 않아요 → 그 수를 쓰지 않아요 (오늘 · 직전 모두)
    bad = fb_data("2026-11-20", 2600, noYahoo=145, own=own)
    bad["pxSrc"]["fb"]["conf"] += 129
    n, why = P.fb_confirmed(bad)
    assert n is None and "칸이 맞지 않아요" in why
    bad_prev = fb_data("2026-11-19", 2740)
    bad_prev["pxSrc"]["fb"]["conf"] += 129                                        # 부풀린 직전 수로 보류하지 않아요
    d, lines = P.evaluate(fb_data("2026-11-20", 2700), "data.json", bad_prev, "git HEAD:data.json", kst(2026, 11, 21, 6, 41))
    assert d.hold is False and any(ln.startswith("!! 직전 발행본:") and "칸이 맞지 않아요" in ln for ln in lines)


@pytest.mark.parametrize("v", [True, -1, 2.5, "2740", None])
def test_counts_must_be_plain_non_negative_integers(v):
    d = fb_data("2026-11-20", 2740)
    d["pxSrc"]["fb"]["conf"] = v
    assert P.fb_confirmed(d)[0] is None


# ── 실행 (main) ──────────────────────────────────────────────
def run_main(tmp_path, monkeypatch, cur, prev, now, argv=(), dry=False, actions=False):
    out, summ = tmp_path / "out.txt", tmp_path / "summary.md"
    for p in (out, summ):
        if p.exists():
            p.unlink()
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summ))
    monkeypatch.setenv("DRY_RUN", "true" if dry else "")
    if actions:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    else:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    seen = []

    def prev_reader(ref):
        seen.append(ref)
        return (prev, f"git {ref}:data.json") if prev is not None else (None, f"git show {ref}:data.json → 종료 코드 128")
    hold = P.main(list(argv), now_fn=lambda: now, cur_reader=lambda p: (cur, p), prev_reader=prev_reader)
    return hold, out.read_text(), summ.read_text(), seen


def test_main_on_a_hold_logs_both_counts_the_line_and_the_time(tmp_path, monkeypatch, capsys):
    hold, out, summ, seen = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526), fb_data("2026-11-19", 2740),
                                     kst(2026, 11, 21, 6, 41), actions=True)
    log = capsys.readouterr().out
    assert hold is True and seen == ["HEAD"]                                      # 관문과 같은 직전 발행본 (HEAD)
    assert out.splitlines()[-1] == "hold=true"
    loud = next(ln for ln in log.splitlines() if ln.startswith("!! [보류]"))
    for part in ("2,526", "2,740", "97% 선 2,658", "06:41 KST"):
        assert part in loud, part
    assert "::warning title=발행 보류 (2차 출처 날 · 08:00 KST 전)::" in log
    assert "보류 — 이 실행은 발행하지 않아요" in summ and "2,658" in summ and "already_published.py" in summ and "건너뛰어요" in summ


def test_main_publishes_from_eight_and_on_normal_days(tmp_path, monkeypatch, capsys):
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526), fb_data("2026-11-19", 2740), kst(2026, 11, 21, 8, 17))
    assert hold is False and out.splitlines()[-1] == "hold=false" and "발행 (보류 아님)" in summ
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, listing_data("2026-11-20"), fb_data("2026-11-19", 2740), kst(2026, 11, 21, 3, 47))
    assert hold is False and out.splitlines()[-1] == "hold=false" and "2차 출처 날이 아니에요" in summ
    assert "!!" not in capsys.readouterr().out


def test_dry_runs_report_the_decision_too(tmp_path, monkeypatch, capsys):
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526), fb_data("2026-11-19", 2740),
                                  kst(2026, 11, 21, 6, 41), dry=True)
    assert hold is True and out.splitlines()[-1] == "hold=true"
    assert "시험 실행" in summ and "보류" in summ and "시험 실행: 어차피 발행하지 않아요" in capsys.readouterr().out


def test_bootstrap_and_a_missing_compare_commit_never_hold(tmp_path, monkeypatch, capsys):
    for argv, word in ((["--bootstrap"], "bootstrap"), (["--no-prev"], "받지 못했어요")):
        hold, out, summ, seen = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2000), fb_data("2026-11-19", 2740),
                                         kst(2026, 11, 21, 6, 41), argv=argv)
        assert hold is False and seen == [] and out.splitlines()[-1] == "hold=false" and word in summ
    hold, out, _, seen = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2000), fb_data("2026-11-19", 2740),
                                  kst(2026, 11, 21, 6, 41), argv=["--prev-ref", "FETCH_HEAD"])
    assert hold is True and seen == ["FETCH_HEAD"]


def test_main_never_holds_when_it_breaks(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def boom(path):
        raise RuntimeError("읽기 실패")
    assert P.main([], now_fn=lambda: kst(2026, 11, 21, 6, 41), cur_reader=boom) is False
    assert out.read_text().splitlines()[-1] == "hold=false"
    assert "!! 이른 발행 보류 확인이 오류로 멈췄어요" in capsys.readouterr().out
    # 오늘 data.json 을 못 읽어도 보류하지 않아요 (관문이 봐요)
    hold, text, _, _ = run_main(tmp_path, monkeypatch, None, fb_data("2026-11-19", 2740), kst(2026, 11, 21, 6, 41))
    assert hold is False and text.splitlines()[-1] == "hold=false"


def test_read_prev_reads_the_same_file_the_gate_compares_with(tmp_path):
    calls = []

    class R:
        def __init__(self, rc, out):
            self.returncode, self.stdout = rc, out

    def fake(cmd, **kw):
        calls.append(cmd)
        return R(0, json.dumps(fb_data("2026-11-19", 2740)).encode())
    data, note = P.read_prev("HEAD", run=fake)
    assert calls == [["git", "show", "HEAD:data.json"]] and P.fb_confirmed(data)[0] == 2740 and note == "git HEAD:data.json"
    assert P.read_prev("HEAD", run=lambda cmd, **kw: R(128, b""))[0] is None
    assert P.read_prev("HEAD", run=lambda cmd, **kw: R(0, b"{not json"))[0] is None
    # 관문의 기본 비교 대상도 HEAD 예요 (validate_data --prev-ref 기본값)
    import validate_data as V
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert 'ap.add_argument("--prev-ref", default="HEAD"' in src and V.PX_SRC_FB == FB


# ── 워크플로 ─────────────────────────────────────────────────
def update_steps():
    with open(WF, encoding="utf-8") as f:
        return yaml.safe_load(f)["jobs"]["update"]["steps"]


def names(st):
    return [s.get("name") or s.get("uses") for s in st]


def test_the_hold_is_decided_once_before_the_gate_and_runs_on_every_run():
    st = update_steps()
    n = names(st)
    i_fetch, i_save, i_hold, i_gate = n.index("데이터 수집"), n.index("DART 캐시 저장"), n.index(HOLD_STEP), n.index(GATE)
    i_main, i_data = n.index(PUBLISH[0]), n.index(PUBLISH[1])
    assert i_fetch < i_save < i_hold < i_gate < i_main < i_data == len(st) - 1
    hold = st[i_hold]
    assert hold["id"] == "hold"
    for k in ("if", "env", "continue-on-error", "timeout-minutes"):
        assert k not in hold, k                                                   # 시험 실행에서도 늘 돌아요 · 토큰 · 비밀 값 없음
    run = hold["run"]
    assert run.count("python tools/publish_hold.py") == 1 and "|| true" not in run
    for bad in ("git push", "git commit", "push_data_branch", "GITHUB_TOKEN", "secrets.", "github.token"):
        assert bad not in json.dumps(hold, ensure_ascii=False), bad
    # 결정은 이 한 단계에서만 · 그 결과를 보는 곳은 발행 두 단계뿐
    whole = json.dumps(st, ensure_ascii=False)
    assert whole.count("publish_hold.py") == 1
    users = [s.get("name") for s in st if "steps.hold" in json.dumps(s, ensure_ascii=False)]
    assert users == list(PUBLISH)
    assert os.path.isfile(os.path.join(ROOT, "tools", "publish_hold.py"))


def test_a_hold_skips_exactly_the_commit_and_the_data_branch_push():
    st = update_steps()
    by = dict(zip(names(st), st))
    for name in PUBLISH:
        assert by[name]["if"] == IF_PUBLISH, name
    # 저장소에 쓰는 단계는 그 둘뿐 (main 커밋 · data 브랜치 → 배포는 data 브랜치 단계가 성공해야만 해요)
    writers = [s.get("name") for s in st if any(w in (s.get("run") or "") for w in ("git push", "git commit", "push_data_branch"))]
    assert writers == list(PUBLISH)

    def gh_if(dry_run, hold_out):
        """IF_PUBLISH 를 GitHub 처럼 풀어요: !inputs.dry_run && steps.hold.outputs.hold != 'true' (출력이 없으면 빈 값)."""
        return (not dry_run) and (hold_out or "") != "true"
    assert gh_if(False, "false") is True and gh_if(False, None) is True           # 보류 아님 · 출력 없음 → 예전처럼 발행
    assert gh_if(False, "true") is False                                          # 보류 → 발행 없음
    assert gh_if(True, "false") is False and gh_if(True, "true") is False         # 시험 실행은 예전처럼 늘 발행 없음


def fake_bin(tmp_path, py_body, git_ok=True):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    py = bin_ / "python"
    py.write_text("#!/bin/bash\n" f'echo "$*" >> "{tmp_path}/calls.txt"\n' + py_body)
    git = bin_ / "git"
    git.write_text("#!/bin/bash\n" f'echo "git $*" >> "{tmp_path}/calls.txt"\n' + ("exit 0\n" if git_ok else "exit 128\n"))
    for f in (py, git):
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return bin_


def run_hold_step(tmp_path, py_body, env=None, git_ok=True):
    run = next(s for s in update_steps() if s.get("name") == HOLD_STEP)["run"]
    bin_ = fake_bin(tmp_path, py_body, git_ok)
    out = tmp_path / "out.txt"
    out.write_text("")
    (tmp_path / "calls.txt").write_text("")
    e = {"PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "BOOTSTRAP": "", "PREV_REF": "", **(env or {})}
    r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp_path, env=e, capture_output=True, text=True)
    return r, out.read_text().split(), (tmp_path / "calls.txt").read_text()


def test_hold_step_bash_passes_the_gate_inputs_and_fails_open(tmp_path):
    ok = 'echo "hold=true" >> "$GITHUB_OUTPUT"\n'
    r, out, calls = run_hold_step(tmp_path, ok)
    assert r.returncode == 0 and out == ["hold=true"] and calls.strip() == "tools/publish_hold.py"
    r, out, calls = run_hold_step(tmp_path, ok, {"BOOTSTRAP": "true"})
    assert r.returncode == 0 and calls.strip() == "tools/publish_hold.py --bootstrap"
    r, out, calls = run_hold_step(tmp_path, ok, {"PREV_REF": "abc123"})
    assert r.returncode == 0 and "git fetch --depth=1 origin abc123" in calls and "tools/publish_hold.py --prev-ref FETCH_HEAD" in calls
    r, out, calls = run_hold_step(tmp_path, ok, {"PREV_REF": "abc123"}, git_ok=False)
    assert r.returncode == 0 and "tools/publish_hold.py --no-prev" in calls and "받지 못했어요" in r.stdout
    # 확인 자체가 멈추면 (파이썬 오류) 보류하지 않고 이어가요 — 크게 남겨요 · 단계는 실패하지 않아요
    r, out, calls = run_hold_step(tmp_path, "exit 1\n")
    assert r.returncode == 0 and out == ["hold=false"] and "!! 이른 발행 보류 확인이 오류로 멈췄어요" in r.stdout
    assert "::warning title=이른 발행 보류 확인 못 함 (보류 없이 발행)::" in r.stdout                   # 09:13 점검이 읽는 경고 알림


def test_hold_step_end_to_end_with_the_real_script_and_git(tmp_path):
    """단계의 bash 를 진짜 publish_hold.py · git 으로: 직전 발행본은 커밋된 data.json (HEAD), 오늘 것은 작업 폴더의 data.json."""
    repo = tmp_path / "repo"
    repo.mkdir()
    genv = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    (repo / "data.json").write_text(json.dumps(fb_data("2026-11-19", 2740)))
    for cmd in (["git", "init", "-q"], ["git", "add", "data.json"], ["git", "commit", "-q", "-m", "prev"]):
        subprocess.run(cmd, cwd=repo, env=genv, check=True, capture_output=True)
    (repo / "data.json").write_text(json.dumps(fb_data("2026-11-20", 2526, noYahoo=220)))     # 오늘 실행이 쓴 것 (커밋 전)
    run = next(s for s in update_steps() if s.get("name") == HOLD_STEP)["run"]
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for when, want in (("2026-11-21T06:41:00+09:00", "hold=true"), ("2026-11-21T08:17:00+09:00", "hold=false")):
        py = bin_ / "python"                                                       # 진짜 파이썬 · 진짜 스크립트에 시각만 정해 줘요
        py.write_text(f'#!/bin/bash\n[ "$1" = "tools/publish_hold.py" ] || exit 9\nshift\n'
                      f'exec "{sys.executable}" "{os.path.join(ROOT, "tools", "publish_hold.py")}" "$@" --now {when}\n')
        py.chmod(py.stat().st_mode | stat.S_IEXEC)
        out, summ = tmp_path / "out.txt", tmp_path / "summ.md"
        out.write_text("")
        summ.write_text("")
        e = {**genv, "PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summ),
             "BOOTSTRAP": "", "PREV_REF": "", "DRY_RUN": ""}
        e.pop("GITHUB_ACTIONS", None)
        r = subprocess.run(["bash", "-e", "-c", run], cwd=repo, env=e, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert out.read_text().splitlines()[-1] == want, (r.stdout, r.stderr)
        assert "2,526" in r.stdout and "2,740" in r.stdout
    # 단계는 파일을 바꾸지 않아요 (오늘 data.json 그대로 · 커밋 없음)
    assert json.loads((repo / "data.json").read_text())["pxDate"] == "2026-11-20"
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, env=genv, capture_output=True, text=True).stdout
    assert len(log.strip().splitlines()) == 1


# ── 보류한 실행은 발행이 아니에요: 배포 · 감시 · already_published ──
HELD_JOBS = [{"name": "check", "conclusion": "success", "steps": [{"name": "x", "conclusion": "success"}]},
             {"name": "update", "conclusion": "success",
              "steps": [{"name": HOLD_STEP, "conclusion": "success"}, {"name": GATE, "conclusion": "success"},
                        {"name": PUBLISH[0], "conclusion": "skipped"}, {"name": PUBLISH[1], "conclusion": "skipped"}]}]


def test_a_held_run_does_not_deploy(tmp_path):
    import test_workflows as TW
    # 보류한 실행: 실행은 성공, 'data 브랜치에 올리기' 는 건너뜀 → 배포할 새 데이터가 없어요
    rc, go, log = TW._decide(tmp_path, "workflow_run", "workflow", conclusion="success", pushed="skipped")
    assert (rc, go) == (0, "go=false") and "올리지 않았어요" in log


def test_a_held_run_raises_no_data_alarm(monkeypatch):
    import test_watchdog as TWD
    runs = [TWD.run(2, "success"), TWD.run(1, "success")]                         # 보류한 실행 (2) 앞에 발행한 실행 (1)
    net = TWD.FakeNet(data_runs=runs, jobs={2: HELD_JOBS})
    assert W.decide(net, "workflow_run", W.DATA_NAME, 2)[0] is True               # 올린 것이 없으니 배포를 기다리지 않고 바로 봐요
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 0 and net.issues == []   # 07:05 KST: 경보 이슈 없음
    rep = W.Report()
    W.check_runs(rep, TWD.FakeNet(data_runs=runs, jobs={2: HELD_JOBS}), W.DATA_WF, W.DATA_NAME)
    name, st, detail = rep.rows[-1][:3]
    assert st == "PASS" and "/runs/1" in detail and "이른 발행 보류 1번" in detail     # 보류한 실행은 셈하지 않고 그 전의 실행으로 판단해요


def test_a_held_run_never_closes_a_real_alarm(monkeypatch):
    """보류한 실행은 초록이지만 발행이 아니에요: 그 전의 실제 실행이 실패해 열린 경보를 닫지 않아요 (정상화됐어요 · healthchecks 정상 신호 없음)."""
    import test_watchdog as TWD
    alarm = {"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open"}
    net = TWD.FakeNet(data_runs=[TWD.run(2, "success"), TWD.run(1, "failure")], jobs={2: HELD_JOBS}, issues=[alarm])
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 1                 # 그 전의 실패 그대로 → 경보 유지
    assert not [c for c in net.calls if c[0] == "PATCH"]                          # 닫지 않아요
    c = TWD.posts(net, "/issues/9/comments")
    assert len(c) == 1 and "아직 문제가 있어요" in c[0][2]["body"] and not c[0][2]["body"].startswith("정상화됐어요")
    assert net.urls[-1].endswith("/fail")                                          # healthchecks 에도 정상 신호를 보내지 않아요
    # 보류한 실행만 있고 그 전의 실행이 성공이면 경보를 열지 않아요 (중립)
    net = TWD.FakeNet(data_runs=[TWD.run(3, "success"), TWD.run(2, "success"), TWD.run(1, "success")], jobs={3: HELD_JOBS, 2: HELD_JOBS})
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 0 and net.issues == []


def test_only_a_held_run_is_neutral_and_an_api_hiccup_counts_the_run_as_before(capsys):
    import test_watchdog as TWD
    pushed = [{"name": "update", "conclusion": "success", "steps": [{"name": W.PUSH_STEP, "conclusion": "success"}]}]
    already = [{"name": "check", "conclusion": "success", "steps": []}, {"name": "update", "conclusion": "skipped", "steps": []}]
    net = TWD.FakeNet(jobs={1: HELD_JOBS, 2: pushed, 3: already})
    assert W.is_held_run(net, TWD.run(1, "success")) is True
    assert W.is_held_run(net, TWD.run(2, "success")) is False                     # 발행한 실행
    assert W.is_held_run(net, TWD.run(3, "success")) is False                     # 이미 발행돼 건너뛴 실행 (update job 건너뜀)
    assert W.is_held_run(net, TWD.run(1, "failure")) is False                     # 빨간 실행은 늘 실패로 세요

    class Down(TWD.FakeNet):
        def gh(self, method, path, body=None, ok=(200, 201, 204)):
            if "/jobs" in path:
                raise RuntimeError("API 막힘")
            return super().gh(method, path, body, ok)
    assert W.is_held_run(Down(jobs={1: HELD_JOBS}), TWD.run(1, "success")) is False   # 모르면 예전처럼 그 실행으로 판단해요
    assert "보류한 실행인지 몰라요" in capsys.readouterr().out


def weekdays(start, end):
    d, out = start, []
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def test_already_published_sees_no_publish_after_a_hold():
    days = weekdays(dt.date(2026, 10, 1), dt.date(2026, 11, 20))
    cal = {"kr": days, "us": days, "usToday": None, "krSources": 2}
    prev, cur = fb_data("2026-11-19", 2740), fb_data("2026-11-20", 2526)
    now = kst(2026, 11, 21, 6, 41)                                                # 토요일 새벽 실행
    assert P.evaluate(cur, "data.json", prev, "git HEAD:data.json", now)[0].hold is True
    # 보류하면 발행 두 단계가 건너뛰어 data 브랜치에는 직전 발행본이 그대로예요 → 다음 실행(06:43 · 08:17)은 건너뛰지 않고 다시 해요
    for hh, mm in ((6, 43), (7, 20), (8, 17)):
        skip, why = A.decide(prev, kst(2026, 11, 21, hh, mm), cal)
        assert skip is False and "아직이에요" in why
    # (보류하지 않고 발행했다면 뒤의 실행은 모두 건너뛰었을 거예요 — 그래서 240종목이 하루 종일 빠져 있었어요)
    assert A.decide(cur, kst(2026, 11, 21, 8, 17), cal)[0] is True


# ── 코넥스 (#158) · 1차 출처 날 기준 · 경고 알림 · 표본 · 계약 ─────────────
def test_konex_kept_is_subtracted_so_both_days_count_kospi_and_kosdaq_only():
    """#158: 코넥스를 그날 파일에 넣은 날 fb.conf = 다음 × 야후 확인 + fb.knx.kept, n · mkt 는 그대로 (코넥스는 mkt 에). 빼지 않으면 칸이 맞지 않아
    보류가 조용히 꺼져요 — 두 날 모두 코스피 · 코스닥 수로 비교해요."""
    d = fb_data("2026-11-20", 2700, knx_kept=23)
    assert d["pxSrc"]["fb"]["conf"] == 2723
    n, why = P.fb_confirmed(d)
    assert n == 2700 and "코넥스 23 는 빼고" in why and "conf 2,723" in why
    now = kst(2026, 11, 21, 6, 41)
    # 바뀌는 날: 직전 발행본에는 knx 가 없고 (2,740) 오늘은 있어요 — 2,650 + 코넥스 23 = 2,673 ≥ 2,658 이지만 코스피 · 코스닥은 2,650 → 보류
    prev = fb_data("2026-11-19", 2740)
    assert P.evaluate(fb_data("2026-11-20", 2650, noYahoo=96, knx_kept=23), "data.json", prev, "git HEAD:data.json", now)[0].hold is True
    assert P.evaluate(fb_data("2026-11-20", 2660, noYahoo=86, knx_kept=23), "data.json", prev, "git HEAD:data.json", now)[0].hold is False
    # 거꾸로: 직전에는 knx 가 있고 (2,740 + 23) 오늘은 없어요 — 직전도 코스피 · 코스닥 2,740 으로 (선 2,658) → 2,665 는 발행
    prev_k = fb_data("2026-11-19", 2740, knx_kept=23)
    assert P.last_count(prev_k)[0] == 2740
    assert P.evaluate(fb_data("2026-11-20", 2665, noYahoo=81), "data.json", prev_k, "git HEAD:data.json", now)[0].hold is False
    assert P.evaluate(fb_data("2026-11-20", 2657, noYahoo=89), "data.json", prev_k, "git HEAD:data.json", now)[0].hold is True


@pytest.mark.parametrize("knx", ["x", None, {}, {"kept": None}, {"kept": True}, {"kept": -1}, {"kept": 99999}])
def test_an_odd_konex_record_is_not_compared(knx):
    d = fb_data("2026-11-20", 2700, knx_kept=23)
    if knx is None:
        d["pxSrc"]["fb"]["knx"] = None                                            # 칸은 있는데 빈 값
    else:
        d["pxSrc"]["fb"]["knx"] = knx
    n, why = P.fb_confirmed(d)
    assert n is None and ("knx" in why or "칸이 맞지 않아요" in why)


def test_a_normal_day_publish_is_a_baseline_too():
    """첫 2차 출처 날 (직전 발행본이 1차 출처 날): 기준 = 그 파일에서 공식 종가가 있는 코스피 · 코스닥 종목 수 (코넥스 · 펀드 · 가격 없음 · pxd 빼요)."""
    extra = [{"t": "069500", "cls": "kr", "fund": True, "price": 79900.0, "dk": "KOSPI 상장"},     # 펀드 (KODEX 200)
             kr_stock("900001", price=None), kr_stock("900002", price=float("nan")), kr_stock("900003", price=0),
             kr_stock("900004", pxd="2026-11-13"),                                           # 마지막 확인 종가 (세지 않아요)
             {"t": "900005", "cls": "kr", "price": 5000.0}]                                  # 설명이 없는 종목은 코스피 · 코스닥으로 세요
    for with_src in (True, False):                                                # pxSrc listing · pxSrc 가 생기기 전 파일 (11-17 발행본처럼)
        prev = normal_day("2026-11-16", 2441, n_konex=31, extra=extra, with_src=with_src)
        n, why = P.last_count(prev)
        assert n == 2442 and "코넥스 31" in why and "펀드 1" in why and "가격 없음 3" in why and "마지막 확인 종가 1" in why
    prev = normal_day("2026-11-16", 2700)
    now = kst(2026, 11, 19, 6, 41)
    d, lines = P.evaluate(fb_data("2026-11-18", 2600, noYahoo=146), "data.json", prev, "git HEAD:data.json", now)
    assert d.hold is True and "97% 선 2,619" in d.why and any("1차 출처 날 발행본" in ln for ln in lines)
    assert P.evaluate(fb_data("2026-11-18", 2619, noYahoo=127), "data.json", prev, "git HEAD:data.json", now)[0].hold is False
    # 실제 11-18 (첫 2차 출처 날): 11-17 06:40 발행본 (pxDate 11-16 · 코스피 · 코스닥 2,441) 이 기준 → 선 2,368.
    # 11-19 06:40 발행본은 2,743 이라 발행 — 야후가 빈 밤의 수 (2,526) 였어도 발행해요 (발행한 종목만 든 기준이라 낮아요 · RUNBOOK)
    real = normal_day("2026-11-16", 2441, n_konex=31, extra=extra[:1], with_src=False)
    assert P.last_count(real)[0] == 2441 and P.share_line(2441) == 2368
    assert P.evaluate(fb_data("2026-11-18", 2743, noYahoo=3), "data.json", real, "git", now)[0].hold is False
    assert P.evaluate(fb_data("2026-11-18", 2526, noYahoo=220), "data.json", real, "git", now)[0].hold is False


@pytest.mark.parametrize("src", [None, "x", {"px": "listing", "date": "2026-11-13"}, {"px": "other", "date": "2026-11-16"}])
def test_an_odd_normal_day_record_is_not_compared(src):
    prev = normal_day("2026-11-16", 2700)
    prev["pxSrc"] = src
    d, lines = P.evaluate(fb_data("2026-11-18", 2000), "data.json", prev, "git HEAD:data.json", kst(2026, 11, 19, 6, 41))
    assert d.hold is False and d.loud is True and P.last_count(prev)[0] is None


def test_a_loud_no_hold_leaves_a_warning_and_marks_the_today_line(tmp_path, monkeypatch, capsys):
    # 2차 출처 날 08:00 전에 비교하지 못하면 (직전을 못 읽음) 보류 없이 발행하지만 경고 알림을 남겨요 (09:13 점검이 읽어요)
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2000), None, kst(2026, 11, 21, 6, 41), actions=True)
    log = capsys.readouterr().out
    assert hold is False and out.splitlines()[-1] == "hold=false"
    assert "::warning title=이른 발행 보류 확인 못 함 (보류 없이 발행)::" in log and "!! 직전 발행본:" in log
    # 오늘 기록을 쓸 수 없으면 '오늘:' 줄에도 !!
    bad = fb_data("2026-11-20", 2600, noYahoo=145)
    bad["pxSrc"]["fb"]["conf"] += 5
    hold, out, _, _ = run_main(tmp_path, monkeypatch, bad, fb_data("2026-11-19", 2740), kst(2026, 11, 21, 6, 41), actions=True)
    log = capsys.readouterr().out
    assert hold is False and "!! 오늘:" in log and "::warning title=이른 발행 보류 확인 못 함" in log
    # 08:00 뒤 · 1차 출처 날에는 경고가 없어요 (예전 그대로)
    for cur, when in ((fb_data("2026-11-20", 2000), kst(2026, 11, 21, 8, 17)), (listing_data("2026-11-20"), kst(2026, 11, 21, 3, 47))):
        run_main(tmp_path, monkeypatch, cur, None, when, actions=True)
        assert "::warning" not in capsys.readouterr().out
    # 오류로 멈추면 경고 하나
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    P.main([], now_fn=lambda: kst(2026, 11, 21, 6, 41), cur_reader=lambda p: (_ for _ in ()).throw(RuntimeError("x")))
    assert capsys.readouterr().out.count("::warning title=이른 발행 보류 확인 못 함 (보류 없이 발행)::") == 1


def test_a_sample_dry_run_says_its_decision_means_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SAMPLE_KR", "50")
    _, _, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526), fb_data("2026-11-19", 2740), kst(2026, 11, 21, 6, 41), dry=True)
    assert "표본 실행(sample)" in summ and "뜻이 없어요" in summ and "표본 실행: 이 결정은 뜻이 없어요" in capsys.readouterr().out
    monkeypatch.setenv("SAMPLE_KR", "0")
    _, _, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526), fb_data("2026-11-19", 2740), kst(2026, 11, 21, 6, 41), dry=True)
    assert "표본" not in summ


def test_contract_with_the_pipelines_own_second_source_record():
    """fetch_data 의 진짜 길로 pxSrc 를 만들어 그대로 읽어요 (실제 응답 픽스처 · tests/fixtures/kr_two_source): kr_fallback_days (kr_fb_confirm) →
    kr_second_source (px_src_counts) → px_src_final. fetch_data 가 집계 모양을 바꾸면 여기서 깨져요 (보류가 조용히 꺼지지 않게)."""
    import test_kr_two_source as T2
    uni = T2.listing("2026-11-18_1452")
    D16, D18 = dt.date(2026, 11, 16), dt.date(2026, 11, 18)

    def fetch_daum(codes, n):
        return T2.daum(), []

    def fetch_yahoo(cm, start, end):
        return {c: {k: v for k, v in d.items() if k != D18} for c, d in T2.yahoo().items()}, 0

    def fill(y, cm, d, close_time):
        mc = set()
        for c, rows in T2.daum().items():
            if c in cm and d in rows:
                y.setdefault(c, {})[d] = rows[d]["tradePrice"]
                mc.add(c)
        return {"need": len(mc), "bar": 0, "meta": len(mc), "none": 0, "fail": 0, "metaCodes": mc}
    seen = {}

    def fallback(days, universe_of, now, special):
        out, notes = F.kr_fallback_days(days, universe_of, now, special, fetch_daum=fetch_daum, fetch_yahoo=fetch_yahoo, fill_day=fill)
        seen.update(out)
        return out, notes
    now = dt.datetime(2026, 11, 19, 2, 15, tzinfo=F.KST)
    px, lst, _, src, _, _ = F.kr_second_source(D16, T2.listing("2026-11-16_2211"), [D18], now, {}, lambda d: (uni, "시험"), fallback=fallback)
    assert px == D18 and src["px"] == FB
    st = seen[D18][1]
    stocks = [{"t": str(c), "cls": "kr"} for c in lst["Code"]]
    data = {"pxDate": px.isoformat(), "pxSrc": F.px_src_final(src, stocks), "stocks": stocks}
    data = json.loads(json.dumps(data))                                          # data.json 에 쓰고 읽은 그대로 (발행본처럼)
    n, why = P.fb_confirmed(data)
    assert n == st["conf"] == len(lst) > 0, why
    assert st["mkt"] and P.FB_PARTS == ("mkt", "noDaum", "bad", "noYahoo", "diff")   # 픽스처의 코넥스 1종목이 mkt 에 (#158 전)
    # 같은 기록이 직전 발행본이면 그 수가 기준이에요 (보류 결정까지)
    assert P.last_count(data)[0] == n
    assert P.hold_decision(FB, kst(2026, 11, 19, 6, 41), n, n).hold is False and P.hold_decision(FB, kst(2026, 11, 19, 6, 41), n - 1, n * 2).hold is True
