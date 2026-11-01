#!/bin/bash
# 뱁새 2.0 빌드: src/v2/ + src/copy/v2.js + src/ui/ → app.html (실제 데이터) 와 app-preview.html (예시 데이터)
#   bash build-app.sh          # 저장소 맨 위에 두 파일을 써요
#   bash build-app.sh DIR      # DIR 에 써요 (테스트가 씀)
# 지금 앱(baepsae.html, build.sh)과는 따로 빌드해요. 두 파일 모두 빌드 결과라 손으로 고치지 않아요.
# app.html 은 메인 주소가 보여 주는 페이지예요 (Part F, Jack 2026-11-01): index.html 이 여기로 보내요.
#   <head> 의 설명·공유 카드(og·twitter) 태그와 GoatCounter 는 지금 앱의 template.html 에서 그대로 가져와요.
# app-preview.html 은 지어낸 예시 데이터(src/preview/fictional.json)를 품고, 데이터 파일을 받지 않아요.
#   noindex 이고 GoatCounter·서비스워커가 없으며, 어디에서도 링크하지 않아요.
set -euo pipefail
OUT="${1:-.}"
mkdir -p "$OUT" dist
COMMON=(--bundle --minify --loader:.jsx=jsx --loader:.js=jsx --jsx=automatic --charset=utf8 --define:process.env.NODE_ENV='"production"')
npx esbuild src/v2/main.jsx "${COMMON[@]}" --outfile=dist/app.js
npx esbuild src/v2/main-preview.jsx "${COMMON[@]}" --outfile=dist/app-preview.js
npx esbuild src/copy/v2.js --bundle --format=cjs --platform=node --charset=utf8 --log-level=warning --outfile=dist/copy-v2.cjs
TITLE=$(node -e 'const a = require("./dist/copy-v2.cjs").C.app; process.stdout.write(JSON.stringify([a.title, a.previewTitle.replace("{title}", a.title).replace("{sample}", a.sample)]))')
TITLE="$TITLE" OUT="$OUT" python3 - << 'PY'
import json, os
tpl = open("src/v2/template.html", encoding="utf-8").read()
title, preview_title = json.loads(os.environ["TITLE"])   # the preview's tab says 예시 데이터 too
out = os.environ["OUT"]
for m in ("/*BUNDLE*/", "/*TITLE*/", "/*SW*/", "/*HEAD*/"):
    assert tpl.count(m) == 1, f"template needs exactly one {m}"
# The current app's approved <head> text (description, og:*, twitter:*) and GoatCounter snippet, taken from
# template.html as they are (that file stays byte-identical), for the live page only.
import re
old = open("template.html", encoding="utf-8").read()
meta = [l for l in old.splitlines() if re.match(r'<meta (name="description"|property="og:|name="twitter:)', l)]
gc = re.findall(r"<script>\n\(function\(\)\{try\{\n  var q=new URLSearchParams.*?</script>", old, flags=re.S)
assert len(meta) >= 12 and any('property="og:url"' in l for l in meta), meta
assert len(gc) == 1 and "goatcounter" in gc[0], "GoatCounter snippet not found in template.html"
LIVE_HEAD = "\n".join(meta) + "\n" + gc[0]
PREVIEW_HEAD = '<meta name="robots" content="noindex, nofollow">'
assert "<" not in title + preview_title and title.strip() and "{" not in preview_title, (title, preview_title)
# Service worker (sw.js, v17.5): network first, cache only offline. Only the live page registers it.
SW = """<script>
(function(){try{
  if(!("serviceWorker" in navigator))return;
  var h=location.hostname;
  if(location.protocol!=="https:"&&h!=="localhost"&&h!=="127.0.0.1")return;
  window.addEventListener("load",function(){navigator.serviceWorker.register("./sw.js").catch(function(){});});
}catch(e){}})();
</script>"""
for name, bundle, sw, ttl, head in (("app.html", "dist/app.js", SW, title, LIVE_HEAD),
                                    ("app-preview.html", "dist/app-preview.js", "", preview_title, PREVIEW_HEAD)):
    js = open(bundle, encoding="utf-8").read()
    assert "</script" not in js, "bundle must not contain a closing script tag"
    html = tpl.replace("/*TITLE*/", ttl).replace("/*HEAD*/", head).replace("/*SW*/", sw).replace("/*BUNDLE*/", js)
    open(os.path.join(out, name), "w", encoding="utf-8").write(html)
    print(f"{name} written:", len(js), "bytes of JS inlined")
PY
