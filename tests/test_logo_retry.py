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


# ── after the fresh-eyes review (2026-11-07) ──
def letters_setup(tmp_path, gone=("005380", "000660")):
    """A reviewed folder (a whole run) in which `gone` show letter marks, as on the logos-run branch."""
    T.write_inputs(tmp_path)
    rc, first = T.run(tmp_path, Net(dict(T.ALL_GOOD)), out_name="first")
    idx = T.index(first)
    for code in gone:
        (first / "logos" / idx["logos"][code]["file"]).unlink()
        del idx["logos"][code]
    idx["count"] = len(idx["logos"])
    (first / "logos" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    return first


def test_a_letters_run_without_limit_records_itself_and_adds_only_the_named_codes(tmp_path):
    first = letters_setup(tmp_path)
    rc, retry = T.run(tmp_path, Net(dict(T.ALL_GOOD)), "--letters-from", str(first), "--extra-routes", out_name="retry")
    info = json.loads((retry / "run.json").read_text(encoding="utf-8"))
    assert rc == 0 and info["ok"] is True and info["companies"] == 2                  # no --limit: every letter mark
    assert info["letters_from"] == str(first) and info["extra_routes"] is True
    assert info["max_credits"] == info["plan"]["ceiling"] == 2 * (2 + 2 + 2 + 3)       # the plan counts a brandmark at 3
    assert {"000660", "005380"} <= set(T.index(retry)["logos"])
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:                                             # never the whole retry at once
        F.main(["--add-from", str(retry), "--dir", str(first)])
    assert "--codes" in str(e.value) and T.snapshot(first) == before
    with pytest.raises(SystemExit) as e:                                             # only logos of that run
        F.main(["--add-from", str(retry), "--dir", str(first), "--codes", "005930"])
    assert "not a logo of that run" in str(e.value) and T.snapshot(first) == before
    assert F.main(["--add-from", str(retry), "--dir", str(first), "--codes", "000660", "--reason", "checked"]) == 0
    idx = T.index(first)
    assert "000660" in idx["logos"] and "005380" not in idx["logos"]                 # the other one stays a letter mark
    assert idx["logos"]["000660"]["flags"][-1] == "added-after-review"


def test_codes_is_refused_for_an_only_run(tmp_path):
    first = letters_setup(tmp_path, gone=("005380",))
    rc, fix = T.run(tmp_path, Net(dict(T.ALL_GOOD)), "--only", "005380", full_run_date=None, out_name="fix")
    before = T.snapshot(first)
    with pytest.raises(SystemExit) as e:
        F.main(["--add-from", str(fix), "--dir", str(first), "--codes", "005380"])
    assert "--codes is for a --letters-from run" in str(e.value) and T.snapshot(first) == before


def test_a_size_less_brandmark_that_draws_wide_is_dropped(tmp_path):
    from PIL import Image, ImageDraw
    T.write_inputs(tmp_path)
    net = Net(dict(T.ALL_GOOD))
    net.answers[("ticker", "005380.KS")] = [small("hmc", "brand_hmc")]
    net.answers[("domain", "hyundai.com")] = [T.not_found()]
    j = json.loads(brandmark_answer("lockup", "brand_hmc").body)
    j["data"]["source"].update(width=None, height=None, format="svg", is_vector=True)    # a vector without a size
    net.answers[("brandmark", "005380.KS")] = [chk.Resp(200, {"Credits-Charged": "1"}, T.body(j))]
    im = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((0, 120, 299, 180), fill=(20, 60, 160, 255))          # drawn part 5:1
    net.pics["lockup"] = T.png(im)
    rc, out = T.run(tmp_path, net, "--extra-routes")
    rv = T.review(out)["005380"]
    assert rc == 0 and rv["result"] == "letter" and "005380" not in T.index(out)["logos"]
    assert (out / "dropped").exists() and any(p.name.startswith("005380") for p in (out / "dropped").iterdir())


def test_another_brands_picture_or_one_dropped_by_eye_is_not_asked_again_but_a_small_one_is(tmp_path):
    first = letters_setup(tmp_path, gone=("005380", "000660", "247540"))
    rows = list(__import__("csv").DictReader(open(first / "review.csv", newline="", encoding="utf-8")))
    for r in rows:
        if r["code"] == "005380":
            r["reason"] = "small"                                                    # failed a check: asked again
        if r["code"] == "000660":
            r["reason"] = "shared"                                                   # another brand's picture
    with open(first / "review.csv", "w", newline="", encoding="utf-8") as f:
        w = __import__("csv").DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (first / "drops.csv").write_text("code,name,file,reason\n247540,에코프로비엠,247540.webp,photo\n", encoding="utf-8")
    net = Net(dict(T.ALL_GOOD))
    rc, out = T.run(tmp_path, net, "--letters-from", str(first), "--extra-routes", out_name="retry")
    assert rc == 0
    asked = {x[1] for x in net.lookups if x[0] in ("ticker", "domain")}
    assert "005380.KS" in asked and "hyundai.com" in asked                          # re-asked: answers change
    assert "000660.KS" not in asked and "skhynix.com" not in asked                  # shared: straight to the ISIN
    assert "247540.KQ" not in asked                                                 # dropped by eye: same
    assert ("isin", "KR7000660001") in net.lookups
    net2 = Net(dict(T.ALL_GOOD))                                                    # without --extra-routes they are left out
    rc, out2 = T.run(tmp_path, net2, "--letters-from", str(first), out_name="retry2")
    assert json.loads((out2 / "run.json").read_text(encoding="utf-8"))["companies"] == 1


def test_the_cap_stops_before_a_brandmark_it_cannot_pay_for(tmp_path):
    T.write_inputs(tmp_path)
    net = Net({("ticker", "005930.KS"): [small("s", "brand_sam")], ("domain", "samsung.com"): [T.not_found(cc="1")],
               ("isin", "KR7005930003"): [T.not_found(cc="1")],
               ("brandmark", "005930.KS"): [brandmark_answer("bm", "brand_sam")]})
    rc, out = T.run(tmp_path, net, "--only", "005930", "--extra-routes", "--max-credits", "8", full_run_date=None)
    assert ("brandmark", "005930.KS") not in net.lookups                           # 2 + 2 + 2 = 6; +3 > 8
    info = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert info["credits"]["counted"] == 6 and info["max_credits"] == 8


def test_a_letters_retry_above_20_dollars_needs_the_explicit_yes(tmp_path, monkeypatch):
    first = letters_setup(tmp_path)
    monkeypatch.setattr(F, "RETRY_SPEND_ASK", 10)                                  # the 2-company plan is 18 credits
    with pytest.raises(SystemExit) as e:
        T.run(tmp_path, Net(dict(T.ALL_GOOD)), "--letters-from", str(first), "--extra-routes", out_name="r1")
    assert "Jack asked to be told first" in str(e.value)
    rc, out = T.run(tmp_path, Net(dict(T.ALL_GOOD)), "--letters-from", str(first), "--extra-routes", "--over-20-ok",
                    out_name="r2")
    assert rc == 0


def test_with_extra_routes_a_usable_homepage_logo_beats_a_small_ticker_icon(tmp_path):
    T.write_inputs(tmp_path)
    net = Net(dict(T.ALL_GOOD))
    net.answers[("ticker", "005380.KS")] = [small("hmc", "brand_hmc")]
    net.answers[("domain", "hyundai.com")] = [T.logo_answer("hmcbig", "brand_hmc")]
    rc, out = T.run(tmp_path, net, "--extra-routes")
    rv = T.review(out)["005380"]
    assert rc == 0 and (rv["result"], rv["route"]) == ("logo", "domain")
    assert ("isin", "KR7005380001") not in net.lookups                              # usable already: no extra lookups


def test_the_workflow_passes_the_over_20_dollars_yes_through_env_only():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "logo-dev-fetch.yml").read_text(encoding="utf-8"))
    assert wf[True]["workflow_dispatch"]["inputs"]["over_20_dollars_ok"]["default"] is False
    run = {s.get("name"): s for s in wf["jobs"]["fetch"]["steps"]}["logo.dev 로고 받기 실행"]
    assert run["env"]["OVER_20_OK"] == "${{ inputs.over_20_dollars_ok }}" and "--over-20-ok" in run["run"]
