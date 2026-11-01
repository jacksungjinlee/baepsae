# -*- coding: utf-8 -*-
"""미리 보기 페이지(app-preview.html)의 예시 데이터 (src/preview/fictional.json) 검사.

- 이름·코드가 실제 회사와 하나도 같지 않아요: 저장소 data.json · corp.json · tests/fixtures/v2 (실제 실행본 표본),
  그리고 REAL_RUN_DIR 환경 변수나 아래 폴더에 실제 발행본이 있으면 그것까지
- v17.5.1 필드가 모두 있어요: d1 · val20(한국) · etf(모두) · ind/indName · dps(0 포함) · fy · macro.idxHist
- 업종 그룹은 실제 그룹 id·이름(data/industry_groups.csv)이고, 시장마다 5개 이상
- 펀드·채권·금(순위에 안 들어감)과 우선주 2개가 있어요. 날짜는 고정(발행일이 지나도 멈춤 경고 없이 '예시 데이터'로만 보여요)
- NaN 없음, v17.5 형식(pxDate · publishedAt)
"""
import json
import math
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN91 = "/tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/run91"
# data/industry_groups.csv (branch claude/v17.5.1-industry) 의 그룹 중 예시 데이터가 쓰는 것
GROUPS = {"semi": "반도체", "semi_eq": "반도체 장비", "auto": "자동차", "bank": "은행", "insurance": "보험", "securities": "증권",
          "food": "음식료·담배", "chem": "화학", "machinery": "기계", "pharma": "제약", "holding": "지주회사",
          "utility": "전력·가스·환경", "construction": "건설·엔지니어링", "software": "소프트웨어", "medical": "의료기기",
          "energy": "정유·에너지"}


def fic():
    with open(os.path.join(ROOT, "src", "preview", "fictional.json"), encoding="utf-8") as f:
        return json.load(f)


def real_sets():
    names, codes = set(), set()
    dirs = [ROOT, os.path.join(ROOT, "tests", "fixtures", "v2")]
    extra = os.environ.get("REAL_RUN_DIR") or (RUN91 if os.path.isdir(RUN91) else None)
    if extra:
        dirs.append(extra)
    for d in dirs:
        for f in ("data.json", "corp.json"):
            p = os.path.join(d, f)
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as fh:
                j = json.load(fh)
            for s in j.get("stocks", []) + j.get("companies", []):
                codes.add(str(s.get("t")).upper())
                for k in ("nk", "ne"):
                    if s.get(k):
                        names.add(str(s[k]).strip().lower())
    assert len(names) > 2000 and len(codes) > 2000, "실제 회사 목록이 너무 작아요"
    return names, codes


def test_no_real_names_or_codes():
    names, codes = real_sets()
    f = fic()
    items = f["data"]["stocks"] + f["corp"]["companies"]
    clash_n = sorted({s["nk"] for s in items if s["nk"].strip().lower() in names} | {s.get("ne", "") for s in items if s.get("ne", "").strip().lower() in names})
    clash_t = sorted({s["t"] for s in items if str(s["t"]).upper() in codes})
    assert not clash_n, f"실제 회사 이름과 같아요: {clash_n}"
    assert not clash_t, f"실제 코드와 같아요: {clash_t}"
    mock = {"늘봄금융", "솔담정밀", "마루식품", "Pinecrest Health"}
    assert mock <= {s["nk"] for s in f["data"]["stocks"]}
    kr = [s for s in f["data"]["stocks"] if s["cls"] == "kr" and not s["etf"]]
    assert all(s["t"].startswith("98") for s in kr), "한국 예시 코드는 98xxxx 범위예요"


def test_sizes_fields_and_groups():
    f = fic()
    st = f["data"]["stocks"]
    kr = [s for s in st if s["cls"] == "kr" and not s["etf"]]
    us = [s for s in st if s["cls"] == "us" and not s["etf"]]
    assert 75 <= len(kr) <= 90 and 35 <= len(us) <= 45, (len(kr), len(us))
    assert all("etf" in s for s in st)
    assert all("d1" in s for s in kr + us)
    assert all("val20" in s for s in kr) and any(s["dps"] == 0 for s in kr) and any(s["dps"] > 0 for s in kr)
    assert all(s.get("fy") == 2025 for s in kr) and all(c.get("fy") == 2025 for c in f["corp"]["companies"])
    h = f["macro"]["idxHist"]
    for k in ("KOSPI", "SP500"):
        assert h[k]["rows"][-1][0] == h[k]["asOf"] and len(h[k]["rows"]) >= 700
    for mk, group in (("kr", kr), ("us", us)):
        counts = {}
        for s in group:
            if s.get("ind"):
                assert GROUPS[s["ind"]] == s["indName"], (s["ind"], s["indName"])
                counts[s["ind"]] = counts.get(s["ind"], 0) + 1
        assert counts and all(n >= 5 for n in counts.values()), (mk, counts)
    pref = [s for s in kr if not s["t"].endswith("0")]
    assert len(pref) == 2 and all(s["nk"].endswith("우") for s in pref)
    funds = [s for s in st if s["etf"]]
    assert {s["cls"] for s in funds} >= {"bond", "metal", "kr", "us"} and all(s["t"] for s in funds)
    cush = {c["t"] for c in f["cushion"]}
    assert cush <= {s["t"] for s in funds} and {c["like"] for c in f["cushion"]} == {"114260", "132030"}


def test_fixed_dates_v175_format_and_no_nan():
    f = fic()
    for k in ("data", "corp"):
        assert f[k]["pxDate"] == "2026-10-30" and f[k]["publishedAt"] == "2026-10-31T06:41:00+09:00" and f[k]["fictional"] is True
    assert f["macro"]["publishedAt"]

    def walk(v):
        if isinstance(v, float):
            assert math.isfinite(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(f)
    text = open(os.path.join(ROOT, "src", "preview", "fictional.json"), encoding="utf-8").read()
    assert "NaN" not in text and "Infinity" not in text


def test_generator_reproduces_the_committed_file(tmp_path):
    """같은 씨앗으로 다시 만들면 커밋한 파일과 같아요 (손으로 고치지 않음)."""
    src = os.path.join(ROOT, "src", "preview", "make_fictional.py")
    before = open(os.path.join(ROOT, "src", "preview", "fictional.json"), encoding="utf-8").read()
    extra = os.environ.get("REAL_RUN_DIR") or (RUN91 if os.path.isdir(RUN91) else None)
    if not extra:
        return    # 실제 발행본이 없으면 이름 피하기 결과가 달라질 수 있어 건너뛰어요 (위 검사가 이름·코드를 따로 확인해요)
    out = str(tmp_path / "fictional.json")
    r = subprocess.run(["python3", src, "--real", extra, "--out", out, "--offline"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    after = open(out, encoding="utf-8").read()
    assert after == before


KNOWN_REAL = ["SAFE", "JANP", "FSNIX"]          # 첫 미리 보기에 있었던 실제 티커 (리뷰 2차): Safehold, PGIM ETF, Fidelity 펀드
MOCKUP = {"늘봄금융", "솔담정밀", "마루식품", "Pinecrest Health"}


def test_every_us_ticker_was_checked_unused_on_yahoo():
    """만들 때 야후 차트 API 에 물어 404(없는 티커)였던 것만 써요. 그 결과를 커밋한 목록과 맞춰 봐요."""
    with open(os.path.join(ROOT, "src", "preview", "ticker-check.json"), encoding="utf-8") as f:
        chk = json.load(f)
    assert "query1.finance.yahoo.com/v8/finance/chart" in chk["source"] and "404" in chk["rule"]
    us_t = sorted(s["t"] for s in fic()["data"]["stocks"] if s["cls"] == "us")
    assert us_t and sorted(chk["status"]) == us_t, "목록과 예시 데이터의 미국 티커가 달라요: 생성기를 다시 돌리세요"
    assert all(v == 404 for v in chk["status"].values())
    _, codes = real_sets()
    assert not [t for t in us_t if t in codes] and not [t for t in KNOWN_REAL if t in us_t]


def test_names_use_invented_words_not_real_brand_prefixes():
    names, _ = real_sets()
    first = {n.split()[0] for n in names if n.split()}
    bad = []
    for s in fic()["data"]["stocks"]:
        nk = s["nk"]
        if nk in MOCKUP or s["etf"] and s["cls"] != "us":
            continue
        if s["cls"] == "us":
            w = nk.split()[0].lower()
            if w in first or any(n.startswith(w) for n in names):
                bad.append(nk)
        else:
            pre = nk[:2].lower()
            if any(n.startswith(pre) for n in names):
                bad.append(nk)
    for s in fic()["data"]["stocks"]:                 # 펀드 이름의 첫 낱말(브랜드)도
        if s["etf"] and s["cls"] != "us" and any(n.startswith(s["nk"].split()[0].lower()) for n in names):
            bad.append(s["nk"])
    assert not bad, f"실제 회사 이름이 이렇게 시작해요: {bad[:10]}"
    joined = " ".join(s["nk"] for s in fic()["data"]["stocks"])
    for word in ("가온", "Juniper", "Ironwood", "Larkfield", "누리"):
        assert word not in joined, word
