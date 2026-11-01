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


def real_data_missing():
    """저장소의 실제 데이터(data·corp·macro.json)에 2.0 이 쓰는 v17.5 형식·v17.5.1 항목 중 빠진 것. smoke_launch.py 도 써요."""
    import json
    data, corp = json.loads(read("data.json")), json.loads(read("corp.json"))
    macro = json.loads(read("macro.json"))
    kr = [s for s in data.get("stocks", []) if s.get("cls") == "kr"]
    missing = []
    if not (data.get("pxDate") and data.get("publishedAt") and corp.get("pxDate") and corp.get("publishedAt")):
        missing.append(V175_FORMAT)
    if not any("ind" in s for s in kr):
        missing.append("ind")
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
