#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Company logos from logo.dev Pro, fetched once and hosted by us (v19.3a, docs/tasks/v19.3-portfolio-pictures-accounts.md
Part J). Run by hand only: from the workflow "logo.dev 로고 받기" (.github/workflows/logo-dev-fetch.yml), or from a terminal:

  LOGO_DEV_SECRET_KEY=sk_... python3 tools/logos/logodev_fetch.py --out DIR [--max-credits 14000] [--workers 4]
  python3 tools/logos/logodev_fetch.py --plan-only           # the companies, the requests and the credit ceiling; no call
  python3 tools/logos/logodev_fetch.py --verdict DIR/run.json # exit 1 unless that run finished or stopped cleanly
  python3 tools/logos/logodev_fetch.py --drop 005930,AAPL --dir DIR --reason "wrong company (sheet review)"
                                                             # after looking at the sheet: those companies get the letter mark
  python3 tools/logos/logodev_fetch.py --keep 066570 --dir DIR --reason "LG group logo, checked"
                                                             # the mirror: a picture in dropped/ goes back into logos/
  LOGO_DEV_SECRET_KEY=sk_... python3 tools/logos/logodev_fetch.py --only 000270 --route ticker --out FIX
                                                             # a fix-up: only the named companies (at most 10), by ticker only
  python3 tools/logos/logodev_fetch.py --add-from FIX --dir DIR --reason "기아: ticker logo, checked"
                                                             # after looking at FIX: its logos join the reviewed folder DIR
  LOGO_DEV_SECRET_KEY=sk_... python3 tools/logos/logodev_fetch.py --letters-from REVIEWED --extra-routes \
      --full-run-date YYYY-MM-DD --out RETRY                  # a retry (2026-11-07): only the Korean companies that show a
                                                             # letter mark in REVIEWED, largest first; --extra-routes adds
                                                             # an ISIN and a brandmark lookup when ticker and homepage give
                                                             # nothing usable. Refuses a cap above $20 unless --over-20-ok
  python3 tools/logos/logodev_fetch.py --add-from RETRY --dir DIR --codes 078930,030530 --reason "checked by eye"
                                                             # a retry is added only company by company, by --codes
--drop, --keep and --add-from are all or nothing (both folders checked before and after; on any error nothing changes),
take each code once, and --drop refuses a preferred share (it goes with its common share). --add-from refuses a company
that already has a logo in DIR (--drop it first); a preferred share follows its issuer.
A run of more than 50 companies (no --limit, or a bigger one) needs --full-run-date set to today's KST date (the
workflow input full_run_date), so a re-run on another day refuses by itself before any request.

What it does
  1. Companies: every Korean company and every US company in the live data.json (or --data), ETFs and funds left out,
     in market-cap order (조원 for both markets, data.json's own unit). A Korean preferred share reuses its issuer's logo
     (kr_homepages.csv `via`, else the common-share code) with no lookup of its own. Refuses data that is plainly
     incomplete (too few companies, a must-have company missing, many market caps blank).
  2. Lookups, exact identifiers only (never a name), GET /v2/brands/logo (2 credits when billed):
       ticker  KOSPI and KONEX 005930.KS · KOSDAQ 247540.KQ · US bare (AAPL, BRK-B);
       domain  Korea only: the DART homepage domain (kr_homepages.csv, domain_ok = 1), after the ticker, whatever the
               ticker found. The logo lookup does not return a brand domain, so the cross-check compares brand_id:
                 ticker logo + homepage logo of the same real brand_id -> the ticker logo, "same-brand";
                 ticker logo + homepage logo of another brand -> the homepage logo ("homepage-over-ticker");
                 either brand_id missing (an equal etag is not enough) -> the ticker logo, "unverified";
                 ticker logo, the homepage found no logo (or no usable domain) -> the ticker logo, flagged "unverified";
                 no ticker logo + homepage logo -> the homepage logo ("homepage"); neither -> the letter mark.
               A second lookup that reaches a brand already billed in the last 24 hours is free (Credits-Charged: 0).
  3. Each chosen logo is downloaded right after its lookups, from the signed address in the answer (it expires after
     about 24 hours and is never written anywhere; the etag is kept). Raster sources are downloaded as PNG at their own
     size up to 128 px, vector sources rasterised by logo.dev at 128 px. Normalised to a 128 x 128 WebP (PNG when this
     Pillow has no WebP), transparency kept, centred, never stretched or upscaled. SVG is never stored.
  4. Automatic quality checks; a failing logo gets the letter mark, never a doubtful logo (QUALITY_NOTE below). A
     picture shared by companies of different or unknown brands gets the letter mark, except for a company whose own
     homepage confirmed its ticker logo (same-brand). Every dropped picture is kept in dropped/ (never published), so
     --keep can restore one after review without paying again.
  5. Writes to --out: logos/<code>.webp + logos/index.json (the folder tools/push_logos_branch.sh publishes; each entry
     carries the company's name, which Deploy compares with that day's data.json), summary.md, review.csv (one row per
     company), sheet.html and sheet-01.png … (review sheet, no caps: the --sheet-top largest companies of each market
     with their chosen logo or letter mark, then every Korean company outside them whose homepage logo replaced the
     ticker's, whose ticker logo is unverified, or whose logo came from the homepage only, then every shared picture),
     run.json and run.log.

Spend, pace and stops (logo.dev docs and pricing page, read 2026-11-06: Pro = 500 API requests a minute, 15 open at once,
$150 of API credit a month, 1 credit = 1¢, logo lookup 2 credits)
  - Credits are counted here, never trusted to logo.dev alone: 2 per answer marked Credits-Charged: 1 (2 also when a
    200 or 404 carries no such header, and 2 for a request that got no answer, in case it was billed). Before every
    request 2 credits are reserved; a request that could pass --max-credits (14,000 = $140, also the most it accepts) is
    never sent. The cap also holds across runs: when logo.dev reports its balance (Credits-Remaining), no request is
    sent that could take it below 1,000 credits (15,000 of Pro credit − 14,000). The first balance is logged with the
    run's worst case; below that worst case plus 1,000 the run stops before any further lookup. A billed answer without
    a balance is said once; a balance that is not a plain number ("15,000", "$150", "inf", "-5") stops the run. A --limit or --only run's cap is its own ceiling (2 credits a lookup: 20 companies, at most 80). The
    run also stops on 402 (no credit left). With auto-reload on the account a 402 may never come: the local limits are
    the real stop.
  - At most --per-minute (200) lookups a minute and --workers (4) open at once; downloads (not billed, not CDN
    requests) at most 300 a minute. 429: waits Retry-After or RateLimit-Reset, else backs off. 202 (indexing): the
    company waits Retry-After (30 s) while the others go on, at most RETRIES_202 times. An answer the docs don't
    describe is that company's alone: it gets the letter mark (odd_answer, the raw source fields in review.csv and the
    log, never the signed address) and the run goes on; a Korean company whose ticker answer is odd gets no homepage
    lookup. A vector source without a size (0 x 0) is fine: it is judged on its downloaded picture (small when that is
    under 64 px), flagged sizeless-vector, counted and drawn on the review sheet. 401/403, more than 30 odd answers (the
    API may have changed), 20 failed picture downloads in a row or one 401/403 from the image host (lookups would be
    billed for nothing), or 5 companies in a row ending in an error stop the run; whatever was found is still saved.
  - Nothing is skipped as "done before": every run looks every company up again. A brand billed in the last 24 hours
    is free again (logo.dev bills a brand once per 24 hours), so a rerun soon after a stopped run costs only the rest.
  - No new lookup starts after --time-limit-min (110), inside the workflow's 150-minute limit.

The key
  Read only from LOGO_DEV_SECRET_KEY, then removed from this process's environment (the browser that draws the sheet
  never inherits it). It goes only into the Authorization header of api.logo.dev requests. Never printed, logged or
  written: every line passes a masker, and every output file is searched for it and for signed image addresses at the
  end (found -> deleted and the run is not OK). A value that looks like a secret key on the command line is refused.

Exit code: 0 when the run finished or stopped cleanly (credit cap, balance floor, 402); 1 otherwise. With
--defer-failure (the workflow) it exits 0 once everything is saved, so the results are uploaded; the workflow's last step
(--verdict) fails. An error after the lookups never loses what was paid for: index.json (from the pictures already in
logos/), dropped/index.json, review.csv, run.json (ok false, outcome crashed, the traceback masked) and summary.md are
still written.
Unit tests: tests/test_logo_fetch.py (no network: the HTTP client is faked).
"""
import argparse
import base64
import collections
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
import threading
import time
import traceback
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import logo_index as LI  # noqa: E402
import logo_sources as lsrc  # noqa: E402
import logodev_api_check as chk  # noqa: E402
from logo_ids import KST, Masker, common_code, is_common_share, is_krx_code, now_kst  # noqa: E402

KEY_ENV = chk.KEY_ENV
CREDITS = chk.CREDITS_PER_LOOKUP                 # 2 per billed logo lookup
DEFAULT_MAX_CREDITS = MAX_CREDITS = 14_000       # $140 at 1 credit = 1 cent (Jack's stop, 2026-11-06): never more
MIN_BALANCE = 1_000                              # stop before logo.dev's reported balance could go below this
                                                 # (15,000 of Pro credit - 14,000): the cap holds across runs too
DEFAULT_WORKERS = 4                              # open at once (Pro allows 15)
DEFAULT_PER_MINUTE = 200                         # lookups a minute (Pro allows 500)
DOWNLOADS_PER_MINUTE = 300
TIME_LIMIT_MIN = 110                             # the workflow's job limit is 150 minutes
SHEET_TOP = 300                                  # per market
RETRIES_202 = 6                                  # logo.dev: usually ready within a minute; stop polling after 300 s
MAX_WAIT_202_S = 60
SIZE = LI.SIZE
SMALL_PX = 64                                    # a raster whose shorter side is under this is dropped (63 yes, 64 no)
BLANK_SHARE = 0.01                               # visible share (alpha 32 or more) under this: blank
FAINT_DIST, FAINT_SHARE = 40, 0.015              # on white, pixels more than 40 levels from white under 1.5%: faint
ONE_COLOUR = 0.985                               # one colour on white and on black at least this share: one_colour
TILES_PER_PAGE = 48
MAX_KR_NOCAP = MAX_US_NOCAP = 25
MUST = chk.MUST
MUST_TOP = 300                                   # each must-have company sits in its market's top 300 by market cap
MIN_COMPANIES = chk.MIN_COMPANIES
URL_NEEDLE = b"img.logo.dev/"                    # a signed image address must never be written
URL_RE = re.compile(r"https?://img\.logo\.dev/\S*")
DROP_REASONS = ("small", "blank", "faint", "one_colour", "shared", "file_clash", "odd_code", "wide_brandmark")
ODD_STOP = 30                                    # more odd answers than this in one run: logo.dev's API may have changed
DOWNLOAD_STOP = 20                               # this many failed picture downloads in a row stop the run
FORMATS = ("png", "jpg", "svg", "webp", "gif", "ico", "avif")    # source.format values logo.dev documents
OK_OUTCOMES = ("complete", "max_credits", "out_of_credits", "balance_floor", "balance_low", "balance_unreadable")
BALANCE_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")  # Credits-Remaining as logo.dev documents it ("18966.99"); else unreadable
FULL_RUN_FREE_LIMIT = 50                         # a --limit run up to this many companies needs no --full-run-date
ONLY_MAX = 10                                    # --only: named companies, at most this many (a fix-up, never a run)
# v19.3a retry (Jack, 2026-11-07): two more exact-identifier routes, for Korean companies only, and only after the ticker
# and the DART homepage found no usable logo (none, or a raster under SMALL_PX): GET /v2/brands/logo?isin=KR7… (2 credits),
# (the company's ISIN from logo_sources: the KRX listing's ISU_CD, check digit verified, else the common-share rule),
# then GET /v2/brands/brandmark?ticker=… (3 credits; "the wide logo lockup" — kept only when no wider than
# BRANDMARK_MAX_ASPECT : 1, so it still reads in the app's square). logo.dev docs, read 2026-11-07: brands/look-up-a-brand,
# logos/get-a-brandmark, platform/credits. Every quality check below applies to these pictures unchanged.
EXTRA_ROUTES = ("isin", "brandmark")
ROUTE_COST = {"ticker": CREDITS, "domain": CREDITS, "isin": CREDITS, "brandmark": 3}
BRANDMARK_ROUTE = "/brands/brandmark"
RETRY_SPEND_ASK = 2_000      # Jack (2026-11-07): report before a retry could spend more than $20 — a --letters-from run whose
                             # cap is above this refuses unless --over-20-ok (the workflow input over_20_dollars_ok)
SKIP_KNOWN = ("shared",)     # letters retry: the old ticker/homepage answer gave another brand's picture (a shared group),
                             # or Claude dropped it after looking (drops.csv) — asking again would bill the same picture, so
                             # those start at the ISIN. A small, blank or faint picture IS asked again: logo.dev's answer
                             # changes (2026-11-07 retry: 아이에스동서's 16 px ticker icon came back as an 800 × 400 logo)
BRANDMARK_MAX_ASPECT = 2.0
OUTCOME_TEXT = dict(chk.OUTCOME_TEXT, complete="Finished: every company was looked up.",
                    balance_floor=f"Stopped cleanly: logo.dev's reported credit balance would have gone below "
                                  f"{MIN_BALANCE:,} credits.",
                    balance_low=f"Stopped cleanly before the lookups: logo.dev's first reported balance was below this "
                                f"run's worst case plus the {MIN_BALANCE:,}-credit floor.",
                    balance_unreadable="Stopped cleanly: logo.dev reported a credit balance this tool cannot read, so "
                                       "the 1,000-credit floor could not be kept.",
                    download_failures="Stopped: the signed picture downloads kept failing, so further lookups would be "
                                      "billed for nothing. What was found is saved.")

QUALITY_NOTE = (
    "Quality checks (a failing logo gets the letter mark): "
    "**small** — a raster source whose shorter side is under 64 px (logo.dev's width and height); "
    "**blank** — under 1% of the 128 px picture is visible (alpha 32 or more); "
    "**faint** — near-invisible on white, which is how the app shows logos: laid on white, under 1.5% of the pixels "
    "are more than 40 levels (of 255) away from white in any channel, so a white or very light logo on transparency "
    "is dropped; "
    "**one_colour** — the picture laid on white and laid on black is, both times, at least 98.5% one colour "
    "(colours rounded to 32 levels a channel), such as a flat coloured square; "
    "**monogram-looking** (a flag, never a drop: on real data it caught only real logos) — an opaque square (75% or "
    "more of the picture fully opaque) of two flat colours (background 55% or more, a far colour 4–40%, at most 6% of "
    "other colours besides the blend between them) whose far colour forms one or two blobs centred within 12% of the "
    "middle, 25–75% of the height and 10–75% of the width. The logo is kept and drawn on the review sheet. "
    "**shared** — the same picture for companies whose logo.dev brand_id differs or is missing (a generic picture, or "
    "a group logo under different brands): the same 64-bit difference hash and 16 x 16 colour thumbnails at most 6 "
    "levels apart on average; only checked pairs form a group. In such a group every company gets the letter mark "
    "except one whose own homepage confirmed its ticker logo (same-brand); a group whose companies all have one real "
    "brand_id is kept. Every shared group is on the review sheet; --keep restores a checked one. "
    "**file_clash** — two codes would share one file name; **odd_code** — a code that is not a plain stock code (both "
    "never expected)."
)


# ── companies ───────────────────────────────────────────────────────────────────────────────────────────────────────

cap_of = chk.cap_of


def safe_file(code):
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", str(code))[:24] or "_"
    if not stem[0].isalnum():
        stem = "x" + stem[:23]
    return stem


def letters_from(order, folder):
    """--letters-from DIR: only the Korean companies that have no picture in the reviewed folder DIR (its
    logos/index.json), in market-cap order. -> (companies, log lines). (pure but for reading the file)"""
    index, bad = LI.validate_dir(pathlib.Path(folder) / "logos")
    if bad:
        raise SystemExit("!! --letters-from: not a valid logo folder: " + "; ".join(bad[:5]))
    have = set(index["logos"])
    keep = [c for c in order if c["side"] == "kr" and c["code"] not in have]
    folder = pathlib.Path(folder)
    prev, dropped_after_review = {}, set()
    if (folder / "review.csv").exists():
        with open(folder / "review.csv", newline="", encoding="utf-8") as f:
            prev = {r["code"]: r for r in csv.DictReader(f)}
    if (folder / "drops.csv").exists():
        with open(folder / "drops.csv", newline="", encoding="utf-8") as f:
            dropped_after_review = {r["code"] for r in csv.DictReader(f)}
    for c in keep:                                       # the old answer was another brand's picture or was dropped
        why = (prev.get(c["code"]) or {}).get("reason", "")        # after review: asking again bills the same picture,
        if why in SKIP_KNOWN or c["code"] in dropped_after_review:  # so the retry starts at the ISIN
            c["skip_known"] = "dropped after review" if c["code"] in dropped_after_review else why
    n_skip = sum(1 for c in keep if c.get("skip_known"))
    return keep, [f"!! --letters-from {folder}: the {len(keep):,} Korean companies without a logo there "
                  f"(of {sum(1 for c in order if c['side'] == 'kr'):,}; {len(have):,} entries in its index) · "
                  f"{n_skip:,} of them get no new ticker/homepage lookup (their old answer was another brand's picture or was "
                  "dropped after review; with --extra-routes they start at the ISIN, without it they are left out)"]


def load_all(data, listing, homepages, min_counts=None, sheet_top=SHEET_TOP):
    """data.json + KRX listing + DART homepages -> (companies, preferred, log). companies: KR common shares and US
    stocks with exact identifiers, ranked by market cap (rank overall and within the market); preferred: Korean
    preferred shares with their issuer's code. Refuses incomplete data (chk.load_companies), more than 25 companies of
    a market without a market cap, or a must-have company outside its market's top 300."""
    companies, log = chk.load_companies(data, listing, homepages, min_counts)
    for side, most in (("kr", MAX_KR_NOCAP), ("us", MAX_US_NOCAP)):
        nocap = [c["code"] for c in companies if c["side"] == side and cap_of(c) is None]
        if len(nocap) > most:
            raise SystemExit(f"!! {len(nocap):,} {side.upper()} companies have no market cap (at most {most}): "
                             "data.json may be a pre-market file, so a market-cap order would be wrong")
    order = sorted(companies, key=lambda c: (cap_of(c) is None, -(cap_of(c) or 0), str(c["code"])))
    seen = collections.Counter()
    for i, c in enumerate(order, 1):
        seen[c["side"]] += 1
        c["rank"], c["mrank"] = i, seen[c["side"]]
    for side in ("kr", "us"):
        top = {c["code"] for c in order if c["side"] == side and c["mrank"] <= MUST_TOP}
        lost = [m for m in MUST[side] if m not in top]
        if lost:
            raise SystemExit(f"!! must-have {side.upper()} companies are not in the top {MUST_TOP} by market cap: {lost}")
    commons = {c["code"] for c in order if c["side"] == "kr"}
    preferred = []
    for s in data.get("stocks") or []:
        code = str(s.get("t") or "").strip()
        if s.get("cls") != "kr" or s.get("etf") or s.get("fund") or not is_krx_code(code) or is_common_share(code):
            continue
        via = (homepages.get(code) or {}).get("via") or common_code(code)
        preferred.append({"code": code, "name": s.get("nk") or s.get("ne") or code, "side": "kr", "cap": s.get("cap"),
                          "issuer": via, "issuer_listed": via in commons})
    log.append(f"· Korean preferred shares: {len(preferred):,} (each reuses its issuer's logo, no lookup of its own; "
               f"issuer not in data.json: {sum(1 for p in preferred if not p['issuer_listed'])})")
    return order, preferred, log


def plan(order, ticker_only=False, extra=False):
    """Lookups and the credit ceiling: one ticker lookup per company with a ticker, plus one homepage lookup per Korean
    company with a usable DART domain (none with --route ticker); every one could be billed (2 credits). With --extra
    routes, every Korean company could also need an ISIN lookup (2) and a brandmark lookup by ticker (3)."""
    asked = [c for c in order if not (extra and c.get("skip_known"))]     # skip_known: straight to the ISIN
    t = sum(1 for c in asked if c.get("ticker"))
    d = 0 if ticker_only else sum(1 for c in asked if c["side"] == "kr" and c.get("domain"))
    i = sum(1 for c in order if c["side"] == "kr" and c.get("isin")) if extra else 0
    b = sum(1 for c in order if c["side"] == "kr" and c.get("ticker")) if extra else 0
    return {"ticker": t, "domain": d, "isin": i, "brandmark": b, "lookups": t + d + i + b,
            "ceiling": CREDITS * (t + d + i) + ROUTE_COST["brandmark"] * b}


# ── network ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def transport(url, params=None, headers=None, timeout=chk.TIMEOUT_S, max_bytes=chk.MAX_ANSWER_BYTES, follow=False):
    """The real network. A lookup (follow=False) never follows a redirect (an unexpected answer). A download from a
    signed address (follow=True) may follow up to 3 https redirects: it carries no key, the signature is the credential.
    At most max_bytes of the body are read."""
    import requests
    if not follow:
        return chk.requests_transport(url, params=params, headers=headers, timeout=timeout, max_bytes=max_bytes)
    with requests.Session() as s:
        s.max_redirects = 3
        with s.get(url, params=params, headers=headers or {}, timeout=timeout, allow_redirects=True, stream=True) as r:
            if not str(r.url).startswith("https://"):
                return chk.Resp(599, {}, b"")
            return chk.Resp(r.status_code, r.headers, r.raw.read(max_bytes, decode_content=True))


def _px(x):
    return not isinstance(x, bool) and isinstance(x, (int, float)) and 0 < x < 1e6 and x == int(x)


def source_facts(src):
    """The raw source fields of an answer, for the log (never the signed address)."""
    src = src if isinstance(src, dict) else {}
    return "source " + json.dumps({k: src.get(k) for k in ("width", "height", "format", "is_vector", "has_transparency")
                                   if k in src}, ensure_ascii=False)[:200]


def parse_logo(j, want="logo"):
    """A 200 answer -> (image, None), or (None, why) when it is not what the docs describe. The image is the documented
    `data` (a ready logo) or `data.logo`. A vector source (is_vector true or format svg) with a 0 x 0 or missing size
    is accepted: logo.dev renders it at the size asked, and the downloaded picture's size is used. Anything else odd (a
    raster without a size, an unknown format, a wrong address) is for this company only (odd_answer)."""
    data = j.get("data") if isinstance(j, dict) else None
    if not isinstance(data, dict):
        return None, "HTTP 200 without a data object" + (" (not JSON)" if j is None else "")
    img, shape, kind = data, "data", data.get("kind")
    if "url" not in data and isinstance(data.get("logo"), dict):
        img, shape, kind = data["logo"], "data.logo", "logo"
    elif data.get("object") != "image" or data.get("status") != "ready" or kind != want:
        return None, (f"HTTP 200 whose data is not a ready logo image (object {data.get('object')!r}, kind {kind!r}, "
                      f"status {data.get('status')!r})")
    url, src = img.get("url"), img.get("source")
    if not isinstance(url, str) or not isinstance(src, dict):
        return None, f"HTTP 200 without an image url and source (keys {sorted(img)})"
    u = urlsplit(url)
    if u.scheme != "https" or u.hostname not in chk.IMAGE_HOSTS:
        return None, f"HTTP 200 whose image address is not https://{chk.IMAGE_HOSTS[0]} (host {u.hostname!r})"
    fmt = str(src.get("format") or "").lower()
    if fmt and fmt not in FORMATS:
        return None, f"HTTP 200 with an unknown source format · {source_facts(src)}"
    vector = src.get("is_vector") is True or fmt == "svg"
    w, h = src.get("width"), src.get("height")
    if _px(w) and _px(h):
        size = (int(w), int(h))
    elif vector and all(x in (None, 0) for x in (w, h)):
        size = (None, None)                              # the downloaded rendition gives the size
    else:
        return None, f"HTTP 200 with an image size that is not two positive whole numbers · {source_facts(src)}"
    return {"url": url, "width": size[0], "height": size[1], "format": fmt, "is_vector": vector,
            "etag": str(img.get("etag") or ""), "shape": shape, "kind": kind,
            "has_transparency": bool(src.get("has_transparency"))}, None


class SafePacer(chk.Pacer):
    """chk.Pacer (at most per_minute starts in any 60 s, a minimum gap, hold) shared by the workers."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:                                  # sleeping inside the lock spaces the starts out
            super().wait()

    def hold(self, seconds):
        with self._lock:
            super().hold(seconds)


class Client:
    """api.logo.dev lookups (the only requests that carry the key) and downloads from the signed addresses (no key)."""

    def __init__(self, key, send, api_pacer, dl_pacer):
        self._auth = "Bearer " + key
        self.send, self.api_pacer, self.dl_pacer = send, api_pacer, dl_pacer
        self._lock = threading.Lock()
        self.api_requests = 0
        self.downloads = 0

    def __repr__(self):
        return "Client(api.logo.dev)"

    def lookup(self, route, ident):
        if route not in chk.ROUTES + EXTRA_ROUTES:
            raise ValueError(f"route {route!r} is not an exact identifier ({', '.join(chk.ROUTES + EXTRA_ROUTES)})")
        self.api_pacer.wait()
        with self._lock:
            self.api_requests += 1
        path, params = ((BRANDMARK_ROUTE, {"ticker": ident}) if route == "brandmark" else (chk.LOGO_ROUTE, {route: ident}))
        return self.send(chk.API_BASE + path, params=params,
                         headers={"Authorization": self._auth, "Accept": "application/json"}, timeout=chk.TIMEOUT_S,
                         max_bytes=chk.MAX_ANSWER_BYTES)

    def download(self, url, size):
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname not in chk.IMAGE_HOSTS:
            raise ValueError("not a logo.dev image address")
        want = {"format": "png", "size": str(int(size))}
        q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k not in want and k != "theme"]
        self.dl_pacer.wait()
        with self._lock:
            self.downloads += 1
        return self.send(urlunsplit((u.scheme, u.netloc, u.path, urlencode(q + list(want.items())), "")), params=None,
                         headers={}, timeout=chk.TIMEOUT_S, max_bytes=chk.MAX_IMAGE_BYTES + 1, follow=True)


class Ledger:
    """Credits, counted locally and shared by the workers. reserve() before a request, settle() after it."""

    def __init__(self, cap):
        self.cap = cap
        self._lock = threading.Lock()
        self.billed = 0                  # credits for answers that were (or may have been) billed
        self.unknown = 0                 # credits for requests that got no answer (counted once per lookup)
        self.reserved = 0
        self.charged = 0                 # answers with Credits-Charged: 1
        self.free = 0                    # answers with Credits-Charged: 0
        self.no_header = 0               # billable answers without the header (counted as billed)
        self.billed_at = collections.Counter()   # price -> billed answers (2 a logo lookup, 3 a brandmark)
        self.unanswered_n = 0            # requests that got no answer (counted once per lookup, at its price)
        self.balance_first = self.balance_last = None
        self.balance = None              # the lowest Credits-Remaining seen (credits), when logo.dev reports one
        self._first, self._first_done = None, False      # the first balance reported, said once (take_notices)
        self._nobal, self._nobal_told = False, False     # a billed answer without a balance, said once
        self.unreadable = None                           # a Credits-Remaining that is not a plain number: stop
        self._unreadable_new = None

    @property
    def counted(self):
        return self.billed + self.unknown

    def reserve(self, price=CREDITS):
        """None when `price` credits (2 a logo lookup, 3 a brandmark) are reserved; else why not: "cap"
        (--max-credits) or "floor" (logo.dev's reported balance minus what is in flight could go below MIN_BALANCE)."""
        with self._lock:
            if self.billed + self.unknown + self.reserved + price > self.cap:
                return "cap"
            if self.unreadable is not None:
                return "unreadable"
            if self.balance is not None and self.balance - self.reserved - price < MIN_BALANCE:
                return "floor"
            self.reserved += price
            return None

    def release(self, price=CREDITS):
        with self._lock:
            self.reserved -= price

    def settle(self, resp, price=CREDITS):
        """Releases the reservation and counts the answer. Returns the credits it cost."""
        cc = resp.headers.get("credits-charged")
        cost = 0
        with self._lock:
            self.reserved -= price
            if cc == "1":
                self.charged += 1
                cost = price
            elif cc == "0":
                self.free += 1
            elif resp.status in (200, 404):
                self.no_header += 1
                cost = price
            if cost:
                self.billed_at[cost] += 1
            self.billed += cost
            bal = resp.headers.get("credits-remaining")
            if bal is not None and str(bal).strip() != "":
                bal = str(bal).strip()
                self.balance_last = bal
                self.balance_first = self.balance_first or bal
                if BALANCE_RE.match(bal):
                    v = float(bal)
                    self.balance = v if self.balance is None else min(self.balance, v)
                    if not self._first_done:
                        self._first_done, self._first = True, v
                elif self.unreadable is None:            # "15,000", "$150.00", "inf", "-5": never go on without the floor
                    self.unreadable = self._unreadable_new = bal
            elif cost and not self._nobal_told:
                self._nobal_told = self._nobal = True
        return cost

    def take_notices(self):
        """(first balance or None, True when a billed answer carried no balance, an unreadable balance or None):
        each one only once."""
        with self._lock:
            out = (self._first, self._nobal, self._unreadable_new)
            self._first, self._nobal, self._unreadable_new = None, False, None
        return out

    def unanswered(self, price=CREDITS):
        with self._lock:
            self.reserved -= price
            self.unknown += price
            self.unanswered_n += 1
        return price


# ── images ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _np():
    import numpy as np
    return np


def can_webp():
    try:
        from PIL import features
        return bool(features.check("webp"))
    except Exception:                                  # noqa: BLE001 — no WebP: PNG instead, said in the summary
        return False


def download_size(img):
    """The size= to ask logo.dev for: 128 for a vector source or a raster of 128 px or more, else the raster's own
    longer side (so a small picture is never upscaled)."""
    if img.get("is_vector"):
        return SIZE
    return max(1, min(SIZE, max(int(img["width"]), int(img["height"]))))


def normalise(raw):
    """Downloaded bytes -> a 128 x 128 RGBA Pillow image: fitted inside, centred, transparency kept, never upscaled."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 4_000_000
    im = Image.open(io.BytesIO(raw))
    if im.format not in ("PNG", "JPEG", "WEBP"):
        raise ValueError(f"not a PNG, JPEG or WebP picture ({im.format})")
    if max(im.size) > 2048:
        raise ValueError(f"picture is {im.size[0]} x {im.size[1]}")
    im.load()
    im = im.convert("RGBA")
    w, h = im.size
    scale = min(1.0, SIZE / max(w, h))
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    if (nw, nh) != (w, h):
        im = im.convert("RGBa").resize((nw, nh), Image.LANCZOS).convert("RGBA")     # premultiplied: no dark fringes
    canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    canvas.paste(im, ((SIZE - nw) // 2, (SIZE - nh) // 2))
    return canvas


def encode(canvas, webp=True):
    """(bytes, extension). WebP quality 90 with full-quality alpha; a little lower if a file would be too large."""
    for q in (90, 80, 70):
        buf = io.BytesIO()
        if webp:
            canvas.save(buf, "WEBP", quality=q, method=6, alpha_quality=100)
        else:
            canvas.save(buf, "PNG", optimize=True)
        b = buf.getvalue()
        if len(b) <= LI.MAX_FILE_BYTES or not webp:
            return b, ("webp" if webp else "png")
    return b, "webp"


def _composite(arr, bg):
    np = _np()
    a = arr[..., 3:4].astype(np.float32) / 255.0
    return (arr[..., :3].astype(np.float32) * a + bg * (1.0 - a)).round().astype(np.uint8)


def top_share(rgb):
    np = _np()
    q = (rgb >> 3).reshape(-1, 3).astype(np.int32)
    keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    return np.bincount(keys).max() / keys.size


def _blobs(mask):
    """Connected parts (4-neighbour) of a boolean mask, as a list of sizes."""
    h, w = mask.shape
    seen = mask.copy()
    sizes = []
    for y0, x0 in zip(*mask.nonzero()):
        if not seen[y0, x0]:
            continue
        seen[y0, x0] = False
        stack, n = [(y0, x0)], 0
        while stack:
            y, x = stack.pop()
            n += 1
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and seen[yy, xx]:
                    seen[yy, xx] = False
                    stack.append((yy, xx))
        sizes.append(n)
    return sizes


def is_monogram(arr):
    """logo.dev's generic letter tile (QUALITY_NOTE)."""
    np = _np()
    opaque = arr[..., 3] >= 250
    if opaque.mean() < 0.75:
        return False
    px = arr[..., :3][opaque].astype(np.int32)
    q = px >> 4
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    counts = np.bincount(keys)
    bgk = int(counts.argmax())
    bg = np.array([(bgk >> 8) * 16 + 8, ((bgk >> 4) & 15) * 16 + 8, (bgk & 15) * 16 + 8])
    d_bg = np.sqrt(((px - bg) ** 2).sum(1))
    if (d_bg <= 40).mean() < 0.55:
        return False
    far = d_bg > 96
    if not far.any():
        return False
    fq = keys[far]
    fgk = int(np.bincount(fq).argmax())
    fg = np.array([(fgk >> 8) * 16 + 8, ((fgk >> 4) & 15) * 16 + 8, (fgk & 15) * 16 + 8])
    d_fg = np.sqrt(((px - fg) ** 2).sum(1))
    fg_share = (d_fg <= 48).mean()
    if not 0.04 <= fg_share <= 0.40:
        return False
    v = fg - bg
    t = np.clip(((px - bg) @ v) / max(float(v @ v), 1.0), 0, 1)
    off_line = np.sqrt((((px - bg) - np.outer(t, v)) ** 2).sum(1)) > 30
    if (off_line & (d_bg > 40) & (d_fg > 48)).mean() > 0.06:
        return False
    full = np.zeros(arr.shape[:2], bool)
    full[opaque] = d_fg <= 48
    ys, xs = full.nonzero()
    hgt, wid = (ys.max() - ys.min() + 1) / SIZE, (xs.max() - xs.min() + 1) / SIZE
    cy, cx = (ys.max() + ys.min()) / 2 / SIZE, (xs.max() + xs.min()) / 2 / SIZE
    if abs(cy - 0.5) > 0.12 or abs(cx - 0.5) > 0.12 or not 0.25 <= hgt <= 0.75 or not 0.10 <= wid <= 0.75:
        return False
    small = full[::2, ::2]
    parts = [s for s in _blobs(small) if s >= max(2, small.sum() * 0.01)]
    return 1 <= len(parts) <= 2


def quality(canvas, img):
    """The drop reasons for one normalised picture (empty = keep). img: logo.dev's facts (width, height, is_vector).
    Monogram-looking is not a drop reason: images() flags it (monogram_looking)."""
    np = _np()
    out = []
    if not img.get("is_vector") and min(int(img["width"]), int(img["height"])) < SMALL_PX:
        out.append("small")
    arr = np.asarray(canvas.convert("RGBA"))
    if (arr[..., 3] >= 32).mean() < BLANK_SHARE:
        return out + ["blank"]
    on_white = _composite(arr, 255.0)
    if ((255 - on_white.astype(np.int16)).max(axis=2) > FAINT_DIST).mean() < FAINT_SHARE:
        out.append("faint")
    elif top_share(on_white) >= ONE_COLOUR and top_share(_composite(arr, 0.0)) >= ONE_COLOUR:
        out.append("one_colour")
    return out


def wide(canvas, img):
    """True when a picture is wider (or taller) than BRANDMARK_MAX_ASPECT : 1 — by logo.dev's own size or by the drawn
    part of the downloaded picture (a vector without a size, or a rendition padded to a square). (pure)"""
    np = _np()
    w, h = img.get("width"), img.get("height")
    if w and h and max(w, h) / min(w, h) > BRANDMARK_MAX_ASPECT:
        return True
    a = np.asarray(canvas.convert("RGBA"))[..., 3] >= 32
    ys, xs = np.nonzero(a)
    if not len(xs):
        return False
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    return max(bw, bh) / min(bw, bh) > BRANDMARK_MAX_ASPECT


def fingerprint(canvas):
    """(64-bit difference hash, 16 x 16 colour thumbnail) of the picture laid on white."""
    from PIL import Image
    np = _np()
    flat = Image.fromarray(_composite(np.asarray(canvas.convert("RGBA")), 255.0))
    a = np.asarray(flat.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    thumb = np.asarray(flat.resize((16, 16), Image.LANCZOS), dtype=np.uint8).tobytes()
    return int("".join("1" if b else "0" for b in bits), 2), thumb


SAME_PICTURE = 6.0                               # mean colour difference (0-255) of the thumbnails for "the same picture"


def shared_groups(items):
    """items: [(code, fingerprint)] -> groups (lists of codes, 2 or more) showing the same picture: the same difference
    hash and thumbnails that differ by at most SAME_PICTURE on average. Only checked pairs join a group, so similar-
    looking but different logos never chain into one big group."""
    np = _np()
    buckets = collections.defaultdict(list)
    for c, (h, thumb) in items:
        buckets[h].append((c, np.frombuffer(thumb, dtype=np.uint8).astype(np.int16)))
    parent = {c: c for c, _ in items}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    for members in buckets.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if np.abs(members[i][1] - members[j][1]).mean() <= SAME_PICTURE:
                    parent[find(members[i][0])] = find(members[j][0])
    groups = collections.defaultdict(list)
    for c, _ in items:
        groups[find(c)].append(c)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g))


# ── the run ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def choose(r, c, ticker_only=False):
    """The ticker/homepage choice from the lookup results r (route -> (kind, info)): (route or None, check, why). The
    rules of the first run, unchanged (decide() uses it; the retry's early stop asks it too). (pure)"""
    t_kind, t = r.get("ticker", ("", {}))
    d_kind, d = r.get("domain", ("", {}))
    if t_kind == "logo" and d_kind == "logo":
        tb, db = t.get("brand_id") or "", d.get("brand_id") or ""
        if tb and db and tb == db:                       # a real brand_id match only (an equal etag is not enough)
            return "ticker", "same-brand", ""
        if tb and db:
            return "domain", "homepage-over-ticker", ""
        return "ticker", "unverified", "brand id missing from an answer"
    if t_kind == "logo":
        if c["side"] == "us":
            return "ticker", "ticker", ""
        return "ticker", "unverified", ("ticker only (--route ticker): no homepage lookup" if ticker_only
                                        else f"homepage {c['domain']}: {d_kind}" if d_kind
                                        else "no usable DART homepage domain")
    if d_kind == "logo":
        return "domain", "homepage", ""
    return None, "", ""


def usable(route, kind, info):
    """A lookup answer worth downloading before the checks: a logo whose source is a vector, or a raster whose shorter
    side is at least SMALL_PX (the 'small' check, read from logo.dev's own size). A brandmark (the wide lockup) must also be
    no wider than BRANDMARK_MAX_ASPECT : 1. (pure)"""
    if kind != "logo":
        return False
    img = info.get("image") or {}
    w, h = img.get("width"), img.get("height")
    if img.get("is_vector"):
        return route != "brandmark" or not (w and h) or max(w, h) / min(w, h) <= BRANDMARK_MAX_ASPECT
    if not (w and h) or min(w, h) < SMALL_PX:
        return False
    return route != "brandmark" or max(w, h) / min(w, h) <= BRANDMARK_MAX_ASPECT


class Job:
    """One company on its way through its lookups, download and checks."""

    def __init__(self, c, extra=False):
        self.c = c
        if extra and c.get("skip_known"):                 # letters retry: the old answer can't change — ISIN first
            self.stage = "isin" if c.get("isin") else "brandmark" if c.get("ticker") else "decide"
        elif c.get("ticker"):
            self.stage = "ticker"
        elif c["side"] == "kr" and c.get("domain"):
            self.stage = "domain"
        elif extra and c["side"] == "kr" and c.get("isin"):
            self.stage = "isin"
        else:
            self.stage = "decide"
        self.tries_202 = collections.Counter()
        self.lookups = []
        self.results = {}                    # route -> (kind, info)
        self.credits = self.requests = 0
        self.choice = None                   # route of the chosen logo
        self.check = ""                      # same-brand · homepage-over-ticker · unverified · homepage · ticker
        self.why = ""                        # detail for unverified
        self.final = None                    # logo · letter (None: not finished)
        self.reason = ""                     # why the letter mark
        self.flags = []                      # quality reasons found on the chosen picture
        self.file = ""
        self.bytes = 0
        self.cands = {}                      # route -> {"png": bytes for the sheet, "flags": [...], "error": str}
        self.hash = None
        self.dropped_file = ""               # its picture in dropped/ (a dropped logo)
        self.note = ""


class Scheduler:
    """New companies in market-cap order; a company waiting after a 202 comes back when its wait is over."""

    def __init__(self, jobs, clock, sleep):
        self.ready = collections.deque(jobs)
        self.pending = []
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.active = 0
        self.n = 0
        self.stopped = False

    def get(self):
        while True:
            with self.lock:
                if self.stopped:
                    return None
                now = self.clock()
                if self.pending and self.pending[0][0] <= now:
                    self.active += 1
                    return heapq.heappop(self.pending)[2]
                if self.ready:
                    self.active += 1
                    return self.ready.popleft()
                wait = self.pending[0][0] - now if self.pending else None
                if wait is None and self.active == 0:
                    return None
                self.wake.clear()
            if wait is not None:
                self.sleep(min(wait, 5.0))
            else:
                self.wake.wait(0.05)

    def later(self, job, delay):
        with self.lock:
            self.n += 1
            heapq.heappush(self.pending, (self.clock() + delay, self.n, job))
            self.active -= 1
        self.wake.set()

    def done(self):
        with self.lock:
            self.active -= 1
        self.wake.set()

    def stop(self):
        with self.lock:
            self.stopped = True
        self.wake.set()

    def leftover(self):
        with self.lock:
            return [p[2] for p in sorted(self.pending)] + list(self.ready)


class Fetcher:
    def __init__(self, client, ledger, log, out_logos, scope=(), clock=time.monotonic, sleep=time.sleep, jitter=None,
                 deadline=None, workers=DEFAULT_WORKERS, webp=True, out_dropped=None, need=0, ticker_only=False,
                 extra=False):
        self.client, self.ledger, self.log = client, ledger, log
        self.ticker_only = ticker_only                   # --route ticker: no homepage lookup, the ticker logo if it passes
        self.route = "ticker" if ticker_only else "auto"
        self.extra = extra                               # --extra-routes: ISIN, then brandmark, for Korean companies
        self.only_codes = []                             # --only: the named companies (for run.json)
        self.out_logos, self.scope, self.webp = out_logos, set(scope), webp
        self.out_dropped = out_dropped or out_logos.parent / "dropped"    # dropped pictures: never in logos/
        self.need = need                                 # this run's worst case in credits (min of cap and plan)
        self.clock, self._sleep, self.deadline, self.workers = clock, sleep, deadline, max(1, int(workers))
        self.jitter = jitter or random.SystemRandom().random
        self.lock = threading.Lock()
        self.counts = collections.Counter()
        self.done = []
        self.odd = 0                                     # odd answers (each one: that company's letter mark)
        self.download_streak = 0                         # failed picture downloads in a row
        self.used_files = set()
        self.unfinished = []
        self.remaining = []
        self.stop = None
        self.error_streak = 0
        self.total = 0

    def sleep(self, s):
        if s > 0:
            self._sleep(s)

    def count(self, key, n=1):
        with self.lock:
            self.counts[key] += n

    def set_stop(self, s):
        with self.lock:
            if self.stop is None:
                self.stop = s
                self.log(f"!! stopping: {s.reason}")

    # one request (with its 429 / 5xx / no-answer retries) -> (kind, info, credits, requests sent)
    def call(self, route, ident):
        rl = tr = spent = sent = 0
        price = ROUTE_COST.get(route, CREDITS)
        unanswered = False
        while True:
            if self.stop is not None:
                raise chk.StopRun("stopped", "another worker stopped the run")
            if self.deadline is not None and self.clock() >= self.deadline:
                raise chk.StopRun("time_limit", "reached the time limit (--time-limit-min): the results so far are "
                                                "saved and uploaded before the workflow's own limit")
            why = self.ledger.reserve(price)
            if why == "cap":
                raise chk.StopRun("max_credits", f"reached --max-credits {self.ledger.cap:,}: {self.ledger.counted:,} "
                                                 f"credits counted, and the next lookup could cost {price} more")
            if why == "unreadable":
                raise chk.StopRun("balance_unreadable", f"logo.dev's credit balance could not be read "
                                                        f"({str(self.ledger.unreadable)[:40]!r}): stopping")
            if why == "floor":
                raise chk.StopRun("balance_floor", f"logo.dev reports {self.ledger.balance:,.0f} credits left; one more "
                                                   f"lookup could take the balance below {MIN_BALANCE:,} (the cap across "
                                                   "runs): stopping")
            sent += 1
            try:
                resp = self.client.lookup(route, ident)
            except Exception as e:                       # noqa: BLE001 — no answer: counted, retried, kept
                self.count("no answer (network)")
                if not unanswered:
                    unanswered = True
                    spent += self.ledger.unanswered(price)
                else:
                    self.ledger.release(price)
                if tr < chk.RETRIES_TRANSIENT:
                    self.log(f"  !! {route} {ident}: no answer ({type(e).__name__}); trying again in {chk.BACKOFF_S[tr]} s")
                    self.sleep(chk.BACKOFF_S[tr])
                    tr += 1
                    self.count("retries after an error")
                    continue
                return "error", {"note": f"no answer after {tr + 1} tries ({type(e).__name__})"}, spent, sent
            spent += self.ledger.settle(resp, price)
            first, nobal, unreadable = self.ledger.take_notices()
            if unreadable is not None:
                self.set_stop(chk.StopRun("balance_unreadable", f"logo.dev reported a credit balance this tool cannot "
                                                                f"read ({unreadable[:40]!r}); without it the "
                                                                f"{MIN_BALANCE:,}-credit floor cannot be kept: no further "
                                                                "lookup, what was found is saved"))
            if first is not None:
                self.first_balance(first)
            if nobal:
                self.log(f"!! logo.dev 가 남은 크레딧을 알려 주지 않아요 — 이번 실행 상한 {self.ledger.cap:,} 만 지켜요")
            self.count(f"HTTP {resp.status}")
            if resp.status != 429:
                self._respect_window(resp.headers)
            if resp.status == 200:                       # read here: an odd answer is this company's, not the run's
                j = resp.json()
                img, why = parse_logo(j, "brandmark" if route == "brandmark" else "logo")
                if why:
                    return "odd", {"note": why, "http": 200}, spent, sent
                kind, info = "logo", {"image": img}
            else:
                try:
                    kind, info = chk.classify(resp)
                except chk.Unexpected as u:
                    return "odd", {"note": f"HTTP {resp.status}: {u}", "http": resp.status}, spent, sent
            info["http"] = resp.status
            if kind == "logo":
                data = j.get("data") if isinstance(j.get("data"), dict) else {}
                res = ((j.get("metadata") or {}).get("resolution") or {}) if isinstance(j.get("metadata"), dict) else {}
                info["brand_id"] = str(data.get("brand_id") or "")            # a real brand_id only
                info["method"] = str(res.get("method") or "") if isinstance(res, dict) else ""
                info["value"] = str(res.get("value") or "") if isinstance(res, dict) else ""
            if kind in ("logo", "not_found", "no_image", "retry"):
                return kind, info, spent, sent
            if kind == "bad_request":
                msg = self.log.mask(info["message"])[:160]
                return "error", {"note": f"logo.dev answered 400 {self.log.mask(info['code'])} {msg!r}", "http": 400}, spent, sent
            if kind == "out_of_credits":
                raise chk.StopRun("out_of_credits", "logo.dev answered 402 (insufficient_credits): the account has no "
                                                    "API credits left")
            if kind == "refused":
                raise chk.StopRun("error", f"logo.dev refused the request (HTTP {resp.status}"
                                           f"{' ' + info['code'] if info['code'] else ''}). Check that the repository "
                                           f"secret {KEY_ENV} holds logo.dev's secret key (sk_...).")
            if kind == "rate_limited":
                rl += 1
                if rl > chk.RETRIES_429:
                    raise chk.StopRun("error", f"logo.dev answered 429 (rate_limited) {rl} times in a row")
                wait, why = chk.rate_limit_wait(resp.headers, rl, self.jitter)
                if wait > chk.MAX_WAIT_429_S:
                    raise chk.StopRun("error", f"logo.dev asked to wait {wait:.0f} s ({why}), more than {chk.MAX_WAIT_429_S} s")
                self.log(f"  · 429 rate_limited: waiting {wait:.1f} s ({why})")
                self.count("retries after 429")
                self.client.api_pacer.hold(wait)
                continue
            if tr < chk.RETRIES_TRANSIENT:
                self.log(f"  !! {route} {ident}: HTTP {resp.status}; trying again in {chk.BACKOFF_S[tr]} s")
                self.sleep(chk.BACKOFF_S[tr])
                tr += 1
                self.count("retries after an error")
                continue
            return "error", {"note": f"logo.dev answered HTTP {resp.status} {tr + 1} times", "http": resp.status}, spent, sent

    def first_balance(self, v):
        """The first Credits-Remaining logo.dev reports: said loudly; below the worst case plus the floor -> stop."""
        need = self.need + MIN_BALANCE
        self.log(f"!! logo.dev reports {v:,.0f} credits left (Credits-Remaining, first answer) · this run's worst case "
                 f"{self.need:,} + floor {MIN_BALANCE:,} = {need:,} needed")
        if v < need:
            self.set_stop(chk.StopRun("balance_low", f"logo.dev reports {v:,.0f} credits left, below this run's worst "
                                                     f"case {self.need:,} plus the {MIN_BALANCE:,}-credit floor: no "
                                                     "further lookup; what was found is saved"))

    def _respect_window(self, headers):
        rem, reset = chk._int(headers.get("ratelimit-remaining")), chk._int(headers.get("ratelimit-reset"))
        if rem == 0 and reset is not None and reset > 0:
            self.count("holds (RateLimit-Remaining 0)")
            self.client.api_pacer.hold(min(reset, chk.MAX_WAIT_429_S))

    def next_stage(self, job, route, kind):
        """The stage after `route`: the DART homepage after the ticker (Korea), then — only with --extra-routes, only for a
        Korean company, and only while no route has given a usable logo — the ISIN, then the brandmark by ticker."""
        c = job.c
        if kind == "odd":
            return "decide"                              # an odd answer means a letter mark: no further lookup
        order = ["ticker"]
        if c["side"] == "kr" and c.get("domain") and not self.ticker_only:
            order.append("domain")
        if self.extra and c["side"] == "kr":
            if c.get("isin"):
                order.append("isin")
            if c.get("ticker"):
                order.append("brandmark")
        after = order[order.index(route) + 1:] if route in order else []
        for nxt in after:
            if nxt in EXTRA_ROUTES and self.has_usable(job):
                return "decide"                          # what decide() would choose is already usable
            return nxt
        return "decide"

    def pick(self, r, c):
        """(route, check, why): the first run's choice; with --extra-routes, when that choice is not usable, a usable
        homepage logo, else a usable ISIN logo, else a usable brandmark. decide() and the early stop both use this."""
        ch, check, why = choose(r, c, self.ticker_only)
        if not self.extra or (ch and usable(ch, *r[ch])):
            return ch, check, why
        if ch == "ticker" and "domain" in r and usable("domain", *r["domain"]):
            return "domain", "homepage", ""             # the homepage has the larger picture of the company's logo
        for rt in EXTRA_ROUTES:
            if rt in r and usable(rt, *r[rt]):
                return rt, rt, ""
        return ch, check, why

    def has_usable(self, job):
        ch = self.pick(job.results, job.c)[0]
        return bool(ch and usable(ch, *job.results[ch]))

    # one lookup stage -> None (stage finished) or seconds to wait (202)
    def lookup(self, job):
        c, route = job.c, job.stage
        ident = c["isin"] if route == "isin" else c["ticker"] if route in ("ticker", "brandmark") else c["domain"]
        kind, info, spent, sent = self.call(route, ident)
        job.credits += spent
        job.requests += sent
        job.lookups.append({"route": route, "id": ident, "http": info.get("http"),
                            "result": "not_indexed (retry)" if kind == "retry" else kind,
                            "brand_id": info.get("brand_id", "")})
        if kind == "retry":
            if info["wait_source"] != "Retry-After":
                self.count("202 without Retry-After")
            if info["wait"] > MAX_WAIT_202_S:
                self.count("202 not retried (wait too long)")
                info["note"] = f"logo.dev asked to wait {info['wait']} s: not retried"
                kind = "not_indexed"
            elif job.tries_202[route] < RETRIES_202:
                job.tries_202[route] += 1
                self.count("202 retries")
                return max(int(info["wait"]), 1)
            else:
                kind = "not_indexed"
        if kind == "odd":
            with self.lock:
                self.odd += 1
                n = self.odd
            self.log(f"!! odd answer {n} ({c['code']}, {route} {ident}): {info['note']} → letter mark")
            if n > ODD_STOP:
                self.set_stop(chk.StopRun("unexpected", f"more than {ODD_STOP} odd answers from logo.dev ({n}): its API "
                                                        "may have changed; what was found is saved"))
        job.results[route] = (kind, info)
        job.stage = self.next_stage(job, route, kind)
        return None

    def decide(self, job):
        r = job.results
        odd = [x.get("note", "") for k, x in r.values() if k == "odd"]
        if odd:                                          # an answer the docs don't describe: never a doubtful logo
            job.reason, job.note = "odd_answer", "; ".join(odd)
            return
        t_kind = r.get("ticker", ("", {}))[0]
        d_kind = r.get("domain", ("", {}))[0]
        job.choice, job.check, job.why = self.pick(r, job.c)
        if self.extra and not job.choice:                # an extra route found a picture that is not usable (small, wide):
            for rt in EXTRA_ROUTES:                      # download it anyway, so the named check drops it to dropped/
                if r.get(rt, ("", {}))[0] == "logo":
                    job.choice, job.check, job.why = rt, rt, ""
                    return
        if job.choice:
            return
        else:
            kinds = [k for k in (t_kind, d_kind) + tuple(r.get(rt, ("", {}))[0] for rt in EXTRA_ROUTES) if k]
            for k in ("no_image", "not_indexed", "error", "not_found"):
                if k in kinds:
                    job.reason = k
                    break
            else:
                job.reason = "no identifier"
            notes = [x.get("note") for _, x in r.values() if x.get("note")]
            job.note = "; ".join(notes)

    def images(self, job):
        """Downloads the chosen logo (and, for a company on the contact sheet, the other route's logo when it is a
        different picture), normalises it and runs the checks. Sets the final result."""
        routes = [job.choice] if job.choice else []
        if job.c["code"] in self.scope or job.check == "homepage-over-ticker":   # on the sheet: the other picture too
            chosen_etag = job.results[job.choice][1]["image"].get("etag") if job.choice else None
            for rt in ("ticker", "domain"):
                k, info = job.results.get(rt, ("", {}))
                if k == "logo" and rt not in routes and (not chosen_etag or info["image"].get("etag") != chosen_etag):
                    routes.append(rt)
        for rt in routes:
            img = job.results[rt][1]["image"]
            try:
                resp = self.client.download(img["url"], download_size(img))
            except Exception as e:                       # noqa: BLE001 — one picture: counted, said, the rest go on
                job.cands[rt] = {"png": None, "flags": [], "error": f"no answer ({type(e).__name__})"}
                self.download_failed(job, f"no answer ({type(e).__name__})")
                continue
            if resp.status in (401, 403):                # the image host refuses our signed addresses: stop at once
                job.cands[rt] = {"png": None, "flags": [], "error": f"HTTP {resp.status} from the image host"}
                self.set_stop(chk.StopRun("download_failures", f"the image host refused a signed download (HTTP "
                                                               f"{resp.status}, company {job.c['code']}): no further "
                                                               "lookup, so none is billed for nothing"))
                continue
            if not chk.image_kind(resp):
                job.cands[rt] = {"png": None, "flags": [], "error": f"HTTP {resp.status} "
                                 f"{resp.headers.get('content-type', '')!r}, {len(resp.body):,} bytes"}
                self.download_failed(job, f"HTTP {resp.status}")
                continue
            with self.lock:
                self.download_streak = 0
            try:
                if img.get("width") is None or img.get("height") is None:     # a vector without a size: the rendition's
                    from PIL import Image
                    with Image.open(io.BytesIO(resp.body)) as im0:
                        img["width"], img["height"] = im0.size
                    img["size_from"] = "download"
                canvas = normalise(resp.body)
            except Exception as e:                       # noqa: BLE001 — a picture that cannot be read
                job.cands[rt] = {"png": None, "flags": [], "error": f"unreadable picture ({type(e).__name__}: {e})"[:120]}
                continue
            flags = quality(canvas, img)
            if rt == "brandmark" and wide(canvas, img) and "wide_brandmark" not in flags:
                flags.insert(0, "wide_brandmark")       # the wide lockup does not read in the app's square
            if img.get("size_from") == "download":       # a size-less vector: judged on the downloaded picture
                self.log(f"!! {job.c['code']} ({rt}): size-less vector (source {img.get('format') or '?'}, no size) → "
                         f"judged on the downloaded {img['width']} x {img['height']} picture")
                if max(img["width"], img["height"]) < SMALL_PX and "small" not in flags:
                    flags.insert(0, "small")
            mono = not flags and is_monogram(_np().asarray(canvas.convert("RGBA")))
            buf = io.BytesIO()
            canvas.save(buf, "PNG")
            job.cands[rt] = {"png": buf.getvalue(), "flags": flags, "error": "", "canvas": canvas, "mono": mono}
        if not job.choice:
            job.final = "letter"
            return
        cand = job.cands.get(job.choice, {})
        if cand.get("error"):
            job.final, job.reason = "letter", "download_failed"
            job.note = cand["error"]
            self.count("downloads failed")
            return
        if cand.get("flags"):
            job.final, job.reason, job.flags = "letter", cand["flags"][0], list(cand["flags"])
            self.keep_dropped(job, cand["canvas"])
            return
        if not LI.CODE_RE.match(str(job.c["code"])):     # the index takes plain stock codes only
            job.final, job.reason, job.flags = "letter", "odd_code", ["odd_code"]
            self.log(f"  !! {job.c['code']!r}: not a plain stock code for logos/index.json → letter mark")
            return
        canvas = cand["canvas"]
        data, ext = encode(canvas, self.webp)
        name = f"{safe_file(job.c['code'])}.{ext}"
        with self.lock:
            clash = name in self.used_files
            self.used_files.add(name)
        if clash:                                        # never two codes in one file (only a preferred share reuses one)
            job.final, job.reason, job.flags = "letter", "file_clash", ["file_clash"]
            self.count("file name clashes")
            self.log(f"  !! {job.c['code']}: the file name {name} is taken by another code → letter mark")
            return
        (self.out_logos / name).write_bytes(data)
        job.final, job.file, job.bytes, job.hash = "logo", name, len(data), fingerprint(canvas)
        if cand.get("mono"):                             # kept, flagged, drawn on the review sheet
            job.flags.append("monogram-looking")
            self.count("monogram-looking (kept)")
        if job.results[job.choice][1]["image"].get("size_from") == "download":   # kept, flagged, on the sheet
            job.flags.append("sizeless-vector")
            self.count("size-less vectors (kept)")

    def download_failed(self, job, why):
        """A failed picture download; DOWNLOAD_STOP of them in a row stop the run (lookups would be billed for nothing)."""
        with self.lock:
            self.download_streak += 1
            n = self.download_streak
        if n >= DOWNLOAD_STOP:
            self.set_stop(chk.StopRun("download_failures", f"{n} picture downloads in a row failed (last: "
                                                           f"{job.c['code']}, {why}): no further lookup, so none is "
                                                           "billed for nothing"))

    def keep_dropped(self, job, canvas):
        """A dropped picture goes to dropped/ (never logos/), so --keep can restore it after review without paying."""
        if not LI.CODE_RE.match(str(job.c["code"])):
            return
        data, ext = encode(canvas, self.webp)
        name = f"{safe_file(job.c['code'])}.{ext}"
        self.out_dropped.mkdir(exist_ok=True)
        (self.out_dropped / name).write_bytes(data)
        job.dropped_file = name

    def finish(self, job):
        for cand in job.cands.values():
            cand.pop("canvas", None)
        with self.lock:
            self.done.append(job)
            n = len(self.done)
            if job.final == "letter" and job.reason == "error":
                self.error_streak += 1
            else:
                self.error_streak = 0
            trip = self.error_streak >= chk.ERROR_STOP
        if trip:
            self.set_stop(chk.StopRun("error", f"{chk.ERROR_STOP} companies in a row ended in an error"))
        c = job.c
        how = " → ".join(f"{x['route']} {x['id']}: {x['result']}" for x in job.lookups) or "no identifier"
        got = f"logo ({job.choice}, {job.check})" if job.final == "logo" else f"letter mark ({job.reason})"
        self.log(f"· [{n:>4}/{self.total}] {c['side'].upper()} {c['code']:<7} {c['name']} · {how} · {got}"
                 f" · credits {self.ledger.counted:,}/{self.ledger.cap:,}")
        if job.reason == "error" and job.note:
            self.log(f"  !! {c['code']}: {job.note}")
        if n % 100 == 0:
            t = collections.Counter(j.final for j in self.done)
            self.log(f"· progress: {n:,}/{self.total:,} · logos {t['logo']:,} · letter marks {t['letter']:,} · credits "
                     f"{self.ledger.counted:,}/{self.ledger.cap:,} · lookups {self.client.api_requests:,} · downloads "
                     f"{self.client.downloads:,}")

    def process(self, job):
        """-> None when the company is finished, else seconds to wait (202)."""
        while job.stage in ("ticker", "domain") + EXTRA_ROUTES:
            wait = self.lookup(job)
            if wait is not None:
                return wait
        self.decide(job)
        self.images(job)
        self.finish(job)
        return None

    def worker(self, sched):
        while True:
            job = sched.get()
            if job is None:
                return
            try:
                wait = self.process(job)
            except chk.StopRun as s:
                if s.outcome != "stopped":
                    self.set_stop(s)
                with self.lock:
                    self.unfinished.append(job)
                sched.done()
                sched.stop()
                return
            except chk.Unexpected as u:
                self.set_stop(chk.StopRun("unexpected", f"logo.dev answered in a way its docs don't describe: {u} "
                                                        f"(company {job.c['code']}, {job.stage} lookup)"))
                with self.lock:
                    self.unfinished.append(job)
                sched.done()
                sched.stop()
                return
            except Exception as e:                       # noqa: BLE001 — a bug: said, recorded, partial results saved
                self.set_stop(chk.StopRun("crashed", f"{type(e).__name__}: {e} (company {job.c['code']})"))
                for line in traceback.format_exc().splitlines():
                    self.log("  " + line)
                with self.lock:
                    self.unfinished.append(job)
                sched.done()
                sched.stop()
                return
            if wait is not None:
                sched.later(job, wait)
            else:
                sched.done()
            if self.stop is not None:
                sched.stop()
                return

    def run(self, companies):
        self.total = len(companies)
        jobs = [Job(c, self.extra) for c in companies]
        for j in jobs:
            if self.ticker_only and j.stage == "domain":
                j.stage = "decide"                       # --route ticker: no ticker, no lookup (the letter mark)
                j.note = "ticker only (--route ticker): this company has no ticker"
        sched = Scheduler(jobs, self.clock, self.sleep)
        if self.workers == 1:
            self.worker(sched)
        else:
            threads = [threading.Thread(target=self.worker, args=(sched,), daemon=True) for _ in range(self.workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.remaining = self.unfinished + sched.leftover()


# ── results ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def drop_shared(fetcher, groups, log):
    """A picture shared by companies whose chosen logos do not all have one real brand_id (a missing brand_id counts as
    unknown) is doubtful. In such a group a company whose own homepage confirmed its ticker logo (same-brand, an exact
    identifier) keeps it; every other member gets the letter mark and its picture moves to dropped/ (--keep restores
    it). Returns {"groups": [group numbers with a switch], "companies": [switched], "kept_same_brand": [kept]}."""
    by = {j.c["code"]: j for j in fetcher.done}
    out = {"groups": [], "companies": [], "kept_same_brand": []}
    for i, g in enumerate(groups, 1):
        jobs = [by[c] for c in g if c in by]
        brands = {(j.results.get(j.choice, ("", {}))[1].get("brand_id") or "") for j in jobs}
        if len(brands) == 1 and "" not in brands:
            log(f"· shared picture {i} kept (one brand, {next(iter(brands))}): " + ", ".join(g))
            continue
        keep = [j for j in jobs if j.check == "same-brand"]
        gone = [j for j in jobs if j.check != "same-brand"]
        out["kept_same_brand"] += [j.c["code"] for j in keep]
        if keep:
            log(f"!! shared picture {i}: kept for {', '.join(j.c['code'] for j in keep)} (confirmed by their own homepage)")
        if not gone:
            continue
        out["groups"].append(i)
        for j in gone:
            if j.file:
                fetcher.out_dropped.mkdir(exist_ok=True)
                (fetcher.out_logos / j.file).replace(fetcher.out_dropped / j.file)
                fetcher.used_files.discard(j.file)
                j.dropped_file = j.file
            j.final, j.reason, j.flags, j.file, j.bytes = "letter", "shared", ["shared"], "", 0
            out["companies"].append(j.c["code"])
        log(f"!! shared picture {i}: different or unknown brands → letter marks for "
            + ", ".join(j.c["code"] for j in gone))
    if out["companies"]:
        log(f"!! shared pictures across different brands: {len(out['companies']):,} companies switched to the letter "
            f"mark in {len(out['groups'])} groups · {len(out['kept_same_brand']):,} kept (same-brand)")
    return out


def dropped_index(fetcher, fmt, stamp):
    """dropped/index.json: every dropped picture saved in dropped/, with what --keep needs to restore it."""
    logos = {}
    for j in fetcher.done:
        if j.dropped_file and j.choice and (fetcher.out_dropped / j.dropped_file).exists():
            img = j.results[j.choice][1]["image"]
            logos[j.c["code"]] = {"file": j.dropped_file, "name": j.c["name"], "route": j.choice,
                                  "w": int(img["width"] or SIZE), "h": int(img["height"] or SIZE), "vector": bool(img.get("is_vector")),
                                  "flags": [j.reason] + ([j.check] if j.check else [])}
    return {"version": LI.VERSION, "size": SIZE, "format": fmt, "source": "logo.dev", "fetched_kst": stamp,
            "dropped": True, "count": len(logos), "logos": dict(sorted(logos.items()))}

def brand_domain(job):
    if job.final != "logo":
        return ""
    if job.choice == "domain":
        return job.results["domain"][1].get("value") or job.c.get("domain", "")
    if job.check == "same-brand":
        return job.c.get("domain", "")
    return ""


def rows_of(fetcher, preferred, groups):
    """One row per company (finished, unfinished, not started) and per preferred share."""
    shared = {c: i for i, g in enumerate(groups, 1) for c in g}
    rows, by = [], {}
    for job in fetcher.done + fetcher.remaining:
        c = job.c
        chosen = job.results.get(job.choice, ("", {}))[1].get("image", {}) if job.choice else {}
        t_kind, t = job.results.get("ticker", ("", {}))
        d_kind, d = job.results.get("domain", ("", {}))
        unfinished = job.final is None
        row = {"rank": c.get("rank", ""), "market_rank": c.get("mrank", ""), "code": c["code"], "name": c["name"],
               "market": c.get("market", ""), "cap": cap_of(c) or "", "ticker": c.get("ticker", ""),
               "domain": c.get("domain", ""), "dart_homepage": c.get("hm_url", ""),
               "result": job.final or "", "route": job.choice or "",
               "check": job.check if job.choice else "", "reason": job.reason if job.final == "letter" else "",
               "flags": " ".join(job.flags), "unverified_why": job.why, "ticker_status": t_kind,
               "ticker_brand": t.get("brand_id", ""), "domain_status": d_kind, "domain_brand": d.get("brand_id", ""),
               "brand_domain": brand_domain(job),
               "resolution": job.results[job.choice][1].get("method", "") if job.choice else "",
               "size_from": (chosen.get("size_from") or "source") if chosen else "", "width": chosen.get("width", ""), "height": chosen.get("height", ""),
               "format": chosen.get("format", ""), "vector": chosen.get("is_vector", ""),
               "transparency": chosen.get("has_transparency", ""), "etag": chosen.get("etag", ""),
               "file": job.file, "bytes": job.bytes or "", "credits": job.credits, "requests": job.requests,
               "shared_group": shared.get(c["code"], ""), "via": "",
               "isin": c.get("isin", "") if "isin" in job.results else "",
               "isin_status": job.results.get("isin", ("", {}))[0], "isin_brand": job.results.get("isin", ("", {}))[1].get("brand_id", ""),
               "brandmark_status": job.results.get("brandmark", ("", {}))[0],
               "brandmark_size": ("{}x{}".format((job.results["brandmark"][1].get("image") or {}).get("width"),
                                                 (job.results["brandmark"][1].get("image") or {}).get("height"))
                                  if job.results.get("brandmark", ("", {}))[0] == "logo" else ""),
               "note": ("unfinished: " + "; ".join(f"{x['route']} {x['result']}" for x in job.lookups) if job.lookups
                        else "not looked up: the run stopped first") if unfinished else job.note}
        rows.append(row)
        by[c["code"]] = (job, row)
    for p in preferred:
        job, row = by.get(p["issuer"], (None, None))
        ok = job is not None and job.final == "logo"
        rows.append({"rank": "", "market_rank": "", "code": p["code"], "name": p["name"], "market": "", "cap": cap_of(p) or "",
                     "ticker": "", "domain": "", "dart_homepage": "", "result": "logo" if ok else ("letter" if job is None or job.final else ""),
                     "route": row["route"] if ok else "", "check": row["check"] if ok else "",
                     "reason": "" if ok else ("issuer not in data.json" if not p["issuer_listed"] else
                                              (f"issuer {p['issuer']}: {row['reason'] or 'unfinished'}" if row else "")),
                     "flags": "", "unverified_why": "", "ticker_status": "", "ticker_brand": "", "domain_status": "",
                     "domain_brand": "", "brand_domain": row["brand_domain"] if ok else "", "resolution": "",
                     "size_from": row["size_from"] if ok else "",
                     "width": row["width"] if ok else "", "height": row["height"] if ok else "",
                     "format": row["format"] if ok else "", "vector": row["vector"] if ok else "",
                     "transparency": row["transparency"] if ok else "", "etag": row["etag"] if ok else "",
                     "file": row["file"] if ok else "", "bytes": "", "credits": 0, "requests": 0, "shared_group": "",
                     "via": p["issuer"], "note": "preferred share: reuses its issuer's logo (no lookup of its own)"})
    return rows


def make_index(rows, stamp, data, fmt):
    logos = {}
    for r in rows:
        if r["result"] != "logo" or r["via"]:
            continue
        logos[r["code"]] = {"file": r["file"], "name": r["name"], "route": r["route"], "w": int(r["width"] or SIZE),
                            "h": int(r["height"] or SIZE), "vector": bool(r["vector"]),
                            "flags": ([r["check"]] if r["check"] else []) + r["flags"].split()}
    for r in rows:
        if r["result"] == "logo" and r["via"] and r["via"] in logos:
            e = logos[r["via"]]
            logos[r["code"]] = dict(e, name=r["name"], via=r["via"])
    return {"version": LI.VERSION, "size": SIZE, "format": fmt, "source": "logo.dev", "fetched_kst": stamp,
            "data_pxDate": data.get("pxDate"), "count": len(logos), "logos": dict(sorted(logos.items()))}


CSV_COLS = ["rank", "market_rank", "code", "name", "market", "cap", "ticker", "domain", "dart_homepage", "result", "route", "check",
            "reason", "flags", "unverified_why", "ticker_status", "ticker_brand", "domain_status", "domain_brand",
            "brand_domain", "resolution", "size_from", "width", "height", "format", "vector", "transparency", "etag", "file", "bytes", "credits",
            "requests", "shared_group", "via", "note", "isin", "isin_status", "isin_brand", "brandmark_status", "brandmark_size"]


def tally(rows):
    """Counts for the summary."""
    out = {}
    for side, label in (("kr", "Korea (common shares)"), ("us", "US")):
        mine = [r for r in rows if not r["via"] and (r["market"] != "US") == (side == "kr")]
        fin = [r for r in mine if r["result"]]
        out[side] = {"label": label, "companies": len(mine), "finished": len(fin),
                     "by_ticker": sum(1 for r in fin if r["result"] == "logo" and r["route"] == "ticker"),
                     "by_domain": sum(1 for r in fin if r["result"] == "logo" and r["route"] == "domain"),
                     "by_isin": sum(1 for r in fin if r["result"] == "logo" and r["route"] == "isin"),
                     "by_brandmark": sum(1 for r in fin if r["result"] == "logo" and r["route"] == "brandmark"),
                     "letter": sum(1 for r in fin if r["result"] == "letter"),
                     "reasons": collections.Counter(r["reason"] for r in fin if r["result"] == "letter"),
                     "checks": collections.Counter(r["check"] for r in fin if r["result"] == "logo")}
    pref = [r for r in rows if r["via"]]
    out["preferred"] = {"companies": len(pref), "logo": sum(1 for r in pref if r["result"] == "logo")}
    kr = [r for r in rows if not r["via"] and r["market"] != "US" and r["result"]]
    out["unverified_why"] = collections.Counter(re.sub(r"^homepage \S+: ", "homepage: ", r["unverified_why"])
                                                for r in kr if r["check"] == "unverified" and r["result"] == "logo")
    flags = collections.Counter()
    for r in rows:
        for f in r["flags"].split():
            flags[f] += 1
    out["flags"] = flags
    return out


def _pct(n, d):
    return f"{n:,} ({100.0 * n / d:.1f}%)" if d else f"{n:,} (–)"


def _billed_text(cr):
    """'98 × 2 + 7 × 3'. A run record from before the 2026-11-07 retry has no billed_at: every billed lookup then was a
    2-credit logo lookup (charged + billable without the header)."""
    at = cr.get("billed_at")
    if at is None:
        n = cr.get("charged", 0) + cr.get("no_header", 0)
        return f"{n:,} × {CREDITS}" if n else "0"
    return " + ".join(f"{n:,} × {p}" for p, n in sorted(at.items(), key=lambda x: int(x[0]))) or "0"


def summary_md(info):
    t, cr, rq = info["tally"], info["credits"], info["requests"]
    out = ["# logo.dev logos (v19.3a)", "",
           f"Run {info['started_kst']} – {info['finished_kst']} KST · data.json prices {info['data']['pxDate']} "
           f"(US {info['data']['usPxDate']}) · logo files: {info['format'].upper()} {SIZE} × {SIZE}", "",
           f"**{OUTCOME_TEXT.get(info['outcome'], info['outcome'])}** {info['reason'] or ''}".rstrip(), "",
           *([f"**A fix-up for named companies (--only {', '.join(info['only'])}, route {info.get('route', 'auto')})**: "
              "look at it, then add it to the reviewed folder with --add-from.", ""] if info.get("only") else []),
           f"Companies finished: **{info['finished']:,} of {info['companies']:,}**"
           + (f" ({info['unfinished']:,} unfinished or not started: they show the letter mark)"
              if info["finished"] < info["companies"] else ""), ""]
    for p in info["problems"]:
        out.append(f"- !! {p}")
    if info["problems"]:
        out.append("")
    out += ["## Coverage", "", "Shares are of the companies finished in that market.", "",
            "| Market | Companies | Finished | Logo by ticker | Logo by DART homepage | Logo by ISIN | Brandmark | Letter mark |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for side in ("kr", "us"):
        m = t[side]
        out.append(f"| {m['label']} | {m['companies']:,} | {m['finished']:,} | {_pct(m['by_ticker'], m['finished'])} | "
                   f"{_pct(m['by_domain'], m['finished'])} | {_pct(m.get('by_isin', 0), m['finished'])} | "
                   f"{_pct(m.get('by_brandmark', 0), m['finished'])} | {_pct(m['letter'], m['finished'])} |")
    p = t["preferred"]
    out += ["", f"Korean preferred shares: {p['companies']:,}, of which {p['logo']:,} reuse their issuer's logo "
                "(no lookup of their own); the rest show the letter mark.", "",
            "Letter marks by reason: " + "; ".join(
                f"{t[s]['label']}: " + (", ".join(f"{k} {v:,}" for k, v in sorted(t[s]['reasons'].items())) or "none")
                for s in ("kr", "us")) + ".", "",
            "## Korea: ticker against the DART homepage", "",
            "The logo lookup returns brand_id, not a brand domain, so the homepage lookup checks the ticker's brand.", ""]
    ck = t["kr"]["checks"]
    out += [f"- same brand by ticker and homepage (ticker logo kept): **{ck.get('same-brand', 0):,}**",
            f"- the homepage reached another brand with a logo (homepage logo used instead): **{ck.get('homepage-over-ticker', 0):,}**",
            f"- ticker logo kept, unverified: **{ck.get('unverified', 0):,}** — "
            + (", ".join(f"{k} {v:,}" for k, v in sorted(t['unverified_why'].items())) or "none"),
            f"- no ticker logo, homepage logo used: **{ck.get('homepage', 0):,}**", "",
            "## Automatic quality checks", "",
            "Counted on the chosen picture (dropped → letter mark), plus companies whose final logo is shared:", ""]
    out += [f"- {k}: **{t['flags'].get(k, 0):,}**" for k in DROP_REASONS]
    out += [f"- monogram-looking, kept and flagged (never dropped): **{t['flags'].get('monogram-looking', 0):,}**",
            f"- size-less vectors (no size in the answer; judged on the downloaded picture), kept and flagged: "
            f"**{t['flags'].get('sizeless-vector', 0):,}**",
            f"- odd answers from logo.dev (letter mark, reason odd_answer): **{info.get('odd', 0):,}** (the run stops "
            f"above {ODD_STOP})"]
    sd = info.get("shared_dropped") or {"groups": [], "companies": [], "kept_same_brand": []}
    out += [f"- shared pictures: **{len(info['shared'])}** groups, {sum(len(g) for g in info['shared']):,} companies: "
            f"**{len(sd['companies']):,}** companies of different or unknown brands switched to letter marks (in "
            f"{len(sd['groups'])} groups), **{len(sd['kept_same_brand']):,}** kept because their own homepage "
            "confirmed them (same-brand); groups of one brand kept", "",
            f"Every dropped picture is in dropped/ (never published); `--keep CODES --dir DIR` restores one after review. "
            f"Restored after review: {', '.join(k['code'] for k in info.get('keeps', [])) or 'none'}.", "",
            QUALITY_NOTE, "",
            "## Credits and requests", "",
            f"- Credits counted: **{cr['counted']:,}** of the {info['max_credits']:,} cap (${cr['counted'] / 100:,.2f}) — "
            f"billed answers {_billed_text(cr)} "
            f"({cr['charged']:,} marked Credits-Charged: 1, {cr['no_header']:,} billable without the header; 2 credits a "
            f"logo lookup, 3 a brandmark), and {cr.get('unanswered', 0):,} requests that got no answer "
            f"({cr['unknown']:,} credits). "
            f"{cr['free']:,} answers were free (Credits-Charged: 0).",
            f"- Balance logo.dev reported (Credits-Remaining), first → last answer: {cr['balance_first'] or 'not reported'}"
            f" → {cr['balance_last'] or 'not reported'}.",
            f"- Ceiling before the run (every lookup billed): {info['plan']['ceiling']:,} credits for "
            f"{info['plan']['lookups']:,} lookups ({info['plan']['ticker']:,} by ticker, {info['plan']['domain']:,} by "
            "DART homepage" + (f", {info['plan'].get('isin', 0):,} by ISIN, {info['plan'].get('brandmark', 0):,} brandmarks"
                               if info["plan"].get("isin") or info["plan"].get("brandmark") else "") + ").",
            f"- API lookups sent: **{rq['api']:,}** (retries after 202: {rq['counts'].get('202 retries', 0):,} · after "
            f"429: {rq['counts'].get('retries after 429', 0):,} · after an error: "
            f"{rq['counts'].get('retries after an error', 0):,}) · downloads: {rq['downloads']:,} (not billed, not CDN "
            f"requests) · failed downloads of a chosen logo: {rq['counts'].get('downloads failed', 0):,}.",
            f"- Pace: at most {info['pace']['per_minute']} lookups a minute, {info['pace']['workers']} open at once, "
            f"downloads at most {DOWNLOADS_PER_MINUTE} a minute · run time {info['minutes']:.1f} min.", "",
            "## Review sheet", "",
            f"sheet.html{' and ' + ', '.join(info['sheet_pages']) if info['sheet_pages'] else ' (no PNG pages)'}, every "
            "tile in each category, no caps (chosen logo or letter mark, with any dropped picture beside it):", ""]
    out += [f"- {title}: **{n:,}**" for title, n in info.get("sheet_counts", [])]
    out += [""]
    if info.get("drops"):
        out += ["## Switched to the letter mark after review", ""]
        out += [f"- {d['code']} {d['name']} — {d['reason']}" for d in info["drops"]]
        out.append("")
    if info.get("adds"):
        out += ["## Added after review (from a --only run)", ""]
        out += [f"- {d['code']} {d['name']} — {d['reason']}" for d in info["adds"]]
        out.append("")
    out += ["## Sources", ""] + [f"- {s}" for s in info["sources"]] + [
        "", "Files: logos/ (pictures + index.json, for tools/push_logos_branch.sh), review.csv (one row per company), "
            "run.json, run.log. Signed image addresses are never kept (they expire after about 24 hours).", ""]
    return "\n".join(out)


# ── contact sheet ───────────────────────────────────────────────────────────────────────────────────────────────────

def mark_colors():
    src = (ROOT / "src" / "v2" / "company.js").read_text(encoding="utf-8")
    cols = re.findall(r'"(#[0-9A-F]{6})"', src.split("export const MARK_COLORS = [", 1)[1].split("]", 1)[0])
    assert len(cols) == 10, cols
    return cols


def mark_color(code, cols):
    """src/v2/company.js markColor: FNV-1a over the code's characters."""
    h = 2166136261
    for ch in str(code or ""):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return cols[h % len(cols)]


def mark_letter(name, code):
    n = str(name or code or "").strip()
    ch = n[0] if n else ""
    return ch.upper() if "a" <= ch <= "z" else ch


SHEET_CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 20px; background: #FFFFFF; color: #1C2B45; font-size: 12px; line-height: 1.35;
       font-family: 'Pretendard Variable', Pretendard, sans-serif; }
h1 { font-size: 20px; margin: 0 0 4px; } h2 { font-size: 15px; margin: 18px 0 8px; }
.meta { color: #5B6576; margin: 0 0 6px; }
.grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
.card { border: 1px solid #E3E6EB; border-radius: 10px; padding: 8px; }
.card.drop { border-color: #C9A64A; }
.row { display: flex; gap: 8px; align-items: center; }
.box { width: 72px; height: 72px; border-radius: 20px; overflow: hidden; position: relative; flex-shrink: 0;
       background: #FFFFFF; border: 1px solid #E3E6EB; }
.box img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
.mark { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #FFFFFF;
        font-weight: 800; font-size: 32px; }
.small { display: flex; flex-direction: column; gap: 3px; }
.small img { width: 36px; height: 36px; border: 1px solid #E3E6EB; border-radius: 8px; background: #F1F3F6; opacity: .75; }
.name { font-weight: 700; margin-top: 6px; overflow-wrap: anywhere; }
.line { color: #5B6576; overflow-wrap: anywhere; }
.bad { color: #8A5A00; font-weight: 700; }
.id { color: #1C2B45; }
"""


def _tile(r, cands, cols):
    e = html.escape
    if r["result"] == "logo" and cands.get(r["route"], {}).get("png"):
        inner = f'<img alt="" src="data:image/png;base64,{base64.b64encode(cands[r["route"]]["png"]).decode()}">'
    else:
        inner = (f'<span class="mark" style="background:{mark_color(r["code"], cols)}">'
                 f'{e(mark_letter(r["name"], r["code"]))}</span>')
    extra = []
    for rt, cd in sorted(cands.items()):
        if r["result"] == "logo" and rt == r["route"]:
            continue
        why = (" ".join(cd.get("flags") or []) or ("download failed" if cd.get("error") else "")
               or (r["reason"] if rt == r["route"] and r["result"] != "logo" and r["reason"] else "not chosen"))
        if cd.get("png"):
            extra.append(f'<div><img alt="" src="data:image/png;base64,{base64.b64encode(cd["png"]).decode()}">'
                         f'<div class="line bad">{e(rt)}: {e(why)}</div></div>')
        else:
            extra.append(f'<div class="line bad">{e(rt)}: {e(why)}</div>')
    what = (f"{e(r['route'])} · {e(r['check'])}" + (f" · {e(r['flags'])}" if r["flags"] else "") if r["result"] == "logo"
            else f'<span class="bad">letter mark · {e(r["reason"] or "unfinished")}</span>')
    src = (f"{r['width']}×{r['height']} {e(str(r['format']))}{' vector' if r['vector'] is True else ''}"
           if r["width"] != "" else "")
    return (f'<div class="card{" drop" if r["result"] != "logo" else ""}"><div class="row"><div class="box">{inner}</div>'
            f'<div class="small">{"".join(extra)}</div></div>'
            f'<div class="name">{e(r["name"])}</div>'
            f'<div class="line">{e(r["code"])} · #{e(str(r["market_rank"]))} {e(r["market"])}</div>'
            f'<div class="line">{what}</div><div class="line">{src}</div>'
            + (f'<div class="line">{e(r["unverified_why"])}</div>' if r["unverified_why"] else "")
            + (f'<div class="line">shared picture group {r["shared_group"]}</div>' + _identity(r) if r["shared_group"]
               else "")
            + "</div>")


def _identity(r):
    """For a shared-picture tile: the company's own DART homepage (Korea) and logo.dev's brand (brand_id, and the brand
    domain when known), so --keep is decided by the company's own homepage, never by its name."""
    e = html.escape
    brand = r["ticker_brand"] if r["route"] == "ticker" else r["domain_brand"] if r["route"] == "domain" else ""
    home = r["domain"] or r.get("dart_homepage") or ""
    lines = [f'DART homepage: {e(home) or "none"}' if r["market"] != "US" else "DART homepage: — (US)",
             f'logo.dev brand: {e(brand) or "unknown"}' + (f' · {e(r["brand_domain"])}' if r["brand_domain"] else "")]
    return "".join(f'<div class="line id">{x}</div>' for x in lines)


def sheet_sections(rows, jobs, groups, top):
    """[(title, [row, ...])] in the order the sheet shows them."""
    comp = [r for r in rows if not r["via"]]
    secs = []
    for side, label in (("kr", "Korea"), ("us", "US")):
        mine = sorted((r for r in comp if (r["market"] != "US") == (side == "kr") and r["market_rank"] != ""
                       and int(r["market_rank"]) <= top), key=lambda r: int(r["market_rank"]))
        secs.append((f"{label}: the {top} largest by market cap", mine))
    outside = [r for r in comp if r["market"] != "US" and (r["market_rank"] == "" or int(r["market_rank"]) > top)
               and r["result"] == "logo"]
    for check, title in (("homepage-over-ticker", "homepage logo used instead of a different ticker brand"),
                         ("unverified", "ticker logo kept, unverified by the DART homepage"),
                         ("homepage", "no ticker logo, homepage logo used")):
        mine = sorted((r for r in outside if r["check"] == check), key=lambda r: int(r["market_rank"] or 10 ** 6))
        secs.append((f"Korea outside the top {top}: {title}", mine))
    rank = lambda r: (r["market"] == "US", int(r["market_rank"] or 10 ** 6))    # noqa: E731
    for check, title in (("isin", "logo found by ISIN (--extra-routes)"),
                         ("brandmark", "brandmark (wide lockup) found by ticker (--extra-routes)")):
        secs.append((f"Korea, any rank: {title}", sorted((r for r in comp if r["check"] == check and r["result"] == "logo"),
                                                         key=lambda r: int(r["market_rank"] or 10 ** 6))))
    secs.append(("Monogram-looking (kept): every company, any rank",
                 sorted((r for r in comp if "monogram-looking" in r["flags"].split()), key=rank)))
    secs.append(("Size-less vector (kept): every company, any rank",
                 sorted((r for r in comp if "sizeless-vector" in r["flags"].split()), key=rank)))
    secs.append(("Odd answers from logo.dev (letter mark): every company, any rank",
                 sorted((r for r in comp if r["reason"] == "odd_answer"), key=rank)))
    by = {r["code"]: r for r in comp}
    for i, g in enumerate(groups, 1):
        mine = [by[c] for c in g if c in by]
        n_gone = sum(1 for r in mine if r["reason"] == "shared")
        what = ("kept (one brand)" if not n_gone else f"{n_gone} switched to letter marks (different brands)"
                + (f", {len(mine) - n_gone} kept (same-brand)" if n_gone < len(mine) else ""))
        secs.append((f"Shared picture, group {i}: {len(g)} companies, {what}", mine))
    return secs


def sheet_page(title_meta, sections, cands, cols, font_href=None):
    e = html.escape
    parts = ["<!DOCTYPE html>", '<html lang="ko"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<meta name="robots" content="noindex">', "<title>logo.dev logos</title>"]
    if font_href:
        parts.append(f'<link rel="stylesheet" href="{e(font_href)}">')
    parts += [f"<style>{SHEET_CSS}</style></head><body>", "<h1>logo.dev logos (v19.3a)</h1>",
              f'<p class="meta">{e(title_meta)}</p>']
    for title, rs in sections:
        parts.append(f"<h2>{e(title)} · {len(rs)}</h2>")
        if not rs:
            parts.append('<p class="meta">none</p>')
            continue
        parts.append('<div class="grid">' + "".join(_tile(r, cands.get(r["code"], {}), cols) for r in rs) + "</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def paginate(sections, per_page=TILES_PER_PAGE):
    """Split the sections into pages of at most per_page tiles (a section may continue on the next page)."""
    pages, cur, n = [], [], 0
    for title, rs in sections:
        i = 0
        while i < len(rs) or (not rs and i == 0):
            room = per_page - n
            if room <= 0:
                pages.append(cur)
                cur, n = [], 0
                room = per_page
            part = rs[i:i + room]
            cur.append((title if i == 0 else title + " (continued)", part))
            n += max(len(part), 1)
            i += max(len(part), 1)
    if cur:
        pages.append(cur)
    return pages


def render_pages(pages, meta, cands, cols, folder, log):
    """sheet-01.png … with Playwright's Chromium, Pretendard by file path; every Korean letter must be drawn in
    Pretendard and every picture must load (tools/render_og.py's check). Returns (file names, problem or None)."""
    sys.path.insert(0, str(ROOT / "tools"))
    from playwright.sync_api import sync_playwright
    from render_og import CHECK_JS, FAMILY, FONT_CSS
    if not FONT_CSS.exists():
        return [], f"sheet PNG pages not drawn: {FONT_CSS} is missing"
    names, problem = [], None

    def one(browser, i, secs, tmp):
        """None when sheet-NN.png was written, else the problem. A fresh context per page keeps memory flat."""
        ctx = browser.new_context(viewport={"width": 1240, "height": 900}, device_scale_factor=1)
        try:
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(tmp.as_uri(), wait_until="load")
            korean = "".join(r["name"] + mark_letter(r["name"], r["code"]) for _, rs in secs for r in rs) + "한국"
            r = page.evaluate(CHECK_JS, [FAMILY, korean])
            if errors:
                return f"sheet page {i}: page errors {errors[:3]}"
            if r["bad"]:
                return f"sheet page {i}: Pretendard did not draw {r['bad'][:10]}"
            if not all(ok and w > 0 for ok, w in r["imgs"]):
                return f"sheet page {i}: a picture did not load"
            page.screenshot(path=str(folder / f"sheet-{i:02d}.png"), full_page=True)
            return None
        finally:
            ctx.close()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for i, secs in enumerate(pages, 1):
                tmp = folder / f".sheet-{i:02d}.html"
                tmp.write_text(sheet_page(f"{meta} · page {i} of {len(pages)}", secs, cands, cols, FONT_CSS.as_uri()),
                               encoding="utf-8")
                try:
                    try:
                        problem = one(browser, i, secs, tmp)
                    except Exception as e:               # noqa: BLE001 — once more in a new browser, then give up
                        log(f"  !! sheet page {i}: {type(e).__name__}; trying once more in a new browser")
                        browser.close()
                        browser = p.chromium.launch()
                        problem = one(browser, i, secs, tmp)
                finally:
                    tmp.unlink(missing_ok=True)
                if problem:
                    break
                names.append(f"sheet-{i:02d}.png")
        finally:
            browser.close()
    log(f"· contact sheet: {len(names)} PNG pages" + (f" · !! {problem}" if problem else ""))
    return names, problem


# ── output ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _put(folder, name, text, mask):
    (folder / name).write_text(mask(text), encoding="utf-8")


def write_csv(folder, rows, mask):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    _put(folder, "review.csv", buf.getvalue(), mask)


def write_reports(folder, info, log, mask):
    _put(folder, "summary.md", info["summary_text"] if "summary_text" in info else summary_md(info), mask)
    _put(folder, "run.json", json.dumps(info, ensure_ascii=False, indent=1, allow_nan=False, default=str), mask)
    _put(folder, "run.log", "\n".join(log.lines) + "\n", mask)


def find_urls(folder):
    return [p for p in sorted(pathlib.Path(folder).rglob("*")) if p.is_file() and URL_NEEDLE in p.read_bytes()]


def verdict(path):
    try:
        info = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        outcome, ok = info["outcome"], info["ok"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"!! cannot read the run's outcome from {path}: {type(e).__name__}")
        return 1
    print(f"{'OK' if ok is True else '!! NOT OK'}: {OUTCOME_TEXT.get(outcome, outcome)} {info.get('reason') or ''}"
          f" Finished {info.get('finished')} of {info.get('companies')}. Problems: {info.get('problems') or 'none'}")
    return 0 if ok is True else 1


def read_dropped(dropped):
    """dropped/index.json (an empty one when there is none). Refuses a dropped/ folder that is not valid."""
    if not (dropped / LI.INDEX).exists():
        return {"version": LI.VERSION, "size": SIZE, "dropped": True, "count": 0, "logos": {}}
    index, bad = LI.validate_dir(dropped)
    if bad:
        raise SystemExit("!! dropped/ is not a valid folder: " + "; ".join(bad[:5]))
    return index


def write_index(folder, index):
    folder.mkdir(exist_ok=True)
    index["count"] = len(index["logos"])
    index["logos"] = dict(sorted(index["logos"].items()))
    (folder / LI.INDEX).write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                   encoding="utf-8")


def _dedupe(codes):
    out = []
    for c in (str(x).strip() for x in codes):
        if c and c not in out:
            out.append(c)
    return out


def _files(folder):
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.name != LI.INDEX} if folder.exists() else {}


def _copy(index):
    return json.loads(json.dumps(index))


def commit_switch(logos, dropped, index, dindex, moves):
    """All or nothing, for --keep and --drop. moves: [(file name, "to_dropped" | "to_logos")]. First the result is
    checked in memory (each index against the files its folder would hold); then the files move and both indexes are
    written and checked on disk. On any error every file and both indexes are put back as they were."""
    lfiles, dfiles = _files(logos), _files(dropped)
    for name, way in moves:
        src, dst = (lfiles, dfiles) if way == "to_dropped" else (dfiles, lfiles)
        if name not in src or name in dst:
            raise SystemExit(f"!! {name} cannot move ({way.replace('_', ' ')}); nothing was changed")
        dst[name] = src.pop(name)
    for idx in (index, dindex):
        idx["count"] = len(idx["logos"])
        idx["logos"] = dict(sorted(idx["logos"].items()))
    bad = [f"logos/: {b}" for b in LI.check_index(index, lfiles)] + \
          [f"dropped/: {b}" for b in LI.check_index(dindex, dfiles)]
    if bad:
        raise SystemExit("!! the switch would leave a folder that is not valid (" + "; ".join(bad[:5]) + "); nothing "
                         "was changed")
    old = {f: ((f / LI.INDEX).read_bytes() if (f / LI.INDEX).exists() else None) for f in (logos, dropped)}
    had_dropped = dropped.exists()
    done = []
    try:
        dropped.mkdir(exist_ok=True)
        for name, way in moves:
            src, dst = (logos, dropped) if way == "to_dropped" else (dropped, logos)
            (src / name).replace(dst / name)
            done.append((src / name, dst / name))
        write_index(logos, index)
        write_index(dropped, dindex)
        for f, what in ((logos, "logos/"), (dropped, "dropped/")):
            _, bad = LI.validate_dir(f)
            if bad:
                raise SystemExit(f"!! {what} is not valid after the switch: " + "; ".join(bad[:5]))
    except BaseException:
        for src, dst in reversed(done):
            dst.replace(src)
        for f, raw in old.items():
            if raw is None:
                (f / LI.INDEX).unlink(missing_ok=True)
            else:
                (f / LI.INDEX).write_bytes(raw)
        if not had_dropped:
            try:
                dropped.rmdir()
            except OSError:
                pass
        raise


def _record_info(folder, kind, new):
    """The folder's updated run.json record and summary text, built in memory only. Called before a switch touches any
    file, so a record that cannot be written (an unreadable run.json, a summary that fails on an older record) stops the
    switch with nothing changed. -> (info, summary text or None)"""
    info = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    info[kind] = info.get(kind, []) + new
    json.dumps(info, ensure_ascii=False, allow_nan=False)
    return info, (None if "summary_text" in info else summary_md(info))


def _record(folder, kind, new):
    """keeps.csv / drops.csv, run.json and summary.md after a switch."""
    path = folder / f"{kind}.csv"
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "reason"], lineterminator="\n")
        if not exists:
            w.writeheader()
        w.writerows(new)
    info = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    info[kind] = info.get(kind, []) + new
    (folder / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    if "summary_text" not in info:
        (folder / "summary.md").write_text(summary_md(info), encoding="utf-8")


def _review_rows(folder):
    with open(folder / "review.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def keep(folder, codes, reason):
    """The mirror of --drop, after looking at the sheet: brings a dropped picture back from dropped/ into logos/ and
    the index (with every preferred share that reuses it, from review.csv), loudly. All or nothing (commit_switch).
    Refuses a code not in dropped/; a code given twice counts once."""
    folder = pathlib.Path(folder)
    logos, dropped = folder / "logos", folder / "dropped"
    index, bad = LI.validate_dir(logos)
    if bad:
        raise SystemExit("!! logos/ is not a valid logo folder: " + "; ".join(bad[:5]))
    dindex = read_dropped(dropped)
    want = _dedupe(codes)
    unknown = [c for c in want if c not in dindex["logos"]]
    if unknown or not want:
        raise SystemExit(f"!! not in dropped/ (nothing to restore): {unknown or want}; nothing was changed")
    used = {e["file"] for e in index["logos"].values()}
    for c in want:
        e = dindex["logos"][c]
        if e["file"] in used or c in index["logos"]:
            raise SystemExit(f"!! {c}: logos/ already has {e['file']} or an entry for {c}; nothing was changed")
    rows = _review_rows(folder)
    ni, nd = _copy(index), _copy(dindex)
    moves, new = [], []
    for c in want:
        e = nd["logos"].pop(c)
        ni["logos"][c] = dict(e, flags=[x for x in e.get("flags", []) if x != "switched-after-review"] + ["kept-after-review"])
        moves.append((e["file"], "to_logos"))
        new.append({"code": c, "name": e["name"], "reason": reason})
        for r in rows:
            if r.get("via") == c and r.get("code") and r["code"] not in ni["logos"]:
                ni["logos"][r["code"]] = dict(ni["logos"][c], name=r["name"], via=c)
                new.append({"code": r["code"], "name": r["name"], "reason": reason + " (preferred share of an issuer above)"})
    _record_info(folder, "keeps", new)                   # the record can be written: checked before any change
    commit_switch(logos, dropped, ni, nd, moves)
    _record(folder, "keeps", new)
    print(f"!! restored from dropped/ after review: {len(new)} ({', '.join(x['code'] for x in new)}) · "
          f"logos now {len(ni['logos']):,}")
    return 0


def drop(folder, codes, reason):
    """After the sheet review: the listed companies (and every preferred share reusing them) get the letter mark; their
    pictures move to dropped/ (--keep brings them back). All or nothing (commit_switch). A preferred share is refused:
    it goes with its common share. A code given twice counts once."""
    folder = pathlib.Path(folder)
    logos, dropped = folder / "logos", folder / "dropped"
    index, bad = LI.validate_dir(logos)
    if bad:
        raise SystemExit("!! logos/ is not a valid logo folder: " + "; ".join(bad[:5]))
    dindex = read_dropped(dropped)
    want = _dedupe(codes)
    unknown = [c for c in want if c not in index["logos"]]
    if unknown or not want:
        raise SystemExit(f"!! not in index.json (no logo to switch off): {unknown or want}; nothing was changed")
    for c in want:
        via = index["logos"][c].get("via")
        if via:
            raise SystemExit(f"!! {c} is a preferred share: 우선주는 보통주({via})를 빼면 같이 빠져요. Give --drop {via} "
                             "instead; nothing was changed")
    names = {r["code"]: r["name"] for r in _review_rows(folder)}
    gone = set(want) | {c for c, e in index["logos"].items() if e.get("via") in want}
    ni, nd = _copy(index), _copy(dindex)
    moves = []
    for c in sorted(gone):
        e = ni["logos"].pop(c)
        if c in want:                                    # the picture goes to dropped/, so --keep can bring it back
            nd["logos"][c] = dict(e, flags=list(e.get("flags", [])) + ["switched-after-review"])
            moves.append((e["file"], "to_dropped"))
    new = [{"code": c, "name": names.get(c, c), "reason": reason + ("" if c in want else " (preferred share of an issuer above)")}
           for c in sorted(gone)]
    _record_info(folder, "drops", new)                   # the record can be written: checked before any change
    commit_switch(logos, dropped, ni, nd, moves)
    _record(folder, "drops", new)
    print(f"!! switched to the letter mark: {len(gone)} ({', '.join(sorted(gone))}) · logos left {len(ni['logos']):,}")
    return 0


def add_from(folder, src, reason, codes=None):
    """After looking at a --only run's result (src): adds its logos to an earlier, reviewed run's folder (the checked
    folder kept on the logos-run branch), with every preferred share that reuses them (from the folder's review.csv),
    loudly. Refuses a company that already has a logo in the folder (--drop it first) and a file name already used; an
    old dropped picture of the same company leaves dropped/ (its record stays in drops.csv). All or nothing: the result
    is checked in memory first, then written; on any error every file and both indexes are put back.
    A --letters-from retry (run.json letters_from) is added only company by company: `codes` (--codes) names the ones
    approved on its sheet, any number; nothing else from that run is added."""
    folder, src = pathlib.Path(folder), pathlib.Path(src)
    logos, dropped = folder / "logos", folder / "dropped"
    index, bad = LI.validate_dir(logos)
    if bad:
        raise SystemExit("!! logos/ is not a valid logo folder: " + "; ".join(bad[:5]))
    sidx, sbad = LI.validate_dir(src / "logos")
    if sbad:
        raise SystemExit("!! the --only run's logos/ is not a valid logo folder: " + "; ".join(sbad[:5]))
    why = LI.not_publishable(sidx)
    if why:
        raise SystemExit(f"!! the --only run's logos/ cannot be added: {why}; nothing was changed")
    try:
        sinfo = json.loads((src / "run.json").read_text(encoding="utf-8"))
        json.loads((folder / "run.json").read_text(encoding="utf-8"))   # the folder's record is updated afterwards
    except (OSError, ValueError) as e:
        raise SystemExit(f"!! run.json missing or unreadable ({type(e).__name__}): only a finished --only run can be "
                         "added to a reviewed folder; nothing was changed")
    letters = bool(sinfo.get("letters_from"))
    if sinfo.get("ok") is not True or not (sinfo.get("only") or letters):
        raise SystemExit("!! the source is not a finished --only run, nor a finished --letters-from run (run.json: ok "
                         f"{sinfo.get('ok')!r}, only {sinfo.get('only')!r}, letters_from "
                         f"{sinfo.get('letters_from')!r}); nothing was changed")
    if letters and not codes:
        raise SystemExit("!! a --letters-from run is added company by company: name the approved ones with --codes; "
                         "nothing was changed")
    if codes and not letters:
        raise SystemExit("!! --codes is for a --letters-from run (a --only run is added whole); nothing was changed")
    if sidx.get("format") != index.get("format"):
        raise SystemExit(f"!! the --only run's pictures are {sidx.get('format')}, the folder's are {index.get('format')}; "
                         "nothing was changed")
    dindex = read_dropped(dropped)
    if letters:
        want = _dedupe(codes)
        missing = [c for c in want if c not in sidx["logos"] or sidx["logos"][c].get("via")]
        if missing or not want:
            raise SystemExit(f"!! not a logo of that run: {missing or want}; nothing was changed")
        codes = want
    else:
        codes = [c for c, e in sorted(sidx["logos"].items()) if not e.get("via")]
        if not codes or len(codes) > ONLY_MAX:
            raise SystemExit(f"!! the --only run has {len(codes)} logos to add (1 to {ONLY_MAX}); nothing was changed")
    clash = [c for c in codes if c in index["logos"]]
    if clash:
        raise SystemExit(f"!! already in logos/: {clash} (--drop them first if the new picture should replace them); "
                         "nothing was changed")
    lfiles, dfiles = _files(logos), _files(dropped)
    rows = _review_rows(folder)
    ni, nd = _copy(index), _copy(dindex)
    adds, gone, new = {}, [], []
    for c in codes:
        e = sidx["logos"][c]
        name = e["file"]
        if name in lfiles or name in adds:
            raise SystemExit(f"!! logos/ already has a file named {name}; nothing was changed")
        adds[name] = (src / "logos" / name).read_bytes()
        ni["logos"][c] = dict(e, flags=list(e.get("flags", [])) + ["added-after-review"])
        new.append({"code": c, "name": e["name"], "reason": reason})
        old = nd["logos"].pop(c, None)
        if old and old["file"] not in gone:
            gone.append(old["file"])
        for r in rows:
            if r.get("via") == c and r.get("code") and r["code"] not in ni["logos"]:
                ni["logos"][r["code"]] = dict(ni["logos"][c], name=r["name"], via=c)
                new.append({"code": r["code"], "name": r["name"], "reason": reason + " (preferred share of an issuer above)"})
    lf = dict(lfiles, **adds)
    df = {k: v for k, v in dfiles.items() if k not in gone}
    # the same picture as another company's logo in the reviewed set (the run's own shared check never saw them)
    from PIL import Image
    fps = []
    for code, e in ni["logos"].items():
        if not e.get("via"):
            fps.append((code, fingerprint(Image.open(io.BytesIO(lf[e["file"]])))))
    added = set(codes)
    clash = [g for g in shared_groups(fps) if added & set(g)]
    if clash:
        raise SystemExit(f"!! the same picture as another company's logo: {clash} (a group logo or a wrong match: look "
                         "again); nothing was changed")
    for idx in (ni, nd):
        idx["count"] = len(idx["logos"])
        idx["logos"] = dict(sorted(idx["logos"].items()))
    bad = [f"logos/: {b}" for b in LI.check_index(ni, lf)] + [f"dropped/: {b}" for b in LI.check_index(nd, df)]
    if bad:
        raise SystemExit("!! adding would leave a folder that is not valid (" + "; ".join(bad[:5]) + "); nothing was "
                         "changed")
    _record_info(folder, "adds", new)                    # the record can be written: checked before any change
    old_idx = {f: ((f / LI.INDEX).read_bytes() if (f / LI.INDEX).exists() else None) for f in (logos, dropped)}
    written, removed = [], []
    try:
        for name, data in adds.items():
            written.append(logos / name)                 # first, so a half-written file is removed too
            (logos / name).write_bytes(data)
        for name in gone:
            removed.append((dropped / name, dfiles[name]))
            (dropped / name).unlink()
        write_index(logos, ni)
        if dropped.exists():
            write_index(dropped, nd)
        for f, what in ((logos, "logos/"), (dropped, "dropped/")):
            if f.exists():
                _, bad = LI.validate_dir(f)
                if bad:
                    raise SystemExit(f"!! {what} is not valid after adding: " + "; ".join(bad[:5]))
    except BaseException:
        for p in written:
            p.unlink(missing_ok=True)
        for p, data in removed:
            p.write_bytes(data)
        for f, raw in old_idx.items():
            if raw is None:
                (f / LI.INDEX).unlink(missing_ok=True)
            elif f.exists():
                (f / LI.INDEX).write_bytes(raw)
        raise
    _record(folder, "adds", new)
    print(f"!! added after review from {src}: {len(new)} ({', '.join(x['code'] for x in new)}) · "
          f"logos now {len(ni['logos']):,}")
    return 0


class Deps:
    """What the tests replace: the network, the clocks, the environment, the sheet renderer."""

    def __init__(self, send=None, clock=time.monotonic, sleep=time.sleep, wall=now_kst, environ=None, jitter=None,
                 min_counts=None, render=render_pages, webp=None):
        self.send = send or transport
        self.clock, self.sleep, self.wall, self.jitter = clock, sleep, wall, jitter
        self.environ = os.environ if environ is None else environ
        self.min_counts, self.render = min_counts, render
        self.webp = can_webp() if webp is None else webp


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=None, help="new or empty output folder")
    ap.add_argument("--max-credits", type=int, default=DEFAULT_MAX_CREDITS, help="never send a lookup that could pass this")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="lookups open at once (Pro allows 15)")
    ap.add_argument("--per-minute", type=int, default=DEFAULT_PER_MINUTE, help="lookups a minute (Pro allows 500)")
    ap.add_argument("--limit", type=int, default=0, help="only the N largest companies (a small trial run); 0 = all")
    ap.add_argument("--sheet-top", type=int, default=SHEET_TOP, help="companies per market on the contact sheet")
    ap.add_argument("--data", default=lsrc.DATA_URL, help="data.json URL or path (default: the live site)")
    ap.add_argument("--listing", default="auto", help="KRX listing CSV path, or auto (the file for data.json pxDate)")
    ap.add_argument("--homepages", default=str(lsrc.HOMEPAGES))
    ap.add_argument("--time-limit-min", type=float, default=TIME_LIMIT_MIN)
    ap.add_argument("--no-png", action="store_true", help="sheet.html only (no browser)")
    ap.add_argument("--plan-only", action="store_true", help="print the companies, lookups and credit ceiling; no call")
    ap.add_argument("--defer-failure", action="store_true", help="exit 0 once everything is saved (the workflow)")
    ap.add_argument("--verdict", metavar="RUN_JSON", help="only read run.json and exit 1 unless the run was ok")
    ap.add_argument("--drop", metavar="CODES", help="comma-separated codes to switch to the letter mark (with --dir)")
    ap.add_argument("--keep", metavar="CODES", help="comma-separated codes to restore from dropped/ (with --dir)")
    ap.add_argument("--dir", help="the output folder of an earlier run (with --drop, --keep or --add-from)")
    ap.add_argument("--reason", default="decided on the review sheet", help="why (with --drop, --keep or --add-from)")
    ap.add_argument("--only", metavar="CODES", default="",
                    help=f"only these companies (comma-separated codes, at most {ONLY_MAX}): a fix-up after a reviewed run")
    ap.add_argument("--route", choices=("auto", "ticker"), default="auto",
                    help="with --only: ticker = look up by ticker only (no DART homepage lookup)")
    ap.add_argument("--add-from", metavar="RUN_DIR",
                    help="add the logos of a reviewed --only run (RUN_DIR) to an earlier run's folder (with --dir)")
    ap.add_argument("--letters-from", metavar="DIR", default="",
                    help="only the Korean companies without a logo in this reviewed folder (its logos/index.json), "
                         "largest first; --limit keeps the N largest of them")
    ap.add_argument("--extra-routes", action="store_true",
                    help="Korean companies: after the ticker and the DART homepage find no usable logo, look up the ISIN "
                         "(2 credits), then the brandmark by ticker (3 credits)")
    ap.add_argument("--codes", default="", help="with --add-from from a --letters-from run: the approved codes")
    ap.add_argument("--over-20-ok", action="store_true",
                    help="a --letters-from run may plan more than $20 (only after Jack's yes)")
    ap.add_argument("--full-run-date", default="", help="today's KST date (YYYY-MM-DD); needed for a run without --limit "
                                                       f"or with --limit above {FULL_RUN_FREE_LIMIT}")
    a = ap.parse_args(argv)
    if not CREDITS <= a.max_credits <= MAX_CREDITS or not 1 <= a.workers <= 10 or not 1 <= a.per_minute <= 450 \
            or a.limit < 0 or a.sheet_top < 1 or a.time_limit_min <= 0:
        ap.error(f"--max-credits 2 to {MAX_CREDITS:,} (never more: Jack's $140 stop), --workers 1 to 10, --per-minute 1 "
                 "to 450 (Pro allows 500), --limit 0 or more, --sheet-top at least 1, --time-limit-min above 0")
    switches = [x for x in (a.drop, a.keep, a.add_from) if x]
    if bool(switches) != bool(a.dir) or len(switches) > 1:
        ap.error("--drop, --keep or --add-from (one of them) goes with --dir")
    if a.route == "ticker" and not a.only:
        ap.error("--route ticker goes with --only (a fix-up for named companies)")
    if a.only and a.limit:
        ap.error("--only and --limit don't go together")
    return a


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
        print("!! the run stopped on an error in this tool (above)", file=sys.stderr, flush=True)
        return 1


def _main(argv, deps, state):
    argv = list(sys.argv[1:] if argv is None else argv)
    chk.refuse_key_in_args(argv)
    a = parse_args(argv)
    if a.verdict:
        return verdict(a.verdict)
    if a.drop:
        return drop(a.dir, a.drop.split(","), a.reason)
    if a.keep:
        return keep(a.dir, a.keep.split(","), a.reason)
    if a.add_from:
        return add_from(a.dir, a.add_from, a.reason, a.codes.split(",") if a.codes else None)
    d = deps or Deps()
    if not a.plan_only and not a.only and (a.limit == 0 or a.limit > FULL_RUN_FREE_LIMIT):
        today = f"{d.wall().astimezone(KST):%Y-%m-%d}"     # KST, even when the clock gives UTC
        if a.full_run_date.strip() != today:
            raise SystemExit(f"!! A run of more than {FULL_RUN_FREE_LIMIT} companies needs --full-run-date (the workflow "
                             f"input full_run_date) set to today's KST date, {today}; it is {a.full_run_date!r}. This "
                             "keeps a re-run on another day from spending again. Nothing was looked up.")
    t0 = d.clock()
    key = None
    if not a.plan_only:
        key = chk.read_secret_key(d.environ)
        d.environ.pop(KEY_ENV, None)                     # children (the browser for the sheet) never inherit it
    keymask = Masker(key) if key else str

    def mask(text):                                      # the key, and any signed image address, never shown
        return URL_RE.sub("[signed image address removed]", keymask(text))
    state["mask"] = mask
    log = chk.Log(mask)
    started = d.wall().astimezone(KST)
    stamp = f"{started:%Y-%m-%d %H:%M}"
    log(f"logo.dev logos · {stamp} KST · max credits {a.max_credits:,} · {a.workers} at once · {a.per_minute} a minute")

    sources = []
    data = json.loads(chk.logged(log, sources, lsrc.load_text, a.data, "data.json"))
    listing = chk.logged(log, sources, lsrc.load_listing, a.listing, data.get("pxDate"))
    homepages = lsrc.load_homepages(a.homepages)
    sources.append(f"DART homepages: {a.homepages} ({len(homepages):,} companies)")
    order, preferred, clog = load_all(data, listing, homepages, d.min_counts, a.sheet_top)
    for line in clog:
        log(line)
    if a.letters_from:
        order, more = letters_from(order, a.letters_from)
        for line in more:
            log(line)
        if not a.extra_routes:                           # nothing new to ask them: never bill the same picture again
            order = [c for c in order if not c.get("skip_known")]
        in_run = {c["code"] for c in order}
        preferred = [p for p in preferred if p["issuer"] in in_run]
    if a.extra_routes:                                   # ISIN: the company's own (logo_sources: KRX ISU_CD, else rule)
        log(f"!! --extra-routes: Korean companies without a usable ticker or homepage logo also get an ISIN lookup "
            f"({ROUTE_COST['isin']} credits) and a brandmark lookup by ticker ({ROUTE_COST['brandmark']} credits, kept only "
            f"when no wider than {BRANDMARK_MAX_ASPECT:g}:1)")
    if a.limit:
        order = order[:a.limit]
        in_run = {c["code"] for c in order}
        preferred = [p for p in preferred if p["issuer"] in in_run]
        log(f"!! --limit {a.limit}: only the {len(order):,} largest companies (a trial run)")
    if a.only:
        want = _dedupe(a.only.split(","))
        known = {c["code"]: c for c in order}
        unknown = [c for c in want if c not in known]
        if not want or len(want) > ONLY_MAX or unknown:
            raise SystemExit(f"!! --only takes 1 to {ONLY_MAX} codes of Korean common shares or US stocks in today's data "
                             f"(a preferred share goes with its issuer); not usable: {unknown or want}. Nothing was looked up.")
        order = [known[c] for c in want]
        preferred = [p for p in preferred if p["issuer"] in set(want)]
        log(f"!! --only {','.join(want)} · route {a.route}: a fix-up for named companies (add it to the reviewed folder "
            "with --add-from after looking at it)")
    ticker_only = a.route == "ticker"
    pl = plan(order, ticker_only, a.extra_routes)
    cap = (min(a.max_credits, pl["ceiling"]) if (a.limit or a.only or a.letters_from)
           else a.max_credits)                           # a trial or a retry never spends past its plan
    if a.letters_from and cap > RETRY_SPEND_ASK and not a.over_20_ok and not a.plan_only:
        raise SystemExit(f"!! this retry could spend {cap:,} credits (${cap / 100:,.2f}), above ${RETRY_SPEND_ASK / 100:,.0f}: "
                         "Jack asked to be told first (2026-11-07). Run with a smaller --limit or --max-credits, or with "
                         "--over-20-ok (workflow input over_20_dollars_ok) once he has said yes. Nothing was looked up.")
    log(f"· data.json asOf {data.get('asOf')} · prices {data.get('pxDate')} (US {data.get('usPxDate')}) · companies "
        f"{len(order):,} (Korea {sum(1 for c in order if c['side'] == 'kr'):,} · US "
        f"{sum(1 for c in order if c['side'] == 'us'):,}) · preferred shares {len(preferred):,}")
    log(f"· lookups: at most {pl['lookups']:,} ({pl['ticker']:,} by ticker + {pl['domain']:,} by DART homepage"
        + (f" + {pl['isin']:,} by ISIN + {pl['brandmark']:,} brandmarks" if a.extra_routes else "") + ") · "
        f"ceiling if every one were billed: {pl['ceiling']:,} credits (${pl['ceiling'] / 100:,.2f}) · the cap stops at "
        f"{cap:,}{' (a trial: its own ceiling)' if cap != a.max_credits else ''} · no ticker: "
        f"{sum(1 for c in order if not c.get('ticker'))}")
    if a.plan_only:
        log("· plan only: no logo.dev call was made")
        return 0

    out = chk.prepare_out(a.out or chk.CACHE_DIR / f"logo-dev-fetch-{started:%Y%m%d-%H%M%S}")
    out_logos = out / "logos"
    out_logos.mkdir()
    log(f"· output folder: {out} · logo files {'WebP' if d.webp else 'PNG (this Pillow has no WebP)'}")
    client = Client(key, d.send, SafePacer(d.clock, d.sleep, per_minute=a.per_minute, interval=60.0 / a.per_minute * 0.9),
                    SafePacer(d.clock, d.sleep, per_minute=DOWNLOADS_PER_MINUTE, interval=0.15))
    ledger = Ledger(cap)
    scope = {c["code"] for c in order if c["mrank"] <= a.sheet_top}
    f = Fetcher(client, ledger, log, out_logos, scope, d.clock, d.sleep, d.jitter,
                deadline=t0 + a.time_limit_min * 60, workers=a.workers, webp=d.webp, need=min(cap, pl["ceiling"]),
                ticker_only=ticker_only, extra=a.extra_routes)
    if a.only:
        f.only_codes = list(order)
    problems = []
    try:
        f.run(order)
    except Exception as e:                               # noqa: BLE001 — a bug: said, recorded, partial results saved
        f.stop = f.stop or chk.StopRun("crashed", f"{type(e).__name__}: {e}")
        for line in traceback.format_exc().splitlines():
            log("  " + line)
    ctx = {"out": out, "a": a, "d": d, "f": f, "ledger": ledger, "client": client, "preferred": preferred, "data": data,
           "pl": pl, "sources": sources, "stamp": stamp, "t0": t0, "problems": problems, "log": log, "mask": mask,
           "cap": cap}
    try:
        info = report(**ctx)
    except Exception as e:                               # noqa: BLE001 — never lose what was paid for: save what there is
        tb = [mask(x) for x in traceback.format_exc().splitlines()]
        for line in tb:
            log("  " + line)
        log(f"!! NOT OK: putting the results together failed ({type(e).__name__}); saving what there is")
        info = salvage(e, tb, **ctx)
    leaks = chk.find_key_in_files(out, key) + find_urls(out)
    if leaks:                                            # never expected: deleted, and the run is not ok
        for p in sorted(set(leaks)):
            p.unlink()
        info["ok"] = False
        info["problems"].append(f"the key or a signed image address was found in {sorted({p.name for p in leaks})}; "
                                "those files were deleted")
        log(f"!! NOT OK: {info['problems'][-1]}")
        write_reports(out, info, log, mask)
        for p in chk.find_key_in_files(out, key) + find_urls(out):
            p.unlink()
    if info["ok"] or a.defer_failure:
        return 0
    return 1


def salvage(err, tb, out, a, d, f, ledger, client, preferred, data, pl, sources, stamp, t0, problems, log, mask, cap):
    """After an error in putting the results together: index.json from the finished companies (pictures already in
    logos/), dropped/index.json, review.csv, run.json (ok false, outcome crashed, traceback masked), summary.md and
    run.log. Each one on its own, so one failure does not stop the others."""
    fmt = "webp" if d.webp else "png"
    out_logos = out / "logos"
    saved = []
    try:
        logos = {}
        for j in f.done:
            if j.final == "logo" and j.file and (out_logos / j.file).exists() and LI.CODE_RE.match(str(j.c["code"])):
                img = j.results[j.choice][1]["image"]
                logos[j.c["code"]] = {"file": j.file, "name": j.c["name"], "route": j.choice, "w": int(img["width"] or SIZE),
                                      "h": int(img["height"] or SIZE), "vector": bool(img.get("is_vector")),
                                      "flags": ([j.check] if j.check else []) + list(j.flags)}
        used = {e["file"] for e in logos.values()}
        for p in out_logos.iterdir():                    # a picture without an entry would make the folder invalid
            if p.name != LI.INDEX and p.name not in used:
                f.out_dropped.mkdir(exist_ok=True)
                p.replace(f.out_dropped / p.name)
        write_index(out_logos, {"version": LI.VERSION, "size": SIZE, "format": fmt, "source": "logo.dev",
                                "fetched_kst": stamp, "data_pxDate": data.get("pxDate"), "salvaged": True, "logos": logos})
        saved.append(f"logos/index.json ({len(logos):,} logos)")
    except Exception as e:                               # noqa: BLE001
        log(f"!! salvage: logos/index.json not written ({type(e).__name__})")
    try:
        dx = dropped_index(f, fmt, stamp)
        dx["logos"] = {c: e for c, e in dx["logos"].items() if (f.out_dropped / e["file"]).exists()}
        write_index(f.out_dropped, dx)
        saved.append("dropped/index.json")
    except Exception as e:                               # noqa: BLE001
        log(f"!! salvage: dropped/index.json not written ({type(e).__name__})")
    try:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["code", "name", "result", "route", "check", "reason", "file", "credits",
                                            "requests"], lineterminator="\n")
        w.writeheader()
        for j in f.done + f.remaining:
            w.writerow({"code": j.c["code"], "name": j.c["name"], "result": j.final or "", "route": j.choice or "",
                        "check": j.check, "reason": j.reason, "file": j.file, "credits": j.credits,
                        "requests": j.requests})
        _put(out, "review.csv", buf.getvalue(), mask)
        saved.append("review.csv")
    except Exception as e:                               # noqa: BLE001
        log(f"!! salvage: review.csv not written ({type(e).__name__})")
    stop = f.stop
    info = {"tool": "tools/logos/logodev_fetch.py", "outcome": "crashed", "ok": False,
            "reason": f"putting the results together failed: {type(err).__name__}: {mask(str(err))[:300]}"
                      + (f" (the lookups had ended: {stop.outcome})" if stop else ""),
            "problems": list(problems) + ["results put together by the salvage path; see traceback"],
            "traceback": tb[-40:], "companies": len(f.done) + len(f.remaining), "finished": len(f.done),
            "max_credits": cap, "saved": saved,
            "credits": {"counted": ledger.counted, "charged": ledger.charged, "free": ledger.free,
                        "no_header": ledger.no_header, "unknown": ledger.unknown, "unanswered": ledger.unanswered_n,
                        "billed_at": {str(k): v for k, v in sorted(ledger.billed_at.items())},
                        "balance_first": ledger.balance_first, "balance_last": ledger.balance_last},
            "requests": {"api": client.api_requests, "downloads": client.downloads,
                         "counts": dict(sorted(f.counts.items()))}}
    info["summary_text"] = "\n".join([
        "# logo.dev logos (v19.3a)", "",
        "**Stopped on an error in this tool after the lookups. What was found is saved; the run is NOT OK.**", "",
        f"- {info['reason']}",
        f"- Companies looked up: {info['finished']:,} of {info['companies']:,} · credits counted {ledger.counted:,} of "
        f"{cap:,} · balance logo.dev reported: {ledger.balance_first or 'not reported'} → "
        f"{ledger.balance_last or 'not reported'}",
        f"- Saved: {', '.join(saved) or 'nothing'} (pictures stay in logos/ and dropped/)", "",
        "The traceback is in run.json and run.log. This logos/ folder is valid but was put together by the salvage path: "
        "no shared-picture check and no preferred shares. Fix the tool and run again within 24 hours (a repeat lookup of "
        "a brand already billed is free), or review every logo before pushing this folder.", ""])
    try:
        write_reports(out, info, log, mask)
    except Exception as e:                               # noqa: BLE001
        log(f"!! salvage: reports not written ({type(e).__name__})")
    return info


def report(out, a, d, f, ledger, client, preferred, data, pl, sources, stamp, t0, problems, log, mask, cap):
    """Everything after the lookups: shared pictures, the index, the review sheet, the reports. Returns run.json's info."""
    out_logos = out / "logos"
    groups = shared_groups([(j.c["code"], j.hash) for j in f.done if j.final == "logo" and j.hash is not None])
    shared_dropped = drop_shared(f, groups, log)
    rows = rows_of(f, preferred, groups)
    fmt = "webp" if d.webp else "png"
    index = make_index(rows, stamp, data, fmt)
    (out_logos / LI.INDEX).write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                      encoding="utf-8")
    write_index(f.out_dropped, dropped_index(f, fmt, stamp))
    _, bad = LI.validate_dir(out_logos)
    if bad:
        problems.append("logos/ is not a valid logo folder: " + "; ".join(bad[:5]))
        log(f"!! {problems[-1]}")
    chosen = [j for j in f.done if j.choice]
    failed = sum(1 for j in chosen if j.reason == "download_failed")
    if chosen and failed * 2 > len(chosen):
        problems.append(f"{failed} of {len(chosen)} chosen logos could not be downloaded")
        log(f"!! {problems[-1]}")
    cands = {j.c["code"]: j.cands for j in f.done}
    cols = mark_colors()
    secs = sheet_sections(rows, f.done, groups, a.sheet_top)
    sheet_counts = [(title, len(rs)) for title, rs in secs]
    for title, n in sheet_counts:
        log(f"· review sheet · {title}: {n:,}")
    finished = f"{d.wall().astimezone(KST):%Y-%m-%d %H:%M}"
    meta = f"{stamp} KST · data.json prices {data.get('pxDate')} · {index['count']:,} logos"
    _put(out, "sheet.html", sheet_page(meta, secs, cands, cols), mask)
    pages = []
    if a.no_png:
        log("· sheet PNG pages: not drawn (--no-png)")
    else:
        try:
            pages, p = d.render(paginate(secs), meta, cands, cols, out, log)
        except Exception as e:                           # noqa: BLE001 — said loudly and makes the run not ok
            p = f"sheet PNG pages not drawn: {type(e).__name__}: {e}"
        if p:
            problems.append(p)
            log(f"!! {p}")
    stop = f.stop
    outcome = stop.outcome if stop else "complete"
    fin = sum(1 for r in rows if r["result"] and not r["via"])
    comp = sum(1 for r in rows if not r["via"])
    info = {
        "tool": "tools/logos/logodev_fetch.py", "outcome": outcome, "ok": outcome in OK_OUTCOMES and not problems,
        "reason": stop.reason if stop else "", "problems": problems, "started_kst": stamp, "finished_kst": finished,
        "minutes": round((d.clock() - t0) / 60, 1), "companies": comp, "finished": fin, "unfinished": comp - fin,
        "max_credits": cap, "format": fmt, "sheet_top": a.sheet_top, "sheet_pages": pages,
        "data": {"pxDate": data.get("pxDate"), "usPxDate": data.get("usPxDate"), "asOf": data.get("asOf")},
        "sources": sources, "plan": pl, "pace": {"per_minute": a.per_minute, "workers": a.workers},
        "tally": tally(rows), "shared": groups, "shared_dropped": shared_dropped, "sheet_counts": sheet_counts,
        "odd": f.odd, "only": [c["code"] for c in getattr(f, "only_codes", [])], "route": f.route,
        "letters_from": str(a.letters_from or ""), "extra_routes": bool(a.extra_routes),
        "index_count": index["count"],
        "credits": {"counted": ledger.counted, "charged": ledger.charged, "free": ledger.free,
                    "no_header": ledger.no_header, "unknown": ledger.unknown, "unanswered": ledger.unanswered_n,
                    "billed_at": {str(k): v for k, v in sorted(ledger.billed_at.items())}, "balance_first": ledger.balance_first,
                    "balance_last": ledger.balance_last},
        "requests": {"api": client.api_requests, "downloads": client.downloads, "counts": dict(sorted(f.counts.items()))},
    }
    t = info["tally"]
    log(f"· finished {fin:,} of {comp:,} · Korea: ticker {t['kr']['by_ticker']:,} · homepage {t['kr']['by_domain']:,} · "
        f"letter {t['kr']['letter']:,} · US: ticker {t['us']['by_ticker']:,} · letter {t['us']['letter']:,} · "
        f"preferred reusing a logo {t['preferred']['logo']:,} · credits {ledger.counted:,}/{cap:,} · "
        f"lookups {client.api_requests:,} · downloads {client.downloads:,}")
    log(f"{'OK' if info['ok'] else '!! NOT OK'}: {OUTCOME_TEXT.get(outcome, outcome)} {info['reason']}".rstrip()
        + f" · results in {out}")
    write_csv(out, rows, mask)
    write_reports(out, info, log, mask)
    return info


if __name__ == "__main__":
    sys.exit(main())
