# -*- coding: utf-8 -*-
"""run_test.py --self-test: the whole pipeline (browser page, probes, retries, stop rules, summary, mix, masking)
against a fake Brandfetch and a fake logo.dev on 127.0.0.1. No provider is contacted; it needs Playwright's Chromium.

Run A: a few tickers whose fake answers cover every case (logo, 404, 429 then logo, 503 then logo, 202 then logo, a
placeholder image returned even with fallback=404, 400). Each (ticker, provider, route) must end with the expected
verdict, the preferred share must take its common share's logo, and the summary numbers must match.
Run B: a wrong Brandfetch client ID -> Brandfetch stops at the probe (403 client_id_invalid_signature), logo.dev
still runs. In both runs the fake keys must not appear in any file written or any line printed.
"""
import contextlib
import hashlib
import http.server
import io
import os
import pathlib
import shutil
import socketserver
import threading
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image

from logo_common import TICKER_COLS, out_dir, read_csv, write_csv

BF_KEY, LD_KEY = "bf-fake-client-id-123", "pk_fake_token_456"


def png(rgba):
    b = io.BytesIO()
    Image.new("RGBA", (128, 128), rgba).save(b, "PNG")
    return b.getvalue()


def color_of(text):
    h = hashlib.md5(text.encode()).digest()
    return (h[0], h[1], h[2], 255)


TRANSPARENT = png((0, 0, 0, 0))
# ident -> behaviour (both providers unless a provider prefix is given)
BEHAVIOUR = {
    "AAPL": "logo", "US0378331005": "logo", "apple.com": "logo",
    "bf:005930.KS": "none", "bf:005930": "none", "bf:KR7005930003": "logo", "bf:samsung.com": "logo",
    "ld:005930.KS": "logo", "ld:KR7005930003": "429once", "ld:samsung.com": "pending",
    "bf:247540.KQ": "503once", "ld:247540.KQ": "none", "bf:KR7247540008": "placeholder", "ld:KR7247540008": "none",
    "bf:BRK-B": "none", "ld:BRK-B": "bad",
}
EXPECT = {
    ("005930", "brandfetch", "ticker"): "miss", ("005930", "brandfetch", "ticker_code"): "miss",
    ("005930", "brandfetch", "isin"): "hit", ("005930", "brandfetch", "domain"): "hit",
    ("005930", "logodev", "ticker"): "hit", ("005930", "logodev", "isin"): "hit", ("005930", "logodev", "domain"): "hit",
    ("005935", "brandfetch", "ticker"): "miss", ("005935", "brandfetch", "ticker_code"): "miss",
    ("005935", "brandfetch", "isin"): "miss", ("005935", "logodev", "ticker"): "miss",
    ("005935", "logodev", "isin"): "miss", ("005935", "brandfetch", "domain"): "hit",
    ("005935", "logodev", "domain"): "hit",
    ("005937", "brandfetch", "ticker"): "miss", ("005937", "brandfetch", "ticker_code"): "miss",
    ("005937", "logodev", "ticker"): "miss",
    ("247540", "brandfetch", "ticker"): "hit", ("247540", "brandfetch", "ticker_code"): "miss",
    ("247540", "brandfetch", "isin"): "fallback", ("247540", "logodev", "ticker"): "miss",
    ("247540", "logodev", "isin"): "miss",
    ("AAPL", "brandfetch", "ticker"): "hit", ("AAPL", "logodev", "ticker"): "hit",
    ("BRK-B", "brandfetch", "ticker"): "miss", ("BRK-B", "logodev", "ticker"): "bad_request",
    ("069500", "brandfetch", "ticker"): "miss", ("069500", "brandfetch", "ticker_code"): "miss",
    ("069500", "brandfetch", "isin"): "miss", ("069500", "logodev", "ticker"): "miss",
    ("069500", "logodev", "isin"): "miss",
}
EXPECT_MIX = {"005930": "logodev:ticker", "005935": "brandfetch:domain", "005937": "logodev:ticker", "247540": "brandfetch:ticker",
              "AAPL": "brandfetch:ticker", "BRK-B": "", "069500": ""}


def tickers():
    base = {c: "" for c in TICKER_COLS}
    rows = [
        dict(base, code="005930", name="삼성전자", cls="kr", market="KOSPI", etf="0", cap="1283.258", rank="1",
             rank_cls="1", ticker="005930.KS", isin="KR7005930003", issuer_code="005930", domain="samsung.com"),
        dict(base, code="005935", name="삼성전자우", cls="kr", market="KOSPI", etf="0", cap="100.000", rank="4",
             rank_cls="3", ticker="005935.KS", isin="KR7005931001", issuer_code="005930", domain="samsung.com"),
        dict(base, code="005937", name="삼성전자3우", cls="kr", market="KOSPI", etf="0", cap="50.000", rank="5",
             rank_cls="4", ticker="005937.KS", issuer_code="005930"),          # made up: no ISIN, no domain
        dict(base, code="247540", name="에코프로비엠", cls="kr", market="KOSDAQ", etf="0", cap="20.000", rank="5",
             rank_cls="4", ticker="247540.KQ", isin="KR7247540008", issuer_code="247540"),
        dict(base, code="AAPL", name="Apple Inc.", cls="us", market="US", etf="0", cap="5000.000", rank="2",
             rank_cls="1", ticker="AAPL", issuer_code="AAPL"),
        dict(base, code="BRK-B", name="Berkshire Hathaway Inc.", cls="us", market="US", etf="0", cap="1400.000",
             rank="3", rank_cls="2", ticker="BRK-B", issuer_code="BRK-B"),
        dict(base, code="069500", name="KODEX 200", cls="kr", market="KOSPI", etf="1", cap="15.000", rank="6",
             rank_cls="5", ticker="069500.KS", isin="KR7069500007", issuer_code="069500"),
    ]
    return rows


class Fake(http.server.BaseHTTPRequestHandler):
    seen = {}
    harness_origin = ""
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def send(self, status, body=b"", ctype="image/png", headers=()):
        self.send_response(status)
        if body:
            self.send_header("Content-Type", ctype)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        parts = [unquote(x) for x in u.path.strip("/").split("/")]
        prov = parts[0]
        ref = self.headers.get("Referer", "")
        if prov == "bf":
            if not ref.startswith(self.harness_origin):
                return self.send(302, headers=[("Location", "/usage"), ("x-bf-error", "hotlink_blocked")])
            if q.get("c", [""])[0] != BF_KEY:
                return self.send(403, b'{"error":"bad"}', "application/json",
                                 [("x-bf-error", "client_id_invalid_signature")])
            ident, f404 = parts[2], "fallback" in parts and parts[parts.index("fallback") + 1] == "404"
            key = "bf:" + ident
        elif prov == "ld":
            if q.get("token", [""])[0] != LD_KEY:
                return self.send(401, b'{"msg":"invalid api token"}', "application/json")
            ident = parts[2] if parts[1] in ("ticker", "isin") else parts[1]
            f404 = q.get("fallback", [""])[0] == "404"
            key = "ld:" + ident
        else:
            return self.send(404)
        beh = BEHAVIOUR.get(key) or BEHAVIOUR.get(ident) or "none"
        with self.lock:
            n = self.seen[key] = self.seen.get(key, 0) + 1
        if beh == "logo" or (beh == "429once" and n > 1) or (beh == "503once" and n > 1) or (beh == "pending" and n > 1):
            return self.send(200, png(color_of(key)))
        if beh == "429once":
            return self.send(429, b'{"msg":"slow down"}', "application/json", [("Retry-After", "1")])
        if beh == "503once":
            return self.send(503, b"busy", "text/plain")
        if beh == "pending":
            return self.send(202, png(color_of("monogram:" + ident[:1])))
        if beh == "placeholder":
            return self.send(200, TRANSPARENT)
        if beh == "bad":
            return self.send(400, b'{"msg":"malformed ticker"}', "application/json")
        if f404:
            return self.send(404)
        if prov == "bf":
            return self.send(200, TRANSPARENT)
        return self.send(200, png(color_of("monogram:" + ident[:1])))


def start_fake():
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Fake)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", lambda: (httpd.shutdown(), httpd.server_close())


def no_secrets(folder, printed, secrets):
    leaks = []
    for p in pathlib.Path(folder).rglob("*"):
        if p.is_file() and p.suffix in (".csv", ".md", ".html", ".txt", ".json"):
            t = p.read_text(encoding="utf-8", errors="replace")
            leaks += [(str(p), s) for s in secrets if s in t]
    leaks += [("stdout", s) for s in secrets if s in printed]
    assert not leaks, f"key value written or printed: {leaks}"


def run(a):
    import run_test
    from logo_common import latest_results

    root = out_dir(a.out) / "selftest"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    fake, stop = start_fake()
    saved_env = {k: os.environ.get(k) for k in ("BRANDFETCH_CLIENT_ID", "LOGODEV_TOKEN")}
    saved_wait = run_test.PENDING_WAIT_S
    run_test.PENDING_WAIT_S = 2
    try:
        # the harness port is only known inside run_live; accept any 127.0.0.1 origin as "the page"
        Fake.harness_origin = "http://127.0.0.1:"
        for name, bf_key, expect_stop in (("A", BF_KEY, False), ("B", "wrong-client-id-789", True)):
            out = root / name
            out.mkdir()
            write_csv(out / "tickers.csv", tickers(), TICKER_COLS)
            os.environ["BRANDFETCH_CLIENT_ID"], os.environ["LOGODEV_TOKEN"] = bf_key, LD_KEY
            Fake.seen = {}
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run_test.main(["--out", str(out), "--bf-base", fake + "/bf", "--ld-base", fake + "/ld",
                                      "--ld-rate", "20", "--bf-rate", "3"])
            printed = buf.getvalue()
            no_secrets(out, printed, [bf_key, LD_KEY])
            latest = latest_results(read_csv(out / "results.csv"))
            summary = (out / "summary.md").read_text(encoding="utf-8")
            if not expect_stop:
                assert code == 0, (code, printed[-2000:])
                got = {k: v["verdict"] for k, v in latest.items()}
                wrong = {k: (got.get(k), v) for k, v in EXPECT.items() if got.get(k) != v}
                assert not wrong, f"run A verdicts (got, expected): {wrong}"
                extra = set(got) - set(EXPECT)
                assert not extra, f"unexpected loads: {extra}"
                assert latest[("005930", "logodev", "isin")]["tries"] == "2", "429 was not retried once"
                assert latest[("247540", "brandfetch", "ticker")]["tries"] == "2", "503 was not retried once"
                assert latest[("005930", "logodev", "domain")]["tries"] == "2", "202 was not rechecked"
                mix = {r["code"]: (f"{r['provider']}:{r['route']}" if r["provider"] else "", r["via_code"])
                       for r in read_csv(out / "mix.csv")}
                assert {c: m for c, (m, _) in mix.items()} == EXPECT_MIX, mix
                assert Fake.seen.get("bf:samsung.com") == 1 and Fake.seen.get("ld:samsung.com") == 2, \
                    f"a URL two tickers share was loaded more than once: {Fake.seen}"      # ld: 202, then the recheck
                assert latest[("005935", "logodev", "domain")]["tries"] == "2"
                assert mix["005937"][1] == "005930", "a preferred share with no logo did not take its common share's"
                assert "| **best mix** | 3 / 3 (100.0%) | 1 / 1 (100.0%) | – | 1 / 2 (50.0%) | 0 / 1 (0.0%) |" in summary, \
                    summary
                assert "| common share | 1 | 0 | 0 | 0 | 0 |" in summary, summary
                # 'fallback' (the placeholder image) is tried but not a hit
                assert "| brandfetch:isin | 1 / 2 (50.0%) | 0 / 1 (0.0%) | – | – | 0 / 1 (0.0%) | 0 / 0 |" in summary, summary
                assert "| brandfetch:domain | 2 / 2 (100.0%) | – | – | – | – | 0 / 0 |" in summary, summary
                probes = read_csv(out / "probes.csv")
                assert len(probes) == 18 and all(p["verdict"] == "hit" for p in probes if p["fallback"] ==
                                                 "404 (known company)"), probes
                assert {p["status"] for p in probes if p["fallback"] == "404"} == {"404"}, probes
                assert {p["status"] for p in probes if p["fallback"] == "default"} == {"200"}, probes
                # resume: a second run has nothing left to load
                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    run_test.main(["--out", str(out), "--bf-base", fake + "/bf", "--ld-base", fake + "/ld", "--dry-run",
                                   "--no-browser-check"])
                assert "· brandfetch: 18 loads planned (+9 probe loads) · 0 still to do" in buf2.getvalue(), buf2.getvalue()
                print(f"self-test A: {len(EXPECT)} loads with the expected verdicts · retries 429/503/202 · "
                      f"placeholder caught · shared URL loaded once · preferred share -> common share · summary and mix match · "
                      f"resume skips all")
            else:
                assert code == 2, (code, printed[-2000:])
                assert "brandfetch" in summary and "client_id_invalid_signature" in summary, summary
                assert not any(k[1] == "brandfetch" for k in latest), "Brandfetch kept loading after a refusal"
                assert sum(1 for k in latest if k[1] == "logodev") == 13, latest.keys()
                print("self-test B: wrong Brandfetch client ID -> Brandfetch stopped at the probe, logo.dev ran on")
        print("self-test passed (no provider was contacted; fake keys never written or printed)")
        return 0
    finally:
        run_test.PENDING_WAIT_S = saved_wait
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        stop()
