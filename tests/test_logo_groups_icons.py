# -*- coding: utf-8 -*-
"""Group marks and homepage icons (Jack, 2026-11-07), added to the reviewed logo folder after Claude looked at each.
--group-mark CODE=FROM: CODE (a letter mark) gets a byte-for-byte copy of FROM's picture, the group's main mark, once
CODE's own website showed that mark as its logo; never from a copied group mark or a preferred share.
--add-site-icons SURVEY --codes: the company's own homepage icon from the site-icon survey, at least 96 px, every
quality check, never the same picture as another company's logo. Both all or nothing, both recorded.
Same fakes as test_logo_fetch.py: no network, no key."""
import csv
import json
import pathlib
import sys

import pytest

from test_data_branch import repo  # noqa: F401, E402  (a fixture)

import test_logo_fetch as T
import test_logo_retry as R

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))

import logo_index as LI  # noqa: E402
import logodev_fetch as F  # noqa: E402

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402


def folder(tmp_path, gone=("005380", "000660")):
    return R.letters_setup(tmp_path, gone=gone)


def icon(colour=(20, 120, 60, 255), size=128):
    im = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((10, 10, size - 10, size - 10), fill=colour)
    d.rectangle((size // 3, size // 4, size // 2, size - size // 4), fill=(255, 255, 255, 255))
    return im


def survey(tmp_path, items):
    """items: {code: (decision, original_size, picture or None)} -> a site-icon survey folder."""
    s = tmp_path / "survey"
    (s / "kr").mkdir(parents=True)
    (s / "review").mkdir()
    dec = {}
    for code, (decision, size, pic) in items.items():
        dec[f"{code}.example.kr"] = {"codes": [code], "decision": decision, "original_size": size,
                                     "source_type": "apple-touch-icon", "final_url": f"https://{code}.example.kr/i.png",
                                     "page_url": f"https://{code}.example.kr/"}
        if pic is not None:
            pic.save(s / ("kr" if decision == "kept" else "review") / f"{code}.png")
    (s / "decisions.json").write_text(json.dumps(dec), encoding="utf-8")
    return s


def test_a_group_mark_is_an_exact_copy_with_its_source_recorded(tmp_path):
    first = folder(tmp_path)
    src = T.index(first)["logos"]["005930"]
    assert F.main(["--group-mark", "005380=005930", "--dir", str(first), "--reason", "own site shows it"]) == 0
    idx = T.index(first)
    e = idx["logos"]["005380"]
    assert e["flags"] == ["group-mark"] and e["group"] == "005930" and e["route"] == src["route"]
    assert e["name"] == "현대차" and e["file"] != src["file"]                      # its own file, its own name
    assert (first / "logos" / e["file"]).read_bytes() == (first / "logos" / src["file"]).read_bytes()
    assert LI.validate_dir(first / "logos")[1] == []
    rows = list(csv.DictReader(open(first / "groups.csv", encoding="utf-8")))
    assert rows[0]["code"] == "005380" and "group mark of" in rows[0]["reason"] and "005930" in rows[0]["reason"]
    assert "000660" not in idx["logos"]                                             # only what was named


def test_a_preferred_share_follows_its_issuers_group_mark(tmp_path):
    first = folder(tmp_path, gone=("005930", "000660"))                            # 005935 goes with 005930
    idx = T.index(first)
    if "005935" in idx["logos"]:
        del idx["logos"]["005935"]
        idx["count"] = len(idx["logos"])
        (first / "logos" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    assert F.main(["--group-mark", "005930=005380", "--dir", str(first)]) == 0
    idx = T.index(first)
    assert idx["logos"]["005935"]["via"] == "005930" and idx["logos"]["005930"]["group"] == "005380"


@pytest.mark.parametrize("pairs,why", [
    ("005380=999999", "has no picture of its own"),                                 # unknown source
    ("005930=005380", "not a Korean common share showing a letter mark"),           # already has a logo
    ("005380", "CODE=FROM"),                                                        # malformed
    ("005380=005930,005380=005930", "a code given twice"),
    ("AAPL=005930", "not a Korean common share"),                                   # US
])
def test_group_mark_refusals_change_nothing(tmp_path, pairs, why):
    first = folder(tmp_path)
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--group-mark", pairs, "--dir", str(first)])
    assert why in str(e.value) and T.snapshot(first) == before


def test_a_copied_group_mark_or_a_preferred_share_is_never_a_source(tmp_path):
    first = folder(tmp_path, gone=("005380", "000660", "247540"))
    assert F.main(["--group-mark", "005380=005930", "--dir", str(first)]) == 0
    before = T.snapshot(first)
    for pair in ("000660=005380", "000660=005935"):
        with pytest.raises(SystemExit) as e:
            F.main(["--group-mark", pair, "--dir", str(first)])
        assert "never a source" in str(e.value) and T.snapshot(first) == before


def test_homepage_icons_pass_every_check_and_are_recorded(tmp_path):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": ("kept", "180x180", icon()), "000660": ("needs_review", "256x256", icon((200, 30, 30, 255)))})
    assert F.main(["--add-site-icons", str(s), "--codes", "005380,000660", "--dir", str(first), "--reason", "looked at"]) == 0
    idx = T.index(first)
    e = idx["logos"]["005380"]
    assert (e["route"], e["flags"], e["w"], e["h"]) == ("site", ["homepage-icon"], 180, 180)
    assert e["src"] == "https://005380.example.kr/i.png" and e["page"] == "https://005380.example.kr/"
    assert idx["logos"]["000660"]["route"] == "site"
    assert LI.validate_dir(first / "logos")[1] == [] and LI.not_publishable(idx) is None
    rows = {r["code"]: r for r in csv.DictReader(open(first / "sites.csv", encoding="utf-8"))}
    assert set(rows) == {"005380", "000660"} and "005380.example.kr" in rows["005380"]["reason"]


@pytest.mark.parametrize("item,why", [
    (("kept", "64x64", icon()), "under 96 px"),                                     # Jack: 96 px or more
    (("kept", "180x180", Image.new("RGBA", (128, 128), (0, 0, 0, 0))), "quality check"),   # blank
    (("too_small", "48x48", icon()), "no kept icon"),
    (("kept", "", icon()), "no size"),
])
def test_homepage_icon_refusals_change_nothing(tmp_path, item, why):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": item})
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)])
    assert why in str(e.value) and T.snapshot(first) == before


def test_a_homepage_icon_that_is_another_companys_logo_is_refused(tmp_path):
    first = folder(tmp_path)
    other = Image.open(first / "logos" / T.index(first)["logos"]["005930"]["file"]).convert("RGBA")
    s = survey(tmp_path, {"005380": ("kept", "180x180", other)})
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)])
    assert "the same picture as another company's logo" in str(e.value) and "--group-mark" in str(e.value)
    assert T.snapshot(first) == before


def test_a_failure_while_writing_puts_everything_back(tmp_path, monkeypatch):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": ("kept", "180x180", icon())})
    before = T.snapshot(first)

    def broken(f, index):
        raise OSError("disk full")
    monkeypatch.setattr(F, "write_index", broken)
    for argv in (["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)],
                 ["--group-mark", "005380=005930", "--dir", str(first)]):
        try:
            rc = F.main(argv)
        except OSError:
            rc = 1
        assert rc == 1 and T.snapshot(first) == before


def test_the_cli_pairs_each_command_with_its_inputs(tmp_path):
    first = folder(tmp_path)
    with pytest.raises(SystemExit):
        F.main(["--add-site-icons", str(tmp_path), "--dir", str(first)])            # needs --codes
    with pytest.raises(SystemExit):
        F.main(["--group-mark", "005380=005930", "--codes", "005380", "--dir", str(first)])
    with pytest.raises(SystemExit):
        F.main(["--group-mark", "005380=005930"])                                   # needs --dir
    assert "site" in LI.ROUTES


# ── after the fresh-eyes review of PR #74 ──
def test_an_svg_icon_is_judged_by_the_surveys_size_field_only(tmp_path):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": ("kept", "svg", icon())})
    assert F.main(["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)]) == 0
    e = T.index(first)["logos"]["005380"]
    assert e["vector"] is True and (e["w"], e["h"]) == (128, 128)
    (tmp_path / "b").mkdir()
    first2 = folder(tmp_path / "b")
    s2 = survey(tmp_path / "b", {"005380": ("kept", "64x64", icon())})
    d = json.loads((s2 / "decisions.json").read_text(encoding="utf-8"))
    for v in d.values():
        v["final_url"], v["source_type"] = "https://x.example.kr/logo.svg", "icon-svg"     # an address alone is not a vector
    (s2 / "decisions.json").write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        F.main(["--add-site-icons", str(s2), "--codes", "005380", "--dir", str(first2)])
    assert "under 96 px" in str(e.value)


@pytest.mark.parametrize("size,ok", [("96x96", True), ("95x96", False), ("96x95", False)])
def test_the_96_px_edge(tmp_path, size, ok):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": ("kept", size, icon())})
    if ok:
        assert F.main(["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)]) == 0
    else:
        with pytest.raises(SystemExit) as e:
            F.main(["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)])
        assert "under 96 px" in str(e.value)


def test_two_identical_icons_in_one_call_are_refused(tmp_path):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": ("kept", "180x180", icon()), "000660": ("kept", "180x180", icon())})
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--add-site-icons", str(s), "--codes", "005380,000660", "--dir", str(first)])
    assert "the same picture as another company's logo" in str(e.value) and T.snapshot(first) == before


def test_an_old_dropped_picture_leaves_dropped_for_group_marks_and_icons(tmp_path):
    first = folder(tmp_path, gone=())
    assert F.main(["--drop", "005380,000660", "--dir", str(first)]) == 0
    assert (first / "dropped" / "005380.webp").exists() and (first / "dropped" / "000660.webp").exists()
    s = survey(tmp_path, {"000660": ("kept", "180x180", icon())})
    assert F.main(["--group-mark", "005380=005930", "--dir", str(first)]) == 0
    assert F.main(["--add-site-icons", str(s), "--codes", "000660", "--dir", str(first)]) == 0
    dropped = json.loads((first / "dropped" / "index.json").read_text(encoding="utf-8"))["logos"]
    assert "005380" not in dropped and "000660" not in dropped
    assert not (first / "dropped" / "005380.webp").exists() and not (first / "dropped" / "000660.webp").exists()
    assert LI.validate_dir(first / "logos")[1] == [] and LI.validate_dir(first / "dropped")[1] == []


def test_the_summary_lists_group_marks_and_homepage_icons(tmp_path):
    first = folder(tmp_path)
    s = survey(tmp_path, {"000660": ("kept", "180x180", icon())})
    assert F.main(["--group-mark", "005380=005930", "--dir", str(first), "--reason", "own site shows it"]) == 0
    assert F.main(["--add-site-icons", str(s), "--codes", "000660", "--dir", str(first)]) == 0
    text = (first / "summary.md").read_text(encoding="utf-8")
    assert "## Group marks added after review" in text and "005380" in text.split("## Group marks", 1)[1]
    assert "## Homepage icons added after review" in text and "000660" in text.split("## Homepage icons", 1)[1]


def test_a_group_mark_source_cannot_be_dropped_while_its_copies_are_live(tmp_path):
    first = folder(tmp_path)
    assert F.main(["--group-mark", "005380=005930", "--dir", str(first)]) == 0
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--drop", "005930", "--dir", str(first)])
    assert "005380" in str(e.value) and "group mark" in str(e.value) and T.snapshot(first) == before
    assert F.main(["--drop", "005930,005380", "--dir", str(first)]) == 0           # both together is fine
    assert "005380" not in T.index(first)["logos"]


def test_a_us_company_is_never_a_group_mark_target_or_source(tmp_path):
    first = folder(tmp_path, gone=("005380", "AAPL"))
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--group-mark", "AAPL=005930", "--dir", str(first)])                # AAPL shows a letter mark: still refused
    assert "not a Korean common share" in str(e.value)
    with pytest.raises(SystemExit) as e:
        F.main(["--group-mark", "005380=MSFT", "--dir", str(first)])                # a US source
    assert "must be a Korean company" in str(e.value) and T.snapshot(first) == before


def test_add_site_icons_without_codes_is_an_argument_error(tmp_path, capsys):
    first = folder(tmp_path)
    with pytest.raises(SystemExit) as e:
        F.main(["--add-site-icons", str(tmp_path), "--dir", str(first)])
    assert e.value.code == 2 and "--add-site-icons needs --codes" in capsys.readouterr().err


def test_a_failed_write_also_leaves_the_records_as_they_were(tmp_path, monkeypatch):
    first = folder(tmp_path)
    s = survey(tmp_path, {"005380": ("kept", "180x180", icon())})
    records = {n: (first / n).read_bytes() if (first / n).exists() else None
               for n in ("run.json", "summary.md", "groups.csv", "sites.csv")}

    def broken(f, index):
        raise OSError("disk full")
    monkeypatch.setattr(F, "write_index", broken)
    for argv in (["--add-site-icons", str(s), "--codes", "005380", "--dir", str(first)],
                 ["--group-mark", "005380=005930", "--dir", str(first)]):
        try:
            F.main(argv)
        except OSError:
            pass
        assert {n: (first / n).read_bytes() if (first / n).exists() else None for n in records} == records


def test_push_refuses_homepage_icons_until_main_names_company_homepages(repo, tmp_path):
    import test_logos_branch as B
    work, origin, _ = repo
    folder_ = B.make_logos(tmp_path / "logos", ["005930"])
    idx = json.loads((folder_ / "index.json").read_text(encoding="utf-8"))
    idx["logos"]["005930"]["route"] = "site"
    (folder_ / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    r = B.push_logos(work, folder_)
    assert r.returncode != 0 and "일부는 각 회사 홈페이지" in r.stdout and not B.tip(origin)
    (work / "src" / "info.jsx").write_text("회사 로고: Logo.dev, 일부는 각 회사 홈페이지. 로고의 권리는 각 회사에 있어요.",
                                           encoding="utf-8")
    B.git(work, "add", "-A")
    B.git(work, "commit", "-q", "-m", "credit line")
    B.git(work, "push", "-q", "origin", "main")
    r = B.push_logos(work, folder_)
    assert r.returncode == 0, r.stdout + r.stderr
    assert B.tip(origin)
