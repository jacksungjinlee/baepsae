#!/bin/bash
# 시험 기계에 한글 글꼴을 깔아요 (내려받기 없음 · apt 없음). CI 와 매일 실행의 '발행 전 화면 검사'가 브라우저를 열기 전에 불러요.
# 예전 뱁새는 Pretendard 를 CDN 에서 받는데 시험은 바깥 주소를 모두 막아요 → 이 글꼴이 없으면 한글이 빈 네모로 그려져서
# 너비 · 넘침 검사가 실제보다 느슨해져요. 깔리지 않으면 실패해요 (네모로 조용히 넘어가지 않아요).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dest="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/baepsae-tests"
echo "3090ccde0442bb347aa7685d9ba8b17436a60682df6e8f92a9a670de14056e22  $here/PretendardVariable.ttf" | sha256sum --quiet --strict -c -
mkdir -p "$dest"
cp "$here/PretendardVariable.ttf" "$dest/"
fc-cache -f "$dest"
got="$(fc-match -f '%{file}' 'Pretendard Variable')"
fam="$(fc-match -f '%{family}' 'Pretendard Variable')"
ko="$(fc-list ':charset=AC00' file | grep -c 'baepsae-tests/PretendardVariable.ttf' || true)"
echo "· 한글 글꼴: 'Pretendard Variable' → $got ($fam) · 한글(가)을 가진 글꼴 파일로 인식 $ko"
# 'Pretendard Variable' 을 찾으면 Pretendard 가 나와야 하고 (이 기계에 같은 글꼴이 이미 깔려 있어도 괜찮아요), 방금 깐 파일이 한글 글꼴로 잡혀야 해요
if [[ "$fam" != *"Pretendard Variable"* ]] || [ "$ko" -lt 1 ]; then
  echo "!! 시험용 한글 글꼴(Pretendard)이 깔리지 않았어요 → 화면 검사를 믿을 수 없어요"
  exit 1
fi
