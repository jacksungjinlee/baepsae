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
    assert pdata["meta"]["ownCheck"] == "logo-review/icons/005930.png"          # the largest company's kept icon
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


def test_page_urls_match_logo_ids_on_the_edge_cases():
    """The picker builds provider URLs in JavaScript (logoUrl); they must equal tools/logos/logo_ids.logo_url
    character for character: a US class share (BRK-B), letters in a KRX code (0126Z0.KS), logo.dev ISIN and domain
    routes, characters that must be escaped ('A B/C?'), keys with - _ ~, the second load (&v=2) and a check size."""
    cases = [("bf", "isin", "KR7005930003"), ("bf", "ticker", "005930.KS"), ("bf", "ticker", "BRK-B"),
             ("bf", "domain", "samsung.com"), ("ld", "ticker", "247540.KQ"), ("ld", "ticker", "0126Z0.KS"),
             ("ld", "domain", "ks-industry.co.kr"), ("ld", "isin", "KR7005930003"), ("bf", "ticker", "A B/C?"),
             ("ld", "ticker", "BRK-B"), ("ld", "domain", "xn--bj0bj06e.kr")]
    keys = {"bf": "bf_Client-01~x", "ld": "pk_abc_DEF-9"}
    js = (f"var K = {json.dumps(keys)}; console.log(JSON.stringify({json.dumps(cases)}.map(c => logoUrl(c[0], c[1], c[2], "
          "K[c[0]])).concat([logoUrl('ld', 'domain', 'x.co.kr', 'pk_k', '2'), logoUrl('bf', 'ticker', 'AAPL', 'cid', null, 100),"
          " logoUrl('ld', 'ticker', 'AAPL', 'pk_k', null, 156)])));")
    got = node(js)
    prov = {"bf": "brandfetch", "ld": "logodev"}
    want = [li.logo_url(prov[p], r, i, keys[p]) for p, r, i in cases]
    want += [li.logo_url("logodev", "domain", "x.co.kr", "pk_k") + "&v=2", li.logo_url("brandfetch", "ticker", "AAPL", "cid", size=100),
             li.logo_url("logodev", "ticker", "AAPL", "pk_k", size=156)]
    assert got == want


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


# ── a pasted image address ("manual") and None of these - find more ("need"), added 2026-11-05 ──

def test_extra_sources_match_python():
    got = node("console.log(JSON.stringify([SOURCES, EXTRA_SOURCES, ALL_SOURCES, MANUAL_MAX, MANUAL_MIN_PX, MANUAL_SOFT_PX]));")
    assert got[0] == list(br.SOURCES) and got[1] == list(br.EXTRA_SOURCES) == ["manual", "need"]
    assert got[2] == list(br.SOURCES) + ["manual", "need"] and got[3:] == [2000, 64, 96]


def manual(raws):
    return node(f"console.log(JSON.stringify({json.dumps(raws)}.map(checkManualUrl)));")


def test_manual_url_https_only_and_normalised():
    ok = {"https://www.samsung.com/images/logo.png": "https://www.samsung.com/images/logo.png",
          "  https://x.co.kr/a.png\n": "https://x.co.kr/a.png",
          "HTTPS://X.CO.KR/a.png": "https://x.co.kr/a.png",
          "https://x.co.kr/logo.svg?v=3#top": "https://x.co.kr/logo.svg?v=3#top",
          "https://x.co.kr:8443/a.png": "https://x.co.kr:8443/a.png",
          "https://notlogo.dev/a.png": "https://notlogo.dev/a.png",            # not a provider's own domain
          "https://logo.dev.example.com/a.png": "https://logo.dev.example.com/a.png",
          "https://www.삼성.com/로고.png": "https://www.xn--cg4bki.com/%EB%A1%9C%EA%B3%A0.png",
          "https://x.com/" + "a" * 1986: "https://x.com/" + "a" * 1986}      # exactly 2,000 characters
    upgraded = {"http://x.co.kr/a.png": "https://x.co.kr/a.png", "HTTP://X.CO.KR:80/a.png": "https://x.co.kr/a.png",
                "http://x.co.kr:8080/a.png": "https://x.co.kr:8080/a.png"}
    got = manual(list(ok) + list(upgraded))
    for (raw, want), g in zip(list(ok.items()) + list(upgraded.items()), got):
        assert g.get("url") == want and not g.get("error"), (raw[:60], g)
        assert ("http to https" in g["note"]) == (raw in upgraded), (raw, g)
    again = manual([g["url"] for g in got])                                      # the checked form is stable
    assert [a["url"] for a in again] == [g["url"] for g in got] and not any(a["note"] for a in again)
    assert all(len(g["url"]) <= 2000 for g in got)


@pytest.mark.parametrize("raw,why", [
    ("", "Paste"), ("   ", "Paste"), (None, "No address"), (5, "No address"),
    ("data:image/png;base64,iVBORw0KGgo=", "data:"), (" DATA:image/svg+xml,<svg/>", "data:"),
    ("javascript:alert(1)", "script"), ("JavaScript:alert(1)", "script"), ("java\tscript:alert(1)", "script"),
    ("vbscript:msgbox", "script"), ("ftp://x.com/a.png", "https"), ("file:///etc/passwd", "https"),
    ("blob:https://x.com/1234", "https"), ("//x.com/a.png", "full web address"), ("x.com/a.png", "full web address"),
    ("https://user:pw@x.com/a.png", "user name"), ("https://x.com/a b.png", "space"),
    ("https://x.com/a.png\nhttps://y.com/b.png", "space"),
    ("https://cdn.brandfetch.io/ticker/AAPL/w/128/h/128?c=x", "Brandfetch"), ("https://asset.brandfetch.io/x.png", "Brandfetch"),
    ("https://brandfetch.com/x.png", "Brandfetch"), ("https://img.logo.dev/apple.com?token=pk_x", "logo.dev"),
    ("https://LOGO.DEV/x.png", "logo.dev"), ("http://img.logo.dev./x", "logo.dev"),
    ("https://127.0.0.1/a.png", "public website"), ("https://169.254.169.254/latest/meta-data", "public website"),
    ("https://0x7f.1/a.png", "public website"), ("https://[::1]/a.png", "public website"),
    ("https://localhost:8443/a.png", "public website"), ("https://intranet/a.png", "public website"),
    ("https://printer.local/a.png", "public website"), ("https://x.home.arpa/a.png", "public website"),
    ("https://app.localhost/a.png", "public website"),
    ("https://x.com/" + "a" * 1987, "at most 2000"), ("https://" + "a" * 2100, "at most 2000"),
])
def test_manual_url_refused(raw, why):
    g = manual([raw])[0]
    assert "url" not in g and why in g["error"], (str(raw)[:60], g)


def test_preview_size_rule():
    got = node("console.log(JSON.stringify([[128,128],[96,96],[95,400],[64,64],[63,500],[500,63],[0,0],[null,10]]"
               ".map(x => judgeSize(x[0], x[1]))));")
    assert [(g["ok"], g.get("warn")) for g in got] == [(True, False), (True, False), (True, True), (True, True),
                                                       (False, None), (False, None), (False, None), (False, None)]
    assert "63 × 500 px" in got[4]["text"] and "64 px" in got[4]["text"] and "measure" in got[6]["text"]


def test_export_and_load_choices_with_manual_and_need():
    keys = {"bf": KEYS[0], "ld": KEYS[1]}
    good = li.logo_url("brandfetch", "isin", "KR7005930003", keys["bf"])
    comps = dict(company_js(), **{"000660": {"c": "000660", "tk": "000660.KS", "isin": "", "dom": "", "ic": ""}})
    ch = {"005930": {"source": "manual", "url": "https://www.samsung.com/logo.png", "reviewed": "2026-11-05"},
          "000660": {"source": "need", "url": None, "reviewed": "2026-11-05"},
          "AAPL": {"source": "own-icon", "url": "logo-review/icons/AAPL.png", "reviewed": "2026-11-04"}}
    js = (f"var C = {json.dumps(comps)}, K = {json.dumps(keys)}, ch = {json.dumps(ch)};\n"
          "var ex = exportChoices(ch, 'T'), back = validateImport(JSON.parse(JSON.stringify(ex)), C, K);\n"
          "console.log(JSON.stringify([ex, back, exportChoices(back.choices, 'T')]));")
    ex, back, again = node(js)
    assert ex == {"version": 1, "created": "T", "choices": ch} and back == {"choices": ch, "rejected": []} and again == ex
    need_url = node("console.log(JSON.stringify(exportChoices({X: {source: 'need', url: 'u', reviewed: '2026-11-05'}}, 'T')));")
    assert need_url["choices"]["X"]["url"] is None
    bad = {
        "http (not the checked form)": ("005930", {"source": "manual", "url": "http://www.samsung.com/logo.png"}),
        "data:": ("005930", {"source": "manual", "url": "data:image/png;base64,AAAA"}),
        "javascript:": ("005930", {"source": "manual", "url": "javascript:alert(1)"}),
        "provider address": ("005930", {"source": "manual", "url": good}),
        "no address": ("005930", {"source": "manual", "url": None}),
        "too long": ("005930", {"source": "manual", "url": "https://x.com/" + "a" * 1990}),
        "need with an address": ("000660", {"source": "need", "url": "https://x.com/a.png"}),
        "manual for an unknown company": ("999990", {"source": "manual", "url": "https://x.com/a.png"}),
        "unknown source": ("005930", {"source": "manuall", "url": "https://x.com/a.png"}),
        "manual, bad date": ("005930", {"source": "manual", "url": "https://x.com/a.png", "reviewed": "2026-02-30"}),
    }
    js = f"var C = {json.dumps(comps)}, K = {json.dumps(keys)}, B = {json.dumps(bad)}, out = {{}};\n"
    js += ("for (var k in B) { var e = Object.assign({reviewed: '2026-11-05'}, B[k][1]), c = {}; c[B[k][0]] = e;"
           " out[k] = validateImport({version: 1, choices: c}, C, K); }\nconsole.log(JSON.stringify(out));")
    for name, res in node(js).items():
        assert res["choices"] == {} and len(res["rejected"]) == 1, (name, res)


# What the page of PR #45 (merged 2026-11-05, the one Jack is using) writes: these must read back unchanged.
def old_choices(keys):
    return {"005930": {"source": "bf-isin", "url": li.logo_url("brandfetch", "isin", "KR7005930003", keys["bf"]),
                       "reviewed": "2026-11-05"},
            "000660": {"source": "ld-ticker", "url": li.logo_url("logodev", "ticker", "000660.KS", keys["ld"]),
                       "reviewed": "2026-11-05"},
            "005380": {"source": "letter", "url": None, "reviewed": "2026-11-04"},
            "AAPL": {"source": "own-icon", "url": "logo-review/icons/AAPL.png", "reviewed": "2026-11-05"},
            "MSFT": {"source": "bf-ticker", "url": li.logo_url("brandfetch", "ticker", "MSFT", keys["bf"]),
                     "reviewed": "2026-11-05"}}


def old_comps():
    return {"005930": {"c": "005930", "tk": "005930.KS", "isin": "KR7005930003", "dom": "samsung.com", "ic": ""},
            "000660": {"c": "000660", "tk": "000660.KS", "isin": "KR7000660001", "dom": "", "ic": ""},
            "005380": {"c": "005380", "tk": "005380.KS", "isin": "", "dom": "", "ic": ""},
            "AAPL": {"c": "AAPL", "tk": "AAPL", "isin": "", "dom": "", "ic": "logo-review/icons/AAPL.png"},
            "MSFT": {"c": "MSFT", "tk": "MSFT", "isin": "", "dom": "", "ic": ""}}


def test_an_old_export_file_loads_unchanged_and_exports_the_same():
    keys = {"bf": KEYS[0], "ld": KEYS[1]}
    old = {"version": 1, "created": "2026-11-05T15:02:11+09:00", "choices": old_choices(keys)}
    js = (f"var C = {json.dumps(old_comps())}, K = {json.dumps(keys)}, old = {json.dumps(old)};\n"
          "var v = validateImport(old, C, K); console.log(JSON.stringify([v, exportChoices(v.choices, old.created)]));")
    v, again = node(js)
    assert v == {"choices": old["choices"], "rejected": []} and again == old


def test_old_saved_progress_reads_back_unchanged():
    """Jack's saved progress as the merged page writes it ({v: 1, savedAt, grid, choices, flags, fix}): every choice,
    mark and fix and the grid come back unchanged. Nothing in it says Start was tapped, so it does not resume by itself;
    what the new page writes back (the same keys plus fixUrl, started, paused) reads back unchanged too."""
    keys = {"bf": KEYS[0], "ld": KEYS[1]}
    old = {"v": 1, "savedAt": "2026-11-05T15:02:11+09:00", "grid": "KR-2", "choices": old_choices(keys),
           "flags": {"000660": 1, "MSFT": 1}, "fix": {"000660": "letter", "MSFT": "bf-ticker"}}
    grids = ["KR-1", "KR-2", "US-1"]
    js = (f"var C = {json.dumps(old_comps())}, K = {json.dumps(keys)}, G = {json.dumps(grids)}, old = {json.dumps(old)};\n"
          "var r = parseProgress(JSON.parse(JSON.stringify(old)), C, K, G);\n"
          # the new page writes the same keys plus fixUrl and started: read back unchanged too
          "var saved = {v: 1, savedAt: 'x', grid: r.grid, choices: r.choices, flags: r.flags, fix: r.fix, fixUrl: r.fixUrl, started: true, paused: false};\n"
          "console.log(JSON.stringify([r, parseProgress(JSON.parse(JSON.stringify(saved)), C, K, G)]));")
    r, r2 = node(js)
    for got in (r, r2):
        assert got["choices"] == old["choices"] and got["flags"] == old["flags"] and got["fix"] == old["fix"]
        assert got["grid"] == "KR-2" and got["fixUrl"] == {} and got["rejected"] == [] and got["error"] == ""
    assert (r["resume"], r2["resume"]) == (False, True)


@pytest.mark.parametrize("blob,resume", [
    ({"v": 1, "choices": {}, "flags": {}, "fix": {}}, False),                      # old format: says nothing about Start
    ({"v": 1, "choices": {}, "flags": {"MSFT": 1}, "fix": {}}, False),             # marks can be made before Start
    ({"v": 1, "choices": {"005380": {"source": "letter", "url": None, "reviewed": "2026-11-05"}}}, False),  # Load choices
    ({"v": 1, "choices": {"005380": {"source": "letter", "url": None, "reviewed": "2026-11-05"}}, "started": False}, False),
    ({"v": 1, "choices": {}, "started": True}, True),
    ({"v": 1, "choices": {}, "started": True, "paused": False}, True),
    ({"v": 1, "choices": {}, "started": True, "paused": True}, False),            # Pause was tapped last
    ({"v": 1, "started": "yes"}, False),
    ({"v": 1}, False),
])
def test_resume_only_after_start_was_tapped(blob, resume):
    r = node(f"console.log(JSON.stringify(parseProgress({json.dumps(blob)}, {json.dumps(old_comps())}, {{}}, ['KR-1'])));")
    assert r["resume"] is resume


def test_saved_fixes_keep_a_pasted_address_only_in_its_checked_form():
    blob = {"v": 1, "choices": {}, "grid": "nope",
            "flags": {"005930": 1, "000660": 1, "005380": 1, "MSFT": 1, "ZZZZ": 1},
            "fix": {"005930": "manual", "000660": "manual", "005380": "need", "MSFT": "made-up", "ZZZZ": "letter"},
            "fixUrl": {"005930": "https://www.samsung.com/logo.png", "000660": "http://x.co.kr/a.png"}}
    r = node(f"console.log(JSON.stringify(parseProgress({json.dumps(blob)}, {json.dumps(old_comps())}, {{}}, ['KR-1'])));")
    assert r["fix"] == {"005930": "manual", "005380": "need"} and r["fixUrl"] == {"005930": "https://www.samsung.com/logo.png"}
    assert r["flags"] == {"005930": 1, "000660": 1, "005380": 1, "MSFT": 1} and r["grid"] is None
    for bad in (None, [], "x", 3):
        out = subprocess.run(["node"], input=pure_js() + f"\ntry {{ parseProgress({json.dumps(bad)}, {{}}, {{}}, []); "
                             "console.log('no'); } catch (e) { console.log('threw'); }", capture_output=True, text=True)
        assert out.stdout.strip() == "threw", bad


# ── what was found, remembered for 7 days (PROBE_KEY): source name, hit or miss, day; never an image ──

def test_probe_memory_reads_fresh_entries_for_this_build_only():
    comps = old_comps()
    o = {"v": 1, "page": "B1", "savedAt": "x", "probes": {
        "005930": {"bf-isin": ["hit", "2026-11-05"], "ld-domain": ["miss", "2026-10-30"],      # 6 days old: kept
                   "bf-ticker": ["miss", "2026-10-29"],                                       # 7 days old: expired
                   "ld-ticker": ["miss", "2026-11-06"]},                                      # in the future: dropped
        "000660": {"ld-domain": ["miss", "2026-11-05"],                                       # no domain now: dropped
                   "bf-isin": ["maybe", "2026-11-05"], "bf-ticker": ["hit"], "ld-ticker": "hit",
                   "own-icon": ["hit", "2026-11-05"], "bf-name": ["hit", "2026-11-05"]},
        "AAPL": {"ld-ticker": ["hit", "2026-11-05"]},
        "999990": {"bf-isin": ["hit", "2026-11-05"]}, "MSFT": "hit"}}
    js = (f"var C = {json.dumps(comps)}, o = {json.dumps(o)};\n"
          "console.log(JSON.stringify([readProbes(o, 'B1', '2026-11-05', C), readProbes(o, 'B2', '2026-11-05', C),"
          " readProbes(Object.assign({}, o, {v: 2}), 'B1', '2026-11-05', C), readProbes(null, 'B1', '2026-11-05', C),"
          " packProbes(o.probes, 'B1', '2026-11-05', 'S')]));")
    same, other, v2, none, packed = node(js)
    assert same["probes"] == {"005930": {"bf-isin": ["hit", "2026-11-05"], "ld-domain": ["miss", "2026-10-30"]},
                              "AAPL": {"ld-ticker": ["hit", "2026-11-05"]}}
    assert same["n"] == 3 and same["dropped"] == 10 and not same["other"]
    assert other == {"probes": {}, "n": 0, "dropped": 0, "other": True} and v2["probes"] == {} and none["probes"] == {}
    assert packed["v"] == 1 and packed["page"] == "B1" and "2026-10-29" not in json.dumps(packed)
    assert "http" not in json.dumps(same) and "data:" not in json.dumps(same)


def test_probe_memory_expires_after_7_days():
    got = node("console.log(JSON.stringify(['2026-11-05','2026-11-04','2026-10-30','2026-10-29','2026-11-06','x', null]"
               ".map(d => probeFresh(d, '2026-11-05'))));")
    assert got == [True, True, True, False, False, False, False]


def test_summary_counts_needs_a_logo_apart():
    comps = [{"c": f"K{i}", "s": "kr", "z": 0} for i in range(4)]
    zones = [{"side": "kr", "z": 0, "label": "Korea 1-4"}]
    ch = {"K0": {"source": "manual"}, "K1": {"source": "need"}, "K2": {"source": "letter"}}
    rows = node(f"console.log(JSON.stringify(summarize({json.dumps(comps)}, {json.dumps(ch)}, {json.dumps(zones)})));")
    assert [(r["label"], r["n"], r["reviewed"], r["logo"], r["letter"], r["need"]) for r in rows] == [
        ("Korea 1-4", 4, 3, 1, 1, 1), ("Korea all", 4, 3, 1, 1, 1), ("US all", 0, 0, 0, 0, 0), ("All", 4, 3, 1, 1, 1)]


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


def test_only_this_pages_own_storage_keys_each_access_in_try():
    """Two keys of its own since 2026-11-05: the choices (STORE_KEY, unchanged) and what was found (PROBE_KEY, kept
    apart so that a full or broken entry there can never cost a confirmed choice). Every access is inside a try."""
    js = TEMPLATE.split("<script>", 1)[1]
    assert "sessionStorage" not in js and "indexedDB" not in js and "document.cookie" not in js
    assert "caches." not in js and "serviceWorker" not in js
    uses = re.findall(r"localStorage\.(\w+)\(([^,)]*)", js)
    assert uses == [("getItem", "STORE_KEY"), ("setItem", "STORE_KEY"), ("getItem", "PROBE_KEY"),
                    ("setItem", "PROBE_KEY")], uses
    for m in re.finditer(r"localStorage\.", js):
        before = js[:m.start()]
        assert before.rfind("try {") > before.rfind("\n}"), js[m.start() - 120:m.start() + 40]
    got = node("console.log(JSON.stringify([STORE_KEY, PROBE_KEY, PROBE_DAYS]));")
    assert got == ["baepsae-logo-review-v1", "baepsae-logo-review-probes-v1", 7]


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
    assert m2["000020"] == {"path": "icons/123450.png", "check": True}       # another company's picture: check
    assert any("000020" in line and "123450" in line and "another company" in line for line in log2)
    assert m2["123450"] == "icons/123450.png" and n2["kept from an earlier run although shared"] == 1   # append only
    assert any("123450: still 'kept'" in line and "earlier run" in line for line in log2)
    assert m2["000040"] == "icons/000040.png"
    assert all((out / k).read_bytes() == v for k, v in before.items())
    assert n2["already in the manifest (left as is)"] == 5 and n2["files written"] == 1


def test_add_site_icons_the_same_picture_for_two_companies_is_check_for_both(tmp_path):
    """A group logo or a web host's default icon: every company with it is 'check' when they arrive in the same run
    (the first one too); its preferred share follows; a third company joining later is 'check' as well."""
    import add_site_icons as ai
    host = png_bytes((120, 120, 120, 255), shape="disc")
    src = collection(tmp_path, {"003090": host, "003095": host, "069620": host, "000100": png_bytes((5, 5, 5, 255))}, {})
    out, man = tmp_path / "icons", tmp_path / "icons.json"
    n, log = ai.add_icons(src, out, man)
    m = json.loads(man.read_text())
    assert m["003090"] == m["003095"] == m["069620"] == {"path": "icons/003090.png", "check": True}
    assert m["000100"] == "icons/000100.png" and (n["kept"], n["check"]) == (1, 3)
    assert sorted(p.name for p in out.glob("*.png")) == ["000100.png", "003090.png"]
    (src / "kr" / "111110.png").write_bytes(host)
    (src / "site_icons.csv").write_text((src / "site_icons.csv").read_text() + "111110,kept\n", encoding="utf-8")
    n2, log2 = ai.add_icons(src, out, man)
    assert json.loads(man.read_text())["111110"] == {"path": "icons/003090.png", "check": True}
    assert n2["kept from an earlier run although shared"] == 0                 # the earlier ones were 'check' already


def test_add_site_icons_codes_are_matched_in_capitals(tmp_path):
    import add_site_icons as ai
    src = collection(tmp_path, {"0126z0": png_bytes((0, 90, 200, 255))}, {}, decisions={"0126z0": "kept"})
    n, log = ai.add_icons(src, tmp_path / "icons", tmp_path / "icons.json")
    assert json.loads((tmp_path / "icons.json").read_text()) == {"0126Z0": "icons/0126Z0.png"} and n["refused"] == 0
    assert not list(tmp_path.glob("*.tmp"))                                   # the manifest was swapped in whole


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
