# -*- coding: utf-8 -*-
"""v19.1 Part L: the logo coverage test tools (tools/logo_test/). Pure functions only — no network, no browser.

ISIN check digit (against real KRX / US ISINs), the short-code -> ISIN rule and where it must refuse, homepage -> domain
on the messy values of the KRX company list, provider URL formats, key masking and the refusal of a logo.dev secret
key, how a load is classified (hit / miss / placeholder / refusal), the best mix (a preferred share takes its common
share's logo), and build_tickers on a small made-up input. The browser path is covered by `run_test.py --self-test`.
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logo_test"))

import build_tickers  # noqa: E402
import logo_common as lc  # noqa: E402
import run_test  # noqa: E402


# ── ISIN ──

@pytest.mark.parametrize("code,isin", [("005930", "KR7005930003"), ("000660", "KR7000660001"),
                                       ("005380", "KR7005380001"), ("035420", "KR7035420009"),
                                       ("373220", "KR7373220003"), ("069500", "KR7069500007"),
                                       ("0126Z0", "KR70126Z0002")])
def test_kr_isin_from_code_matches_the_krx_listing(code, isin):
    assert lc.kr_isin_from_code(code) == isin
    assert lc.isin_valid(isin)


@pytest.mark.parametrize("isin", ["US0378331005", "KR7005931001", "KR7005382007", "KR700680K019", "KYG5307W1015",
                                  "HK0000307485", "KR8840120008", "USU652221081", "us0378331005"])
def test_real_isins_pass_the_check_digit(isin):
    assert lc.isin_valid(isin)


@pytest.mark.parametrize("isin", ["KR7005930004", "US0378331006", "KR700593000", "KR70059300031", "", None,
                                  "1R7005930003", "KR7-05930003", "KR700593000A"])
def test_wrong_isins_fail(isin):
    assert not lc.isin_valid(isin)


@pytest.mark.parametrize("code", ["005935", "005387", "00680K", "900140", "950160", "AAPL", "12345", "", None])
def test_no_isin_is_derived_where_the_rule_does_not_hold(code):
    """Preferred shares (005935 -> KR7005931001, not KR7005935...) and foreign issuers (9xxxxx) have other ISINs."""
    assert lc.kr_isin_from_code(code) is None


def test_check_digit_rejects_a_bad_body():
    for body in ("KR70059300", "1R700593000", "KR7 0593000", "가R700593000"):
        with pytest.raises(ValueError):
            lc.isin_check_digit(body)


def test_common_code():
    assert lc.common_code("005935") == "005930" and lc.common_code("005387") == "005380"
    assert lc.common_code("00680K") == "006800" and lc.common_code("005930") == "005930"
    assert lc.common_code("AAPL") == "AAPL"


# ── homepage -> domain ──

@pytest.mark.parametrize("raw,domain", [
    ("http://www.samsung.com/sec", "samsung.com"), ("http://https://ks-industry.co.kr/", "ks-industry.co.kr"),
    ("http:///www.nota.ai", "nota.ai"), ("http:// http://www.megamd.co.kr", "megamd.co.kr"), ("RAON.io", "raon.io"),
    ("http://https://www.doosanenerbility.com/kr", "doosanenerbility.com"), ("http://kr.Example.com:8080/x?y", "kr.example.com"),
    ("https://www.hyundai.com", "hyundai.com"), ("http://www,cuckoo.co.kr", ""), ("", ""), (None, ""), ("http://", ""),
    ("localhost", ""), ("http://dsol.co.kr/bbs/board.php?bo_table=pds", "dsol.co.kr"), ("http//www.x-y.co.kr", "x-y.co.kr"),
    ("httpbin.org", "httpbin.org"), ("HTTPS://WWW.LGES.CO.KR/", "lges.co.kr"),
])
def test_homepage_domain(raw, domain):
    assert lc.homepage_domain(raw) == domain


def test_shared_hosts_are_not_company_domains():
    for d in ("blog.naver.com", "shop.cafe24.com", "facebook.com", "sites.google.com", "x.modoo.at", "kind.krx.co.kr"):
        assert lc.is_shared_host(d), d
    for d in ("naver.com", "cafe24.com", "samsung.com", "navercorp.com", "kakaocorp.com"):
        assert not lc.is_shared_host(d), d


# ── provider URLs and keys ──

def test_logo_urls_follow_the_documented_formats():
    k = "KEY"
    assert lc.logo_url("brandfetch", "ticker", "005930.KS", k) == \
        "https://cdn.brandfetch.io/ticker/005930.KS/w/128/h/128/fallback/404?c=KEY"
    assert lc.logo_url("brandfetch", "ticker_code", "005930", k) == \
        "https://cdn.brandfetch.io/ticker/005930/w/128/h/128/fallback/404?c=KEY"
    assert lc.logo_url("brandfetch", "isin", "KR7005930003", k, fallback404=False) == \
        "https://cdn.brandfetch.io/isin/KR7005930003/w/128/h/128?c=KEY"
    assert lc.logo_url("brandfetch", "domain", "samsung.com", k) == \
        "https://cdn.brandfetch.io/domain/samsung.com/w/128/h/128/fallback/404?c=KEY"
    assert lc.logo_url("logodev", "ticker", "247540.KQ", "pk_x") == \
        "https://img.logo.dev/ticker/247540.KQ?token=pk_x&size=128&format=webp&fallback=404"
    assert lc.logo_url("logodev", "isin", "KR7005930003", "pk_x", fallback404=False) == \
        "https://img.logo.dev/isin/KR7005930003?token=pk_x&size=128&format=webp"
    assert lc.logo_url("logodev", "domain", "samsung.com", "pk_x") == \
        "https://img.logo.dev/samsung.com?token=pk_x&size=128&format=webp&fallback=404"
    assert lc.logo_url("logodev", "ticker", "BRK-B", "pk_x").startswith("https://img.logo.dev/ticker/BRK-B?")
    with pytest.raises(KeyError):
        lc.logo_url("logodev", "ticker_code", "005930", "pk_x")


def test_masker_hides_keys_and_their_url_encoded_form():
    m = lc.Masker("pk_abc/123", "bf-client-9", "")
    t = m("a https://img.logo.dev/x?token=pk_abc%2F123 b pk_abc/123 c ?c=bf-client-9 d")
    assert "pk_abc" not in t and "bf-client" not in t and t.count("***") == 3
    assert m("nothing secret") == "nothing secret"


def test_keys_come_from_the_environment_and_a_secret_key_is_refused(monkeypatch):
    monkeypatch.delenv(lc.ENV_BRANDFETCH, raising=False)
    monkeypatch.delenv(lc.ENV_LOGODEV, raising=False)
    keys, missing = lc.read_keys()
    assert keys == {"brandfetch": "", "logodev": ""} and missing == [lc.ENV_BRANDFETCH, lc.ENV_LOGODEV]
    monkeypatch.setenv(lc.ENV_LOGODEV, "sk_secret_value")
    with pytest.raises(SystemExit) as e:
        lc.read_keys()
    assert "sk_secret_value" not in str(e.value) and "publishable" in str(e.value)
    monkeypatch.setenv(lc.ENV_LOGODEV, "pk_ok")
    monkeypatch.setenv(lc.ENV_BRANDFETCH, "bf")
    assert lc.read_keys() == ({"brandfetch": "bf", "logodev": "pk_ok"}, [])


def test_route_identifiers():
    kr = {"code": "005930", "market": "KOSPI", "ticker": "005930.KS", "isin": "KR7005930003", "domain": ""}
    us = {"code": "AAPL", "market": "US", "ticker": "AAPL", "isin": "", "domain": ""}
    assert lc.route_ident(kr, "brandfetch", "ticker") == "005930.KS"
    assert lc.route_ident(kr, "brandfetch", "ticker_code") == "005930"
    assert lc.route_ident(kr, "logodev", "isin") == "KR7005930003"
    assert lc.route_ident(kr, "logodev", "domain") == ""
    assert lc.route_ident(us, "brandfetch", "ticker_code") == "" and lc.route_ident(us, "logodev", "ticker") == "AAPL"


def test_output_folder_is_never_inside_a_git_checkout(tmp_path):
    with pytest.raises(SystemExit):
        lc.out_dir(str(ROOT / "tools" / "logo_test" / "out"))
    with pytest.raises(SystemExit):
        lc.out_dir(str(ROOT))
    other = tmp_path / "other-checkout"
    (other / ".git").mkdir(parents=True)                                    # e.g. the main checkout around a worktree
    with pytest.raises(SystemExit):
        lc.out_dir(str(other / "logos"))
    assert lc.out_dir(str(tmp_path / "scratch" / "logos")).is_dir()


# ── classifying one load ──

OK = {"ok": True, "w": 128, "h": 128}
BAD = {"ok": False, "w": 0, "h": 0}


@pytest.mark.parametrize("provider,status,headers,js,sha,expect", [
    ("logodev", 200, {}, OK, "aa", ("hit", None, False)),
    ("logodev", 200, {}, OK, "fb", ("fallback", None, False)),          # the probed placeholder image
    ("brandfetch", 404, {}, BAD, "", ("miss", None, False)),
    ("logodev", 400, {}, BAD, "", ("bad_request", None, False)),
    ("logodev", 202, {}, OK, "aa", ("pending", run_test.PENDING_WAIT_S, False)),
    ("logodev", 429, {"Retry-After": "7"}, BAD, "", ("rate_limited", 7.0, False)),
    ("brandfetch", 429, {}, BAD, "", ("rate_limited", 30.0, False)),
    ("logodev", 429, {"Retry-After": "86400"}, BAD, "", ("error", None, True)),
    ("brandfetch", 302, {"x-bf-error": "automated_traffic"}, BAD, "", ("error", None, True)),
    ("brandfetch", 302, {"X-BF-Error": "hotlink_blocked"}, BAD, "", ("error", None, True)),
    ("brandfetch", 429, {"x-bf-error": "quota_exceeded"}, BAD, "", ("error", None, True)),
    ("brandfetch", 403, {"x-bf-error": "client_id_invalid_signature"}, BAD, "", ("error", None, True)),
    ("logodev", 401, {}, BAD, "", ("error", None, True)),
    ("logodev", 503, {}, BAD, "", ("error", None, False)),
    ("logodev", None, {}, None, "", ("error", None, False)),
    ("logodev", 200, {}, BAD, "aa", ("error", None, False)),            # 200 but not an image
])
def test_classify(provider, status, headers, js, sha, expect):
    verdict, retry, fatal = run_test.classify(provider, status, headers, js, sha, {"fb"})
    assert (verdict, retry, bool(fatal)) == expect


# ── best mix and summary ──

def _t(code, market, issuer=None, etf="0"):
    return {"code": code, "name": code, "market": market, "etf": etf, "issuer_code": issuer or code,
            "ticker": code + (".KS" if market != "US" else ""), "isin": "", "domain": ""}


def _r(code, p, r, verdict, sha=""):
    return (code, p, r), {"code": code, "provider": p, "route": r, "verdict": verdict, "ident": code, "sha256": sha}


def test_best_mix_order_and_preferred_share_takes_its_common_share():
    tickers = [_t("005930", "KOSPI"), _t("005935", "KOSPI", "005930"), _t("AAPL", "US"), _t("MSFT", "US")]
    latest = dict([_r("005930", "brandfetch", "ticker", "miss"), _r("005930", "logodev", "isin", "hit"),
                   _r("005930", "brandfetch", "isin", "hit"), _r("005935", "brandfetch", "ticker", "miss"),
                   _r("AAPL", "logodev", "ticker", "hit"), _r("AAPL", "brandfetch", "ticker", "hit"),
                   _r("MSFT", "brandfetch", "ticker", "fallback")])
    mix = {m["code"]: m for m in lc.choose_mix(tickers, latest)}
    assert mix["005930"]["pick"] == "brandfetch:isin" and mix["005930"]["via_code"] == ""
    assert mix["005935"]["pick"] == "brandfetch:isin" and mix["005935"]["via_code"] == "005930"
    assert mix["AAPL"]["pick"] == "brandfetch:ticker" and mix["MSFT"]["pick"] == ""
    md, rows = lc.summarize(tickers, latest)
    assert "| **best mix** | 2 / 2 (100.0%) | – | – | 1 / 2 (50.0%) | – |" in md, md
    assert "| brandfetch:ticker | 0 / 2 (0.0%) | – | – | 2 / 2 (100.0%) | – |" not in md       # fallback is no hit
    assert "| brandfetch:ticker | 0 / 2 (0.0%) | – | – | 1 / 2 (50.0%) | – |" in md, md
    assert "| common share | 1 | 0 | 0 | 0 | 0 |" in md, md


def test_same_image_for_several_companies_is_listed():
    tickers = [_t(c, "KOSPI") for c in ("000001", "000002", "000003")] + [_t("000005", "KOSPI", "000001")]
    latest = dict([_r(c, "logodev", "domain", "hit", "same") for c in ("000001", "000002", "000003", "000005")])
    shared = lc.shared_image_hashes(tickers, latest, min_companies=3)
    assert len(shared) == 1 and shared[0][0] == ("logodev:domain", "same") and len(shared[0][1]) == 3


# ── build_tickers on made-up input ──

def test_build_tickers_rows():
    data = {"stocks": [
        {"t": "005930", "nk": "삼성전자", "ne": "Samsung", "cls": "kr", "cap": 1283.2, "etf": False},
        {"t": "005935", "nk": "삼성전자우", "cls": "kr", "cap": 100.0, "etf": False},
        {"t": "247540", "nk": "에코프로비엠", "cls": "kr", "cap": 20.0, "etf": False},
        {"t": "069500", "nk": "KODEX 200", "cls": "kr", "cap": 15.0, "etf": True},
        {"t": "111110", "nk": "가", "cls": "kr", "cap": 1.0, "etf": False},
        {"t": "222220", "nk": "나", "cls": "kr", "cap": 2.0, "etf": False},
        {"t": "333330", "nk": "다", "cls": "kr", "cap": None, "etf": False},
        {"t": "AAPL", "nk": "Apple Inc.", "ne": "Apple Inc.", "cls": "us", "cap": float("nan"), "etf": False},
        {"t": "TLT", "nk": "bond", "cls": "bond", "cap": 1.0, "etf": True},
    ]}
    listing = {"005930": {"Market": "KOSPI", "ISU_CD": "KR7005930003"},
               "005935": {"Market": "KOSPI", "ISU_CD": "KR7005931001"},
               "247540": {"Market": "KOSDAQ GLOBAL", "ISU_CD": "KR7247540008"},
               "111110": {"Market": "KONEX", "ISU_CD": "KR7111110009"},       # wrong check digit on purpose
               "222220": {"Market": "KOSDAQ", "ISU_CD": "KR7222220006"},
               "333330": {"Market": "KOSDAQ", "ISU_CD": ""}}
    desc = {"005930": {"HomePage": "http://www.samsung.com/sec"}, "005935": {"HomePage": ""},
            "247540": {"HomePage": "http://blog.naver.com/x"}, "111110": {"HomePage": "http://www.group.co.kr"},
            "222220": {"HomePage": "group.co.kr/sub"}}
    rows, log = build_tickers.build(data, listing, desc)
    by = {r["code"]: r for r in rows}
    assert set(by) == {"005930", "005935", "247540", "069500", "111110", "222220", "333330", "AAPL"}      # no bond
    assert by["005930"]["ticker"] == "005930.KS" and by["005930"]["isin_src"] == "krx_listing"
    assert by["005930"]["domain"] == "samsung.com" and by["005935"]["domain"] == "samsung.com"
    assert by["005935"]["domain_src"] == "krx_desc (common share)" and by["005935"]["issuer_code"] == "005930"
    assert by["247540"]["market"] == "KOSDAQ" and by["247540"]["ticker"] == "247540.KQ"
    assert by["247540"]["domain"] == ""                                    # blog.naver.com is someone else's logo
    assert by["069500"]["market"] == "KOSPI" and by["069500"]["isin"] == "KR7069500007"
    assert by["069500"]["isin_src"] == "derived" and by["069500"]["etf"] == "1"
    assert by["111110"]["isin"] == "" and any("111110" in x and "check digit" in x for x in log)
    assert by["111110"]["ticker"] == "111110.KS" and by["111110"]["market"] == "KONEX"
    assert by["111110"]["domain"] == "" and by["222220"]["domain"] == ""      # one domain, two companies
    assert by["AAPL"]["market"] == "US" and by["AAPL"]["ticker"] == "AAPL" and by["AAPL"]["isin"] == ""
    assert by["AAPL"]["rank"] == "" and by["333330"]["rank"] == ""          # blank or NaN cap is never ranked
    assert [by[c]["rank"] for c in ("005930", "005935", "247540", "069500", "222220", "111110")] == [1, 2, 3, 4, 5, 6]
    top = lc.top_companies(rows, 4, "kr")
    assert [r["code"] for r in top] == ["005930", "005935", "247540", "222220"]       # the ETF is not a company
    assert lc.top_companies(rows, 5, "us") == []                             # AAPL's cap was NaN: not ranked
    assert [r["code"] for r in lc.top_companies(rows, 2)] == ["005930", "005935"]


def test_resume_ignores_results_for_an_identifier_that_changed():
    t = {"code": "005930", "market": "KOSPI", "ticker": "005930.KS", "isin": "KR7005930003", "domain": "samsung.com"}
    rows = [{"code": "005930", "provider": "logodev", "route": "domain", "ident": "old-domain.com", "verdict": "hit"},
            {"code": "005930", "provider": "logodev", "route": "isin", "ident": "KR7005930003", "verdict": "miss"},
            {"code": "005930", "provider": "brandfetch", "route": "isin", "ident": "KR7005930003", "verdict": "hit"},
            {"code": "999990", "provider": "logodev", "route": "isin", "ident": "X", "verdict": "hit"}]
    latest = lc.current_latest([t], rows, {"logodev:domain", "logodev:isin"})
    assert set(latest) == {("005930", "logodev", "isin")}                   # old domain, other route, other ticker: out
    items, skipped = run_test.plan_items([t], {"logodev:domain", "logodev:isin"}, latest)
    assert skipped == 1 and [(i["route"], i["ident"]) for i in items["logodev"]] == [("domain", "samsung.com")]


def test_unfinished_loads_are_counted():
    t = {"code": "005930", "market": "KOSPI", "ticker": "005930.KS", "isin": "KR7005930003", "domain": ""}
    latest = dict([_r("005930", "logodev", "ticker", "error"), _r("005930", "logodev", "isin", "hit")])
    c = run_test.unfinished_counts([t], latest, {"logodev:ticker", "logodev:isin", "brandfetch:ticker"})
    assert c == {"logodev": {"error": 1}, "brandfetch": {"not tried": 1}}


def test_status_of_a_load_with_redirects():
    assert run_test.resolve_status(None) == (None, {}, None)
    ok = {"status": 200, "headers": {"Content-Type": "image/webp"}, "last": (200, {})}
    assert run_test.resolve_status(ok) == (200, {"content-type": "image/webp"}, None)
    refused = {"status": 302, "headers": {"X-BF-Error": "automated_traffic"}, "last": (200, {"content-type": "text/html"})}
    assert run_test.resolve_status(refused)[:2] == (302, {"x-bf-error": "automated_traffic"})   # judged on the 1st hop
    moved = {"status": 301, "headers": {"location": "/x.png"}, "last": (200, {"content-type": "image/png"})}
    assert run_test.resolve_status(moved) == (200, {"content-type": "image/png"}, 301)          # followed


class _FakeCdp:
    def __init__(self):
        self.h = {}

    def on(self, name, fn):
        self.h[name] = fn

    def emit(self, name, ev):
        self.h[name](ev)


def test_capture_keeps_a_raw_header_event_that_arrives_first():
    """Chromium may send responseReceivedExtraInfo before requestWillBeSent. For an ORB-blocked refusal (a JSON 401)
    it is the only event with the status, so it must not be dropped."""
    cdp = _FakeCdp()
    cap = run_test.NetCapture(cdp)
    cdp.emit("Network.responseReceivedExtraInfo", {"requestId": "1", "statusCode": 401, "headers": {"a": "b"}})
    cdp.emit("Network.requestWillBeSent", {"requestId": "1", "request": {"url": "https://x/1", "headers": {
        "Referer": "http://127.0.0.1:5/"}}})
    cdp.emit("Network.loadingFailed", {"requestId": "1", "blockedReason": "orb"})
    rec = cap.req["1"]
    assert rec["status"] == 401 and rec["done"] and rec["failure"] == "orb" and rec["referer"] == "http://127.0.0.1:5/"
    cdp.emit("Network.requestWillBeSent", {"requestId": "2", "request": {"url": "https://x/2", "headers": {}}})
    cdp.emit("Network.requestWillBeSent", {"requestId": "2", "request": {"url": "https://x/guide", "headers": {}},
                                           "redirectResponse": {"status": 302, "headers": {"x-bf-error": "hotlink_blocked"}}})
    cdp.emit("Network.responseReceived", {"requestId": "2", "response": {"status": 200, "headers": {}, "mimeType": "text/html"}})
    rec = cap.req["2"]
    assert rec["status"] == 302 and rec["headers"]["x-bf-error"] == "hotlink_blocked" and rec["last"][0] == 200
    assert cap.by_url == {"https://x/1": "1", "https://x/2": "2"}


def test_tools_never_read_a_dart_key():
    for f in ("logo_common.py", "build_tickers.py", "run_test.py", "contact_sheet.py", "selftest_fake.py"):
        text = (ROOT / "tools" / "logo_test" / f).read_text(encoding="utf-8")
        assert "DART_API_KEY" not in text and "opendart" not in text, f
    assert os.path.exists(ROOT / "tools" / "logo_test" / "README.md")
    assert os.path.exists(ROOT / "tools" / "logo_test" / "KEYS.md")
