# -*- coding: utf-8 -*-
"""Shared helpers for the v19.1 Part L logo coverage test (tools/logo_test/). See README.md in this folder.

Pure functions here (ISIN check digit, homepage -> domain, provider URLs, key masking, the coverage summary) are unit-tested
in tests/test_logo_tools.py without any network. The browser helpers at the bottom start a local page and Playwright's
Chromium: both providers' rules say their CDN images must be loaded by a browser page that embeds them (with a Referer),
not fetched by a script, so every logo request in this test is an <img> load from a page on http://127.0.0.1.

Keys come only from environment variables (BRANDFETCH_CLIENT_ID, LOGODEV_TOKEN). Nothing here prints, logs or writes
them: every log line and every URL written to disk goes through Masker.
"""
import csv
import datetime as dt
import http.server
import os
import pathlib
import re
import socketserver
import sys
import threading
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent                                   # repository root
KST = ZoneInfo("Asia/Seoul")

# Where results, contact sheets and (opt-in) image copies go: never inside the repository (no logo files, no API
# responses in git). Override with --out or LOGO_TEST_DIR.
DEFAULT_OUT = os.environ.get(
    "LOGO_TEST_DIR",
    "/tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/logos")

ENV_BRANDFETCH = "BRANDFETCH_CLIENT_ID"
ENV_LOGODEV = "LOGODEV_TOKEN"

DATA_URL = "https://jacksungjinlee.github.io/baepsae/data.json"
CACHE_BASE = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing"
LISTING_URL = CACHE_BASE + "/krx/{d}.csv"                  # Code, ISU_CD (ISIN), Name, Market … (same file fetch_data.py reads)
DESC_URL = CACHE_BASE + "/desc/{d}.csv"                     # Code, Name, Market, … HomePage (KRX KIND company list)


def now_kst():
    return dt.datetime.now(KST)


def out_dir(path=None):
    """The scratch folder (created). Refuses a folder inside the repository so logo files and results never get committed."""
    p = pathlib.Path(path or DEFAULT_OUT).expanduser().resolve()
    if p == ROOT or ROOT in p.parents:
        raise SystemExit(f"!! output folder {p} is inside the repository; use a scratch folder outside it (--out)")
    p.mkdir(parents=True, exist_ok=True)
    return p


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


# ── homepage -> domain ──────────────────────────────────────────────────────────────────────────────────────────────

_SCHEME = re.compile(r"^\s*(?:[a-z][a-z0-9+.-]*:)?/*\s*", re.I)
_DOMAIN = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")
# Hosts that many unrelated companies use for their "homepage". A logo looked up by such a domain is the platform's
# logo, i.e. a wrong match, so these never become a company's domain:
#  - SHARED_HOSTS: the host and every subdomain (facebook.com/…, xxx.modoo.at, sites.google.com …);
#  - PLATFORM_SUBDOMAINS: only subdomains (blog.naver.com, xxx.cafe24.com). The bare host stays usable, because the
#    one company that lists it as its own homepage is the platform itself (카페24 -> cafe24.com).
SHARED_HOSTS = ("daum.net", "tistory.com", "modoo.at", "wixsite.com", "wix.com", "imweb.me", "google.com",
                "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "github.io", "notion.site",
                "krx.co.kr", "fss.or.kr")
PLATFORM_SUBDOMAINS = ("naver.com", "kakao.com", "cafe24.com")


def homepage_domain(url):
    """'http://www.samsung.com/sec' -> 'samsung.com'. Copes with the messy values in the KRX company list
    ('http://https://x.co.kr/', 'http:///www.x.ai', 'http:// http://www.x.co.kr', 'RAON.io'). Returns '' when the value
    is empty or not a usable host name. Only a leading 'www.' is removed; other subdomains stay."""
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


# ── providers and routes ────────────────────────────────────────────────────────────────────────────────────────────
# Brandfetch Logo API (docs.brandfetch.com/logo-api/parameters, read 2026-11-04):
#   https://cdn.brandfetch.io/{route}/{id}/w/{w}/h/{h}/fallback/404?c=CLIENT_ID      route = ticker | isin | domain
#   fallback/404 -> HTTP 404 with an empty body when there is no logo (default fallback: a 200 'transparent' or
#   'brandfetch' image). Refusals carry an x-bf-error header (302 automated_traffic / hotlink_blocked …, 403, 429).
# logo.dev (logo.dev/docs/logo-images/*, read 2026-11-04):
#   https://img.logo.dev/ticker/{T}?token=pk_…   T = AAPL (US) · 005930.KS (Korea Exchange) · 247540.KQ (KOSDAQ)
#   https://img.logo.dev/isin/{ISIN}?token=…  ·  https://img.logo.dev/{domain}?token=…
#   fallback=404 -> 404 when there is no logo (default: a 200 generated monogram); 202 = first request for a domain
#   that logo.dev is still fetching (try again after a few minutes).
BF_BASE = "https://cdn.brandfetch.io"
LD_BASE = "https://img.logo.dev"
SIZE = 128

# (provider, route): which tickers.csv column feeds it. ticker_code is Brandfetch's ticker route with the bare KRX code
# (its docs name no exchange suffix, so both 005930.KS and 005930 are tried); it is not tried for US tickers.
ROUTES = [
    ("brandfetch", "ticker", "ticker"),
    ("brandfetch", "ticker_code", "code"),
    ("brandfetch", "isin", "isin"),
    ("brandfetch", "domain", "domain"),
    ("logodev", "ticker", "ticker"),
    ("logodev", "isin", "isin"),
    ("logodev", "domain", "domain"),
]
ROUTE_KEYS = [f"{p}:{r}" for p, r, _ in ROUTES]
PROVIDERS = ("brandfetch", "logodev")
# Best mix, tried in this order (ticker -> ISIN -> domain across providers). Change with --mix-order.
DEFAULT_MIX = ["brandfetch:ticker", "logodev:ticker", "brandfetch:ticker_code", "brandfetch:isin", "logodev:isin",
               "brandfetch:domain", "logodev:domain"]


def route_ident(row, provider, route):
    """The identifier a route uses for one tickers.csv row, or '' when the route does not apply."""
    col = {r: c for p, r, c in ROUTES if p == provider}.get(route)
    if col is None:
        raise KeyError(f"{provider}:{route}")
    if route == "ticker_code" and row.get("market") == "US":
        return ""
    v = str(row.get(col) or "").strip()
    if route == "ticker_code" and v == str(row.get("ticker") or ""):
        return ""                                            # same request as the ticker route
    return v


def logo_url(provider, route, ident, key, bf_base=BF_BASE, ld_base=LD_BASE, fallback404=True, size=SIZE):
    """The image URL a page would embed. key is the publishable key / client ID (never printed: see Masker)."""
    from urllib.parse import quote
    ident_q = quote(str(ident), safe=".-_")
    if provider == "brandfetch":
        if route not in ("ticker", "ticker_code", "isin", "domain"):
            raise KeyError(route)
        seg = "ticker" if route in ("ticker", "ticker_code") else route
        tail = "/fallback/404" if fallback404 else ""
        return f"{bf_base}/{seg}/{ident_q}/w/{size}/h/{size}{tail}?c={quote(str(key), safe='')}"
    if provider == "logodev":
        if route not in ("ticker", "isin", "domain"):
            raise KeyError(route)
        path = ident_q if route == "domain" else f"{route}/{ident_q}"
        fb = "&fallback=404" if fallback404 else ""
        return f"{ld_base}/{path}?token={quote(str(key), safe='')}&size={size}&format=webp{fb}"
    raise KeyError(provider)


class Masker:
    """Replaces every secret value (and its URL-encoded form) with *** in text that is printed or written."""

    def __init__(self, *secrets):
        from urllib.parse import quote
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


def read_keys(need=PROVIDERS):
    """Keys from the environment only. A logo.dev secret key (sk_) is refused: this test needs the publishable key."""
    keys = {"brandfetch": os.environ.get(ENV_BRANDFETCH, "").strip(), "logodev": os.environ.get(ENV_LOGODEV, "").strip()}
    if keys["logodev"].startswith("sk_"):
        raise SystemExit(f"!! {ENV_LOGODEV} holds a logo.dev SECRET key (sk_…). Use the publishable key (pk_…); "
                         "never paste the secret key anywhere.")
    missing = [ENV_BRANDFETCH if p == "brandfetch" else ENV_LOGODEV for p in need if not keys[p]]
    return keys, missing


# ── CSV helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────

TICKER_COLS = ["code", "name", "name_en", "cls", "market", "market_raw", "etf", "cap", "rank", "rank_cls", "ticker",
               "isin", "isin_src", "issuer_code", "domain", "domain_src", "homepage_raw"]
RESULT_COLS = ["code", "provider", "route", "ident", "verdict", "status", "content_type", "bytes", "sha256", "w", "h",
               "x_bf_error", "tries", "url", "at"]
FINAL_VERDICTS = ("hit", "miss", "fallback", "bad_request")    # a resumed run skips these and retries the rest


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, cols):
    tmp = pathlib.Path(str(path) + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def latest_results(rows):
    """Last row per (code, provider, route): results.csv is append-only, a resumed run adds newer rows."""
    out = {}
    for r in rows:
        out[(r["code"], r["provider"], r["route"])] = r
    return out


# ── coverage summary (pure) ─────────────────────────────────────────────────────────────────────────────────────────

MARKETS = ["KOSPI", "KOSDAQ", "KONEX", "US"]


def group_of(row):
    return "ETF/fund" if str(row.get("etf")) == "1" else (row.get("market") or "?")


def choose_mix(tickers, latest, order=DEFAULT_MIX):
    """For each ticker: the first route in `order` that found a logo. A preferred share with no hit of its own takes
    its common share's choice (same company, 005935 -> 005930) and is marked 'common:<route>'."""
    by_code = {}
    for t in tickers:
        pick = ""
        for key in order:
            p, r = key.split(":")
            res = latest.get((t["code"], p, r))
            if res and res["verdict"] == "hit":
                pick = key
                break
        by_code[t["code"]] = pick
    out = []
    for t in tickers:
        pick, via = by_code[t["code"]], ""
        ic = t.get("issuer_code") or ""
        if not pick and ic and ic != t["code"] and by_code.get(ic):
            pick, via = by_code[ic], ic
        out.append({"code": t["code"], "pick": pick, "via_code": via})
    return out


def _pct(n, d):
    return f"{n:,} / {d:,} ({100.0 * n / d:.1f}%)" if d else "–"


def summarize(tickers, latest, order=DEFAULT_MIX, notes=(), probes=None, stopped=None, shared_hashes=None):
    """Markdown coverage report: per provider × route × market, per provider (any route), and the best mix."""
    groups = MARKETS + ["ETF/fund"]
    by_group = {g: [t for t in tickers if group_of(t) == g] for g in groups}
    lines = [f"# Logo coverage test — {now_kst():%Y-%m-%d %H:%M} KST", ""]
    lines += [f"- {n}" for n in notes]
    lines += ["", "Tickers: " + " · ".join(f"{g} {len(by_group[g]):,}" for g in groups) + f" · total {len(tickers):,}", ""]
    if stopped:
        lines += ["## Stopped early", ""] + [f"- **{p}**: {why}" for p, why in stopped.items()] + [""]
    if probes:
        lines += ["## How each provider marks \"no logo\" (probe at start)", "",
                  "| provider | route | identifier | fallback | status | type | bytes | size | x-bf-error | reads as |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for p in probes:
            lines.append(f"| {p['provider']} | {p['route']} | `{p['ident']}` | {p['fallback']} | {p['status']} | "
                         f"{p['content_type']} | {p['bytes']} | {p['w']}×{p['h']} | {p['x_bf_error']} | "
                         f"{p.get('verdict', '')} |")
        lines.append("")
    lines += ["## Coverage per provider × route × market", "",
              "Each cell: logos found / identifiers tried (share of tried). A route is tried only where the identifier "
              "exists (no ISIN or domain → not tried).", "",
              "| route | " + " | ".join(groups) + " | not tried / errors |", "|---|" + "---|" * (len(groups) + 1)]
    for key in ROUTE_KEYS:
        p, r = key.split(":")
        cells, nt, err = [], 0, 0
        for g in groups:
            tried = hit = 0
            for t in by_group[g]:
                res = latest.get((t["code"], p, r))
                if res is None or res["verdict"] in ("", "skip"):
                    if route_ident(t, p, r):
                        nt += 1
                    continue
                if res["verdict"] in FINAL_VERDICTS:
                    tried += 1
                    hit += res["verdict"] == "hit"
                else:
                    err += 1
            cells.append(_pct(hit, tried))
        lines.append(f"| {key} | " + " | ".join(cells) + f" | {nt:,} / {err:,} |")
    lines += ["", "## Coverage per provider (any of its routes) and the best mix", "",
              "Share of ALL tickers in the group.", "", "| | " + " | ".join(groups) + " |", "|---|" + "---|" * len(groups)]
    for prov in PROVIDERS:
        own = [k for k in order if k.startswith(prov + ":")]
        mix = {m["code"]: m for m in choose_mix(tickers, latest, own)}
        lines.append(f"| {prov} alone | " + " | ".join(_pct(sum(1 for t in by_group[g] if mix[t['code']]['pick']),
                                                            len(by_group[g])) for g in groups) + " |")
    mix_rows = choose_mix(tickers, latest, order)
    mix = {m["code"]: m for m in mix_rows}
    lines.append("| **best mix** | " + " | ".join(_pct(sum(1 for t in by_group[g] if mix[t['code']]['pick']),
                                                         len(by_group[g])) for g in groups) + " |")
    lines += ["", "Best mix order: " + " → ".join(order) + " → (preferred share: its common share's logo)", "",
              "## Where the best mix found each logo", "", "| step | " + " | ".join(groups) + " |",
              "|---|" + "---|" * len(groups)]
    for key in order + ["common share"]:
        def n(g):
            return sum(1 for t in by_group[g]
                       if (mix[t["code"]]["pick"] == key and not mix[t["code"]]["via_code"])
                       or (key == "common share" and mix[t["code"]]["via_code"]))
        lines.append(f"| {key} | " + " | ".join(f"{n(g):,}" for g in groups) + " |")
    if shared_hashes:
        lines += ["", "## Same image for different companies (check for placeholders or group logos)", "",
                  "| route | sha256 | companies |", "|---|---|---|"]
        for (key, h), names in shared_hashes:
            lines.append(f"| {key} | `{h[:12]}` | {len(names)}: {', '.join(names[:8])}{' …' if len(names) > 8 else ''} |")
    lines += ["", "Next: `python3 tools/logo_test/contact_sheet.py` (the 200 largest Korean and the 200 largest US "
              "companies with the best mix) and look for wrong matches.", ""]
    return "\n".join(lines), mix_rows


def shared_image_hashes(tickers, latest, min_companies=3):
    """Hashes that one route returned as a 'hit' for >= min_companies different issuers (preferred shares count with
    their common share). Either an unknown placeholder or one group logo for several companies: both need a look."""
    names = {t["code"]: (t.get("issuer_code") or t["code"], t.get("name") or t["code"]) for t in tickers}
    seen = {}
    for (code, p, r), res in latest.items():
        if res.get("verdict") == "hit" and res.get("sha256") and code in names:
            issuer, nm = names[code]
            seen.setdefault((f"{p}:{r}", res["sha256"]), {})[issuer] = nm
    out = [(k, sorted(v.values())) for k, v in seen.items() if len(v) >= min_companies]
    return sorted(out, key=lambda x: -len(x[1]))


# ── local page server and browser (Chromium through the session proxy) ─────────────────────────────────────────────

class _Quiet(http.server.SimpleHTTPRequestHandler):
    mounts = {}

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        for prefix, base in sorted(self.mounts.items(), key=lambda kv: -len(kv[0])):
            if clean == prefix.rstrip("/") or clean.startswith(prefix):
                rel = clean[len(prefix):].lstrip("/")
                target = (pathlib.Path(base) / rel).resolve()
                if pathlib.Path(base).resolve() in target.parents or target == pathlib.Path(base).resolve():
                    return str(target)
                return str(pathlib.Path(base) / "__denied__")
        return str(pathlib.Path(self.mounts.get("/", ".")) / "__denied__")


def serve(mounts):
    """Serve folders on http://127.0.0.1:<free port>/ — mounts = {"/": dir, "/fonts/": dir, …}. Returns (base_url, stop)."""
    handler = type("H", (_Quiet,), {"mounts": dict(mounts)})
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", lambda: (httpd.shutdown(), httpd.server_close())


def browser_launch_args(headed=False):
    """Chromium options: the session's outbound proxy (HTTPS_PROXY) when there is one; 127.0.0.1 stays direct."""
    args = {"headless": not headed}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        args["proxy"] = {"server": proxy, "bypass": "127.0.0.1,localhost"}
    return args


# The page-side loader: plain <img> loads with the browser's default Referrer-Policy (strict-origin-when-cross-origin,
# which both providers accept), paced to `rate` requests per second with at most `conc` in flight. It reports whether
# each image decoded and its natural size; status, type and bytes come from Playwright's response events.
PROBE_JS = r"""
window.__slots = window.__slots || {};
window.probe = async (lane, urls, rate, conc, timeoutMs) => {
  const out = new Array(urls.length);
  const gap = 1000 / Math.max(rate, 0.01);
  let next = 0;
  const wait = async () => {
    const now = performance.now();
    const at = Math.max(now, window.__slots[lane] || 0);
    window.__slots[lane] = at + gap;
    if (at > now) await new Promise((r) => setTimeout(r, at - now));
  };
  const one = (url) => new Promise((resolve) => {
    const img = new Image();
    let done = false;
    const t0 = performance.now();
    const fin = (ok) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve({ ok, w: img.naturalWidth || 0, h: img.naturalHeight || 0, ms: Math.round(performance.now() - t0) });
    };
    const timer = setTimeout(() => fin(null), timeoutMs);
    img.onload = () => fin(true);
    img.onerror = () => fin(false);
    img.decoding = 'async';
    img.src = url;
  });
  const worker = async () => {
    while (next < urls.length) {
      const k = next++;
      await wait();
      out[k] = await one(urls[k]);
    }
  };
  await Promise.all(Array.from({ length: Math.min(conc, urls.length) }, worker));
  return out;
};
"""

HARNESS_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>logo coverage test</title>
<meta name="referrer" content="strict-origin-when-cross-origin"></head>
<body><p>Logo coverage test page (tools/logo_test/run_test.py). Images load here the way an app page loads them.</p>
</body></html>
"""


def log_factory(masker, stream=None):
    def log(*parts):
        print(masker(" ".join(str(p) for p in parts)), file=stream or sys.stdout, flush=True)
    return log

