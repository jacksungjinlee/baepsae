#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Site icons from each Korean listed company's own homepage (logo plan step 4, Jack 2026-11-05).

  python3 tools/logos/site_icons.py --limit 50        # pilot: the first 50 domains of the fixed order
  python3 tools/logos/site_icons.py                   # every usable domain (resumes: domains already done are skipped)
  python3 tools/logos/site_icons.py --decide-only     # no network: judge what was collected and write the outputs again
  python3 tools/logos/site_icons_sheet.py             # the contact sheet Jack looks over before anything goes live

For companies the logo services miss, the app will show the icon the company publishes on its own homepage (the
service's terms forbid checking them by script, so we collect for every Korean company with a usable DART homepage
and each user's browser decides later). Exact identifiers only: the homepage comes from DART (tools/logos/
kr_homepages.csv, domain_ok = 1), never from matching names. A preferred share uses its issuer's homepage.

What it requests, and nothing else (Jack's rules):
  - the company's homepage (the DART hm_url; a value without a scheme is tried as https, then http if https cannot be
    connected to), following redirects (HTTP 3xx and a <meta http-equiv=refresh>);
  - the icon URLs that page or its web manifest points to (<link rel=apple-touch-icon|icon|manifest>);
  - /apple-touch-icon.png, /apple-touch-icon-precomposed.png and /favicon.ico on the homepage's host;
  - robots.txt of every host before anything else on it. A host whose robots.txt disallows "/" for our agent (or for
    "*" when no group names us) is skipped and counted; every other URL is checked against the rules too (RFC 9309:
    longest match wins, allow wins a tie, * and $ work; 4xx = no rules; 5xx = disallow everything).
  - Never a logo provider (cdn.brandfetch.io, img.logo.dev, favicon services, logo sites): refused before any request.
Politeness: honest User-Agent (UA below), one request at a time per host with at least 1 s between them (longer if
robots.txt asks, up to 10 s), at most 6 requests at once overall, 15 s timeout, at most 6 HTTP requests per company
(robots.txt, every redirect hop and every retry included), one retry on a network error, no retry on an HTTP answer
(4xx or 5xx) and no retry on a TLS error (normal verification only, counted as unreachable). If the session proxy
refuses many hosts (403/407 from the proxy itself), the run stops after a sample of 50 and says so.

What it keeps (Jack's rules): icons whose decoded image is at least 96 x 96 px on its own pixels (ICO: the largest
frame; SVG: drawn at 256 px in headless Chromium with every network request blocked; a small icon the site enlarged,
blocky or blurry, counts at its real size — nothing is ever enlarged to reach 96 px), that are not
  (a) the same image (exact bytes, same pixels, or a near-identical perceptual hash) chosen by 3 or more different
      companies with different domains,
  (b) a known website-builder or hosting default (BUILDER_* and PLATFORM_* below), a known stock icon
      (KNOWN_GENERIC), a homepage that is a parked or placeholder page, or one that moved to a blog, cafe or builder,
  (c) blank, almost one colour, or broken.
A kept icon that looks like a picture rather than a mark (photo_flags: many colours, smooth gradients or photo noise,
no transparency with content off every edge, far from square, a text-heavy block, a light mark invisible on white)
is "needs_review", not kept: Jack looks at each one (Jack's coverage test, 2026-11-05: campaign pictures, building
photos, game art, mascots, slogans).
Only icons count: apple-touch-icon, manifest icons, <link rel=icon> and the fixed paths — never og:image,
twitter:image or any other preview picture. When several candidates pass: apple-touch-icon, then the largest
manifest icon, then the largest <link rel=icon>, then the fixed paths. Candidates are fetched in that order and the
first that passes is kept (fewer requests).

Outputs (outside the repository; icons are never committed — Jack looks first):
  OUT/kr/<code>.png      kept: 128 x 128 PNG, transparency kept, centred, never stretched (a non-square icon padded)
  OUT/review/<code>.png  needs review: the same, for Jack to look at
  OUT/site_icons.csv     code, domain, final_url, source_type, original_size, sha256, decision, reason (+ details)
  OUT/decisions.json     the same per domain, for the contact sheet
  OUT/collect.jsonl      what was fetched (append-only; a rerun skips domains already in it)
  OUT/raw/               every decoded candidate (original bytes and a PNG), for the decisions and the contact sheet
OUT defaults to $SITE_ICONS_DIR, else $TMPDIR/site_icons. A folder inside the repository is refused.
A company that asks for its logo to be removed: add its code or domain to site_icons_optout.txt (next to this file);
it is then never fetched and never written. Refresh every few months with --fresh (a new collect.jsonl).
Unit tests (no network): tests/test_site_icons.py.
"""
import argparse
import collections
import concurrent.futures as cf
import contextlib
import csv
import datetime as dt
import hashlib
import html
import html.parser
import io
import json
import os
import pathlib
import queue
import re
import sys
import threading
import time
from urllib.parse import unquote, urljoin, urlsplit
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from logo_ids import homepage_domain, is_shared_host  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
HOMEPAGES = HERE / "kr_homepages.csv"
OPTOUT = HERE / "site_icons_optout.txt"

UA = "BaepsaeLogoCollector/1.0 (+https://jacksungjinlee.github.io/baepsae/)"
UA_TOKEN = "BaepsaeLogoCollector"               # the product token robots.txt groups are matched against
TIMEOUT_S = 15.0
MAX_REQUESTS = 6                                # HTTP requests per company: robots.txt, redirects and retries included
MAX_WORKERS = 6                                 # hosts in parallel overall
MAX_REDIRECTS = 5
HOST_GAP_S = 1.0                                # between two requests to the same host
MAX_CRAWL_DELAY_S = 10.0
MIN_SIDE = 96
OUT_SIDE = 128
SVG_SIDE = 256
MAX_PIXELS = 4096 * 4096
MAX_HTML = 1_000_000
MAX_ICON = 2_000_000
MAX_ROBOTS = 512_000
MAX_MANIFEST = 256_000
PROXY_SAMPLE = 50
PROXY_STOP_SHARE = 0.2
PROXY_BUSY_PAUSE_S = 20.0
DHASH_N = 16                                    # 16 x 16 = 256-bit difference hash
DHASH_MAX = 6                                   # bits apart for "the same image" (rule a)
COLOUR_MAX = 12                                 # mean colour apart (0-255) for "the same image" (rule a)
SHARED_MIN = 3                                  # different companies (domains) using one image -> generic
BLANK_SHARE = 0.985                             # share of pixels within BLANK_TOL of the main colour -> one colour
BLANK_TOL = 24

ACCEPT_HTML = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"
ACCEPT_IMAGE = "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5"
ACCEPT_MANIFEST = "application/manifest+json,application/json;q=0.9,*/*;q=0.5"
ACCEPT_ROBOTS = "text/plain,*/*;q=0.5"


def now_kst():
    return dt.datetime.now(KST)


def log(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


# ── hosts we never request ─────────────────────────────────────────────────────────────────────────────────────────
# Logo providers and favicon services: their terms forbid fetching by script, and an icon from them is not the
# company's own. A homepage that points to one of these is treated as having no such icon (the URL is refused before
# any request; tests/test_site_icons.py checks the transport never sees it).
NEVER_HOSTS = ("brandfetch.io", "brandfetch.com", "logo.dev", "clearbit.com", "uplead.com", "icon.horse",
               "faviconkit.com", "favicongrabber.com", "favicone.com", "duckduckgo.com", "favicon.yandex.net",
               "google.com", "googleusercontent.com", "gstatic.com", "besticon-demo.herokuapp.com",
               "companieslogo.com", "seeklogo.com", "worldvectorlogo.com", "logowik.com", "1000logos.net",
               "logos-world.net", "brandsoftheworld.com", "logolynx.com", "logo-share.com", "vectorlogo.zone")


def host_of(url):
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def host_key(url, scheme=None):
    """The host a URL talks to, for robots.txt and the per-host gate: lower case, no user info, no trailing dot,
    the port only when it is not the scheme's default (https://x.kr:443/ and https://x.kr/ are one host)."""
    p = urlsplit(url) if isinstance(url, str) else url
    h = (p.hostname or "").lower().rstrip(".")
    try:
        port = p.port
    except ValueError:
        port = None
    default = {"https": 443, "http": 80}.get(scheme or p.scheme)
    return f"{h}:{port}" if port and port != default else h


def within(host, domain):
    host, domain = str(host or "").lower(), str(domain or "").lower()
    return bool(domain) and (host == domain or host.endswith("." + domain))


def never_fetch(url):
    """Why this URL is never requested ('' when it may be): a non-web scheme, no host, or a logo provider."""
    try:
        p = urlsplit(url)
    except ValueError:
        return "malformed URL"
    if p.scheme not in ("http", "https"):
        return f"scheme {p.scheme or '(none)'}"
    h = (p.hostname or "").lower().rstrip(".")
    if not h:
        return "no host"
    if any(within(h, n) for n in NEVER_HOSTS):
        return f"logo provider or favicon service ({h})"
    return ""


# ── robots.txt (RFC 9309) ──────────────────────────────────────────────────────────────────────────────────────────

def parse_robots(text):
    """robots.txt text -> groups [{agents: [lower-case], rules: [(allow, pattern)], delay}]. Lines that are not rules
    (an HTML page served as robots.txt, comments, sitemaps) are ignored, so such a file means 'no rules'."""
    groups, cur, in_agents = [], None, False
    for raw in str(text or "").lstrip("﻿").splitlines():
        line = raw.split("#", 1)[0].strip()
        key, sep, val = line.partition(":")
        if not sep:
            continue
        key, val = key.strip().lower(), val.strip()
        if key in ("user-agent", "useragent", "user agent"):
            if cur is None or not in_agents:
                cur = {"agents": [], "rules": [], "delay": None}
                groups.append(cur)
            cur["agents"].append(val.lower())
            in_agents = True
        elif key in ("allow", "disallow"):
            if cur is not None and val:                       # an empty Disallow allows everything: no rule
                cur["rules"].append((key == "allow", val))
            in_agents = False
        elif key == "crawl-delay":
            if cur is not None:
                try:
                    d = float(val)
                    if d == d and d >= 0:
                        cur["delay"] = max(cur["delay"] or 0.0, d)
                except ValueError:
                    pass
            in_agents = False
    return groups


def select_group(groups, token=UA_TOKEN):
    """(rules, crawl_delay) for our product token: groups naming us (case-insensitive, version ignored) win; else the
    '*' groups; several matching groups are combined (RFC 9309 2.2.1)."""
    tok = token.lower()
    mine = [g for g in groups if any(a.split("/")[0].strip() == tok for a in g["agents"])]
    if not mine:
        mine = [g for g in groups if any(a.strip() == "*" for a in g["agents"])]
    rules = [r for g in mine for r in g["rules"]]
    delays = [g["delay"] for g in mine if g["delay"] is not None]
    return rules, (max(delays) if delays else None)


def _rx(pattern):
    p = unquote(pattern)
    end = p.endswith("$")
    body = p[:-1] if end else p
    return re.compile("".join(".*" if ch == "*" else re.escape(ch) for ch in body) + ("$" if end else ""), re.S)


def rules_allow(rules, path):
    """Longest matching pattern wins; allow wins a tie; no match -> allowed. /robots.txt is always allowed."""
    path = unquote(path or "/")
    if path == "/robots.txt":
        return True
    best = None
    for allow, pat in rules:
        if _rx(pat).match(path):
            key = (len(pat), allow)
            if best is None or key > best:
                best = key
    return True if best is None else best[1]


class Robots:
    def __init__(self, rules=(), delay=None, note=""):
        self.rules, self.delay, self.note = list(rules), delay, note

    @classmethod
    def from_answer(cls, status, body):
        """2xx -> the rules for our agent · other 3xx/4xx (401/403 too) -> no rules (RFC 9309 'unavailable') ·
        5xx and 429 -> disallow everything (RFC 9309 'unreachable'; 429 = the server asks us to back off)."""
        if 200 <= status < 300:
            rules, delay = select_group(parse_robots(body))
            return cls(rules, delay, f"robots.txt {len(rules)} rule(s) for us")
        if status >= 500 or status == 429:
            return cls([(False, "/")], None, f"robots.txt answered HTTP {status}: treated as disallow (RFC 9309)")
        return cls([], None, f"no robots.txt (HTTP {status})")

    def allows(self, path):
        return rules_allow(self.rules, path)


def join_location(url, location):
    """A redirect's Location against the URL it came from; a malformed one is refused (never a crash)."""
    try:
        nxt = urljoin(url, str(location).strip())
        urlsplit(nxt).port                                  # raises on a bad port or a broken [IPv6] host
        return nxt
    except ValueError:
        raise Refused(f"malformed redirect {str(location)[:60]!r}", url) from None


def path_of(url):
    p = urlsplit(url)
    return (p.path or "/") + (f"?{p.query}" if p.query else "")


# ── network: errors, the transport, the per-host gate, one company's requests ────────────────────────────────────

class FetchError(Exception):
    kind = "error"


class NetError(FetchError):          # connection refused/reset, timeout, DNS, proxy 502: one retry
    kind = "network"


class TlsError(FetchError):          # certificate or handshake: no retry, unreachable
    kind = "tls"


class ProxyBlocked(FetchError):      # 403/407 from the session proxy itself
    kind = "proxy"


class ProxyBusy(FetchError):         # 429/503 from the session proxy: back off; never a reason to go around it
    kind = "proxy_busy"


class Refused(FetchError):           # we refuse to request it (logo provider, bad scheme, malformed redirect)
    kind = "refused"

    def __init__(self, why, url=""):
        super().__init__(why)
        self.url = url


class BudgetUsed(FetchError):        # the company's 6 requests are used
    kind = "budget"


class RobotsDenied(FetchError):      # robots.txt disallows this URL for us
    kind = "robots"


class TooManyRedirects(FetchError):
    kind = "redirects"


class Resp:
    def __init__(self, status, headers, body, url, truncated=False):
        self.status, self.body, self.url, self.truncated = status, body, url, truncated
        self.headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        self.final_url = url


class RealTransport:
    """requests through the environment's proxy settings, normal certificate verification, streamed with a size cap
    and a 15 s total time cap."""

    def __init__(self):
        import requests
        from urllib3.util import Timeout
        self.rq = requests
        self.timeout = Timeout(connect=TIMEOUT_S, read=TIMEOUT_S, total=TIMEOUT_S)    # 15 s for the whole answer

    def new_session(self):
        s = self.rq.Session()
        s.trust_env = True
        return s

    def __call__(self, session, url, headers, max_bytes, stop_early=None):
        rq = self.rq
        t0 = time.monotonic()
        try:
            r = session.get(url, headers=headers, timeout=self.timeout, allow_redirects=False, stream=True,
                            verify=True)
            body, truncated = bytearray(), False
            try:
                for chunk in r.iter_content(16384):
                    body += chunk
                    if len(body) >= max_bytes:
                        truncated = True
                        break
                    if time.monotonic() - t0 > TIMEOUT_S:
                        raise NetError(f"timeout ({TIMEOUT_S:.0f} s in all)")
                    if stop_early and stop_early(body):
                        break
            finally:
                r.close()
            return Resp(r.status_code, r.headers, bytes(body[:max_bytes]), url, truncated)
        except FetchError:
            raise
        except rq.exceptions.SSLError as e:
            raise TlsError(short_error(e)) from None
        except rq.exceptions.ProxyError as e:
            m = re.search(r"Tunnel connection failed: (\d{3})", str(e))
            if m and m.group(1) in ("403", "407"):
                raise ProxyBlocked(f"proxy answered {m.group(1)}") from None
            if m and m.group(1) in ("429", "503"):
                raise ProxyBusy(f"proxy answered {m.group(1)} (busy)") from None
            raise NetError(short_error(e)) from None
        except (rq.exceptions.ConnectionError, rq.exceptions.Timeout, rq.exceptions.ChunkedEncodingError,
                rq.exceptions.ContentDecodingError) as e:
            raise NetError(short_error(e)) from None
        except rq.exceptions.RequestException as e:
            raise Refused(short_error(e)) from None


def short_error(e):
    s = str(e)
    for pat, label in ((r"CERTIFICATE_VERIFY_FAILED[^)']*", None), (r"Tunnel connection failed: \d{3}[^')]*", None),
                       (r"Connection reset by peer", None), (r"Read timed out", None), (r"timed out", None),
                       (r"Name or service not known|nodename nor servname|getaddrinfo failed", "DNS"),
                       (r"Connection refused", None), (r"EOF occurred in violation of protocol", None),
                       (r"WRONG_VERSION_NUMBER|wrong version number", None), (r"RemoteDisconnected", None)):
        m = re.search(pat, s)
        if m:
            return f"{type(e).__name__}: {label or m.group(0)}"[:160]
    return f"{type(e).__name__}: {s}"[:160]


class HostGate:
    """One request at a time per host, HOST_GAP_S (or the robots.txt crawl delay, up to 10 s) between two requests
    to the same host, and at most MAX_WORKERS requests at once overall."""

    def __init__(self, gap=HOST_GAP_S, parallel=MAX_WORKERS, clock=time.monotonic, sleep=time.sleep):
        self.gap, self.clock, self.sleep = gap, clock, sleep
        self.locks = collections.defaultdict(threading.Lock)
        self.last, self.delay = {}, {}
        self.meta = threading.Lock()
        self.sem = threading.BoundedSemaphore(parallel)

    def set_delay(self, host, seconds):
        if seconds:
            self.delay[host] = min(float(seconds), MAX_CRAWL_DELAY_S)

    @contextlib.contextmanager
    def slot(self, host):
        with self.meta:
            lock = self.locks[host]
        with lock:
            gap = max(self.gap, self.delay.get(host, 0.0))
            last = self.last.get(host)
            if last is not None:
                wait = last + gap - self.clock()
                if wait > 0:
                    self.sleep(wait)
            with self.sem:
                try:
                    yield
                finally:
                    self.last[host] = self.clock()


class Shared:
    """What every company's requests share: the transport, the gate, the robots.txt cache, the counters."""

    def __init__(self, transport, gate=None):
        self.transport, self.gate = transport, gate or HostGate()
        self.robots = {}
        self.robots_locks = collections.defaultdict(threading.Lock)
        self.meta = threading.Lock()
        self.proxy_busy = 0


class CompanyNet:
    """One company's requests: at most MAX_REQUESTS (robots.txt, redirect hops and retries counted), robots.txt
    checked for every URL before it is requested."""

    def __init__(self, shared, limit=MAX_REQUESTS):
        self.sh, self.limit, self.used = shared, limit, 0
        self.trail = []                                   # (url, status or error) for the record
        self.session = shared.transport.new_session() if hasattr(shared.transport, "new_session") else None

    def close(self):
        if self.session is not None and hasattr(self.session, "close"):
            self.session.close()

    def _send(self, url, accept, max_bytes, stop_early=None, retry=True):
        why = never_fetch(url)
        if why:
            self.trail.append((url, f"refused: {why}"))
            raise Refused(why, url)
        host = host_key(url)
        headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "ko,en;q=0.8"}
        tries = 0
        while True:
            if self.used >= self.limit:
                self.trail.append((url, "budget used"))
                raise BudgetUsed(f"{self.limit} requests used")
            self.used += 1
            tries += 1
            try:
                with self.sh.gate.slot(host):
                    r = self.sh.transport(self.session, url, headers, max_bytes, stop_early)
            except NetError as e:
                self.trail.append((url, f"network: {e}"))
                if retry and tries < 2:
                    continue
                raise
            except ProxyBusy as e:                          # the proxy asks us to slow down: wait, then once more
                self.trail.append((url, f"{e.kind}: {e}"))
                self.sh.proxy_busy += 1
                if tries < 2:
                    self.sh.gate.sleep(PROXY_BUSY_PAUSE_S)
                    continue
                raise
            except FetchError as e:
                self.trail.append((url, f"{e.kind}: {e}"))
                raise
            self.trail.append((url, r.status))
            return r

    def robots(self, scheme, hostport, retry=True):
        """Robots for a host (cached for the run, by host; one fetch per host even across workers). robots.txt
        redirects are followed (up to 5, counted); a network or TLS failure raises (the host is unreachable)."""
        key = host_key(f"{scheme}://{hostport}/")
        with self.sh.meta:
            lock = self.sh.robots_locks[key]
        with lock:
            got = self.sh.robots.get(key)
            if got is not None:
                return got
            url = f"{scheme}://{key}/robots.txt"
            for _ in range(MAX_REDIRECTS + 1):
                r = self._send(url, ACCEPT_ROBOTS, MAX_ROBOTS, retry=retry)
                loc = r.headers.get("location")
                if r.status in (301, 302, 303, 307, 308) and loc:
                    url = join_location(url, loc)
                    continue
                rb = Robots.from_answer(r.status, r.body.decode("utf-8", "replace") if 200 <= r.status < 300 else "")
                break
            else:
                rb = Robots([], None, "robots.txt redirected too often: no rules (RFC 9309)")
            self.sh.robots[key] = rb
            if rb.delay:
                self.sh.gate.set_delay(key, rb.delay)
            final = urlsplit(url)
            fkey = host_key(final)
            if fkey and fkey != key and final.path == "/robots.txt" and fkey not in self.sh.robots:
                self.sh.robots[fkey] = rb                     # it is that host's own file: no second fetch
                if rb.delay:
                    self.sh.gate.set_delay(fkey, rb.delay)
            return rb

    def get(self, url, accept, max_bytes, stop_early=None, retry=True, follow=None):
        """GET following redirects; robots.txt checked for every URL (its host's file fetched first if needed).
        follow(from_url, to_url) -> False stops at that redirect: the 3xx answer is returned (final_url = the
        target, not requested)."""
        for _ in range(MAX_REDIRECTS + 1):
            why = never_fetch(url)
            if why:
                self.trail.append((url, f"refused: {why}"))
                raise Refused(why, url)
            p = urlsplit(url)
            rb = self.robots(p.scheme, host_key(p), retry=retry)
            if not rb.allows(path_of(url)):
                self.trail.append((url, "robots: disallowed"))
                raise RobotsDenied(f"robots.txt disallows {path_of(url)[:80]} on {host_key(p)}")
            r = self._send(url, accept, max_bytes, stop_early, retry=retry)
            loc = r.headers.get("location")
            if r.status in (301, 302, 303, 307, 308) and loc:
                nxt = join_location(url, loc)
                if follow is not None and not follow(url, nxt):
                    r.final_url = nxt
                    return r
                url = nxt
                continue
            r.final_url = url
            return r
        raise TooManyRedirects(f"more than {MAX_REDIRECTS} redirects")


# ── the homepage: decoding, links, manifest ───────────────────────────────────────────────────────────────────────

_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)


def decode_html(body, content_type=""):
    """Bytes -> text. Charset from the header, else a <meta> in the first 4 KB, else UTF-8, else CP949 (EUC-KR)."""
    names = []
    m = re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9_\-]+)", content_type or "", re.I)
    if m:
        names.append(m.group(1))
    m = _CHARSET.search(body[:4096])
    if m:
        names.append(m.group(1).decode("ascii", "ignore"))
    names += ["utf-8", "cp949"]
    for n in names:
        n = {"euc-kr": "cp949", "ks_c_5601-1987": "cp949", "x-windows-949": "cp949"}.get(n.lower(), n)
        try:
            return body.decode(n)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", "replace")


def head_done(body):
    """Stop reading a homepage once its <head> is complete (icons are declared there)."""
    return b"</head" in body[-65536:].lower() if len(body) > 0 else False


class _PageParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.base, self.refresh, self.title, self.generator = [], "", "", "", ""
        self.frames, self._in_title = [], False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "link" and a.get("href"):
            self.links.append({"rel": a.get("rel", "").lower().split(), "href": a["href"].strip(),
                               "sizes": a.get("sizes", ""), "type": a.get("type", "").lower(),
                               "purpose": a.get("purpose", "")})
        elif tag == "base" and a.get("href") and not self.base:
            self.base = a["href"].strip()
        elif tag == "meta":
            if a.get("http-equiv", "").lower() == "refresh" and not self.refresh:
                self.refresh = a.get("content", "")
            if a.get("name", "").lower() == "generator" and not self.generator:
                self.generator = a.get("content", "")[:80]
        elif tag == "title" and not self.title:
            self._in_title = True
        elif tag in ("frame", "iframe") and a.get("src"):
            self.frames.append(a["src"].strip())

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title + data)[:200]


def parse_page(text):
    p = _PageParser()
    try:
        p.feed(text)
        p.close()
    except Exception:                                       # noqa: BLE001 — a broken page still gives what it had
        pass
    return {"links": p.links, "base": p.base, "refresh": p.refresh, "title": " ".join(p.title.split()),
            "generator": p.generator, "frames": p.frames[:5]}


def refresh_target(content, page_url):
    """<meta http-equiv=refresh content='0; url=/kor/'> -> absolute URL, or '' (no URL, or a wait over 10 s)."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)?\s*[;,]?\s*(?:url\s*=\s*)?(.*)$", str(content or ""), re.I | re.S)
    if not m:
        return ""
    wait, target = m.group(1), m.group(2).strip().strip("'\"").strip()
    if not target or (wait and float(wait) > 10):
        return ""
    return urljoin(page_url, target)


def declared_side(sizes, typ="", href=""):
    """Largest side a sizes attribute declares: '180x180' -> 180, '16x16 32x32' -> 32, 'any' or an SVG -> SVG_SIDE,
    nothing -> None (unknown until fetched)."""
    best = None
    for tok in str(sizes or "").lower().split():
        if tok == "any":
            return SVG_SIDE
        m = re.fullmatch(r"(\d{1,5})x(\d{1,5})", tok)
        if m:
            s = min(int(m.group(1)), int(m.group(2)))
            best = s if best is None else max(best, s)
    if best is None and ("svg" in str(typ) or re.search(r"\.svgz?(\?|#|$)", str(href), re.I)):
        return SVG_SIDE
    return best


KIND_RANK = {"apple-touch-icon": 0, "manifest-link": 1, "manifest": 1, "icon": 2, "fallback-apple-touch-icon": 3,
             "fallback-favicon": 4, "fallback-apple-touch-icon-precomposed": 5}
FALLBACKS = (("fallback-apple-touch-icon", "/apple-touch-icon.png"),
             ("fallback-favicon", "/favicon.ico"),
             ("fallback-apple-touch-icon-precomposed", "/apple-touch-icon-precomposed.png"))


def _abs(href, base):
    href = str(href or "").strip()
    if href.lower().startswith("data:"):
        return href
    try:
        u = urljoin(base, href)
    except ValueError:
        return ""
    return u if urlsplit(u).scheme in ("http", "https") else ""


def page_candidates(page, page_url):
    """Icon candidates a homepage declares, plus the fixed paths on its host, in the order they are tried:
    apple-touch-icon (largest first), the manifest (its icons are added when it is read), <link rel=icon> (largest
    first, unknown sizes last), /apple-touch-icon.png, /favicon.ico, /apple-touch-icon-precomposed.png.
    Declared sizes under 96 px stay in the list (marked) so the record shows them; they are never fetched."""
    base = _abs(page.get("base") or "", page_url) or page_url
    out, seen = [], set()

    def add(kind, url, side, typ="", purpose=""):
        if url and url not in seen:
            seen.add(url)
            out.append({"kind": kind, "url": url, "declared": side, "type": typ, "purpose": purpose})

    for ln in page.get("links") or []:
        rel = set(ln["rel"])
        url = _abs(ln["href"], base)
        if rel & {"apple-touch-icon", "apple-touch-icon-precomposed"}:
            add("apple-touch-icon", url, declared_side(ln["sizes"], ln["type"], ln["href"]), ln["type"])
        elif "manifest" in rel:
            add("manifest-link", url, None)
        elif "icon" in rel and "mask-icon" not in rel:     # "shortcut icon" too; mask-icon is one colour by design
            add("icon", url, declared_side(ln["sizes"], ln["type"], ln["href"]), ln["type"])
    root = f"{urlsplit(page_url).scheme}://{urlsplit(page_url).netloc}"
    for kind, path in FALLBACKS:
        add(kind, root + path, None)
    return order_candidates(out)


def _sort_side(c):
    s = c.get("declared")
    if s is None:
        return 180 if c["kind"] == "apple-touch-icon" else 0      # an undeclared apple-touch-icon is usually 180
    return s


def order_candidates(cands):
    """Preference: kind (KIND_RANK), then the largest declared size; the original order breaks ties. A manifest's
    icons that are not for 'any' purpose (maskable or monochrome only) come after its 'any' icons."""
    def key(ic):
        i, c = ic
        purpose = set(str(c.get("purpose") or "any").lower().split())
        return (KIND_RANK.get(c["kind"], 9), 0 if (not purpose or "any" in purpose) else 1, -_sort_side(c), i)
    return [c for _, c in sorted(enumerate(cands), key=key)]


def manifest_candidates(text, manifest_url):
    """A web manifest's icons -> candidates (kind 'manifest'), largest first; monochrome-only icons left out
    (one colour by design). Not JSON or no icons -> []."""
    try:
        j = json.loads(str(text or "").lstrip("﻿"))
    except ValueError:
        return []
    icons = j.get("icons") if isinstance(j, dict) else None
    out = []
    for ic in icons if isinstance(icons, list) else []:
        if not isinstance(ic, dict) or not isinstance(ic.get("src"), str):
            continue
        purpose = str(ic.get("purpose") or "any").lower()
        if set(purpose.split()) == {"monochrome"}:
            continue
        url = _abs(ic["src"], manifest_url)
        if url:
            out.append({"kind": "manifest", "url": url, "type": str(ic.get("type") or "").lower(),
                        "declared": declared_side(ic.get("sizes"), ic.get("type"), ic["src"]), "purpose": purpose})
    return order_candidates(out)


# ── images ─────────────────────────────────────────────────────────────────────────────────────────────────────────

class BadImage(Exception):
    pass


def is_svg(body):
    head = body[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<svg"):
        return True
    return head.startswith((b"<?xml", b"<!doctype svg", b"<!--")) and b"<svg" in head and b"<html" not in head


_SVG_OUTSIDE = re.compile(rb"""(?:\bhref|\bsrc)\s*=\s*["']\s*(?!#|data:)[^"'\s]|url\(\s*["']?\s*(?!#|data:)[^)\s"']|@import""",
                          re.I)


def svg_refers_outside(body):
    """True when an SVG points to other files (an <image href>, url(...), @import). We never fetch those, and
    Chromium draws its broken-picture symbol in their place, which must not pass for a logo."""
    return bool(_SVG_OUTSIDE.search(body))


def decode_image(body):
    """Raster bytes -> (RGBA image at its native size, format). ICO: the largest frame (by area, then colour depth);
    an animation: its first frame. Raises BadImage for anything that does not decode or is unreasonably large."""
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(body))
        fmt = im.format or "?"
        if fmt == "ICO":
            sizes = sorted(im.ico.sizes(), key=lambda s: (s[0] * s[1], s))
            if not sizes:
                raise BadImage("ICO without frames")
            im = im.ico.getimage(sizes[-1])
        w, h = im.size
        if w * h > MAX_PIXELS:
            raise BadImage(f"image too large to decode ({w}x{h})")
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)
        im.load()
        return im.convert("RGBA"), fmt
    except BadImage:
        raise
    except Exception as e:                                  # noqa: BLE001 — any decoder failure = broken image
        raise BadImage(f"not a decodable image ({type(e).__name__})") from None


def data_uri_bytes(uri):
    """data:image/png;base64,... -> bytes (no request needed)."""
    import base64
    head, sep, payload = str(uri).partition(",")
    if not sep or not head.lower().startswith("data:"):
        raise BadImage("malformed data: URI")
    try:
        return base64.b64decode(payload, validate=False) if ";base64" in head.lower() else unquote(payload).encode()
    except ValueError:
        raise BadImage("malformed data: URI") from None


def fit_geometry(w, h, side=OUT_SIDE):
    """(new_w, new_h, x, y): scale (w, h) so its longer side is `side`, keep the aspect ratio, centre it."""
    if w <= 0 or h <= 0:
        raise ValueError((w, h))
    scale = side / max(w, h)
    nw = max(1, min(side, round(w * scale)))
    nh = max(1, min(side, round(h * scale)))
    return nw, nh, (side - nw) // 2, (side - nh) // 2


def normalise(img, side=OUT_SIDE):
    """Square side x side RGBA: the icon scaled to fit (premultiplied alpha, Lanczos), centred, padded with
    transparency; never stretched."""
    from PIL import Image
    im = img.convert("RGBA")
    nw, nh, x, y = fit_geometry(im.width, im.height, side)
    if (nw, nh) != im.size:
        im = im.convert("RGBa").resize((nw, nh), Image.LANCZOS).convert("RGBA")
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(im, (x, y))
    return out


SOFT_LOWRES_MAX = 1.6          # mean difference (0-255) after shrinking to 32 px and enlarging back: a blurred-up icon


def upscaled_from(img, sizes=(8, 16, 24, 32)):
    """A small icon the website enlarged (Jack: never let an enlarged small icon pass for a large one; the size rule
    is about the pixels the icon really has). Returns (size, how) or None:
      - 'blocky': hard pixel blocks (a 16 px favicon saved as a 256 px frame, also by a non-whole factor): shrinking
        to that size and enlarging back (nearest pixel) gives the same picture on all but 1 % of the pixels;
      - 'blurry': a smooth enlargement: shrinking to 32 px and enlarging back (bicubic) changes almost nothing (mean
        difference <= SOFT_LOWRES_MAX).
    A real large icon has fine anti-aliased edges and fails both; a flat design drawn on a coarse grid is the rare
    exception, and it looks the same as the enlarged small icon anyway."""
    from PIL import Image, ImageChops
    im = img.convert("RGBA")
    w, h = im.size
    for s in sizes:
        if min(w, h) < 3 * s:
            continue
        k = s / max(w, h)
        small = (max(1, round(w * k)), max(1, round(h * k)))
        back = im.resize(small, Image.NEAREST).resize((w, h), Image.NEAREST)   # samples each block's middle
        r, g, b, a = ImageChops.difference(im, back).split()
        worst = ImageChops.lighter(ImageChops.lighter(r, g), ImageChops.lighter(b, a))
        if worst.point(lambda v: 255 if v > 24 else 0).histogram()[255] <= 0.01 * w * h:
            return s, "blocky"
    if min(w, h) >= 96:
        g0 = Image.alpha_composite(Image.new("RGBA", (w, h), (128, 128, 128, 255)), im).convert("RGB")
        k = 32 / max(w, h)
        back = g0.resize((max(1, round(w * k)), max(1, round(h * k))), Image.BOX).resize((w, h), Image.BICUBIC)
        r, g, b = ImageChops.difference(g0, back).split()
        worst = ImageChops.lighter(ImageChops.lighter(r, g), b)
        hist = worst.histogram()
        if sum(i * n for i, n in enumerate(hist)) / (w * h) <= SOFT_LOWRES_MAX:
            return 32, "blurry"
    return None


# ── photo-like: kept back for Jack to look at ("needs review"), never kept silently ──────────────────────────────
# Jack's coverage test (2026-11-05) found campaign pictures, product and building photos, game art, a mascot and a
# slogan where a logo should be. A site icon is a small flat mark; these signs say "picture, not a mark". Thresholds
# set on the first 123 kept icons (all real logos: entropy at most 5.6 bits, at most 487 colours, soft share at
# most 0.67, one 1.9:1 image) so that none of them would trip a rule on its own except a 3D-sphere logo (gradient).
PHOTO_ENTROPY = 6.5            # bits, colour histogram (16 levels per channel) of the visible pixels -> many colours
PHOTO_COLOURS = 1200           # distinct colours (32 levels per channel) of the visible pixels -> many colours
PHOTO_SOFT = 0.55              # share of soft transitions (2-16 levels between neighbours) ...
PHOTO_SOFT_ENTROPY = 5.0       # ... together with this entropy -> smooth gradients or photographic noise
PHOTO_BLEED_RING = 0.6         # fully opaque, and less than this share of the edge in one colour ...
PHOTO_BLEED_ENTROPY = 4.0      # ... with entropy (or soft share PHOTO_BLEED_SOFT) above -> a full-bleed picture
PHOTO_BLEED_SOFT = 0.3
PHOTO_ASPECT = 1.6             # longer side / shorter side of the image as served -> far from square (banner)
PHOTO_TEXT_STRONG = 0.3        # share of hard edges in an opaque block -> text-heavy banner
PHOTO_TEXT_OPAQUE = 0.9


def photo_metrics(img):
    """Numbers behind photo_flags, measured on the 128 px normalised icon (aspect on the image as served)."""
    import numpy as np
    from PIL import Image
    im = img.convert("RGBA")
    w, h = im.size
    n = normalise(im)
    a = np.asarray(n).astype(np.int32)
    vis = a[..., 3] >= 128
    rgb = a[..., :3][vis]
    m = {"w": w, "h": h, "aspect": round(max(w, h) / min(w, h), 2), "opaque": float((a[..., 3] >= 250).mean())}
    if rgb.size:
        q5 = rgb >> 3
        m["colours"] = int(len(np.unique(q5[:, 0] * 1024 + q5[:, 1] * 32 + q5[:, 2])))
        q4 = rgb >> 4
        _, cnt = np.unique(q4[:, 0] * 256 + q4[:, 1] * 16 + q4[:, 2], return_counts=True)
        p = cnt / cnt.sum()
        m["entropy"] = round(float(-(p * np.log2(p)).sum()), 2)
    else:
        m["colours"], m["entropy"] = 0, 0.0
    nw, nh, x, y = fit_geometry(w, h)
    box = a[y:y + nh, x:x + nw]
    e = max(1, min(3, nw // 8, nh // 8))
    ring = np.concatenate([box[:e].reshape(-1, 4), box[-e:].reshape(-1, 4), box[:, :e].reshape(-1, 4),
                           box[:, -e:].reshape(-1, 4)])
    m["ring_opaque"] = float((ring[:, 3] >= 250).mean())
    med = np.median(ring[:, :3], axis=0)
    m["ring_uniform"] = round(float((np.abs(ring[:, :3] - med).max(axis=1) <= 24).mean()), 3)
    g = np.asarray(Image.alpha_composite(Image.new("RGBA", n.size, (128, 128, 128, 255)), n).convert("L"))
    g = g.astype(np.int32)
    mag = np.maximum(np.abs(np.diff(g, axis=1))[:-1, :], np.abs(np.diff(g, axis=0))[:, :-1])
    region = vis[:-1, :-1]
    tot = max(int(region.sum()), 1)
    m["soft"] = round(float(((mag >= 2) & (mag <= 16) & region).sum() / tot), 3)
    m["strong"] = round(float(((mag >= 60) & region).sum() / tot), 3)
    m["invisible_on_white"] = bool(flat_over(im, (255, 255, 255)))
    return m


def photo_flags(m):
    """Why an icon looks like a picture rather than a mark ([] when it does not). Each sign alone is enough for a
    look by eye; none rejects anything."""
    out = []
    if m["entropy"] >= PHOTO_ENTROPY or m["colours"] >= PHOTO_COLOURS:
        out.append(f"many colours ({m['colours']} colours, entropy {m['entropy']:.1f} bits)")
    if m["soft"] >= PHOTO_SOFT and m["entropy"] >= PHOTO_SOFT_ENTROPY:
        out.append(f"smooth gradients or photo noise (soft share {m['soft']:.2f})")
    if m["opaque"] >= 0.995 and m["ring_uniform"] < PHOTO_BLEED_RING and (
            m["entropy"] >= PHOTO_BLEED_ENTROPY or m["soft"] >= PHOTO_BLEED_SOFT):
        out.append("no transparency and the picture runs off every edge")
    if m["aspect"] >= PHOTO_ASPECT:
        out.append(f"far from square ({m['w']}x{m['h']})")
    if m["strong"] >= PHOTO_TEXT_STRONG and m["opaque"] >= PHOTO_TEXT_OPAQUE:
        out.append(f"text-heavy block (hard-edge share {m['strong']:.2f})")
    if m.get("invisible_on_white"):
        out.append("a light mark on transparency: invisible on a white page")
    return out


# Stock icons several unrelated companies use (a floppy disk, a globe …), matched like rule (a): (label, difference
# hash of the 128 px icon, mean colour over grey). Each one was seen on more than one unrelated site in the
# 2026-11-05 run and looked at by eye; rule (a) catches any that 3+ companies share anyway.
KNOWN_GENERIC = (
    ("Next.js / Vercel default favicon (black circle, white triangle)",
     "20f9c01c8826201b050b4b25571516912d497c055a251013200b88a6c01c20f9", (55.1, 55.1, 55.1)),
    ("Create React App default icon (the React atom, logo192.png)",
     "0b2c38e0b692a33ab69274d1d1741b271b27d17474d1b692a33ab69238e20b2c", (119.9, 153.4, 161.6)),
)


def known_generic(norm):
    dh, col = dhash(norm), mean_colour(norm)
    for label, hx, colour in KNOWN_GENERIC:
        if (dh ^ int(hx, 16)).bit_count() <= DHASH_MAX and max(abs(col[k] - colour[k]) for k in range(3)) <= COLOUR_MAX:
            return label
    return ""


def _rgb_pixels(im):
    b = im.convert("RGB").tobytes()
    return list(zip(b[0::3], b[1::3], b[2::3]))


def blank_reason(img):
    """'' for an icon with real content; else why it is blank: fully transparent, or one colour (within BLANK_TOL on
    BLANK_SHARE of the pixels) both over white and over black (a white logo on transparency is not blank)."""
    im = img.convert("RGBA")
    if im.getextrema()[3][1] <= 8:
        return "fully transparent"
    if flat_over(im, (255, 255, 255)) and flat_over(im, (0, 0, 0)):
        return "almost one colour (no visible logo)"
    return ""


def flat_over(img, bg):
    """True when the icon laid over this background is one colour on BLANK_SHARE of its pixels (nothing to see)."""
    from PIL import Image
    small = img.convert("RGBA").convert("RGBa").resize((64, 64), Image.BOX).convert("RGBA")
    comp = Image.alpha_composite(Image.new("RGBA", small.size, tuple(bg) + (255,)), small).convert("RGB")
    px = _rgb_pixels(comp)
    bucket = collections.Counter((r // 16, g // 16, b // 16) for r, g, b in px).most_common(1)[0][0]
    inb = [p for p in px if (p[0] // 16, p[1] // 16, p[2] // 16) == bucket]
    main = tuple(sum(c[i] for c in inb) / len(inb) for i in range(3))
    near = sum(1 for p in px if max(abs(p[i] - main[i]) for i in range(3)) <= BLANK_TOL)
    return near / len(px) >= BLANK_SHARE


def dhash(img, n=DHASH_N):
    """Difference hash (n x n bits) over mid-grey, so white-on-transparent and black-on-transparent icons both count."""
    from PIL import Image
    im = img.convert("RGBA")
    g = Image.alpha_composite(Image.new("RGBA", im.size, (128, 128, 128, 255)), im).convert("L")
    px = list(g.resize((n + 1, n), Image.LANCZOS).tobytes())
    bits = 0
    for r in range(n):
        for c in range(n):
            bits = (bits << 1) | (px[r * (n + 1) + c] < px[r * (n + 1) + c + 1])
    return bits


def mean_colour(img):
    from PIL import Image
    im = img.convert("RGBA")
    g = Image.alpha_composite(Image.new("RGBA", im.size, (128, 128, 128, 255)), im).convert("RGB").resize((16, 16))
    px = _rgb_pixels(g)
    return tuple(round(sum(p[i] for p in px) / len(px), 1) for i in range(3))


def pixel_hash(img):
    return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


# ── generic: website builders, hosting defaults, platforms, parked pages (rule b) ────────────────────────────────
# Rule (a) (one image chosen by 3+ companies) catches any default not listed here; these catch the ones that also
# show up on fewer sites:
#  - BUILDER_PATHS: default files a builder or web server puts on the company's own host (no exemption);
#  - BUILDER_HOSTS: an icon served from a builder's or hosting/parking service's host, unless its path is where that
#    builder keeps a site's own upload (custom_rx) — a company's own icon uploaded to imweb or Cafe24 is its own;
#    exempt when the company is that service (owners) or the icon is on the company's own domain;
#  - PLATFORM_HOSTS + logo_ids.is_shared_host: a homepage that ends on a blog, cafe, builder or parking host that is
#    not the company's own domain (its icon is the platform's): no icon is fetched there.
# Big portals' content networks (pstatic.net, daumcdn.net, kakaocdn.net) are not listed: their group companies serve
# their own icons from them; a Naver blog or Daum cafe homepage is caught by the page rule instead.
BUILDER_PATHS = (
    ("WordPress default icon", r"/wp-includes/images/w-logo|/wp-admin/images/w-logo|/wp-includes/images/wpicons"),
    ("Wix default icon", r"/pfavico\.ico"),
    ("Squarespace default icon", r"/universal/default-favicon"),
    ("Tomcat or server default icon", r"/tomcat\.(png|gif|svg|ico)$|/docs/images/tomcat|/icons/apache_pb"),
)
BUILDER_HOSTS = (                                   # (label, hosts, custom_rx or None, owners)
    ("WordPress", ("s.w.org", "wp.com", "wordpress.com", "wordpress.org"), r"/files/|/uploads/", ()),
    ("Wix", ("wix.com", "wixstatic.com", "parastorage.com", "wixsite.com"), r"^/(media|shapes)/", ()),
    ("Squarespace", ("squarespace.com", "squarespace-cdn.com", "sqspcdn.com"), r"^/content/", ()),
    ("Blogger", ("blogger.com", "blogspot.com", "blogblog.com"), None, ()),
    ("Weebly", ("weebly.com", "editmysite.com", "weeblysite.com"), r"/uploads/", ()),
    ("GoDaddy", ("wsimg.com", "godaddysites.com", "secureserver.net"), r"^/isteam/ip/[0-9a-f]{8}-", ("godaddy.com",)),
    ("Cafe24", ("cafe24.com", "cafe24img.com", "cafe24.co.kr", "cafe24shop.com", "cafe24app.com"), r"/upload/",
     ("cafe24.com", "cafe24corp.com")),
    ("imweb", ("imweb.me", "imweb.io"), r"/(upload|thumbnail)/", ()),
    ("Godomall", ("godo.co.kr", "godomall.com", "godohosting.com"), r"/data/|/upload/", ("nhncommerce.com",)),
    ("Sixshop", ("sixshop.com", "sixshop.kr"), r"/uploadedfiles/", ()),
    ("Creatorlink or Webflow", ("creatorlink.net", "webflow.io", "website-files.com"), r"^/[0-9a-f]{24}/", ()),
    ("domain parking", ("sedoparking.com", "sedo.com", "parkingcrew.net", "bodis.com", "above.com", "dan.com",
                        "afternic.com", "hugedomains.com", "domainmarket.com", "uniregistry.com", "parklogic.com",
                        "parked.com"), None, ()),
    ("Korean hosting default", ("gabia.com", "gabia.io", "whois.co.kr", "hosting.kr", "dothome.co.kr",
                                "ivyro.net", "inames.co.kr", "hostinger.com"), None, ("gabia.com",)),
)
PLATFORM_HOSTS = ("blog.me", "modoo.at", "tistory.com", "blog.naver.com", "cafe.naver.com", "m.blog.naver.com",
                  "cafe.daum.net", "blog.daum.net", "smartstore.naver.com", "brunch.co.kr", "sites.google.com")
PARKED_TITLE = re.compile(
    r"(domain|도메인).{0,24}(for sale|is parked|parking|판매|만료|주차|구매|연결되지)|this domain (is|may be)|"
    r"buy this domain|parked (free|domain)|hugedomains|sedoparking|"
    r"(호스팅|홈페이지|사이트|웹사이트|서비스).{0,8}(준비\s*중|만료|정지|중지|일시\s*중단)|"
    r"welcome to nginx|apache2? .{0,24}default page|test page for the apache|iis windows server|^index of /|"
    r"^it works!?$|default web site page|under construction|^coming soon", re.I)


def builder_reason(icon_url, company_domain):
    """(b) for one icon URL: '' when it is not a known builder or hosting default."""
    if not icon_url or icon_url.startswith("data:"):
        return ""
    p = urlsplit(icon_url)
    path = (p.path or "").lower()
    for label, rx in BUILDER_PATHS:
        if re.search(rx, path):
            return f"{label} ({path[:60]})"
    h = (p.hostname or "").lower()
    if within(h, company_domain):
        return ""
    for label, hosts, custom_rx, owners in BUILDER_HOSTS:
        if any(within(h, x) for x in hosts) and not any(within(company_domain, o) for o in owners):
            if custom_rx and re.search(custom_rx, path):
                return ""                                    # the site's own upload on that builder
            return f"icon served by {label} ({h})"
    return ""


def platform_reason(page_url, company_domain):
    """(b) the homepage ended on a blog, cafe, builder or parking host that is not the company's own domain."""
    h = host_of(page_url)
    if not h or within(h, company_domain):
        return ""
    for label, hosts, _, owners in BUILDER_HOSTS:
        if any(within(h, x) for x in hosts) and not any(within(company_domain, o) for o in owners):
            return f"homepage is on {label} ({h})"
    if any(within(h, x) for x in PLATFORM_HOSTS) or is_shared_host(h):
        return f"homepage is on a platform ({h})"
    return ""


def title_reason(title):
    """(b) the homepage is a parked, hosting-default or placeholder page (by its <title>)."""
    t = " ".join(str(title or "").split())
    if t and PARKED_TITLE.search(t):
        return f"parked or placeholder page (title: {t[:60]})"
    return ""


# ── rule (a): one image chosen by several companies ───────────────────────────────────────────────────────────────

def shared_clusters(items, max_bits=DHASH_MAX, max_colour=COLOUR_MAX, min_domains=SHARED_MIN):
    """items: [{key, domain, sha, pix, dh, colour}] (one per company's chosen icon). Two icons are 'the same image'
    when their bytes or pixels are identical, or their difference hashes are at most max_bits apart and their mean
    colours at most max_colour apart. Identical ones form a unit first; a unit then joins a group only when it is
    near every unit already in it (no chaining: A~B and B~C does not make A~C). Returns {key: (cluster_no, sorted
    domains)} for every icon whose group spans at least min_domains different domains. Same domain twice (a
    preferred share) counts once."""
    n = len(items)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by = collections.defaultdict(list)
    for i, it in enumerate(items):
        by[("sha", it["sha"])].append(i)
        by[("pix", it["pix"])].append(i)
    for idx in by.values():
        for j in idx[1:]:
            a, b = find(idx[0]), find(j)
            if a != b:
                parent[max(a, b)] = min(a, b)
    units = collections.defaultdict(list)
    for i in range(n):
        units[find(i)].append(i)

    def near(i, j):
        a, b = items[i], items[j]
        return (a["dh"] ^ b["dh"]).bit_count() <= max_bits and \
            max(abs(a["colour"][k] - b["colour"][k]) for k in range(3)) <= max_colour

    groups = []                                             # [[unit roots]]
    for root in sorted(units, key=lambda r: (-len(units[r]), min(items[i]["key"] for i in units[r]))):
        for g in groups:
            if all(near(root, other) for other in g):
                g.append(root)
                break
        else:
            groups.append([root])
    groups = {g[0]: [i for root in g for i in units[root]] for g in groups}
    out, no = {}, 0
    for root in sorted(groups, key=lambda r: min(items[i]["key"] for i in groups[r])):
        idx = groups[root]
        doms = sorted({items[i]["domain"] for i in idx})
        if len(doms) >= min_domains:
            no += 1
            for i in idx:
                out[items[i]["key"]] = (no, doms)
    return out


# ── one company: what it fetches ─────────────────────────────────────────────────────────────────────────────────

def start_target(hm_url, domain):
    """DART hm_url -> (host, path, schemes). A value without a scheme (most of DART's) is tried as https first, then
    http when https cannot be connected to; an explicit scheme is used as it is. The host must give the CSV's domain
    (the same rule as logo_ids.homepage_domain), else ValueError."""
    raw = str(hm_url or "").strip()
    if homepage_domain(raw) != domain or not domain:
        raise ValueError(f"homepage {raw!r} does not give the domain {domain!r}")
    schemes = re.findall(r"(https?)\s*:?/{2,}", raw[:40], re.I)
    explicit = schemes[-1].lower() if len(schemes) == 1 else None
    s = raw
    while True:
        t = re.sub(r"^\s*(?:https?:/*|https?/{2,}|/+)\s*", "", s, count=1, flags=re.I)
        if t == s:
            break
        s = t
    host = re.split(r"[\s,;/?#\\]", s, maxsplit=1)[0]
    rest = s[len(host):]
    host = host.rsplit("@", 1)[-1].strip(".").lower()
    if not host.isascii():
        host = host.encode("idna").decode("ascii")
    path = rest if re.fullmatch(r"/[^\s,;\\]*", rest or "") else "/"
    return host, path, ([explicit] if explicit else ["https", "http"])


def _raw_save(raw_dir, body, img, fmt):
    """Keep a decoded candidate (original bytes and a PNG of the decoded image) under its sha256."""
    sha = hashlib.sha256(body).hexdigest()
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        tag = f".{os.getpid()}-{threading.get_ident()}.tmp"     # written whole, then moved into place
        orig = raw_dir / f"{sha}.orig"
        if not orig.exists():
            tmp = raw_dir / (orig.name + tag)
            tmp.write_bytes(body)
            os.replace(tmp, orig)
        png = raw_dir / f"{sha}.png"
        if img is not None and not png.exists():
            keep = img
            if max(img.size) > 1024:
                from PIL import Image
                nw, nh, _, _ = fit_geometry(img.width, img.height, 1024)
                keep = img.convert("RGBa").resize((nw, nh), Image.LANCZOS).convert("RGBA")
            tmp = raw_dir / (png.name + tag)
            keep.save(tmp, "PNG")
            os.replace(tmp, png)
    return sha


def judge_candidate(c, body, domain, svg_render, raw_dir):
    """Decode one fetched candidate and judge it on its own (size, builder default, blank). Fills c in place and
    returns True when it passes."""
    c["bytes"] = len(body)
    try:
        if is_svg(body):
            c["format"] = "SVG"
            if svg_refers_outside(body):
                raise BadImage("SVG refers to other files (not fetched)")
            img = svg_render(body) if svg_render else None
            if img is None:
                raise BadImage("SVG did not render")
            c["original_size"] = "svg"
        else:
            img, c["format"] = decode_image(body)
            c["original_size"] = f"{img.width}x{img.height}"
    except BadImage as e:
        c["sha256"] = hashlib.sha256(body).hexdigest()
        c["result"], c["note"] = "broken", str(e)
        return False
    c["w"], c["h"] = img.width, img.height
    c["sha256"] = _raw_save(raw_dir, body, img, c["format"])
    if min(img.width, img.height) < MIN_SIDE:
        c["result"], c["note"] = "too_small", f"{img.width}x{img.height} < {MIN_SIDE}"
        return False
    b = builder_reason(c.get("final_url") or c["url"], domain)
    if b:
        c["result"], c["note"] = "builder", b
        return False
    blank = blank_reason(img)
    if blank:
        c["result"], c["note"] = "blank", blank
        return False
    up = upscaled_from(img)
    if up:
        c["result"], c["note"] = "too_small", f"{img.width}x{img.height} enlarged from a {up[0]} px icon ({up[1]})"
        return False
    c["result"] = "ok"
    return True


def collect_domain(item, shared, svg_render=None, raw_dir=None, limit=MAX_REQUESTS):
    """Fetch one company's homepage and icons. item: {domain, hm_url, codes}. Returns the record (JSON-safe)."""
    dom = item["domain"]
    rec = {"domain": dom, "hm_url": item["hm_url"], "codes": item["codes"], "at": now_kst().isoformat(timespec="seconds"),
           "outcome": "", "reason": "", "page_url": "", "page_status": None, "title": "", "generator": "",
           "frames": [], "requests": 0, "candidates": [], "chosen": None, "trail": []}
    net = CompanyNet(shared, limit)
    try:
        _collect(rec, item, net, svg_render, raw_dir)
    except BudgetUsed:
        rec["outcome"] = rec["outcome"] or "budget"
        rec["reason"] = rec["reason"] or f"{limit} requests used before an icon passed"
    except Exception as e:                                  # noqa: BLE001 — one odd site never stops the run
        rec["outcome"], rec["chosen"] = "error", None
        rec["reason"] = f"tool error: {type(e).__name__}: {str(e)[:120]}"
        log(f"  !! {dom}: {rec['reason']}")
    finally:
        net.close()
        rec["requests"] = net.used
        rec["trail"] = [[u[:200], s] for u, s in net.trail]
    if not rec["outcome"]:
        rec["outcome"] = "icon" if rec["chosen"] is not None else ("no_icon" if not any(
            c.get("result") in ("ok", "too_small", "builder", "blank") for c in rec["candidates"]) else "rejected")
    return rec


_IMAGE_EXT = re.compile(r"\.(png|ico|jpe?g|gif|webp|svgz?|avif|bmp)$", re.I)


def fallback_follow(src, dst):
    """A fixed path (/favicon.ico …) that redirects is followed only to the same file name or another image file
    (http -> https, www, a CDN copy). A redirect to a page ('/error/404.html', the hosting company's error site)
    means the file is not there: not followed."""
    a, b = urlsplit(src).path.rsplit("/", 1)[-1].lower(), urlsplit(dst).path.rsplit("/", 1)[-1].lower()
    return a == b or bool(_IMAGE_EXT.search(b))


def fallback_skip(c, tried):
    """Why a fixed-path fallback is not worth a request ('' to try it): the host already answered a fixed path with
    a web page (its 'not found' page: the others would be too); /favicon.ico when the page's own declared icon was
    already read (the same picture, as a rule); the -precomposed icon when /apple-touch-icon.png was not there."""
    if not c["kind"].startswith("fallback-"):
        return ""
    if any(t["kind"].startswith("fallback-") and t.get("result") == "not_image" for t in tried):
        return "this host answers fixed paths with a web page or a redirect to one"
    if c["kind"] == "fallback-favicon" and any(t["kind"] == "icon" and t.get("result") in FOUND for t in tried):
        return "the page's declared icon was already read"
    if c["kind"] == "fallback-apple-touch-icon-precomposed" and any(
            t["kind"] == "fallback-apple-touch-icon" and t.get("status") in (404, 410) for t in tried):
        return "/apple-touch-icon.png is not there either"
    return ""


def _collect(rec, item, net, svg_render, raw_dir):
    dom = rec["domain"]
    try:
        host, path, schemes = start_target(item["hm_url"], dom)
    except (ValueError, UnicodeError) as e:
        rec["outcome"], rec["reason"] = "unreachable", f"homepage value not usable: {e}"
        return
    page = None
    for i, scheme in enumerate(schemes):
        fallback = i + 1 < len(schemes)                     # https could not be connected to (after its retry) -> http
        try:
            rb = net.robots(scheme, host)
            if not rb.allows("/"):
                rec["outcome"], rec["reason"] = "robots_blocked", f"robots.txt disallows / on {host} ({rb.note})"
                return
            page = net.get(f"{scheme}://{host}{path}", ACCEPT_HTML, MAX_HTML, head_done)
            break
        except NetError as e:
            if fallback:
                continue
            rec["outcome"], rec["reason"] = "unreachable", f"network: {e}"
            return
        except TlsError as e:
            rec["outcome"], rec["reason"] = "tls", f"TLS: {e}"
            return
        except ProxyBlocked as e:
            rec["outcome"], rec["reason"] = "proxy_blocked", str(e)
            return
        except ProxyBusy as e:                              # never answered by going around the proxy (no http)
            rec["outcome"], rec["reason"] = "unreachable", f"proxy busy: {e}"
            return
        except RobotsDenied as e:
            rec["outcome"], rec["reason"] = "robots_blocked", str(e)
            return
        except Refused as e:
            plat = platform_reason(e.url, dom) if e.url else ""
            if plat:                                        # e.g. a homepage that moved to sites.google.com
                rec["outcome"], rec["reason"] = "platform", plat
            else:
                rec["outcome"], rec["reason"] = "unreachable", f"{e.kind}: {e}"
            return
        except TooManyRedirects as e:
            rec["outcome"], rec["reason"] = "unreachable", f"{e.kind}: {e}"
            return
    rec["page_status"], rec["page_url"] = page.status, page.final_url
    ph = urlsplit(page.final_url)
    if host_key(ph) != host_key(f"{scheme}://{host}/"):     # redirected to another host: "/" must be allowed there too
        try:
            if not net.robots(ph.scheme, host_key(ph)).allows("/"):
                rec["outcome"], rec["reason"] = "robots_blocked", f"robots.txt disallows / on {host_key(ph)}"
                return
        except BudgetUsed:
            raise
        except FetchError as e:
            rec["outcome"], rec["reason"] = ("unreachable", f"{e.kind}: {e}")
            return
    plat = platform_reason(page.final_url, dom)
    if plat:                                                 # a blog, cafe, builder or parking page: not its own icon
        rec["outcome"], rec["reason"] = "platform", plat
        return
    parsed = {"links": [], "base": "", "refresh": "", "title": "", "generator": "", "frames": []}
    if 200 <= page.status < 300:
        parsed = parse_page(decode_html(page.body, page.headers.get("content-type", "")))
        target = refresh_target(parsed["refresh"], page.final_url)
        icons_declared = any({"icon", "apple-touch-icon", "apple-touch-icon-precomposed"} & set(ln["rel"])
                             for ln in parsed["links"])
        if target and target != page.final_url and not icons_declared:   # an HTML redirect: follow it once
            try:
                page2 = net.get(target, ACCEPT_HTML, MAX_HTML, head_done)
                if 200 <= page2.status < 300:
                    page = page2
                    rec["page_status"], rec["page_url"] = page.status, page.final_url
                    parsed = parse_page(decode_html(page.body, page.headers.get("content-type", "")))
            except BudgetUsed:
                raise
            except FetchError as e:
                rec["trail_note"] = f"meta refresh not followed: {e.kind}: {e}"
            plat = platform_reason(page.final_url, dom)
            if plat:
                rec["outcome"], rec["reason"] = "platform", plat
                return
    elif page.status in (404, 410):
        pass                                                 # no homepage at that path: the fixed icon paths may exist
    else:
        rec["outcome"], rec["reason"] = "unreachable", f"homepage answered HTTP {page.status}"
        return
    rec["title"], rec["generator"], rec["frames"] = parsed["title"], parsed["generator"], parsed["frames"]
    cands = page_candidates(parsed, page.final_url)
    manifest_done = False
    i = 0
    while i < len(cands):
        c = cands[i]
        i += 1
        if c["kind"] == "manifest-link":
            if manifest_done:
                continue
            manifest_done = True
            try:
                m = net.get(c["url"], ACCEPT_MANIFEST, MAX_MANIFEST)
                c["status"] = m.status
                more = manifest_candidates(m.body.decode("utf-8", "replace"), m.final_url) if 200 <= m.status < 300 else []
                c["result"], c["note"] = "manifest", f"{len(more)} icon(s)"
                known = {x["url"] for x in cands}
                cands[i:i] = [x for x in more if x["url"] not in known]
            except BudgetUsed:
                c["result"] = "budget"
                rec["candidates"].append(c)
                raise
            except FetchError as e:
                c["result"], c["note"] = e.kind, str(e)[:120]
            rec["candidates"].append(c)
            continue
        if c.get("declared") is not None and c["declared"] < MIN_SIDE:
            c["result"], c["note"] = "declared_small", f"declares {c['declared']} px"
            rec["candidates"].append(c)
            continue
        skip = fallback_skip(c, rec["candidates"])
        if skip:
            c["result"], c["note"] = "skipped", skip
            rec["candidates"].append(c)
            continue
        rec["candidates"].append(c)
        try:
            if c["url"].startswith("data:"):
                body, c["final_url"], c["status"] = data_uri_bytes(c["url"]), "data:", 200
                c["url"] = c["url"][:64] + "..."
            else:
                fixed = c["kind"].startswith("fallback-")
                r = net.get(c["url"], ACCEPT_IMAGE, MAX_ICON, follow=fallback_follow if fixed else None)
                c["status"], c["final_url"], c["ctype"] = r.status, r.final_url, r.headers.get("content-type", "")
                if 300 <= r.status < 400 and fixed:
                    c["result"], c["note"] = "not_image", f"redirects to a page ({r.final_url[:80]}): not followed"
                    continue
                if not 200 <= r.status < 300:
                    c["result"], c["note"] = "http", f"HTTP {r.status}"
                    continue
                if r.truncated:
                    c["result"], c["note"] = "broken", f"larger than {MAX_ICON:,} bytes"
                    continue
                if c["ctype"].lower().startswith(("text/html", "application/xhtml")) and not is_svg(r.body):
                    c["result"], c["note"] = "not_image", "a web page, not an image (the site's 'not found' page)"
                    continue
                body = r.body
        except BudgetUsed:
            c["result"] = "budget"
            raise
        except BadImage as e:
            c["result"], c["note"] = "broken", str(e)
            continue
        except FetchError as e:
            c["result"], c["note"] = e.kind, str(e)[:120]
            continue
        if judge_candidate(c, body, dom, svg_render, raw_dir):
            rec["chosen"] = len(rec["candidates"]) - 1
            return


# ── SVG: drawn in headless Chromium, no network ────────────────────────────────────────────────────────────────────

class SvgRenderer:
    """One Chromium in its own thread (Playwright's sync API is single-threaded); workers wait for their picture.
    The SVG is shown as an <img> from a data: URL (an SVG image cannot run scripts or load anything), and every
    network request the page might make is aborted."""

    def __init__(self, side=SVG_SIDE):
        self.side, self.q = side, queue.Queue()
        self.t = threading.Thread(target=self._run, daemon=True)
        self.ready = threading.Event()
        self.err = None
        self.t.start()
        self.ready.wait(60)
        if self.err:
            raise RuntimeError(self.err)

    def _run(self):
        import base64
        from PIL import Image
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": self.side, "height": self.side}, device_scale_factor=1,
                                 java_script_enabled=True, offline=True)
            ctx.route("**/*", lambda route: route.abort() if not route.request.url.startswith("data:") else route.continue_())
            page = ctx.new_page()
        except Exception as e:                              # noqa: BLE001
            self.err = f"Chromium did not start: {e}"
            self.ready.set()
            return
        self.ready.set()
        while True:
            job = self.q.get()
            if job is None:
                break
            body, fut = job
            try:
                src = "data:image/svg+xml;base64," + base64.b64encode(body).decode("ascii")
                page.set_content(f'<html><body style="margin:0;background:transparent">'
                                 f'<img id="i" src="{src}" style="display:block;width:{self.side}px;'
                                 f'height:{self.side}px;object-fit:contain"></body></html>')
                ok = page.evaluate("""() => new Promise(res => { const i = document.getElementById('i');
                    const done = () => res(i.complete && i.naturalWidth > 0);
                    if (i.complete) done(); else { i.onload = done; i.onerror = () => res(false);
                    setTimeout(() => res(false), 3000); } })""")
                if not ok:
                    fut.set_result(None)
                    continue
                png = page.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": self.side,
                                                                   "height": self.side})
                fut.set_result(Image.open(io.BytesIO(png)).convert("RGBA"))
            except Exception as e:                          # noqa: BLE001 — a bad SVG is a broken image
                fut.set_result(None)
                log(f"  !! SVG render failed: {type(e).__name__}")
        br.close()
        pw.stop()

    def __call__(self, body):
        fut = cf.Future()
        self.q.put((body, fut))
        try:
            return fut.result(timeout=30)
        except cf.TimeoutError:
            return None

    def close(self):
        self.q.put(None)
        self.t.join(10)


# ── inputs and state ───────────────────────────────────────────────────────────────────────────────────────────────

def read_optout(path=OPTOUT):
    out = set()
    p = pathlib.Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            v = line.split("#", 1)[0].strip().lower()
            if v:
                out.add(v)
    return out


def load_items(homepages=HOMEPAGES, optout=frozenset()):
    """kr_homepages.csv -> one item per usable domain {domain, hm_url, codes}, in a fixed order that mixes company
    sizes (sha1 of the domain), so a --limit pilot is a spread and a rerun continues in the same order.
    A company that opted out (by any of its codes, or by its domain) is left out whole: every share class of that
    issuer, i.e. the whole domain. Returns (items, opted-out domains)."""
    with open(homepages, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("domain_ok") == "1"]
    opted = {r["domain"].strip().lower() for r in rows
             if r["code"].strip().lower() in optout or r["domain"].strip().lower() in optout}
    by = {}
    for r in rows:
        code, dom = r["code"].strip().upper(), r["domain"].strip().lower()
        if dom in opted:
            continue
        it = by.setdefault(dom, {"domain": dom, "hm_url": r["hm_url"], "codes": []})
        it["codes"].append(code)
        if not r.get("via"):                                # the common share's own value wins
            it["hm_url"] = r["hm_url"]
    items = sorted(by.values(), key=lambda it: hashlib.sha1(it["domain"].encode()).hexdigest())
    for it in items:
        it["codes"].sort()
    return items, opted


def purge_raw(recs, domains, raw_dir):
    """Delete the kept copies (raw/) of every image collected for these domains, unless another domain's record
    uses the same file. For opt-outs: 'never written' includes our working copies."""
    mine, others = set(), set()
    for dom, r in recs.items():
        shas = {c.get("sha256") for c in r.get("candidates") or [] if c.get("sha256")}
        (mine if dom in domains else others).update(shas)
    gone = 0
    for sha in mine - others:
        for ext in (".orig", ".png"):
            f = pathlib.Path(raw_dir) / f"{sha}{ext}"
            if f.exists():
                f.unlink()
                gone += 1
    return gone


def read_state(path):
    recs = {}
    p = pathlib.Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue                            # a line cut by a crash: that domain runs again
                    recs[r["domain"]] = r
    return recs


RETRYABLE = ("unreachable", "budget", "proxy_blocked", "error")


def retryable(rec):
    """--retry tries a domain again only when nothing on the site said no: a network failure, a busy or refusing
    proxy, the request budget, a tool error. Never a host that answered with an HTTP error (no retries on 4xx), a
    TLS failure, a robots.txt refusal or a malformed or refused URL."""
    if rec.get("outcome") not in RETRYABLE:
        return False
    if rec["outcome"] == "unreachable":
        return str(rec.get("reason", "")).startswith(("network:", "proxy busy"))
    return True


def default_out():
    base = os.environ.get("SITE_ICONS_DIR") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "site_icons")
    return pathlib.Path(base)


def refuse_inside_repo(path):
    p = pathlib.Path(path).resolve()
    if p == ROOT or ROOT in p.parents:
        raise SystemExit(f"!! {p} is inside the repository; icons must not be committed before Jack looks. "
                         "Use a folder outside it (SITE_ICONS_DIR or --out).")
    return p


# ── decisions and outputs ──────────────────────────────────────────────────────────────────────────────────────────

FOUND = ("ok", "too_small", "builder", "blank")         # candidate results that decoded as an image


def _pick_unchosen(found):
    """No candidate passed: the one that explains the decision. A >= 96 px builder default or blank image says more
    than a small icon; among equals the larger, then the preferred kind."""
    order = {"builder": 0, "blank": 1, "too_small": 2, "ok": 3}
    return min(found, key=lambda c: (order.get(c["result"], 9), -min(c.get("w", 0), c.get("h", 0)),
                                     KIND_RANK.get(c["kind"], 9)))


def decide(recs, raw_dir):
    """Per domain: kept · generic (a/b/c) · too_small · platform · no_icon · unreachable · tls · robots_blocked ·
    proxy_blocked · budget, with the reason. Rules (b) and (c) are applied again (they may have changed since the
    collection) and rule (a) across all domains. Returns (decisions, {domain: 128 px image} for the kept ones)."""
    from PIL import Image
    dec, items, imgs = {}, [], {}
    for dom, r in recs.items():
        d = {"domain": dom, "codes": r["codes"], "page_url": r.get("page_url", ""), "title": r.get("title", ""),
             "requests": r.get("requests", 0), "final_url": r.get("page_url", ""), "source_type": "",
             "original_size": "", "sha256": "", "decision": "", "reason": "", "raw": "", "cluster": None}
        dec[dom] = d
        cands = r.get("candidates") or []
        found = [c for c in cands if c.get("result") in FOUND]
        chosen = cands[r["chosen"]] if r.get("chosen") is not None else None
        best = chosen or (_pick_unchosen(found) if found else None)
        if best:
            d.update(final_url=best.get("final_url") or best["url"], source_type=best["kind"],
                     original_size=best.get("original_size", ""), sha256=best.get("sha256", ""),
                     raw=f"{best.get('sha256', '')}.png")
        if r.get("outcome") == "platform":
            d["decision"], d["reason"] = "platform", "(b) " + r.get("reason", "")
            continue
        if not best:
            d["decision"] = r["outcome"] if r["outcome"] not in ("icon", "rejected", "") else "no_icon"
            d["reason"] = r.get("reason") or _no_icon_reason(cands)
            continue
        try:
            img = Image.open(raw_dir / d["raw"]).convert("RGBA")
        except (OSError, ValueError) as e:                  # raw/ cleaned or damaged: say so, never guess
            d["decision"], d["reason"] = "no_icon", f"decoded copy missing in raw/ ({type(e).__name__}); run again"
            continue
        if min(img.size) < MIN_SIDE:
            d["decision"], d["reason"] = "too_small", best.get("note") or f"{best.get('original_size')} < {MIN_SIDE}"
            continue
        b = builder_reason(d["final_url"], dom) or title_reason(r.get("title", ""))
        if b or best.get("result") == "builder":
            d["decision"], d["reason"] = "generic", "(b) " + (b or best.get("note", ""))
            continue
        blank = blank_reason(img)
        if blank or best.get("result") == "blank":
            d["decision"], d["reason"] = "generic", "(c) " + (blank or best.get("note", ""))
            continue
        up = upscaled_from(img)
        if up:
            d["decision"], d["reason"] = "too_small", \
                f"{best.get('original_size')} enlarged from a {up[0]} px icon ({up[1]})"
            continue
        norm = normalise(img)
        stock = known_generic(norm)
        if stock:
            d["decision"], d["reason"] = "generic", f"(b) known stock icon: {stock}"
            continue
        m = photo_metrics(img)
        size = re.fullmatch(r"(\d+)x(\d+)", str(best.get("original_size") or ""))
        if size:                                            # raw/ keeps at most 1024 px: report the served size
            m["w"], m["h"] = int(size.group(1)), int(size.group(2))
        d["metrics"] = m
        flags = photo_flags(m)
        d["decision"], d["reason"] = ("needs_review", "needs a look: " + "; ".join(flags)) if flags else ("kept", "")
        imgs[dom] = norm
        items.append({"key": dom, "domain": dom, "sha": d["sha256"], "pix": pixel_hash(norm), "dh": dhash(norm),
                      "colour": mean_colour(norm)})
    for dom, (no, doms) in shared_clusters(items).items():
        d = dec[dom]
        d["decision"], d["cluster"] = "generic", no
        others = [x for x in doms if x != dom]
        d["reason"] = f"(a) same image as {len(others)} other compan{'y' if len(others) == 1 else 'ies'}: " \
                      + ", ".join(others[:4]) + (" ..." if len(others) > 4 else "")
        imgs.pop(dom, None)
    return dec, imgs


def _no_icon_reason(cands):
    if not cands:
        return "no candidate"
    res = collections.Counter(c.get("result", "?") for c in cands)
    return "candidates: " + ", ".join(f"{k} {v}" for k, v in res.most_common())


CSV_COLS = ["code", "domain", "final_url", "source_type", "original_size", "sha256", "decision", "reason",
            "page_url", "requests"]


def write_outputs(out, dec, imgs):
    """kept -> OUT/kr/<code>.png · needs_review -> OUT/review/<code>.png (Jack looks; nothing there is kept until he
    says so) · anything else in those folders from an earlier run is removed."""
    stale = []
    for sub, decision in (("kr", "kept"), ("review", "needs_review")):
        folder = out / sub
        folder.mkdir(parents=True, exist_ok=True)
        keep_files = set()
        for dom, img in imgs.items():
            if dec[dom]["decision"] != decision:
                continue
            for code in dec[dom]["codes"]:
                f = folder / f"{code}.png"
                img.save(f, "PNG", optimize=True)
                keep_files.add(f.name)
        old = [f for f in folder.glob("*.png") if f.name not in keep_files]
        for f in old:
            f.unlink()
        stale += old
    rows = []
    for dom, d in dec.items():
        for code in d["codes"]:
            rows.append({**{k: d.get(k, "") for k in CSV_COLS}, "code": code})
    rows.sort(key=lambda r: r["code"])
    tmp = out / "site_icons.csv.tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out / "site_icons.csv")
    tmp = out / "decisions.json.tmp"
    tmp.write_text(json.dumps(dec, ensure_ascii=False, indent=0, sort_keys=True, allow_nan=False), encoding="utf-8")
    os.replace(tmp, out / "decisions.json")
    return len(rows), len(stale)


COUNT_KEYS = ["tried", "reachable", "robots-blocked", "unreachable", "  of which TLS", "  of which proxy refused",
              "homepage on a platform (b, no icon fetched)", "icon found", ">= 96 px", "generic rejected",
              "  (a) same image as 3+ companies", "  (b) builder or hosting default, parked page",
              "  (c) blank or one colour", "needs review (picture-like or hard to see)", "kept", "too small (< 96 px)",
              "  of which enlarged from a small icon", "broken image seen (any candidate)", "tool error"]


def counts(recs, dec):
    """The loud counts, by domain and by company (stock code). The ladder: tried >= reachable >= icon found >= 96 px
    >= kept, and >= 96 px = generic rejected + needs review + kept."""
    c = collections.Counter()
    for dom, r in recs.items():
        n = len(r["codes"])
        d = dec.get(dom, {})
        why = str(d.get("reason", ""))
        gen = d.get("decision") == "generic"
        cands = r.get("candidates") or []
        rows = [("tried", True),
                ("reachable", r.get("page_status") is not None and r["outcome"] not in
                 ("unreachable", "tls", "proxy_blocked", "robots_blocked")),
                ("robots-blocked", r["outcome"] == "robots_blocked"),
                ("unreachable", r["outcome"] in ("unreachable", "tls", "proxy_blocked")),
                ("  of which TLS", r["outcome"] == "tls"),
                ("  of which proxy refused", r["outcome"] == "proxy_blocked"),
                ("homepage on a platform (b, no icon fetched)", d.get("decision") == "platform"),
                ("icon found", any(x.get("result") in FOUND for x in cands)),
                (">= 96 px", d.get("decision") in ("kept", "generic", "needs_review")),
                ("generic rejected", gen),
                ("  (a) same image as 3+ companies", gen and why.startswith("(a)")),
                ("  (b) builder or hosting default, parked page", gen and why.startswith("(b)")),
                ("  (c) blank or one colour", gen and why.startswith("(c)")),
                ("needs review (picture-like or hard to see)", d.get("decision") == "needs_review"),
                ("kept", d.get("decision") == "kept"),
                ("too small (< 96 px)", d.get("decision") == "too_small"),
                ("  of which enlarged from a small icon", d.get("decision") == "too_small" and "enlarged" in why),
                ("broken image seen (any candidate)", any(x.get("result") == "broken" for x in cands)),
                ("tool error", r["outcome"] == "error")]
        for k, v in rows:
            if v:
                c[("domains", k)] += 1
                c[("companies", k)] += n
    return c


def print_counts(recs, dec, total_items=None):
    c = counts(recs, dec)
    log("· counts (companies = stock codes; a preferred share shares its issuer's homepage) ·"
        + (f" planned domains {total_items:,}" if total_items else ""))
    for k in COUNT_KEYS:
        log(f"    {k:<48} companies {c[('companies', k)]:>5,}   domains {c[('domains', k)]:>5,}")
    other = collections.Counter(d["decision"] for d in dec.values())
    log("    decisions by domain: " + ", ".join(f"{k} {v:,}" for k, v in other.most_common()))
    return c


# ── main ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def run_collect(todo, shared, state_path, raw_dir, workers, svg_render, stop_flag):
    lock = threading.Lock()
    done = collections.Counter()
    t0 = time.monotonic()

    def one(item):
        if stop_flag.is_set():
            return None
        rec = collect_domain(item, shared, svg_render, raw_dir)
        with lock:
            with open(state_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
            done["n"] += 1
            done[rec["outcome"]] += 1
            n = done["n"]
            ch = rec["candidates"][rec["chosen"]] if rec["chosen"] is not None else None
            log(f"  [{n:>4}/{len(todo)}] {rec['domain']:<28} {rec['outcome']:<14} req {rec['requests']} "
                + (f"{ch['kind']} {ch.get('original_size', '')}" if ch else rec["reason"][:70]))
            if n % PROXY_SAMPLE == 0:
                share = done["proxy_blocked"] / n
                el = time.monotonic() - t0
                log(f"· {n:,} done in {el / 60:.1f} min · " + ", ".join(f"{k} {v}" for k, v in done.most_common()
                                                                         if k != "n"))
                if share >= PROXY_STOP_SHARE:
                    log(f"!! the session proxy refused {done['proxy_blocked']} of the first {n} hosts "
                        f"({share:.0%}): stopping (not working around the proxy)")
                    stop_flag.set()
        return rec

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, it) for it in todo]
        try:
            for f in cf.as_completed(futs):
                f.result()
        except KeyboardInterrupt:
            stop_flag.set()
            log("!! interrupted: finishing the companies in progress; a rerun continues")
            raise
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--homepages", default=str(HOMEPAGES))
    ap.add_argument("--out", default=str(default_out()), help="output folder (outside the repository)")
    ap.add_argument("--limit", type=int, default=0, help="at most this many domains this run (pilot)")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"hosts in parallel (at most {MAX_WORKERS})")
    ap.add_argument("--decide-only", action="store_true", help="no network: decide and write the outputs again")
    ap.add_argument("--retry", action="store_true", help="also try again domains that were unreachable or ran out "
                                                        "of requests last time")
    ap.add_argument("--fresh", action="store_true", help="start a new collection (the old collect.jsonl is kept "
                                                        "beside it with a date)")
    ap.add_argument("--no-svg", action="store_true", help="do not start Chromium (SVG icons count as broken)")
    a = ap.parse_args(argv)
    out = refuse_inside_repo(a.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_dir, state = out / "raw", out / "collect.jsonl"
    workers = max(1, min(a.workers, MAX_WORKERS))
    optout = read_optout()
    items, opted = load_items(a.homepages, optout)
    log(f"· {len(items):,} usable domains ({sum(len(i['codes']) for i in items):,} companies) from {a.homepages}"
        f" · opted out {len(opted)} domain(s)")
    if a.fresh and state.exists():
        aside = state.with_name(f"collect-{now_kst():%Y%m%d-%H%M%S}.jsonl")
        os.replace(state, aside)
        log(f"· previous collection kept as {aside}")
    recs = read_state(state)
    stop_flag = threading.Event()
    if not a.decide_only:
        want = {it["domain"] for it in items}
        todo = [it for it in items if it["domain"] not in recs or (a.retry and retryable(recs[it["domain"]]))]
        if a.limit:
            todo = todo[:a.limit]
        log(f"· already done {sum(1 for d in recs if d in want):,} · to fetch now {len(todo):,} · workers {workers} · "
            f"UA {UA!r} · timeout {TIMEOUT_S:.0f} s · max {MAX_REQUESTS} requests per company")
        svg = None
        if todo and not a.no_svg:
            svg = SvgRenderer()
        shared = Shared(RealTransport())
        try:
            done = run_collect(todo, shared, state, raw_dir, workers, svg, stop_flag)
        finally:
            if svg:
                svg.close()
        log("· this run: " + ", ".join(f"{k} {v}" for k, v in done.most_common() if k != "n")
            + f" · proxy busy answers {shared.proxy_busy}")
        recs = read_state(state)
    if opted:
        log(f"· opt-outs: {purge_raw(recs, opted, raw_dir)} kept file(s) deleted from {raw_dir}")
    recs = {d: r for d, r in recs.items() if d in {it["domain"] for it in items}}     # opt-outs drop out here too
    dec, imgs = decide(recs, raw_dir)
    nrows, stale = write_outputs(out, dec, imgs)
    print_counts(recs, dec, len(items))
    log(f"· wrote {out / 'site_icons.csv'} ({nrows:,} rows) · {out / 'kr'} "
        f"({sum(len(dec[d]['codes']) for d in imgs if dec[d]['decision'] == 'kept'):,} icons) · {out / 'review'} "
        f"({sum(len(dec[d]['codes']) for d in imgs if dec[d]['decision'] == 'needs_review'):,}) · {stale} stale "
        f"removed · {out / 'decisions.json'}")
    if stop_flag.is_set():
        log("!! stopped early (see above)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
