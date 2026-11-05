#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DART homepages for every Korean listed company in the live data (logo plan step 2).

  python3 tools/logos/dart_homepages.py --dry-run     # what it would fetch; no DART call
  python3 tools/logos/dart_homepages.py               # fetch (resumes: codes already fetched are skipped)

What it does
  1. Reads the live data.json (or --data PATH): every Korean stock (cls kr), ETFs and funds left out.
  2. DART corpCode.xml (one call, kept for the rest of the KST day outside the repository): stock code -> corp_code,
     by the exact stock code. A preferred share (005935) uses its issuer's common-share code (005930): same company,
     same corp_code, no extra call. A code DART does not list is written with status no_corp_code (no call).
  3. DART company.json once per corp_code for hm_url (the company's own homepage, as the company filed it).
  4. Writes tools/logos/kr_homepages.csv (a tool file, not one of the site's four data files):
       code, corp_code, via, name_en, corp_cls, hm_url (raw, as DART has it), domain (scheme, path, port and a
       leading www. removed), domain_ok (1 = usable to look a logo up by domain), domain_note (why not), fetched_at
       (KST), status (ok · empty · nodata · no_corp_code · mismatch · error).
     No Korean company names are written (name_en is DART's English name): tests/test_names.py reads every file
     under tools/ and two company names contain a syllable that test forbids there.

Limits (Jack, 2026-11-05) — DART's key is shared with the daily data run:
  - refuses to start, and stops between batches, inside 03:40-08:30 KST (the daily run uses DART then);
  - at most 1 call per second, in batches of 300 with a 30-second pause between;
  - at most 3,000 calls per KST day for this tool (checked before every call, corpCode.xml included; each call is
    booked to the KST day it is made), counted across runs in a ledger outside the repository
    (~/.cache/baepsae-logos/dart_calls.json) and, since a cloud container starts empty, never below what the
    committed CSV shows was fetched today;
  - stops at once on DART status 020 (daily limit) or a key error (010 · 011 · 012 · 901), and after 5 network errors
    in a row. Progress is saved after every batch and on any stop; a rerun continues.
The key comes only from DART_API_KEY and never appears in output (every printed line goes through a masker).
"""
import argparse
import collections
import csv
import io
import json
import os
import pathlib
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from logo_ids import (KST, Masker, common_code, has_homepage, in_quiet_window, is_krx_code,  # noqa: E402
                      judge_homepage, now_kst, refuse_in_quiet_window)

DATA_URL = "https://jacksungjinlee.github.io/baepsae/data.json"
DART_BASE = "https://opendart.fss.or.kr/api/"
OUT = HERE / "kr_homepages.csv"
CACHE_DIR = pathlib.Path(os.environ.get("BAEPSAE_LOGO_CACHE", pathlib.Path.home() / ".cache" / "baepsae-logos"))
COLS = ["code", "corp_code", "via", "name_en", "corp_cls", "hm_url", "domain", "domain_ok", "domain_note",
        "fetched_at", "status"]
FINAL = ("ok", "empty", "nodata", "mismatch")           # a rerun skips these; error and no_corp_code are tried again
DAILY_CAP = 3000                                        # DART calls per KST day for this tool (Jack, 2026-11-05)
BATCH = 300
PAUSE_S = 30.0
MIN_INTERVAL_S = 1.05                                   # ≤ 1 call per second, with a little room
NET_STOP = 5                                            # network errors in a row -> stop
FATAL = {"010": "unregistered key", "011": "key not usable", "012": "IP not allowed", "020": "daily limit reached",
         "901": "key expired"}
MUST = ("005930", "000660", "005380")


def log(*parts, mask=None):
    text = " ".join(str(p) for p in parts)
    print(mask(text) if mask else text, flush=True)


# ── inputs ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def kr_companies(data):
    """Korean stocks in data.json, ETFs and funds left out: [{code, cap}]. Refuses data that is plainly incomplete."""
    stocks = data.get("stocks") or []
    rows = []
    for s in stocks:
        if s.get("cls") != "kr" or s.get("etf"):
            continue
        code = str(s.get("t") or "").strip().upper()
        if not is_krx_code(code):
            raise SystemExit(f"!! data.json has a Korean stock with a code that is not a KRX code: {code!r}")
        rows.append({"code": code})
    codes = {r["code"] for r in rows}
    missing = [c for c in MUST if c not in codes]
    if missing or len(rows) < 2000:
        raise SystemExit(f"!! data.json looks incomplete: {len(rows):,} Korean stocks, missing {missing}")
    return rows


def parse_corp_codes(xml_bytes):
    """CORPCODE.xml -> {stock_code: corp_code} for listed companies (stock_code is 6 characters)."""
    root = ET.fromstring(xml_bytes)
    m = {}
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip().upper()
        cc = (el.findtext("corp_code") or "").strip()
        if len(sc) == 6 and cc:
            m[sc] = cc
    return m


def plan(companies, corp_map):
    """Each company -> (corp_code, via). via = the common-share code a preferred share was mapped through, else ''.
    Exact codes only: the company's own code, or (preferred share) its issuer's common-share code."""
    out = {}
    for c in companies:
        code = c["code"]
        if code in corp_map:
            out[code] = (corp_map[code], "")
            continue
        cc = common_code(code)
        if cc != code and cc in corp_map:
            out[code] = (corp_map[cc], cc)
        else:
            out[code] = ("", "")
    return out


# ── the CSV ────────────────────────────────────────────────────────────────────────────────────────────────────────

def read_rows(path):
    if not pathlib.Path(path).exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def write_rows(path, rows):
    tmp = pathlib.Path(str(path) + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for code in sorted(rows):
            w.writerow(rows[code])
    os.replace(tmp, path)


def apply_domains(rows):
    """Fill domain · domain_ok · domain_note from hm_url, then mark a domain that two or more different companies
    (corp_codes) list as not usable: a logo looked up by it could be the other company's or the group's."""
    for r in rows.values():
        if r.get("status") in ("ok", "empty"):               # DART answered: ok when hm_url holds a homepage at all
            r["status"] = "ok" if has_homepage(r.get("hm_url")) else "empty"
        if r.get("status") in ("ok", "empty", "mismatch"):
            dom, ok, note = judge_homepage(r.get("hm_url"))
            if r["status"] == "mismatch":
                ok, note = False, "DART answered for another stock code"
        else:
            dom, ok, note = "", False, {"nodata": "DART has no company record", "no_corp_code": "not in DART's list",
                                        "error": "not fetched yet"}.get(r.get("status"), "")
        r["domain"], r["domain_ok"], r["domain_note"] = dom, "1" if ok else "0", note
    corps = collections.defaultdict(set)
    for r in rows.values():
        if r["domain_ok"] == "1":
            corps[r["domain"]].add(r["corp_code"])
    for r in rows.values():
        n = len(corps.get(r["domain"], ())) if r["domain_ok"] == "1" else 0
        if n > 1:
            r["domain_ok"], r["domain_note"] = "0", f"same domain as {n - 1} other compan{'y' if n == 2 else 'ies'}"
    return rows


# ── DART calls ─────────────────────────────────────────────────────────────────────────────────────────────────────

class Ledger:
    """DART calls this tool made per KST day (all runs), in a file outside the repository. A cloud container is thrown
    away after its session, so main() also raises today's count to what the committed CSV shows (calls_in_csv)."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        try:
            self.days = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.days = {}

    def used(self, day):
        return int(self.days.get(day, 0))

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.days, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, day, n=1):
        self.days[day] = self.used(day) + n
        self._save()

    def at_least(self, day, n):
        if n > self.used(day):
            self.days[day] = n
            self._save()


def calls_in_csv(rows, day):
    """DART calls the CSV proves were made on `day` (KST): one company.json per distinct corp_code fetched that day,
    plus the corpCode.xml call. An undercount (network errors leave no row), but it survives a new container."""
    corps = {r.get("corp_code") for r in rows.values() if str(r.get("fetched_at") or "").startswith(day)
             and r.get("corp_code")}
    return len(corps) + 1 if corps else 0


def kst_day(when):
    return when.astimezone(KST).date().isoformat()


def classify_company(want, j):
    """One company.json answer -> the row fields it sets (pure). want = the stock code DART lists for this corp_code
    (the common share's); j is the parsed JSON."""
    st = str(j.get("status"))
    if st == "000":
        got = str(j.get("stock_code") or "").strip().upper()
        hm = str(j.get("hm_url") or "").strip()
        status = "mismatch" if got != str(want).upper() else ("ok" if has_homepage(hm) else "empty")
        return {"status": status, "hm_url": hm, "name_en": str(j.get("corp_name_eng") or "").strip(),
                "corp_cls": str(j.get("corp_cls") or "").strip()}
    if st == "013":
        return {"status": "nodata", "hm_url": "", "name_en": "", "corp_cls": ""}
    return {"status": "error", "hm_url": "", "name_en": "", "corp_cls": "", "_dart_status": st,
            "_message": str(j.get("message") or "")}


def fetch_all(todo, call, ledger, budget, mask, clock=time.monotonic, sleep=time.sleep, wall=now_kst,
              batch=BATCH, pause=PAUSE_S, interval=MIN_INTERVAL_S, on_batch=None):
    """Call company.json once per corp_code in todo [(corp_code, want_stock_code)], paced. call(corp_code) returns the
    parsed JSON, or raises on a network error. Every call is booked to the KST day it is made (a run may cross
    midnight). Returns (results {corp_code: fields incl. 'at' = fetch time}, counts, stop_reason or None)."""
    results, counts = {}, collections.Counter()
    stop, net_streak, last = None, 0, None
    made = 0
    for i, (corp, want) in enumerate(todo):
        if made >= budget:
            stop = f"call budget reached ({made:,} this run · {ledger.used(kst_day(wall())):,} today, cap {DAILY_CAP:,})"
            break
        if i and i % batch == 0:
            if on_batch:
                on_batch(results, counts, i)
            log(f"· batch done: {i:,} / {len(todo):,} companies · pausing {pause:.0f}s")
            sleep(pause)
        if in_quiet_window(wall()):
            stop = "reached 03:40 KST (the daily data run's DART window)"
            break
        if last is not None:
            wait = interval - (clock() - last)
            if wait > 0:
                sleep(wait)
        day = kst_day(wall())
        if ledger.used(day) >= DAILY_CAP:
            stop = f"today's cap of {DAILY_CAP:,} DART calls is used ({day} KST)"
            break
        last = clock()
        made += 1
        ledger.add(day)
        at = wall().astimezone(KST).isoformat(timespec="seconds")
        try:
            j = call(corp)
        except Exception as e:                               # noqa: BLE001 — network: counted, masked, maybe stop
            net_streak += 1
            counts["network error"] += 1
            log(f"  !! {corp}: {type(e).__name__}: {e}", mask=mask)
            if net_streak >= NET_STOP:
                stop = f"{NET_STOP} network errors in a row"
                break
            continue
        net_streak = 0
        st = str(j.get("status"))
        counts[f"status {st}"] += 1
        if st in FATAL:
            stop = f"DART status {st} ({FATAL[st]}): {j.get('message')}"
            break
        res = classify_company(want, j)
        if res["status"] == "error":
            log(f"  !! {corp}: DART status {st} {res.get('_message')!r}", mask=mask)
        if res["status"] == "mismatch":
            log(f"  !! {corp}: DART answered for stock code {j.get('stock_code')!r}, expected {want!r}")
        res["at"] = at
        results[corp] = res
    return results, counts, stop


def dart_session(key):
    import requests
    s = requests.Session()

    def get(endpoint, params, timeout=25):
        r = s.get(DART_BASE + endpoint, params={"crtfc_key": key, **params}, timeout=timeout)
        return r

    return get


def load_corp_map(get, ledger, day, mask):
    """corpCode.xml, once per KST day (kept in the cache folder outside the repository)."""
    cache = CACHE_DIR / f"corpcode-{day}.json"
    if cache.exists():
        m = json.loads(cache.read_text(encoding="utf-8"))
        log(f"· DART corp codes: {len(m):,} (kept from earlier today, {cache})")
        return m
    if ledger.used(day) >= DAILY_CAP:
        raise SystemExit(f"!! today's cap of {DAILY_CAP:,} DART calls is used ({day} KST); run again tomorrow")
    ledger.add(day)
    r = get("corpCode.xml", {}, timeout=90)
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        try:
            j = r.json()
        except ValueError:
            raise SystemExit(mask(f"!! corpCode.xml: not a zip and not JSON: HTTP {r.status_code} {r.text[:120]!r}"))
        raise SystemExit(mask(f"!! corpCode.xml: DART status {j.get('status')} {j.get('message')!r}"))
    m = parse_corp_codes(zf.read(zf.namelist()[0]))
    if len(m) < 2000:
        raise SystemExit(f"!! corpCode.xml has only {len(m):,} listed companies")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(m, sort_keys=True), encoding="utf-8")
    log(f"· DART corp codes: {len(m):,} listed companies (corpCode.xml, 1 call)")
    return m


def report(rows, companies):
    want = {c["code"] for c in companies}
    rs = [r for c, r in rows.items() if c in want]
    st = collections.Counter(r["status"] for r in rs)
    usable = sum(1 for r in rs if r.get("domain_ok") == "1")
    notes = collections.Counter(r["domain_note"] for r in rs if r.get("domain_ok") != "1")
    fetched = sum(st[k] for k in FINAL)
    lines = [f"· companies {len(rs):,} · fetched {fetched:,} · with homepage {st['ok'] + st['mismatch']:,} · "
             f"empty {st['empty']:,} · no DART record {st['nodata']:,} · not in DART's list {st['no_corp_code']:,} · "
             f"error {st['error']:,} · mismatch {st['mismatch']:,}",
             f"· usable domain {usable:,} / {len(rs):,} · not usable: "
             + ", ".join(f"{k} {v:,}" for k, v in notes.most_common())]
    return lines, st, usable, fetched


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=DATA_URL, help="data.json URL or path (default: the live site)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--max-calls", type=int, default=DAILY_CAP, help=f"calls this run (never above today's {DAILY_CAP:,})")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; no DART call (corpCode.xml only if kept)")
    ap.add_argument("--reclassify", action="store_true",
                    help="no DART call: apply the domain rules again to the saved CSV (after a rule change) and report")
    a = ap.parse_args(argv)

    if a.reclassify:
        rows = read_rows(a.out)
        if not rows:
            raise SystemExit(f"!! {a.out} is empty or missing")
        apply_domains(rows)
        write_rows(a.out, rows)
        lines, _, _, _ = report(rows, [{"code": c} for c in rows])
        for line in lines:
            log(line)
        log(f"wrote {a.out} (no DART call)")
        return 0

    started = refuse_in_quiet_window()
    day = started.date().isoformat()
    key = os.environ.get("DART_API_KEY", "").strip()
    mask = Masker(key)
    if not key and not a.dry_run:
        raise SystemExit("!! DART_API_KEY is not set")

    if a.data.startswith(("http://", "https://")):
        import requests
        resp = requests.get(a.data, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    else:
        data = json.loads(pathlib.Path(a.data).read_text(encoding="utf-8"))
    companies = kr_companies(data)
    log(f"· data.json asOf {data.get('asOf')} · pxDate {data.get('pxDate')} · Korean companies (no ETFs) {len(companies):,}")

    rows = read_rows(a.out)
    ledger = Ledger(CACHE_DIR / "dart_calls.json")
    ledger.at_least(day, calls_in_csv(rows, day))           # a fresh container has no ledger; the CSV is committed
    log(f"· DART calls by this tool today ({day} KST) before this run: {ledger.used(day):,} / {DAILY_CAP:,}")
    if a.dry_run:
        cache = CACHE_DIR / f"corpcode-{day}.json"
        corp_map = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
    else:
        get = dart_session(key)
        corp_map = load_corp_map(get, ledger, day, mask)

    if corp_map is None:
        done = sum(1 for c in companies if rows.get(c["code"], {}).get("status") in FINAL)
        log(f"· dry run: {done:,} already fetched · up to {len(companies) - done:,} to fetch (corp codes not loaded "
            "yet, so preferred shares sharing a call are not counted) · 1 corpCode.xml call")
        return 0
    mapping = plan(companies, corp_map)
    stock_of = {cc: sc for sc, cc in corp_map.items()}       # corp_code -> the stock code DART lists (common share)
    codes_of = collections.OrderedDict()                      # corp_code -> our codes to fetch it for
    for c in companies:
        corp, via = mapping[c["code"]]
        if not corp:
            rows[c["code"]] = {"code": c["code"], "corp_code": "", "via": "", "name_en": "", "corp_cls": "",
                               "hm_url": "", "fetched_at": "", "status": "no_corp_code"}
            continue
        old = rows.get(c["code"])
        if old and old.get("status") in FINAL and old.get("corp_code") == corp:
            continue
        codes_of.setdefault(corp, []).append(c["code"])
    todo = [(corp, stock_of[corp]) for corp in codes_of]
    left = DAILY_CAP - ledger.used(day)
    budget = max(0, min(a.max_calls, left))
    n_map = sum(1 for c in companies if mapping[c["code"]][0])
    log(f"· mapped to a DART corp_code: {n_map:,} / {len(companies):,} (preferred shares through their common share: "
        f"{sum(1 for c in companies if mapping[c['code']][1]):,}) · to fetch now: {len(todo):,} companies · "
        f"budget {budget:,} calls")
    if a.dry_run:
        return 0
    if len(todo) > budget:
        log(f"!! {len(todo):,} to fetch but only {budget:,} calls left today: fetching the first {budget:,}, rerun tomorrow")

    def merge(results):
        for corp, res in results.items():
            for code in codes_of[corp]:
                rows[code] = {"code": code, "corp_code": corp, "via": mapping[code][1], "name_en": res["name_en"],
                              "corp_cls": res["corp_cls"], "hm_url": res["hm_url"], "fetched_at": res["at"],
                              "status": res["status"]}
        apply_domains(rows)
        write_rows(a.out, rows)

    def on_batch(results, counts, i):
        merge(results)
        today = now_kst().date().isoformat()
        log(f"· saved {a.out} · calls today {ledger.used(today):,} / {DAILY_CAP:,} · "
            + ", ".join(f"{k} {v:,}" for k, v in sorted(counts.items())))

    t0 = time.monotonic()
    results, counts, stop = fetch_all(
        todo, lambda corp: get("company.json", {"corp_code": corp}).json(), ledger, budget, mask, on_batch=on_batch)
    merge(results)
    calls = sum(counts.values())                              # company.json calls made by this run
    if stop:
        log(f"!! stopped: {stop}")
    lines, st, usable, fetched = report(rows, companies)
    for line in lines:
        log(line)
    today = now_kst().date().isoformat()
    log(f"· 홈페이지 수집: {st['ok'] + st['mismatch']:,} / {len(companies):,} · 호출 {calls:,}회 "
        f"(오늘 이 도구 {ledger.used(today):,}회) · {(time.monotonic() - t0) / 60:.1f}분 · "
        + ", ".join(f"{k} {v:,}" for k, v in sorted(counts.items())))
    log(f"wrote {a.out}")
    return 2 if stop else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:                                   # noqa: BLE001 — print masked, then fail
        import traceback
        print(Masker(os.environ.get("DART_API_KEY", ""))(traceback.format_exc()), file=sys.stderr)
        sys.exit(1)
