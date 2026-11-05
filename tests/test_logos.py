# -*- coding: utf-8 -*-
"""Logo plan (tools/logos/): exact identifiers, the DART homepage tool, and what the logo picker builds on.

No network and no logo provider: ISIN check digit and the exact short-code rule, homepage -> domain on the messy values
DART and KRX hold, platform hosts that are never a company's domain, the DART quiet window (03:40-08:30 KST), the
DART loop's pacing, batches, call budget and stops (status 020, key errors, network errors) against a fake DART, the
seeded sample (same seed -> same sample), the provider URL formats, key checks, and every company's exact identifiers
from data.json + the KRX listing + the DART homepages (logo_sources.py). The coverage test page that used to be tested
here was removed on 2026-11-05 (Jack); the logo picker's own tests are in tests/test_logo_review.py.
"""
import datetime as dt
import pathlib
import sys
from zoneinfo import ZoneInfo

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))

import dart_homepages as dh  # noqa: E402
import logo_ids as li  # noqa: E402
import logo_sources as lsrc  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
UTC = dt.timezone.utc


# ── ISIN (from the v19.1 Part L logo test) ──

@pytest.mark.parametrize("code,isin", [("005930", "KR7005930003"), ("000660", "KR7000660001"),
                                       ("005380", "KR7005380001"), ("035420", "KR7035420009"),
                                       ("373220", "KR7373220003"), ("069500", "KR7069500007"),
                                       ("0126Z0", "KR70126Z0002")])
def test_kr_isin_from_code_matches_the_krx_listing(code, isin):
    assert li.kr_isin_from_code(code) == isin
    assert li.isin_valid(isin)


@pytest.mark.parametrize("isin", ["US0378331005", "KR7005931001", "KR7005382007", "KR700680K019", "KYG5307W1015",
                                  "HK0000307485", "KR8840120008", "USU652221081", "us0378331005"])
def test_real_isins_pass_the_check_digit(isin):
    assert li.isin_valid(isin)


@pytest.mark.parametrize("isin", ["KR7005930004", "US0378331006", "KR700593000", "KR70059300031", "", None,
                                  "1R7005930003", "KR7-05930003", "KR700593000A"])
def test_wrong_isins_fail(isin):
    assert not li.isin_valid(isin)


@pytest.mark.parametrize("code", ["005935", "005387", "00680K", "900140", "950160", "AAPL", "12345", "", None])
def test_no_isin_is_derived_where_the_rule_does_not_hold(code):
    """Preferred shares (005935 -> KR7005931001, not KR7005935...) and foreign issuers (9xxxxx) have other ISINs."""
    assert li.kr_isin_from_code(code) is None


def test_check_digit_rejects_a_bad_body():
    for body in ("KR70059300", "1R700593000", "KR7 0593000", "가R700593000"):
        with pytest.raises(ValueError):
            li.isin_check_digit(body)


def test_common_code_and_common_share():
    assert li.common_code("005935") == "005930" and li.common_code("005387") == "005380"
    assert li.common_code("00680K") == "006800" and li.common_code("005930") == "005930"
    assert li.common_code("AAPL") == "AAPL"
    assert li.is_common_share("005930") and li.is_common_share("0126Z0")
    assert not li.is_common_share("005935") and not li.is_common_share("00680K") and not li.is_common_share("AAPL")


# ── homepage -> domain ──

@pytest.mark.parametrize("raw,domain", [
    ("http://www.samsung.com/sec", "samsung.com"), ("http://https://ks-industry.co.kr/", "ks-industry.co.kr"),
    ("http:///www.nota.ai", "nota.ai"), ("http:// http://www.megamd.co.kr", "megamd.co.kr"), ("RAON.io", "raon.io"),
    ("http://https://www.doosanenerbility.com/kr", "doosanenerbility.com"), ("http://kr.Example.com:8080/x?y", "kr.example.com"),
    ("https://www.hyundai.com", "hyundai.com"), ("http://www,cuckoo.co.kr", ""), ("", ""), (None, ""), ("http://", ""),
    ("localhost", ""), ("http://dsol.co.kr/bbs/board.php?bo_table=pds", "dsol.co.kr"), ("http//www.x-y.co.kr", "x-y.co.kr"),
    ("httpbin.org", "httpbin.org"), ("HTTPS://WWW.LGES.CO.KR/", "lges.co.kr"),
    # DART hm_url values usually have no scheme and often a path
    ("www.skhynix.com", "skhynix.com"), ("www.lgchem.com/kr/main", "lgchem.com"), ("  www.posco.co.kr  ", "posco.co.kr"),
    ("http://123.45.67.89/index.html", ""), ("www.x.co.kr#top", "x.co.kr"), ("user@www.x.co.kr", "x.co.kr"),
])
def test_homepage_domain(raw, domain):
    assert li.homepage_domain(raw) == domain


def test_platform_hosts_are_not_company_domains():
    for d in ("blog.naver.com", "cafe.naver.com", "m.blog.naver.com", "smartstore.naver.com", "pf.kakao.com",
              "shop.cafe24.com", "facebook.com", "instagram.com", "linktr.ee", "sites.google.com", "x.modoo.at",
              "kind.krx.co.kr", "dart.fss.or.kr", "band.us", "x.blogspot.com", "youtube.com"):
        assert li.is_shared_host(d), d
    for d in ("naver.com", "cafe24.com", "samsung.com", "navercorp.com", "kakaocorp.com", "linktree.com"):
        assert not li.is_shared_host(d), d


@pytest.mark.parametrize("raw,want", [
    ("www.samsung.com/sec", ("samsung.com", True, "")),
    ("https://blog.naver.com/somecompany", ("blog.naver.com", False, "platform host")),
    ("http://cafe.naver.com/x", ("cafe.naver.com", False, "platform host")),
    ("https://www.facebook.com/x", ("facebook.com", False, "platform host")),
    ("https://www.instagram.com/x", ("instagram.com", False, "platform host")),
    ("https://linktr.ee/x", ("linktr.ee", False, "platform host")),
    ("http://www,cuckoo.co.kr", ("", False, "not a host name")),
    ("", ("", False, "no homepage")), (None, ("", False, "no homepage")),
    ("-", ("", False, "no homepage")), (" -- ", ("", False, "no homepage")), (".", ("", False, "no homepage")),
    ("없음", ("", False, "no homepage")), ("N/A", ("", False, "no homepage")), ("none", ("", False, "no homepage")),
    ("www.한글.kr", ("xn--bj0bj06e.kr", True, "")),                          # a Korean-script domain still works
])
def test_judge_homepage(raw, want):
    assert li.judge_homepage(raw) == want


def test_dart_placeholder_dash_is_no_homepage_even_in_rows_saved_before_the_rule():
    assert not li.has_homepage("-") and not li.has_homepage("") and li.has_homepage("www.x.co.kr")
    assert dh.classify_company("005930", {"status": "000", "stock_code": "005930", "hm_url": "-"})["status"] == "empty"
    rows = {"009970": {"code": "009970", "corp_code": "A", "status": "ok", "hm_url": "-"}}
    dh.apply_domains(rows)
    assert rows["009970"]["status"] == "empty" and rows["009970"]["domain_note"] == "no homepage"
    assert rows["009970"]["hm_url"] == "-"                                   # the raw value stays


def test_a_domain_two_companies_list_is_not_usable_and_the_raw_value_stays():
    rows = {
        "000001": {"code": "000001", "corp_code": "A", "status": "ok", "hm_url": "http://www.group.co.kr/a"},
        "000002": {"code": "000002", "corp_code": "B", "status": "ok", "hm_url": "group.co.kr"},
        "000010": {"code": "000010", "corp_code": "C", "status": "ok", "hm_url": "www.own.co.kr"},
        "000015": {"code": "000015", "corp_code": "C", "status": "ok", "hm_url": "www.own.co.kr", "via": "000010"},
        "000020": {"code": "000020", "corp_code": "D", "status": "ok", "hm_url": "https://blog.naver.com/d"},
        "000030": {"code": "000030", "corp_code": "E", "status": "empty", "hm_url": ""},
        "000040": {"code": "000040", "corp_code": "", "status": "no_corp_code", "hm_url": ""},
        "000050": {"code": "000050", "corp_code": "F", "status": "mismatch", "hm_url": "www.f.co.kr"},
    }
    dh.apply_domains(rows)
    assert [rows[c]["domain_ok"] for c in ("000001", "000002")] == ["0", "0"]
    assert rows["000001"]["domain"] == "group.co.kr" and "other company" in rows["000001"]["domain_note"]
    assert rows["000001"]["hm_url"] == "http://www.group.co.kr/a"                  # the raw value is kept
    assert rows["000010"]["domain_ok"] == rows["000015"]["domain_ok"] == "1"     # a preferred share is the same company
    assert (rows["000020"]["domain_ok"], rows["000020"]["domain_note"]) == ("0", "platform host")
    assert (rows["000030"]["domain_ok"], rows["000030"]["domain_note"]) == ("0", "no homepage")
    assert (rows["000040"]["domain_ok"], rows["000040"]["domain_note"]) == ("0", "not in DART's list")
    assert rows["000050"]["domain_ok"] == "0" and rows["000050"]["domain"] == "f.co.kr"


# ── DART: mapping, answers, the loop ──

def test_plan_maps_by_exact_stock_code_and_preferred_shares_through_their_common_share():
    corp_map = {"005930": "00126380", "005380": "00164742", "0126Z0": "01234567"}
    got = dh.plan([{"code": c} for c in ("005930", "005935", "005387", "0126Z0", "123450", "123455")], corp_map)
    assert got == {"005930": ("00126380", ""), "005935": ("00126380", "005930"), "005387": ("00164742", "005380"),
                   "0126Z0": ("01234567", ""), "123450": ("", ""), "123455": ("", "")}


def test_parse_corp_codes_keeps_listed_companies_only():
    xml = ("<result><list><corp_code>00126380</corp_code><corp_name>x</corp_name><stock_code>005930</stock_code></list>"
           "<list><corp_code>00999999</corp_code><corp_name>y</corp_name><stock_code> </stock_code></list>"
           "<list><corp_code>01234567</corp_code><stock_code>0126z0</stock_code></list></result>").encode()
    assert dh.parse_corp_codes(xml) == {"005930": "00126380", "0126Z0": "01234567"}


def test_classify_company():
    ok = {"status": "000", "stock_code": "005930", "hm_url": "www.samsung.com/sec", "corp_name_eng": "SAMSUNG",
          "corp_cls": "Y"}
    assert dh.classify_company("005930", ok) == {"status": "ok", "hm_url": "www.samsung.com/sec", "name_en": "SAMSUNG",
                                                 "corp_cls": "Y"}
    assert dh.classify_company("005930", dict(ok, hm_url=" "))["status"] == "empty"
    assert dh.classify_company("000660", ok)["status"] == "mismatch"
    assert dh.classify_company("005930", {"status": "013", "message": "no data"})["status"] == "nodata"
    assert dh.classify_company("005930", {"status": "800", "message": "maintenance"})["status"] == "error"


class FakeDart:
    def __init__(self, answers, clock):
        self.answers, self.clock, self.calls = answers, clock, []

    def __call__(self, corp):
        self.calls.append((corp, self.clock.t))
        a = self.answers.get(corp, {"status": "000", "stock_code": "S" + corp, "hm_url": f"www.{corp}.co.kr"})
        if isinstance(a, Exception):
            raise a
        return a


class Clock:
    def __init__(self, start=None):
        self.t = 0.0
        self.wall0 = start or dt.datetime(2026, 11, 5, 11, 0, tzinfo=KST)

    def mono(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def wall(self):
        return self.wall0 + dt.timedelta(seconds=self.t)


def run_fake(tmp_path, n=10, answers=None, budget=3000, batch=4, start=None, used=0):
    clock = Clock(start)
    fake = FakeDart(answers or {}, clock)
    ledger = dh.Ledger(tmp_path / "calls.json")
    if used:
        ledger.add("2026-11-05", used)
    todo = [(f"C{i:03d}", f"SC{i:03d}") for i in range(n)]
    for corp, want in todo:
        fake.answers.setdefault(corp, {"status": "000", "stock_code": want, "hm_url": f"www.{corp}.co.kr"})
    res, counts, stop = dh.fetch_all(todo, fake, ledger, budget, li.Masker("SECRETKEY"),
                                     clock=clock.mono, sleep=clock.sleep, wall=clock.wall, batch=batch, pause=30)
    return fake, ledger, res, counts, stop


def test_dart_loop_stops_at_the_daily_cap_counted_across_runs(tmp_path):
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=10, used=dh.DAILY_CAP - 3)
    assert len(fake.calls) == 3 and "cap" in stop and ledger.used("2026-11-05") == dh.DAILY_CAP


def test_dart_calls_are_booked_to_the_kst_day_they_are_made_and_stamped_when_fetched(tmp_path):
    start = dt.datetime(2026, 11, 5, 23, 59, 57, tzinfo=KST)
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=6, start=start)
    assert stop is None and ledger.used("2026-11-05") == 3 and ledger.used("2026-11-06") == 3
    stamps = [res[f"C{i:03d}"]["at"] for i in range(6)]
    assert stamps[0] == "2026-11-05T23:59:57+09:00" and stamps[-1].startswith("2026-11-06T00:00:")   # after a pause


def test_a_fresh_container_counts_todays_calls_from_the_committed_csv(tmp_path):
    rows = {"005930": {"corp_code": "A", "fetched_at": "2026-11-05T11:00:00+09:00"},
            "005935": {"corp_code": "A", "fetched_at": "2026-11-05T11:00:00+09:00"},      # same company, one call
            "000660": {"corp_code": "B", "fetched_at": "2026-11-05T11:00:01+09:00"},
            "005380": {"corp_code": "C", "fetched_at": "2026-11-04T11:00:00+09:00"},
            "123450": {"corp_code": "", "fetched_at": ""}}
    assert dh.calls_in_csv(rows, "2026-11-05") == 3 and dh.calls_in_csv(rows, "2026-11-07") == 0   # + corpCode.xml
    led = dh.Ledger(tmp_path / "c.json")
    led.at_least("2026-11-05", 3)
    led.at_least("2026-11-05", 1)
    assert dh.Ledger(tmp_path / "c.json").used("2026-11-05") == 3


def test_corp_code_list_is_not_fetched_when_the_cap_is_used(tmp_path, monkeypatch):
    monkeypatch.setattr(dh, "CACHE_DIR", tmp_path)
    led = dh.Ledger(tmp_path / "c.json")
    led.add("2026-11-05", dh.DAILY_CAP)
    called = []
    with pytest.raises(SystemExit):
        dh.load_corp_map(lambda *a, **k: called.append(a), led, "2026-11-05", li.Masker("K" * 8))
    assert not called and led.used("2026-11-05") == dh.DAILY_CAP


def test_dart_loop_paces_one_call_per_second_and_pauses_between_batches(tmp_path):
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=10, batch=4)
    assert stop is None and len(res) == 10 and all(r["status"] == "ok" for r in res.values())
    times = [t for _, t in fake.calls]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(g >= 1.0 for g in gaps), gaps                         # never more than 1 call per second
    assert gaps[3] >= 29.99 and gaps[7] >= 29.99 and gaps[0] < 2     # a 30 s pause after each batch of 4
    assert ledger.used("2026-11-05") == 10 and counts["status 000"] == 10


def test_dart_loop_stops_at_once_on_status_020_and_on_key_errors(tmp_path):
    for st in ("020", "010", "011", "012", "901"):
        fake, ledger, res, counts, stop = run_fake(tmp_path / st, n=10, answers={"C003": {"status": st, "message": "m"}})
        assert len(fake.calls) == 4 and len(res) == 3 and stop and f"status {st}" in stop, (st, stop)


def test_dart_loop_stops_after_repeated_network_errors_and_masks_the_key(tmp_path, capsys):
    err = ConnectionError("HTTPSConnectionPool: /api/company.json?crtfc_key=SECRETKEY&corp_code=x")
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=20, answers={f"C{i:03d}": err for i in range(2, 20)})
    assert stop == f"{dh.NET_STOP} network errors in a row" and len(fake.calls) == 2 + dh.NET_STOP
    out = capsys.readouterr().out
    assert "SECRETKEY" not in out and "crtfc_key=***" in out
    assert ledger.used("2026-11-05") == 2 + dh.NET_STOP              # a failed call still counts against the cap


def test_one_network_error_does_not_stop_and_the_company_is_left_for_a_rerun(tmp_path):
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=5, answers={"C001": TimeoutError("slow")})
    assert stop is None and "C001" not in res and len(res) == 4 and counts["network error"] == 1


def test_dart_loop_respects_the_call_budget(tmp_path):
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=10, budget=6)
    assert len(fake.calls) == 6 and "budget" in stop


def test_dart_loop_stops_when_the_quiet_window_begins(tmp_path):
    start = dt.datetime(2026, 11, 5, 3, 39, 50, tzinfo=KST)          # 10 s before 03:40 KST
    fake, ledger, res, counts, stop = run_fake(tmp_path, n=40, batch=100, start=start)
    assert "03:40" in stop and 5 <= len(fake.calls) <= 11


def test_the_ledger_adds_up_across_runs(tmp_path):
    led = dh.Ledger(tmp_path / "c.json")
    led.add("2026-11-05", 2)
    assert dh.Ledger(tmp_path / "c.json").used("2026-11-05") == 2 and led.used("2026-11-06") == 0


def test_kr_companies_leaves_out_etfs_and_refuses_incomplete_data():
    stocks = [{"t": f"{i:06d}", "cls": "kr"} for i in range(10, 2500)] + \
             [{"t": c, "cls": "kr"} for c in dh.MUST] + [{"t": "069500", "cls": "kr", "etf": True},
                                                          {"t": "AAPL", "cls": "us"}]
    rows = dh.kr_companies({"stocks": stocks})
    codes = {r["code"] for r in rows}
    assert "069500" not in codes and "AAPL" not in codes and set(dh.MUST) <= codes
    with pytest.raises(SystemExit):
        dh.kr_companies({"stocks": stocks[:100]})


def test_the_csv_round_trips_and_has_no_korean_names(tmp_path):
    rows = {"005930": {"code": "005930", "corp_code": "00126380", "via": "", "name_en": "SAMSUNG", "corp_cls": "Y",
                       "hm_url": "www.samsung.com/sec", "fetched_at": "2026-11-05T11:00:00+09:00", "status": "ok"}}
    dh.apply_domains(rows)
    dh.write_rows(tmp_path / "x.csv", rows)
    back = dh.read_rows(tmp_path / "x.csv")
    assert back["005930"]["domain"] == "samsung.com" and back["005930"]["domain_ok"] == "1"
    assert list(back["005930"]) == dh.COLS and "name" not in dh.COLS


# ── the DART quiet window ──

@pytest.mark.parametrize("hh,mm,ss,quiet", [(3, 39, 59, False), (3, 40, 0, True), (6, 0, 0, True), (8, 29, 59, True),
                                            (8, 30, 0, False), (10, 41, 0, False), (0, 0, 0, False), (23, 59, 0, False)])
def test_quiet_window_in_kst(hh, mm, ss, quiet):
    assert li.in_quiet_window(dt.datetime(2026, 11, 5, hh, mm, ss, tzinfo=KST)) is quiet


def test_quiet_window_converts_utc_and_refuses_a_naive_time():
    assert li.in_quiet_window(dt.datetime(2026, 11, 4, 19, 0, tzinfo=UTC))          # 04:00 KST
    assert not li.in_quiet_window(dt.datetime(2026, 11, 5, 1, 41, tzinfo=UTC))      # 10:41 KST
    with pytest.raises(ValueError):
        li.in_quiet_window(dt.datetime(2026, 11, 5, 5, 0))
    with pytest.raises(SystemExit):
        li.refuse_in_quiet_window(dt.datetime(2026, 11, 5, 7, 0, tzinfo=KST))
    assert li.refuse_in_quiet_window(dt.datetime(2026, 11, 5, 1, 41, tzinfo=UTC)).hour == 10


def test_the_tool_refuses_to_start_in_the_quiet_window(monkeypatch):
    monkeypatch.setattr(dh, "refuse_in_quiet_window", lambda: li.refuse_in_quiet_window(
        dt.datetime(2026, 11, 5, 5, 0, tzinfo=KST)))
    monkeypatch.setenv("DART_API_KEY", "x" * 40)
    with pytest.raises(SystemExit) as e:
        dh.main(["--data", "/nonexistent.json"])
    assert "03:40-08:30" in str(e.value)


# ── sample for the coverage test page ──

def companies(n_kr=2400, n_us=740):
    kr = [{"code": f"{i:05d}0", "side": "kr", "cap": 500.0 / i} for i in range(1, n_kr + 1)]
    us = [{"code": f"US{i}", "side": "us", "cap": 5000.0 / i} for i in range(1, n_us + 1)]
    return kr + us + [{"code": "000BLK", "side": "kr", "cap": None}, {"code": "USNAN", "side": "us", "cap": float("nan")}]


def test_sample_is_the_same_for_the_same_seed_and_differs_for_another():
    a, ga, la = li.draw_sample(companies(), seed=20261105)
    b, gb, lb = li.draw_sample(list(reversed(companies())), seed=20261105)
    c, _, _ = li.draw_sample(companies(), seed=7)
    assert [x["code"] for x in a] == [x["code"] for x in b] and ga == gb
    assert [x["code"] for x in a] != [x["code"] for x in c]


def test_sample_shape_top_200_stratified_300_and_100_us():
    picked, groups, left = li.draw_sample(companies(), seed=1)
    by = {}
    for p in picked:
        by.setdefault(p["group"], []).append(p)
    assert [g["id"] for g in groups] == ["KR-A", "KR-B", "KR-C", "KR-D", "KR-E", "US-A", "US-B", "US-C", "US-D"]
    assert [x["rank"] for x in by["KR-A"]] == list(range(1, 201))                # the 200 largest, every one
    assert [len(by[g]) for g in ("KR-B", "KR-C", "KR-D", "KR-E")] == [75] * 4
    assert [len(by[g]) for g in ("US-A", "US-B", "US-C", "US-D")] == [25] * 4
    assert len({p["code"] for p in picked}) == len(picked) == 600            # no company twice
    assert {g["id"]: g["population"] for g in groups}["KR-B"] == 550 and sum(
        g["population"] for g in groups if g["side"] == "kr") == 2400
    ranks = {g: [x["rank"] for x in by[g]] for g in by}
    assert max(ranks["KR-B"]) < min(ranks["KR-C"]) and max(ranks["KR-D"]) < min(ranks["KR-E"])   # size groups in order
    assert {x["code"] for x in left} == {"000BLK", "USNAN"}                  # no cap -> never ranked or sampled
    assert "000BLK" not in {p["code"] for p in picked}


def test_sample_refuses_a_group_smaller_than_its_draw():
    with pytest.raises(ValueError):
        li.draw_sample(companies(n_kr=300), seed=1)


# ── providers: URLs, keys ──

def test_logo_urls_follow_the_documented_formats():
    k = "KEY"
    assert li.logo_url("brandfetch", "ticker", "005930.KS", k) == \
        "https://cdn.brandfetch.io/ticker/005930.KS/w/128/h/128/fallback/404?c=KEY"
    assert li.logo_url("brandfetch", "isin", "KR7005930003", k) == \
        "https://cdn.brandfetch.io/isin/KR7005930003/w/128/h/128/fallback/404?c=KEY"
    assert li.logo_url("brandfetch", "domain", "samsung.com", k) == \
        "https://cdn.brandfetch.io/domain/samsung.com/w/128/h/128/fallback/404?c=KEY"
    assert li.logo_url("logodev", "ticker", "247540.KQ", "pk_x") == \
        "https://img.logo.dev/ticker/247540.KQ?token=pk_x&size=128&format=webp&fallback=404"
    assert li.logo_url("logodev", "domain", "samsung.com", "pk_x") == \
        "https://img.logo.dev/samsung.com?token=pk_x&size=128&format=webp&fallback=404"
    assert li.logo_url("logodev", "ticker", "BRK-B", "pk_x").startswith("https://img.logo.dev/ticker/BRK-B?")
    with pytest.raises(KeyError):
        li.logo_url("logodev", "lettermark", "005930", "pk_x")


def test_logodev_ticker_suffixes():
    assert li.logodev_ticker("005930", "KOSPI") == "005930.KS" and li.logodev_ticker("247540", "KOSDAQ") == "247540.KQ"
    assert li.logodev_ticker("123456", "KONEX") == "123456.KS" and li.logodev_ticker("BRK-B", "US") == "BRK-B"
    assert li.logodev_ticker("123456", "") == ""


def test_masker_hides_keys_and_their_url_encoded_form():
    m = li.Masker("pk_abc/123", "bf-client-9", "")
    t = m("a https://img.logo.dev/x?token=pk_abc%2F123 b pk_abc/123 c ?c=bf-client-9 d")
    assert "pk_abc" not in t and "bf-client" not in t and t.count("***") == 3
    assert m("nothing secret") == "nothing secret"


def test_only_publishable_keys_go_into_a_page():
    assert li.check_publishable_keys("abcDEF123456", "pk_abcdef") == ("abcDEF123456", "pk_abcdef")
    for bf, ld in (("abcDEF123456", "sk_secret"), ("sk_abcdef", "pk_abcdef"), ("", "pk_abcdef"),
                   ("abcDEF123456", "abcdef"), ("abc<script>", "pk_abcdef")):
        with pytest.raises(SystemExit) as e:
            li.check_publishable_keys(bf, ld)
        assert all(v not in str(e.value) for v in (bf, ld) if len(v) > 3), e.value      # never echoes a key


# ── every company's exact identifiers, keys (tools/logos/logo_sources.py, used by the logo picker) ──

MUST_KR_TOP = ("005930", "000660", "005380")


def fake_inputs():
    """A made-up data.json, KRX listing and homepage CSV in the shapes the builder reads (no network)."""
    stocks = [{"t": c, "nk": f"KR{i}", "cls": "kr", "cap": 900.0 - i} for i, c in enumerate(MUST_KR_TOP)]
    stocks += [{"t": f"1{i:04d}0", "nk": f"KR co {i}", "cls": "kr", "cap": 100.0 / (i + 1)} for i in range(2400)]
    stocks += [{"t": "100005", "nk": "KR co 0 pref", "cls": "kr", "cap": 50.0},          # preferred share of 100000
               {"t": "069500", "nk": "ETF", "cls": "kr", "cap": 30.0, "etf": True},
               {"t": "0126Z0", "nk": "Letters", "cls": "kr", "cap": 0.5}]
    stocks += [{"t": f"U{i}", "nk": f"US co {i}", "cls": "us", "cap": 5000.0 / (i + 1)} for i in range(700)]
    stocks += [{"t": "BRK-B", "nk": "Berkshire", "cls": "us", "cap": 1000.0},
               {"t": "SPY", "cls": "us", "etf": True, "cap": 1.0}]
    data = {"pxDate": "2026-11-04", "usPxDate": "2026-11-04", "asOf": "2026-11-05", "stocks": stocks}
    listing = {"005930": {"Code": "005930", "ISU_CD": "KR7005930003", "Market": "KOSPI"},
               "000660": {"Code": "000660", "ISU_CD": "KR7000660001", "Market": "KOSPI"},
               "100040": {"Code": "100040", "ISU_CD": "KR7005930003", "Market": "KOSPI"},     # another code's ISIN
               "005380": {"Code": "005380", "ISU_CD": "KR7005380009", "Market": "KOSPI"},     # bad check digit
               "100000": {"Code": "100000", "ISU_CD": "KR7100000004", "Market": "KOSDAQ GLOBAL"},
               "100010": {"Code": "100010", "ISU_CD": "", "Market": "KONEX"}}
    homepages = {"005930": {"code": "005930", "domain": "samsung.com", "domain_ok": "1", "hm_url": "www.samsung.com/sec",
                            "corp_cls": "Y", "status": "ok"},
                 "000660": {"code": "000660", "domain": "blog.naver.com", "domain_ok": "0", "hm_url": "blog.naver.com/x",
                            "domain_note": "platform host", "corp_cls": "Y", "status": "ok"},
                 "100020": {"code": "100020", "domain": "", "domain_ok": "0", "hm_url": "-", "domain_note": "no homepage",
                            "corp_cls": "K", "status": "empty"}}
    return data, listing, homepages


def test_builder_uses_exact_identifiers_only():
    data, listing, homepages = fake_inputs()
    comps, log = lsrc.build_companies(data, listing, homepages)
    by = {c["code"]: c for c in comps}
    assert "100005" not in by and "069500" not in by and "SPY" not in by          # preferred share, ETFs left out
    assert by["005930"]["ticker"] == "005930.KS" and by["005930"]["isin"] == "KR7005930003"
    assert by["005930"]["isin_src"] == "KRX listing" and by["005930"]["domain"] == "samsung.com"
    assert by["000660"]["domain"] == "" and by["000660"]["domain_note"] == "platform host"
    assert by["005380"]["isin"] == "KR7005380001" and by["005380"]["isin_src"] == "common-share rule"   # listing one fails
    assert any("005380" in line and "check digit" in line for line in log)
    assert by["100000"]["ticker"] == "100000.KQ" and by["100010"]["ticker"] == "100010.KS"          # KOSDAQ GLOBAL, KONEX
    assert by["100020"]["ticker"] == "100020.KQ"                                  # not in the listing: DART corp_cls K
    assert by["100030"]["ticker"] == "" and by["100030"]["isin"] == li.kr_isin_from_code("100030")  # no market: no ticker
    assert by["BRK-B"]["ticker"] == "BRK-B" and by["BRK-B"]["isin"] == "" and by["BRK-B"]["domain"] == ""
    assert by["0126Z0"]["isin"] == "KR70126Z0002"
    assert by["100040"]["isin"] == li.kr_isin_from_code("100040") != "KR7005930003"   # listing ISIN of another code
    assert any("100040" in line and "another code" in line for line in log)
    assert not any(c["ticker"] and "." not in c["ticker"] and c["side"] == "kr" for c in comps)   # never a bare code


def test_the_builder_refuses_secret_keys(tmp_path):
    f = tmp_path / "k.env"
    f.write_text("BRANDFETCH_CLIENT_ID=abcdef123456\nLOGODEV_TOKEN=sk_secretvalue\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        lsrc.read_keys(str(f))
    assert "sk_secretvalue" not in str(e.value)
    f.write_text("BRANDFETCH_CLIENT_ID=abcdef123456\nLOGODEV_TOKEN=pk_ok123456\n", encoding="utf-8")
    assert lsrc.read_keys(str(f)) == ("abcdef123456", "pk_ok123456")
