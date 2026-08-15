#!/bin/bash
# 뱁새 v11 빌드: src/ → baepsae.html (번들 인라인)
set -e
npx esbuild src/main.jsx --bundle --minify --loader:.jsx=jsx --jsx=automatic --charset=utf8 --outfile=dist/bundle.js
python3 - << 'PY'
tpl = open("template.html", encoding="utf-8").read()
js = open("dist/bundle.js", encoding="utf-8").read()
open("baepsae.html", "w", encoding="utf-8").write(tpl.replace("/*BUNDLE*/", js))
print("baepsae.html written:", len(js), "bytes of JS inlined")
PY
