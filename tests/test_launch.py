# -*- coding: utf-8 -*-
"""메인 주소를 뱁새 2.0 으로 (v18.3 Part F, Jack 2026-11-01 결정).

- index.html 은 app.html 로 보내요 (meta refresh · canonical · 안 열릴 때 누르는 링크). 바뀐 것은 이 세 주소와 공유 카드뿐이에요:
  공유 카드(설명 · og · twitter 태그)를 빼고 './app.html' 을 './baepsae.html' 로 바꾸면 예전 index.html 과 똑같아져요
- 공유 카드(Jack 승인, 2026-11-01): 메인 주소를 카톡·슬랙에 붙여도 카드가 떠요. 태그는 지금 앱(template.html)의 승인된 줄과 한 글자도 다르지 않아요
- 지금 앱(baepsae.html)은 그대로: 지금 소스로 새로 빌드해도 커밋한 파일과 한 글자도 다르지 않아요
- 2.0 에서 지금 앱으로 갈 수 있어요: 머리말의 '예전 뱁새 보기'와 찾기 탭이 ./baepsae.html 을 열어요
- 미리 보기(app-preview.html)로 가는 길은 메인 주소 어디에도 없어요
"""
import os
import re
import subprocess
import tempfile

from buildapp import built

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEFORE = "ca935dd"          # Part F 전의 main (index.html 이 baepsae.html 로 보내던 때)


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def test_index_redirects_to_app_and_keeps_its_text():
    idx = read("index.html")
    assert '<meta http-equiv="refresh" content="0; url=./app.html">' in idx
    assert '<link rel="canonical" href="./app.html">' in idx
    assert '<a href="./app.html" style="color:#1B2B4B">열리지 않으면 여기를 눌러주세요</a>' in idx
    assert "뱁이가 날아오는 중…" in idx and "<title>뱁새 Baepsae</title>" in idx
    assert idx.count("./app.html") == 3 and "baepsae.html" not in idx and "app-preview" not in idx


def share_lines(html):
    return [l for l in html.splitlines() if re.match(r'<meta (name="description"|property="og:|name="twitter:)', l)]


def test_index_has_the_approved_share_card():
    card = share_lines(read("index.html"))
    assert card == share_lines(read("template.html")), "index.html 의 공유 카드가 지금 앱(template.html)과 달라요"
    assert len(card) == 12 and '<meta property="og:url" content="https://jacksungjinlee.github.io/baepsae/">' in card
    assert '<meta property="og:image" content="https://jacksungjinlee.github.io/baepsae/og.png">' in card
    assert os.path.exists(os.path.join(ROOT, "og.png"))


def test_redirect_is_one_substitution_from_the_old_index():
    r = subprocess.run(["git", "show", f"{BEFORE}:index.html"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:                     # 얕은 clone 이면 예전 판이 없을 수 있어요: 위 검사로 충분해요
        return
    card = set(share_lines(read("index.html")))
    rest = "".join(l for l in read("index.html").splitlines(keepends=True) if l.rstrip("\n") not in card)
    assert rest.replace("./app.html", "./baepsae.html") == r.stdout


def test_current_app_still_builds_byte_identical():
    """build.sh 와 같은 명령으로 임시 폴더에 빌드해서 커밋한 baepsae.html 과 비교해요."""
    tmp = tempfile.mkdtemp()
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, "src/main.jsx", "--bundle", "--minify", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8",
                        f"--outfile={tmp}/bundle.js", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with open(f"{tmp}/bundle.js", encoding="utf-8") as f:
        js = f.read()
    assert read("template.html").replace("/*BUNDLE*/", js) == read("baepsae.html"), "baepsae.html 이 소스와 달라요"


def test_current_app_is_reachable_from_2_0():
    app = built("app.html")
    assert os.path.exists(os.path.join(ROOT, "baepsae.html"))
    assert '"./baepsae.html"' in app                       # 머리말 '예전 뱁새 보기' 와 찾기 탭이 쓰는 주소
    sw = read("sw.js")
    assert 'caches.match("./baepsae.html"' in sw           # 오프라인이면 캐시해 둔 지금 앱이라도 열려요


def test_preview_is_not_reachable_from_the_main_address():
    for f in ("index.html", "app.html", "baepsae.html", "sw.js", "manifest.webmanifest"):
        assert "app-preview" not in read(f), f
    assert not re.search(r"app-preview", built("app.html"))


def test_main_address_only_points_to_2_0_when_the_real_fields_are_live():
    """머지 문(리뷰 제안): 메인 주소가 app.html 로 가려면 저장소의 실제 데이터가 v17.5 형식이고 v17.5.1 항목이 있어야 해요.
    없으면 첫 방문자 모두가 '데이터를 불러오지 못했어요'(옛 형식)나 '준비 중'(항목 없음)만 보게 돼요.
    매일 실행이 v17.5.1 데이터를 발행하기 전에는 이 테스트가 실패해서, 메인 주소 전환을 머지할 수 없어요."""
    if "./app.html" not in read("index.html"):
        return
    missing = real_data_missing()
    assert not missing, "메인 주소를 2.0 으로 돌리기 전에 실제 데이터에 필요한 항목: " + ", ".join(missing)


V175_FORMAT = "pxDate·publishedAt (v17.5 형식)"


def real_data_missing(data=None, corp=None, macro=None):
    """저장소의 실제 데이터(data·corp·macro.json)에 2.0 이 쓰는 v17.5 형식·v17.5.1 항목 중 빠진 것. smoke_launch.py 도 써요.
    Jack(2026-11-02): ind · d1 · val20 · fy · etf 가 사이트에 올라오기 전에는 메인 주소를 2.0 으로 돌리지 않아요."""
    import json
    data = data if data is not None else json.loads(read("data.json"))
    corp = corp if corp is not None else json.loads(read("corp.json"))
    macro = macro if macro is not None else json.loads(read("macro.json"))
    kr = [s for s in data.get("stocks", []) if s.get("cls") == "kr"]
    missing = []
    if not (data.get("pxDate") and data.get("publishedAt") and corp.get("pxDate") and corp.get("publishedAt")):
        missing.append(V175_FORMAT)
    if not any("ind" in s for s in kr):
        missing.append("ind")
    if not any(isinstance(s.get("d1"), (int, float)) and not isinstance(s.get("d1"), bool) for s in kr):
        missing.append("d1")
    if not any("val20" in s for s in kr):
        missing.append("val20")
    if not data.get("stocks") or not all(isinstance(s.get("etf"), bool) for s in data["stocks"]):
        missing.append("etf (모든 종목)")
    if not any(s.get("dps") == 0 for s in kr):
        missing.append("dps = 0")
    if not any(isinstance(c.get("fy"), int) for c in corp.get("companies", [])):
        missing.append("fy")
    if not macro.get("idxHist"):
        missing.append("idxHist")
    return missing


def test_merge_gate_names_each_missing_field():
    """머지 문이 정말 막는지: v17.5.1 데이터(tests/fixtures/v2)는 통과하고, 항목 하나만 빠져도 그 이름을 대며 막아요."""
    import copy
    import json

    def fx(name):
        with open(os.path.join(ROOT, "tests", "fixtures", "v2", name), encoding="utf-8") as f:
            return json.load(f)
    base = {"data": fx("data.json"), "corp": fx("corp.json"), "macro": fx("macro.json")}
    assert real_data_missing(**copy.deepcopy(base)) == []
    assert "./app.html" in read("index.html")          # 이 브랜치에서는 머지 문이 실제로 검사해요 (건너뛰지 않아요)

    def drop_kr(key):
        def f(b):
            for s in b["data"]["stocks"]:
                if s.get("cls") == "kr":
                    s.pop(key, None)
        return f

    def drop_fy(b):
        for c in b["corp"]["companies"]:
            c.pop("fy", None)

    def drop_one_etf(b):
        b["data"]["stocks"][0].pop("etf", None)

    def no_zero_dps(b):
        for s in b["data"]["stocks"]:
            if s.get("dps") == 0:
                s.pop("dps")

    def drop_idx(b):
        b["macro"].pop("idxHist", None)

    def old_format(b):
        b["data"].pop("pxDate", None)
    cases = {"ind": drop_kr("ind"), "d1": drop_kr("d1"), "val20": drop_kr("val20"), "fy": drop_fy,
             "etf (모든 종목)": drop_one_etf, "dps = 0": no_zero_dps, "idxHist": drop_idx, V175_FORMAT: old_format}
    for want, change in cases.items():
        b = copy.deepcopy(base)
        change(b)
        assert real_data_missing(**b) == [want], (want, real_data_missing(**b))


def test_merge_gate_is_wired_to_the_repo_files(monkeypatch):
    """머지 문 테스트 자체가 저장소 파일을 읽고 막는지: d1 만 빠진 데이터면 실패, v17.5.1 데이터면 통과."""
    import json
    import pytest
    real = read
    files = {}
    for n in ("data.json", "corp.json", "macro.json"):
        with open(os.path.join(ROOT, "tests", "fixtures", "v2", n), encoding="utf-8") as f:
            files[n] = f.read()
    monkeypatch.setitem(globals(), "read", lambda p: files.get(p) or real(p))
    test_main_address_only_points_to_2_0_when_the_real_fields_are_live()          # 항목이 다 있으면 통과
    d = json.loads(files["data.json"])
    for s in d["stocks"]:
        if s.get("cls") == "kr":
            s.pop("d1", None)
    files["data.json"] = json.dumps(d, ensure_ascii=False)
    with pytest.raises(AssertionError, match="d1"):
        test_main_address_only_points_to_2_0_when_the_real_fields_are_live()
