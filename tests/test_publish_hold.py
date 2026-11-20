# -*- coding: utf-8 -*-
"""2026-11-20 (Jack, "5. Yes"): 2차 출처 날의 이른 발행 보류 (tools/publish_hold.py · update-data.yml 단계 id hold).

Jack 이 승인한 제안 (그대로): "Backup days, hold an early publish. Before 08:00 KST on a backup day, publish only when confirmed closes
reach at least 97% of the last publish's count. Today that means about 80 or fewer missing. Otherwise the run stops and the next one
tries again. From 08:00, publish what we have; the rest show their last close with your line."

- 규칙은 hold_decision 한 곳 (모드 · KST 시각 · 오늘 확인 수 · 직전 발행본 확인 수): 08:00 전 · 딱 97% · 08:00 부터 · 1차 출처 날 ·
  직전 수를 모를 때 · 러너의 UTC 시계.
- '확인' = pxSrc.fb.conf (두 출처) — 마지막 확인 종가로 실은 종목(pxSrc.own · pxd · #159)은 세지 않아요.
- 워크플로: 결정은 한 단계(hold)에서 한 번, 보류면 발행 두 단계만 건너뛰어요 (커밋 · data 브랜치 푸시 · 배포 없음), 실행은 초록
  (감시가 경보를 열지 않아요), already_published.py 는 발행 안 됨으로 봐요.
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


def fb_data(px, conf, noYahoo=6, mkt=107, diff=25, own=None, stocks=None, n=None):
    """2차 출처 날 data.json 의 필요한 부분. 기본값은 2026-11-19 발행본의 실제 수 (목록 2,878 · 확인 2,740 · 코넥스 107 · 야후 없음 6 · 다름 25)."""
    fb = {"n": n if n is not None else conf + mkt + noYahoo + diff, "conf": conf, "mkt": mkt, "noDaum": 0, "bad": 0, "noYahoo": noYahoo,
          "diff": diff, "yMeta": 1, "diffEx": [], "must": [], "cut": {"s": 600, "daum": 0, "yahoo": 0, "fill": 0}}
    src = {"v": 1, "px": FB, "date": px, "days": {px: FB}, "fb": fb, "must": [], "chk": None, "n": {FB: 2475}}
    if own is not None:
        src["own"] = own
    return {"pxDate": px, "usPxDate": px, "pxSrc": src, "stocks": stocks or [{"t": "005930", "cls": "kr", "px": 50000}]}


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
    ("listing", "git HEAD:data.json"),                                            # 직전 발행본이 1차 출처 날 (fb 없음)
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
    prev_line = next(ln for ln in lines if "직전 발행본:" in ln)
    assert prev_line.startswith("!! ") and note in prev_line                      # 왜 비교하지 못했는지 크게 남겨요


def test_evaluate_holds_on_the_real_numbers_of_a_blank_close_night():
    d, lines = P.evaluate(fb_data("2026-11-20", 2526, noYahoo=220), "data.json", fb_data("2026-11-19", 2740), "git HEAD:data.json",
                          kst(2026, 11, 21, 6, 41))
    assert d.hold is True
    assert any("두 출처로 확인 2,526 / 목록 2,878" in ln for ln in lines) and any("두 출처로 확인 2,740 / 목록 2,878" in ln for ln in lines)
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
    net = TWD.FakeNet(data_runs=[TWD.run(1, "success")], jobs={1: HELD_JOBS})
    assert W.decide(net, "workflow_run", W.DATA_NAME, 1)[0] is True               # 올린 것이 없으니 배포를 기다리지 않고 바로 봐요
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 0 and net.issues == []   # 07:05 KST: 경보 이슈 없음
    rep = W.Report()
    W.check_runs(rep, TWD.FakeNet(data_runs=[TWD.run(1, "success")], jobs={1: HELD_JOBS}), W.DATA_WF, W.DATA_NAME)
    assert rep.rows[-1][1] == "PASS"                                              # '데이터 마지막 실행' 은 성공 (빨간 실행이 아니에요)


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
