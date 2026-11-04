# -*- coding: utf-8 -*-
"""v17.6 Part 3a: 데이터는 data 브랜치로, 사이트는 배포 workflow 가 만들어요.

- tools/push_data_branch.sh: 관문 영수증이 맞을 때만, 네 JSON 만 담은 커밋을 data 브랜치에 (처음이면 새로, 강제 푸시 없음)
- tools/assemble_site.py: main 의 파일(점 파일 빼고) + data 브랜치의 네 JSON (main 의 JSON 은 절대 안 써요)
- tools/build_tag.py: 배포할 때만 <head> 에 빌드 표시 (BAEPSAE_BUILD 가 없으면 아무것도 안 바뀌어요)
- already_published.py: data 브랜치의 발행본을 봐요. 그 브랜치가 아직 없을 때만 main (크게 남겨요)
진짜 git 저장소(임시 폴더, 원격은 bare 저장소)로 돌려 봐요.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import already_published as A      # noqa: E402
import build_tag as BT             # noqa: E402

PUSH = os.path.join(ROOT, "tools", "push_data_branch.sh")
ASSEMBLE = os.path.join(ROOT, "tools", "assemble_site.py")
FILES = ("data.json", "corp.json", "disc.json", "macro.json")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=ENV)
    if check and r.returncode != 0:
        raise AssertionError(r.stdout + r.stderr)
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """main 이 있는 작업 저장소와 그 원격(bare). 네 JSON 은 관문을 통과한 것처럼 영수증과 함께 놓여요."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "init", "-q", "-b", "main", str(work))
    (work / "src").mkdir()
    (work / "src" / "a.js").write_text("code")
    (work / ".github").mkdir()
    (work / ".github" / "w.yml").write_text("x")
    (work / ".gitignore").write_text("dist/\n")
    for f in FILES:
        (work / f).write_text(json.dumps({"from": "main", "f": f}))
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "main")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "origin", "main")
    return work, origin, tmp_path / "gate-pass.sha256"


def write_data(work, tag):
    for f in FILES:
        (work / f).write_text(json.dumps({"from": "gate", "tag": tag, "f": f}))


def receipt(work, path):
    out = subprocess.run(["sha256sum", *FILES], cwd=work, capture_output=True, text=True, check=True).stdout
    path.write_text(out)


def push(work, rec):
    return subprocess.run(["bash", PUSH, str(rec)], cwd=work, capture_output=True, text=True, env=ENV)


def data_tip(origin):
    return git(origin, "rev-parse", "--verify", "-q", "refs/heads/data", check=False)


def test_first_publish_creates_the_data_branch_with_only_the_four_files(repo):
    work, origin, rec = repo
    head = git(work, "rev-parse", "HEAD")
    write_data(work, 1)
    receipt(work, rec)
    r = push(work, rec)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "처음 만들어요" in r.stdout and "::notice title=data 브랜치 처음 만듦::" in r.stdout
    tip = data_tip(origin)
    assert tip and git(origin, "ls-tree", "--name-only", tip).split() == sorted(FILES)          # 코드 없음
    assert git(origin, "rev-list", "--count", tip) == "1"                                         # main 과 이어지지 않은 첫 커밋
    assert json.loads(git(origin, "show", f"{tip}:data.json")) == {"from": "gate", "tag": 1, "f": "data.json"}
    assert git(work, "rev-parse", "HEAD") == head and git(work, "rev-parse", "--abbrev-ref", "HEAD") == "main"  # 작업 브랜치 그대로


def test_next_publish_adds_one_commit_and_unchanged_data_adds_none(repo):
    work, origin, rec = repo
    write_data(work, 1)
    receipt(work, rec)
    assert push(work, rec).returncode == 0
    first = data_tip(origin)
    write_data(work, 2)
    receipt(work, rec)
    assert push(work, rec).returncode == 0
    second = data_tip(origin)
    assert second != first and git(origin, "rev-parse", f"{second}^") == first
    assert json.loads(git(origin, "show", f"{second}:corp.json"))["tag"] == 2
    r = push(work, rec)
    assert r.returncode == 0 and "바뀐 것이 없어요" in r.stdout and data_tip(origin) == second


@pytest.mark.parametrize("how", ["no-receipt", "changed-after-gate", "receipt-missing-a-file", "empty-receipt"])
def test_data_branch_is_never_written_without_a_matching_gate_receipt(repo, how):
    work, origin, rec = repo
    write_data(work, 1)
    if how != "no-receipt":
        receipt(work, rec)
    if how == "changed-after-gate":
        (work / "data.json").write_text(json.dumps({"from": "nobody checked this"}))
    if how == "receipt-missing-a-file":
        rec.write_text("\n".join(ln for ln in rec.read_text().splitlines() if "macro.json" not in ln) + "\n")
    if how == "empty-receipt":
        rec.write_text("")
    r = push(work, rec)
    assert r.returncode != 0 and "올리지 않아요" in r.stdout
    assert not data_tip(origin)


def test_push_never_forces():
    text = open(PUSH, encoding="utf-8").read()
    pushes = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("git push")]
    assert pushes == ['git push "$REMOTE" "$commit:refs/heads/$BRANCH"']
    assert "--force" not in text and "-f " not in text and "|| true" not in text


def test_a_remote_that_cannot_be_asked_stops_the_push(repo, tmp_path):
    work, origin, rec = repo
    write_data(work, 1)
    receipt(work, rec)
    git(work, "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))
    r = push(work, rec)
    assert r.returncode != 0 and "확인하지 못했어요" in r.stdout


# ── 사이트 폴더 ──
def test_site_takes_data_only_from_the_data_branch(repo, tmp_path):
    work, origin, rec = repo
    write_data(work, 7)
    receipt(work, rec)
    assert push(work, rec).returncode == 0
    for f in FILES:                                   # 작업 폴더의 JSON 은 main 의 것으로 되돌려요
        git(work, "checkout", "--", f)
    git(work, "fetch", "-q", "origin", "+refs/heads/data:refs/remotes/origin/data")
    out = tmp_path / "_site"
    r = subprocess.run([sys.executable, ASSEMBLE, str(out), "origin/data"], cwd=work, capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, r.stdout + r.stderr
    got = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    assert got == sorted(["src/a.js", *FILES])                                   # 점 파일(.github · .gitignore) 없음
    for f in FILES:
        assert json.loads((out / f).read_text())["tag"] == 7                       # main 의 JSON 이 아니에요


def test_site_refuses_a_data_ref_without_the_four_files(repo, tmp_path):
    work, origin, rec = repo
    out = tmp_path / "_site"
    git(work, "checkout", "-q", "--orphan", "half")
    git(work, "rm", "-rq", "--cached", ".")
    (work / "data.json").write_text("{}")
    git(work, "add", "data.json")
    git(work, "commit", "-q", "-m", "half")
    r = subprocess.run([sys.executable, ASSEMBLE, str(out), "half"], cwd=work, capture_output=True, text=True, env=ENV)
    assert r.returncode != 0 and "corp.json" in (r.stdout + r.stderr)


# ── 빌드 표시 ──
HTML = '<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<title>x</title>\n</head>\n<body>s</body></html>'


def test_build_tag_only_when_asked(tmp_path, monkeypatch):
    p = tmp_path / "p.html"
    p.write_text(HTML)
    monkeypatch.delenv("BAEPSAE_BUILD", raising=False)
    assert BT.main([str(p)]) == 0 and p.read_text() == HTML                      # 커밋하는 빌드는 그대로
    monkeypatch.setenv("BAEPSAE_BUILD", "c" * 40)
    BT.main([str(p)])
    assert p.read_text() == HTML.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="baepsae-build" content="' + "c" * 40 + '">')
    with pytest.raises(SystemExit):
        BT.main([str(p)])                                                        # 두 번 달지 않아요
    with pytest.raises(SystemExit):
        BT.tag(HTML, "main")                                                     # 커밋 해시만
    with pytest.raises(SystemExit):
        BT.tag("<html><body>no head</body></html>", "c" * 40)


def test_every_build_script_tags_every_page_it_writes():
    want = {"build.sh": "python3 tools/build_tag.py baepsae.html",
            "build-app.sh": 'python3 tools/build_tag.py "$OUT/app.html" "$OUT/app-preview.html"',
            "build-styleguide.sh": "python3 tools/build_tag.py styleguide.html"}
    for f, line in want.items():
        text = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert text.rstrip().splitlines()[-1] == line, f                           # 페이지를 다 쓴 뒤 마지막 줄


def test_real_pages_take_the_tag_right_after_charset():
    for f in ("baepsae.html", "app.html", "app-preview.html", "styleguide.html"):
        html = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert 'name="baepsae-build"' not in html, f                               # 커밋한 페이지에는 없어요
        out = BT.tag(html, "d" * 40)
        assert out.count('name="baepsae-build"') == 1 and out.index("baepsae-build") < out.index("</head>")


# ── already_published: data 브랜치 ──
class Done:
    def __init__(self, rc=0, out=b""):
        self.returncode, self.stdout = rc, out


def fake_git(ls_rc, show=None, fail_show=False):
    seen = []

    def run(cmd, **kw):
        seen.append(cmd)
        if cmd[:2] == ["git", "ls-remote"]:
            return Done(ls_rc)
        if cmd[:2] == ["git", "show"]:
            if fail_show:
                raise subprocess.CalledProcessError(128, cmd)
            return Done(0, json.dumps(show).encode())
        return Done(0)
    run.seen = seen
    return run


def test_already_published_reads_the_data_branch():
    run = fake_git(0, {"pxDate": "2026-11-04", "usPxDate": "2026-11-04"})
    assert A.read_published(run) == {"pxDate": "2026-11-04", "usPxDate": "2026-11-04"}
    assert run.seen[0] == ["git", "ls-remote", "--exit-code", "--heads", "origin", "data"]
    assert ["git", "fetch", "--depth=1", "origin", "+refs/heads/data:refs/remotes/origin/data"] in run.seen
    assert run.seen[-1] == ["git", "show", "origin/data:data.json"]
    assert A.main.__defaults__[1] is A.read_published                         # 정해진 시각 실행이 쓰는 기본값


def test_already_published_falls_back_to_main_only_when_the_branch_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(A, "read_main", lambda: {"pxDate": "2026-11-03"})
    assert A.read_published(fake_git(2)) == {"pxDate": "2026-11-03"}
    assert "data 브랜치가 아직 없어요" in capsys.readouterr().out
    assert A.read_published(fake_git(128)) is None                            # 물어보지 못하면 '발행 안 됨' (= 실행)
    assert A.read_published(fake_git(0, fail_show=True)) is None
