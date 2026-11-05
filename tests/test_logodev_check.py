# -*- coding: utf-8 -*-
"""logo.dev API check (tools/logos/logodev_api_check.py) and its hand-run workflow (.github/workflows/logo-dev-check.yml).

No network and no real key: the HTTP client is faked, the clocks are fake, and the key is a made-up sk_ value.
Covers the stratified sample (same seed -> same sample), the exact identifiers (Korea .KS / .KQ, US bare; the DART
domain only after a free not_found, Korea only), what each answer means (200 · free 404 · billed 404 · 202 with retries
· 429 with waits · 402 stop · 401), credit counting and the --max-credits stop, pacing (one at a time, at most 60 a
minute), image downloads without the key, a stop on an answer the docs don't describe (partial results saved), the key
never appearing in any output or log, the summary's math, and the workflow's shape.
"""
import csv
import datetime as dt
import json
import pathlib
import random
import re
import sys
from zoneinfo import ZoneInfo

import pytest
import yaml

from test_workflows import assert_no_hidden_failure

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))

import logo_ids as li  # noqa: E402
import logodev_api_check as L  # noqa: E402

FAKE_KEY = "sk_TestOnly0123456789abcdefXYZ"
IMG_URL = "https://img.logo.dev/assets/SIGNED_TOKEN_abc"
PNG_BYTES = (L.PNG + b"\x00\x00\x00\rIHDR" + (256).to_bytes(4, "big") + (256).to_bytes(4, "big")
             + b"\x08\x06\x00\x00\x00" + b"\x00" * 40)                           # a 256 x 256 PNG header
KST = ZoneInfo("Asia/Seoul")


# ── fakes ──

class Clock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def body(obj):
    return json.dumps(obj).encode("utf-8")


def ok_logo(cc="1", url=IMG_URL, w=512, h=512, **headers):
    headers = {k.replace("_", "-"): v for k, v in headers.items()}
    return L.Resp(200, {"Credits-Charged": cc, "Credits-Remaining": "400", "Request-Id": "request_1", **headers}, body(
        {"data": {"object": "image", "kind": "logo", "brand_id": "brand_1", "status": "ready", "url": url, "etag": "e1",
                  "blurhash": "x", "source": {"width": w, "height": h, "format": "png", "has_transparency": True,
                                              "is_vector": False},
                  "last_updated_at": None, "expires_at": "2026-11-06T12:00:00Z"},
         "metadata": {"request_id": "request_1",
                      "resolution": {"type": "ticker", "value": "X", "method": "security", "context": {}}}}))


def not_found(cc="0"):
    return L.Resp(404, {"Credits-Charged": cc}, body({"data": {"object": "image", "status": "not_found"},
                                                      "metadata": {"request_id": "r"}, "docs_url": "https://x"}))


def no_image():
    return not_found(cc="1")


def indexing(wait="30"):
    return L.Resp(202, {"Retry-After": wait, "Credits-Charged": "0"}, body(
        {"data": {"object": "image", "status": "not_indexed"},
         "metadata": {"request_id": "r", "pending": {"reason": "indexing", "retry_after_seconds": 30,
                                                     "expires_in_seconds": 300}}}))


def limited(**headers):
    return L.Resp(429, {k.replace("_", "-"): v for k, v in headers.items()},
                  body({"error": {"code": "rate_limited", "message": "slow down"}}))


def broke():
    return L.Resp(402, {}, body({"error": {"code": "insufficient_credits", "message": "out of credits"}}))


class FakeAPI:
    """Answers by identifier from a script {(route, id): [answer, ...]} (one per call; the last one repeats), else a
    free not_found. An answer may be an exception (raised) or a callable. Records every call with the fake time."""

    def __init__(self, clock, script=None, image=PNG_BYTES, image_type="image/png"):
        self.clock, self.script = clock, {k: list(v) for k, v in (script or {}).items()}
        self.image, self.image_type = image, image_type
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None, max_bytes=None):
        self.calls.append({"t": self.clock(), "url": url, "params": dict(params or {}), "headers": dict(headers or {}),
                           "max_bytes": max_bytes})
        if url.startswith(L.API_BASE):
            (route, ident), = params.items()
            seq = self.script.get((route, ident))
            a = (seq.pop(0) if len(seq) > 1 else seq[0]) if seq else not_found()
            if isinstance(a, Exception):
                raise a
            return a() if callable(a) else a
        return L.Resp(200, {"Content-Type": self.image_type}, self.image)

    def lookups(self):
        return [tuple(c["params"].items())[0] for c in self.calls if c["url"].startswith(L.API_BASE)]


def comp(code, side="kr", market="KOSPI", cap=1.0, domain="", group=None, name=None):
    return {"code": code, "name": name or f"회사 {code}", "side": side, "market": "US" if side == "us" else market,
            "cap": cap, "ticker": li.logodev_ticker(code, "US" if side == "us" else market), "isin": "", "domain": domain,
            "group": group or ("US" if side == "us" else "KR-TOP"), "rank": None}


def make_checker(script=None, max_credits=480):
    clock = Clock()
    api = FakeAPI(clock, script)
    client = L.Client(FAKE_KEY, api, L.Pacer(clock, clock.sleep))
    log = L.Log(li.Masker(FAKE_KEY))
    return L.Checker(client, max_credits, log, clock, None, jitter=lambda: 0.0), api, clock


def universe(n_kr=2000, n_us=600, seed=1):
    rng = random.Random(seed)
    kr = [comp(f"{i:05d}0", cap=round(rng.uniform(0.01, 300), 3), market=rng.choice(["KOSPI", "KOSDAQ"]))
          for i in range(1, n_kr + 1)]
    us = [comp(f"U{i:04d}", side="us", cap=rng.uniform(1, 3000)) for i in range(n_us)]
    return kr + us


# ── the sample ──

def test_sample_is_stratified_and_the_same_for_the_same_seed():
    cs = universe()
    order, groups, left_out = L.draw_sample(cs, 300, 20261105)
    again, _, _ = L.draw_sample(list(reversed(cs)), 300, 20261105)       # input order does not matter
    assert [c["code"] for c in order] == [c["code"] for c in again]
    other, _, _ = L.draw_sample(cs, 300, 7)
    assert [c["code"] for c in other] != [c["code"] for c in order]
    assert {g: v["sampled"] for g, v in groups.items()} == {"US": 100, "KR-TOP": 100, "KR-REST": 100}
    assert {g: v["population"] for g, v in groups.items()} == {"US": 600, "KR-TOP": 1000, "KR-REST": 1000}
    assert len({c["code"] for c in order}) == 300
    by_cap = sorted((c for c in cs if c["side"] == "kr"), key=lambda c: (-c["cap"], c["code"]))
    top = {c["code"] for c in by_cap[:1000]}
    assert all(c["side"] == "us" for c in order if c["group"] == "US")
    assert all(c["code"] in top and c["rank"] <= 1000 for c in order if c["group"] == "KR-TOP")
    assert all(c["code"] not in top and c["rank"] > 1000 for c in order if c["group"] == "KR-REST")
    assert [c["group"] for c in order[:6]] == ["US", "KR-TOP", "KR-REST"] * 2    # groups in turn: an early stop is fair
    assert left_out == {"no ticker (market unknown)": [], "Korea, no market cap (cannot be ranked)": []}
    assert L.group_sizes(100) == {"US": 33, "KR-TOP": 33, "KR-REST": 34}


def test_sample_leaves_out_what_cannot_be_ranked_or_looked_up_and_says_so():
    cs = universe(n_kr=1200, n_us=50)
    cs[0]["cap"] = None                                   # cannot be ranked
    cs[1]["cap"] = float("nan")
    cs[2]["ticker"] = ""                                   # market unknown: no ticker
    order, _, left_out = L.draw_sample(cs, 30, 1)
    assert left_out["Korea, no market cap (cannot be ranked)"] == sorted([cs[0]["code"], cs[1]["code"]])
    assert left_out["no ticker (market unknown)"] == [cs[2]["code"]]
    assert not {cs[0]["code"], cs[1]["code"], cs[2]["code"]} & {c["code"] for c in order}
    with pytest.raises(SystemExit, match="fewer than"):
        L.draw_sample(universe(n_kr=1010, n_us=50), 60, 1)          # 20 to draw from 10 left after the top 1,000


# ── exact identifiers ──

def test_identifiers_are_exact_ks_kq_and_us_bare():
    data = {"stocks": [
        {"t": "005930", "nk": "삼성전자", "cls": "kr", "etf": False, "cap": 500},
        {"t": "247540", "nk": "에코프로비엠", "cls": "kr", "etf": False, "cap": 20},
        {"t": "123450", "nk": "코넥스회사", "cls": "kr", "etf": False, "cap": 1},
        {"t": "005935", "nk": "삼성전자우", "cls": "kr", "etf": False, "cap": 50},
        {"t": "069500", "nk": "KODEX 200", "cls": "kr", "etf": True, "fund": True},
        {"t": "088980", "nk": "맥쿼리인프라", "cls": "kr", "etf": True},
        {"t": "BRK-B", "nk": "버크셔", "cls": "us", "etf": False, "cap": 900},
        {"t": "AAPL", "nk": "애플", "cls": "us", "etf": False, "cap": 4000},
        {"t": "SPY", "nk": "SPY", "cls": "us", "etf": True},
    ]}
    listing = {"005930": {"Code": "005930", "Market": "KOSPI"}, "247540": {"Code": "247540", "Market": "KOSDAQ"},
               "123450": {"Code": "123450", "Market": "KONEX"}}
    homepages = {"005930": {"code": "005930", "domain": "samsung.com", "domain_ok": "1", "corp_cls": "Y"},
                 "247540": {"code": "247540", "domain": "blog.naver.com", "domain_ok": "0", "domain_note": "platform host"}}
    cs, _ = L.lsrc.build_companies(data, listing, homepages)
    got = {c["code"]: (c["ticker"], c["domain"]) for c in cs}
    assert got == {"005930": ("005930.KS", "samsung.com"), "247540": ("247540.KQ", ""), "123450": ("123450.KS", ""),
                   "BRK-B": ("BRK-B", ""), "AAPL": ("AAPL", "")}            # no ETF, fund or preferred share


def test_ticker_first_then_the_domain_only_after_a_free_not_found_and_only_in_korea():
    cs = [comp("005930", domain="samsung.com"),               # ticker not_found (free) -> domain
          comp("000660", domain="skhynix.com"),               # ticker no_image (billed) -> no domain
          comp("247540", market="KOSDAQ", domain="ecoprobm.co.kr"),   # ticker logo -> no domain
          comp("111110"),                                     # not_found, no usable domain -> stays not_found
          comp("222220", domain="x-corp.co.kr"),              # not_indexed after retries -> no domain
          comp("ZZZZ", side="us", domain="zzzz.com")]         # US not_found -> never a domain, even if one is known
    ch, api, _ = make_checker({("ticker", "000660.KS"): [no_image()], ("ticker", "247540.KQ"): [ok_logo()],
                               ("domain", "samsung.com"): [ok_logo()], ("ticker", "222220.KS"): [indexing()]})
    ch.run(cs)
    assert api.lookups() == [("ticker", "005930.KS"), ("domain", "samsung.com"), ("ticker", "000660.KS"),
                             ("ticker", "247540.KQ"), ("ticker", "111110.KS"), ("ticker", "222220.KS"),
                             ("ticker", "ZZZZ"), ("ticker", "222220.KS"), ("ticker", "222220.KS")]
    rows = {r["code"]: r for r in L.result_rows(ch)}
    assert {c: (r["status"], r["route"], r["ticker_status"], r["domain_status"]) for c, r in rows.items()} == {
        "005930": ("logo", "domain", "not_found", "logo"), "000660": ("no_image", "ticker", "no_image", ""),
        "247540": ("logo", "ticker", "logo", ""), "111110": ("not_found", "ticker", "not_found", ""),
        "222220": ("not_indexed", "ticker", "not_indexed", ""), "ZZZZ": ("not_found", "ticker", "not_found", "")}
    for c in api.calls:                                       # the only identifiers ever sent: ticker or domain
        assert set(c["params"]) <= {"ticker", "domain"} and "name" not in c["params"]
        assert c["url"] == "https://api.logo.dev/v2/brands/logo"
        assert c["headers"]["Authorization"] == "Bearer " + FAKE_KEY
    with pytest.raises(ValueError):
        ch.client.lookup("name", "Samsung")


# ── what each answer means ──

@pytest.mark.parametrize("resp,kind", [
    (ok_logo(), "logo"), (ok_logo(cc="0"), "logo"), (not_found(), "not_found"), (no_image(), "no_image"),
    (indexing(), "retry"), (limited(Retry_After="3"), "rate_limited"), (broke(), "out_of_credits"),
    (L.Resp(401, {}, body({"msg": "invalid api token"})), "refused"),
    (L.Resp(403, {}, body({"error": {"code": "forbidden", "message": "no"}})), "refused"),
    (L.Resp(400, {}, body({"error": {"code": "invalid_request", "message": "bad ticker"}})), "bad_request"),
    (L.Resp(500, {}, body({"error": {"code": "internal", "message": "oops"}})), "server_error"),
])
def test_status_mapping(resp, kind):
    assert L.classify(resp)[0] == kind


def test_a_logo_answer_is_read_as_documented():
    kind, info = L.classify(ok_logo(w=800, h=600))
    assert kind == "logo" and info["image"] == {"url": IMG_URL, "width": 800, "height": 600, "format": "png",
                                                "is_vector": False, "etag": "e1", "shape": "data", "kind": "logo"}
    brand_style = L.Resp(200, {"Credits-Charged": "1"}, body({"data": {"object": "brand", "status": "ready", "logo": {
        "url": IMG_URL, "etag": "e2", "source": {"width": 10, "height": 10, "format": "svg", "is_vector": True}}},
        "metadata": {}}))
    assert L.classify(brand_style)[1]["image"]["shape"] == "data.logo"
    assert L.classify(indexing("45"))[1] == {"wait": 45, "wait_source": "Retry-After"}
    no_header = L.Resp(202, {}, body({"data": {"object": "image", "status": "not_indexed"},
                                      "metadata": {"pending": {"retry_after_seconds": 50}}}))
    assert L.classify(no_header)[1] == {"wait": 50, "wait_source": "metadata.pending.retry_after_seconds"}
    bare = L.Resp(202, {}, body({"data": {"object": "image", "status": "not_indexed"}, "metadata": []}))
    assert L.classify(bare)[1]["wait"] == 30                              # documented value, said in the log
    assert L.classify(ok_logo(w=512.0, h=256.0))[1]["image"]["width"] == 512   # a whole number sent as 512.0


@pytest.mark.parametrize("resp", [
    L.Resp(200, {"Credits-Charged": "1"}, b"<html>not json</html>"),
    L.Resp(200, {"Credits-Charged": "1"}, body({"data": {"object": "image", "status": "ready", "source": {}}})),
    ok_logo(url="https://elsewhere.example.com/x.png"),
    ok_logo(url="http://img.logo.dev/assets/x"),
    ok_logo(w=0),
    L.Resp(404, {}, body({"data": {"object": "image", "status": "not_found"}})),          # no Credits-Charged
    L.Resp(404, {"Credits-Charged": "0"}, body({"data": {"object": "image", "status": "gone"}})),
    L.Resp(404, {"Credits-Charged": "0"}, body({"error": {"code": "resource_missing", "message": "x"}})),
    L.Resp(202, {"Retry-After": "30"}, body({"data": {"status": "ready"}})),
    L.Resp(301, {"Location": "https://x"}, b""),
    L.Resp(418, {}, b"{}"),
])
def test_answers_the_docs_do_not_describe_are_unexpected(resp):
    with pytest.raises(L.Unexpected):
        L.classify(resp)


def test_202_is_retried_at_most_twice_and_the_others_go_on_meanwhile():
    cs = [comp("005930", group="US"), comp("000660", group="KR-TOP"), comp("035420", group="KR-REST")]
    ch, api, clock = make_checker({("ticker", "005930.KS"): [indexing("30"), indexing("30"), ok_logo()],
                                   ("ticker", "000660.KS"): [indexing("40")]})
    ch.run(cs)
    seq = api.lookups()
    assert seq[:3] == [("ticker", "005930.KS"), ("ticker", "000660.KS"), ("ticker", "035420.KS")]   # no blocking
    assert seq.count(("ticker", "005930.KS")) == 3 and seq.count(("ticker", "000660.KS")) == 3      # 1 + 2 retries
    rows = {r["code"]: r["status"] for r in L.result_rows(ch)}
    assert rows == {"005930": "logo", "000660": "not_indexed", "035420": "not_found"}
    times = {}
    for c in api.calls:
        times.setdefault(c["params"]["ticker"], []).append(c["t"])
    assert all(b - a >= 30 for a, b in zip(times["005930.KS"], times["005930.KS"][1:]))
    assert all(b - a >= 40 for a, b in zip(times["000660.KS"], times["000660.KS"][1:]))
    assert ch.credits_counted == 2 and ch.counts["202 retries"] == 4
    huge, hapi, hclock = make_checker({("ticker", "005930.KS"): [indexing("9999"), ok_logo()]})
    huge.run([comp("005930")])                                             # never asked again sooner than told
    row = L.result_rows(huge)[0]
    assert len(hapi.calls) == 1 and row["status"] == "not_indexed" and "9999 s" in row["note"]
    assert huge.counts["202 not retried (wait too long)"] == 1 and not hclock.sleeps


def test_429_waits_as_told_then_backs_off_and_stops_when_it_never_ends():
    ch, api, clock = make_checker({("ticker", "AAPL"): [limited(Retry_After="7"), ok_logo()],
                                   ("ticker", "MSFT"): [limited(RateLimit_Remaining="0", RateLimit_Reset="12"),
                                                        ok_logo()],
                                   ("ticker", "NVDA"): [limited(), limited(), ok_logo()]})
    ch.run([comp("AAPL", side="us"), comp("MSFT", side="us"), comp("NVDA", side="us")])
    assert [r["status"] for r in L.result_rows(ch)] == ["logo"] * 3
    assert 7 in clock.sleeps and 12 in clock.sleeps                        # Retry-After, then RateLimit-Reset
    assert 2.0 in clock.sleeps and 4.0 in clock.sleeps                     # no headers: 2, 4 ... seconds
    assert ch.counts["retries after 429"] == 4 and ch.credits_counted == 6
    ch2, api2, _ = make_checker({("ticker", "AAPL"): [limited(Retry_After="1")]})
    ch2.run([comp("AAPL", side="us"), comp("MSFT", side="us")])
    assert ch2.stop.outcome == "error" and "429" in ch2.stop.reason
    assert len(api2.calls) == 1 + L.RETRIES_429 and [r["status"] for r in L.result_rows(ch2)] == ["", ""]
    ch3, api3, _ = make_checker({("ticker", "AAPL"): [limited(Retry_After="3600")]})
    ch3.run([comp("AAPL", side="us")])
    assert ch3.stop.outcome == "error" and "wait 3600" in ch3.stop.reason and len(api3.calls) == 1


def test_window_used_up_holds_the_next_request():
    ch, api, clock = make_checker({("ticker", "AAPL"): [ok_logo(RateLimit_Remaining="0", RateLimit_Reset="20")]})
    ch.run([comp("AAPL", side="us"), comp("MSFT", side="us")])
    assert api.calls[1]["t"] - api.calls[0]["t"] >= 20


def test_402_stops_the_whole_run_cleanly_and_reports():
    cs = [comp(f"U{i}", side="us") for i in range(5)]
    ch, api, _ = make_checker({("ticker", "U0"): [ok_logo()], ("ticker", "U1"): [ok_logo()],
                               ("ticker", "U2"): [broke()]})
    ch.run(cs)
    assert ch.stop.outcome == "out_of_credits" and "402" in ch.stop.reason
    assert len(api.calls) == 3                                            # nothing after the 402
    rows = L.result_rows(ch)
    assert [r["status"] for r in rows] == ["logo", "logo", "", "", ""] and ch.credits_counted == 4


def test_401_stops_with_a_plain_message_about_the_secret():
    ch, api, _ = make_checker({("ticker", "AAPL"): [L.Resp(401, {}, body({"msg": "invalid api token"}))]})
    ch.run([comp("AAPL", side="us"), comp("MSFT", side="us")])
    assert ch.stop.outcome == "error" and "LOGO_DEV_SECRET_KEY" in ch.stop.reason and len(api.calls) == 1


def test_no_answer_is_retried_then_an_error_counted_as_possibly_billed_and_five_in_a_row_stop():
    boom = ConnectionError("reset")
    ch, api, clock = make_checker({("ticker", f"U{i}"): [boom] for i in range(7)})
    ch.run([comp(f"U{i}", side="us") for i in range(7)])
    assert [r["status"] for r in L.result_rows(ch)][:5] == ["error"] * 5
    assert ch.stop.outcome == "error" and "5 companies in a row" in ch.stop.reason
    assert len(api.calls) == 5 * (1 + L.RETRIES_TRANSIENT) and ch.credits_unknown == 10 and ch.credits_billed == 0
    assert clock.sleeps.count(5) >= 5 and clock.sleeps.count(15) >= 5


def test_server_error_then_success():
    ch, api, _ = make_checker({("ticker", "AAPL"): [L.Resp(500, {}, b"{}"), ok_logo()]})
    ch.run([comp("AAPL", side="us")])
    assert L.result_rows(ch)[0]["status"] == "logo" and ch.counts["retries after an error"] == 1


# ── credits ──

def test_credits_are_counted_two_per_logo_or_no_image_and_none_for_free_answers():
    script = {("ticker", "A"): [ok_logo()], ("ticker", "B"): [ok_logo(cc="0")], ("ticker", "C"): [no_image()],
              ("ticker", "E"): [indexing(), indexing(), indexing()], ("ticker", "F"): [limited(Retry_After="1"),
                                                                                       not_found()]}
    ch, api, _ = make_checker(script)
    ch.run([comp(x, side="us") for x in "ABCDEF"])
    rows = {r["code"]: (r["status"], r["credits"]) for r in L.result_rows(ch)}
    assert rows == {"A": ("logo", 2), "B": ("logo", 2), "C": ("no_image", 2), "D": ("not_found", 0),
                    "E": ("not_indexed", 0), "F": ("not_found", 0)}
    assert ch.credits_counted == 6 and ch.credits_billed == 6               # A, B (counted although free), C
    assert ch.server_charged == 2 and ch.balance_last == "400"


def test_max_credits_stops_before_the_cap_could_be_passed():
    cs = [comp(f"U{i}", side="us") for i in range(6)]
    ch, api, _ = make_checker({("ticker", f"U{i}"): [ok_logo()] for i in range(6)}, max_credits=7)
    ch.run(cs)
    assert ch.stop.outcome == "max_credits" and ch.credits_counted == 6 and len(api.calls) == 3
    assert [r["status"] for r in L.result_rows(ch)] == ["logo"] * 3 + [""] * 3
    # a free answer may be next, but a lookup is never sent when it could pass the cap
    ch2, api2, _ = make_checker({("ticker", "U0"): [ok_logo()]}, max_credits=2)
    ch2.run(cs)
    assert ch2.stop.outcome == "max_credits" and len(api2.calls) == 1
    # the cap is checked before every request: here the next company's first lookup ...
    ch3, api3, _ = make_checker({("ticker", "U0"): [ok_logo()]}, max_credits=3)
    ch3.run([comp("U0", side="us"), comp("005930", domain="samsung.com")])
    assert ch3.stop.outcome == "max_credits" and api3.lookups() == [("ticker", "U0")]
    assert L.result_rows(ch3)[1]["note"] == "not checked: the run stopped first"
    # ... and a 202 retry (a retry that finds the brand indexed is billed)
    ch4, api4, _ = make_checker({("ticker", "U0"): [indexing(), ok_logo()], ("ticker", "U1"): [ok_logo()],
                                 ("ticker", "U2"): [ok_logo()]}, max_credits=5)
    ch4.run([comp("U0", side="us"), comp("U1", side="us"), comp("U2", side="us")])
    assert ch4.stop.outcome == "max_credits" and ch4.credits_counted == 4
    assert api4.lookups() == [("ticker", "U0"), ("ticker", "U1"), ("ticker", "U2")]
    u0 = next(r for r in L.result_rows(ch4) if r["code"] == "U0")
    assert u0["status"] == "" and u0["note"] == "unfinished: ticker not_indexed (retry)"


# ── pacing ──

def test_pacer_one_at_a_time_and_at_most_60_a_minute():
    clock = Clock()
    p = L.Pacer(clock, clock.sleep)
    starts = []
    for i in range(200):
        p.wait()
        starts.append(clock())
        clock.t += 0.2 if i % 3 else 0.0                     # answers take some time, sometimes none
    assert all(b - a >= L.MIN_INTERVAL_S - 1e-9 for a, b in zip(starts, starts[1:]))
    assert max(sum(1 for t in starts if s <= t < s + 60) for s in starts) <= 60
    fast = L.Pacer(clock, clock.sleep, interval=0.0)          # the window alone also holds the line
    st = []
    for _ in range(130):
        fast.wait()
        st.append(clock())
    assert max(sum(1 for t in st if s <= t < s + 60) for s in st) <= 60


def test_every_request_is_paced_lookups_and_downloads_alike(tmp_path):
    ch, api, clock = make_checker({("ticker", f"U{i}"): [ok_logo()] for i in range(8)})
    ch.run([comp(f"U{i}", side="us") for i in range(8)])
    rows = L.result_rows(ch)
    saved, failed = L.save_images(L.pick_images(rows, 5, 1), ch.client, tmp_path, L.Log())
    ts = [c["t"] for c in api.calls]
    assert len(ts) == 13 and all(b - a >= L.MIN_INTERVAL_S - 1e-9 for a, b in zip(ts, ts[1:]))
    assert len(saved) == 5 and not failed


# ── images ──

def test_downloads_carry_no_key_and_go_only_to_logo_dev(tmp_path):
    ch, api, _ = make_checker({("ticker", "AAPL"): [ok_logo(url=IMG_URL + "?size=64")]})
    ch.run([comp("AAPL", side="us")])
    rows = L.result_rows(ch)
    saved, _ = L.save_images(L.pick_images(rows, 3, 1), ch.client, tmp_path, L.Log())
    dl = [c for c in api.calls if not c["url"].startswith(L.API_BASE)]
    assert len(dl) == 1 and dl[0]["headers"] == {} and dl[0]["params"] == {}
    assert dl[0]["url"] == "https://img.logo.dev/assets/SIGNED_TOKEN_abc?size=256&format=png"
    assert (tmp_path / "images" / "US_AAPL.png").read_bytes() == PNG_BYTES and rows[0]["image_file"] == "images/US_AAPL.png"
    assert rows[0]["saved_px"] == "256x256" and saved[0]["px"] == (256, 256)          # read from the file itself
    assert dl[0]["max_bytes"] == L.MAX_IMAGE_BYTES + 1                                  # never read past the limit
    assert api.calls[0]["max_bytes"] == L.MAX_ANSWER_BYTES
    for bad in ("https://evil.example.com/a.png", "http://img.logo.dev/a.png"):
        with pytest.raises(ValueError):
            ch.client.download(bad)


def test_a_download_that_is_not_an_image_is_counted_not_saved(tmp_path):
    clock = Clock()
    api = FakeAPI(clock, {("ticker", "AAPL"): [ok_logo()]}, image=b"<html>nope</html>", image_type="text/html")
    ch = L.Checker(L.Client(FAKE_KEY, api, L.Pacer(clock, clock.sleep)), 480, L.Log(), clock, None, lambda: 0.0)
    ch.run([comp("AAPL", side="us")])
    saved, failed = L.save_images(L.pick_images(L.result_rows(ch), 3, 1), ch.client, tmp_path, L.Log())
    assert not saved and len(failed) == 1 and not list((tmp_path / "images").iterdir())


def test_images_are_spread_over_the_groups():
    assert L.spread(50, {"US": 40, "KR-TOP": 40, "KR-REST": 5}) == {"US": 23, "KR-TOP": 22, "KR-REST": 5}
    assert L.spread(50, {"US": 30, "KR-TOP": 30, "KR-REST": 30}) == {"US": 17, "KR-TOP": 17, "KR-REST": 16}
    assert L.spread(10, {"US": 1, "KR-TOP": 0, "KR-REST": 2}) == {"US": 1, "KR-TOP": 0, "KR-REST": 2}
    rows = [{"group": g, "status": "logo", "rank": i, "code": f"{g}{i}"} for g in ("US", "KR-TOP", "KR-REST")
            for i in range(1, 30)] + [{"group": "US", "status": "not_found", "rank": 99, "code": "X"}]
    a, b = L.pick_images(rows, 12, 5), L.pick_images(rows, 12, 5)
    assert a == b and [r["group"] for r in a].count("KR-REST") == 4 and all(r["status"] == "logo" for r in a)


# ── the summary ──

def test_coverage_math_and_summary_text():
    rows = ([{"group": "US", "status": s, "side": "us"} for s in ("logo", "logo", "not_found")]
            + [{"group": "KR-TOP", "status": s, "side": "kr"} for s in ("logo", "no_image", "not_indexed", "error")]
            + [{"group": "KR-REST", "status": "", "side": "kr"}])
    cov = L.coverage(rows)
    assert cov["US"] == {"sampled": 3, "checked": 3, "counts": {"logo": 2, "not_found": 1, "no_image": 0,
                                                                "not_indexed": 0, "error": 0},
                         "pct": {"logo": 66.7, "not_found": 33.3, "no_image": 0.0, "not_indexed": 0.0, "error": 0.0}}
    assert cov["KR-TOP"]["pct"] == {"logo": 25.0, "not_found": 0.0, "no_image": 25.0, "not_indexed": 25.0,
                                    "error": 25.0}
    assert cov["KR-REST"]["checked"] == 0 and cov["KR-REST"]["pct"]["logo"] is None
    assert cov["ALL"]["sampled"] == 8 and cov["ALL"]["checked"] == 7 and cov["ALL"]["pct"]["logo"] == 42.9
    assert L._cell(cov["US"], "logo") == "2 (66.7%)" and L._cell(cov["KR-REST"], "logo") == "0 (–)"


# ── the whole run (main) ──

def write_inputs(tmp_path, n_kr=14, n_us=8):
    kr = ["005930", "000660", "005380"] + [f"{i:05d}0" for i in range(20001, 20001 + n_kr - 3)]
    us = ["AAPL", "MSFT"] + [f"U{i}" for i in range(n_us - 2)]
    stocks = [{"t": c, "nk": f"한국 회사 {i}", "ne": f"KR {i}", "cls": "kr", "etf": False, "cap": 100.0 - i}
              for i, c in enumerate(kr)]
    stocks += [{"t": c, "nk": f"미국 회사 {i}", "ne": c, "cls": "us", "etf": False, "cap": 50.0 - i}
               for i, c in enumerate(us)]
    stocks += [{"t": "005935", "nk": "우선주", "cls": "kr", "etf": False, "cap": 9.0},
               {"t": "069500", "nk": "KODEX 200", "cls": "kr", "etf": True, "fund": True},
               {"t": "SPY", "nk": "SPY", "cls": "us", "etf": True}]
    (tmp_path / "data.json").write_text(json.dumps({"asOf": "2026-11-05", "pxDate": "2026-11-04",
                                                    "usPxDate": "2026-11-04", "stocks": stocks}, ensure_ascii=False),
                                        encoding="utf-8")
    with open(tmp_path / "listing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Code", "Market"])
        for i, c in enumerate(kr):
            w.writerow([c, "KOSDAQ" if i % 2 else "KOSPI"])
    with open(tmp_path / "homepages.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "corp_cls", "hm_url", "domain", "domain_ok", "domain_note"])
        for i, c in enumerate(kr):
            w.writerow([c, "K" if i % 2 else "Y", f"www.co{c}.co.kr", f"co{c}.co.kr", "1", ""])
    return kr, us


def run_main(tmp_path, extra=(), script=None, environ=None, render=None, kr_top=6, **fake):
    clock = Clock()
    api = FakeAPI(clock, script, **fake)
    env = {"LOGO_DEV_SECRET_KEY": FAKE_KEY, "OTHER": "x"} if environ is None else environ
    deps = L.Deps(send=api, clock=clock, sleep=clock.sleep, wall=lambda: dt.datetime(2026, 11, 5, 21, 0, tzinfo=KST),
                  environ=env, jitter=lambda: 0.0, min_counts={"kr": 1, "us": 1}, kr_top=kr_top,
                  render=render or (lambda saved, meta, folder, log: None))
    out = tmp_path / "out"
    rc = L.main(["--data", str(tmp_path / "data.json"), "--listing", str(tmp_path / "listing.csv"),
                 "--homepages", str(tmp_path / "homepages.csv"), "--out", str(out), "--sample", "12", "--seed", "3",
                 *extra], deps)
    return rc, out, api, env


def all_output_text(out, captured):
    blobs = [captured.out.encode("utf-8"), captured.err.encode("utf-8")]
    blobs += [p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()]
    return blobs


def test_a_whole_run_writes_every_output_and_never_the_key(tmp_path, capsys):
    kr, us = write_inputs(tmp_path, n_us=4)                                 # all four US companies are sampled
    script = {("ticker", f"{c}.KS"): [ok_logo()] for c in kr} | {("ticker", f"{c}.KQ"): [ok_logo()] for c in kr}
    script |= {("ticker", c): [ok_logo()] for c in us}
    script[("ticker", "U1")] = [L.Resp(400, {}, body({"error": {"code": "invalid_request",
                                                                "message": "x" * 150 + f" token {FAKE_KEY} echoed"}}))]
    drawn = {}

    def fake_render(saved, meta, folder, log):
        drawn["n"] = len(saved)
        (folder / "sheet.png").write_bytes(PNG_BYTES)

    rc, out, api, env = run_main(tmp_path, ("--save-images", "6"), script=script, render=fake_render)
    cap = capsys.readouterr()
    assert rc == 0
    assert "LOGO_DEV_SECRET_KEY" not in env and env["OTHER"] == "x"        # removed from the environment after reading
    names = sorted(p.name for p in out.iterdir())
    assert names == ["images", "results.csv", "results.json", "run.json", "run.log", "sheet.html", "sheet.png",
                     "summary.md"]
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert info["outcome"] == "complete" and info["ok"] is True and info["checked"] == 12 and drawn["n"] == 6
    assert info["images"]["saved"] == 6 and info["images"]["png"] is True
    assert sorted(info["images"]["per_group"].values()) == [2, 2, 2]
    sheet = (out / "sheet.html").read_text(encoding="utf-8")
    assert sheet.count("data:image/png;base64,") == 6 and "한국 회사" in sheet and IMG_URL not in sheet
    for f in ("results.csv", "results.json", "run.json", "run.log", "summary.md", "sheet.html"):
        assert "SIGNED_TOKEN" not in (out / f).read_text(encoding="utf-8"), f      # signed addresses are not kept
    for blob in all_output_text(out, cap):                                 # the key: not whole, not in part
        assert FAKE_KEY.encode() not in blob and FAKE_KEY[3:15].encode() not in blob
    assert "***" in (out / "run.log").read_text(encoding="utf-8")          # the echoed key was masked
    for c in api.calls:
        if c["url"].startswith(L.API_BASE):
            assert c["headers"] == {"Authorization": "Bearer " + FAKE_KEY, "Accept": "application/json"}
        else:
            assert c["headers"] == {} and c["url"].startswith("https://img.logo.dev/")
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "Finished: every company in the sample was checked." in summary and "seed **3**" in summary
    for s in L.STATUSES:
        assert f"- **{s}** — " in summary
    assert "Credits counted: **22** of the 480 cap" in summary                # 11 logos, one 400 error
    rows = list(csv.DictReader(open(out / "results.csv", encoding="utf-8")))
    assert len(rows) == 12 and {r["status"] for r in rows} == {"logo", "error"}
    assert L.verdict(out / "run.json") == 0


def test_a_crash_with_the_key_in_its_message_is_masked_everywhere(tmp_path, capsys):
    kr, _ = write_inputs(tmp_path)

    class Weird:
        @property
        def status(self):
            raise RuntimeError(f"broken client said Bearer {FAKE_KEY}")

    rc, out, _, _ = run_main(tmp_path, script={("ticker", "AAPL"): [Weird()], ("ticker", "MSFT"): [Weird()]}
                             | {("ticker", c): [Weird()] for c in ("U0", "U1", "U2", "U3", "U4", "U5")})
    cap = capsys.readouterr()
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 1 and info["outcome"] == "crashed" and info["ok"] is False and "***" in info["reason"]
    assert info["sample"] == 12 and info["checked"] == 0 and info["unfinished"] == 1 and info["not_started"] == 11
    assert len(list(csv.DictReader(open(out / "results.csv", encoding="utf-8")))) == 12    # nobody dropped
    for blob in all_output_text(out, cap):
        assert FAKE_KEY.encode() not in blob and FAKE_KEY[3:15].encode() not in blob


def test_an_unexpected_answer_stops_the_run_and_keeps_the_results_so_far(tmp_path, capsys):
    write_inputs(tmp_path)
    answered = []

    def two_logos_then_a_strange_answer():
        answered.append(1)
        return ok_logo() if len(answered) <= 2 else L.Resp(200, {"Credits-Charged": "1"}, body({"data": {"what": 1}}))

    script = {("ticker", c): [two_logos_then_a_strange_answer] for c in ("AAPL", "MSFT", "U0", "U1", "U2", "U3",
                                                                         "U4", "U5")}
    rc, out, api, _ = run_main(tmp_path, script=script)
    capsys.readouterr()
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 1 and info["outcome"] == "unexpected" and info["ok"] is False
    assert "docs don't describe" in info["reason"] and "data is not a ready logo image" in info["reason"]
    assert info["images"]["saved"] == 0 and not any(                       # no downloads after an error stop
        not c["url"].startswith(L.API_BASE) for c in api.calls)
    rows = list(csv.DictReader(open(out / "results.csv", encoding="utf-8")))
    assert len(rows) == 12 and sum(1 for r in rows if r["status"] == "logo") == 2
    assert sum(1 for r in rows if r["status"]) == info["checked"] and info["checked"] >= 2
    assert "Stopped on an error" in (out / "summary.md").read_text(encoding="utf-8")
    assert L.verdict(out / "run.json") == 1
    again = tmp_path / "again"                                             # the workflow's way: exit 0, then verdict
    again.mkdir()
    write_inputs(again)
    rc2, out2, _, _ = run_main(again, ("--defer-failure",), script=script)
    capsys.readouterr()
    assert rc2 == 0 and L.verdict(out2 / "run.json") == 1


def test_a_sheet_png_problem_makes_the_run_not_ok(tmp_path, capsys):
    write_inputs(tmp_path)
    rc, out, _, _ = run_main(tmp_path, render=lambda *a: "sheet.png not drawn: Pretendard did not draw ['가@400']")
    capsys.readouterr()
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 1 and info["outcome"] == "complete" and info["ok"] is False and info["problems"]
    assert L.verdict(out / "run.json") == 1


def test_found_key_in_an_output_file_is_reported(tmp_path):
    (tmp_path / "a.txt").write_text("nothing here")
    (tmp_path / "b.txt").write_text("x" + FAKE_KEY)
    assert [p.name for p in L.find_key_in_files(tmp_path, FAKE_KEY)] == ["b.txt"]


# ── what the fresh-eyes review found (2026-11-05) ──

def test_only_a_ready_logo_counts_never_a_brandmark():
    j = json.loads(ok_logo().body)
    for kind in ("brandmark", None):
        j["data"]["kind"] = kind
        with pytest.raises(L.Unexpected, match="not a ready logo image"):
            L.classify(L.Resp(200, {"Credits-Charged": "1"}, body(j)))
    with pytest.raises(L.Unexpected, match="whole numbers"):
        L.classify(ok_logo(w=512.5))
    assert L.classify(ok_logo())[1]["image"]["kind"] == "logo"


def test_a_request_without_an_answer_counts_as_possibly_billed_even_when_a_server_error_follows():
    ch, api, _ = make_checker({("ticker", "AAPL"): [ConnectionError("x"), L.Resp(500, {}, b"{}"),
                                                    L.Resp(503, {}, b"{}")]})
    ch.run([comp("AAPL", side="us")])
    assert len(api.calls) == 3 and L.result_rows(ch)[0]["status"] == "error"
    assert ch.credits_unknown == 2 and ch.credits_counted == 2           # counted at once, toward the cap
    ch2, api2, _ = make_checker({("ticker", "AAPL"): [ConnectionError("x"), ok_logo()]}, max_credits=3)
    ch2.run([comp("AAPL", side="us")])                                    # 2 counted for the lost request: the
    assert len(api2.calls) == 1 and ch2.stop.outcome == "max_credits"     # retry could pass a cap of 3, so no retry


def test_a_stop_in_the_middle_of_a_company_keeps_the_request_it_sent():
    ch, api, _ = make_checker({("ticker", "U0"): [broke()]})
    ch.run([comp("U0", side="us"), comp("U1", side="us")])
    rows = L.result_rows(ch)
    assert rows[0]["requests"] == 1 and rows[0]["note"] == "unfinished: ticker stopped (out_of_credits)"
    assert rows[1]["requests"] == 0 and rows[1]["note"] == "not checked: the run stopped first"
    weird = L.Resp(200, {"Credits-Charged": "1"}, body({"data": {"what": 1}}))
    ch2, _, _ = make_checker({("ticker", "U0"): [weird]})
    ch2.run([comp("U0", side="us")])
    r = L.result_rows(ch2)[0]
    assert ch2.stop.outcome == "unexpected" and r["credits"] == 2 and r["requests"] == 1
    assert r["note"] == "unfinished: ticker stopped (Unexpected)"
    ch3, _, _ = make_checker({("domain", "samsung.com"): [broke()]})
    ch3.run([comp("005930", domain="samsung.com")])
    assert L.result_rows(ch3)[0]["note"] == "unfinished: ticker not_found; domain stopped (out_of_credits)"


def test_429_waits_for_the_reset_unless_requests_are_left_in_the_minute():
    zero = lambda: 0.0                                                     # noqa: E731
    assert L.rate_limit_wait({"ratelimit-reset": "45"}, 1, zero) == (45.0, "RateLimit-Reset")
    assert L.rate_limit_wait({"ratelimit-reset": "45", "ratelimit-remaining": "0"}, 1, zero) == (45.0, "RateLimit-Reset")
    assert L.rate_limit_wait({"ratelimit-reset": "45", "ratelimit-remaining": "3"}, 1, zero) == (2.0, "backoff")
    assert L.rate_limit_wait({"retry-after": "9", "ratelimit-reset": "45"}, 1, zero) == (9.0, "Retry-After")


def test_the_korea_top_group_needs_market_caps_and_the_must_have_companies():
    cs = universe(n_kr=1500, n_us=10)
    caps = {"005930": 900.0, "000660": 800.0, "005380": 700.0}
    for c in cs:
        c["cap"] = caps.get(c["code"], c["cap"])
    assert L.check_ranking(cs).startswith("· Korea top 1,000: 005930 rank 1, 000660 rank 2, 005380 rank 3")
    low = [dict(c, cap=0.0001) if c["code"] == "005380" else c for c in cs]
    with pytest.raises(SystemExit, match=r"not in the top 1,000 by market cap: \['005380'\]"):
        L.check_ranking(low)
    blank = [dict(c, cap=None) if i < 30 else c for i, c in enumerate(cs)]
    with pytest.raises(SystemExit, match="30 Korean companies have no market cap"):
        L.check_ranking(blank)


def test_a_run_refuses_a_top_group_without_a_must_have_company(tmp_path, capsys):
    write_inputs(tmp_path)
    data = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    next(s for s in data["stocks"] if s["t"] == "005380")["cap"] = 0.5     # 14th of 14, top group is 6
    (tmp_path / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"not in the top 6 by market cap: \['005380'\]"):
        run_main(tmp_path)
    assert not (tmp_path / "out").exists()                                 # refused before any lookup


def test_the_time_limit_stops_the_lookups_and_keeps_the_results(tmp_path, capsys):
    write_inputs(tmp_path)
    rc, out, api, _ = run_main(tmp_path, ("--time-limit-min", "0.05"))     # 3 seconds of fake time
    capsys.readouterr()
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 1 and info["outcome"] == "time_limit" and info["ok"] is False
    assert 0 < len(api.calls) <= 4 and info["sample"] == 12 and (out / "summary.md").exists()


def test_most_images_failing_makes_the_run_not_ok(tmp_path, capsys):
    write_inputs(tmp_path)
    script = {("ticker", c): [ok_logo()] for c in ("AAPL", "MSFT", "U0", "U1", "U2", "U3", "U4", "U5")}
    rc, out, _, _ = run_main(tmp_path, ("--save-images", "4"), script=script, image=b"<html>", image_type="text/html")
    capsys.readouterr()
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 1 and info["outcome"] == "complete" and info["ok"] is False
    assert info["problems"] == ["4 of 4 chosen logo images could not be downloaded"]
    assert "Not saved (4): " in (out / "summary.md").read_text(encoding="utf-8")


def test_a_key_found_at_the_end_is_said_in_the_summary_too(tmp_path, capsys, monkeypatch):
    write_inputs(tmp_path)
    real, seen = L.find_key_in_files, []

    def finds_it_once(folder, key):
        seen.append(1)
        return [folder / "results.csv"] if len(seen) == 1 else real(folder, key)

    monkeypatch.setattr(L, "find_key_in_files", finds_it_once)
    rc, out, _, _ = run_main(tmp_path)
    capsys.readouterr()
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 1 and info["ok"] is False and not (out / "results.csv").exists()
    assert info["problems"] == ["the key was found in ['results.csv']; those files were deleted"]
    for f in ("summary.md", "run.log"):
        assert "the key was found in ['results.csv']" in (out / f).read_text(encoding="utf-8"), f


def test_an_error_outside_the_lookups_is_printed_masked(tmp_path, capsys, monkeypatch):
    write_inputs(tmp_path)

    def boom(*a, **k):
        raise RuntimeError(f"bad thing near Bearer {FAKE_KEY}")

    monkeypatch.setattr(L, "build_info", boom)
    rc, out, _, _ = run_main(tmp_path)
    cap = capsys.readouterr()
    assert rc == 1 and "RuntimeError: bad thing near Bearer ***" in cap.err
    assert FAKE_KEY not in cap.err + cap.out and FAKE_KEY[3:15] not in cap.err + cap.out


def test_the_data_sources_are_in_the_kept_files(tmp_path, capsys):
    write_inputs(tmp_path)
    rc, out, _, _ = run_main(tmp_path)
    capsys.readouterr()
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert f"- data.json: {tmp_path / 'data.json'} (" in summary and f"- KRX listing: {tmp_path / 'listing.csv'} (" in summary
    assert f"- DART homepages: {tmp_path / 'homepages.csv'} (14 companies)" in summary
    assert f"· KRX listing: {tmp_path / 'listing.csv'}" in (out / "run.log").read_text(encoding="utf-8")
    assert "Limit: logo.dev bills a brand once per 24 hours" in summary


# ── the key: where it may come from ──

def test_refuses_to_run_without_the_key_and_says_so_plainly(tmp_path, capsys):
    write_inputs(tmp_path)
    with pytest.raises(SystemExit, match="LOGO_DEV_SECRET_KEY is not set, so nothing was looked up"):
        run_main(tmp_path, environ={})
    with pytest.raises(SystemExit, match="publishable key"):
        run_main(tmp_path, environ={"LOGO_DEV_SECRET_KEY": "pk_abcdefghijkl"})
    with pytest.raises(SystemExit, match="does not look like") as e:
        run_main(tmp_path, environ={"LOGO_DEV_SECRET_KEY": "sk_short"})
    assert "sk_short" not in str(e.value)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("argv", [["--seed", FAKE_KEY], ["--out", f"/tmp/{FAKE_KEY}"], [f"--data={FAKE_KEY}"],
                                  ["--verdict", FAKE_KEY], [FAKE_KEY]])
def test_refuses_a_key_on_the_command_line_without_showing_it(argv):
    with pytest.raises(SystemExit) as e:
        L.main(argv, L.Deps(environ={"LOGO_DEV_SECRET_KEY": FAKE_KEY}))
    assert "looks like a secret key" in str(e.value) and FAKE_KEY not in str(e.value)


def test_paths_that_merely_contain_sk_are_fine():
    L.refuse_key_in_args(["--out", "/home/user/disk_backup/run1", "--data", "task_sk.json"])


def test_the_key_is_read_only_from_the_environment():
    src = (ROOT / "tools" / "logos" / "logodev_api_check.py").read_text(encoding="utf-8")
    assert src.count("environ.get(KEY_ENV)") == 1 and "read_text" not in src.split("def read_secret_key")[1][:900]
    assert "--key" not in src and "keys-file" not in src


# ── the workflow ──

WF_PATH = ROOT / ".github" / "workflows" / "logo-dev-check.yml"


def test_workflow_is_hand_run_read_only_and_uploads_then_judges():
    raw = WF_PATH.read_text(encoding="utf-8")
    wf = yaml.safe_load(raw)
    on = wf[True]
    assert list(on) == ["workflow_dispatch"]                                # no pull_request, no schedule
    inputs = on["workflow_dispatch"]["inputs"]
    assert {k: v["default"] for k, v in inputs.items()} == {"sample": 300, "seed": 20261105, "max_credits": 480}
    assert wf["permissions"] == {"contents": "read"}
    assert wf["concurrency"] == {"group": "logo-dev-check", "cancel-in-progress": False}
    assert list(wf["jobs"]) == ["check"] and "permissions" not in wf["jobs"]["check"]
    assert_no_hidden_failure(wf)
    for bad in ("git push", "git commit", "pull_request", "schedule", "DART_API_KEY", "ECOS_API_KEY", "HC_PING_URL"):
        assert bad not in raw, bad
    assert set(re.findall(r"secrets\.(\w+)", raw)) == {"LOGO_DEV_SECRET_KEY"}
    st = wf["jobs"]["check"]["steps"]
    with_secret = [s for s in st if "secrets." in json.dumps(s)]
    assert len(with_secret) == 1 and with_secret[0]["env"]["LOGO_DEV_SECRET_KEY"] == "${{ secrets.LOGO_DEV_SECRET_KEY }}"
    run = with_secret[0]["run"]
    assert "tools/logos/logodev_api_check.py" in run and "--defer-failure" in run and "${{" not in run
    assert '--out "$RUNNER_TEMP/logo-dev-check"' in run
    co = st[0]
    assert co["uses"].startswith("actions/checkout") and co["with"]["persist-credentials"] is False
    up = next(s for s in st if s.get("uses", "").startswith("actions/upload-artifact"))
    assert up["with"]["name"] == "logo-dev-check" and up["with"]["retention-days"] == 1
    assert up["with"]["path"] == "${{ runner.temp }}/logo-dev-check" and up["with"]["if-no-files-found"] == "error"
    last = st[-1]["run"]
    assert st.index(with_secret[0]) < st.index(up) < len(st) - 1
    assert 'cat "$RUNNER_TEMP/logo-dev-check/summary.md" >> "$GITHUB_STEP_SUMMARY"' in last
    assert last.strip().splitlines()[-1].strip() == \
        'python tools/logos/logodev_api_check.py --verdict "$RUNNER_TEMP/logo-dev-check/run.json"'
    assert all("if" not in s for s in st)                                  # every step runs, the verdict last
    install = "\n".join(s.get("run") or "" for s in st)
    assert "pip install -r requirements-dev.txt" in install and "playwright install --with-deps chromium" in install
    py = next(s for s in st if s.get("uses", "").startswith("actions/setup-python"))
    assert py["with"]["python-version"] == "3.11"
