# -*- coding: utf-8 -*-
"""v19.3a: company logos live on their own `logos` branch, never on main; Deploy copies them into the site.

- tools/push_logos_branch.sh: only a folder that passes tools/logos/logo_index.py (index.json + 128 px .webp/.png that
  match it, nothing else) goes to exactly refs/heads/logos, as a commit holding only logos/ (first push creates the
  branch, never forced; main and data untouched).
- tools/assemble_site.py: logos/ comes only from the logos branch. No branch, a broken index, a stray file or an
  unexpected error -> a loud warning and the site without logos (letter marks), never a failed deploy. A logos/ folder
  on main is not published.
- deploy.yml's step "logos 브랜치의 로고 받기": a missing or unreachable branch never fails the deploy.
- sw.js: logo files are network-first like everything else (offline: the cached copy, else an error -> letter mark).
Real git repositories in temporary folders (the remote is a bare repository), like tests/test_data_branch.py.
"""
import io
import json
import os
import stat
import subprocess
import sys

import pytest
import yaml

from test_data_branch import ENV, FILES, git, push, receipt, repo, write_data  # noqa: F401  (repo is a fixture)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUSH_LOGOS = os.path.join(ROOT, "tools", "push_logos_branch.sh")
ASSEMBLE = os.path.join(ROOT, "tools", "assemble_site.py")
PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def webp(color, size=128):
    b = io.BytesIO()
    Image.new("RGBA", (size, size), color).save(b, "WEBP", quality=90)
    return b.getvalue()


def make_logos(path, codes, color=(30, 60, 90, 255), extra=None):
    path.mkdir(parents=True, exist_ok=True)
    logos = {}
    for c in codes:
        (path / f"{c}.webp").write_bytes(webp(color))
        logos[c] = {"file": f"{c}.webp", "route": "ticker", "w": 512, "h": 512, "vector": False, "flags": []}
    if "005930" in logos:
        logos["005935"] = dict(logos["005930"], via="005930")
    (path / "index.json").write_text(json.dumps({"version": 1, "size": 128, "format": "webp", "logos": logos}),
                                     encoding="utf-8")
    for name, body in (extra or {}).items():
        (path / name).write_bytes(body)
    return path


def push_logos(work, folder):
    return subprocess.run(["bash", PUSH_LOGOS, str(folder)], cwd=work, capture_output=True, text=True, env=ENV)


def tip(origin, ref="refs/heads/logos"):
    return git(origin, "rev-parse", "--verify", "-q", ref, check=False)


# ── tools/push_logos_branch.sh ──

def test_first_push_creates_the_logos_branch_with_only_the_logo_folder(repo, tmp_path):
    work, origin, _ = repo
    head, main_tip = git(work, "rev-parse", "HEAD"), tip(origin, "refs/heads/main")
    folder = make_logos(tmp_path / "art" / "logos", ["005930", "AAPL"])
    r = push_logos(work, folder)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "처음 만들어요" in r.stdout
    t = tip(origin)
    assert t and git(origin, "rev-list", "--count", t) == "1"                                       # not joined to main
    assert sorted(git(origin, "ls-tree", "-r", "--name-only", t).split()) == \
        ["logos/005930.webp", "logos/AAPL.webp", "logos/index.json"]
    blob = subprocess.run(["git", "show", f"{t}:logos/005930.webp"], cwd=origin, capture_output=True, env=ENV).stdout
    assert blob == (folder / "005930.webp").read_bytes()
    assert git(origin, "log", "-1", "--format=%s", t).startswith("로고 갱신 ")
    assert git(work, "rev-parse", "HEAD") == head and tip(origin, "refs/heads/main") == main_tip    # main untouched
    assert not tip(origin, "refs/heads/data")


def test_next_push_adds_one_commit_and_unchanged_adds_none(repo, tmp_path):
    work, origin, _ = repo
    assert push_logos(work, make_logos(tmp_path / "a", ["005930"])).returncode == 0
    first = tip(origin)
    assert push_logos(work, make_logos(tmp_path / "b", ["005930", "000660"])).returncode == 0
    second = tip(origin)
    assert second != first and git(origin, "rev-parse", f"{second}^") == first
    r = push_logos(work, make_logos(tmp_path / "c", ["005930", "000660"]))
    assert r.returncode == 0 and "바뀐 것이 없어요" in r.stdout and tip(origin) == second


@pytest.mark.parametrize("how", ["extra-file", "svg", "subfolder", "listed-but-missing", "broken-json", "link",
                                 "wrong-size", "no-folder"])
def test_logos_branch_is_never_written_from_a_folder_that_fails_the_check(repo, tmp_path, how):
    work, origin, _ = repo
    folder = make_logos(tmp_path / "logos", ["005930"])
    if how == "extra-file":
        (folder / "README.md").write_text("hi")
    if how == "svg":
        (folder / "x.svg").write_text("<svg onload='alert(1)'/>")
    if how == "subfolder":
        (folder / "more").mkdir()
    if how == "listed-but-missing":
        (folder / "005930.webp").unlink()
    if how == "broken-json":
        (folder / "index.json").write_text("{not json")
    if how == "link":
        (folder / "000660.webp").symlink_to(folder / "005930.webp")
    if how == "wrong-size":
        (folder / "005930.webp").write_bytes(webp((1, 2, 3, 255), size=64))
    if how == "no-folder":
        folder = tmp_path / "nowhere"
    r = push_logos(work, folder)
    assert r.returncode != 0 and "올리지 않아요" in r.stdout, r.stdout + r.stderr
    assert not tip(origin)


def test_push_logos_never_forces_and_writes_only_the_logos_branch():
    text = open(PUSH_LOGOS, encoding="utf-8").read()
    pushes = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("git push")]
    assert pushes == ['git push "$REMOTE" "$commit:refs/heads/$BRANCH"']
    assert 'BRANCH="logos"' in text and "LOGOS_BRANCH" not in text                            # the name is fixed
    assert "--force" not in text and "-f " not in text and "|| true" not in text
    assert os.stat(PUSH_LOGOS).st_mode & stat.S_IXUSR


def test_a_branch_merely_ending_in_logos_is_not_the_logos_branch(repo, tmp_path):
    work, origin, _ = repo
    git(work, "push", "-q", "origin", "main:refs/heads/claude/x/logos")
    r = push_logos(work, make_logos(tmp_path / "logos", ["005930"]))
    assert r.returncode == 0 and "처음 만들어요" in r.stdout
    assert git(origin, "rev-list", "--count", tip(origin)) == "1"
    assert git(origin, "rev-parse", "refs/heads/claude/x/logos") == git(work, "rev-parse", "main")


# ── tools/assemble_site.py ──

def publish_data(work, rec):
    write_data(work, 7)
    receipt(work, rec)
    assert push(work, rec).returncode == 0
    for f in FILES:
        git(work, "checkout", "--", f)
    git(work, "fetch", "-q", "origin", "+refs/heads/data:refs/remotes/origin/data")


def assemble(work, out, *refs):
    return subprocess.run([sys.executable, ASSEMBLE, str(out), "origin/data", *refs], cwd=work, capture_output=True,
                          text=True, env=ENV)


def files_in(out):
    return sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())


def test_site_takes_logos_from_the_logos_branch(repo, tmp_path):
    work, origin, rec = repo
    publish_data(work, rec)
    folder = make_logos(tmp_path / "art" / "logos", ["005930", "AAPL"])
    assert push_logos(work, folder).returncode == 0
    git(work, "fetch", "-q", "origin", "+refs/heads/logos:refs/remotes/origin/logos")
    out = tmp_path / "_site"
    r = assemble(work, out, "refs/remotes/origin/logos")
    assert r.returncode == 0, r.stdout + r.stderr
    assert files_in(out) == sorted(["src/a.js", *FILES, "logos/005930.webp", "logos/AAPL.webp", "logos/index.json"])
    for f in ("005930.webp", "AAPL.webp", "index.json"):
        assert (out / "logos" / f).read_bytes() == (folder / f).read_bytes()
    assert "회사 로고:" in r.stdout and "로고 없이" not in r.stdout
    assert not [p for p in os.listdir(tmp_path) if p.startswith(".logos-")]                    # no staging left over


def test_site_without_a_logos_branch_deploys_with_letter_marks_and_says_so(repo, tmp_path):
    work, origin, rec = repo
    publish_data(work, rec)
    out = tmp_path / "_site"
    r = assemble(work, out, "refs/remotes/origin/logos")
    assert r.returncode == 0, r.stdout + r.stderr
    assert files_in(out) == sorted(["src/a.js", *FILES])
    assert "::warning title=로고 없이 배포::" in r.stdout and "!! 회사 로고 없이 배포해요" in r.stdout
    r2 = assemble(work, tmp_path / "_site2")                                                    # no ref given at all
    assert r2.returncode == 0 and "::warning title=로고 없이 배포::" in r2.stdout


def commit_logos_tree(work, origin, files):
    """A logos branch built by hand (not by the push script): files = {path: bytes}."""
    git(work, "checkout", "-q", "--orphan", "handmade")
    git(work, "rm", "-rq", "--cached", ".")
    for path, body in files.items():
        full = work / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(body)
        git(work, "add", "-f", path)
    git(work, "commit", "-q", "-m", "handmade logos")
    git(work, "push", "-q", "origin", "handmade:refs/heads/logos")
    git(work, "checkout", "-q", "-f", "main")
    git(work, "clean", "-fdq")
    git(work, "fetch", "-q", "origin", "+refs/heads/logos:refs/remotes/origin/logos")


@pytest.mark.parametrize("how", ["broken-index", "listed-but-missing", "stray-file", "svg", "not-a-picture"])
def test_a_bad_logos_branch_never_breaks_the_site(repo, tmp_path, how):
    work, origin, rec = repo
    publish_data(work, rec)
    good = webp((10, 20, 30, 255))
    entry = {"file": "005930.webp", "route": "ticker", "w": 512, "h": 512, "vector": False, "flags": []}
    index = json.dumps({"version": 1, "size": 128, "logos": {"005930": entry}}).encode()
    files = {"logos/index.json": index, "logos/005930.webp": good}
    if how == "broken-index":
        files["logos/index.json"] = b'{"version": 1, "logos": '
    if how == "listed-but-missing":
        files["logos/index.json"] = json.dumps({"version": 1, "size": 128, "logos": {
            "005930": entry, "000660": dict(entry, file="000660.webp")}}).encode()
    if how == "stray-file":
        files["README.md"] = b"not a logo"
    if how == "svg":
        files["logos/005930.svg"] = b"<svg/>"
    if how == "not-a-picture":
        files["logos/005930.webp"] = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 60
    commit_logos_tree(work, origin, files)
    out = tmp_path / "_site"
    r = assemble(work, out, "refs/remotes/origin/logos")
    assert r.returncode == 0, r.stdout + r.stderr
    assert files_in(out) == sorted(["src/a.js", *FILES])                                         # site as before
    assert "::warning title=로고 없이 배포::" in r.stdout


def test_logos_on_main_are_never_published(repo, tmp_path):
    work, origin, rec = repo
    (work / "logos").mkdir()
    (work / "logos" / "index.json").write_text("{}")
    git(work, "add", "logos/index.json")
    git(work, "commit", "-q", "-m", "a mistake")
    git(work, "push", "-q", "origin", "main")
    publish_data(work, rec)
    out = tmp_path / "_site"
    r = assemble(work, out, "refs/remotes/origin/logos")
    assert r.returncode == 0 and "logos/index.json" not in files_in(out)
    assert "::warning title=main 에 로고 파일::" in r.stdout


# ── deploy.yml: the logos step ──

def logos_step():
    wf = yaml.safe_load(open(os.path.join(ROOT, ".github", "workflows", "deploy.yml"), encoding="utf-8"))
    return next(s for s in wf["jobs"]["build"]["steps"] if s.get("name") == "logos 브랜치의 로고 받기")["run"]


def run_step(tmp_path, heads=("logos",), ls_rc=0, fetch_rc=0):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    log = tmp_path / "git.log"
    lines = "".join(f"echo '{'a' * 40}\trefs/heads/{h}'; " for h in heads)
    (bin_ / "git").write_text("#!/bin/bash\n"
                              f'echo "$*" >> "{log}"\n'
                              'case "$1" in\n'
                              f"  ls-remote) {lines}exit {ls_rc} ;;\n"
                              f"  fetch) exit {fetch_rc} ;;\n"
                              "  rev-parse) echo abc1234 ;;\n"
                              "  log) echo '로고 갱신' ;;\n"
                              "esac\n")
    (bin_ / "git").chmod(0o755)
    env = {"PATH": f"{bin_}:{os.environ['PATH']}"}
    r = subprocess.run(["bash", "-e", "-c", logos_step()], env=env, capture_output=True, text=True)
    return r, (log.read_text() if log.exists() else "")


def test_deploy_logos_step_never_fails_the_deploy(tmp_path):
    (tmp_path / "a").mkdir()
    r, calls = run_step(tmp_path / "a")
    assert r.returncode == 0 and "fetch --depth=1 origin +refs/heads/logos:refs/remotes/origin/logos" in calls
    assert "::warning" not in r.stdout and "logos 브랜치 끝: abc1234" in r.stdout
    for kw in ({"heads": ()}, {"heads": ("claude/x/logos",)}, {"ls_rc": 128}, {"fetch_rc": 1}):
        d = tmp_path / str(len(os.listdir(tmp_path)))
        d.mkdir()
        r, calls = run_step(d, **kw)
        assert r.returncode == 0 and "::warning title=로고 없이 배포::" in r.stdout, kw
        if "fetch_rc" not in kw:
            assert "fetch" not in calls, kw


# ── sw.js: logo files ──

def test_service_worker_serves_logos_network_first_and_offline_from_cache():
    node = __import__("shutil").which("node")
    if not node:
        pytest.skip("node 가 없어요")
    import test_sw
    script = test_sw.HARNESS.split("(async () => {", 1)[0] + r"""
(async () => {
  const out = {};
  out.index1 = await get('logos/index.json');
  out.img1 = await get('logos/005930.webp', 'no-cors');
  version = 'v2';
  out.img2 = await get('logos/005930.webp', 'no-cors');
  online = false;
  out.imgOff = await get('logos/005930.webp', 'no-cors');
  out.indexOff = await get('logos/index.json');
  out.missOff = await get('logos/000660.webp', 'no-cors');
  console.log(JSON.stringify(out));
})();
"""
    r = subprocess.run([node, "-e", script, os.path.join(ROOT, "sw.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["index1"] == "net v1 /baepsae/logos/index.json" and got["img2"] == "net v2 /baepsae/logos/005930.webp"
    assert got["imgOff"] == "net v2 /baepsae/logos/005930.webp" and got["indexOff"] == "net v1 /baepsae/logos/index.json"
    assert got["missOff"] == "ERROR"                                                            # -> the letter mark
