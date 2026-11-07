# -*- coding: utf-8 -*-
"""스모크 시험의 임시 폴더 정리 (tests/tmpdirs.py, Jack 승인 2026-11-07).

통과한 실행은 자기 폴더를 남기지 않고, 실패한 실행은 자기 폴더만 남기며 같은 시험의 그 전 실패 폴더를 지워요. 표시 파일이 없거나
다른 시험 것인 폴더 · 아직 도는 실행의 폴더 · 임시 폴더 밖의 것은 절대 지우지 않아요.
진짜 시험처럼 별도 프로세스로 작은 시험 파일(smoke_fake.py · smoke_other.py)을 돌리고, TMPDIR 를 이 시험만의 빈 폴더로 둬요
(이 pytest 프로세스에서는 finish 를 부르지 않아요: buildapp 이 만든 폴더를 지우면 안 되니까요)."""
import json
import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tmpdirs  # noqa: E402

FAKE = '''import os, shutil, sys
sys.path.insert(0, {here!r})
import tmpdirs
mode = sys.argv[1]


def main():
    a = tmpdirs.make("baepsae-fake-")
    b = tmpdirs.make("baepsae-fake-site-")
    c = tmpdirs.make("baepsae-fake-clean-")
    shutil.rmtree(c)                       # 시험 코드가 이미 지운 폴더 ('끝나면 지워요')
    print(a, flush=True)
    print(b, flush=True)
    if mode == "raise":
        raise RuntimeError("장면 밖에서 멈춤")
    if mode == "wait":
        sys.stdin.readline()
    return 0 if mode == "pass" else 1


sys.exit(tmpdirs.run(main))
'''


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "root"
    bindir = tmp_path / "bin"
    root.mkdir()
    bindir.mkdir()
    for name in ("smoke_fake.py", "smoke_other.py"):
        (bindir / name).write_text(FAKE.format(here=HERE), encoding="utf-8")
    e = dict(os.environ, TMPDIR=str(root), PYTHONDONTWRITEBYTECODE="1")
    return {"root": str(root), "bin": str(bindir), "env": e, "tmp": tmp_path}


def run(env, mode, script="smoke_fake.py"):
    r = subprocess.run([sys.executable, os.path.join(env["bin"], script), mode], env=env["env"], capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    made = r.stdout.split()
    return r.returncode, made, r.stderr


def entries(env):
    return sorted(os.listdir(env["root"]))


def test_passing_run_leaves_no_folder(env):
    code, made, err = run(env, "pass")
    assert code == 0, err
    assert len(made) == 2 and all(p.startswith(env["root"] + os.sep) for p in made), made
    assert entries(env) == [], entries(env)
    assert "폴더 2 / 2개를 지웠어요" in err, err


def test_failing_run_keeps_only_its_own_folders_and_removes_the_older_failure(env):
    code, first, err = run(env, "fail")
    assert code == 1, err
    assert all(os.path.isdir(p) for p in first) and entries(env) == sorted(os.path.basename(p) for p in first)
    j = tmpdirs.marker(first[0])
    assert j["script"] == "smoke_fake.py" and j["prefix"] == "baepsae-fake-", j
    assert all(p in err for p in first), err                                  # 남긴 폴더 위치를 찍어요
    code, second, err = run(env, "fail")
    assert code == 1, err
    assert all(os.path.isdir(p) for p in second) and not any(os.path.exists(p) for p in first)
    assert entries(env) == sorted(os.path.basename(p) for p in second), entries(env)
    assert "그 전 실패 실행 폴더 2 / 2개를 지웠어요" in err, err


def test_removing_an_old_failure_does_not_follow_links_inside_it(env):
    _, first, _ = run(env, "fail")
    outside = env["tmp"] / "outside"                                      # 예: trendflip 폴더의 node_modules 바로가기
    outside.mkdir()
    (outside / "precious.txt").write_text("x", encoding="utf-8")
    os.symlink(str(outside), os.path.join(first[0], "node_modules"))
    code, _, err = run(env, "fail")
    assert code == 1 and not os.path.lexists(first[0]), err
    assert (outside / "precious.txt").read_text(encoding="utf-8") == "x"


def test_exception_counts_as_failure(env):
    code, made, err = run(env, "raise")
    assert code == 1 and "RuntimeError" in err, err                           # 예외 · 종료 코드는 그대로
    assert len(made) == 2 and all(os.path.isdir(p) for p in made)
    code, later, err = run(env, "fail")                                     # 다음 실패가 그 폴더를 '그 전 실패'로 지워요
    assert code == 1 and not any(os.path.exists(p) for p in made) and all(os.path.isdir(p) for p in later)


def test_passing_run_touches_only_its_own_folders(env):
    _, failed, _ = run(env, "fail")
    code, _, err = run(env, "pass")
    assert code == 0, err
    assert entries(env) == sorted(os.path.basename(p) for p in failed), entries(env)   # 그 전 실패 폴더는 그대로


def test_never_deletes_unmarked_other_script_or_outside_folders(env):
    root = env["root"]
    _, other, _ = run(env, "fail", script="smoke_other.py")                 # 다른 시험의 실패 폴더 (그 실행은 끝났어요)
    _, donor, _ = run(env, "fail")                                          # 이 시험의 진짜 표시 파일 (끝난 실행)
    real = open(os.path.join(donor[0], tmpdirs.MARK), encoding="utf-8").read()
    os.makedirs(os.path.join(root, "baepsae-fake-nomark", "keep"))         # 표시 파일 없음
    os.makedirs(os.path.join(root, "baepsae-fake-broken"))
    with open(os.path.join(root, "baepsae-fake-broken", tmpdirs.MARK), "w", encoding="utf-8") as fh:
        fh.write("{not json")                                               # 읽을 수 없는 표시 파일
    os.makedirs(os.path.join(root, "tmpcopied"))
    with open(os.path.join(root, "tmpcopied", tmpdirs.MARK), "w", encoding="utf-8") as fh:
        fh.write(real)                                                      # 이름이 접두어와 맞지 않음
    os.makedirs(os.path.join(root, "baepsae-zzz-renamed"))
    with open(os.path.join(root, "baepsae-zzz-renamed", tmpdirs.MARK), "w", encoding="utf-8") as fh:
        fh.write(real)                                                      # 표시 파일의 접두어(baepsae-fake-)와 이름이 다름
    outside = env["tmp"] / "outside" / "baepsae-fake-outside"               # 임시 폴더 밖 (표시 파일은 진짜)
    outside.mkdir(parents=True)
    (outside / tmpdirs.MARK).write_text(real, encoding="utf-8")
    (outside / "precious.txt").write_text("x", encoding="utf-8")
    os.symlink(str(outside), os.path.join(root, "baepsae-fake-link"))      # 임시 폴더 안의 바로가기 → 밖
    keep = sorted(set(entries(env)) - {os.path.basename(p) for p in donor})

    code, last, err = run(env, "fail")
    assert code == 1, err
    assert not any(os.path.exists(p) for p in donor)                       # 이 시험의 그 전 실패만 지워졌어요
    assert entries(env) == sorted(keep + [os.path.basename(p) for p in last]), entries(env)
    assert all(os.path.isdir(p) for p in other) and os.path.isdir(os.path.join(root, "baepsae-fake-nomark", "keep"))
    assert (outside / "precious.txt").read_text(encoding="utf-8") == "x" and os.path.islink(os.path.join(root, "baepsae-fake-link"))
    code, _, err = run(env, "pass")
    assert code == 0 and entries(env) == sorted(keep + [os.path.basename(p) for p in last]), entries(env)


def test_still_running_run_of_the_same_script_is_not_touched(env):
    p = subprocess.Popen([sys.executable, os.path.join(env["bin"], "smoke_fake.py"), "wait"], env=env["env"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        running = [p.stdout.readline().strip(), p.stdout.readline().strip()]
        code, failed, err = run(env, "fail")                               # 다른 창에서 같은 시험이 아직 도는 중
        assert code == 1, err
        assert all(os.path.isdir(x) for x in running + failed), entries(env)
        out, err = p.communicate("\n", timeout=60)                         # 그 실행도 실패로 끝나면 끝난 실행(failed)의 폴더를 지워요
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 1, err
    assert all(os.path.isdir(x) for x in running) and not any(os.path.exists(x) for x in failed), entries(env)


def test_make_needs_the_baepsae_prefix():
    with pytest.raises(ValueError):
        tmpdirs.make("tmp")


SMOKES = ["smoke_app.py", "smoke_launch.py", "smoke_preview.py", "smoke_v2.py"]


@pytest.mark.parametrize("name", SMOKES + ["buildapp.py"])
def test_smoke_scripts_make_temp_folders_only_through_the_helper(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        src = f.read()
    assert not re.search(r"\bmkdtemp\s*\(|\bmkstemp\s*\(|TemporaryDirectory\s*\(", src), name
    assert "tmpdirs.make(" in src, name
    if name in SMOKES:
        assert src.count("sys.exit(tmpdirs.run(main))") == 1 and "sys.exit(main())" not in src, name
