#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Company logos from logo.dev Pro, fetched once and hosted by us (v19.3a, docs/tasks/v19.3-portfolio-pictures-accounts.md
Part J). Run by hand only: from the workflow "logo.dev 로고 받기" (.github/workflows/logo-dev-fetch.yml), or from a terminal:

  LOGO_DEV_SECRET_KEY=sk_... python3 tools/logos/logodev_fetch.py --out DIR [--max-credits 14000] [--workers 4]
  python3 tools/logos/logodev_fetch.py --plan-only           # the companies, the requests and the credit ceiling; no call
  python3 tools/logos/logodev_fetch.py --verdict DIR/run.json # exit 1 unless that run finished or stopped cleanly
  python3 tools/logos/logodev_fetch.py --drop 005930,AAPL --dir DIR --reason "wrong company (sheet review)"
                                                             # after looking at the sheet: those companies get the letter mark

What it does
  1. Companies: every Korean company and every US company in the live data.json (or --data), ETFs and funds left out,
     in market-cap order (조원 for both markets, data.json's own unit). A Korean preferred share reuses its issuer's logo
     (kr_homepages.csv `via`, else the common-share code) with no lookup of its own. Refuses data that is plainly
     incomplete (too few companies, a must-have company missing, many market caps blank).
  2. Lookups, exact identifiers only (never a name), GET /v2/brands/logo (2 credits when billed):
       ticker  KOSPI and KONEX 005930.KS · KOSDAQ 247540.KQ · US bare (AAPL, BRK-B);
       domain  Korea only: the DART homepage domain (kr_homepages.csv, domain_ok = 1), after the ticker, whatever the
               ticker found. The logo lookup does not return a brand domain, so the cross-check compares brand_id:
                 ticker logo + homepage logo of the same brand (same brand_id or same etag) -> the ticker logo, "same-brand";
                 ticker logo + homepage logo of another brand -> the homepage logo ("homepage-over-ticker");
                 ticker logo, the homepage found no logo (or no usable domain) -> the ticker logo, flagged "unverified";
                 no ticker logo + homepage logo -> the homepage logo ("homepage"); neither -> the letter mark.
               A second lookup that reaches a brand already billed in the last 24 hours is free (Credits-Charged: 0).
  3. Each chosen logo is downloaded right after its lookups, from the signed address in the answer (it expires after
     about 24 hours and is never written anywhere; the etag is kept). Raster sources are downloaded as PNG at their own
     size up to 128 px, vector sources rasterised by logo.dev at 128 px. Normalised to a 128 x 128 WebP (PNG when this
     Pillow has no WebP), transparency kept, centred, never stretched or upscaled. SVG is never stored.
  4. Automatic quality checks; a failing logo gets the letter mark, never a doubtful logo (QUALITY_NOTE below).
  5. Writes to --out: logos/<code>.webp + logos/index.json (the folder tools/push_logos_branch.sh publishes),
     summary.md, review.csv (one row per company), sheet.html and sheet-01.png … (contact sheet: the --sheet-top largest
     companies of each market with their chosen logo or letter mark, then every Korean company whose homepage logo
     replaced the ticker's, then every picture shared by different companies), run.json and run.log.

Spend, pace and stops (logo.dev docs and pricing page, read 2026-11-06: Pro = 500 API requests a minute, 15 open at once,
$150 of API credit a month, 1 credit = 1¢, logo lookup 2 credits)
  - Credits are counted here, never trusted to logo.dev alone: 2 per answer marked Credits-Charged: 1 (2 also when a
    200 or 404 carries no such header, and 2 for a request that got no answer, in case it was billed). Before every
    request 2 credits are reserved; a request that could pass --max-credits (default 14,000 = $140) is never sent. The
    run also stops on 402 (no credit left). With auto-reload on the account a 402 may never come: the local cap is the
    real stop.
  - At most --per-minute (200) lookups a minute and --workers (4) open at once; downloads (not billed, not CDN
    requests) at most 300 a minute. 429: waits Retry-After or RateLimit-Reset, else backs off. 202 (indexing): the
    company waits Retry-After (30 s) while the others go on, at most RETRIES_202 times. 401/403, an answer the docs
    don't describe, or 5 companies in a row ending in an error stop the run; whatever was found is still saved.
  - No new lookup starts after --time-limit-min (110), inside the workflow's 150-minute limit.

The key
  Read only from LOGO_DEV_SECRET_KEY, then removed from this process's environment (the browser that draws the sheet
  never inherits it). It goes only into the Authorization header of api.logo.dev requests. Never printed, logged or
  written: every line passes a masker, and every output file is searched for it and for signed image addresses at the
  end (found -> deleted and the run is not OK). A value that looks like a secret key on the command line is refused.

Exit code: 0 when the run finished or stopped cleanly (credit cap, 402); 1 otherwise. With --defer-failure (the
workflow) it exits 0 once everything is saved, so the results are uploaded; the workflow's last step (--verdict) fails.
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
from logo_ids import Masker, common_code, is_common_share, is_krx_code, now_kst  # noqa: E402

KEY_ENV = chk.KEY_ENV
CREDITS = chk.CREDITS_PER_LOOKUP                 # 2 per billed logo lookup
DEFAULT_MAX_CREDITS = 14_000                     # $140 at 1 credit = 1 cent (Jack's stop, 2026-11-06)
DEFAULT_WORKERS = 4                              # open at once (Pro allows 15)
DEFAULT_PER_MINUTE = 200                         # lookups a minute (Pro allows 500)
DOWNLOADS_PER_MINUTE = 300
TIME_LIMIT_MIN = 110                             # the workflow's job limit is 150 minutes
SHEET_TOP = 300                                  # per market
RETRIES_202 = 6                                  # logo.dev: usually ready within a minute; stop polling after 300 s
MAX_WAIT_202_S = 60
SIZE = LI.SIZE
SMALL_PX = 64
TILES_PER_PAGE = 48
SHEET_EXTRA_MAX = 300                            # the sheet's "homepage over ticker" section outside the top: at most
SHARED_PER_GROUP, SHARED_TILES_MAX = 24, 480     # shared pictures: tiles per group and in all (review.csv has every one)
MAX_KR_NOCAP = MAX_US_NOCAP = 25
MUST = chk.MUST
MUST_TOP = 300                                   # each must-have company sits in its market's top 300 by market cap
MIN_COMPANIES = chk.MIN_COMPANIES
URL_NEEDLE = b"img.logo.dev/"                    # a signed image address must never be written
URL_RE = re.compile(r"https?://img\.logo\.dev/\S*")
DROP_REASONS = ("small", "blank", "one_colour", "monogram")
OK_OUTCOMES = ("complete", "max_credits", "out_of_credits")
OUTCOME_TEXT = dict(chk.OUTCOME_TEXT, complete="Finished: every company was looked up.")

QUALITY_NOTE = (
    "Quality checks (a failing logo gets the letter mark): "
    "**small** — a raster source whose shorter side is under 64 px (logo.dev's width and height); "
    "**blank** — under 1% of the 128 px picture is visible (alpha 32 or more); "
    "**one_colour** — the picture laid on white and laid on black is, both times, at least 98.5% one colour "
    "(colours rounded to 32 levels a channel), so a white logo on transparency or a black one passes; "
    "**monogram** — logo.dev's generic letter tile, recognised by its shape: an opaque square (75% or more of the "
    "picture fully opaque) of two flat colours (background 55% or more, a far colour 4–40%, at most 6% of other "
    "colours besides the blend between them) whose far colour forms one or two blobs centred within 12% of the middle, "
    "25–75% of the height and 10–75% of the width. Real letter-on-colour logos fail it too; they then show our own "
    "letter mark, which looks alike. Not dropped but listed: **shared** — the same picture for different companies "
    "(a group logo, or a generic picture): the same 64-bit difference hash and 16 x 16 colour thumbnails at most 6 "
    "levels apart on average; only checked pairs form a group. Shared groups are on the contact sheet."
)


# ── companies ───────────────────────────────────────────────────────────────────────────────────────────────────────

cap_of = chk.cap_of


def safe_file(code):
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", str(code))[:24] or "_"
    if not stem[0].isalnum():
        stem = "x" + stem[:23]
    return stem


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


def plan(order):
    """Lookups and the credit ceiling: one ticker lookup per company with a ticker, plus one homepage lookup per Korean
    company with a usable DART domain; every one could be billed (2 credits)."""
    t = sum(1 for c in order if c.get("ticker"))
    d = sum(1 for c in order if c["side"] == "kr" and c.get("domain"))
    return {"ticker": t, "domain": d, "lookups": t + d, "ceiling": CREDITS * (t + d)}


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
        if route not in chk.ROUTES:
            raise ValueError(f"route {route!r} is not an exact identifier ({', '.join(chk.ROUTES)})")
        self.api_pacer.wait()
        with self._lock:
            self.api_requests += 1
        return self.send(chk.API_BASE + chk.LOGO_ROUTE, params={route: ident},
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
        self.balance_first = self.balance_last = None

    @property
    def counted(self):
        return self.billed + self.unknown

    def reserve(self):
        with self._lock:
            if self.billed + self.unknown + self.reserved + CREDITS > self.cap:
                return False
            self.reserved += CREDITS
            return True

    def release(self):
        with self._lock:
            self.reserved -= CREDITS

    def settle(self, resp):
        """Releases the reservation and counts the answer. Returns the credits it cost."""
        cc = resp.headers.get("credits-charged")
        cost = 0
        with self._lock:
            self.reserved -= CREDITS
            if cc == "1":
                self.charged += 1
                cost = CREDITS
            elif cc == "0":
                self.free += 1
            elif resp.status in (200, 404):
                self.no_header += 1
                cost = CREDITS
            self.billed += cost
            bal = resp.headers.get("credits-remaining")
            if bal:
                self.balance_last = bal
                self.balance_first = self.balance_first or bal
        return cost

    def unanswered(self):
        with self._lock:
            self.reserved -= CREDITS
            self.unknown += CREDITS
        return CREDITS


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
    """The drop reasons for one normalised picture (empty = keep). img: logo.dev's facts (width, height, is_vector)."""
    np = _np()
    out = []
    if not img.get("is_vector") and min(int(img["width"]), int(img["height"])) < SMALL_PX:
        out.append("small")
    arr = np.asarray(canvas.convert("RGBA"))
    if (arr[..., 3] >= 32).mean() < 0.01:
        return out + ["blank"]
    if top_share(_composite(arr, 255.0)) >= 0.985 and top_share(_composite(arr, 0.0)) >= 0.985:
        out.append("one_colour")
    elif is_monogram(arr):
        out.append("monogram")
    return out


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

class Job:
    """One company on its way through its lookups, download and checks."""

    def __init__(self, c):
        self.c = c
        if c.get("ticker"):
            self.stage = "ticker"
        elif c["side"] == "kr" and c.get("domain"):
            self.stage = "domain"
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
                 deadline=None, workers=DEFAULT_WORKERS, webp=True):
        self.client, self.ledger, self.log = client, ledger, log
        self.out_logos, self.scope, self.webp = out_logos, set(scope), webp
        self.clock, self._sleep, self.deadline, self.workers = clock, sleep, deadline, max(1, int(workers))
        self.jitter = jitter or random.SystemRandom().random
        self.lock = threading.Lock()
        self.counts = collections.Counter()
        self.done = []
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
        unanswered = False
        while True:
            if self.stop is not None:
                raise chk.StopRun("stopped", "another worker stopped the run")
            if self.deadline is not None and self.clock() >= self.deadline:
                raise chk.StopRun("time_limit", "reached the time limit (--time-limit-min): the results so far are "
                                                "saved and uploaded before the workflow's own limit")
            if not self.ledger.reserve():
                raise chk.StopRun("max_credits", f"reached --max-credits {self.ledger.cap:,}: {self.ledger.counted:,} "
                                                 f"credits counted, and the next lookup could cost {CREDITS} more")
            sent += 1
            try:
                resp = self.client.lookup(route, ident)
            except Exception as e:                       # noqa: BLE001 — no answer: counted, retried, kept
                self.count("no answer (network)")
                if not unanswered:
                    unanswered = True
                    spent += self.ledger.unanswered()
                else:
                    self.ledger.release()
                if tr < chk.RETRIES_TRANSIENT:
                    self.log(f"  !! {route} {ident}: no answer ({type(e).__name__}); trying again in {chk.BACKOFF_S[tr]} s")
                    self.sleep(chk.BACKOFF_S[tr])
                    tr += 1
                    self.count("retries after an error")
                    continue
                return "error", {"note": f"no answer after {tr + 1} tries ({type(e).__name__})"}, spent, sent
            spent += self.ledger.settle(resp)
            self.count(f"HTTP {resp.status}")
            if resp.status != 429:
                self._respect_window(resp.headers)
            kind, info = chk.classify(resp)
            info["http"] = resp.status
            if kind == "logo":
                j = resp.json() or {}
                data = j.get("data") if isinstance(j.get("data"), dict) else {}
                res = ((j.get("metadata") or {}).get("resolution") or {}) if isinstance(j.get("metadata"), dict) else {}
                info["brand_id"] = str(data.get("brand_id") or data.get("id") or "")
                info["method"] = str(res.get("method") or "") if isinstance(res, dict) else ""
                info["value"] = str(res.get("value") or "") if isinstance(res, dict) else ""
                info["image"]["has_transparency"] = bool(((data.get("source") or {}) if isinstance(data.get("source"), dict)
                                                          else {}).get("has_transparency"))
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

    def _respect_window(self, headers):
        rem, reset = chk._int(headers.get("ratelimit-remaining")), chk._int(headers.get("ratelimit-reset"))
        if rem == 0 and reset is not None and reset > 0:
            self.count("holds (RateLimit-Remaining 0)")
            self.client.api_pacer.hold(min(reset, chk.MAX_WAIT_429_S))

    # one lookup stage -> None (stage finished) or seconds to wait (202)
    def lookup(self, job):
        c, route = job.c, job.stage
        ident = c["ticker"] if route == "ticker" else c["domain"]
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
        job.results[route] = (kind, info)
        job.stage = "domain" if route == "ticker" and c["side"] == "kr" and c.get("domain") else "decide"
        return None

    def decide(self, job):
        r = job.results
        t_kind, t = r.get("ticker", ("", {}))
        d_kind, d = r.get("domain", ("", {}))
        if t_kind == "logo" and d_kind == "logo":
            same = (t.get("brand_id") and t.get("brand_id") == d.get("brand_id")) or \
                   (t["image"].get("etag") and t["image"].get("etag") == d["image"].get("etag"))
            if same:
                job.choice, job.check = "ticker", "same-brand"
            elif t.get("brand_id") and d.get("brand_id"):
                job.choice, job.check = "domain", "homepage-over-ticker"
            else:
                job.choice, job.check, job.why = "ticker", "unverified", "brand id missing from an answer"
        elif t_kind == "logo":
            if job.c["side"] == "us":
                job.choice, job.check = "ticker", "ticker"
            else:
                job.choice, job.check = "ticker", "unverified"
                job.why = (f"homepage {job.c['domain']}: {d_kind}" if d_kind
                           else "no usable DART homepage domain")
        elif d_kind == "logo":
            job.choice, job.check = "domain", "homepage"
        else:
            kinds = [k for k in (t_kind, d_kind) if k]
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
        if job.c["code"] in self.scope:                  # on the sheet: also the other route's picture, when different
            chosen_etag = job.results[job.choice][1]["image"].get("etag") if job.choice else None
            for rt in ("ticker", "domain"):
                k, info = job.results.get(rt, ("", {}))
                if k == "logo" and rt not in routes and (not chosen_etag or info["image"].get("etag") != chosen_etag):
                    routes.append(rt)
        for rt in routes:
            img = job.results[rt][1]["image"]
            facts_small = not img.get("is_vector") and min(img["width"], img["height"]) < SMALL_PX
            if rt == job.choice and facts_small and job.c["code"] not in self.scope:
                job.cands[rt] = {"png": None, "flags": ["small"], "error": ""}
                continue
            try:
                resp = self.client.download(img["url"], download_size(img))
            except Exception as e:                       # noqa: BLE001 — one picture: counted, said, the rest go on
                job.cands[rt] = {"png": None, "flags": [], "error": f"no answer ({type(e).__name__})"}
                continue
            if not chk.image_kind(resp):
                job.cands[rt] = {"png": None, "flags": [], "error": f"HTTP {resp.status} "
                                 f"{resp.headers.get('content-type', '')!r}, {len(resp.body):,} bytes"}
                continue
            try:
                canvas = normalise(resp.body)
            except Exception as e:                       # noqa: BLE001 — a picture that cannot be read
                job.cands[rt] = {"png": None, "flags": [], "error": f"unreadable picture ({type(e).__name__}: {e})"[:120]}
                continue
            flags = quality(canvas, img)
            buf = io.BytesIO()
            canvas.save(buf, "PNG")
            job.cands[rt] = {"png": buf.getvalue(), "flags": flags, "error": "", "canvas": canvas}
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
            return
        canvas = cand["canvas"]
        data, ext = encode(canvas, self.webp)
        name = f"{safe_file(job.c['code'])}.{ext}"
        (self.out_logos / name).write_bytes(data)
        job.final, job.file, job.bytes, job.hash = "logo", name, len(data), fingerprint(canvas)

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
        while job.stage in ("ticker", "domain"):
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
        sched = Scheduler([Job(c) for c in companies], self.clock, self.sleep)
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
               "domain": c.get("domain", ""), "result": job.final or "", "route": job.choice or "",
               "check": job.check if job.choice else "", "reason": job.reason if job.final == "letter" else "",
               "flags": " ".join(job.flags), "unverified_why": job.why, "ticker_status": t_kind,
               "ticker_brand": t.get("brand_id", ""), "domain_status": d_kind, "domain_brand": d.get("brand_id", ""),
               "brand_domain": brand_domain(job),
               "resolution": job.results[job.choice][1].get("method", "") if job.choice else "", "width": chosen.get("width", ""), "height": chosen.get("height", ""),
               "format": chosen.get("format", ""), "vector": chosen.get("is_vector", ""),
               "transparency": chosen.get("has_transparency", ""), "etag": chosen.get("etag", ""),
               "file": job.file, "bytes": job.bytes or "", "credits": job.credits, "requests": job.requests,
               "shared_group": shared.get(c["code"], ""), "via": "",
               "note": ("unfinished: " + "; ".join(f"{x['route']} {x['result']}" for x in job.lookups) if job.lookups
                        else "not looked up: the run stopped first") if unfinished else job.note}
        rows.append(row)
        by[c["code"]] = (job, row)
    for p in preferred:
        job, row = by.get(p["issuer"], (None, None))
        ok = job is not None and job.final == "logo"
        rows.append({"rank": "", "market_rank": "", "code": p["code"], "name": p["name"], "market": "", "cap": cap_of(p) or "",
                     "ticker": "", "domain": "", "result": "logo" if ok else ("letter" if job is None or job.final else ""),
                     "route": row["route"] if ok else "", "check": row["check"] if ok else "",
                     "reason": "" if ok else ("issuer not in data.json" if not p["issuer_listed"] else
                                              (f"issuer {p['issuer']}: {row['reason'] or 'unfinished'}" if row else "")),
                     "flags": "", "unverified_why": "", "ticker_status": "", "ticker_brand": "", "domain_status": "",
                     "domain_brand": "", "brand_domain": row["brand_domain"] if ok else "", "resolution": "",
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
        logos[r["code"]] = {"file": r["file"], "route": r["route"], "w": int(r["width"]), "h": int(r["height"]),
                            "vector": bool(r["vector"]), "flags": [r["check"]] if r["check"] else []}
    for r in rows:
        if r["result"] == "logo" and r["via"] and r["via"] in logos:
            e = logos[r["via"]]
            logos[r["code"]] = dict(e, via=r["via"])
    return {"version": LI.VERSION, "size": SIZE, "format": fmt, "source": "logo.dev", "fetched_kst": stamp,
            "data_pxDate": data.get("pxDate"), "count": len(logos), "logos": dict(sorted(logos.items()))}


CSV_COLS = ["rank", "market_rank", "code", "name", "market", "cap", "ticker", "domain", "result", "route", "check",
            "reason", "flags", "unverified_why", "ticker_status", "ticker_brand", "domain_status", "domain_brand",
            "brand_domain", "resolution", "width", "height", "format", "vector", "transparency", "etag", "file", "bytes", "credits",
            "requests", "shared_group", "via", "note"]


def tally(rows):
    """Counts for the summary."""
    out = {}
    for side, label in (("kr", "Korea (common shares)"), ("us", "US")):
        mine = [r for r in rows if not r["via"] and (r["market"] != "US") == (side == "kr")]
        fin = [r for r in mine if r["result"]]
        out[side] = {"label": label, "companies": len(mine), "finished": len(fin),
                     "by_ticker": sum(1 for r in fin if r["result"] == "logo" and r["route"] == "ticker"),
                     "by_domain": sum(1 for r in fin if r["result"] == "logo" and r["route"] == "domain"),
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


def summary_md(info):
    t, cr, rq = info["tally"], info["credits"], info["requests"]
    out = ["# logo.dev logos (v19.3a)", "",
           f"Run {info['started_kst']} – {info['finished_kst']} KST · data.json prices {info['data']['pxDate']} "
           f"(US {info['data']['usPxDate']}) · logo files: {info['format'].upper()} {SIZE} × {SIZE}", "",
           f"**{OUTCOME_TEXT.get(info['outcome'], info['outcome'])}** {info['reason'] or ''}".rstrip(), "",
           f"Companies finished: **{info['finished']:,} of {info['companies']:,}**"
           + (f" ({info['unfinished']:,} unfinished or not started: they show the letter mark)"
              if info["finished"] < info["companies"] else ""), ""]
    for p in info["problems"]:
        out.append(f"- !! {p}")
    if info["problems"]:
        out.append("")
    out += ["## Coverage", "", "Shares are of the companies finished in that market.", "",
            "| Market | Companies | Finished | Logo by ticker | Logo by DART homepage | Letter mark |",
            "|---|---:|---:|---:|---:|---:|"]
    for side in ("kr", "us"):
        m = t[side]
        out.append(f"| {m['label']} | {m['companies']:,} | {m['finished']:,} | {_pct(m['by_ticker'], m['finished'])} | "
                   f"{_pct(m['by_domain'], m['finished'])} | {_pct(m['letter'], m['finished'])} |")
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
    out += [f"- shared pictures: **{len(info['shared'])}** groups, {sum(len(g) for g in info['shared']):,} companies "
            "(kept; on the contact sheet)", "", QUALITY_NOTE, "",
            "## Credits and requests", "",
            f"- Credits counted: **{cr['counted']:,}** of the {info['max_credits']:,} cap (${cr['counted'] / 100:,.2f}) — "
            f"{CREDITS} for each of {cr['charged']:,} answers marked Credits-Charged: 1, {cr['no_header']:,} billable "
            f"answers without the header, and {cr['unknown'] // CREDITS:,} requests that got no answer. "
            f"{cr['free']:,} answers were free (Credits-Charged: 0).",
            f"- Balance logo.dev reported (Credits-Remaining), first → last answer: {cr['balance_first'] or 'not reported'}"
            f" → {cr['balance_last'] or 'not reported'}.",
            f"- Ceiling before the run (every lookup billed): {info['plan']['ceiling']:,} credits for "
            f"{info['plan']['lookups']:,} lookups ({info['plan']['ticker']:,} by ticker, {info['plan']['domain']:,} by "
            "DART homepage).",
            f"- API lookups sent: **{rq['api']:,}** (retries after 202: {rq['counts'].get('202 retries', 0):,} · after "
            f"429: {rq['counts'].get('retries after 429', 0):,} · after an error: "
            f"{rq['counts'].get('retries after an error', 0):,}) · downloads: {rq['downloads']:,} (not billed, not CDN "
            f"requests) · failed downloads of a chosen logo: {rq['counts'].get('downloads failed', 0):,}.",
            f"- Pace: at most {info['pace']['per_minute']} lookups a minute, {info['pace']['workers']} open at once, "
            f"downloads at most {DOWNLOADS_PER_MINUTE} a minute · run time {info['minutes']:.1f} min.", "",
            "## Contact sheet", "",
            f"sheet.html{' and ' + ', '.join(info['sheet_pages']) if info['sheet_pages'] else ' (no PNG pages)'}: the "
            f"{info['sheet_top']} largest companies of each market (chosen logo or letter mark, with any dropped picture "
            "beside it), every Korean company whose homepage logo replaced the ticker's, and every shared picture.", ""]
    if info.get("drops"):
        out += ["## Switched to the letter mark after review", ""]
        out += [f"- {d['code']} {d['name']} — {d['reason']}" for d in info["drops"]]
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
        why = " ".join(cd.get("flags") or []) or ("not chosen" if not cd.get("error") else "download failed")
        if cd.get("png"):
            extra.append(f'<div><img alt="" src="data:image/png;base64,{base64.b64encode(cd["png"]).decode()}">'
                         f'<div class="line bad">{e(rt)}: {e(why)}</div></div>')
        else:
            extra.append(f'<div class="line bad">{e(rt)}: {e(why)}</div>')
    what = (f"{e(r['route'])} · {e(r['check'])}" if r["result"] == "logo"
            else f'<span class="bad">letter mark · {e(r["reason"] or "unfinished")}</span>')
    src = (f"{r['width']}×{r['height']} {e(str(r['format']))}{' vector' if r['vector'] is True else ''}"
           if r["width"] != "" else "")
    return (f'<div class="card{" drop" if r["result"] != "logo" else ""}"><div class="row"><div class="box">{inner}</div>'
            f'<div class="small">{"".join(extra)}</div></div>'
            f'<div class="name">{e(r["name"])}</div>'
            f'<div class="line">{e(r["code"])} · #{e(str(r["market_rank"]))} {e(r["market"])}</div>'
            f'<div class="line">{what}</div><div class="line">{src}</div>'
            + (f'<div class="line">{e(r["unverified_why"])}</div>' if r["unverified_why"] else "")
            + (f'<div class="line">shared picture group {r["shared_group"]}</div>' if r["shared_group"] else "")
            + "</div>")


def sheet_sections(rows, jobs, groups, top):
    """[(title, [row, ...])] in the order the sheet shows them."""
    comp = [r for r in rows if not r["via"]]
    secs = []
    for side, label in (("kr", "Korea"), ("us", "US")):
        mine = sorted((r for r in comp if (r["market"] != "US") == (side == "kr") and r["market_rank"] != ""
                       and int(r["market_rank"]) <= top), key=lambda r: int(r["market_rank"]))
        secs.append((f"{label}: the {top} largest by market cap", mine))
    over = sorted((r for r in comp if r["check"] == "homepage-over-ticker" and r["result"] == "logo"
                   and r["market"] != "US" and (r["market_rank"] == "" or int(r["market_rank"]) > top)),
                  key=lambda r: int(r["market_rank"] or 10 ** 6))
    secs.append(("Korea outside the top: homepage logo used instead of a different ticker brand"
                 + (f" (the {SHEET_EXTRA_MAX} largest of {len(over):,}; every one is in review.csv)"
                    if len(over) > SHEET_EXTRA_MAX else ""), over[:SHEET_EXTRA_MAX]))
    by = {r["code"]: r for r in comp}
    left = SHARED_TILES_MAX
    for i, g in enumerate(groups, 1):
        if left <= 0:
            secs.append((f"Shared pictures: {len(groups) - i + 1} more groups not drawn (review.csv, shared_group)", []))
            break
        mine = [by[c] for c in g if c in by][:min(SHARED_PER_GROUP, left)]
        left -= len(mine)
        secs.append((f"Shared picture, group {i}: {len(g)} companies"
                     + (f" (first {len(mine)} drawn)" if len(mine) < len(g) else ""), mine))
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
    _put(folder, "summary.md", summary_md(info), mask)
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


def drop(folder, codes, reason):
    """After the sheet review: the listed companies (and every preferred share reusing them) get the letter mark.
    Rewrites logos/index.json, deletes pictures nothing uses any more, records the switch in drops.csv and run.json,
    and rewrites summary.md. Refuses a folder that is not valid before or after."""
    folder = pathlib.Path(folder)
    logos = folder / "logos"
    index, bad = LI.validate_dir(logos)
    if bad:
        raise SystemExit("!! logos/ is not a valid logo folder: " + "; ".join(bad[:5]))
    info = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    names = {}
    with open(folder / "review.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            names[r["code"]] = r["name"]
    want = [c.strip() for c in codes if c.strip()]
    unknown = [c for c in want if c not in index["logos"]]
    if unknown:
        raise SystemExit(f"!! not in index.json (no logo to switch off): {unknown}")
    gone = set(want) | {c for c, e in index["logos"].items() if e.get("via") in want}
    for c in sorted(gone):
        index["logos"].pop(c)
    used = {e["file"] for e in index["logos"].values()}
    for p in logos.iterdir():
        if p.name != LI.INDEX and p.name not in used:
            p.unlink()
    index["count"] = len(index["logos"])
    (logos / LI.INDEX).write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                  encoding="utf-8")
    _, bad = LI.validate_dir(logos)
    if bad:
        raise SystemExit("!! logos/ is not valid after the switch: " + "; ".join(bad[:5]))
    new = [{"code": c, "name": names.get(c, c), "reason": reason + ("" if c in want else " (preferred share of an issuer above)")}
           for c in sorted(gone)]
    exists = (folder / "drops.csv").exists()
    with open(folder / "drops.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "reason"], lineterminator="\n")
        if not exists:
            w.writeheader()
        w.writerows(new)
    info["drops"] = info.get("drops", []) + new
    (folder / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    (folder / "summary.md").write_text(summary_md(info), encoding="utf-8")
    print(f"· switched to the letter mark: {len(gone)} ({', '.join(sorted(gone))}) · logos left {len(index['logos']):,}")
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
    ap.add_argument("--dir", help="the output folder of an earlier run (with --drop)")
    ap.add_argument("--reason", default="wrong company on the contact sheet", help="why (with --drop)")
    a = ap.parse_args(argv)
    if a.max_credits < CREDITS or not 1 <= a.workers <= 10 or not 1 <= a.per_minute <= 450 or a.limit < 0 \
            or a.sheet_top < 1 or a.time_limit_min <= 0:
        ap.error("--max-credits at least 2, --workers 1 to 10, --per-minute 1 to 450 (Pro allows 500), --limit 0 or "
                 "more, --sheet-top at least 1, --time-limit-min above 0")
    if bool(a.drop) != bool(a.dir):
        ap.error("--drop and --dir go together")
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
    d = deps or Deps()
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
    started = d.wall()
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
    if a.limit:
        order = order[:a.limit]
        keep = {c["code"] for c in order}
        preferred = [p for p in preferred if p["issuer"] in keep]
        log(f"!! --limit {a.limit}: only the {len(order):,} largest companies (a trial run)")
    pl = plan(order)
    log(f"· data.json asOf {data.get('asOf')} · prices {data.get('pxDate')} (US {data.get('usPxDate')}) · companies "
        f"{len(order):,} (Korea {sum(1 for c in order if c['side'] == 'kr'):,} · US "
        f"{sum(1 for c in order if c['side'] == 'us'):,}) · preferred shares {len(preferred):,}")
    log(f"· lookups: at most {pl['lookups']:,} ({pl['ticker']:,} by ticker + {pl['domain']:,} by DART homepage) · "
        f"ceiling if every one were billed: {pl['ceiling']:,} credits (${pl['ceiling'] / 100:,.2f}) · the cap stops at "
        f"{a.max_credits:,} · no ticker: {sum(1 for c in order if not c.get('ticker'))}")
    if a.plan_only:
        log("· plan only: no logo.dev call was made")
        return 0

    out = chk.prepare_out(a.out or chk.CACHE_DIR / f"logo-dev-fetch-{started:%Y%m%d-%H%M%S}")
    out_logos = out / "logos"
    out_logos.mkdir()
    log(f"· output folder: {out} · logo files {'WebP' if d.webp else 'PNG (this Pillow has no WebP)'}")
    client = Client(key, d.send, SafePacer(d.clock, d.sleep, per_minute=a.per_minute, interval=60.0 / a.per_minute * 0.9),
                    SafePacer(d.clock, d.sleep, per_minute=DOWNLOADS_PER_MINUTE, interval=0.15))
    ledger = Ledger(a.max_credits)
    scope = {c["code"] for c in order if c["mrank"] <= a.sheet_top}
    f = Fetcher(client, ledger, log, out_logos, scope, d.clock, d.sleep, d.jitter,
                deadline=t0 + a.time_limit_min * 60, workers=a.workers, webp=d.webp)
    problems = []
    try:
        f.run(order)
    except Exception as e:                               # noqa: BLE001 — a bug: said, recorded, partial results saved
        f.stop = f.stop or chk.StopRun("crashed", f"{type(e).__name__}: {e}")
        for line in traceback.format_exc().splitlines():
            log("  " + line)
    groups = shared_groups([(j.c["code"], j.hash) for j in f.done if j.final == "logo" and j.hash is not None])
    rows = rows_of(f, preferred, groups)
    for i, g in enumerate(groups, 1):
        log(f"· shared picture {i}: " + ", ".join(g))
    fmt = "webp" if d.webp else "png"
    index = make_index(rows, stamp, data, fmt)
    (out_logos / LI.INDEX).write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                      encoding="utf-8")
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
    finished = f"{d.wall():%Y-%m-%d %H:%M}"
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
        "max_credits": a.max_credits, "format": fmt, "sheet_top": a.sheet_top, "sheet_pages": pages,
        "data": {"pxDate": data.get("pxDate"), "usPxDate": data.get("usPxDate"), "asOf": data.get("asOf")},
        "sources": sources, "plan": pl, "pace": {"per_minute": a.per_minute, "workers": a.workers},
        "tally": tally(rows), "shared": groups, "index_count": index["count"],
        "credits": {"counted": ledger.counted, "charged": ledger.charged, "free": ledger.free,
                    "no_header": ledger.no_header, "unknown": ledger.unknown, "balance_first": ledger.balance_first,
                    "balance_last": ledger.balance_last},
        "requests": {"api": client.api_requests, "downloads": client.downloads, "counts": dict(sorted(f.counts.items()))},
    }
    t = info["tally"]
    log(f"· finished {fin:,} of {comp:,} · Korea: ticker {t['kr']['by_ticker']:,} · homepage {t['kr']['by_domain']:,} · "
        f"letter {t['kr']['letter']:,} · US: ticker {t['us']['by_ticker']:,} · letter {t['us']['letter']:,} · "
        f"preferred reusing a logo {t['preferred']['logo']:,} · credits {ledger.counted:,}/{a.max_credits:,} · "
        f"lookups {client.api_requests:,} · downloads {client.downloads:,}")
    log(f"{'OK' if info['ok'] else '!! NOT OK'}: {OUTCOME_TEXT.get(outcome, outcome)} {info['reason']}".rstrip()
        + f" · results in {out}")
    write_csv(out, rows, mask)
    write_reports(out, info, log, mask)
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


if __name__ == "__main__":
    sys.exit(main())
