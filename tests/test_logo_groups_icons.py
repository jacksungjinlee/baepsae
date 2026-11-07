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
