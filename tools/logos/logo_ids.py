# -*- coding: utf-8 -*-
"""Exact identifiers for company logos (shared by dart_homepages.py and build_test_page.py). Pure functions only.

Jack's rule (2026-11-05): a logo is looked up by an exact identifier only — ticker, ISIN or the company's own homepage
from DART — never by matching names. Anything without a hit gets a coloured letter mark in the app.

Taken from the v19.1 Part L logo test (branch claude/v19.1-logo-test, tools/logo_test/logo_common.py): the ISIN check
digit, the exact short-code -> ISIN rule, homepage -> domain, the provider URL formats and key masking. Added here: the
DART quiet window (no DART calls while the daily data run uses DART) and the seeded sample for the coverage test page.
Unit tests: tests/test_logos.py (no network).
"""
import datetime as dt
import random
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst():
    return dt.datetime.now(KST)


# ── DART quiet window ──────────────────────────────────────────────────────────────────────────────────────────────
# The daily data run (update-data.yml) starts 03:47 · 05:13 · 06:43 · 08:17 KST and uses DART. A tool that spends the
# same DART key's daily allowance must not run in that window, so the morning run never finds the allowance used up.
QUIET_START = dt.time(3, 40)
QUIET_END = dt.time(8, 30)


def in_quiet_window(when):
    """True when `when` (a timezone-aware datetime, any zone) is between 03:40 and 08:30 KST. A naive datetime is
    refused: on GitHub's runners and in the cloud the clock is UTC, and guessing the zone is how dates go wrong."""
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("in_quiet_window needs a timezone-aware datetime (KST or UTC), not a naive one")
    t = when.astimezone(KST).time()
    return QUIET_START <= t < QUIET_END


def refuse_in_quiet_window(when=None):
    """Stop (SystemExit) inside the DART quiet window. Returns the KST time it checked."""
    when = when or now_kst()
    k = when.astimezone(KST) if when.tzinfo else when
    if in_quiet_window(when):
        raise SystemExit(f"!! {k:%H:%M} KST is inside 03:40-08:30 KST, when the daily data run uses DART. "
                         "Run this after 08:30 KST.")
    return k


# ── ISIN ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def isin_check_digit(body):
    """Check digit for the first 11 characters of an ISIN (ISO 6166): letters become numbers (A=10 … Z=35), then the
    Luhn rule runs over the digit string, doubling every second digit starting from the rightmost one."""
    body = str(body).upper()
    if len(body) != 11 or not body.isascii() or not body.isalnum() or not body[:2].isalpha():
        raise ValueError(f"not an ISIN body (2 letters + 9 letters/digits): {body!r}")
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def isin_valid(isin):
    s = str(isin or "").strip().upper()
    if len(s) != 12 or not s[11].isdigit():
        return False
    try:
        return isin_check_digit(s[:11]) == s[11]
    except ValueError:
        return False


KRX_CODE = re.compile(r"^[0-9][0-9A-Z]{5}$")               # 6 characters; new listings since 2024 use letters too (0126Z0)


def is_krx_code(code):
    return bool(KRX_CODE.match(str(code or "")))


def kr_isin_from_code(code):
    """KRX ISIN derived from a short code, only where the rule is exact: a common share (code ends in 0) of a Korean
    issuer (not 9xxxxx, which are foreign issuers with KY/HK/US/KR8 ISINs) is KR7 + code + 00 + check digit.
    Preferred shares (005935 -> KR7005931001) and foreign issuers do not follow it, so they return None.
    Checked against all 2,741 such rows of the 2026-11-03 KRX listing: 2,741 equal, 0 different."""
    code = str(code or "").upper()
    if not is_krx_code(code) or code[-1] != "0" or code[0] == "9":
        return None
    body = "KR7" + code + "00"
    return body + isin_check_digit(body)


def common_code(code):
    """The issuer's common-share code for a KRX code: 005935 -> 005930, 00680K -> 006800. Same code for a common share."""
    code = str(code or "").upper()
    return code[:5] + "0" if is_krx_code(code) else code


def is_common_share(code):
    return is_krx_code(code) and str(code).upper().endswith("0")


# ── homepage -> domain ──────────────────────────────────────────────────────────────────────────────────────────────

_SCHEME = re.compile(r"^\s*(?:https?:/*|https?/{2,}|/+)\s*", re.I)       # http:// · http:/// · http// · leading /
_DOMAIN = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")
# Hosts that many unrelated companies use for their "homepage". A logo looked up by such a domain is the platform's
# logo, i.e. a wrong match, so these are never a company's domain:
#  - SHARED_HOSTS: the host and every subdomain (facebook.com/…, xxx.modoo.at, sites.google.com, linktr.ee/…);
#  - PLATFORM_SUBDOMAINS: only subdomains (blog.naver.com, cafe.naver.com, xxx.cafe24.com). The bare host stays usable,
#    because the one company that lists it as its own homepage is the platform itself (카페24 -> cafe24.com).
SHARED_HOSTS = ("daum.net", "tistory.com", "modoo.at", "wixsite.com", "wix.com", "imweb.me", "google.com",
                "facebook.com", "fb.com", "instagram.com", "linkedin.com", "youtube.com", "youtu.be", "twitter.com",
                "x.com", "linktr.ee", "band.us", "github.io", "github.com", "notion.site", "notion.so", "blogspot.com",
                "wordpress.com", "medium.com", "naver.me", "bit.ly", "me2.do", "krx.co.kr", "fss.or.kr",
                "sixshop.com", "creatorlink.net", "weebly.com", "webflow.io", "gitbook.io")
PLATFORM_SUBDOMAINS = ("naver.com", "kakao.com", "cafe24.com")


def homepage_domain(url):
    """'http://www.samsung.com/sec' -> 'samsung.com'. Adds nothing and guesses nothing: copes with the messy values
    in DART and the KRX company list ('http://https://x.co.kr/', 'http:///www.x.ai', 'http:// http://www.x.co.kr',
    'RAON.io', 'www.x.co.kr/kor/main.do') by removing the scheme, the path, a port and user info. Returns '' when the
    value is empty or not a usable host name. Only a leading 'www.' is removed; other subdomains stay."""
    s = str(url or "").strip()
    while True:
        t = _SCHEME.sub("", s, count=1)
        if t == s:
            break
        s = t
    s = re.split(r"[\s,;/?#\\]", s, maxsplit=1)[0]
    s = s.rsplit("@", 1)[-1].split(":", 1)[0].strip(".").lower()
    if not s:
        return ""
    if not s.isascii():
        try:
            s = s.encode("idna").decode("ascii")
        except UnicodeError:
            return ""
    if s.startswith("www.") and s.count(".") >= 2:
        s = s[4:]
    return s if _DOMAIN.match(s) else ""


def is_shared_host(domain):
    d = str(domain or "")
    if any(d == h or d.endswith("." + h) for h in SHARED_HOSTS):
        return True
    return any(d.endswith("." + h) for h in PLATFORM_SUBDOMAINS)          # blog.naver.com yes, naver.com no


_NO_HOMEPAGE = {"n/a", "na", "none", "null", "nil", "no", "x", "tbd"}


def has_homepage(raw):
    """False for an empty value and for DART's placeholders: '-', '.', a Korean word for "none" (no Latin letter or
    digit at all — every web address has one, even a Korean-script domain ends in .kr or .com) and n/a, none …"""
    s = str(raw or "").strip()
    return bool(re.search(r"[0-9A-Za-z]", s)) and s.lower() not in _NO_HOMEPAGE


def judge_homepage(raw):
    """(domain, usable, note) for one raw homepage value. usable is False for an empty value, a value that is not a
    host name, and a platform host (blog.naver.com, facebook.com …): a logo looked up by those would not be the
    company's. The domain is still returned for a platform host so the CSV shows what was there."""
    raw = str(raw or "").strip()
    if not has_homepage(raw):
        return "", False, "no homepage"
    dom = homepage_domain(raw)
    if not dom:
        return "", False, "not a host name"
    if is_shared_host(dom):
        return dom, False, "platform host"
    return dom, True, ""


# ── providers ───────────────────────────────────────────────────────────────────────────────────────────────────────
# Brandfetch Logo API (docs.brandfetch.com/logo-api/parameters, read 2026-11-04):
#   https://cdn.brandfetch.io/{route}/{id}/w/{w}/h/{h}/fallback/404?c=CLIENT_ID      route = ticker | isin | domain
#   fallback/404 -> HTTP 404 with an empty body when there is no logo (default fallback: a 200 placeholder image).
# logo.dev (logo.dev/docs/logo-images/*, read 2026-11-04):
#   https://img.logo.dev/ticker/{T}?token=pk_…   T = AAPL (US) · 005930.KS (KOSPI) · 247540.KQ (KOSDAQ)
#   https://img.logo.dev/{domain}?token=…   fallback=404 -> 404 when there is no logo (default: a generated monogram);
#   202 = first request for a domain that logo.dev is still fetching (try again after a few minutes).
# Both providers' terms: these images are for pages in people's browsers. No script, crawler or headless browser may
# request them — the coverage test page builds these URLs in Jack's own browser; nothing in tools/ or tests/ loads them.
BF_BASE = "https://cdn.brandfetch.io"
LD_BASE = "https://img.logo.dev"
SIZE = 128


def logo_url(provider, route, ident, key, fallback404=True, size=SIZE, bf_base=BF_BASE, ld_base=LD_BASE):
    """The image URL a page embeds (the page's JavaScript builds the same string; tests/test_logos.py checks both)."""
    ident_q = quote(str(ident), safe=".-_")
    if provider == "brandfetch":
        if route not in ("ticker", "isin", "domain"):
            raise KeyError(route)
        tail = "/fallback/404" if fallback404 else ""
        return f"{bf_base}/{route}/{ident_q}/w/{size}/h/{size}{tail}?c={quote(str(key), safe='')}"
    if provider == "logodev":
        if route not in ("ticker", "isin", "domain"):
            raise KeyError(route)
        path = ident_q if route == "domain" else f"{route}/{ident_q}"
        fb = "&fallback=404" if fallback404 else ""
        return f"{ld_base}/{path}?token={quote(str(key), safe='')}&size={size}&format=webp{fb}"
    raise KeyError(provider)


def logodev_ticker(code, market):
    """logo.dev's ticker form: KOSPI 005930.KS · KOSDAQ 247540.KQ · KONEX .KS (logo.dev has no KONEX suffix and says it
    also checks a market's other exchanges) · US as it is (BRK-B). '' when the market is unknown."""
    if market == "US":
        return str(code)
    if market in ("KOSPI", "KONEX"):
        return f"{code}.KS"
    if market == "KOSDAQ":
        return f"{code}.KQ"
    return ""


class Masker:
    """Replaces every secret value (and its URL-encoded form) with *** in text that is printed or written."""

    def __init__(self, *secrets):
        vals = set()
        for s in secrets:
            if s:
                vals.add(str(s))
                vals.add(quote(str(s), safe=""))
        self.vals = sorted((v for v in vals if len(v) >= 4), key=len, reverse=True)

    def __call__(self, text):
        t = str(text)
        for v in self.vals:
            t = t.replace(v, "***")
        return t


def check_publishable_keys(brandfetch, logodev):
    """The two keys that may sit in a page's source. Refuses a secret key (logo.dev sk_…, or anything sk_) and blanks."""
    for name, v in (("BRANDFETCH_CLIENT_ID", brandfetch), ("LOGODEV_TOKEN", logodev)):
        v = str(v or "").strip()
        if not v:
            raise SystemExit(f"!! {name} is empty")
        if v.lower().startswith("sk_"):
            raise SystemExit(f"!! {name} is a SECRET key (sk_…). Only publishable keys may go into a page.")
        if not re.fullmatch(r"[A-Za-z0-9_\-]{6,80}", v):
            raise SystemExit(f"!! {name} has unexpected characters (only letters, digits, _ and -)")
    if not str(logodev).strip().startswith("pk_"):
        raise SystemExit("!! LOGODEV_TOKEN must be the publishable key (pk_…)")
    return str(brandfetch).strip(), str(logodev).strip()


# ── sample for the coverage test page ───────────────────────────────────────────────────────────────────────────────

def _cap(r):
    v = r.get("cap")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) and v > 0 else None


def quantile_groups(rows, k):
    """Split rows (already sorted largest first) into k groups of (almost) equal size, largest first."""
    n = len(rows)
    bounds = [round(i * n / k) for i in range(k + 1)]
    return [rows[bounds[i]:bounds[i + 1]] for i in range(k)]


def draw_sample(companies, seed, kr_top=200, kr_random=300, kr_groups=4, us_random=100, us_groups=4):
    """The coverage test sample. companies: dicts with code, side ('kr' | 'us'), cap (조원), and anything else.
    ETFs, funds and preferred shares must already be left out by the caller.

    - KR group A: the kr_top largest Korean companies by market cap (every one of them, not a sample).
    - KR groups B…: the remaining Korean companies split into kr_groups equal-size market-cap groups; kr_random of them
      at random, the same number from each group (stratified).
    - US groups A…: all US companies split into us_groups equal-size market-cap groups; us_random at random, the same
      number from each group.
    A company without a market cap is never ranked or grouped (left out, and counted in `left_out`).
    Same input + same seed -> the same sample. Returns (picked, groups, left_out):
      picked: [{**company, group, rank}] in group order, largest first within each group;
      groups: [{id, side, label, population, sampled, cap_hi, cap_lo, rank_lo, rank_hi}]."""
    rng = random.Random(seed)
    left_out = [c for c in companies if _cap(c) is None]
    picked, groups = [], []
    for side in ("kr", "us"):
        rows = sorted((c for c in companies if c.get("side") == side and _cap(c) is not None),
                      key=lambda c: (-_cap(c), str(c["code"])))
        ranked = [dict(c, rank=i) for i, c in enumerate(rows, 1)]
        if side == "kr":
            parts = [("A", ranked[:kr_top], None)]
            rest = ranked[kr_top:]
            per = kr_random // kr_groups if kr_groups else 0
            parts += [(chr(ord("B") + i), g, per) for i, g in enumerate(quantile_groups(rest, kr_groups))]
        else:
            per = us_random // us_groups if us_groups else 0
            parts = [(chr(ord("A") + i), g, per) for i, g in enumerate(quantile_groups(ranked, us_groups))]
        for letter, members, n in parts:
            gid = f"{side.upper()}-{letter}"
            if n is None:
                chosen = list(members)
            else:
                if n > len(members):
                    raise ValueError(f"group {gid} has {len(members)} companies, fewer than the {n} to draw")
                chosen = sorted(rng.sample(members, n), key=lambda c: c["rank"])
            picked += [dict(c, group=gid) for c in chosen]
            groups.append({"id": gid, "side": side, "population": len(members), "sampled": len(chosen),
                           "census": n is None,
                           "rank_hi": members[0]["rank"] if members else None,
                           "rank_lo": members[-1]["rank"] if members else None,
                           "cap_hi": _cap(members[0]) if members else None,
                           "cap_lo": _cap(members[-1]) if members else None})
    return picked, groups, left_out
