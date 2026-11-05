# -*- coding: utf-8 -*-
"""Jack's logo picker (tools/logos/build_review_page.py -> logo-review.html). No network and no logo provider.

Who is on the page and in what order (grids of 100 by market cap), our own icons manifest, the pre-pick order (Python
and the page's JavaScript agree), the fingerprint used for "both services agree", the export format, what Load choices
accepts, the pacing defaults, keys (publishable only, sk_ refused), storage (one localStorage key), and that the page
is noindex, English only and not linked from the app. The browser side is in tests/smoke_logo_review.py.
"""
import json
import pathlib
import random
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))
sys.path.insert(0, str(ROOT / "tests"))

import build_review_page as br  # noqa: E402
import logo_sources as lsrc  # noqa: E402
import logo_ids as li  # noqa: E402

TEMPLATE = (ROOT / "tools" / "logos" / "logo_review_template.html").read_text(encoding="utf-8")
PAGE = ROOT / "logo-review.html"
KEYS = ("bfClientTEST1234", "pk_TEST123456")


def fake_inputs(n_kr=250, n_us=120):
    """A made-up data.json, KRX listing and homepage CSV in the shapes the builder reads."""
    stocks = [{"t": c, "nk": f"KR{i}", "cls": "kr", "cap": 900.0 - i} for i, c in enumerate(br.MUST["kr"])]
    stocks += [{"t": f"1{i:04d}0", "nk": f"KR co {i}", "cls": "kr", "cap": 100.0 / (i + 1)} for i in range(n_kr)]
    stocks += [{"t": "100005", "nk": "pref", "cls": "kr", "cap": 50.0},                     # preferred share
               {"t": "069500", "nk": "ETF", "cls": "kr", "cap": 30.0, "etf": True},
               {"t": "153130", "nk": "bond fund", "cls": "bond", "cap": 9.0, "etf": True},
               {"t": "04020000", "nk": "gold", "cls": "metal", "cap": 9.0},
               {"t": "1ZZZZ0", "nk": "no cap", "cls": "kr", "cap": None}]
    stocks += [{"t": t, "nk": t, "cls": "us", "cap": 3000.0 - i} for i, t in enumerate(br.MUST["us"])]
    stocks += [{"t": f"U{i}", "nk": f"US co {i}", "cls": "us", "cap": 500.0 / (i + 1)} for i in range(n_us)]
    stocks += [{"t": "SPY", "cls": "us", "etf": True, "cap": 1.0}, {"t": "NOCAP", "cls": "us", "cap": float("nan")},
               {"t": "ZERO", "cls": "us", "cap": 0}]
    data = {"pxDate": "2026-11-04", "usPxDate": "2026-11-04", "asOf": "2026-11-05", "stocks": stocks}
    listing = {"005930": {"Code": "005930", "ISU_CD": "KR7005930003", "Market": "KOSPI"},
               "000660": {"Code": "000660", "ISU_CD": "KR7000660001", "Market": "KOSPI"},
               "100000": {"Code": "100000", "ISU_CD": "KR7100000004", "Market": "KOSDAQ"}}
    homepages = {"005930": {"code": "005930", "domain": "samsung.com", "domain_ok": "1", "hm_url": "www.samsung.com/sec",
                            "corp_cls": "Y", "status": "ok"},
                 "000660": {"code": "000660", "domain": "blog.naver.com", "domain_ok": "0", "hm_url": "blog.naver.com/x",
                            "domain_note": "platform host", "corp_cls": "Y", "status": "ok"}}
    return data, listing, homepages


def build(tmp_path, icons=None, **kw):
    data, listing, homepages = fake_inputs(**kw)
    manifest = tmp_path / "logo-review" / "icons.json"
    if icons is not None:
        (tmp_path / "logo-review" / "icons").mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(icons), encoding="utf-8")
    return br.build(data, listing, homepages, KEYS, icons_manifest=manifest, built_at="T", template=TEMPLATE,
                    root=tmp_path)


# ── who is on the page, in what order ──

def test_every_company_sorted_by_market_cap_in_grids_of_100(tmp_path):
    page, pdata, log = build(tmp_path)
    comp = pdata["companies"]
    kr = [c for c in comp if c["s"] == "kr"]
    us = [c for c in comp if c["s"] == "us"]
    codes = {c["c"] for c in comp}
    assert not codes & {"100005", "069500", "153130", "04020000", "SPY"}       # preferred share, ETFs, funds
    assert len(kr) == 3 + 250 + 1 and len(us) == 2 + 120 + 2
    assert [c["c"] for c in kr[:3]] == list(br.MUST["kr"]) and kr[-1]["c"] == "1ZZZZ0" and kr[-1]["nc"] == 1
    assert [c["c"] for c in us[-2:]] == ["NOCAP", "ZERO"] and all(c.get("nc") == 1 for c in us[-2:])  # no cap: last
    assert [c["r"] for c in kr] == list(range(1, len(kr) + 1)) and [c["r"] for c in us] == list(range(1, len(us) + 1))
    assert any("without a market cap" in line and "NOCAP" in line for line in log)
    grids = pdata["grids"]
    assert [g["id"] for g in grids] == ["KR-1", "KR-2", "KR-3", "US-1", "US-2"]
    assert [g["label"] for g in grids] == ["Korea 1–100", "Korea 101–200", "Korea 201–254",
                                           "US 1–100", "US 101–124"]
    for c in comp:
        g = next(x for x in grids if x["id"] == c["g"])
        assert g["side"] == c["s"] and g["from"] <= c["r"] <= g["to"]
    assert [(z["side"], z["label"]) for z in pdata["zones"]] == [("kr", "Korea 1–200"), ("kr", "Korea 201–254"),
                                                                  ("us", "US 1–124")]
    assert all(c["z"] == (0 if c["r"] <= 200 else 1) for c in comp)


def test_exact_identifiers_only(tmp_path):
    page, pdata, log = build(tmp_path)
    by = {c["c"]: c for c in pdata["companies"]}
    assert by["005930"]["tk"] == "005930.KS" and by["005930"]["isin"] == "KR7005930003" and by["005930"]["dom"] == "samsung.com"
    assert by["000660"]["dom"] == ""                                            # a platform host is never a domain
    assert by["100000"]["tk"] == "100000.KQ"
    assert by["AAPL"]["tk"] == "AAPL" and by["AAPL"]["isin"] == "" and by["AAPL"]["dom"] == ""
    for c in pdata["companies"]:
        if c["s"] == "kr":
            assert li.is_common_share(c["c"]) and c["tk"] in ("", c["c"] + ".KS", c["c"] + ".KQ")
            assert not c["isin"] or li.isin_valid(c["isin"])


def test_must_have_companies(tmp_path):
    data, listing, homepages = fake_inputs()
    data["stocks"] = [s for s in data["stocks"] if s["t"] != "000660"]
    with pytest.raises(SystemExit):
        br.build(data, listing, homepages, KEYS, icons_manifest=tmp_path / "none.json", template=TEMPLATE)


# ── our own website icons (optional manifest) ──

@pytest.mark.parametrize("raw,want", [
    ("icons/005930.png", "logo-review/icons/005930.png"), ("logo-review/icons/005930.png", "logo-review/icons/005930.png"),
    ("icons/../x.png", ""), ("logo-review/icons/../../x.png", ""), ("/logo-review/icons/x.png", ""),
    ("https://example.com/x.png", ""), ("icons/x.jpg", ""), ("icons/sub/x.png", ""), ("other/x.png", ""), ("", ""),
    (None, ""), ("icons/a b.png", ""), ("icons/.png", "")])
def test_icon_path(raw, want):
    assert br.icon_path(raw) == want


def test_icons_manifest_keeps_valid_entries_only(tmp_path):
    (tmp_path / "logo-review" / "icons").mkdir(parents=True)
    for name in ("005930.png", "AAPL.png", "100010.png"):
        (tmp_path / "logo-review" / "icons" / name).write_bytes(b"png")
    page, pdata, log = build(tmp_path, icons={
        "005930": "icons/005930.png", "AAPL": "logo-review/icons/AAPL.png",
        "100010": {"path": "icons/100010.png", "check": True},          # needs a look: Fix panel only
        "100005": "icons/005930.png",                                   # a preferred share of 100000: accepted, not shown
        "000660": "icons/missing.png", "005380": "../x.png", "999990": "icons/005930.png",
        "100020": {"path": "icons/100010.png", "check": "yes"}, "100030": ["icons/100010.png"]})
    by = {c["c"]: c for c in pdata["companies"]}
    assert by["005930"]["ic"] == "logo-review/icons/005930.png" and by["AAPL"]["ic"] == "logo-review/icons/AAPL.png"
    assert by["100010"]["ic"] == "logo-review/icons/100010.png" and by["100010"]["icx"] == 1
    assert "icx" not in by["005930"] and "100005" not in by
    assert by["000660"]["ic"] == "" and by["005380"]["ic"] == "" and by["100020"]["ic"] == "" and by["100030"]["ic"] == ""
    assert pdata["meta"]["icons"] == 3 and pdata["meta"]["iconsCheck"] == 1
    head = log[next(i for i, line in enumerate(log) if "website icons" in line)]
    assert "3 of 9" in head and "(2 kept, 1 to check)" in head and "preferred shares (same file as their issuer, not shown) 1" in head
    assert sum("left out" in line for line in log if "icon for" in line) == 5


def test_no_icons_manifest_is_fine(tmp_path):
    page, pdata, log = build(tmp_path)
    assert pdata["meta"]["icons"] == 0 and not any(c["ic"] for c in pdata["companies"])


# ── the pre-pick order ──

def fp(i):
    return {"g": "".join("f" if k // 2 == i else "0" for k in range(16)), "ar": 1.0}


def hit(i=None):
    return {"s": "hit", "hash": fp(i) if i is not None else None}


MISS = {"s": "miss"}


@pytest.mark.parametrize("cands,want", [
    # rule 1: both services agree -> the first agreeing route in order, even over an earlier Brandfetch hit
    ({"bfI": hit(1), "bfT": hit(2), "ldT": hit(2)}, ("bfT", "agree", "ldT")),
    ({"bfI": hit(1), "ldT": hit(3), "bfD": hit(3)}, ("ldT", "agree", "bfD")),
    ({"bfI": hit(1), "ldT": hit(1)}, ("bfI", "agree", "ldT")),
    # rules 2-5 by order
    ({"bfI": hit(1), "bfT": hit(2), "ldT": hit(3), "ldD": hit(4), "bfD": hit(5), "own": hit(6)}, ("bfI", "order", None)),
    ({"bfI": MISS, "bfT": hit(2), "ldT": hit(3)}, ("bfT", "order", None)),
    ({"bfI": MISS, "bfT": MISS, "ldT": hit(3), "ldD": hit(4), "bfD": hit(5)}, ("ldT", "order", None)),
    ({"bfI": MISS, "bfT": MISS, "ldT": MISS, "ldD": hit(4), "bfD": hit(5)}, ("ldD", "order", None)),
    ({"bfI": MISS, "bfT": MISS, "ldT": MISS, "ldD": MISS, "bfD": hit(5), "own": hit(6)}, ("bfD", "order", None)),
    ({"bfI": MISS, "bfT": MISS, "ldT": MISS, "ldD": MISS, "bfD": MISS, "own": hit(6)}, ("own", "order", None)),
    ({"bfI": MISS, "bfT": MISS, "ldT": MISS}, (None, "none", None)),
    ({}, (None, "none", None)),
    # our icon that needs a look is never pre-picked (Fix panel only); a kept one is, last
    ({"bfI": MISS, "bfT": MISS, "own": {"s": "hit", "hash": fp(6), "check": True}}, (None, "none", None)),
    ({"bfI": MISS, "ldT": hit(2), "own": {"s": "hit", "hash": fp(2), "check": True}}, ("ldT", "order", None)),
    ({"bfI": MISS, "bfT": MISS, "own": {"s": "hit", "hash": fp(6), "check": False}}, ("own", "order", None)),
    # never agreement within one provider, nor with our own icon; no fingerprint = unknown, not agreement
    ({"bfI": hit(1), "bfT": hit(2), "bfD": hit(2), "ldT": hit(3)}, ("bfI", "order", None)),
    ({"bfI": hit(1), "ldT": hit(2), "own": hit(2)}, ("bfI", "order", None)),
    ({"bfI": hit(1), "bfT": hit(2), "ldT": hit()}, ("bfI", "order", None)),
    ({"bfI": {"s": "off"}, "bfT": hit(2), "ldT": MISS}, ("bfT", "order", None)),
])
def test_pre_pick_order(cands, want):
    got = br.pre_pick(cands)
    assert (got["pick"], got["via"], got["partner"]) == want and got["settled"]


def test_pre_pick_is_settled_only_when_every_route_has_ended():
    assert not br.pre_pick({"bfI": hit(1), "ldD": {"s": "recheck"}})["settled"]     # a pending route could agree
    assert not br.pre_pick({"bfI": {"s": "queued"}, "bfT": hit(1)})["settled"]
    for s in ("na", "hit", "miss", "off", "err", "stopped"):
        assert br.pre_pick({"bfI": {"s": s}})["settled"]


def test_agreement_needs_a_similar_shape():
    a = {"g": "8" * 256, "ar": 1.0}
    assert br.agrees(a, {"g": "8" * 256, "ar": 1.3}) and not br.agrees(a, {"g": "8" * 256, "ar": 1.4})
    near = {"g": "a" * 256, "ar": 1.0}                                            # 2 of 15 apart in every cell
    far = {"g": "b" * 256, "ar": 1.0}                                             # 3 of 15
    assert br.distance(a["g"], near["g"]) == pytest.approx(2 / 15) and br.agrees(a, near)
    assert not br.agrees(a, far) and not br.agrees(a, None) and not br.agrees(a, {"g": "8" * 64, "ar": 1.0})


def pure_js():
    m = re.search(r"// ==pure-start==.*?\n(.*?)// ==pure-end==", TEMPLATE, re.S)
    assert m, "pure block markers"
    return m.group(1)


def node(js):
    r = subprocess.run(["node"], input=pure_js() + "\n" + js, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_page_pre_pick_is_the_same_as_python():
    rng = random.Random(7)
    states = ["na", "hit", "hit", "hit", "miss", "off", "err", "stopped", "queued", "recheck"]
    cases = []
    for _ in range(600):
        c = {}
        for r in br.ORDER:
            s = rng.choice(states)
            c[r] = {"s": s, "hash": fp(rng.randrange(4)) if s == "hit" and rng.random() < 0.8 else None,
                    "check": r == "own" and rng.random() < 0.5}
        cases.append(c)
    got = node(f"console.log(JSON.stringify({json.dumps(cases)}.map(prePick)));")
    want = [br.pre_pick(c) for c in cases]
    assert got == want
    assert sum(w["via"] == "agree" for w in want) > 30 and sum(w["via"] == "order" for w in want) > 30


def test_page_routes_and_sources_match_python():
    got = node("console.log(JSON.stringify([ROUTES.map(r => [r.id, r.src]), SOURCES, AGREE_MAX, ASPECT_MAX, STORE_KEY]));")
    assert got[0] == [[r, br.SOURCE[r]] for r in br.ORDER] and got[1] == list(br.SOURCES)
    assert got[2] == br.AGREE_MAX and got[3] == br.ASPECT_MAX and got[4] == "baepsae-logo-review-v1"


# ── the fingerprint ──

def shape(kind, W=64, pad=8, color=(27, 43, 75), bg=None):
    """RGBA pixels of a test picture: a filled disc, a ring, a bar or a cross, inside `pad` px of transparent margin."""
    px = []
    lo, hi = pad, W - pad
    cx = cy = (W - 1) / 2
    rad = (hi - lo) / 2
    for y in range(W):
        for x in range(W):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            inside = {"disc": d <= rad, "ring": rad * 0.55 <= d <= rad,
                      "bar": lo <= x < hi and abs(y - cy) <= (hi - lo) / 6,
                      "cross": lo <= x < hi and lo <= y < hi and (abs(x - cx) <= (hi - lo) / 7 or abs(y - cy) <= (hi - lo) / 7)}[kind]
            px += list(color) + [255] if inside else (list(bg) + [255] if bg else [0, 0, 0, 0])
    return px


def test_fingerprint_matches_the_same_shape_and_separates_others():
    pics = {"disc": shape("disc"), "disc-pad": shape("disc", pad=20), "disc-white-bg": shape("disc", bg=(255, 255, 255)),
            "disc-red": shape("disc", color=(200, 30, 30)), "ring": shape("ring"), "bar": shape("bar"),
            "cross": shape("cross"), "white-on-clear": shape("disc", color=(255, 255, 255)), "empty": [0] * (64 * 64 * 4)}
    out = node(f"var P = {json.dumps(pics)}; var o = {{}}; for (var k in P) o[k] = hashFromPixels(P[k], 64, 64);"
               "console.log(JSON.stringify(o));")
    assert out["empty"] is None
    assert len(out["disc"]["g"]) == 256 and out["disc"]["ar"] == pytest.approx(1, abs=0.05)
    for k in ("disc-pad", "disc-white-bg", "disc-red", "white-on-clear"):    # padding, a white square, colour, white logo
        assert br.agrees(out["disc"], out[k]), k
    for a, b in (("disc", "ring"), ("disc", "bar"), ("disc", "cross"), ("ring", "cross"), ("bar", "cross")):
        assert not br.agrees(out[a], out[b]), (a, b, br.distance(out[a]["g"], out[b]["g"]))
    assert out["bar"]["ar"] > 2.5


# ── addresses, export, Load choices ──

def company_js():
    return {"005930": {"c": "005930", "tk": "005930.KS", "isin": "KR7005930003", "dom": "samsung.com", "ic": ""},
            "AAPL": {"c": "AAPL", "tk": "AAPL", "isin": "", "dom": "", "ic": "logo-review/icons/AAPL.png"}}


def test_page_addresses_are_logo_ids_urls():
    keys = {"bf": KEYS[0], "ld": KEYS[1]}
    got = node(f"var C = {json.dumps(company_js())}, K = {json.dumps(keys)};"
               "console.log(JSON.stringify(SOURCES.map(s => [s, candidateUrl(C['005930'], s, K), candidateUrl(C.AAPL, s, K)])));")
    prov = {"bf": "brandfetch", "ld": "logodev"}
    for src, kr, us in got:
        rt = next((r for r in br.ORDER if br.SOURCE[r] == src), None)
        if rt is None:
            assert src == "letter" and kr is None and us is None
        elif rt == "own":
            assert kr is None and us == "logo-review/icons/AAPL.png"
        else:
            p, route = br.PROVIDER[rt], {"I": "isin", "T": "ticker", "D": "domain"}[rt[-1]]
            ident = {"isin": "KR7005930003", "ticker": "005930.KS", "domain": "samsung.com"}[route]
            assert kr == li.logo_url(prov[p], route, ident, keys[p])
            assert us == (li.logo_url(prov[p], "ticker", "AAPL", keys[p]) if route == "ticker" else None)


def test_export_has_reviewed_companies_only_and_no_image_data():
    ch = {"AAPL": {"source": "own-icon", "url": "logo-review/icons/AAPL.png", "reviewed": "2026-11-05"},
          "005930": {"source": "letter", "url": "x", "reviewed": "2026-11-05", "img": "data:image/png;base64,AA"}}
    got = node(f"console.log(JSON.stringify(exportChoices({json.dumps(ch)}, '2026-11-05T10:00:00+09:00')));")
    assert got == {"version": 1, "created": "2026-11-05T10:00:00+09:00", "choices": {
        "005930": {"source": "letter", "url": None, "reviewed": "2026-11-05"},
        "AAPL": {"source": "own-icon", "url": "logo-review/icons/AAPL.png", "reviewed": "2026-11-05"}}}
    assert list(got["choices"]) == ["005930", "AAPL"]


def test_load_choices_accepts_only_exact_addresses_for_companies_on_the_page():
    keys = {"bf": KEYS[0], "ld": KEYS[1]}
    good = li.logo_url("brandfetch", "isin", "KR7005930003", keys["bf"])
    entries = {
        "005930": {"source": "bf-isin", "url": good, "reviewed": "2026-11-05", "extra": "dropped"},
        "AAPL": {"source": "own-icon", "url": "logo-review/icons/AAPL.png", "reviewed": "2026-11-05"},
    }
    bad = {
        "unknown code": ("999999", {"source": "letter", "url": None, "reviewed": "2026-11-05"}),
        "unknown source": ("005930", {"source": "bf-name", "url": good, "reviewed": "2026-11-05"}),
        "secret key": ("005930", {"source": "ld-ticker", "reviewed": "2026-11-05",
                                  "url": li.logo_url("logodev", "ticker", "005930.KS", "sk_live_secret")}),
        "other key": ("005930", {"source": "bf-isin", "url": li.logo_url("brandfetch", "isin", "KR7005930003", "other"),
                                 "reviewed": "2026-11-05"}),
        "other identifier": ("005930", {"source": "bf-ticker", "reviewed": "2026-11-05",
                                        "url": li.logo_url("brandfetch", "ticker", "005930", keys["bf"])}),
        "image data": ("005930", {"source": "bf-isin", "url": "data:image/png;base64,AAAA", "reviewed": "2026-11-05"}),
        "letter with an address": ("005930", {"source": "letter", "url": good, "reviewed": "2026-11-05"}),
        "no date": ("005930", {"source": "letter", "url": None}),
        "impossible date": ("005930", {"source": "letter", "url": None, "reviewed": "2026-13-45"}),
        "Feb 30": ("005930", {"source": "letter", "url": None, "reviewed": "2026-02-30"}),
        "no identifier": ("AAPL", {"source": "bf-isin", "url": None, "reviewed": "2026-11-05"}),
        "another icon": ("AAPL", {"source": "own-icon", "url": "logo-review/icons/x.png", "reviewed": "2026-11-05"}),
        "not an object": ("005930", "letter"),
    }
    js = f"var C = {json.dumps(company_js())}, K = {json.dumps(keys)};\n"
    js += f"var ok = validateImport({{version: 1, created: 'x', choices: {json.dumps(entries)}}}, C, K);\n"
    js += f"var B = {json.dumps({k: v for k, v in bad.items()})};\n"
    js += "var each = {}; for (var k in B) { var ch = {}; ch[B[k][0]] = B[k][1]; each[k] = validateImport({version: 1, choices: ch}, C, K); }\n"
    js += ("var errs = [null, 1, [], 'x', {version: 2, choices: {}}, {choices: {}}, {version: 1}, {version: 1, choices: []}]"
           ".map(o => validateImport(o, C, K).error || null);\n")
    js += "console.log(JSON.stringify([ok, each, errs]));"
    ok, each, errs = node(js)
    assert ok == {"choices": {"005930": {"source": "bf-isin", "url": good, "reviewed": "2026-11-05"},
                              "AAPL": {"source": "own-icon", "url": "logo-review/icons/AAPL.png", "reviewed": "2026-11-05"}},
                  "rejected": []}
    for name, res in each.items():
        assert res["choices"] == {} and len(res["rejected"]) == 1, name
    assert all(errs), errs


def test_merge_choices_later_review_wins_and_the_file_wins_a_tie():
    a = {"X": {"source": "letter", "url": None, "reviewed": "2026-11-05"},
         "Y": {"source": "letter", "url": None, "reviewed": "2026-11-06"},
         "Z": {"source": "letter", "url": None, "reviewed": "2026-11-05"}}
    b = {"X": {"source": "own-icon", "url": "u", "reviewed": "2026-11-05"},
         "Y": {"source": "own-icon", "url": "u", "reviewed": "2026-11-05"},
         "Z": {"source": "letter", "url": None, "reviewed": "2026-11-05"},
         "W": {"source": "letter", "url": None, "reviewed": "2026-11-04"}}
    m = node(f"console.log(JSON.stringify(mergeChoices({json.dumps(a)}, {json.dumps(b)})));")
    assert m["choices"]["X"]["source"] == "own-icon" and m["choices"]["Y"]["source"] == "letter" and "W" in m["choices"]
    assert (m["added"], m["replaced"], m["kept"], m["same"]) == (1, 1, 1, 1)
    assert sorted(m["used"]) == ["W", "X", "Z"]                         # Y: the newer choice here stays, with its marks


def test_summary_counts_reviewed_logo_and_letter_per_size_group():
    comps = [{"c": f"K{i}", "s": "kr", "z": 0 if i < 3 else 1} for i in range(5)] + [{"c": "U0", "s": "us", "z": 0}]
    zones = [{"side": "kr", "z": 0, "label": "Korea 1-3"}, {"side": "kr", "z": 1, "label": "Korea 4-5"},
             {"side": "us", "z": 0, "label": "US 1-1"}]
    ch = {"K0": {"source": "bf-isin"}, "K1": {"source": "letter"}, "K3": {"source": "ld-domain"}, "U0": {"source": "letter"}}
    rows = node(f"console.log(JSON.stringify(summarize({json.dumps(comps)}, {json.dumps(ch)}, {json.dumps(zones)})));")
    got = [(r["label"], r["n"], r["reviewed"], r["logo"], r["letter"]) for r in rows]
    assert got == [("Korea 1-3", 3, 2, 1, 1), ("Korea 4-5", 2, 1, 1, 0), ("Korea all", 5, 3, 2, 1),
                   ("US 1-1", 1, 1, 0, 1), ("US all", 1, 1, 0, 1), ("All", 6, 4, 2, 2)]


def test_kst_dates():
    got = node("console.log(JSON.stringify([kstDate(Date.UTC(2026, 10, 4, 15, 30)), kstStamp(Date.UTC(2026, 10, 4, 15, 30))]));")
    assert got == ["2026-11-05", "2026-11-05T00:30:00+09:00"]


# ── pacing, keys, storage, links ──

def test_pacing_and_check_defaults_are_the_test_pages():
    cfg = re.search(r"var CFG = \{(.*?)\};", TEMPLATE, re.S).group(1)
    for k, v in (("bfGapMs", "500"), ("ldGapMs", "250"), ("recheckMs", "330000"), ("controls", "true"),
                 ("checkEvery", "100"), ("badEvery", "300"), ("autostart", "false")):
        assert re.search(rf"\b{k}: {v}\b", cfg), k
    assert "fallback/404" in TEMPLATE and "&fallback=404" in TEMPLATE


def test_the_builder_refuses_secret_keys(tmp_path):
    f = tmp_path / "k.env"
    f.write_text("BRANDFETCH_CLIENT_ID=abcdef123456\nLOGODEV_TOKEN=sk_secretvalue\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        br.main(["--keys-file", str(f), "--data", str(tmp_path / "none.json")])
    assert "sk_secretvalue" not in str(e.value)


def test_built_page_has_only_the_two_publishable_keys(tmp_path):
    page, pdata, log = build(tmp_path)
    keys = json.loads(re.search(r"var KEYS = (\{.*?\});", page).group(1))
    assert keys == {"bf": KEYS[0], "ld": KEYS[1]}
    assert "sk_" not in page and page.count("pk_") == 1


def test_only_this_pages_own_storage_key():
    js = TEMPLATE.split("<script>", 1)[1]
    assert "sessionStorage" not in js and "indexedDB" not in js and "document.cookie" not in js
    assert "caches." not in js and "serviceWorker" not in js
    uses = re.findall(r"localStorage\.(\w+)\(([^,)]*)", js)
    assert uses == [("getItem", "STORE_KEY"), ("setItem", "STORE_KEY")], uses


SITE_PAGES = ["index.html", "app.html", "app-preview.html", "baepsae.html", "styleguide.html", "template.html",
              "sw.js", "manifest.webmanifest", "src/v2/template.html"]


def test_the_page_is_not_linked_from_the_site():
    files = list(SITE_PAGES)
    for d in ("src", "styleguide"):
        files += [str(p.relative_to(ROOT)) for p in (ROOT / d).rglob("*")
                  if p.is_file() and p.suffix in (".js", ".jsx", ".html", ".json", ".css")]
    found = [f for f in files if (ROOT / f).exists() and "logo-review" in (ROOT / f).read_text(encoding="utf-8")]
    assert not found, found


def check_page(html, template=TEMPLATE):
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    keys = json.loads(re.search(r"var KEYS = (\{.*?\});", html).group(1))
    li.check_publishable_keys(keys["bf"], keys["ld"])                              # publishable only, never sk_
    assert set(keys) == {"bf", "ld"}
    assert lsrc.render(template, data, (keys["bf"], keys["ld"])) == html, "logo-review.html was edited by hand"
    assert '<meta name="robots" content="noindex,nofollow">' in html
    assert "<title>Logo picker (temporary review tool)</title>" in html
    outside = html.replace(re.search(r'<script id="data".*?</script>', html, re.S).group(0), "")
    assert not re.search("[ㄱ-ㆎ가-힣]", outside), "Korean text outside the company data"
    from test_text import EMOJI, banned_words
    assert not EMOJI.findall(html)
    assert not [w for w in banned_words() if w in html]
    return data


def test_a_built_page_is_safe(tmp_path):
    page, pdata, log = build(tmp_path)
    check_page(page)


# ── adding our website icons (tools/logos/add_site_icons.py): append only, one file per picture, lossless ──

def png_bytes(color, size=(128, 128), shape="square", mode="RGBA"):
    from PIL import Image, ImageDraw
    import io
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    (d.ellipse if shape == "disc" else d.rectangle)([16, 16, size[0] - 16, size[1] - 16], fill=color)
    buf = io.BytesIO()
    im.convert(mode).save(buf, "PNG", compress_level=0)                    # big on purpose: room to optimise
    return buf.getvalue()


def collection(tmp_path, kept, review, decisions=None):
    src = tmp_path / "src"
    (src / "kr").mkdir(parents=True, exist_ok=True)
    (src / "review").mkdir(parents=True, exist_ok=True)
    for folder, items in (("kr", kept), ("review", review)):
        for code, data in items.items():
            (src / folder / f"{code}.png").write_bytes(data)
    rows = {**{c: "kept" for c in kept}, **{c: "needs_review" for c in review}, **(decisions or {})}
    (src / "site_icons.csv").write_text("code,decision\n" + "".join(f"{c},{d}\n" for c, d in rows.items()),
                                        encoding="utf-8")
    return src


def test_add_site_icons_append_only_one_file_per_picture(tmp_path):
    import add_site_icons as ai
    red, blue, green = png_bytes((200, 0, 0, 255)), png_bytes((0, 0, 200, 255), shape="disc"), png_bytes((0, 150, 0, 255))
    src = collection(tmp_path, {"005930": red, "005935": red, "000660": blue, "123450": green},
                     {"003310": png_bytes((90, 90, 90, 255), shape="disc")},
                     decisions={"777770": "too_small"})
    (src / "kr" / "777770.png").write_bytes(red)                               # the CSV says too_small: refused
    (src / "kr" / "BADCODE.png").write_bytes(red)                              # not a KRX code: refused
    out, man = tmp_path / "site" / "logo-review" / "icons", tmp_path / "site" / "logo-review" / "icons.json"
    n, log = ai.add_icons(src, out, man)
    m = json.loads(man.read_text(encoding="utf-8"))
    assert m == {"005930": "icons/005930.png", "005935": "icons/005930.png", "000660": "icons/000660.png",
                 "123450": "icons/123450.png", "003310": {"path": "icons/003310.png", "check": True}}
    assert sorted(p.name for p in out.glob("*.png")) == ["000660.png", "003310.png", "005930.png", "123450.png"]
    assert (n["kept"], n["check"], n["files written"], n["same picture as a file already there"], n["refused"]) == (4, 1, 4, 1, 2)
    for code in ("005930", "000660", "123450"):                                # lossless: same pixels, smaller file
        assert ai.rgba((out / f"{code}.png").read_bytes()) == ai.rgba((src / "kr" / f"{code}.png").read_bytes())
        assert (out / f"{code}.png").stat().st_size < (src / "kr" / f"{code}.png").stat().st_size
    # a later collection: new codes are added, nothing that is there changes (not even when the source changed)
    before = {p.name: p.read_bytes() for p in out.glob("*.png")}
    (src / "kr" / "005930.png").write_bytes(green)
    (src / "kr" / "000020.png").write_bytes(green)                             # same picture as 123450's file
    (src / "kr" / "000040.png").write_bytes(png_bytes((10, 10, 10, 255), shape="disc"))
    (src / "site_icons.csv").write_text((src / "site_icons.csv").read_text() + "000020,kept\n000040,kept\n",
                                        encoding="utf-8")
    n2, log2 = ai.add_icons(src, out, man)
    m2 = json.loads(man.read_text(encoding="utf-8"))
    assert {k: v for k, v in m2.items() if k in m} == m
    assert m2["000020"] == "icons/123450.png" and m2["000040"] == "icons/000040.png"
    assert all((out / k).read_bytes() == v for k, v in before.items())
    assert n2["already in the manifest (left as is)"] == 5 and n2["files written"] == 1


def test_add_site_icons_never_overwrites_a_file(tmp_path):
    import add_site_icons as ai
    out, man = tmp_path / "icons", tmp_path / "icons.json"
    out.mkdir()
    black = png_bytes((0, 0, 0, 255))
    (out / "005930.png").write_bytes(black)                                    # there, but not in the manifest
    src = collection(tmp_path, {"005930": png_bytes((250, 0, 0, 255))}, {})
    n, log = ai.add_icons(src, out, man)
    assert n["refused"] == 1 and any("already exists with another picture" in line for line in log)
    assert json.loads(man.read_text()) == {} and (out / "005930.png").read_bytes() == black


@pytest.mark.skipif(not (ROOT / "logo-review" / "icons.json").exists(), reason="no icons yet")
def test_the_committed_icons_are_complete_and_stored_once():
    import add_site_icons as ai
    man = json.loads((ROOT / "logo-review" / "icons.json").read_text(encoding="utf-8"))
    files = sorted((ROOT / "logo-review" / "icons").glob("*.png"))
    paths = {ai.entry_path(e) for e in man.values()}
    assert paths == {f"icons/{p.name}" for p in files}                        # every file used, none missing
    keys = [ai.pixel_key(p.read_bytes()) for p in files]
    assert len(keys) == len(set(keys))                                        # no picture stored twice
    for code, e in man.items():
        assert li.is_krx_code(code) and br.icon_path(ai.entry_path(e))
        assert isinstance(e, str) or (set(e) == {"path", "check"} and e["check"] is True)
    assert sum(p.stat().st_size for p in files) < 4_000_000


@pytest.mark.skipif(not PAGE.exists(), reason="logo-review.html not built")
def test_the_committed_page_is_the_template_plus_its_data_and_is_safe():
    data = check_page(PAGE.read_text(encoding="utf-8"))
    comps = data["companies"]
    assert len({c["c"] for c in comps}) == len(comps)
    kr = [c for c in comps if c["s"] == "kr"]
    us = [c for c in comps if c["s"] == "us"]
    assert len(kr) > 2000 and len(us) > 500 and data["meta"]["counts"] == {"kr": len(kr), "us": len(us)}
    assert [c["c"] for c in kr[:3]] != [] and {"005930", "000660", "005380"} <= {c["c"] for c in kr[:100]}
    assert [c["r"] for c in kr] == list(range(1, len(kr) + 1)) and [c["r"] for c in us] == list(range(1, len(us) + 1))
    for g in data["grids"]:
        members = [c for c in comps if c["g"] == g["id"]]
        assert 0 < len(members) <= 100 and members[0]["r"] == g["from"] and members[-1]["r"] == g["to"]
    for c in comps:
        if c["s"] == "kr":
            assert li.is_common_share(c["c"]), c["c"]
            assert c["tk"] in ("", c["c"] + ".KS", c["c"] + ".KQ"), c
            assert not c["isin"] or li.isin_valid(c["isin"]), c
            assert not c["dom"] or (li.homepage_domain(c["dom"]) == c["dom"] and not li.is_shared_host(c["dom"])), c
        else:
            assert c["tk"] == c["c"] and not c["isin"] and not c["dom"], c
        assert not c["ic"] or (br.icon_path(c["ic"]) == c["ic"] and (ROOT / c["ic"]).is_file()), c
        assert c.get("icx", 0) in (0, 1) and (not c.get("icx") or c["ic"]), c
    if (ROOT / "logo-review" / "icons.json").exists():
        man = json.loads((ROOT / "logo-review" / "icons.json").read_text(encoding="utf-8"))
        shown = {c["c"]: c for c in comps if c["ic"]}
        assert shown and all(c in man for c in shown)
        assert {c for c, x in shown.items() if x.get("icx")} == {c for c, e in man.items() if not isinstance(e, str) and c in shown}
