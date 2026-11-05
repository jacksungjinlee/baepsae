#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""logo.dev coverage check through logo.dev's official API and its secret key (Jack's logo plan). Run by hand only:
from the workflow "logo.dev 확인" (.github/workflows/logo-dev-check.yml), or from a terminal:

  LOGO_DEV_SECRET_KEY=sk_... python3 tools/logos/logodev_api_check.py --out DIR \
      [--sample 300] [--seed 20261105] [--max-credits 480] [--save-images 50]
  python3 tools/logos/logodev_api_check.py --plan-only      # the sample and its credit ceiling; no logo.dev call
  python3 tools/logos/logodev_api_check.py --verdict DIR/run.json     # exit 1 when that run stopped on an error

What it does
  1. Sample. From the live data.json (or --data): every Korean common share and every US stock, ETFs and funds left
     out (logo_sources.build_companies: the logo picker's exact identifiers). A stratified random sample with a fixed
     seed, printed: about a third US, a third Korea top 1,000 by market cap, a third Korea rest. A Korean company
     without a market cap cannot be ranked, and a company without a ticker cannot be looked up: both are left out,
     counted. The three groups are looked up in turn, so a run that stops early still covers all three.
  2. Lookup, one company at a time, by exact identifier only (never a name search), GET /v2/brands/logo:
       ticker  KOSPI and KONEX 005930.KS · KOSDAQ 247540.KQ · US bare (AAPL);
       domain  Korea only: the DART homepage (kr_homepages.csv, domain_ok = 1), and only after the ticker found no
               brand (a free not_found).
  3. Writes to --out: summary.md (coverage per group, credits, requests, what each status means), results.csv and
     results.json (one row per sampled company), up to --save-images logo files in images/ (spread over the three
     groups), sheet.html (contact sheet, images inlined), sheet.png (drawn with Pretendard from fonts/pretendard/ by
     file path; stops if a Korean letter was drawn in another font), run.json (outcome) and run.log.

logo.dev facts it follows (logo.dev/docs, read 2026-11-05: brand/introduction, api-reference/logos/get-a-logo,
platform/errors, platform/credits, platform/rate-limits, platform/conventions):
  - 200: the image object is `data` itself (object image, status ready, url = a signed download address that expires
    after about 24 hours, source = width, height, format). Billed: 2 credits.
  - 404, data.status not_found, Credits-Charged 0: no brand matches. Free.
  - 404, Credits-Charged 1: a brand matches but has no logo image. Billed: 2 credits.
  - 202, data.status not_indexed, Retry-After: logo.dev is indexing the brand. Retried after Retry-After seconds, at
    most twice (retries are not billed); the run goes on with other companies meanwhile. A Retry-After above 60 s is
    not waited for (never retried sooner than asked): the company ends as not_indexed.
  - A brand is billed once per 24 hours; a repeat inside that time is free, so a repeat 404 for a brand without a logo
    looks like "no brand" (not_found). Run this at most once in 24 hours for the same sample (REPEAT_NOTE).
  - 402 insufficient_credits: the whole run stops cleanly and reports. 429 rate_limited: waits Retry-After, or
    RateLimit-Reset when RateLimit-Remaining is 0, else backs off.
  - Community plan: 500 credits a month, 100 API requests a minute, 5 open at once. This tool sends one request at a
    time, at most 60 a minute (image downloads included), and stops before --max-credits could be passed.
  - "On every plan, you can store anything the Logo.dev API returns, logo files included." Downloads from the signed
    addresses are not billed and carry no key (the signature is the credential); the addresses are never written.

The key
  Read only from the environment variable LOGO_DEV_SECRET_KEY, then removed from this process's environment, so the
  browser that draws sheet.png never inherits it. It goes only into the Authorization header of api.logo.dev requests.
  Never printed, logged or written: every printed or written line passes a masker, and at the end every output file
  is searched for it. A value that looks like a secret key (sk_...) anywhere on the command line is refused.

No silent failure: counts are logged as it goes; an answer the docs don't describe stops the run with a clear message,
and the results so far are saved. No new lookup starts after --time-limit-min (40), so a slow run still saves and
uploads its results before the workflow's 60-minute limit. Exit code 0 when the run finished or stopped cleanly
(credit cap, 402); 1 when it stopped on an error, hit the time limit, or more than half the chosen images or sheet.png
failed. With --defer-failure (the workflow) it exits 0 once everything is saved, so the results can be
uploaded, and the workflow's last step (--verdict run.json) fails the run.
Unit tests: tests/test_logodev_check.py (no network; the HTTP client is faked).
"""
import argparse
import base64
import collections
import contextlib
import csv
import heapq
import html
import io
import json
import os
import pathlib
import random
import re
import sys
import time
import traceback
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import logo_sources as lsrc  # noqa: E402
from logo_ids import Masker, _cap, now_kst  # noqa: E402

API_BASE = "https://api.logo.dev/v2"
LOGO_ROUTE = "/brands/logo"
ROUTES = ("ticker", "domain")                  # exact identifiers only: never name
IMAGE_HOSTS = ("img.logo.dev",)                # where the signed download addresses point (docs, 2026-11-05)
KEY_ENV = "LOGO_DEV_SECRET_KEY"
CACHE_DIR = pathlib.Path(os.environ.get("BAEPSAE_LOGO_CACHE", pathlib.Path.home() / ".cache" / "baepsae-logos"))

CREDITS_PER_LOOKUP = 2                         # GET /v2/brands/logo
DEFAULT_SAMPLE, DEFAULT_SEED, DEFAULT_MAX_CREDITS, DEFAULT_IMAGES = 300, 20261105, 480, 50
KR_TOP = 1000
PER_MINUTE = 60                                # requests in any 60 seconds (logo.dev allows 100 on Community)
MIN_INTERVAL_S = 1.05                          # between request starts
RETRIES_202 = 2
MAX_WAIT_202_S = 60
RETRIES_429 = 5
MAX_WAIT_429_S = 120
RETRIES_TRANSIENT = 2                          # no answer, or HTTP 5xx
BACKOFF_S = (5, 15)
ERROR_STOP = 5                                 # companies in a row that end in error -> stop
TIMEOUT_S = 30                                 # logo.dev: at least 15 s, it may prepare a brand at request time
DOWNLOAD = {"size": "256", "format": "png"}
MAX_IMAGE_BYTES = 2_000_000
MAX_ANSWER_BYTES = 1_000_000                   # an API answer is a small JSON document
TIME_LIMIT_MIN = 40                            # lookups stop by then; the workflow's job limit is 60 minutes
MUST = {"kr": ("005930", "000660", "005380"), "us": ("AAPL", "MSFT")}
MIN_COMPANIES = {"kr": 2000, "us": 500}

GROUPS = (("US", "US"), ("KR-TOP", "Korea top 1,000 by market cap"), ("KR-REST", "Korea rest"))
GROUP_LABEL = dict(GROUPS)
STATUSES = ("logo", "not_found", "no_image", "not_indexed", "error")
STATUS_MEANING = {
    "logo": "logo.dev returned a logo for the identifier (HTTP 200). Billed: 2 credits.",
    "not_found": "No brand matches the identifier (HTTP 404, data.status not_found, Credits-Charged 0). Free. For a "
                 "Korean company this is the final status only when the DART-homepage domain also found nothing, "
                 "or there was no usable domain.",
    "no_image": "A brand matches, but logo.dev has no logo image for it (HTTP 404, Credits-Charged 1). Billed: 2 "
                "credits. The domain is not tried after this: it would reach the same brand.",
    "not_indexed": f"logo.dev was still indexing the brand after {RETRIES_202} retries (HTTP 202). Free. Asking again "
                   "later may find a logo.",
    "error": "No usable answer: HTTP 400 for this identifier, or no answer or a server error after "
             f"{RETRIES_TRANSIENT} retries. A request that got no answer is counted as 2 credits in case it was billed.",
}
REPEAT_NOTE = ("logo.dev bills a brand once per 24 hours, and a repeat answer inside that time is free (Credits-Charged "
               "0). A repeat answer for a brand without a logo is then a free 404, the same as no brand at all, so it "
               "reads as not_found. In a first run this is rare (two sampled companies would have to reach the same "
               "brand). Run this check at most once in 24 hours for the same sample, or no_image companies from the "
               "earlier run come back as not_found.")
PNG, JPEG, WEBP = b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"WEBP"

SK_LIKE = re.compile(r"(?<![A-Za-z0-9])sk_[A-Za-z0-9_\-]{4,}")
KEY_SHAPE = re.compile(r"sk_[A-Za-z0-9_\-]{8,200}")


# ── the key ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def refuse_key_in_args(argv):
    """The key comes only from the environment. A value that looks like one anywhere else stops the run (unshown)."""
    for a in argv:
        if SK_LIKE.search(str(a)):
            raise SystemExit("!! Something on the command line looks like a secret key (sk_...). The key is read "
                             f"only from the environment variable {KEY_ENV}, never from an argument or a file. "
                             "Nothing was looked up, and the value is not shown.")


def read_secret_key(environ):
    """The secret key from environ[KEY_ENV], checked for shape. Refuses (SystemExit, plain words, value never shown)
    when it is missing, a publishable key (pk_...), or not shaped like sk_..."""
    v = str(environ.get(KEY_ENV) or "").strip()
    if not v:
        raise SystemExit(f"!! {KEY_ENV} is not set, so nothing was looked up. This check needs logo.dev's secret key "
                         f"(sk_...) in that environment variable; in GitHub it is the repository secret {KEY_ENV}.")
    if v.startswith("pk_"):
        raise SystemExit(f"!! {KEY_ENV} holds a publishable key (pk_...). The logo.dev API takes only the secret key "
                         "(sk_...). Nothing was looked up.")
    if not KEY_SHAPE.fullmatch(v):
        raise SystemExit(f"!! {KEY_ENV} does not look like a logo.dev secret key (sk_ then letters, digits, _ or -). "
                         "Nothing was looked up, and the value is not shown.")
    return v


def find_key_in_files(folder, key):
    """Output files that contain the key, raw or URL-encoded (there should be none)."""
    if not key:
        return []
    needles = {key.encode("utf-8"), quote(key, safe="").encode("utf-8")}
    return [p for p in sorted(pathlib.Path(folder).rglob("*"))
            if p.is_file() and any(n in p.read_bytes() for n in needles)]


class Log:
    """Prints a line and keeps it for run.log; every line passes the masker first."""

    def __init__(self, mask=None):
        self.mask = mask or str
        self.lines = []

    def __call__(self, text=""):
        t = self.mask(str(text))
        print(t, flush=True)
        self.lines.append(t)


# ── companies and the sample ───────────────────────────────────────────────────────────────────────────────────────

cap_of = _cap                                  # the logo picker's rule: a finite market cap above 0, else None
MAX_KR_NOCAP = 25                              # more Korean companies without a market cap -> refuse to rank


def rank_korea(companies):
    """Korean companies with a ticker and a market cap, largest first (ties by code), with rank 1, 2, ..."""
    kr = sorted((c for c in companies if c["side"] == "kr" and c.get("ticker") and cap_of(c) is not None),
                key=lambda c: (-cap_of(c), str(c["code"])))
    return [dict(c, rank=i) for i, c in enumerate(kr, 1)]


def check_ranking(companies, kr_top=KR_TOP):
    """The Korea top-1,000 group is ranked by market cap, a field that can be blank: refuse when too many Korean
    companies have none, or when a must-have company is not in the top group (CLAUDE.md). Returns a log line."""
    nocap = [c["code"] for c in companies if c["side"] == "kr" and cap_of(c) is None]
    if len(nocap) > MAX_KR_NOCAP:
        raise SystemExit(f"!! {len(nocap):,} Korean companies have no market cap (at most {MAX_KR_NOCAP} allowed), so "
                         f"a top {kr_top:,} by market cap would be wrong. data.json may be a pre-market file.")
    top = {c["code"]: c["rank"] for c in rank_korea(companies)[:kr_top]}
    lost = [m for m in MUST["kr"] if m not in top]
    if lost:
        raise SystemExit(f"!! must-have Korean companies are not in the top {kr_top:,} by market cap: {lost}")
    return f"· Korea top {kr_top:,}: " + ", ".join(f"{m} rank {top[m]}" for m in MUST["kr"]) + \
        f" · without a market cap: {len(nocap)}"


def load_companies(data, listing, homepages, min_counts=None):
    """data.json + KRX listing + DART homepages -> (companies, log lines). Funds and ETFs left out. Refuses data that
    is plainly incomplete (too few companies, or a must-have company missing)."""
    min_counts = MIN_COMPANIES if min_counts is None else min_counts
    stocks = data.get("stocks") or []
    funds = sum(1 for s in stocks if s.get("fund") and not s.get("etf") and s.get("cls") in ("kr", "us"))
    companies, log = lsrc.build_companies(dict(data, stocks=[s for s in stocks if not s.get("fund")]), listing, homepages)
    log.append(f"· funds left out (besides ETFs): {funds:,}")
    for side in ("kr", "us"):
        codes = {c["code"] for c in companies if c["side"] == side}
        lost = [m for m in MUST[side] if m not in codes]
        if lost or len(codes) < min_counts[side]:
            raise SystemExit(f"!! data.json looks incomplete: {len(codes):,} {side.upper()} companies "
                             f"(at least {min_counts[side]:,} expected), missing {lost}")
    return companies, log


def interleave(lists):
    """[[a1, a2], [b1], [c1, c2]] -> [a1, b1, c1, a2, c2]."""
    lists = [list(x) for x in lists]
    out = []
    while any(lists):
        for x in lists:
            if x:
                out.append(x.pop(0))
    return out


def group_sizes(n):
    us = top = round(n / 3)
    return {"US": us, "KR-TOP": top, "KR-REST": n - us - top}


def draw_sample(companies, n, seed, kr_top=KR_TOP):
    """Stratified random sample. Same companies + same n + same seed -> the same sample, in the same order.
    Returns (order, groups, left_out):
      order: [{**company, group, rank}], the three groups taken in turn (US, KR-TOP, KR-REST, US, ...);
      groups: {gid: {label, population, sampled}};
      left_out: {reason: [codes]} (companies that cannot be sampled, said loudly)."""
    if n < 3:
        raise SystemExit(f"!! --sample must be at least 3 (one per group), not {n}")
    no_ticker = sorted(c["code"] for c in companies if not c.get("ticker"))
    usable = [c for c in companies if c.get("ticker")]
    kr_nocap = sorted(c["code"] for c in usable if c["side"] == "kr" and cap_of(c) is None)
    ranked = rank_korea(usable)
    pools = {"US": [dict(c, rank=None) for c in sorted((c for c in usable if c["side"] == "us"),
                                                      key=lambda c: str(c["code"]))],
             "KR-TOP": ranked[:kr_top], "KR-REST": ranked[kr_top:]}
    want = group_sizes(n)
    rng = random.Random(seed)
    picked, groups = [], {}
    for gid, label in GROUPS:
        if want[gid] > len(pools[gid]):
            raise SystemExit(f"!! group {gid} has {len(pools[gid]):,} companies, fewer than the {want[gid]:,} to draw")
        picked.append([dict(c, group=gid) for c in rng.sample(pools[gid], want[gid])])
        groups[gid] = {"label": label, "population": len(pools[gid]), "sampled": want[gid]}
    left_out = {"no ticker (market unknown)": no_ticker, "Korea, no market cap (cannot be ranked)": kr_nocap}
    return interleave(picked), groups, left_out


# ── HTTP ────────────────────────────────────────────────────────────────────────────────────────────────────────────

class Resp:
    """One HTTP answer: status, headers (lower-case names) and body bytes."""

    def __init__(self, status, headers=None, body=b""):
        self.status = int(status)
        self.headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        self.body = body if isinstance(body, bytes) else str(body).encode("utf-8")

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None


def requests_transport(url, params=None, headers=None, timeout=TIMEOUT_S, max_bytes=MAX_ANSWER_BYTES):
    """The real network: one GET, no redirects followed (a redirect is an unexpected answer), no shared session, and
    at most max_bytes of the body read (a longer body is cut, so it fails the JSON or image check)."""
    import requests
    with requests.get(url, params=params, headers=headers or {}, timeout=timeout, allow_redirects=False,
                      stream=True) as r:
        return Resp(r.status_code, r.headers, r.raw.read(max_bytes, decode_content=True))


class Pacer:
    """One request at a time (the caller waits for each answer), at least MIN_INTERVAL_S between starts and at most
    PER_MINUTE starts in any 60 seconds. hold() delays the next start (logo.dev said the minute's requests are used)."""

    def __init__(self, clock=time.monotonic, sleep=time.sleep, per_minute=PER_MINUTE, interval=MIN_INTERVAL_S):
        self.clock, self._sleep_fn = clock, sleep
        self.per_minute, self.interval = per_minute, interval
        self.starts = collections.deque()
        self.not_before = None
        self.waited = 0.0

    def sleep(self, seconds):
        if seconds > 0:
            self._sleep_fn(seconds)
            self.waited += seconds

    def hold(self, seconds):
        t = self.clock() + seconds
        self.not_before = t if self.not_before is None else max(self.not_before, t)

    def wait(self):
        now = self.clock()
        if self.not_before is not None and now < self.not_before:
            self.sleep(self.not_before - now)
            now = self.clock()
        if self.starts and now - self.starts[-1] < self.interval:
            self.sleep(self.interval - (now - self.starts[-1]))
            now = self.clock()
        while self.starts and now - self.starts[0] >= 60:
            self.starts.popleft()
        if len(self.starts) >= self.per_minute:
            self.sleep(60 - (now - self.starts[0]))
            now = self.clock()
            while self.starts and now - self.starts[0] >= 60:
                self.starts.popleft()
        self.starts.append(now)


class Client:
    """api.logo.dev lookups (the only requests that carry the key) and image downloads (no key, no extra header)."""

    def __init__(self, key, send, pacer):
        self._auth = "Bearer " + key
        self.send = send
        self.pacer = pacer
        self.api_requests = 0
        self.downloads = 0

    def __repr__(self):
        return "Client(api.logo.dev)"

    def lookup(self, route, ident):
        if route not in ROUTES:
            raise ValueError(f"route {route!r} is not an exact identifier ({', '.join(ROUTES)})")
        self.pacer.wait()
        self.api_requests += 1
        return self.send(API_BASE + LOGO_ROUTE, params={route: ident},
                         headers={"Authorization": self._auth, "Accept": "application/json"}, timeout=TIMEOUT_S,
                         max_bytes=MAX_ANSWER_BYTES)

    def download(self, url):
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname not in IMAGE_HOSTS:
            raise ValueError("not a logo.dev image address")
        q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k not in DOWNLOAD] + list(DOWNLOAD.items())
        self.pacer.wait()
        self.downloads += 1
        return self.send(urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), "")), params=None, headers={},
                         timeout=TIMEOUT_S, max_bytes=MAX_IMAGE_BYTES + 1)


# ── reading an answer ──────────────────────────────────────────────────────────────────────────────────────────────

class Unexpected(Exception):
    """logo.dev answered in a way its docs don't describe: the run stops (the results so far are saved)."""


class StopRun(Exception):
    def __init__(self, outcome, reason):
        super().__init__(reason)
        self.outcome, self.reason = outcome, reason


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def describe(resp):
    """A short, safe description of an answer for error messages: status, keys, billing header. No body text."""
    j = resp.json()
    top = sorted(j) if isinstance(j, dict) else ("not JSON" if j is None else type(j).__name__)
    data = sorted(j["data"]) if isinstance(j, dict) and isinstance(j.get("data"), dict) else None
    st = j["data"].get("status") if data is not None else None
    return (f"HTTP {resp.status}, keys {top}, data keys {data}, data.status {st!r}, "
            f"Credits-Charged {resp.headers.get('credits-charged')!r}")


def read_image(j):
    """The image object of a 200 answer -> {url, width, height, format, is_vector, etag, shape}. Raises Unexpected.
    Documented shape: `data` is the image (object image, status ready). The shape GET /v2/brands uses (`data.logo`)
    is accepted too, and counted."""
    data = j.get("data") if isinstance(j, dict) else None
    if not isinstance(data, dict):
        raise Unexpected("HTTP 200 without a data object")
    img, shape, kind = data, "data", data.get("kind")
    if "url" not in data and isinstance(data.get("logo"), dict):
        img, shape, kind = data["logo"], "data.logo", "logo"
    elif data.get("object") != "image" or data.get("status") != "ready" or kind != "logo":
        raise Unexpected(f"HTTP 200 whose data is not a ready logo image (object {data.get('object')!r}, "
                         f"kind {kind!r}, status {data.get('status')!r}, keys {sorted(data)})")
    url, src = img.get("url"), img.get("source")
    if not isinstance(url, str) or not isinstance(src, dict):
        raise Unexpected(f"HTTP 200 without an image url and source (keys {sorted(img)})")
    u = urlsplit(url)
    if u.scheme != "https" or u.hostname not in IMAGE_HOSTS:
        raise Unexpected(f"HTTP 200 whose image address is not https://{IMAGE_HOSTS[0]} (host {u.hostname!r})")
    size = []
    for x in (src.get("width"), src.get("height")):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not 0 < x < 1e6 or x != int(x):
            raise Unexpected(f"HTTP 200 with an image size that is not two positive whole numbers "
                             f"({src.get('width')!r} x {src.get('height')!r})")
        size.append(int(x))
    return {"url": url, "width": size[0], "height": size[1], "format": str(src.get("format") or ""),
            "is_vector": bool(src.get("is_vector")), "etag": str(img.get("etag") or ""), "shape": shape,
            "kind": kind}


def classify(resp):
    """One answer -> (kind, info). kind: logo · not_found · no_image · retry (202) · rate_limited · out_of_credits ·
    refused (401/403) · bad_request (400) · server_error (5xx). Raises Unexpected for anything else."""
    st, cc, j = resp.status, resp.headers.get("credits-charged"), resp.json()
    err = j.get("error") if isinstance(j, dict) and isinstance(j.get("error"), dict) else {}
    if st == 200:
        return "logo", {"image": read_image(j)}
    if st == 404:
        if not isinstance(j, dict) or not isinstance(j.get("data"), dict) or err:
            raise Unexpected(f"a 404 without the lookup envelope ({describe(resp)})")
        if cc == "1":
            return "no_image", {}
        if cc == "0" and j["data"].get("status") == "not_found":
            return "not_found", {}
        raise Unexpected(f"a 404 that is neither a free not_found nor a billed brand without a logo ({describe(resp)})")
    if st == 202:
        data = j.get("data") if isinstance(j, dict) else None
        if not isinstance(data, dict) or data.get("status") != "not_indexed":
            raise Unexpected(f"a 202 that is not not_indexed ({describe(resp)})")
        meta = j.get("metadata") if isinstance(j.get("metadata"), dict) else {}
        pend = meta.get("pending") if isinstance(meta.get("pending"), dict) else {}
        wait, source = _int(resp.headers.get("retry-after")), "Retry-After"
        if wait is None or wait < 1:
            wait, source = _int(pend.get("retry_after_seconds")), "metadata.pending.retry_after_seconds"
        if wait is None or wait < 1:
            wait, source = 30, "none given: 30 s, logo.dev's documented value"
        return "retry", {"wait": wait, "wait_source": source}
    code = str(err.get("code") or "")
    if st == 402:
        return "out_of_credits", {"code": code}
    if st == 429:
        return "rate_limited", {"code": code}
    if st in (401, 403):
        return "refused", {"code": code}
    if st == 400:
        return "bad_request", {"code": code, "message": str(err.get("message") or "")}   # cut after masking
    if 500 <= st < 600:
        return "server_error", {"code": code}
    raise Unexpected(f"HTTP {st} ({describe(resp)})")


def rate_limit_wait(headers, attempt, jitter):
    """Seconds to wait after a 429: Retry-After; else RateLimit-Reset unless RateLimit-Remaining says requests are
    left in the minute (0 or missing: the minute is used up); else too many open lookups: exponential backoff with
    jitter (logo.dev's advice)."""
    ra = _int(headers.get("retry-after"))
    if ra is not None and ra >= 0:
        return float(max(ra, 1)), "Retry-After"
    rem, reset = _int(headers.get("ratelimit-remaining")), _int(headers.get("ratelimit-reset"))
    if reset is not None and reset >= 0 and not (rem and rem > 0):
        return float(max(reset, 1)), "RateLimit-Reset"
    return float(min(2 ** attempt, 32)) + jitter(), "backoff"


# ── the run ─────────────────────────────────────────────────────────────────────────────────────────────────────────

class Task:
    """One sampled company on its way through the lookups."""

    def __init__(self, c):
        self.c = c
        self.stage = "ticker"
        self.tries_202 = 0
        self.wait = 0
        self.lookups = []
        self.results = {}
        self.credits = 0
        self.requests = 0
        self.final = None
        self.route = ""
        self.image = None
        self.note = ""


class Checker:
    """Looks the sample up, one request at a time, and keeps every count the summary needs."""

    def __init__(self, client, max_credits, log, clock=time.monotonic, sleep=None, jitter=None, deadline=None):
        self.client, self.max_credits, self.log, self.clock = client, max_credits, log, clock
        self.deadline = deadline                 # clock() value after which no new request starts
        self._sleep = sleep or client.pacer.sleep
        self.jitter = jitter or random.SystemRandom().random
        self.credits_billed = 0            # 2 per answer that was (or may have been) billed
        self.credits_unknown = 0           # 2 per lookup where a request got no answer (it may have been billed)
        self.server_charged = 0            # answers with Credits-Charged: 1
        self.balance_first = self.balance_last = None
        self.shapes = collections.Counter()
        self.counts = collections.Counter()
        self.done = []
        self.remaining = []
        self.stop = None
        self.error_streak = 0
        self.total = 0

    @property
    def credits_counted(self):
        return self.credits_billed + self.credits_unknown

    def can_spend(self):
        return self.credits_counted + CREDITS_PER_LOOKUP <= self.max_credits

    def sleep(self, seconds):
        if seconds > 0:
            self._sleep(seconds)

    def tally(self):
        return collections.Counter(t.final for t in self.done)

    # one request (with its 429 / 5xx / no-answer retries) -> (kind, info)
    def call(self, route, ident):
        rl = tr = 0
        unanswered = False
        while True:
            if not self.can_spend():
                raise StopRun("max_credits", f"reached --max-credits {self.max_credits}: {self.credits_counted} "
                                             f"credits counted, and the next lookup could cost {CREDITS_PER_LOOKUP} more")
            if self.deadline is not None and self.clock() >= self.deadline:
                raise StopRun("time_limit", "reached the time limit (--time-limit-min), so the results so far can "
                                            "still be saved and uploaded before the workflow's own limit")
            try:
                resp = self.client.lookup(route, ident)
            except Exception as e:                       # noqa: BLE001 — no answer: counted, masked, retried, kept
                self.counts["no answer (network)"] += 1
                if not unanswered:                       # it may have reached logo.dev and been billed: count it
                    unanswered = True                    # now (once: a repeat of the same brand is free for 24 h)
                    self.credits_unknown += CREDITS_PER_LOOKUP
                if tr < RETRIES_TRANSIENT:
                    self.log(f"  !! {route} {ident}: no answer ({type(e).__name__}); trying again in {BACKOFF_S[tr]} s")
                    self.sleep(BACKOFF_S[tr])
                    tr += 1
                    self.counts["retries after an error"] += 1
                    continue
                return "error", {"note": f"no answer after {tr + 1} tries ({type(e).__name__}); counted as "
                                         f"{CREDITS_PER_LOOKUP} credits in case it was billed"}
            self.counts[f"HTTP {resp.status}"] += 1
            cc = resp.headers.get("credits-charged")
            if cc == "1":
                self.server_charged += 1
            bal = resp.headers.get("credits-remaining")
            if bal:
                self.balance_last = bal
                self.balance_first = self.balance_first or bal
            if resp.status == 200 or cc == "1" or (resp.status == 404 and cc != "0"):
                self.credits_billed += CREDITS_PER_LOOKUP
            if resp.status != 429:
                self._respect_window(resp.headers)
            kind, info = classify(resp)
            info["http"] = resp.status
            if kind in ("logo", "not_found", "no_image", "retry"):
                if kind == "logo":
                    self.shapes[info["image"]["shape"]] += 1
                return kind, info
            if kind == "bad_request":
                msg = self.log.mask(info["message"])[:160]          # masked first, so a cut never splits the key
                return "error", {"note": f"logo.dev answered 400 {self.log.mask(info['code'])} {msg!r}", "http": 400}
            if kind == "out_of_credits":
                raise StopRun("out_of_credits", "logo.dev answered 402 (insufficient_credits): the account has no "
                                                "API credits left. They come back when the monthly grant renews.")
            if kind == "refused":
                raise StopRun("error", f"logo.dev refused the request (HTTP {resp.status}"
                                       f"{' ' + info['code'] if info['code'] else ''}). Check that the repository "
                                       f"secret {KEY_ENV} holds logo.dev's secret key (sk_...) and is not disabled.")
            if kind == "rate_limited":
                rl += 1
                if rl > RETRIES_429:
                    raise StopRun("error", f"logo.dev answered 429 (rate_limited) {rl} times in a row")
                wait, why = rate_limit_wait(resp.headers, rl, self.jitter)
                if wait > MAX_WAIT_429_S:
                    raise StopRun("error", f"logo.dev asked to wait {wait:.0f} s ({why}), more than {MAX_WAIT_429_S} s")
                self.log(f"  · 429 rate_limited: waiting {wait:.1f} s ({why})")
                self.counts["retries after 429"] += 1
                self.sleep(wait)
                continue
            # server_error
            if tr < RETRIES_TRANSIENT:
                self.log(f"  !! {route} {ident}: HTTP {resp.status}; trying again in {BACKOFF_S[tr]} s")
                self.sleep(BACKOFF_S[tr])
                tr += 1
                self.counts["retries after an error"] += 1
                continue
            return "error", {"note": f"logo.dev answered HTTP {resp.status} {tr + 1} times", "http": resp.status}

    def _respect_window(self, headers):
        rem, reset = _int(headers.get("ratelimit-remaining")), _int(headers.get("ratelimit-reset"))
        if rem == 0 and reset is not None and reset > 0:
            self.counts["holds (RateLimit-Remaining 0)"] += 1
            self.client.pacer.hold(min(reset, MAX_WAIT_429_S))

    # one lookup for one task -> "retry" (202, try later) · "domain" (look up the domain next) · "done"
    def step(self, t):
        c = t.c
        route = t.stage
        ident = c["ticker"] if route == "ticker" else c["domain"]
        cr, rq = self.credits_counted, self.client.api_requests
        try:
            kind, info = self.call(route, ident)
        except Exception as e:                           # the run stops here: keep what this company already sent
            if self.client.api_requests > rq:
                t.lookups.append({"route": route, "id": ident, "http": None,
                                  "result": f"stopped ({getattr(e, 'outcome', type(e).__name__)})"})
            raise
        finally:
            t.credits += self.credits_counted - cr
            t.requests += self.client.api_requests - rq
        t.lookups.append({"route": route, "id": ident, "http": info.get("http"),
                          "result": "not_indexed (retry)" if kind == "retry" else kind})
        if kind == "retry":
            if info["wait_source"] != "Retry-After":
                self.counts["202 without Retry-After"] += 1
                self.log(f"  !! {route} {ident}: 202 without a Retry-After header; waiting {info['wait']} s "
                         f"({info['wait_source']})")
            if info["wait"] > MAX_WAIT_202_S:            # never ask again sooner than logo.dev said
                self.counts["202 not retried (wait too long)"] += 1
                info["note"] = f"logo.dev asked to wait {info['wait']} s (more than {MAX_WAIT_202_S} s): not retried"
                kind = "not_indexed"
            elif t.tries_202 < RETRIES_202:
                t.tries_202 += 1
                t.wait = max(info["wait"], 1)
                self.counts["202 retries"] += 1
                return "retry"
            else:
                kind = "not_indexed"
        t.results[route] = kind
        if route == "ticker" and kind == "not_found" and c["side"] == "kr" and c.get("domain"):
            t.stage, t.tries_202 = "domain", 0
            return "domain"
        t.final, t.route, t.image, t.note = kind, route, info.get("image"), info.get("note", "")
        self.finish(t)
        return "done"

    def finish(self, t):
        self.done.append(t)
        c = t.c
        how = " → ".join(f"{x['route']} {x['id']}: {x['result']}" for x in t.lookups)
        self.log(f"· [{len(self.done):>3}/{self.total}] {c['group']:<7} {c['code']:<7} {c['name']} · {how}"
                 f" · credits {self.credits_counted}/{self.max_credits}")
        if t.final == "error":
            self.log(f"  !! {c['code']}: {t.note}")
            self.error_streak += 1
            if self.error_streak >= ERROR_STOP:
                self.stop = StopRun("error", f"{ERROR_STOP} companies in a row ended in an error")
        else:
            self.error_streak = 0
        if len(self.done) % 25 == 0:
            n = self.tally()
            self.log(f"· progress: {len(self.done)}/{self.total} checked · "
                     + " · ".join(f"{s} {n[s]}" for s in STATUSES)
                     + f" · credits {self.credits_counted}/{self.max_credits} · requests {self.client.api_requests}")

    def run(self, order):
        """Looks every company in `order` up. A 202 waits in `pending` while the others go on. Stops on StopRun or
        an unexpected answer; whatever was not finished is in self.remaining."""
        self.total = len(order)
        queue = collections.deque(Task(c) for c in order)
        pending, n, task = [], 0, None
        try:
            while (queue or pending) and not self.stop:
                now = self.clock()
                if pending and pending[0][0] <= now:
                    task = heapq.heappop(pending)[2]
                elif queue:
                    task = queue.popleft()
                else:
                    self.sleep(pending[0][0] - now)
                    continue
                nxt = self.step(task)
                if nxt == "retry":
                    n += 1
                    heapq.heappush(pending, (self.clock() + task.wait, n, task))
                elif nxt == "domain":
                    queue.appendleft(task)
                task = None
        except StopRun as s:
            self.stop = s
        except Unexpected as u:
            self.stop = StopRun("unexpected", f"logo.dev answered in a way its docs don't describe: {u}. "
                                              f"(company {task.c['code']}, {task.stage} lookup)")
        finally:                                         # also on a crash: every company stays in the results
            self.remaining = ([task] if task is not None else []) + [p[2] for p in sorted(pending)] + list(queue)
            if self.stop:
                self.log(f"!! stopped: {self.stop.reason}")


# ── results ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def result_rows(checker):
    """One row per sampled company: finished ones with their status, the others with an empty status and a note."""
    rows = []
    for t in checker.done + checker.remaining:
        c = t.c
        img = t.image or {}
        note = t.note
        if t.final is None:
            note = ("unfinished: " + "; ".join(f"{x['route']} {x['result']}" for x in t.lookups)) if t.lookups \
                else "not checked: the run stopped first"
        rows.append({"group": c["group"], "rank": c.get("rank") or "", "code": c["code"], "name": c["name"],
                     "side": c["side"], "market": c.get("market", ""), "cap": cap_of(c) if cap_of(c) else "",
                     "ticker": c.get("ticker", ""), "domain": c.get("domain", ""), "status": t.final or "",
                     "route": t.route, "ticker_status": t.results.get("ticker", ""),
                     "domain_status": t.results.get("domain", ""), "credits": t.credits, "requests": t.requests,
                     "kind": img.get("kind", ""), "width": img.get("width", ""), "height": img.get("height", ""),
                     "format": img.get("format", ""), "is_vector": img.get("is_vector", ""),
                     "etag": img.get("etag", ""), "image_file": "", "saved_px": "",
                     "note": note, "_url": img.get("url", ""), "_lookups": t.lookups})
    return rows


def coverage(rows):
    """Per group and for all: companies in the sample, companies checked (a final status), and the count and share
    (of those checked, in %, one decimal) of each status."""
    out = {}
    for gid in [g for g, _ in GROUPS] + ["ALL"]:
        mine = [r for r in rows if gid == "ALL" or r["group"] == gid]
        done = [r for r in mine if r["status"] in STATUSES]
        n = len(done)
        counts = {s: sum(1 for r in done if r["status"] == s) for s in STATUSES}
        out[gid] = {"sampled": len(mine), "checked": n, "counts": counts,
                    "pct": {s: (round(100.0 * counts[s] / n, 1) if n else None) for s in STATUSES}}
    return out


def spread(k, available):
    """k image slots over the groups (in GROUPS order), one at a time in turn, never more than a group has."""
    quota = {g: 0 for g in available}
    left = max(int(k), 0)
    while left:
        open_ = [g for g in available if quota[g] < available[g]]
        if not open_:
            break
        for g in open_:
            if not left:
                break
            quota[g] += 1
            left -= 1
    return quota


def pick_images(rows, k, seed):
    """Up to k logo rows, spread over the three groups, chosen at random (fixed seed) within each group."""
    logos = {gid: [r for r in rows if r["group"] == gid and r["status"] == "logo"] for gid, _ in GROUPS}
    quota = spread(k, {gid: len(v) for gid, v in logos.items()})
    rng = random.Random(f"images:{seed}")
    chosen = []
    for gid, _ in GROUPS:
        chosen += sorted(rng.sample(logos[gid], quota[gid]), key=lambda r: (r["rank"] or 0, r["code"]))
    return chosen


def image_kind(resp):
    """(extension, mime) of a downloaded image, or None when the answer is not a plain image file."""
    if resp.status != 200 or not resp.headers.get("content-type", "").startswith("image/"):
        return None
    b = resp.body
    if not 0 < len(b) <= MAX_IMAGE_BYTES:
        return None
    if b.startswith(PNG):
        return "png", "image/png"
    if b.startswith(JPEG):
        return "jpg", "image/jpeg"
    if b[:4] == b"RIFF" and b[8:12] == WEBP:
        return "webp", "image/webp"
    return None


def png_size(b):
    """(width, height) from a PNG's header, or None."""
    if b.startswith(PNG) and len(b) >= 24 and b[12:16] == b"IHDR":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    return None


def save_images(chosen, client, folder, log):
    """Downloads each chosen logo once (no key: the signed address is the credential) into folder/images."""
    (folder / "images").mkdir(parents=True, exist_ok=True)
    saved, failed = [], []
    for r in chosen:
        try:
            resp = client.download(r["_url"])
        except Exception as e:                           # noqa: BLE001 — one image: counted, said, the rest go on
            failed.append((r, f"no answer ({type(e).__name__})"))
            continue
        kind = image_kind(resp)
        if not kind:
            failed.append((r, f"HTTP {resp.status} {resp.headers.get('content-type', '')!r}, {len(resp.body):,} bytes"))
            continue
        name = f"{r['group']}_{re.sub(r'[^A-Za-z0-9_.-]', '_', r['code'])}.{kind[0]}"
        (folder / "images" / name).write_bytes(resp.body)
        px = png_size(resp.body)
        r["image_file"], r["saved_px"] = f"images/{name}", f"{px[0]}x{px[1]}" if px else ""
        saved.append({"row": r, "file": name, "mime": kind[1], "bytes": len(resp.body), "data": resp.body, "px": px})
    for r, why in failed:
        log(f"  !! image {r['code']}: not saved: {why}")
    log(f"· images saved: {len(saved)} / {len(chosen)}"
        + (f" ({len(failed)} failed)" if failed else "")
        + " · per group: " + ", ".join(f"{gid} {sum(1 for s in saved if s['row']['group'] == gid)}" for gid, _ in GROUPS))
    return saved, failed


# ── contact sheet ───────────────────────────────────────────────────────────────────────────────────────────────────

SHEET_CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: #FFFFFF; color: #1C2B45; font-size: 13px; line-height: 1.4;
       font-family: 'Pretendard Variable', Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif; }
h1 { font-size: 20px; font-weight: 700; margin: 0 0 4px; }
h2 { font-size: 15px; font-weight: 700; margin: 24px 0 10px; }
.meta { color: #5B6576; margin: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.card { border: 1px solid #E3E6EB; border-radius: 10px; padding: 10px; }
.img { height: 96px; display: flex; align-items: center; justify-content: center; background: #F1F3F6; border-radius: 8px; }
.img img { max-width: 80px; max-height: 80px; display: block; }
.name { font-weight: 700; margin-top: 8px; overflow-wrap: anywhere; }
.line { color: #5B6576; margin-top: 2px; overflow-wrap: anywhere; }
"""


def sheet_html(saved, meta, font_href=None):
    """The contact sheet: every saved logo inlined, with company name, code, route and image size."""
    e = html.escape
    parts = ["<!DOCTYPE html>", '<html lang="ko"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<meta name="robots" content="noindex">', "<title>logo.dev API check</title>"]
    if font_href:
        parts.append(f'<link rel="stylesheet" href="{e(font_href)}">')
    parts += [f"<style>{SHEET_CSS}</style></head><body>", "<h1>logo.dev API check</h1>",
              f'<p class="meta">{e(meta)}</p>']
    if not saved:
        parts.append('<p class="meta">No logo images were saved in this run.</p>')
    for gid, label in GROUPS:
        mine = [s for s in saved if s["row"]["group"] == gid]
        if not mine:
            continue
        parts.append(f"<h2>{e(label)} · {len(mine)}</h2>")
        parts.append('<div class="grid">')
        for s in mine:
            r = s["row"]
            ident = r["ticker"] if r["route"] == "ticker" else r["domain"]
            vec = ", vector" if r["is_vector"] else ""
            b64 = base64.b64encode(s["data"]).decode("ascii")
            parts.append(
                f'<div class="card"><div class="img"><img alt="" src="data:{s["mime"]};base64,{b64}"></div>'
                f'<div class="name">{e(r["name"])}</div>'
                f'<div class="line">{e(r["code"])} · {e(r["route"])} {e(ident)}</div>'
                f'<div class="line">source {r["width"]}×{r["height"]} {e(r["format"])}{vec}</div>'
                f'<div class="line">saved {"×".join(map(str, s["px"])) if s.get("px") else "size not read"} '
                f'{e(s["mime"].split("/")[1])}, {s["bytes"] / 1024:.1f} KB</div></div>')
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def render_png(saved, meta, folder, log):
    """sheet.png with Playwright's Chromium and Pretendard loaded by file path. Every Korean letter must be drawn in
    Pretendard (tools/render_og.py's check) and every image must load; else no picture and a problem is returned."""
    sys.path.insert(0, str(ROOT / "tools"))
    from playwright.sync_api import sync_playwright
    from render_og import CHECK_JS, FAMILY, FONT_CSS
    if not FONT_CSS.exists():
        return f"sheet.png not drawn: {FONT_CSS} is missing"
    tmp = folder / ".sheet-render.html"
    tmp.write_text(sheet_html(saved, meta, font_href=FONT_CSS.as_uri()), encoding="utf-8")
    korean = meta + "".join(s["row"]["name"] for s in saved)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 800}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(tmp.as_uri(), wait_until="load")
            r = page.evaluate(CHECK_JS, [FAMILY, korean])
            log(f"· sheet.png: Korean letters {r['letters']} · drawn in another font: {r['bad'] or 'none'} · "
                f"font files loaded {r['loaded']} · images {sum(1 for ok, w in r['imgs'] if ok and w > 0)}/{len(r['imgs'])}")
            problem = None
            if errors:
                problem = f"sheet.png not drawn: page errors {errors[:3]}"
            elif r["bad"]:
                problem = f"sheet.png not drawn: Pretendard did not draw {r['bad'][:10]}"
            elif not all(ok and w > 0 for ok, w in r["imgs"]):
                problem = "sheet.png not drawn: an image did not load"
            else:
                page.screenshot(path=str(folder / "sheet.png"), full_page=True)
            browser.close()
    finally:
        tmp.unlink(missing_ok=True)
    return problem


# ── summary ─────────────────────────────────────────────────────────────────────────────────────────────────────────

OUTCOME_TEXT = {
    "complete": "Finished: every company in the sample was checked.",
    "max_credits": "Stopped cleanly at the credit cap (--max-credits).",
    "out_of_credits": "Stopped cleanly: logo.dev answered 402, the account is out of API credits.",
    "unexpected": "Stopped on an error: logo.dev answered in a way its docs don't describe.",
    "error": "Stopped on an error.",
    "crashed": "Stopped on an error in this tool.",
    "time_limit": "Stopped at the time limit (--time-limit-min), before the workflow's own limit.",
}
OK_OUTCOMES = ("complete", "max_credits", "out_of_credits")


def _cell(cov, s):
    p = cov["pct"][s]
    return f"{cov['counts'][s]:,} ({p:.1f}%)" if p is not None else f"{cov['counts'][s]:,} (–)"


def summary_md(info):
    """summary.md from the run's facts (info: what run.json holds)."""
    cov = info["coverage"]
    cr, rq, im = info["credits"], info["requests"], info["images"]
    out = ["# logo.dev API check", "",
           f"Run {info['started_kst']} – {info['finished_kst']} KST · seed **{info['seed']}** · sample "
           f"{info['sample']} · data.json prices {info['data']['pxDate']} (US {info['data']['usPxDate']})", "",
           f"**{OUTCOME_TEXT[info['outcome']]}** {info['reason'] or ''}".rstrip(), "",
           f"Companies checked: **{info['checked']:,} of {info['sample']:,}**"
           + (f" ({info['unfinished']:,} unfinished, {info['not_started']:,} not started)"
              if info["checked"] < info["sample"] else ""), ""]
    for p in info["problems"]:
        out.append(f"- !! {p}")
    if info["problems"]:
        out.append("")
    out += ["## Coverage", "", "Shares are of the companies checked in that group.", "",
            "| Group | In sample | Checked | Logo | Not found | No image | Not indexed | Error |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for gid in [g for g, _ in GROUPS] + ["ALL"]:
        c = cov[gid]
        out.append(f"| {GROUP_LABEL.get(gid, 'All')} | {c['sampled']:,} | {c['checked']:,} | "
                   + " | ".join(_cell(c, s) for s in STATUSES) + " |")
    kr = info["korea_routes"]
    out += ["", f"Korea, logo found by ticker: {kr['logo_by_ticker']:,} · by DART-homepage domain: "
                f"{kr['logo_by_domain']:,} (the domain was tried for {kr['domain_tried']:,} companies whose ticker "
                f"found no brand; {kr['no_domain']:,} such companies had no usable domain).", "",
            "## Credits and requests", "",
            f"- Credits counted: **{cr['counted']:,}** of the {info['max_credits']:,} cap — {CREDITS_PER_LOOKUP} per "
            f"logo or no_image answer ({cr['billed_answers']:,} answers) plus {CREDITS_PER_LOOKUP} per request that "
            f"got no answer ({cr['unknown_requests']:,}). An upper bound: logo.dev bills a brand once per 24 hours.",
            f"- logo.dev marked {cr['server_charged']:,} answers as billed (Credits-Charged: 1). Balance it reported "
            f"after the first and after the last answer: {cr['balance_first'] or 'not reported'} → "
            f"{cr['balance_last'] or 'not reported'} (Credits-Remaining).",
            f"- API requests: **{rq['api']:,}** (retries after 202: {rq['retries_202']:,} · after 429: "
            f"{rq['retries_429']:,} · after no answer or a server error: {rq['retries_error']:,}; requests that got "
            f"no answer: {rq['no_answer']:,}; 202 without Retry-After: {rq['no_retry_after']:,}) · image downloads: "
            f"{rq['downloads']:,}. One at a time, at most {PER_MINUTE} a minute; time spent waiting "
            f"{rq['waited_s']:,.0f} s.",
            "- Answer shapes for logos: " + (", ".join(f"{k} {v:,}" for k, v in info["shapes"].items()) or "none")
            + " (data = the documented shape; every one is kind logo, never a brandmark).", "",
            "## Images", "",
            f"{im['saved']:,} of {im['chosen']:,} chosen logos saved in images/ (asked for {im['asked']:,}, spread over "
            f"the three groups: " + ", ".join(f"{GROUP_LABEL[g]} {n}" for g, n in im["per_group"].items())
            + f"). Contact sheet: sheet.html{' and sheet.png' if im['png'] else ' (sheet.png: not drawn)'}.", ""]
    if im["failed"]:
        out += [f"Not saved ({len(im['failed'])}): " + "; ".join(im["failed"]), ""]
    g = info["groups"]
    out += ["## The sample", "",
            f"Stratified random sample, seed {info['seed']}, from data.json's Korean common shares and US stocks "
            "(ETFs, funds and Korean preferred shares left out): "
            + "; ".join(f"{g[k]['label']} {g[k]['sampled']:,} of {g[k]['population']:,}" for k, _ in GROUPS) + ".",
            "Left out before sampling: " + "; ".join(f"{k}: {len(v):,}" for k, v in info["left_out"].items()) + ".",
            "Lookups use exact identifiers only (never a name search): the ticker first (Korea 005930.KS / 247540.KQ, "
            "US bare); for Korea only, the DART-homepage domain when the ticker found no brand.", "",
            "Sources:", ""]
    out += [f"- {s}" for s in info["sources"]]
    out += ["", "## What each status means", ""]
    out += [f"- **{s}** — {STATUS_MEANING[s]}" for s in STATUSES]
    out += ["", f"Limit: {REPEAT_NOTE}", "",
            "Per-company results: results.csv (and results.json, with every lookup). The signed image addresses "
            "logo.dev returns are not kept: they expire after about 24 hours.", ""]
    return "\n".join(out)


def build_info(a, checker, rows, groups, left_out, data, started, finished, images, problems, client, sources=()):
    cov = coverage(rows)
    done = [r for r in rows if r["status"] in STATUSES]
    kr = [r for r in done if r["side"] == "kr"]
    kr_nf_ticker = [r for r in kr if r["ticker_status"] == "not_found"]
    stop = checker.stop
    outcome = stop.outcome if stop else "complete"
    return {
        "tool": "tools/logos/logodev_api_check.py", "outcome": outcome,
        "ok": outcome in OK_OUTCOMES and not problems, "reason": stop.reason if stop else "",
        "problems": problems, "started_kst": started, "finished_kst": finished,
        "seed": a.seed, "sample": len(rows), "max_credits": a.max_credits,
        "checked": len(done), "unfinished": sum(1 for r in rows if not r["status"] and r["_lookups"]),
        "not_started": sum(1 for r in rows if not r["status"] and not r["_lookups"]),
        "data": {"pxDate": data.get("pxDate"), "usPxDate": data.get("usPxDate"), "asOf": data.get("asOf")},
        "sources": list(sources), "groups": groups, "left_out": left_out, "coverage": cov,
        "korea_routes": {"logo_by_ticker": sum(1 for r in kr if r["status"] == "logo" and r["route"] == "ticker"),
                         "logo_by_domain": sum(1 for r in kr if r["status"] == "logo" and r["route"] == "domain"),
                         "domain_tried": sum(1 for r in kr if r["domain_status"]),
                         "no_domain": sum(1 for r in kr_nf_ticker if not r["domain_status"])},
        "credits": {"counted": checker.credits_counted, "billed_answers": checker.credits_billed // CREDITS_PER_LOOKUP,
                    "unknown_requests": checker.credits_unknown // CREDITS_PER_LOOKUP,
                    "server_charged": checker.server_charged, "balance_first": checker.balance_first,
                    "balance_last": checker.balance_last},
        "requests": {"api": client.api_requests, "downloads": client.downloads,
                     "retries_202": checker.counts["202 retries"], "retries_429": checker.counts["retries after 429"],
                     "retries_error": checker.counts["retries after an error"],
                     "no_answer": checker.counts["no answer (network)"],
                     "no_retry_after": checker.counts["202 without Retry-After"],
                     "counts": dict(sorted(checker.counts.items())),
                     "waited_s": round(client.pacer.waited, 1)},
        "shapes": dict(checker.shapes), "images": images,
    }


# ── output ──────────────────────────────────────────────────────────────────────────────────────────────────────────

CSV_COLS = ["group", "rank", "code", "name", "side", "market", "cap", "ticker", "domain", "status", "route",
            "ticker_status", "domain_status", "credits", "requests", "kind", "width", "height", "format", "is_vector",
            "etag", "image_file", "saved_px", "note"]


def _put(folder, name, text, mask):
    (folder / name).write_text(mask(text), encoding="utf-8")


def write_reports(folder, info, log, mask):
    """summary.md, run.json and run.log: what is written again when the run's verdict changes at the very end."""
    _put(folder, "summary.md", summary_md(info), mask)
    _put(folder, "run.json", json.dumps(info, ensure_ascii=False, indent=1, allow_nan=False), mask)
    _put(folder, "run.log", "\n".join(log.lines) + "\n", mask)


def write_outputs(folder, rows, info, sheet, log, mask):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    _put(folder, "results.csv", buf.getvalue(), mask)
    clean = [{k: v for k, v in r.items() if k != "_url"} for r in rows]
    for r in clean:
        r["lookups"] = r.pop("_lookups")
    _put(folder, "results.json", json.dumps(clean, ensure_ascii=False, indent=1, allow_nan=False), mask)
    _put(folder, "sheet.html", sheet, mask)
    write_reports(folder, info, log, mask)


def verdict(path):
    """The workflow's last step: exit 0 only when run.json says the run finished or stopped cleanly."""
    try:
        info = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        outcome, ok = info["outcome"], info["ok"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"!! cannot read the run's outcome from {path}: {type(e).__name__}")
        return 1
    print(f"{'OK' if ok is True else '!! NOT OK'}: {OUTCOME_TEXT.get(outcome, outcome)} {info.get('reason') or ''}"
          f" Checked {info.get('checked')} of {info.get('sample')}. Problems: {info.get('problems') or 'none'}")
    return 0 if ok is True else 1


def prepare_out(folder):
    folder = pathlib.Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise SystemExit(f"!! {folder} is not empty. Give --out a new or empty folder (one folder per run).")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class Deps:
    """What the tests replace: the network, the clocks, the environment, the size checks and the picture."""

    def __init__(self, send=None, clock=time.monotonic, sleep=time.sleep, wall=now_kst, environ=None, jitter=None,
                 min_counts=None, kr_top=KR_TOP, render=render_png):
        self.send = send or requests_transport
        self.clock, self.sleep, self.wall, self.jitter = clock, sleep, wall, jitter
        self.environ = os.environ if environ is None else environ
        self.min_counts, self.kr_top = min_counts, kr_top
        self.render = render


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample", type=int, default=DEFAULT_SAMPLE, help="companies to sample (a third per group)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed (printed; same seed = same sample)")
    ap.add_argument("--max-credits", type=int, default=DEFAULT_MAX_CREDITS,
                    help="stop before the credits counted could pass this")
    ap.add_argument("--save-images", type=int, default=DEFAULT_IMAGES, help="logo images to download, at most")
    ap.add_argument("--out", default=None, help="new or empty output folder (default: a new folder under "
                                               f"{CACHE_DIR})")
    ap.add_argument("--data", default=lsrc.DATA_URL, help="data.json URL or path (default: the live site)")
    ap.add_argument("--listing", default="auto", help="KRX listing CSV path, or auto (the file for data.json pxDate)")
    ap.add_argument("--homepages", default=str(lsrc.HOMEPAGES))
    ap.add_argument("--time-limit-min", type=float, default=TIME_LIMIT_MIN,
                    help="no new lookup starts after this many minutes; the results so far are saved")
    ap.add_argument("--no-png", action="store_true", help="write sheet.html only (no browser)")
    ap.add_argument("--plan-only", action="store_true", help="draw and print the sample; no logo.dev call, no key")
    ap.add_argument("--defer-failure", action="store_true",
                    help="exit 0 once everything is saved even when the run stopped on an error; run.json holds the "
                         "outcome and --verdict turns it into the exit code (the workflow's last step)")
    ap.add_argument("--verdict", metavar="RUN_JSON", help="only read a run's run.json and exit 1 unless it was ok")
    a = ap.parse_args(argv)
    if a.sample < 3 or a.max_credits < CREDITS_PER_LOOKUP or a.save_images < 0 or a.time_limit_min <= 0:
        ap.error("--sample must be at least 3, --max-credits at least 2, --save-images 0 or more and "
                 "--time-limit-min above 0")
    return a


def logged(log, sources, fn, *args):
    """Runs a logo_sources loader, which reports with print(), and puts what it printed into the log and the
    sources list (which data.json and KRX listing were used, and any fallback to an older listing)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*args)
    finally:
        for line in buf.getvalue().splitlines():
            log(line)
            sources.append(line.lstrip("· "))


def main(argv=None, deps=None):
    """Every error that reaches here is printed through the masker (the key never shows), then exit 1."""
    state = {"mask": str}
    try:
        return _main(argv, deps, state)
    except SystemExit:
        raise
    except Exception:                                    # noqa: BLE001 — printed masked, then a failing exit
        for line in traceback.format_exc().splitlines():
            print(state["mask"](line), file=sys.stderr, flush=True)
        print("!! the check stopped on an error in this tool (above)", file=sys.stderr, flush=True)
        return 1


def _main(argv, deps, state):
    argv = list(sys.argv[1:] if argv is None else argv)
    refuse_key_in_args(argv)
    a = parse_args(argv)
    if a.verdict:
        return verdict(a.verdict)
    d = deps or Deps()
    t0 = d.clock()
    key = None
    if not a.plan_only:
        key = read_secret_key(d.environ)
        d.environ.pop(KEY_ENV, None)          # children (the browser for sheet.png) never inherit it
    mask = Masker(key) if key else str
    state["mask"] = mask
    log = Log(mask)
    started = d.wall()
    stamp = f"{started:%Y-%m-%d %H:%M}"
    log(f"logo.dev API check · {stamp} KST · seed {a.seed} · sample {a.sample} · max credits {a.max_credits} · "
        f"images {a.save_images}")

    sources = []
    data = json.loads(logged(log, sources, lsrc.load_text, a.data, "data.json"))
    listing = logged(log, sources, lsrc.load_listing, a.listing, data.get("pxDate"))
    homepages = lsrc.load_homepages(a.homepages)
    sources.append(f"DART homepages: {a.homepages} ({len(homepages):,} companies)")
    companies, clog = load_companies(data, listing, homepages, d.min_counts)
    for line in clog:
        log(line)
    log(check_ranking(companies, d.kr_top))
    order, groups, left_out = draw_sample(companies, a.sample, a.seed, d.kr_top)
    log(f"· data.json asOf {data.get('asOf')} · prices {data.get('pxDate')} (US {data.get('usPxDate')}) · companies "
        f"{len(companies):,} (Korea {sum(1 for c in companies if c['side'] == 'kr'):,} · "
        f"US {sum(1 for c in companies if c['side'] == 'us'):,})")
    log(f"· sample, seed {a.seed}: " + " · ".join(f"{g['label']} {g['sampled']} of {g['population']:,}"
                                                   for g in groups.values()))
    for why, codes in left_out.items():
        log(f"{'!!' if codes else '·'} left out, {why}: {len(codes):,}" + (f" {codes[:10]}" if codes else ""))
    log(f"· credits: at most {CREDITS_PER_LOOKUP} per company (the domain is tried only after a free not_found), so "
        f"this sample costs at most {CREDITS_PER_LOOKUP * a.sample:,}; the cap stops the run after "
        f"{a.max_credits // CREDITS_PER_LOOKUP:,} billed answers")
    if a.plan_only:
        for gid, _ in GROUPS:
            log(f"· {gid}: " + " ".join(c["code"] for c in order if c["group"] == gid))
        log("· plan only: no logo.dev call was made")
        return 0

    out = prepare_out(a.out or CACHE_DIR / f"logo-dev-check-{started:%Y%m%d-%H%M%S}")
    log(f"· output folder: {out}")
    log(f"· {REPEAT_NOTE}")
    client = Client(key, d.send, Pacer(d.clock, d.sleep))
    checker = Checker(client, a.max_credits, log, d.clock, None, d.jitter, deadline=t0 + a.time_limit_min * 60)
    problems = []
    try:
        checker.run(order)
    except Exception as e:                               # noqa: BLE001 — a bug: said, recorded, partial results saved
        checker.stop = StopRun("crashed", f"{type(e).__name__}: {e}")
        for line in traceback.format_exc().splitlines():
            log("  " + line)
        log(f"!! stopped: {checker.stop.reason}")
    rows = result_rows(checker)
    clean_stop = not checker.stop or checker.stop.outcome in OK_OUTCOMES
    chosen = pick_images(rows, a.save_images, a.seed) if clean_stop else []
    if not clean_stop:
        log("· images: none downloaded, because the run stopped on an error")
    saved, failed = save_images(chosen, client, out, log) if chosen else ([], [])
    if chosen and len(failed) * 2 > len(chosen):
        problems.append(f"{len(failed)} of {len(chosen)} chosen logo images could not be downloaded")
        log(f"!! {problems[-1]}")
    finished = f"{d.wall():%Y-%m-%d %H:%M}"
    meta = (f"{stamp} KST · seed {a.seed} · {len(saved)} logos from a sample of {len(rows)} "
            f"({', '.join(GROUP_LABEL[g] for g, _ in GROUPS)})")
    png = False
    if a.no_png:
        log("· sheet.png: not drawn (--no-png)")
    else:
        try:
            p = d.render(saved, meta, out, log)
        except Exception as e:                           # noqa: BLE001 — said loudly and makes the run not ok
            p = f"sheet.png not drawn: {type(e).__name__}: {e}"
        if p:
            problems.append(p)
            log(f"!! {p}")
        png = (out / "sheet.png").exists()
    images = {"asked": a.save_images, "chosen": len(chosen), "saved": len(saved), "png": png,
              "per_group": {g: sum(1 for s in saved if s["row"]["group"] == g) for g, _ in GROUPS},
              "failed": [f"{r['code']}: {why}" for r, why in failed]}
    info = build_info(a, checker, rows, groups, left_out, data, stamp, finished, images, problems, client, sources)
    cov = info["coverage"]["ALL"]
    log(f"· checked {info['checked']:,} of {len(rows):,} · " + " · ".join(f"{s} {cov['counts'][s]:,}" for s in STATUSES)
        + f" · credits counted {checker.credits_counted:,}/{a.max_credits:,} · API requests {client.api_requests:,}"
        f" · downloads {client.downloads:,}")
    log(f"{'OK' if info['ok'] else '!! NOT OK'}: {OUTCOME_TEXT[info['outcome']]} {info['reason']}".rstrip()
        + f" · results in {out}")
    write_outputs(out, rows, info, sheet_html(saved, meta), log, mask)
    leaks = find_key_in_files(out, key)
    if leaks:                                            # never expected: deleted, and the run is not ok
        for p in leaks:
            p.unlink()
        info["ok"] = False
        info["problems"].append(f"the key was found in {[p.name for p in leaks]}; those files were deleted")
        log(f"!! NOT OK: the key was found in {[p.name for p in leaks]}; those files were deleted")
        write_reports(out, info, log, mask)              # the summary and run.json say so too
        for p in find_key_in_files(out, key):
            p.unlink()
    if info["ok"] or a.defer_failure:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
