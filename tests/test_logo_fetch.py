# -*- coding: utf-8 -*-
"""v19.3a logos: the logo.dev fetch job (tools/logos/logodev_fetch.py), its hand-run workflow
(.github/workflows/logo-dev-fetch.yml) and the logo folder rules (tools/logos/logo_index.py).

No network and no real key: the HTTP client is faked (lookups and downloads), the clocks are fake, the key is made up.
Covers: exact identifiers (Korea .KS / .KQ, US bare; the DART homepage domain only for Korea, only domain_ok = 1),
market-cap order, the credit cap (also with several workers at once), the 402 stop, Credits-Charged counting, 202
retries, the brand_id cross-check (same brand · another brand · unverified), preferred shares reusing their issuer's
logo with no lookup, the automatic quality checks (small · blank · one colour · monogram), 128 px WebP files that are
never upscaled, a valid index.json, the key and signed addresses never in any output, the --drop switch after review,
and the workflow's shape (read-only, the secret in one step only).
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


PICS = {
    "good": png(good_logo()),
    "good100": png(good_logo(100)),
    "blank": png(Image.new("RGBA", (128, 128), (0, 0, 0, 0))),
    "flat": png(Image.new("RGBA", (128, 128), (238, 238, 238, 255))),
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


def logo_answer(token, brand, w=512, h=512, vector=False, cc="1", etag=None):
    return chk.Resp(200, {"Credits-Charged": cc, "Credits-Remaining": "15000"}, body(
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

    def __call__(self, url, params=None, headers=None, timeout=None, max_bytes=None):
        with self.lock:
            self.open += 1
            self.most_open = max(self.most_open, self.open)
        try:
            if url == chk.API_BASE + chk.LOGO_ROUTE:
                (route, ident), = params.items()
                self.lookups.append((route, ident))
                self.headers.append(("api", dict(headers)))
                q = self.answers.get((route, ident)) or [not_found()]
                return q.pop(0) if len(q) > 1 else q[0]
            assert url.startswith("https://img.logo.dev/assets/"), url
            self.headers.append(("img", dict(headers)))
            token = url.split("/assets/", 1)[1].split("?", 1)[0]
            q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
            self.downloads.append((token, q))
            pic = self.pics.get(token, PICS["good"])
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


def run(tmp, net, *extra, workers="1", env=None, webp=True, clock=None):
    clock = clock or Clock()
    environ = {F.KEY_ENV: FAKE_KEY} if env is None else env
    deps = F.Deps(send=net, clock=clock, sleep=clock.sleep, wall=lambda: chk.now_kst(), environ=environ,
                  jitter=lambda: 0.0, min_counts={"kr": 1, "us": 1}, render=lambda *a: ([], None), webp=webp)
    out = tmp / "out"
    rc = F.main(["--data", str(tmp / "data.json"), "--listing", str(tmp / "listing.csv"), "--homepages",
                 str(tmp / "homes.csv"), "--out", str(out), "--workers", workers, "--no-png", *extra], deps)
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
    assert idx["logos"]["005935"] == dict(idx["logos"]["005930"], via="005930")    # preferred: the issuer's file
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
    assert (rv["005380"]["result"], rv["005380"]["reason"]) == ("letter", "monogram")
    assert rv["000660"]["result"] == "logo"                                   # a white logo on transparency passes
    assert rv["AAPL"]["result"] == "logo"
    s = (out / "summary.md").read_text(encoding="utf-8")
    for k in ("small", "blank", "one_colour", "monogram"):
        assert f"- {k}: **1**" in s, k
    assert "difference hash" in s and "monogram" in s                          # the methods are described


def test_monogram_check_keeps_ordinary_logos():
    assert F.is_monogram(F._np().asarray(monogram()))
    assert not F.is_monogram(F._np().asarray(F.normalise(PICS["good"])))
    two_tone = Image.new("RGBA", (128, 128), (20, 20, 20, 255))
    ImageDraw.Draw(two_tone).rectangle((0, 0, 127, 40), fill=(250, 200, 0, 255))          # a banded flag, not a letter
    assert not F.is_monogram(F._np().asarray(two_tone))


def test_shared_pictures_are_grouped():
    a, b = F.normalise(PICS["good"]), F.normalise(PICS["mono"])
    groups = F.shared_groups([("A", F.dhash(a)), ("B", F.dhash(a)), ("C", F.dhash(b))])
    assert groups == [["A", "B"]]


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


ENTRY = {"file": "005930.webp", "route": "ticker", "w": 512, "h": 512, "vector": False, "flags": []}


def test_index_rules(tmp_path):
    ok = make_folder(tmp_path / "ok", {"005930": ENTRY, "005935": dict(ENTRY, via="005930")}, {"005930.webp": webp128()})
    assert LI.validate_dir(ok)[1] == []
    cases = {
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
    assert up["with"]["retention-days"] == 1 and up["with"]["if-no-files-found"] == "error"
    assert "--verdict" in st[-1]["run"]
    assert "push_logos_branch" not in raw and "git push" not in raw and "contents: write" not in raw
    assert wf["concurrency"]["cancel-in-progress"] is False
