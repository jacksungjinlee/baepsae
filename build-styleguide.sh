#!/bin/bash
# 뱁새 2.0 스타일 페이지 빌드: styleguide/ + src/ui/ → styleguide.html (번들 인라인)
# 앱(baepsae.html)과는 따로 빌드해요. 앱 화면은 아직 src/ui/ 를 쓰지 않아요 (v18.1 Part 4 게이트).
set -euo pipefail
npx esbuild styleguide/main.jsx --bundle --minify --loader:.jsx=jsx --loader:.js=jsx --jsx=automatic --charset=utf8 \
  --define:process.env.NODE_ENV='"production"' --outfile=dist/styleguide.js
python3 - << 'PY'
tpl = open("styleguide/template.html", encoding="utf-8").read()
js = open("dist/styleguide.js", encoding="utf-8").read()
assert tpl.count("/*BUNDLE*/") == 1, "template must have exactly one /*BUNDLE*/ marker"
assert "</script" not in js, "bundle must not contain a closing script tag"
open("styleguide.html", "w", encoding="utf-8").write(tpl.replace("/*BUNDLE*/", js))
print("styleguide.html written:", len(js), "bytes of JS inlined")
PY
