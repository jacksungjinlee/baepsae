#!/bin/bash
# 뱁새 2.0 빌드: src/v2/ + src/copy/v2.js + src/ui/ → app.html (실제 데이터) 와 app-preview.html (예시 데이터)
#   bash build-app.sh          # 저장소 맨 위에 두 파일을 써요
#   bash build-app.sh DIR      # DIR 에 써요 (테스트가 씀)
# 지금 앱(baepsae.html, build.sh)과는 따로 빌드해요. 두 파일 모두 빌드 결과라 손으로 고치지 않아요.
# app.html 은 v17.5.1 필드가 실제 데이터에 들어올 때까지 커밋하지 않아요 (.gitignore, v18.3 스펙의 머지 조건).
# app-preview.html 은 지어낸 예시 데이터(src/preview/fictional.json)를 품고, 데이터 파일을 받지 않아요.
set -euo pipefail
OUT="${1:-.}"
mkdir -p "$OUT" dist
COMMON=(--bundle --minify --loader:.jsx=jsx --loader:.js=jsx --jsx=automatic --charset=utf8 --define:process.env.NODE_ENV='"production"')
npx esbuild src/v2/main.jsx "${COMMON[@]}" --outfile=dist/app.js
npx esbuild src/v2/main-preview.jsx "${COMMON[@]}" --outfile=dist/app-preview.js
npx esbuild src/copy/v2.js --bundle --format=cjs --platform=node --charset=utf8 --log-level=warning --outfile=dist/copy-v2.cjs
TITLE=$(node -e 'process.stdout.write(JSON.stringify(require("./dist/copy-v2.cjs").C.app.title))')
TITLE="$TITLE" OUT="$OUT" python3 - << 'PY'
import json, os
tpl = open("src/v2/template.html", encoding="utf-8").read()
title = json.loads(os.environ["TITLE"])
out = os.environ["OUT"]
for m in ("/*BUNDLE*/", "/*TITLE*/", "/*SW*/"):
    assert tpl.count(m) == 1, f"template needs exactly one {m}"
assert "<" not in title and title.strip(), title
# Service worker (sw.js, v17.5): network first, cache only offline. Only the live page registers it.
SW = """<script>
(function(){try{
  if(!("serviceWorker" in navigator))return;
  var h=location.hostname;
  if(location.protocol!=="https:"&&h!=="localhost"&&h!=="127.0.0.1")return;
  window.addEventListener("load",function(){navigator.serviceWorker.register("./sw.js").catch(function(){});});
}catch(e){}})();
</script>"""
for name, bundle, sw in (("app.html", "dist/app.js", SW), ("app-preview.html", "dist/app-preview.js", "")):
    js = open(bundle, encoding="utf-8").read()
    assert "</script" not in js, "bundle must not contain a closing script tag"
    html = tpl.replace("/*TITLE*/", title).replace("/*SW*/", sw).replace("/*BUNDLE*/", js)
    open(os.path.join(out, name), "w", encoding="utf-8").write(html)
    print(f"{name} written:", len(js), "bytes of JS inlined")
PY
