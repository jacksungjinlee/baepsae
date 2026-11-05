# -*- coding: utf-8 -*-
"""Logo plan step 4 (tools/logos/site_icons.py): icons from each company's own DART homepage.

No network: every request goes to a fake web (FakeWeb) and a guard makes any real socket connection fail the test.
Covered: robots.txt (RFC 9309 groups, longest match, wildcards, status codes), what is requested and what never is
(logo providers, URLs robots.txt disallows), politeness (6 requests per company with robots.txt, redirects and retries
counted, one retry on a network error, none on 4xx or TLS, one request at a time per host, at most 6 at once, the
gap between requests), HTML and manifest icon parsing and the order candidates are tried in, ICO frame choice, the
96 px rule, SVG through an injected renderer, generic detection (a) shared image (b) builder / platform / parked
(c) blank, the 128 px normalisation geometry, the decisions and the files written.
"""
import collections
import io
import json
import pathlib
import socket
import sys
import threading
import time

import pytest
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))

import site_icons as si  # noqa: E402

UA = "BaepsaeLogoCollector/1.0 (+https://jacksungjinlee.github.io/baepsae/)"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a test tried to open a real network connection")
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


# ── fixtures ───────────────────────────────────────────────────────────────────────────────────────────────────────

def logo(w=180, h=180, colour=(20, 60, 160), mark=(250, 190, 40), alpha_bg=False, seed=0):
    """A small picture with real content: a coloured square with a mark (different seed -> different mark)."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0) if alpha_bg else (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([w // 8, h // 8, w - w // 8, h - h // 8], fill=colour + (255,))
    k = 3 + seed % 5
    d.ellipse([w // k, h // 3, w - w // k, h - h // 4], fill=mark + (255,))
    d.rectangle([w // 2 - w // 12, h // 6 + seed * 2, w // 2 + w // 12, h // 2], fill=(255, 255, 255, 255))
    return im


def png(im):
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def ico(sizes):
    b = io.BytesIO()
    logo(256, 256).save(b, "ICO", sizes=sizes)
    return b.getvalue()


def html_page(head, title="Company"):
    return f"<!doctype html><html><head><title>{title}</title>{head}</head><body>hello</body></html>".encode()


class FakeWeb:
    """routes: url -> (status, headers, body) · an Exception (raised) · a list of those (one per call, last repeats).
    Unknown URLs answer 404. Records every call with its headers, thread and time."""

    def __init__(self, routes=None, delay=0.0):
        self.routes, self.delay = dict(routes or {}), delay
        self.calls, self.lock = [], threading.Lock()
        self.active, self.active_hosts, self.max_active, self.overlap = 0, collections.Counter(), 0, []

    def __call__(self, session, url, headers, max_bytes, stop_early=None):
        host = url.split("/")[2]
        with self.lock:
            self.calls.append({"url": url, "headers": dict(headers)})
            self.active += 1
            self.active_hosts[host] += 1
            self.max_active = max(self.max_active, self.active)
            if self.active_hosts[host] > 1:
                self.overlap.append(host)
            v = self.routes.get(url, (404, {}, b"not found"))
            if isinstance(v, list):
                v = v.pop(0) if len(v) > 1 else v[0]
        try:
            if self.delay:
                time.sleep(self.delay)
            if isinstance(v, Exception):
                raise v
            status, hdrs, body = v
            return si.Resp(status, hdrs, body[:max_bytes], url, len(body) > max_bytes)
        finally:
            with self.lock:
                self.active -= 1
                self.active_hosts[host] -= 1

    def urls(self):
        return [c["url"] for c in self.calls]


def shared(web):
    return si.Shared(web, si.HostGate(gap=0))


def collect(routes, domain="acme.co.kr", hm="www.acme.co.kr", tmp=None, svg=None, web=None):
    web = web or FakeWeb(routes)
    rec = si.collect_domain({"domain": domain, "hm_url": hm, "codes": ["123450"]}, shared(web), svg,
                            pathlib.Path(tmp) if tmp else None)
    return rec, web


OK_ROBOTS = (200, {"content-type": "text/plain"}, b"User-agent: *\nDisallow: /admin\n")
HTML = {"content-type": "text/html; charset=utf-8"}
PNGH = {"content-type": "image/png"}


# ── the fixed rules ────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_rules_jack_set_are_the_constants():
    assert si.UA == UA and "@" not in si.UA
    assert si.UA_TOKEN == "BaepsaeLogoCollector"
    assert si.TIMEOUT_S == 15 and si.MAX_REQUESTS == 6 and si.MAX_WORKERS == 6
    assert si.MIN_SIDE == 96 and si.OUT_SIDE == 128 and si.SVG_SIDE == 256 and si.SHARED_MIN == 3


# ── robots.txt ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_robots_our_own_group_wins_over_star_and_groups_combine():
    txt = """# comment
User-agent: *
Disallow: /

User-agent: Googlebot
User-agent: baepsaelogocollector/2.0
Disallow: /private
Crawl-delay: 4

User-agent: BaepsaeLogoCollector
Allow: /private/logo.png
"""
    rules, delay = si.select_group(si.parse_robots(txt))
    assert sorted(rules) == [(False, "/private"), (True, "/private/logo.png")] and delay == 4
    assert si.rules_allow(rules, "/") and si.rules_allow(rules, "/favicon.ico")
    assert not si.rules_allow(rules, "/private/x") and si.rules_allow(rules, "/private/logo.png")


def test_robots_star_group_applies_when_no_group_names_us():
    rb = si.Robots.from_answer(200, "User-agent: Googlebot\nDisallow:\n\nUser-agent: *\nDisallow: /\n")
    assert not rb.allows("/") and not rb.allows("/favicon.ico")
    assert rb.allows("/robots.txt")                         # robots.txt itself is always allowed


def test_robots_longest_match_wins_and_allow_wins_a_tie():
    rules, _ = si.select_group(si.parse_robots(
        "User-agent: *\nDisallow: /img\nAllow: /img/logo\nDisallow: /a\nAllow: /a\n"))
    assert not si.rules_allow(rules, "/img/x.png") and si.rules_allow(rules, "/img/logo.png")
    assert si.rules_allow(rules, "/a/b")                     # same length: allow


def test_robots_wildcards_end_anchor_and_query():
    rules, _ = si.select_group(si.parse_robots("User-agent: *\nDisallow: /*.ico$\nDisallow: /*?session=\n"))
    assert not si.rules_allow(rules, "/favicon.ico") and si.rules_allow(rules, "/favicon.ico.png")
    assert not si.rules_allow(rules, "/index.do?session=1") and si.rules_allow(rules, "/index.do")


def test_robots_empty_disallow_comments_and_an_html_page_mean_no_rules():
    assert si.Robots.from_answer(200, "User-agent: *\nDisallow:\n").allows("/")
    assert si.Robots.from_answer(200, "<html><head><title>Not found</title></head></html>").allows("/x")
    assert si.Robots.from_answer(200, "﻿User-agent: * # all\nDisallow: / # nothing\n").allows("/") is False


@pytest.mark.parametrize("status,allowed", [(404, True), (410, True), (401, True), (403, True), (301, True),
                                            (500, False), (503, False), (429, False)])
def test_robots_status_codes_follow_rfc_9309(status, allowed):
    assert si.Robots.from_answer(status, "").allows("/") is allowed


def test_crawl_delay_is_honoured_up_to_10_seconds():
    g = si.HostGate(gap=1.0, clock=lambda: 0.0, sleep=lambda s: None)
    g.set_delay("a.com", 3)
    g.set_delay("b.com", 3600)
    assert g.delay == {"a.com": 3.0, "b.com": 10.0}


# ── what is requested, and what never is ───────────────────────────────────────────────────────────────────────────

def test_a_normal_site_requests_robots_then_the_homepage_then_the_preferred_icon_only(tmp_path):
    head = ('<link rel="icon" href="/favicon.ico"><link rel="apple-touch-icon" sizes="180x180" '
            'href="/img/apple.png"><link rel="manifest" href="/site.webmanifest">')
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page(head)),
                        "https://www.acme.co.kr/img/apple.png": (200, PNGH, png(logo()))}, tmp=tmp_path)
    assert web.urls() == ["https://www.acme.co.kr/robots.txt", "https://www.acme.co.kr/",
                          "https://www.acme.co.kr/img/apple.png"]
    assert all(c["headers"]["User-Agent"] == UA for c in web.calls)
    assert rec["outcome"] == "icon" and rec["requests"] == 3
    ch = rec["candidates"][rec["chosen"]]
    assert ch["kind"] == "apple-touch-icon" and ch["original_size"] == "180x180"
    assert (tmp_path / f"{ch['sha256']}.png").exists() and (tmp_path / f"{ch['sha256']}.orig").exists()


def test_only_the_homepage_its_icons_its_manifest_and_the_three_fixed_paths_are_ever_requested(tmp_path):
    head = ('<base href="https://www.acme.co.kr/kor/"><link rel="shortcut icon" href="img/fav.ico">'
            '<link rel="manifest" href="/m.json"><link rel="stylesheet" href="/x.css">'
            '<link rel="mask-icon" href="/pin.svg"><a href="/about">about</a>')
    manifest = json.dumps({"icons": [{"src": "/i/192.png", "sizes": "192x192"}]}).encode()
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page(head)),
                        "https://www.acme.co.kr/m.json": (200, {"content-type": "application/json"}, manifest),
                        "https://www.acme.co.kr/i/192.png": (200, PNGH, png(logo(48, 48)))}, tmp=tmp_path)
    allowed = {"https://www.acme.co.kr/robots.txt", "https://www.acme.co.kr/", "https://www.acme.co.kr/m.json",
               "https://www.acme.co.kr/i/192.png", "https://www.acme.co.kr/kor/img/fav.ico",
               "https://www.acme.co.kr/apple-touch-icon.png", "https://www.acme.co.kr/favicon.ico",
               "https://www.acme.co.kr/apple-touch-icon-precomposed.png"}
    assert set(web.urls()) <= allowed, set(web.urls()) - allowed
    assert not any(u.endswith(("/x.css", "/pin.svg", "/about")) for u in web.urls())
    assert len(web.urls()) <= si.MAX_REQUESTS


@pytest.mark.parametrize("url", ["https://cdn.brandfetch.io/domain/acme.co.kr", "https://img.logo.dev/acme.co.kr",
                                 "https://logo.clearbit.com/acme.co.kr", "https://www.google.com/s2/favicons?d=x",
                                 "https://t1.gstatic.com/faviconV2?url=x", "https://icons.duckduckgo.com/ip3/x.ico",
                                 "ftp://acme.co.kr/x.png", "javascript:alert(1)"])
def test_logo_providers_and_odd_schemes_are_never_fetched(url):
    assert si.never_fetch(url)


def test_a_page_pointing_at_a_logo_provider_never_reaches_the_transport(tmp_path):
    head = ('<link rel="apple-touch-icon" href="https://cdn.brandfetch.io/domain/acme.co.kr/w/400">'
            '<link rel="icon" sizes="192x192" href="https://img.logo.dev/acme.co.kr?token=pk_x">')
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page(head)),
                        "https://www.acme.co.kr/apple-touch-icon.png": (200, PNGH, png(logo()))}, tmp=tmp_path)
    assert not any("brandfetch" in u or "logo.dev" in u for u in web.urls())
    assert [c["result"] for c in rec["candidates"][:2]] == ["refused", "refused"]
    assert rec["candidates"][rec["chosen"]]["kind"] == "fallback-apple-touch-icon"


def test_a_redirect_to_a_logo_provider_is_refused():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (302, {"location": "https://img.logo.dev/acme.co.kr"}, b"")})
    assert rec["outcome"] == "unreachable" and "logo provider" in rec["reason"]
    assert web.urls() == ["https://www.acme.co.kr/robots.txt", "https://www.acme.co.kr/"]


def test_robots_disallowing_root_skips_the_host_after_one_request():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": (200, {}, b"User-agent: *\nDisallow: /\n")})
    assert rec["outcome"] == "robots_blocked" and web.urls() == ["https://www.acme.co.kr/robots.txt"]


def test_robots_on_the_host_a_homepage_redirects_to_is_read_and_respected():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (301, {"location": "https://corp.acme.com/ko/"}, b""),
                        "https://corp.acme.com/robots.txt": (200, {}, b"User-agent: BaepsaeLogoCollector\nDisallow: /\n")})
    assert rec["outcome"] == "robots_blocked"
    assert web.urls() == ["https://www.acme.co.kr/robots.txt", "https://www.acme.co.kr/",
                          "https://corp.acme.com/robots.txt"]


def test_an_icon_path_robots_disallows_is_not_requested(tmp_path):
    head = '<link rel="apple-touch-icon" href="/private/apple.png">'
    rec, web = collect({"https://www.acme.co.kr/robots.txt": (200, {}, b"User-agent: *\nDisallow: /private/\n"),
                        "https://www.acme.co.kr/": (200, HTML, html_page(head)),
                        "https://www.acme.co.kr/private/apple.png": (200, PNGH, png(logo()))}, tmp=tmp_path)
    assert "https://www.acme.co.kr/private/apple.png" not in web.urls()
    assert rec["candidates"][0]["result"] == "robots"


def test_a_robots_redirect_is_followed_and_kept_for_the_host_it_lands_on():
    web = FakeWeb({"https://acme.co.kr/robots.txt": (301, {"location": "https://www.acme.co.kr/robots.txt"}, b""),
                   "https://www.acme.co.kr/robots.txt": (404, {}, b""),
                   "https://acme.co.kr/": (301, {"location": "https://www.acme.co.kr/"}, b""),
                   "https://www.acme.co.kr/": (200, HTML, html_page(""))})
    collect(None, hm="acme.co.kr", web=web)
    assert web.urls()[:4] == ["https://acme.co.kr/robots.txt", "https://www.acme.co.kr/robots.txt",
                              "https://acme.co.kr/", "https://www.acme.co.kr/"]   # no second robots.txt for www


def test_a_default_port_is_the_same_host_for_robots_and_the_gate():
    assert si.host_key("https://WWW.Acme.co.kr:443/x") == si.host_key("https://www.acme.co.kr/") == "www.acme.co.kr"
    assert si.host_key("http://acme.co.kr:80/") == "acme.co.kr" and si.host_key("https://acme.co.kr:8443/") == \
        "acme.co.kr:8443"
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page(
                            '<link rel="apple-touch-icon" href="https://www.acme.co.kr:443/a.png">'))})
    assert web.urls().count("https://www.acme.co.kr/robots.txt") == 1
    assert "https://www.acme.co.kr:443/robots.txt" not in web.urls()


# ── politeness: budget, retries, TLS, proxy, http fallback, per-host and overall limits ─────────────────────────────

def test_at_most_six_requests_per_company_with_robots_redirects_and_retries_counted():
    routes = {"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
              "https://www.acme.co.kr/": (302, {"location": "/a"}, b""),
              "https://www.acme.co.kr/a": (302, {"location": "/b"}, b""),
              "https://www.acme.co.kr/b": (200, HTML, html_page('<link rel="icon" href="/1.png">'
                                                                '<link rel="icon" href="/2.png">'
                                                                '<link rel="icon" href="/3.png">'))}
    rec, web = collect(routes)
    assert len(web.calls) == si.MAX_REQUESTS == rec["requests"]
    assert rec["outcome"] == "budget"


def test_one_retry_on_a_network_error_then_it_works():
    err = si.NetError("Connection reset by peer")
    rec, web = collect({"https://www.acme.co.kr/robots.txt": [err, OK_ROBOTS],
                        "https://www.acme.co.kr/": (200, HTML, html_page(""))})
    assert web.urls()[:3] == ["https://www.acme.co.kr/robots.txt"] * 2 + ["https://www.acme.co.kr/"]
    assert rec["page_status"] == 200


def test_no_retry_on_4xx_or_5xx_answers():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (403, HTML, b"forbidden")})
    assert web.urls() == ["https://www.acme.co.kr/robots.txt", "https://www.acme.co.kr/"]
    assert rec["outcome"] == "unreachable" and "403" in rec["reason"]
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (503, HTML, b"busy")})
    assert len(web.calls) == 2 and rec["outcome"] == "unreachable"


def test_a_tls_error_is_tried_once_counted_as_unreachable_and_never_downgraded_to_http():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": si.TlsError("CERTIFICATE_VERIFY_FAILED")})
    assert web.urls() == ["https://www.acme.co.kr/robots.txt"]
    assert rec["outcome"] == "tls"


def test_https_that_cannot_connect_is_retried_once_then_http_is_used():
    err = si.NetError("Connection refused")
    rec, web = collect({"https://www.acme.co.kr/robots.txt": err,
                        "http://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "http://www.acme.co.kr/": (200, HTML, html_page(""))})
    assert web.urls()[:4] == ["https://www.acme.co.kr/robots.txt"] * 2 + ["http://www.acme.co.kr/robots.txt",
                                                                          "http://www.acme.co.kr/"]
    assert rec["page_url"] == "http://www.acme.co.kr/"


def test_an_explicit_scheme_is_used_as_it_is():
    rec, web = collect({"http://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "http://www.acme.co.kr/": (200, HTML, html_page(""))}, hm="http://www.acme.co.kr")
    assert web.urls()[0] == "http://www.acme.co.kr/robots.txt"


def test_a_proxy_refusal_is_counted_as_such_and_not_retried():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": si.ProxyBlocked("proxy answered 403")})
    assert rec["outcome"] == "proxy_blocked" and len(web.calls) == 1
    assert "proxy_blocked" in si.RETRYABLE and "error" in si.RETRYABLE


def test_a_busy_proxy_is_waited_for_once_and_never_answered_with_plain_http():
    web = FakeWeb({"https://www.acme.co.kr/robots.txt": si.ProxyBusy("proxy answered 503 (busy)")})
    slept = []
    sh = si.Shared(web, si.HostGate(gap=0, sleep=slept.append))
    rec = si.collect_domain({"domain": "acme.co.kr", "hm_url": "www.acme.co.kr", "codes": ["123450"]}, sh)
    assert web.urls() == ["https://www.acme.co.kr/robots.txt"] * 2 and slept == [si.PROXY_BUSY_PAUSE_S]
    assert rec["outcome"] == "unreachable" and "busy" in rec["reason"] and sh.proxy_busy == 2


def test_a_homepage_that_moved_to_a_refused_platform_is_a_platform_not_unreachable():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (302, {"location": "https://sites.google.com/view/acme"}, b"")})
    assert rec["outcome"] == "platform" and not any("google" in u for u in web.urls())


def test_a_malformed_redirect_or_a_tool_error_never_stops_the_run(tmp_path, monkeypatch):
    rec, _ = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                      "https://www.acme.co.kr/": (302, {"location": "http://[bad"}, b"")})
    assert rec["outcome"] == "unreachable" and "malformed redirect" in rec["reason"]

    def boom(*a, **k):
        raise RuntimeError("decoder exploded")
    monkeypatch.setattr(si, "judge_candidate", boom)
    rec, _ = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                      "https://www.acme.co.kr/": (200, HTML, html_page('<link rel="apple-touch-icon" href="/a.png">')),
                      "https://www.acme.co.kr/a.png": (200, PNGH, png(logo()))}, tmp=tmp_path)
    assert rec["outcome"] == "error" and "RuntimeError" in rec["reason"] and rec["chosen"] is None


def test_one_request_at_a_time_per_host_and_at_most_six_at_once():
    routes = {}
    items = []
    for i in range(10):
        h = f"www.c{i}.co.kr"
        routes[f"https://{h}/robots.txt"] = OK_ROBOTS
        routes[f"https://{h}/"] = (200, HTML, html_page('<link rel="icon" href="https://cdn.shared.com/x.png">'))
        items.append({"domain": f"c{i}.co.kr", "hm_url": h, "codes": [f"{i:05d}0"]})
    routes["https://cdn.shared.com/robots.txt"] = OK_ROBOTS
    web = FakeWeb(routes, delay=0.01)
    sh = si.Shared(web, si.HostGate(gap=0, parallel=6))
    threads = [threading.Thread(target=si.collect_domain, args=(it, sh)) for it in items]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not web.overlap, web.overlap                     # cdn.shared.com was never asked twice at once
    assert 1 < web.max_active <= 6
    assert web.urls().count("https://cdn.shared.com/robots.txt") == 1


def test_the_gate_waits_the_gap_between_two_requests_to_one_host():
    now = [100.0]
    slept = []
    g = si.HostGate(gap=1.0, clock=lambda: now[0], sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)))
    with g.slot("a.com"):
        pass
    now[0] += 0.25
    with g.slot("a.com"):
        pass
    with g.slot("b.com"):
        pass
    assert slept == [pytest.approx(0.75)]


def test_a_host_answering_fixed_paths_with_a_web_page_is_not_asked_for_the_other_paths(tmp_path):
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page("")),
                        "https://www.acme.co.kr/apple-touch-icon.png": (200, HTML, html_page("", "Not found"))},
                       tmp=tmp_path)
    assert web.urls() == ["https://www.acme.co.kr/robots.txt", "https://www.acme.co.kr/",
                          "https://www.acme.co.kr/apple-touch-icon.png"]
    assert [c["result"] for c in rec["candidates"]] == ["not_image", "skipped", "skipped"]


def test_a_fixed_path_redirecting_to_an_error_page_is_not_followed(tmp_path):
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page("")),
                        "https://www.acme.co.kr/apple-touch-icon.png": (302, {"location": "http://errdoc.host.io/404.html"},
                                                                        b"")}, tmp=tmp_path)
    assert not any("errdoc" in u for u in web.urls())
    assert [c["result"] for c in rec["candidates"]] == ["not_image", "skipped", "skipped"]
    assert si.fallback_follow("http://a.kr/favicon.ico", "https://www.a.kr/favicon.ico")
    assert si.fallback_follow("https://a.kr/apple-touch-icon.png", "https://cdn.a.kr/img/touch-180.png")
    assert not si.fallback_follow("https://a.kr/favicon.ico", "https://a.kr/error/404.html")
    assert not si.fallback_follow("https://a.kr/favicon.ico", "https://a.kr/")


def test_favicon_ico_is_skipped_when_the_declared_icon_was_read(tmp_path):
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page('<link rel="icon" href="/i/f.png">')),
                        "https://www.acme.co.kr/i/f.png": (200, PNGH, png(logo(32, 32)))}, tmp=tmp_path)
    assert "https://www.acme.co.kr/favicon.ico" not in web.urls()
    assert rec["outcome"] == "rejected"


# ── the homepage: parsing and candidate order ─────────────────────────────────────────────────────────────────────

def test_candidates_are_resolved_and_ordered_apple_manifest_icons_then_fixed_paths():
    page = si.parse_page(
        '<html><head><base href="/kor/">'
        '<link rel="icon" type="image/png" sizes="16x16" href="f16.png">'
        '<link rel="icon" sizes="192x192" href="f192.png">'
        '<link rel="Shortcut Icon" href="/favicon.ico">'
        '<link rel="icon" type="image/svg+xml" href="logo.svg">'
        '<link rel="apple-touch-icon" href="a.png">'
        '<link rel="apple-touch-icon-precomposed" sizes="152x152" href="a152.png">'
        '<link rel="apple-touch-icon" sizes="57x57" href="a57.png">'
        '<link rel="manifest" href="/site.webmanifest">'
        '<link rel="mask-icon" href="/pin.svg" color="#000">'
        '</head></html>')
    c = si.page_candidates(page, "https://www.acme.co.kr/index.do")
    got = [(x["kind"], x["url"].replace("https://www.acme.co.kr", ""), x["declared"]) for x in c]
    assert got == [("apple-touch-icon", "/kor/a.png", None), ("apple-touch-icon", "/kor/a152.png", 152),
                   ("apple-touch-icon", "/kor/a57.png", 57), ("manifest-link", "/site.webmanifest", None),
                   ("icon", "/kor/logo.svg", 256), ("icon", "/kor/f192.png", 192), ("icon", "/kor/f16.png", 16),
                   ("icon", "/favicon.ico", None), ("fallback-apple-touch-icon", "/apple-touch-icon.png", None),
                   ("fallback-apple-touch-icon-precomposed", "/apple-touch-icon-precomposed.png", None)]


def test_fixed_paths_use_the_host_the_homepage_ended_on():
    c = si.page_candidates(si.parse_page(""), "http://corp.acme.com/main/")
    assert [x["url"] for x in c] == ["http://corp.acme.com/apple-touch-icon.png", "http://corp.acme.com/favicon.ico",
                                     "http://corp.acme.com/apple-touch-icon-precomposed.png"]


@pytest.mark.parametrize("sizes,typ,href,want", [("180x180", "", "", 180), ("16x16 32x32", "", "", 32),
                                                 ("any", "image/svg+xml", "", 256), ("", "", "/x.svg", 256),
                                                 ("", "", "/x.png", None), ("192X192", "", "", 192),
                                                 ("200x96", "", "", 96), ("bogus", "", "", None)])
def test_declared_side(sizes, typ, href, want):
    assert si.declared_side(sizes, typ, href) == want


def test_manifest_icons_largest_first_any_before_maskable_monochrome_left_out():
    m = json.dumps({"icons": [{"src": "i/192.png", "sizes": "192x192"},
                              {"src": "i/512m.png", "sizes": "512x512", "purpose": "maskable"},
                              {"src": "i/512.png", "sizes": "512x512", "purpose": "any maskable"},
                              {"src": "i/mono.png", "sizes": "512x512", "purpose": "monochrome"},
                              {"sizes": "64x64"}, "junk"]})
    c = si.manifest_candidates(m, "https://www.acme.co.kr/static/site.webmanifest")
    assert [x["url"].rsplit("/", 1)[1] for x in c] == ["512.png", "192.png", "512m.png"]
    assert all(x["url"].startswith("https://www.acme.co.kr/static/i/") for x in c)
    assert si.manifest_candidates("not json", "https://x/") == [] and si.manifest_candidates("[]", "https://x/") == []


@pytest.mark.parametrize("content,want", [("0;url=/kor/main.do", "https://a.kr/kor/main.do"),
                                          ("0; URL='http://b.kr/'", "http://b.kr/"), ("5", ""),
                                          ("30; url=/later", ""), ("", "")])
def test_meta_refresh_target(content, want):
    assert si.refresh_target(content, "https://a.kr/") == want


def test_a_meta_refresh_is_followed_once_when_the_page_declares_no_icon(tmp_path):
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page(
                            '<meta http-equiv="refresh" content="0;url=/kor/index.do">')),
                        "https://www.acme.co.kr/kor/index.do": (200, HTML, html_page(
                            '<link rel="apple-touch-icon" href="/a.png">')),
                        "https://www.acme.co.kr/a.png": (200, PNGH, png(logo()))}, tmp=tmp_path)
    assert rec["page_url"] == "https://www.acme.co.kr/kor/index.do" and rec["outcome"] == "icon"


def test_korean_pages_in_euc_kr_decode():
    body = '<html><head><meta charset="euc-kr"><title>회사 소개</title></head></html>'.encode("cp949")
    assert "회사 소개" in si.decode_html(body, "text/html")
    assert "회사 소개" in si.decode_html(body, "text/html; charset=EUC-KR")


def test_start_target():
    assert si.start_target("www.acme.co.kr", "acme.co.kr") == ("www.acme.co.kr", "/", ["https", "http"])
    assert si.start_target("http://www.acme.co.kr/kor/main.do", "acme.co.kr") == \
        ("www.acme.co.kr", "/kor/main.do", ["http"])
    assert si.start_target("https://acme.co.kr", "acme.co.kr")[2] == ["https"]
    assert si.start_target("http://https://acme.co.kr/", "acme.co.kr")[2] == ["https", "http"]
    with pytest.raises(ValueError):
        si.start_target("www.other.co.kr", "acme.co.kr")


# ── images: decoding, size, ICO frames, SVG, blank ─────────────────────────────────────────────────────────────────

def test_ico_takes_the_largest_frame():
    img, fmt = si.decode_image(ico([(16, 16), (32, 32), (128, 128), (48, 48)]))
    assert fmt == "ICO" and img.size == (128, 128) and img.mode == "RGBA"


def test_an_ico_whose_largest_frame_is_small_is_too_small(tmp_path):
    c = {"kind": "icon", "url": "https://www.acme.co.kr/favicon.ico"}
    assert not si.judge_candidate(c, ico([(16, 16), (48, 48)]), "acme.co.kr", None, tmp_path)
    assert c["result"] == "too_small" and c["original_size"] == "48x48"


@pytest.mark.parametrize("w,h,ok", [(96, 96, True), (95, 95, False), (96, 95, False), (200, 80, False),
                                    (512, 512, True), (180, 120, True)])
def test_the_96_px_rule_is_on_the_shorter_side(tmp_path, w, h, ok):
    c = {"kind": "apple-touch-icon", "url": "https://www.acme.co.kr/a.png"}
    assert si.judge_candidate(c, png(logo(w, h)), "acme.co.kr", None, tmp_path) is ok
    assert c["result"] == ("ok" if ok else "too_small")


def test_a_small_icon_enlarged_with_hard_pixels_counts_as_too_small(tmp_path):
    blocky = logo(16, 16).resize((256, 256), Image.NEAREST)
    assert si.upscaled_from(blocky) == (16, "blocky")
    assert si.upscaled_from(logo(32, 32).resize((128, 128), Image.NEAREST)) == (32, "blocky")
    flat = Image.new("RGBA", (256, 256), (20, 40, 120, 255))     # a real flat icon with edges on a 4 px grid
    ImageDraw.Draw(flat).rectangle([100, 100, 139, 179], fill=(255, 255, 255, 255))
    ImageDraw.Draw(flat).ellipse([30, 30, 90, 90], fill=(250, 190, 40, 255))
    assert si.upscaled_from(flat) is None
    assert si.upscaled_from(logo(256, 256)) is None and si.upscaled_from(logo(180, 180)) is None
    c = {"kind": "icon", "url": "https://www.acme.co.kr/favicon.ico"}
    assert not si.judge_candidate(c, png(blocky), "acme.co.kr", None, tmp_path)
    assert c["result"] == "too_small" and "enlarged from a 16 px" in c["note"]


def test_a_small_icon_enlarged_smoothly_or_by_an_uneven_factor_counts_as_too_small():
    assert si.upscaled_from(logo(24, 24).resize((567, 567), Image.NEAREST)) == (24, "blocky")     # 23.6x
    from PIL import ImageFilter
    soft = logo(180, 180).filter(ImageFilter.GaussianBlur(9))       # no more detail than a ~16 px icon
    assert si.upscaled_from(soft) == (32, "blurry")
    assert si.upscaled_from(logo(180, 180)) is None


def _photo(w=180, h=180, seed=5):
    import random
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (min(255, x + rnd.randrange(40)), min(255, y + rnd.randrange(40)),
                        min(255, (x * y) // 160 + rnd.randrange(60)))
    return im.convert("RGBA")


def test_photo_like_pictures_are_flagged_and_logos_are_not():
    m = si.photo_metrics(_photo())
    flags = si.photo_flags(m)
    assert any(f.startswith("many colours") for f in flags) and any("every edge" in f for f in flags)
    gradient = Image.linear_gradient("L").resize((180, 180)).convert("RGBA")
    assert any("smooth" in f or "many colours" in f for f in si.photo_flags(si.photo_metrics(
        Image.merge("RGBA", (gradient.getchannel(0), gradient.getchannel(0).rotate(90),
                             gradient.getchannel(0).rotate(180), Image.new("L", (180, 180), 255))))))
    for img in (logo(), logo(alpha_bg=True), logo(512, 512, seed=3), Image.new("RGBA", (180, 180), (0, 0, 0, 0))):
        assert si.photo_flags(si.photo_metrics(img)) == [], si.photo_metrics(img)
    assert si.photo_flags(si.photo_metrics(logo(400, 200))) == ["far from square (400x200)"]
    text = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    d = ImageDraw.Draw(text)
    for y in range(6, 174, 8):
        for x in range(4, 176, 6):
            d.rectangle([x, y, x + 2, y + 4], fill=(0, 0, 0, 255))
    assert any("text-heavy" in f for f in si.photo_flags(si.photo_metrics(text)))


def test_known_stock_icons_are_generic_even_on_one_site(monkeypatch):
    assert si.KNOWN_GENERIC and all(len(hx) == 64 and int(hx, 16) and len(col) == 3 and label
                                    for label, hx, col in si.KNOWN_GENERIC)
    assert si.known_generic(si.normalise(logo())) == ""
    stock = si.normalise(logo(seed=4, colour=(10, 10, 10)))
    monkeypatch.setattr(si, "KNOWN_GENERIC", (("test globe", format(si.dhash(stock), "064x"), si.mean_colour(stock)),))
    again = logo(seed=4, colour=(10, 10, 10)).resize((256, 256), Image.LANCZOS)      # the same icon, another size
    assert si.known_generic(si.normalise(again)) == "test globe"
    assert si.known_generic(si.normalise(logo())) == ""


def test_preview_pictures_are_never_candidates():
    page = si.parse_page('<meta property="og:image" content="/og.png"><meta name="twitter:image" content="/tw.png">'
                         '<link rel="image_src" href="/share.png"><link rel="preload" as="image" href="/hero.jpg">'
                         '<meta name="msapplication-TileImage" content="/tile.png"><img src="/logo.png">')
    urls = [c["url"] for c in si.page_candidates(page, "https://www.acme.co.kr/")]
    assert urls == ["https://www.acme.co.kr/apple-touch-icon.png", "https://www.acme.co.kr/favicon.ico",
                    "https://www.acme.co.kr/apple-touch-icon-precomposed.png"]


def test_broken_bytes_and_an_svg_without_a_renderer_are_broken(tmp_path):
    c = {"kind": "icon", "url": "https://www.acme.co.kr/x.png"}
    assert not si.judge_candidate(c, b"\x89PNG\r\n\x1a\n broken", "acme.co.kr", None, tmp_path)
    assert c["result"] == "broken"
    c = {"kind": "icon", "url": "https://www.acme.co.kr/x.svg"}
    assert not si.judge_candidate(c, b'<svg xmlns="http://www.w3.org/2000/svg"/>', "acme.co.kr", None, tmp_path)
    assert c["result"] == "broken"


def test_svg_goes_through_the_renderer_at_256_px_and_must_have_content(tmp_path):
    seen = []

    def renderer(body):
        seen.append(body)
        return logo(256, 256) if b"<circle" in body else Image.new("RGBA", (256, 256), (0, 0, 0, 0))

    svg = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle r="4"/></svg>'
    c = {"kind": "icon", "url": "https://www.acme.co.kr/logo.svg"}
    assert si.judge_candidate(c, svg, "acme.co.kr", renderer, tmp_path)
    assert c["format"] == "SVG" and c["original_size"] == "svg" and (c["w"], c["h"]) == (256, 256)
    c = {"kind": "icon", "url": "https://www.acme.co.kr/empty.svg"}
    assert not si.judge_candidate(c, b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "acme.co.kr", renderer,
                                  tmp_path)
    assert c["result"] == "blank" and len(seen) == 2


def test_an_svg_that_points_to_other_files_is_broken_and_never_drawn(tmp_path):
    drawn = []
    outside = [b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
               b'<image xlink:href="https://cdn.x.kr/logo.png"/></svg>',
               b'<svg xmlns="http://www.w3.org/2000/svg"><image href="/logo.png"/></svg>',
               b'<svg xmlns="http://www.w3.org/2000/svg"><style>@import "x.css";</style></svg>',
               b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(other.svg#g)"/></svg>']
    for body in outside:
        c = {"kind": "icon", "url": "https://www.acme.co.kr/logo.svg"}
        assert not si.judge_candidate(c, body, "acme.co.kr", lambda b: drawn.append(b), tmp_path)
        assert c["result"] == "broken" and "other files" in c["note"]
    assert not drawn
    inside = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><defs>'
              b'<linearGradient id="g"/></defs><rect fill="url(#g)"/><use xlink:href="#g"/>'
              b'<image href="data:image/png;base64,AAAA"/></svg>')
    assert not si.svg_refers_outside(inside)


def test_is_svg_sniffs_content_not_the_name():
    assert si.is_svg(b"\xef\xbb\xbf  <svg viewBox='0 0 1 1'/>") and si.is_svg(b"<?xml version='1.0'?><svg/>")
    assert not si.is_svg(b"<!doctype html><html><svg/></html>") and not si.is_svg(png(logo(8, 8)))


def test_blank_one_colour_and_real_content():
    assert si.blank_reason(Image.new("RGBA", (128, 128), (0, 0, 0, 0))) == "fully transparent"
    assert si.blank_reason(Image.new("RGBA", (128, 128), (200, 30, 30, 255)))
    almost = Image.new("RGBA", (128, 128), (255, 255, 255, 255))
    ImageDraw.Draw(almost).point((5, 5), fill=(0, 0, 0, 255))
    assert si.blank_reason(almost)
    white_on_clear = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(white_on_clear).rectangle([30, 30, 98, 98], fill=(255, 255, 255, 255))
    black_on_clear = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(black_on_clear).ellipse([30, 30, 98, 98], fill=(0, 0, 0, 255))
    assert si.blank_reason(white_on_clear) == "" and si.blank_reason(black_on_clear) == ""
    assert si.blank_reason(logo()) == ""


def test_a_data_uri_icon_needs_no_request(tmp_path):
    import base64
    uri = "data:image/png;base64," + base64.b64encode(png(logo(160, 160))).decode()
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (200, HTML, html_page(f'<link rel="apple-touch-icon" href="{uri}">'))},
                       tmp=tmp_path)
    assert rec["outcome"] == "icon" and len(web.calls) == 2


# ── normalisation geometry ─────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("w,h,want", [(96, 96, (128, 128, 0, 0)), (512, 512, (128, 128, 0, 0)),
                                      (200, 100, (128, 64, 0, 32)), (100, 200, (64, 128, 32, 0)),
                                      (300, 97, (128, 41, 0, 43)), (128, 128, (128, 128, 0, 0))])
def test_fit_geometry_keeps_the_aspect_ratio_and_centres(w, h, want):
    assert si.fit_geometry(w, h) == want


def test_normalise_pads_with_transparency_and_never_stretches():
    src = Image.new("RGBA", (200, 100), (10, 120, 200, 255))
    out = si.normalise(src)
    assert out.size == (128, 128) and out.mode == "RGBA"
    assert out.getpixel((64, 5)) == (0, 0, 0, 0) and out.getpixel((64, 122)) == (0, 0, 0, 0)
    assert out.getpixel((64, 64))[3] == 255 and out.getpixel((2, 64))[3] == 255
    box = out.getchannel("A").getbbox()
    assert box == (0, 32, 128, 96)                           # 2:1 stays 2:1, centred
    small = si.normalise(Image.new("RGBA", (96, 96), (0, 0, 0, 0)))
    assert small.size == (128, 128) and small.getextrema()[3] == (0, 0)


# ── generic: (a) shared image, (b) builders, platforms, parked pages ─────────────────────────────────────────────

def _item(key, domain, img, sha=None):
    n = si.normalise(img)
    return {"key": key, "domain": domain, "sha": sha or key, "pix": si.pixel_hash(n), "dh": si.dhash(n),
            "colour": si.mean_colour(n)}


def test_one_image_on_three_different_domains_is_generic_on_two_it_is_not():
    a = logo(seed=1)
    three = [_item("x1", "x1.co.kr", a), _item("x2", "x2.co.kr", a), _item("x3", "x3.com", a.resize((96, 96)))]
    other = [_item("y1", "y1.co.kr", logo(colour=(150, 20, 20), mark=(20, 200, 20), seed=4))]
    got = si.shared_clusters(three + other)
    assert set(got) == {"x1", "x2", "x3"} and got["x1"][1] == ["x1.co.kr", "x2.co.kr", "x3.com"]
    assert si.shared_clusters(three[:2] + other) == {}


def test_the_same_domain_twice_counts_once():
    a = logo(seed=2)
    assert si.shared_clusters([_item("p", "acme.co.kr", a), _item("q", "acme.co.kr", a),
                               _item("r", "beta.co.kr", a)]) == {}


def test_identical_bytes_group_even_when_hashes_differ():
    items = [_item("a", "a.kr", logo(seed=1), sha="S"), _item("b", "b.kr", logo(seed=3), sha="S"),
             _item("c", "c.kr", logo(colour=(0, 150, 0), seed=0), sha="S")]
    assert len(si.shared_clusters(items)) == 3


def test_near_matches_do_not_chain_unrelated_icons_together():
    a, b, c = {"dh": 0, "colour": (100, 100, 100)}, {"dh": 0b111, "colour": (100, 100, 100)}, \
        {"dh": 0b111111, "colour": (100, 100, 100)}
    items = [dict(a, key="a", domain="a.kr", sha="1", pix="1"), dict(b, key="b", domain="b.kr", sha="2", pix="2"),
             dict(c, key="c", domain="c.kr", sha="3", pix="3")]
    assert si.shared_clusters(items, max_bits=3) == {}        # a~b (3 bits), b~c (3 bits), but a and c are 6 apart
    assert len(si.shared_clusters(items, max_bits=6)) == 3


def test_a_recoloured_template_is_not_the_same_image():
    items = [_item("a", "a.kr", logo(colour=(20, 60, 160))), _item("b", "b.kr", logo(colour=(160, 20, 20))),
             _item("c", "c.kr", logo(colour=(20, 140, 20)))]
    assert si.shared_clusters(items) == {}


@pytest.mark.parametrize("url,domain,flag", [
    ("https://www.acme.co.kr/wp-includes/images/w-logo-blue.png", "acme.co.kr", True),
    ("https://static.parastorage.com/client/pfavico.ico", "acme.co.kr", True),
    ("https://static.wixstatic.com/media/abc~mv2.png", "acme.co.kr", False),
    ("https://vendor-cdn.imweb.me/images/favicon_default.png", "acme.co.kr", True),
    ("https://cdn.imweb.me/upload/S2019/abc/favicon.png", "acme.co.kr", False),
    ("https://img.echosting.cafe24.com/skin/favicon.ico", "acme.co.kr", True),
    ("https://acme.cafe24.com/web/upload/favicon.png", "acme.co.kr", False),
    ("https://www.cafe24.com/favicon.png", "cafe24.com", False),
    ("https://t1.kakaocdn.net/kakaopay/icons/web/180-brand.png", "kakaopay.com", False),
    ("https://ssl.pstatic.net/static/www/favicon.png", "navercorp.com", False),
    ("https://img1.wsimg.com/parking-lander/static/favicon.png", "acme.co.kr", True),
    ("https://www.acme.co.kr/images/favicon.png", "acme.co.kr", False),
    ("data:image/png;base64,AAAA", "acme.co.kr", False)])
def test_builder_and_hosting_defaults(url, domain, flag):
    assert bool(si.builder_reason(url, domain)) is flag


@pytest.mark.parametrize("url,domain,flag", [
    ("https://blog.naver.com/acme", "acme.co.kr", True), ("https://acme.tistory.com/", "acme.co.kr", True),
    ("https://acme.imweb.me/", "acme.co.kr", True), ("https://www.sedoparking.com/acme.co.kr", "acme.co.kr", True),
    ("https://sites.google.com/view/acme", "acme.co.kr", True),
    ("https://www.acme.co.kr/kor/", "acme.co.kr", False), ("https://corp.acme.com/", "acme.co.kr", False),
    ("https://www.cafe24.com/", "cafe24.com", False)])
def test_a_homepage_on_a_platform(url, domain, flag):
    assert bool(si.platform_reason(url, domain)) is flag


@pytest.mark.parametrize("title,flag", [("This domain is for sale!", True), ("도메인 연결되지 않음", True),
                                        ("홈페이지 준비중입니다", True), ("Welcome to nginx!", True),
                                        ("IIS Windows Server", True), ("Index of /", True),
                                        ("주식회사 에이씨엠이 - 고객과 함께", False), ("Samsung C&T", False), ("", False)])
def test_parked_or_placeholder_titles(title, flag):
    assert bool(si.title_reason(title)) is flag


def test_a_platform_homepage_fetches_no_icon():
    rec, web = collect({"https://www.acme.co.kr/robots.txt": OK_ROBOTS,
                        "https://www.acme.co.kr/": (302, {"location": "https://blog.naver.com/acme"}, b""),
                        "https://blog.naver.com/robots.txt": OK_ROBOTS,
                        "https://blog.naver.com/acme": (200, HTML, html_page('<link rel="icon" href="/f.ico">'))})
    assert rec["outcome"] == "platform" and not any(u.endswith(("/f.ico", "favicon.ico")) for u in web.urls())


# ── decisions and files ────────────────────────────────────────────────────────────────────────────────────────────

def _site(routes, host, head, icon=None, path="/a.png", title="Company"):
    routes[f"https://{host}/robots.txt"] = OK_ROBOTS
    routes[f"https://{host}/"] = (200, HTML, html_page(head, title))
    if icon is not None:
        routes[f"https://{host}{path}"] = (200, PNGH, icon)


def test_decisions_and_written_files(tmp_path):
    raw = tmp_path / "raw"
    shared_img = png(logo(seed=7, colour=(90, 90, 90)))
    routes = {}
    plan = [("own.co.kr", "www.own.co.kr", '<link rel="apple-touch-icon" href="/a.png">', png(logo(seed=1)), "Own"),
            ("small.co.kr", "www.small.co.kr", '<link rel="icon" href="/a.png">', png(logo(40, 40)), "Small"),
            ("s1.co.kr", "www.s1.co.kr", '<link rel="apple-touch-icon" href="/a.png">', shared_img, "S1"),
            ("s2.co.kr", "www.s2.co.kr", '<link rel="apple-touch-icon" href="/a.png">', shared_img, "S2"),
            ("s3.com", "www.s3.com", '<link rel="apple-touch-icon" href="/a.png">', shared_img, "S3"),
            ("parked.co.kr", "www.parked.co.kr", '<link rel="apple-touch-icon" href="/a.png">', png(logo(seed=3)),
             "This domain is for sale"),
            ("flat.co.kr", "www.flat.co.kr", '<link rel="apple-touch-icon" href="/a.png">',
             png(Image.new("RGBA", (180, 180), (0, 90, 200, 255))), "Flat"),
            ("none.co.kr", "www.none.co.kr", "", None, "None")]
    recs = {}
    sh = shared(FakeWeb(routes))
    for dom, host, head, icon, title in plan:
        _site(routes, host, head, icon, title=title)
    sh = shared(FakeWeb(routes))
    for n, (dom, host, head, icon, title) in enumerate(plan):
        codes = [f"{n:05d}0"] + ([f"{n:05d}5"] if dom == "own.co.kr" else [])
        recs[dom] = si.collect_domain({"domain": dom, "hm_url": host, "codes": codes}, sh, None, raw)
    dec, imgs = si.decide(recs, raw)
    got = {d: (v["decision"], v["reason"][:3]) for d, v in dec.items()}
    assert got == {"own.co.kr": ("kept", ""), "small.co.kr": ("too_small", "40x"),
                   "s1.co.kr": ("generic", "(a)"), "s2.co.kr": ("generic", "(a)"), "s3.com": ("generic", "(a)"),
                   "parked.co.kr": ("generic", "(b)"), "flat.co.kr": ("generic", "(c)"),
                   "none.co.kr": ("no_icon", "can")}
    out = tmp_path / "out"
    (out / "kr").mkdir(parents=True)
    (out / "kr" / "999990.png").write_bytes(b"old")           # a stale file from an earlier run
    nrows, stale = si.write_outputs(out, dec, imgs)
    assert sorted(p.name for p in (out / "kr").glob("*.png")) == ["000000.png", "000005.png"]   # preferred share too
    assert stale == 1 and nrows == 9
    im = Image.open(out / "kr" / "000000.png")
    assert im.size == (128, 128) and im.mode == "RGBA"
    rows = (out / "site_icons.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0].split(",")[:8] == ["code", "domain", "final_url", "source_type", "original_size", "sha256",
                                      "decision", "reason"]
    c = si.counts(recs, dec)
    assert c[("domains", "tried")] == 8 and c[("domains", "kept")] == 1 and c[("companies", "kept")] == 2
    assert c[("domains", ">= 96 px")] == c[("domains", "generic rejected")] + c[("domains", "kept")] == 6


def test_load_items_one_per_domain_preferred_shares_follow_and_opt_outs_are_left_out(tmp_path):
    csvp = tmp_path / "hp.csv"
    csvp.write_text("code,corp_code,via,name_en,corp_cls,hm_url,domain,domain_ok,domain_note,fetched_at,status\n"
                    "000100,1,,A,Y,www.a.co.kr,a.co.kr,1,,,ok\n"
                    "000105,1,000100,A,Y,www.a.co.kr,a.co.kr,1,,,ok\n"
                    "000200,2,,B,Y,blog.naver.com/b,blog.naver.com,0,platform host,,ok\n"
                    "000300,3,,C,K,www.c.com,c.com,1,,,ok\n"
                    "000400,4,,D,K,www.d.com,d.com,1,,,ok\n", encoding="utf-8")
    items, opted = si.load_items(csvp, optout={"000300"})
    assert sorted((i["domain"], tuple(i["codes"])) for i in items) == [("a.co.kr", ("000100", "000105")),
                                                                       ("d.com", ("000400",))]
    assert opted == {"c.com"}
    again, _ = si.load_items(csvp, optout={"000300"})
    assert [i["domain"] for i in again] == [i["domain"] for i in items]       # fixed order
    pref, opted = si.load_items(csvp, optout={"000105"})        # asking through a preferred share removes the issuer
    assert "a.co.kr" not in {i["domain"] for i in pref} and opted == {"a.co.kr"}


def test_an_opt_out_deletes_the_kept_copies_of_that_company_only(tmp_path):
    for sha in ("s1", "s2", "shared"):
        for ext in (".orig", ".png"):
            (tmp_path / f"{sha}{ext}").write_bytes(b"x")
    recs = {"a.kr": {"candidates": [{"sha256": "s1"}, {"sha256": "shared"}]},
            "b.kr": {"candidates": [{"sha256": "s2"}, {"sha256": "shared"}]}}
    assert si.purge_raw(recs, {"a.kr"}, tmp_path) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s2.orig", "s2.png", "shared.orig", "shared.png"]


def test_the_optout_file_is_read_and_the_output_folder_must_be_outside_the_repo(tmp_path):
    f = tmp_path / "o.txt"
    f.write_text("# header\n005930  # asked 2026-12-01\nAcme.co.kr\n\n", encoding="utf-8")
    assert si.read_optout(f) == {"005930", "acme.co.kr"}
    assert si.read_optout(si.OPTOUT) == set()                   # the committed list starts empty
    with pytest.raises(SystemExit):
        si.refuse_inside_repo(ROOT / "tools" / "logos" / "out")
    assert si.refuse_inside_repo(tmp_path) == tmp_path.resolve()


def test_state_resumes_and_skips_a_line_cut_by_a_crash(tmp_path):
    p = tmp_path / "collect.jsonl"
    p.write_text(json.dumps({"domain": "a.kr", "outcome": "icon"}) + "\n" + '{"domain": "b.kr", "outc', encoding="utf-8")
    assert list(si.read_state(p)) == ["a.kr"]
