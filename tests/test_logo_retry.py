# -*- coding: utf-8 -*-
"""Logo retry (Jack, 2026-11-07): --letters-from (only the companies still showing a letter mark in the reviewed folder,
largest first) and --extra-routes (Korean companies: an ISIN lookup, then a brandmark lookup by ticker, only after the
ticker and the DART homepage gave no usable logo). Same fakes as test_logo_fetch.py: no network, no real key.
Every quality check still applies; a wide brandmark lockup is never used; the brandmark's 3 credits are counted.
"""
import json
import pathlib
import sys

import pytest

import test_logo_fetch as T

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))

import logodev_api_check as chk  # noqa: E402
import logodev_fetch as F  # noqa: E402

pytest.importorskip("PIL")


def brandmark_answer(token, brand, w=512, h=512, cc="1"):
    r = T.logo_answer(token, brand, w=w, h=h, cc=cc)
    j = json.loads(r.body)
    j["data"]["kind"] = "brandmark"
    return chk.Resp(200, dict(r.headers), T.body(j))


class Net(T.Net):
    """T.Net plus the brandmark path: answers[("brandmark", ticker)]."""

    def __call__(self, url, params=None, headers=None, timeout=None, max_bytes=None, follow=False):
        if url == chk.API_BASE + F.BRANDMARK_ROUTE:
            (key, ident), = params.items()
            assert key == "ticker" and follow is False
            with self.lock:
                self.lookups.append(("brandmark", ident))
            q = self.answers.get(("brandmark", ident)) or [T.not_found()]
            return q.pop(0) if len(q) > 1 else q[0]
        return super().__call__(url, params, headers, timeout, max_bytes, follow)


def small(token, brand):
    return T.logo_answer(token, brand, w=32, h=32)


def test_without_the_flag_nothing_changes(tmp_path):
    T.write_inputs(tmp_path)
    net = Net(dict(T.ALL_GOOD))
    net.answers[("ticker", "005380.KS")] = [small("hmc", "brand_hmc")]
    rc, out = T.run(tmp_path, net)
    assert rc == 0 and not [x for x in net.lookups if x[0] in ("isin", "brandmark")]
    assert T.review(out)["005380"]["result"] == "letter" and T.review(out)["005380"]["reason"] == "small"


def test_isin_only_after_ticker_and_homepage_give_nothing_usable(tmp_path):
    T.write_inputs(tmp_path)
    net = Net(dict(T.ALL_GOOD))
    net.answers[("ticker", "005380.KS")] = [small("hmc", "brand_hmc")]           # a 32 px site icon
    net.answers[("domain", "hyundai.com")] = [T.not_found()]
    net.answers[("isin", "KR7005380001")] = [T.logo_answer("hmcisin", "brand_hmc2")]
    rc, out = T.run(tmp_path, net, "--extra-routes")
    rv = T.review(out)
    assert rc == 0 and (rv["005380"]["result"], rv["005380"]["route"], rv["005380"]["check"]) == ("logo", "isin", "isin")
    assert rv["005380"]["isin"] == "KR7005380001" and rv["005380"]["isin_status"] == "logo"
    assert ("brandmark", "005380.KS") not in net.lookups                           # the ISIN logo was usable: no brandmark
    # companies whose ticker logo was fine never get the extra lookups
    assert ("isin", "KR7005930003") not in net.lookups and ("isin", "KR7000660001") not in net.lookups
    assert "005380" in T.index(out)["logos"]
    assert "logo found by ISIN" in (out / "sheet.html").read_text(encoding="utf-8")


def test_brandmark_only_when_it_is_large_and_not_too_wide(tmp_path):
    T.write_inputs(tmp_path)
    net = Net(dict(T.ALL_GOOD))
    for t, dom in (("005380.KS", "hyundai.com"), ("000660.KS", "skhynix.com")):
        net.answers[("ticker", t)] = [small("s" + t, "b" + t)]
        net.answers[("domain", dom)] = [T.not_found()]
    net.answers[("brandmark", "005380.KS")] = [brandmark_answer("wide", "brand_hmc", w=600, h=150)]    # 4:1 lockup
    net.answers[("brandmark", "000660.KS")] = [brandmark_answer("ok", "brand_hyn", w=300, h=200)]     # 1.5:1
    rc, out = T.run(tmp_path, net, "--extra-routes")
    rv = T.review(out)
    assert ("isin", "KR7005380001") in net.lookups and ("brandmark", "005380.KS") in net.lookups      # ISIN first, then brandmark
    assert (rv["005380"]["result"], rv["005380"]["reason"]) == ("letter", "small")                    # the wide one is not used
    assert rv["005380"]["brandmark_status"] == "logo" and rv["005380"]["brandmark_size"] == "600x150"
    assert (rv["000660"]["result"], rv["000660"]["route"]) == ("logo", "brandmark")
    assert "brandmark (wide lockup)" in (out / "sheet.html").read_text(encoding="utf-8")
    # US companies never get the extra lookups
    assert not [x for x in net.lookups if x[0] in ("isin", "brandmark") and not x[1].startswith(("KR7", "0"))]


def test_a_small_brandmark_still_fails_the_small_check(tmp_path):
    T.write_inputs(tmp_path)
    net = Net(dict(T.ALL_GOOD))
    net.answers[("ticker", "005380.KS")] = [small("hmc", "brand_hmc")]
    net.answers[("domain", "hyundai.com")] = [T.not_found()]
    net.answers[("brandmark", "005380.KS")] = [brandmark_answer("tiny", "brand_hmc", w=40, h=40)]
    rc, out = T.run(tmp_path, net, "--extra-routes")
    assert (T.review(out)["005380"]["result"], T.review(out)["005380"]["reason"]) == ("letter", "small")


def test_a_brandmark_costs_three_credits_and_the_cap_holds():
    led = F.Ledger(7)
    assert led.reserve(F.ROUTE_COST["isin"]) is None and led.reserve(F.ROUTE_COST["brandmark"]) is None   # 2 + 3 = 5
    assert led.reserve(F.ROUTE_COST["brandmark"]) == "cap"                                               # 5 + 3 > 7
    assert led.settle(chk.Resp(200, {"Credits-Charged": "1"}, b"{}"), F.ROUTE_COST["brandmark"]) == 3
    assert led.counted == 3 and led.reserved == 2
    assert led.unanswered(F.ROUTE_COST["isin"]) == 2 and led.counted == 5 and led.reserved == 0
    assert F.plan([{"side": "kr", "ticker": "1.KS", "domain": "a.kr", "isin": "KR7"}], extra=True)["ceiling"] == 2 + 2 + 2 + 3


def test_letters_from_keeps_only_companies_without_a_logo_largest_first(tmp_path):
    T.write_inputs(tmp_path)
    rc, first = T.run(tmp_path, Net(dict(T.ALL_GOOD)), out_name="first")              # every company gets a logo
    idx = T.index(first)
    for code in ("005380", "000660"):                                                  # pretend these two are letter marks
        (first / "logos" / idx["logos"][code]["file"]).unlink()
        del idx["logos"][code]
    (first / "logos" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    net = Net(dict(T.ALL_GOOD))
    rc, out = T.run(tmp_path, net, "--letters-from", str(first), "--limit", "1", full_run_date=None, out_name="retry")
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["companies"] == 1                                          # the larger of the two: SK하이닉스
    assert {x[1] for x in net.lookups} <= {"000660.KS", "skhynix.com"} and net.lookups
    assert info["max_credits"] == info["plan"]["ceiling"] == 4                           # a retry never spends past its plan
    with pytest.raises(SystemExit):
        F.letters_from([], tmp_path / "nowhere")


def test_the_workflow_passes_the_retry_inputs_through_env_only():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "logo-dev-fetch.yml").read_text(encoding="utf-8"))
    inp = wf[True]["workflow_dispatch"]["inputs"]
    assert inp["letters_only"]["default"] is False and inp["extra_routes"]["default"] is False
    steps = {s.get("name"): s for s in wf["jobs"]["fetch"]["steps"]}
    get = steps["검사를 마친 로고 폴더 받기 (letters_only 일 때만)"]
    assert get["if"] == "inputs.letters_only" and "logos-run" in get["run"] and "LOGO_DEV" not in get["run"]
    run = steps["logo.dev 로고 받기 실행"]
    assert run["env"]["LETTERS_ONLY"] == "${{ inputs.letters_only }}" and run["env"]["EXTRA_ROUTES"] == "${{ inputs.extra_routes }}"
    assert "${{" not in run["run"]                                                  # inputs only through env
    assert '--letters-from "$RUNNER_TEMP/reviewed"' in run["run"] and "--extra-routes" in run["run"]
    # the published logo folder accepts the new routes (Deploy validates with tools/logos/logo_index.py)
    import logo_index as LI
    assert {"isin", "brandmark"} <= set(LI.ROUTES)
