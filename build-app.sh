#!/bin/bash
# 뱁새 2.0 미리 보기 빌드: src/v2/ + src/copy/v2.js + src/ui/ → app.html (번들 인라인)
# 지금 앱(baepsae.html, build.sh)과는 따로 빌드해요. app.html 은 빌드 결과라 손으로 고치지 않아요.
set -euo pipefail
npx esbuild src/v2/main.jsx --bundle --minify --loader:.jsx=jsx --loader:.js=jsx --jsx=automatic --charset=utf8 \
  --define:process.env.NODE_ENV='"production"' --outfile=dist/app.js
npx esbuild src/copy/v2.js --bundle --format=cjs --platform=node --charset=utf8 --log-level=warning --outfile=dist/copy-v2.cjs
TITLE=$(node -e 'process.stdout.write(JSON.stringify(require("./dist/copy-v2.cjs").C.app.title))')
TITLE="$TITLE" python3 - << 'PY'
import json, os
tpl = open("src/v2/template.html", encoding="utf-8").read()
js = open("dist/app.js", encoding="utf-8").read()
title = json.loads(os.environ["TITLE"])
assert tpl.count("/*BUNDLE*/") == 1 and tpl.count("/*TITLE*/") == 1, "template needs one /*BUNDLE*/ and one /*TITLE*/ marker"
assert "</script" not in js, "bundle must not contain a closing script tag"
assert "<" not in title and title.strip(), title
open("app.html", "w", encoding="utf-8").write(tpl.replace("/*TITLE*/", title).replace("/*BUNDLE*/", js))
print("app.html written:", len(js), "bytes of JS inlined")
PY
