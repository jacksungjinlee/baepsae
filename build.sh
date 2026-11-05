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
# v17.6: 배포(deploy.yml)할 때만 BAEPSAE_BUILD=커밋 을 넣어 <head> 에 빌드 표시를 달아요. 없으면 아무것도 바꾸지 않아요.
python3 tools/build_tag.py baepsae.html
