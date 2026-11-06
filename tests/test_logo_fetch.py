# -*- coding: utf-8 -*-
"""v19.3a logos: the logo.dev fetch job (tools/logos/logodev_fetch.py), its hand-run workflow
(.github/workflows/logo-dev-fetch.yml) and the logo folder rules (tools/logos/logo_index.py).

No network and no real key: the HTTP client is faked (lookups and downloads), the clocks are fake, the key is made up.
Covers: exact identifiers (Korea .KS / .KQ, US bare; the DART homepage domain only for Korea, only domain_ok = 1),
market-cap order, the credit cap (also with several workers at once), the 402 stop, Credits-Charged counting, 202
retries, the brand_id cross-check (same brand · another brand · unverified), preferred shares reusing their issuer's
logo with no lookup, the automatic quality checks (small · blank · faint · one colour · shared drops and the monogram-looking flag,
each limit on both sides), odd answers kept to their company (a vector 0 x 0 is fine; above 30 the run stops), 128 px WebP files that are never upscaled, a valid index.json with names, the key and signed addresses
never in any output, --drop and --keep after review (dropped pictures wait in dropped/), the spend guards across runs
(the 14,000 cap, the 1,000 floor with lookups in flight, the first balance, a billed answer without a balance, today's
date for a full run, a trial's own cap), an error after the lookups that still saves everything, and the workflow's
shape (read-only, the secret in one step only, 7 days, one run at a time).
"""
import csv
import io
import json
import pathlib
import sys
import threading

import pytest
import yaml

from test_workflows import assert_no_hidden_failure

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))

import logo_index as LI  # noqa: E402
import logodev_api_check as chk  # noqa: E402
import logodev_fetch as F  # noqa: E402

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

FAKE_KEY = "sk_TestOnly0123456789abcdefXYZ"
KEYLESS_HOSTS = ("img.logo.dev",)


# ── pictures ──

def png(im):
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def good_logo(size=256):
    im = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    s = size / 256
    d.ellipse((20 * s, 20 * s, 130 * s, 130 * s), fill=(200, 30, 40, 255))
    d.rectangle((120 * s, 110 * s, 230 * s, 220 * s), fill=(20, 140, 60, 255))
    d.polygon([(30 * s, 230 * s), (110 * s, 150 * s), (120 * s, 236 * s)], fill=(30, 60, 200, 255))
    return im


def monogram():
    im = Image.new("RGBA", (128, 128), (51, 102, 204, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((40, 34, 88, 44), fill=(255, 255, 255, 255))
    d.rectangle((59, 34, 69, 94), fill=(255, 255, 255, 255))
    return im


_DISTINCT = {}


def distinct(token):
    """A different ordinary logo for every token (so no two companies share a picture by accident)."""
    if token not in _DISTINCT:
        import hashlib
        h = hashlib.sha256(token.encode()).digest()
        im = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
        d = ImageDraw.Draw(im)
        for k in range(2 + h[0] % 3):
            x, y, w = h[1 + k * 3] % 150, h[2 + k * 3] % 150, 50 + h[3 + k * 3] % 80
            (d.ellipse if k % 2 else d.rectangle)((x, y, x + w, y + w), fill=(h[10 + k], h[13 + k], h[16 + k], 255))
        _DISTINCT[token] = png(im)
    return _DISTINCT[token]


PICS = {
    "good": png(good_logo()),
    "good100": png(good_logo(100)),
    "blank": png(Image.new("RGBA", (128, 128), (0, 0, 0, 0))),
    "flat": png(Image.new("RGBA", (128, 128), (40, 90, 180, 255))),
    "mono": png(monogram()),
    "white_on_clear": None,
}
_w = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
ImageDraw.Draw(_w).rectangle((20, 50, 108, 78), fill=(255, 255, 255, 255))
PICS["white_on_clear"] = png(_w)


# ── fakes ──

class Clock:
    def __init__(self):
        self.t = 1000.0
        self.lock = threading.Lock()

    def __call__(self):
        return self.t

    def sleep(self, s):
        with self.lock:
            self.t += s


def body(obj):
    return json.dumps(obj).encode("utf-8")


def logo_answer(token, brand, w=512, h=512, vector=False, cc="1", etag=None, remaining="15000"):
    return chk.Resp(200, {"Credits-Charged": cc, "Credits-Remaining": remaining}, body(
        {"data": {"object": "image", "kind": "logo", "brand_id": brand, "status": "ready",
                  "url": f"https://img.logo.dev/assets/{token}?sig=SIGNED", "etag": etag or f"etag-{token}",
                  "blurhash": "x", "source": {"width": w, "height": h, "format": "svg" if vector else "png",
                                              "has_transparency": True, "is_vector": vector},
                  "last_updated_at": None, "expires_at": "2026-11-07T12:00:00Z"},
         "metadata": {"request_id": "r", "resolution": {"type": "ticker", "value": "X", "method": "security",
                                                        "context": {}}}}))


def not_found(cc="0"):
    return chk.Resp(404, {"Credits-Charged": cc}, body({"data": {"object": "image", "status": "not_found"},
                                                       "metadata": {"request_id": "r"}}))


def indexing():
    return chk.Resp(202, {"Retry-After": "30", "Credits-Charged": "0"}, body(
        {"data": {"object": "image", "status": "not_indexed"},
         "metadata": {"request_id": "r", "pending": {"reason": "indexing", "retry_after_seconds": 30}}}))


def out_of_credits():
    return chk.Resp(402, {}, body({"error": {"code": "insufficient_credits", "message": "out of credits"}}))


class Net:
    """answers: {(route, ident): [Resp, ...]} (the last one repeats); pics: {token: bytes}."""

    def __init__(self, answers, pics=None):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.pics = pics or {}
        self.lookups, self.downloads, self.headers = [], [], []
        self.lock = threading.Lock()
        self.open = self.most_open = 0

    def __call__(self, url, params=None, headers=None, timeout=None, max_bytes=None, follow=False):
        with self.lock:
            self.open += 1
            self.most_open = max(self.most_open, self.open)
        try:
            if url == chk.API_BASE + chk.LOGO_ROUTE:
                (route, ident), = params.items()
                assert follow is False                                     # a lookup never follows a redirect
                self.lookups.append((route, ident))
                self.headers.append(("api", dict(headers)))
                q = self.answers.get((route, ident)) or [not_found()]
                return q.pop(0) if len(q) > 1 else q[0]
            assert url.startswith("https://img.logo.dev/assets/") and follow is True, url
            self.headers.append(("img", dict(headers)))
            token = url.split("/assets/", 1)[1].split("?", 1)[0]
            q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
            self.downloads.append((token, q))
            pic = self.pics.get(token) or distinct(token)
            return chk.Resp(200, {"Content-Type": "image/png"}, pic)
        finally:
            with self.lock:
                self.open -= 1


def stock(t, cls, cap, nk=None, **kw):
    return {"t": t, "cls": cls, "cap": cap, "nk": nk or t, "ne": nk or t, **kw}


BASE_STOCKS = [
    stock("005930", "kr", 900.0, "삼성전자"), stock("000660", "kr", 500.0, "SK하이닉스"),
    stock("005380", "kr", 60.0, "현대차"), stock("247540", "kr", 20.0, "에코프로비엠"),
    stock("005935", "kr", 100.0, "삼성전자우"), stock("069500", "kr", 10.0, "KODEX 200", etf=True, fund=True),
    stock("AAPL", "us", 6000.0, "Apple"), stock("MSFT", "us", 5000.0, "Microsoft"),
    stock("BRK-B", "us", 1000.0, "Berkshire Hathaway"), stock("SPY", "us", 800.0, "SPDR", etf=True),
]
LISTING = [("005930", "KOSPI", "KR7005930003"), ("000660", "KOSPI", "KR7000660001"), ("005380", "KOSPI", "KR7005380001"),
           ("247540", "KOSDAQ", "KR7247540008"), ("005935", "KOSPI", "KR7005931001")]
HOMES = [("005930", "", "samsung.com", "1"), ("000660", "", "skhynix.com", "1"), ("005380", "", "hyundai.com", "1"),
         ("247540", "", "", "0"), ("005935", "005930", "samsung.com", "1")]


def write_inputs(tmp, stocks=None):
    data = {"asOf": "2026-11-06", "pxDate": "2026-11-05", "usPxDate": "2026-11-05", "stocks": stocks or BASE_STOCKS}
    (tmp / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with open(tmp / "listing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Code", "Market", "ISU_CD"])
        w.writerows(LISTING)
    with open(tmp / "homes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "corp_code", "via", "name_en", "corp_cls", "hm_url", "domain", "domain_ok", "domain_note",
                    "fetched_at", "status"])
        for code, via, dom, ok in HOMES:
            w.writerow([code, "1", via, "", "Y", dom, dom, ok, "" if ok == "1" else "no homepage", "", "ok"])
    return tmp


NOW = chk.now_kst()
TODAY = f"{NOW:%Y-%m-%d}"


def run(tmp, net, *extra, workers="1", env=None, webp=True, clock=None, full_run_date=TODAY, out_name="out", wall=None):
    clock = clock or Clock()
    environ = {F.KEY_ENV: FAKE_KEY} if env is None else env
    deps = F.Deps(send=net, clock=clock, sleep=clock.sleep, wall=wall or (lambda: NOW), environ=environ,
                  jitter=lambda: 0.0, min_counts={"kr": 1, "us": 1}, render=lambda *a: ([], None), webp=webp)
    out = tmp / out_name
    date = ["--full-run-date", full_run_date] if full_run_date is not None else []
    rc = F.main(["--data", str(tmp / "data.json"), "--listing", str(tmp / "listing.csv"), "--homepages",
                 str(tmp / "homes.csv"), "--out", str(out), "--workers", workers, "--no-png", *date, *extra], deps)
    return rc, out


def review(out):
    with open(out / "review.csv", newline="", encoding="utf-8") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def index(out):
    return json.loads((out / "logos" / "index.json").read_text(encoding="utf-8"))


ALL_GOOD = {
    ("ticker", "005930.KS"): [logo_answer("sam", "brand_sam")], ("domain", "samsung.com"): [logo_answer("sam", "brand_sam", cc="0")],
    ("ticker", "000660.KS"): [logo_answer("hyn", "brand_hyn")], ("domain", "skhynix.com"): [logo_answer("hyn2", "brand_hyn", cc="0")],
    ("ticker", "005380.KS"): [logo_answer("hmc", "brand_hmc")], ("domain", "hyundai.com"): [logo_answer("hmc", "brand_hmc", cc="0")],
    ("ticker", "247540.KQ"): [logo_answer("eco", "brand_eco")],
    ("ticker", "AAPL"): [logo_answer("aapl", "brand_aapl", vector=True)], ("ticker", "MSFT"): [logo_answer("msft", "brand_msft")],
    ("ticker", "BRK-B"): [logo_answer("brk", "brand_brk", w=100, h=100)],
}


# ── identifiers, order, files ──

def test_exact_identifiers_market_cap_order_and_no_lookup_for_preferred_or_etf(tmp_path):
    write_inputs(tmp_path)
    net = Net(ALL_GOOD, {"brk": PICS["good100"]})
    rc, out = run(tmp_path, net)
    assert rc == 0
    tickers = [i for r, i in net.lookups if r == "ticker"]
    assert tickers == ["AAPL", "MSFT", "BRK-B", "005930.KS", "000660.KS", "005380.KS", "247540.KQ"]   # 조원, largest first
    domains = [i for r, i in net.lookups if r == "domain"]
    assert domains == ["samsung.com", "skhynix.com", "hyundai.com"]           # Korea only, domain_ok = 1 only
    assert not any("005935" in i or "069500" in i or i == "SPY" for _, i in net.lookups)
    assert all(r in ("ticker", "domain") for r, _ in net.lookups)              # never a name search
    idx = index(out)
    assert LI.validate_dir(out / "logos")[1] == []
    assert sorted(idx["logos"]) == sorted(["005930", "005935", "000660", "005380", "247540", "AAPL", "MSFT", "BRK-B"])
    assert idx["logos"]["005935"] == dict(idx["logos"]["005930"], name="삼성전자우", via="005930")    # preferred: the issuer's file
    assert not (out / "logos" / "005935.webp").exists()
    for name in ("005930.webp", "AAPL.webp", "BRK-B.webp"):
        im = Image.open(out / "logos" / name)
        assert im.format == "WEBP" and im.size == (128, 128) and im.mode == "RGBA"
    # never upscaled: a 100 px raster is asked for at 100 and sits centred at 100 px inside the 128 square
    q = dict(net.downloads)
    assert q["brk"]["size"] == "100" and q["sam"]["size"] == "128" and q["aapl"]["size"] == "128"
    assert all(v["format"] == "png" for v in q.values())
    a = Image.open(out / "logos" / "BRK-B.webp").getchannel("A")
    assert a.getbbox() is not None and a.getbbox()[2] - a.getbbox()[0] <= 101
    rv = review(out)
    assert rv["005930"]["check"] == "same-brand" and rv["005930"]["brand_domain"] == "samsung.com"
    assert rv["247540"]["check"] == "unverified" and "no usable DART homepage domain" in rv["247540"]["unverified_why"]
    assert rv["AAPL"]["check"] == "ticker" and rv["AAPL"]["vector"] == "True"
    assert rv["005935"]["via"] == "005930" and rv["005935"]["result"] == "logo" and rv["005935"]["requests"] == "0"


def test_png_files_when_this_pillow_has_no_webp(tmp_path):
    write_inputs(tmp_path)
    rc, out = run(tmp_path, Net(ALL_GOOD), webp=False)
    assert rc == 0 and index(out)["format"] == "png" and index(out)["logos"]["005930"]["file"] == "005930.png"
    assert LI.validate_dir(out / "logos")[1] == []


# ── the cross-check ──

def test_brand_id_cross_check_against_the_dart_homepage(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("domain", "skhynix.com")] = [logo_answer("hynhome", "brand_other")]          # another brand: homepage wins
    answers[("domain", "hyundai.com")] = [not_found()]                                    # homepage found nothing
    answers[("ticker", "005930.KS")] = [not_found()]                                      # no ticker logo
    rc, out = run(tmp_path, Net(answers))
    rv = review(out)
    assert rc == 0
    assert (rv["000660"]["route"], rv["000660"]["check"]) == ("domain", "homepage-over-ticker")
    assert rv["000660"]["ticker_brand"] == "brand_hyn" and rv["000660"]["domain_brand"] == "brand_other"
    assert (rv["005380"]["route"], rv["005380"]["check"]) == ("ticker", "unverified")     # kept, flagged
    assert rv["005380"]["unverified_why"] == "homepage hyundai.com: not_found"
    assert (rv["005930"]["route"], rv["005930"]["check"]) == ("domain", "homepage")
    s = (out / "summary.md").read_text(encoding="utf-8")
    assert "another brand with a logo (homepage logo used instead): **1**" in s and "unverified: **2**" in s


def test_no_logo_anywhere_is_a_letter_mark_with_its_reason(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "005380.KS")] = [not_found(cc="1")]                                # brand, no logo (billed)
    answers[("domain", "hyundai.com")] = [not_found()]
    answers[("ticker", "MSFT")] = [not_found()]
    rc, out = run(tmp_path, Net(answers))
    rv = review(out)
    assert (rv["005380"]["result"], rv["005380"]["reason"]) == ("letter", "no_image")
    assert (rv["MSFT"]["result"], rv["MSFT"]["reason"]) == ("letter", "not_found")
    assert "005380" not in index(out)["logos"] and "MSFT" not in index(out)["logos"]


# ── quality checks ──

def test_quality_checks_drop_doubtful_pictures(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [logo_answer("tiny", "brand_msft", w=48, h=48)]
    answers[("ticker", "BRK-B")] = [logo_answer("blank", "brand_brk")]
    answers[("ticker", "247540.KQ")] = [logo_answer("flat", "brand_eco")]
    answers[("ticker", "005380.KS")] = [logo_answer("mono", "brand_hmc")]
    answers[("domain", "hyundai.com")] = [logo_answer("mono", "brand_hmc", cc="0")]
    answers[("ticker", "000660.KS")] = [logo_answer("wclear", "brand_hyn")]
    pics = {"blank": PICS["blank"], "flat": PICS["flat"], "mono": PICS["mono"], "wclear": PICS["white_on_clear"]}
    rc, out = run(tmp_path, Net(answers, pics), "--sheet-top", "1")
    rv = review(out)
    assert (rv["MSFT"]["result"], rv["MSFT"]["reason"]) == ("letter", "small")
    assert (rv["BRK-B"]["result"], rv["BRK-B"]["reason"]) == ("letter", "blank")
    assert (rv["247540"]["result"], rv["247540"]["reason"]) == ("letter", "one_colour")
    assert (rv["005380"]["result"], rv["005380"]["flags"]) == ("logo", "monogram-looking")    # kept, flagged
    assert (rv["000660"]["result"], rv["000660"]["reason"]) == ("letter", "faint")   # white on transparency: invisible on white
    assert rv["AAPL"]["result"] == "logo"
    s = (out / "summary.md").read_text(encoding="utf-8")
    for k in ("small", "blank", "faint", "one_colour"):
        assert f"- {k}: **1**" in s, k
    assert "- monogram-looking, kept and flagged (never dropped): **1**" in s
    assert "monogram-looking" in index(out)["logos"]["005380"]["flags"]
    assert "Monogram-looking (kept)" in (out / "sheet.html").read_text(encoding="utf-8")
    assert "difference hash" in s and "thumbnails" in s and "monogram" in s                          # the methods are described


BIG = {"width": 512, "height": 512, "is_vector": False}


def flat(bg, blocks=()):
    a = F._np().zeros((128, 128, 4), F._np().uint8)
    a[:] = bg
    for y0, y1, x0, x1, col in blocks:
        a[y0:y1, x0:x1] = col
    return Image.fromarray(a, "RGBA")


def bar(w, h, dx=0):
    x0, y0 = 64 - w // 2 + dx, 64 - h // 2
    return flat((51, 102, 204, 255), [(y0, y0 + h, x0, x0 + w, (255, 255, 255, 255))])


BLACK, WHITE = (0, 0, 0, 255), (255, 255, 255, 255)


def test_every_quality_threshold_on_both_sides():
    q = F.quality
    # small: the shorter side of a raster source; 64 kept, 63 dropped; a vector source is never small
    assert "small" not in q(flat(WHITE, [(0, 64, 0, 64, BLACK)]), {"width": 64, "height": 64})
    assert "small" in q(flat(WHITE, [(0, 64, 0, 64, BLACK)]), {"width": 63, "height": 200})
    assert "small" not in q(flat(WHITE, [(0, 64, 0, 64, BLACK)]), {"width": 16, "height": 16, "is_vector": True})
    # blank: under 1% of 16,384 pixels visible (163 px blank, 165 px not)
    assert q(flat((0, 0, 0, 0), [(0, 1, 0, 128, BLACK), (1, 2, 0, 35, BLACK)]), BIG) == ["blank"]
    assert "blank" not in q(flat((0, 0, 0, 0), [(0, 1, 0, 128, BLACK), (1, 2, 0, 37, BLACK)]), BIG)
    # faint on white: under 1.5% of pixels more than 40 levels from white (225 px faint, 256 px kept)
    assert q(flat(WHITE, [(10, 25, 10, 25, BLACK)]), BIG) == ["faint"]
    assert q(flat(WHITE, [(10, 26, 10, 26, BLACK)]), BIG) == []
    assert q(flat((0, 0, 0, 0), [(0, 64, 0, 128, (215, 215, 215, 255))]), BIG) == ["faint"]     # 40 away: not visible
    assert q(flat((0, 0, 0, 0), [(0, 64, 0, 128, (214, 214, 214, 255))]), BIG) == []            # 41 away: visible
    assert q(flat((0, 0, 0, 0), [(50, 78, 20, 108, WHITE)]), BIG) == ["faint"]                   # white on transparency
    # one colour: at least 98.5% one colour on white and on black (225 px of white on blue: one colour; 272 px: not)
    assert q(flat((30, 60, 200, 255), [(10, 25, 10, 25, WHITE)]), BIG) == ["one_colour"]
    assert q(flat((30, 60, 200, 255), [(10, 27, 10, 26, WHITE)]), BIG) == []
    # monogram: the far colour 4-40% (16 x 43 = 4.2% in, 14 x 43 = 3.7% out), centred within 12% (14 px in, 17 out),
    # 25-75% tall (33 px in, 31 out)
    mono = lambda im: F.is_monogram(F._np().asarray(im))                                        # noqa: E731
    assert mono(bar(16, 43)) and not mono(bar(14, 43))
    assert mono(bar(16, 43, dx=14)) and not mono(bar(16, 43, dx=17))
    assert mono(bar(22, 33)) and not mono(bar(22, 31))
    assert q(bar(16, 43), BIG) == [] and q(bar(14, 43), BIG) == []                            # never a drop reason


def test_max_credits_can_never_go_above_14000(tmp_path):
    write_inputs(tmp_path)
    with pytest.raises(SystemExit):
        run(tmp_path, Net(ALL_GOOD), "--max-credits", "14002")
    rc, out = run(tmp_path, Net(ALL_GOOD), "--max-credits", "14000")
    assert rc == 0


def test_stops_before_logo_dev_balance_goes_below_1000(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [logo_answer("msft", "brand_msft", remaining="1001.5")]     # first one was 15000
    net = Net(answers)
    rc, out = run(tmp_path, net)
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["outcome"] == "balance_floor" and info["ok"] is True
    assert net.lookups == [("ticker", "AAPL"), ("ticker", "MSFT")]             # 1001.5 - 2 < 1000 for the next one
    assert "below 1,000" in (out / "run.log").read_text(encoding="utf-8")
    assert sorted(index(out)["logos"]) == ["AAPL", "MSFT"]


def test_a_picture_shared_by_different_brands_becomes_letter_marks(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [logo_answer("same", "brand_msft")]
    answers[("ticker", "BRK-B")] = [logo_answer("same", "brand_brk")]                         # same picture, other brand
    answers[("ticker", "005930.KS")] = [logo_answer("same", "brand_sam")]                     # ... and 삼성전자, whose own
    answers[("domain", "samsung.com")] = [logo_answer("same", "brand_sam", cc="0")]           # homepage confirms it
    answers[("ticker", "005380.KS")] = [logo_answer("grp", "brand_grp")]
    answers[("domain", "hyundai.com")] = [logo_answer("grp", "brand_grp", cc="0")]
    answers[("ticker", "247540.KQ")] = [logo_answer("grp", "brand_grp")]                       # same picture, same brand
    rc, out = run(tmp_path, Net(answers))
    rv, idx = review(out), index(out)
    for code in ("MSFT", "BRK-B"):
        assert (rv[code]["result"], rv[code]["reason"]) == ("letter", "shared") and code not in idx["logos"], code
        assert not (out / "logos" / f"{code}.webp").exists() and (out / "dropped" / f"{code}.webp").exists()
    assert rv["005930"]["result"] == "logo" and rv["005930"]["check"] == "same-brand"         # kept: an exact identifier
    assert "005930" in idx["logos"] and "005935" in idx["logos"]
    assert rv["005380"]["result"] == rv["247540"]["result"] == "logo" and rv["005380"]["shared_group"]
    assert LI.validate_dir(out / "logos")[1] == [] and LI.validate_dir(out / "dropped")[1] == []
    dropped = json.loads((out / "dropped" / "index.json").read_text(encoding="utf-8"))
    assert sorted(dropped["logos"]) == ["BRK-B", "MSFT"] and dropped["logos"]["MSFT"]["flags"][0] == "shared"
    s = (out / "summary.md").read_text(encoding="utf-8")
    assert "- shared: **2**" in s and "**2** companies of different or unknown brands switched" in s
    assert "**1** kept because their own homepage confirmed them" in s
    log = (out / "run.log").read_text(encoding="utf-8")
    assert "!! shared picture" in log and "kept for 005930 (confirmed by their own homepage)" in log
    sheet = (out / "sheet.html").read_text(encoding="utf-8")
    assert "ticker: shared" in sheet and "2 switched to letter marks (different brands), 1 kept (same-brand)" in sheet
    assert "kept (one brand)" in sheet


def test_a_missing_brand_id_counts_as_unknown(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    no_id = logo_answer("dup", "")                                                             # no real brand_id
    answers[("ticker", "MSFT")] = [no_id]
    answers[("ticker", "BRK-B")] = [no_id]
    rc, out = run(tmp_path, Net(answers))
    rv = review(out)
    assert rv["MSFT"]["reason"] == rv["BRK-B"]["reason"] == "shared"                          # never "one brand"
    data = json.loads(logo_answer("x", "").body)["data"]
    assert data.get("brand_id") == "" and "id" not in data


def test_keep_restores_a_dropped_picture_after_review_and_refuses_others(tmp_path, capsys):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [logo_answer("same", "brand_msft")]
    answers[("ticker", "BRK-B")] = [logo_answer("same", "brand_brk")]
    answers[("ticker", "AAPL")] = [logo_answer("faint", "brand_aapl")]
    rc, out = run(tmp_path, Net(answers, {"faint": PICS["white_on_clear"]}))
    assert review(out)["AAPL"]["reason"] == "faint" and (out / "dropped" / "AAPL.webp").exists()
    assert F.main(["--keep", "MSFT,AAPL", "--dir", str(out), "--reason", "checked on the sheet"]) == 0
    idx = index(out)
    assert idx["logos"]["MSFT"]["flags"][-1] == "kept-after-review" and "AAPL" in idx["logos"]
    assert (out / "logos" / "MSFT.webp").exists() and not (out / "dropped" / "MSFT.webp").exists()
    assert LI.validate_dir(out / "logos")[1] == [] and LI.validate_dir(out / "dropped")[1] == []
    assert "restored from dropped/ after review" in capsys.readouterr().out
    assert "MSFT" in (out / "keeps.csv").read_text(encoding="utf-8")
    assert "Restored after review: MSFT, AAPL" in (out / "summary.md").read_text(encoding="utf-8")
    for bad in ("005930", "NOPE", "MSFT"):                                                      # not in dropped/ (any more)
        with pytest.raises(SystemExit):
            F.main(["--keep", bad, "--dir", str(out)])
    # --drop moves a picture to dropped/ (with its preferred share), and --keep brings both back
    assert F.main(["--drop", "005930", "--dir", str(out)]) == 0
    assert "005930" not in index(out)["logos"] and (out / "dropped" / "005930.webp").exists()
    assert F.main(["--keep", "005930", "--dir", str(out)]) == 0
    assert index(out)["logos"]["005935"]["via"] == "005930" and index(out)["logos"]["005935"]["name"] == "삼성전자우"


def snapshot(out):
    return {str(p.relative_to(out)): p.read_bytes() for p in sorted((out / "logos").iterdir()) + sorted(
        (out / "dropped").iterdir() if (out / "dropped").exists() else [])}


def test_drop_refuses_a_preferred_share_and_dropped_stays_valid(tmp_path):
    write_inputs(tmp_path)
    rc, out = run(tmp_path, Net(ALL_GOOD))
    before = snapshot(out)
    with pytest.raises(SystemExit) as e:
        F.main(["--drop", "005935", "--dir", str(out)])
    assert "우선주는 보통주(005930)를 빼면 같이 빠져요" in str(e.value) and snapshot(out) == before
    assert F.main(["--drop", "005930", "--dir", str(out)]) == 0                                 # the issuer: both go
    idx = index(out)
    assert "005930" not in idx["logos"] and "005935" not in idx["logos"]
    assert LI.validate_dir(out / "logos")[1] == [] and LI.validate_dir(out / "dropped")[1] == []
    assert F.main(["--drop", "AAPL", "--dir", str(out)]) == 0                                    # later switches still work
    assert F.main(["--keep", "005930,AAPL", "--dir", str(out)]) == 0
    assert LI.validate_dir(out / "logos")[1] == [] and LI.validate_dir(out / "dropped")[1] == []


def test_a_code_given_twice_counts_once(tmp_path):
    write_inputs(tmp_path)
    rc, out = run(tmp_path, Net(ALL_GOOD))
    assert F.main(["--drop", "AAPL,AAPL, AAPL", "--dir", str(out)]) == 0
    assert F.main(["--keep", "AAPL,AAPL", "--dir", str(out)]) == 0
    assert "AAPL" in index(out)["logos"] and (out / "logos" / "AAPL.webp").exists()
    assert LI.validate_dir(out / "logos")[1] == [] and LI.validate_dir(out / "dropped")[1] == []
    assert (out / "keeps.csv").read_text(encoding="utf-8").count("AAPL") == 1


@pytest.mark.parametrize("what", ["drop", "keep"])
def test_a_failure_midway_changes_nothing(tmp_path, monkeypatch, what):
    write_inputs(tmp_path)
    rc, out = run(tmp_path, Net(ALL_GOOD))
    if what == "keep":
        assert F.main(["--drop", "AAPL,MSFT", "--dir", str(out)]) == 0
    before = snapshot(out)
    real, calls = F.write_index, []

    def flaky(folder, index_):
        calls.append(folder.name)
        if len(calls) == 2:                                    # logos/index.json written, then the second one fails
            raise OSError("disk full (test)")
        return real(folder, index_)
    monkeypatch.setattr(F, "write_index", flaky)
    rc = F.main([f"--{what}", "AAPL,MSFT", "--dir", str(out)])
    assert rc == 1 and len(calls) == 2
    assert snapshot(out) == before                                                              # files and both indexes


@pytest.mark.parametrize("bal", ["15,000", "$150.00", "15000 credits", "inf", "nan", "-5", "1e5", " "])
def test_an_unreadable_balance_stops_the_run_cleanly(tmp_path, bal):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "AAPL")] = [logo_answer("aapl", "brand_aapl", remaining=bal)]
    net = Net(answers)
    rc, out = run(tmp_path, net)
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    if not bal.strip():                                                                         # no balance at all
        assert info["outcome"] == "complete"
        return
    assert rc == 0 and info["outcome"] == "balance_unreadable" and info["ok"] is True, info["outcome"]
    assert net.lookups == [("ticker", "AAPL")] and sorted(index(out)["logos"]) == ["AAPL"]      # results saved
    assert "cannot read" in (out / "run.log").read_text(encoding="utf-8")


def test_a_balance_written_150_00_reads_as_150_and_stops(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "AAPL")] = [logo_answer("aapl", "brand_aapl", remaining="150.00")]
    net = Net(answers)
    rc, out = run(tmp_path, net)
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert info["outcome"] in ("balance_low", "balance_floor") and net.lookups == [("ticker", "AAPL")]


def test_same_brand_needs_a_real_brand_id_match(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "000660.KS")] = [logo_answer("hyn", "", etag="same-etag")]              # no brand_id, same etag
    answers[("domain", "skhynix.com")] = [logo_answer("hyn", "", etag="same-etag", cc="0")]
    answers[("ticker", "005380.KS")] = [logo_answer("hmc", "brand_a", etag="same2")]          # different brand_ids,
    answers[("domain", "hyundai.com")] = [logo_answer("hmc", "brand_b", etag="same2")]        # same etag
    rc, out = run(tmp_path, Net(answers))
    rv = review(out)
    assert (rv["000660"]["check"], rv["000660"]["unverified_why"]) == ("unverified", "brand id missing from an answer")
    assert rv["005380"]["check"] == "homepage-over-ticker"
    assert rv["005930"]["check"] == "same-brand"


def test_full_run_date_is_the_korean_date_even_at_1am(tmp_path):
    import datetime as dt
    write_inputs(tmp_path)
    utc_clock = lambda: dt.datetime(2026, 11, 6, 16, 0, tzinfo=dt.timezone.utc)                # noqa: E731 (01:00 KST)
    with pytest.raises(SystemExit) as e:
        run(tmp_path, Net(ALL_GOOD), full_run_date="2026-11-06", wall=utc_clock)
    assert "2026-11-07" in str(e.value)
    rc, out = run(tmp_path, Net(ALL_GOOD), full_run_date="2026-11-07", wall=utc_clock)
    assert rc == 0 and "2026-11-07 01:00 KST" in (out / "run.log").read_text(encoding="utf-8")


def test_a_crash_after_the_lookups_still_saves_and_uploads(tmp_path, monkeypatch):
    write_inputs(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("bug after the lookups " + FAKE_KEY)
    monkeypatch.setattr(F, "drop_shared", boom)
    net = Net(ALL_GOOD)
    rc, out = run(tmp_path, net, "--defer-failure")
    assert rc == 0                                                                             # so the artifact uploads
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert info["ok"] is False and info["outcome"] == "crashed" and "RuntimeError" in info["reason"]
    assert any("boom" in line or "RuntimeError" in line for line in info["traceback"])
    assert LI.validate_dir(out / "logos")[1] == [] and len(index(out)["logos"]) == 7          # every paid logo kept
    assert (out / "review.csv").exists() and "NOT OK" in (out / "summary.md").read_text(encoding="utf-8")
    for p in out.rglob("*"):
        if p.is_file():
            assert FAKE_KEY.encode() not in p.read_bytes(), p                                    # masked
    assert F.verdict(out / "run.json") == 1
    rc2, out2 = run(tmp_path, Net(ALL_GOOD), out_name="out2")
    assert rc2 == 1                                                                            # without --defer-failure


def test_full_runs_need_todays_date(tmp_path):
    write_inputs(tmp_path)
    net = Net(ALL_GOOD)
    for date in (None, "", "2020-01-01"):
        with pytest.raises(SystemExit) as e:
            run(tmp_path, net, full_run_date=date)
        assert "full_run_date" in str(e.value)
    with pytest.raises(SystemExit):
        run(tmp_path, net, "--limit", "51", full_run_date=None)
    assert net.lookups == []                                                                   # refused before any request
    rc, out = run(tmp_path, net, "--limit", "5", full_run_date=None)
    assert rc == 0
    rc, out = run(tmp_path, Net(ALL_GOOD), full_run_date=TODAY, out_name="out2")
    assert rc == 0


def test_a_limit_20_trial_is_a_clean_end_to_end_run(tmp_path, capsys):
    stocks = list(BASE_STOCKS) + [stock(f"T{i:03d}", "us", 100.0 - i * 0.1, f"Co{i}") for i in range(40)]
    write_inputs(tmp_path, stocks)
    answers = dict(ALL_GOOD)
    for i in range(40):
        answers[("ticker", f"T{i:03d}")] = [logo_answer(f"t{i}", f"b{i}")]
    net = Net(answers)
    rc, out = run(tmp_path, net, "--limit", "20", "--defer-failure", full_run_date=None)
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["ok"] is True and info["outcome"] == "complete" and info["companies"] == 20
    assert info["max_credits"] == info["plan"]["ceiling"] <= 80 and info["credits"]["counted"] <= 80
    for f in ("summary.md", "review.csv", "sheet.html", "run.json", "run.log", "logos/index.json", "dropped/index.json"):
        assert (out / f).exists(), f
    assert "credits left (Credits-Remaining, first answer)" in (out / "run.log").read_text(encoding="utf-8")
    assert LI.validate_dir(out / "logos")[1] == []


def test_first_balance_is_logged_and_a_low_one_stops_the_run(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "AAPL")] = [logo_answer("aapl", "brand_aapl", remaining="5000")]       # worst case 20 + 1,000 fits
    rc, out = run(tmp_path, Net(answers))
    log = (out / "run.log").read_text(encoding="utf-8")
    assert "!! logo.dev reports 5,000 credits left" in log and "worst case 20 + floor 1,000 = 1,020 needed" in log
    assert log.count("credits left (Credits-Remaining, first answer)") == 1
    stocks = list(BASE_STOCKS) + [stock(f"T{i:03d}", "us", 100.0 - i * 0.1, f"Co{i}") for i in range(600)]
    write_inputs(tmp_path, stocks)
    answers = dict(ALL_GOOD)
    answers[("ticker", "AAPL")] = [logo_answer("aapl", "brand_aapl", remaining="2000")]       # needs 1,220 + 1,000
    for i in range(600):
        answers[("ticker", f"T{i:03d}")] = [logo_answer(f"t{i}", f"b{i}")]
    net = Net(answers)
    rc, out = run(tmp_path, net, out_name="out2")
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["outcome"] == "balance_low" and info["ok"] is True
    assert net.lookups == [("ticker", "AAPL")] and sorted(index(out)["logos"]) == ["AAPL"]


def test_billed_answers_without_a_balance_are_said_once(tmp_path):
    write_inputs(tmp_path)
    answers = {k: [chk.Resp(r.status, {kk: vv for kk, vv in r.headers.items() if kk != "credits-remaining"}, r.body)
                   for r in v] for k, v in ALL_GOOD.items()}
    rc, out = run(tmp_path, Net(answers))
    log = (out / "run.log").read_text(encoding="utf-8")
    assert log.count("logo.dev 가 남은 크레딧을 알려 주지 않아요 — 이번 실행 상한 14,000 만 지켜요") == 1


def test_the_floor_counts_lookups_still_in_flight():
    led = F.Ledger(14_000)
    assert led.reserve() is None
    led.settle(chk.Resp(200, {"Credits-Charged": "1", "Credits-Remaining": "1007"}, b"{}"))   # balance 1007, none in flight
    assert led.reserve() is None                                                                # 1007 - 0 - 2 = 1005
    assert led.reserve() is None                                                                # 1007 - 2 - 2 = 1003
    assert led.reserve() is None                                                                # 1007 - 4 - 2 = 1001
    assert led.reserve() == "floor"                       # 1007 - 6 - 2 = 999 (ignoring in-flight: 1005, wrongly allowed)
    led.release()
    assert led.reserve() is None                                                                # one came back
    assert F.Ledger(10).reserve() is None and F.Ledger(1).reserve() == "cap"


def test_index_entries_carry_the_company_name_and_odd_codes_get_letter_marks(tmp_path):
    stocks = list(BASE_STOCKS) + [stock("X/Y", "us", 700.0, "Odd Co")]
    write_inputs(tmp_path, stocks)
    answers = dict(ALL_GOOD)
    answers[("ticker", "X/Y")] = [logo_answer("odd", "brand_odd")]
    rc, out = run(tmp_path, Net(answers))
    idx = index(out)
    assert idx["logos"]["005930"]["name"] == "삼성전자" and idx["logos"]["005935"]["name"] == "삼성전자우"
    assert idx["logos"]["AAPL"]["name"] == "Apple"
    assert (review(out)["X/Y"]["result"], review(out)["X/Y"]["reason"]) == ("letter", "odd_code")
    assert LI.validate_dir(out / "logos")[1] == []


def test_review_sheet_draws_every_flagged_company_without_caps(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("domain", "skhynix.com")] = [logo_answer("hynhome", "brand_other")]
    rc, out = run(tmp_path, Net(answers), "--sheet-top", "1")
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    counts = dict(info["sheet_counts"])
    assert counts["Korea outside the top 1: homepage logo used instead of a different ticker brand"] == 1
    assert counts["Korea outside the top 1: ticker logo kept, unverified by the DART homepage"] == 1   # 247540
    s = (out / "summary.md").read_text(encoding="utf-8")
    assert "## Review sheet" in s and "no caps" in s
    html_ = (out / "sheet.html").read_text(encoding="utf-8")
    assert "에코프로비엠" in html_ and "SK하이닉스" in html_


def answer_with_source(token, brand, source, cc="1"):
    """A 200 answer whose source block is exactly `source` (to fake undocumented sizes and formats)."""
    return chk.Resp(200, {"Credits-Charged": cc, "Credits-Remaining": "15000"}, body(
        {"data": {"object": "image", "kind": "logo", "brand_id": brand, "status": "ready",
                  "url": f"https://img.logo.dev/assets/{token}?sig=SIGNED", "etag": f"etag-{token}", "blurhash": "x",
                  "source": source, "last_updated_at": None, "expires_at": "2026-11-07T12:00:00Z"},
         "metadata": {"request_id": "r", "resolution": {"type": "ticker", "value": "X", "method": "security",
                                                        "context": {}}}}))


def test_a_vector_source_without_a_size_is_kept_after_a_good_download(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [answer_with_source("lmt", "brand_msft", {"width": 0, "height": 0, "format": "svg",
                                                                            "has_transparency": True, "is_vector": True})]
    answers[("ticker", "BRK-B")] = [answer_with_source("brk", "brand_brk", {"format": "svg", "has_transparency": True,
                                                                            "is_vector": False})]     # svg, no size
    net = Net(answers)
    rc, out = run(tmp_path, net)
    rv, idx = review(out), index(out)
    assert rc == 0 and json.loads((out / "run.json").read_text(encoding="utf-8"))["outcome"] == "complete"
    for code in ("MSFT", "BRK-B"):
        assert rv[code]["result"] == "logo" and rv[code]["vector"] == "True", code
        assert (idx["logos"][code]["w"], idx["logos"][code]["h"]) == (256, 256)              # the downloaded rendition
    assert dict(net.downloads)["lmt"]["size"] == "128"                                          # rendered at our size
    assert LI.validate_dir(out / "logos")[1] == []


@pytest.mark.parametrize("source", [
    {"width": 0, "height": 0, "format": "png", "has_transparency": True, "is_vector": False},   # a raster 0 x 0
    {"width": 300, "format": "png", "is_vector": False},                                         # a raster, one side
    {"width": 128, "height": 128, "format": "bmp2", "is_vector": False},                         # an unknown format
])
def test_an_odd_answer_is_that_companys_letter_mark_and_the_run_goes_on(tmp_path, source):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [answer_with_source("odd", "brand_msft", source)]
    net = Net(answers)
    rc, out = run(tmp_path, net)
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    rv = review(out)
    assert rc == 0 and info["outcome"] == "complete" and info["odd"] == 1
    assert (rv["MSFT"]["result"], rv["MSFT"]["reason"]) == ("letter", "odd_answer") and "MSFT" not in index(out)["logos"]
    assert rv["AAPL"]["result"] == rv["005930"]["result"] == "logo"                            # the others went on
    assert "source {" in rv["MSFT"]["note"] or "format" in rv["MSFT"]["note"]                   # raw source fields
    log = (out / "run.log").read_text(encoding="utf-8")
    assert "!! odd answer 1 (MSFT, ticker MSFT)" in log and '"width"' in log
    assert "SIGNED" not in log and "img.logo.dev/" not in rv["MSFT"]["note"]                    # never the address
    s = (out / "summary.md").read_text(encoding="utf-8")
    assert "- odd answers from logo.dev (letter mark, reason odd_answer): **1**" in s
    assert "Odd answers from logo.dev (letter mark)" in (out / "sheet.html").read_text(encoding="utf-8")


def test_an_odd_non_200_answer_is_per_company_too(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "MSFT")] = [chk.Resp(404, {"Credits-Charged": "0"}, body({"error": {"code": "x"}}))]
    rc, out = run(tmp_path, Net(answers))
    rv = review(out)
    assert rc == 0 and rv["MSFT"]["reason"] == "odd_answer" and rv["AAPL"]["result"] == "logo"


def test_more_than_30_odd_answers_stop_the_run_and_keep_what_was_found(tmp_path):
    stocks = list(BASE_STOCKS) + [stock(f"T{i:03d}", "us", 100.0 - i * 0.1, f"Co{i}") for i in range(40)]
    write_inputs(tmp_path, stocks)
    answers = dict(ALL_GOOD)
    for i in range(40):
        answers[("ticker", f"T{i:03d}")] = [answer_with_source(f"t{i}", f"b{i}", {"width": 0, "height": 0,
                                                                                    "format": "png", "is_vector": False})]
    net = Net(answers)
    rc, out = run(tmp_path, net, "--defer-failure")
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["outcome"] == "unexpected" and info["ok"] is False and info["odd"] == 31
    assert "more than 30 odd answers" in info["reason"]
    assert not any(i == f"T{k:03d}" for _, i in net.lookups for k in range(31, 40))             # nothing after the 31st
    assert sorted(index(out)["logos"]) == ["000660", "005930", "005935", "AAPL", "BRK-B", "MSFT"]   # found before: saved
    assert ("ticker", "005380.KS") not in net.lookups                                           # smaller: never reached
    assert LI.validate_dir(out / "logos")[1] == [] and (out / "review.csv").exists()
    assert F.verdict(out / "run.json") == 1


def test_the_answer_reader_on_its_own():
    ok = json.loads(answer_with_source("v", "b", {"width": 0, "height": 0, "format": "svg", "is_vector": True}).body)
    img, why = F.parse_logo(ok)
    assert why is None and img["is_vector"] and img["width"] is None
    for src in ({"width": 0, "height": 0, "is_vector": False}, {"width": -1, "height": 5}, {"width": True, "height": 5},
                {"width": 1.5, "height": 5}, {"width": 5, "height": 5, "format": "exe"}):
        assert F.parse_logo(json.loads(answer_with_source("v", "b", src).body))[1], src
    assert F.parse_logo(None)[1] and F.parse_logo({"data": []})[1]
    bad_host = json.loads(answer_with_source("v", "b", {"width": 5, "height": 5}).body)
    bad_host["data"]["url"] = "https://evil.example/x"
    assert "not https://img.logo.dev" in F.parse_logo(bad_host)[1]


def test_monogram_check_keeps_ordinary_logos():
    assert F.is_monogram(F._np().asarray(monogram()))
    assert not F.is_monogram(F._np().asarray(F.normalise(PICS["good"])))
    two_tone = Image.new("RGBA", (128, 128), (20, 20, 20, 255))
    ImageDraw.Draw(two_tone).rectangle((0, 0, 127, 40), fill=(250, 200, 0, 255))          # a banded flag, not a letter
    assert not F.is_monogram(F._np().asarray(two_tone))


def test_shared_pictures_are_grouped():
    a, b = F.normalise(PICS["good"]), F.normalise(PICS["mono"])
    swapped = Image.merge("RGBA", [a.getchannel(c) for c in ("B", "G", "R", "A")])          # same shapes, other colours
    groups = F.shared_groups([("A", F.fingerprint(a)), ("B", F.fingerprint(a)), ("C", F.fingerprint(b)),
                              ("D", F.fingerprint(swapped))])
    assert groups == [["A", "B"]]                                              # D: same shapes, not the same picture


# ── spend, stops and pacing ──

def test_spend_cap_is_never_passed_even_with_several_workers(tmp_path):
    stocks = list(BASE_STOCKS) + [stock(f"T{i:03d}", "us", 100.0 - i * 0.1, f"Co{i}") for i in range(60)]
    write_inputs(tmp_path, stocks)
    answers = dict(ALL_GOOD)
    for i in range(60):
        answers[("ticker", f"T{i:03d}")] = [logo_answer(f"t{i}", f"b{i}")]
    net = Net(answers)
    rc, out = run(tmp_path, net, "--max-credits", "41", workers="4")
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["outcome"] == "max_credits" and info["ok"] is True
    assert info["credits"]["counted"] <= 41 and info["credits"]["counted"] >= 38
    billed = sum(1 for r, i in net.lookups) - info["credits"]["free"]
    assert billed * 2 <= 41
    assert net.most_open <= 4
    rv = review(out)
    assert any(r["result"] == "" for r in rv.values())                         # the rest: unfinished, letter marks
    assert LI.validate_dir(out / "logos")[1] == []                              # what was found is still a valid folder


def test_free_repeats_are_not_counted(tmp_path):
    write_inputs(tmp_path)
    rc, out = run(tmp_path, Net(ALL_GOOD))
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert info["credits"]["charged"] == 7 and info["credits"]["free"] == 3 and info["credits"]["counted"] == 14


def test_402_stops_cleanly_and_keeps_what_was_found(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "BRK-B")] = [out_of_credits()]
    net = Net(answers)
    rc, out = run(tmp_path, net)
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["outcome"] == "out_of_credits" and info["ok"] is True
    assert ("ticker", "005930.KS") not in net.lookups                          # nothing after the 402
    assert sorted(index(out)["logos"]) == ["AAPL", "MSFT"]
    assert F.verdict(out / "run.json") == 0


def test_202_waits_and_retries_while_others_go_on(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "AAPL")] = [indexing(), logo_answer("aapl", "brand_aapl")]
    net = Net(answers)
    rc, out = run(tmp_path, net)
    assert rc == 0 and review(out)["AAPL"]["result"] == "logo"
    assert net.lookups.index(("ticker", "MSFT")) < len(net.lookups) - 1 - net.lookups[::-1].index(("ticker", "AAPL"))
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert info["requests"]["counts"]["202 retries"] == 1


def test_refused_key_stops_with_a_failing_verdict(tmp_path):
    write_inputs(tmp_path)
    answers = dict(ALL_GOOD)
    answers[("ticker", "AAPL")] = [chk.Resp(401, {}, body({"msg": "invalid api token"}))]
    rc, out = run(tmp_path, Net(answers), "--defer-failure")
    assert rc == 0                                                             # saved and uploaded first
    assert F.verdict(out / "run.json") == 1


# ── the key and signed addresses ──

def test_key_and_signed_addresses_never_reach_any_output(tmp_path, capsys):
    write_inputs(tmp_path)
    net = Net(ALL_GOOD)
    env = {F.KEY_ENV: FAKE_KEY}
    rc, out = run(tmp_path, net, env=env)
    assert rc == 0 and F.KEY_ENV not in env                                     # removed from the environment
    printed = capsys.readouterr()
    assert FAKE_KEY not in printed.out + printed.err and "SIGNED" not in printed.out + printed.err
    for p in out.rglob("*"):
        if p.is_file():
            b = p.read_bytes()
            assert FAKE_KEY.encode() not in b and b"img.logo.dev/" not in b and b"SIGNED" not in b, p
    for kind, h in net.headers:
        if kind == "api":
            assert h == {"Authorization": "Bearer " + FAKE_KEY, "Accept": "application/json"}
        else:
            assert h == {}                                                     # downloads carry no key
    assert (out / "sheet.html").exists() and (out / "summary.md").exists() and (out / "review.csv").exists()


def test_key_only_from_the_environment(tmp_path):
    write_inputs(tmp_path)
    with pytest.raises(SystemExit):
        run(tmp_path, Net(ALL_GOOD), "--reason", FAKE_KEY)
    with pytest.raises(SystemExit):
        run(tmp_path, Net(ALL_GOOD), env={F.KEY_ENV: "pk_publishable123456"})
    with pytest.raises(SystemExit):
        run(tmp_path, Net(ALL_GOOD), env={})


def test_a_signed_address_in_a_log_line_is_masked():
    log = chk.Log(lambda t: F.URL_RE.sub("[signed image address removed]", t))
    log("download https://img.logo.dev/assets/abc?sig=x failed")
    assert "img.logo.dev/" not in log.lines[-1]


# ── refusing bad data ──

def test_refuses_incomplete_data(tmp_path):
    write_inputs(tmp_path, [s for s in BASE_STOCKS if s["t"] != "005380"])
    with pytest.raises(SystemExit):
        run(tmp_path, Net(ALL_GOOD))
    stocks = [dict(s, cap=None) if s["cls"] == "kr" else s for s in BASE_STOCKS]
    stocks += [stock(f"0{i:04d}0", "kr", None) for i in range(30)]
    write_inputs(tmp_path, stocks)
    with pytest.raises(SystemExit):
        run(tmp_path, Net(ALL_GOOD))


def test_plan_only_needs_no_key_and_calls_nothing(tmp_path, capsys):
    write_inputs(tmp_path)
    net = Net(ALL_GOOD)
    rc, _ = run(tmp_path, net, "--plan-only", env={})
    assert rc == 0 and net.lookups == [] and net.downloads == []
    assert "at most 10 (7 by ticker + 3 by DART homepage)" in capsys.readouterr().out


# ── after review: switching companies to the letter mark ──

def test_drop_switches_a_company_and_its_preferred_share(tmp_path):
    write_inputs(tmp_path)
    rc, out = run(tmp_path, Net(ALL_GOOD))
    assert F.main(["--drop", "005930", "--dir", str(out), "--reason", "wrong company"]) == 0
    idx = index(out)
    assert "005930" not in idx["logos"] and "005935" not in idx["logos"] and "AAPL" in idx["logos"]
    assert not (out / "logos" / "005930.webp").exists() and LI.validate_dir(out / "logos")[1] == []
    assert "005930" in (out / "drops.csv").read_text(encoding="utf-8")
    assert "Switched to the letter mark after review" in (out / "summary.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        F.main(["--drop", "NOPE", "--dir", str(out)])


# ── the logo folder rules ──

def webp128(color=(10, 20, 30, 255)):
    b = io.BytesIO()
    Image.new("RGBA", (128, 128), color).save(b, "WEBP", quality=90)
    return b.getvalue()


def make_folder(path, logos, files):
    path.mkdir(parents=True, exist_ok=True)
    (path / "index.json").write_text(json.dumps({"version": 1, "size": 128, "logos": logos}), encoding="utf-8")
    for n, b in files.items():
        (path / n).write_bytes(b)
    return path


ENTRY = {"file": "005930.webp", "name": "삼성전자", "route": "ticker", "w": 512, "h": 512, "vector": False, "flags": []}


def test_index_rules(tmp_path):
    ok = make_folder(tmp_path / "ok", {"005930": ENTRY, "005935": dict(ENTRY, name="삼성전자우", via="005930")},
                     {"005930.webp": webp128()})
    assert LI.validate_dir(ok)[1] == []
    cases = {
        "two-codes-one-file": ({"005930": ENTRY, "000660": dict(ENTRY, name="SK하이닉스")}, {"005930.webp": webp128()}),
        "no-name": ({"005930": {k: v for k, v in ENTRY.items() if k != "name"}}, {"005930.webp": webp128()}),
        "blank-name": ({"005930": dict(ENTRY, name="  ")}, {"005930.webp": webp128()}),
        "unlisted": ({"005930": ENTRY}, {"005930.webp": webp128(), "000660.webp": webp128()}),
        "missing": ({"005930": ENTRY, "000660": dict(ENTRY, file="000660.webp")}, {"005930.webp": webp128()}),
        "svg": ({"005930": dict(ENTRY, file="005930.svg")}, {"005930.svg": b"<svg onload=alert(1)>"}),
        "path": ({"005930": dict(ENTRY, file="../x.webp")}, {"005930.webp": webp128()}),
        "not-a-picture": ({"005930": ENTRY}, {"005930.webp": b"RIFF....WEBPjunkjunkjunkjunkjunkjunkjunkjunk"}),
        "wrong-size": ({"005930": ENTRY}, {"005930.webp": (lambda: (lambda b: (Image.new("RGB", (64, 64)).save(b, "WEBP"), b.getvalue())[1])(io.BytesIO()))()}),
        "bad-via": ({"005935": dict(ENTRY, via="000660")}, {"005930.webp": webp128()}),
        "bad-route": ({"005930": dict(ENTRY, route="name")}, {"005930.webp": webp128()}),
    }
    for name, (logos, files) in cases.items():
        assert LI.validate_dir(make_folder(tmp_path / name, logos, files))[1], name
    sub = make_folder(tmp_path / "sub", {"005930": ENTRY}, {"005930.webp": webp128()})
    (sub / "inner").mkdir()
    assert LI.validate_dir(sub)[1]
    nan = make_folder(tmp_path / "nan", {"005930": ENTRY}, {"005930.webp": webp128()})
    (nan / "index.json").write_text('{"version": 1, "size": 128, "logos": {"005930": {"file": "005930.webp", '
                                    '"route": "ticker", "w": NaN, "h": 1}}}')
    assert LI.validate_dir(nan)[1]


def test_keep_current_drops_reused_or_renamed_codes_and_their_preferred_shares():
    index = {"version": 1, "size": 128, "logos": {
        "005930": ENTRY, "005935": dict(ENTRY, name="삼성전자우", via="005930"),
        "000660": dict(ENTRY, file="000660.webp", name="SK하이닉스"), "AAPL": dict(ENTRY, file="AAPL.webp", name="Apple")}}
    data = {"stocks": [{"t": "005930", "nk": "삼성전자"}, {"t": "005935", "nk": "삼성전자우"},
                       {"t": "000660", "nk": "다른 회사"}, {"t": "MSFT", "nk": "Microsoft"}]}
    out, gone, unknown = LI.keep_current(index, LI.stock_names(data))
    assert sorted(out["logos"]) == ["005930", "005935"] and gone == ["000660", "AAPL"] and out["count"] == 2
    assert unknown == []
    out, gone, unknown = LI.keep_current(index, LI.stock_names({"stocks": [{"t": "005935", "nk": "삼성전자우"}]}))
    assert out["logos"] == {} and "005935" in gone                                # issuer gone -> preferred gone too
    assert index["logos"]["000660"]["name"] == "SK하이닉스"                        # the input is not changed


def test_harmless_name_changes_keep_the_logo_and_nameless_ones_do_not():
    index = {"version": 1, "size": 128, "logos": {
        "HLT": dict(ENTRY, file="HLT.webp", name="Hilton Worldwide Holdings Inc. Common Stock"),
        "ZZ": dict(ENTRY, file="ZZ.webp", name="ZZ"),                                          # the name was the ticker
        "AB": dict(ENTRY, file="AB.webp", name="Alpha  Beta   Corp"),                          # double spaces
        "005930": dict(ENTRY, name="㈜삼성전자"), "C1": dict(ENTRY, file="C1.webp", name="Gamma Inc. Class A"),
        "OLD": dict(ENTRY, file="OLD.webp", name="Old Company")}}
    today = {"HLT": "Hilton Worldwide Holdings Inc.", "ZZ": "Zeta Zulu Holdings", "AB": "alpha beta corp",
             "005930": "삼성전자 주식회사", "C1": "GAMMA INC", "OLD": "New Company"}
    out, gone, unknown = LI.keep_current(index, today)
    assert gone == ["OLD"] and unknown == ["ZZ"] and sorted(out["logos"]) == ["005930", "AB", "C1", "HLT"]
    out, gone, unknown = LI.keep_current(index, dict(today, AB="", OLD="OLD", ZZ="Zeta Zulu Holdings"))
    assert unknown == ["AB", "OLD", "ZZ"] and gone == []                                       # empty or just the code
    assert sorted(out["logos"]) == ["005930", "C1", "HLT"]
    assert LI.same_company("A", "Alpha", "Beta") == "different" and LI.same_company("A", "Alpha", "ALPHA") == "same"
    assert LI.same_company("A", "A", "Alpha") == LI.same_company("A", "Alpha", " ") == "unknown"


def test_image_size_reads_png_and_every_webp_kind():
    for mode, kw in (("RGBA", {}), ("RGB", {}), ("RGBA", {"lossless": True})):
        b = io.BytesIO()
        Image.new(mode, (128, 96)).save(b, "WEBP", **kw)
        assert LI.image_size("x.webp", b.getvalue()) == (128, 96), (mode, kw)
    assert LI.image_size("x.png", png(Image.new("RGBA", (128, 7)))) == (128, 7)
    assert LI.image_size("x.png", PICS["good"][:10]) is None


# ── the workflow ──

def test_fetch_workflow_is_hand_run_read_only_and_keeps_the_secret_in_one_step():
    path = ROOT / ".github" / "workflows" / "logo-dev-fetch.yml"
    wf = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw = path.read_text(encoding="utf-8")
    assert list(wf[True]) == ["workflow_dispatch"]                               # by hand only
    assert wf["permissions"] == {"contents": "read"}
    assert_no_hidden_failure(wf)
    job = wf["jobs"]["fetch"]
    assert 120 <= job["timeout-minutes"] <= 180
    st = job["steps"]
    assert st[0]["uses"].startswith("actions/checkout") and st[0]["with"]["persist-credentials"] is False
    with_key = [s for s in st if "LOGO_DEV_SECRET_KEY" in json.dumps(s)]
    assert len(with_key) == 1 and with_key[0]["env"]["LOGO_DEV_SECRET_KEY"] == "${{ secrets.LOGO_DEV_SECRET_KEY }}"
    assert raw.count("secrets.") == 1
    run_ = with_key[0]["run"]
    assert "tools/logos/logodev_fetch.py" in run_ and "--defer-failure" in run_ and "--out" in run_
    up = next(s for s in st if s.get("uses", "").startswith("actions/upload-artifact"))
    assert up["with"]["retention-days"] == 7 and up["with"]["if-no-files-found"] == "error"
    assert wf["concurrency"]["group"] == "logo-dev-fetch"                       # two runs never overlap
    inp = wf[True]["workflow_dispatch"]["inputs"]["max_credits"]
    assert inp["default"] == 14000 and "14,000" in inp["description"]
    frd = wf[True]["workflow_dispatch"]["inputs"]["full_run_date"]                # the cross-run guard
    assert frd["type"] == "string" and frd["default"] == ""
    assert with_key[0]["env"]["FULL_RUN_DATE"] == "${{ inputs.full_run_date }}" and '--full-run-date "$FULL_RUN_DATE"' in run_
    assert "--verdict" in st[-1]["run"]
    assert "push_logos_branch" not in raw and "git push" not in raw and "contents: write" not in raw
    assert wf["concurrency"]["cancel-in-progress"] is False
