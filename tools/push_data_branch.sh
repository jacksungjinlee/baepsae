#!/bin/bash
# v17.6 Part 3a: 발행 관문(validate_data.py)을 통과한 네 JSON 을 data 브랜치에 올려요. 사이트 배포(deploy.yml)가 여기서 가져가요.
#
#   bash tools/push_data_branch.sh RECEIPT
#
# - RECEIPT: 관문 단계가 PASS 한 뒤에만 쓰는 sha256 영수증(네 파일). 없거나, 네 파일이 다 없거나, 파일이 영수증과 다르면
#   아무것도 올리지 않고 멈춰요 (관문을 거치지 않은 데이터는 data 브랜치에 절대 들어가지 않아요).
# - data 브랜치의 커밋에는 이 네 파일만 들어 있어요 (코드 없음). 있으면 그 끝 위에 커밋 하나를 더하고, 없으면(이 버전의 첫 발행)
#   네 파일만 담은 첫 커밋으로 새로 만들어요. 바뀐 것이 없으면 커밋하지 않아요.
# - 강제 푸시는 하지 않아요. 그사이 누가 먼저 올렸으면 푸시가 거절되고 실행이 빨갛게 끝나요 (사이트는 그대로예요).
# - 작업 폴더·현재 브랜치는 건드리지 않아요 (git 의 저수준 명령으로 커밋을 직접 만들어요).
set -euo pipefail

RECEIPT="${1:?관문 영수증 파일 경로가 필요해요}"
REMOTE="${DATA_REMOTE:-origin}"
BRANCH="${DATA_BRANCH:-data}"
FILES=(corp.json data.json disc.json macro.json)

if [ ! -s "$RECEIPT" ]; then
  echo "!! 발행 관문 영수증이 없어요 ($RECEIPT) → data 브랜치에 올리지 않아요"
  exit 1
fi
listed=$(awk '{ sub(/^\*/, "", $2); print $2 }' "$RECEIPT" | sort | tr '\n' ' ')
if [ "$listed" != "corp.json data.json disc.json macro.json " ]; then
  echo "!! 영수증에 네 파일이 정확히 들어 있지 않아요 ($listed) → 올리지 않아요"
  exit 1
fi
if ! sha256sum --quiet --strict -c "$RECEIPT"; then
  echo "!! 파일이 관문을 통과한 것과 달라요 → data 브랜치에 올리지 않아요"
  exit 1
fi

set +e
git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null
rc=$?
set -e
parent=""
if [ "$rc" -eq 0 ]; then
  git fetch -q --depth=1 "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH"
  parent=$(git rev-parse "refs/remotes/$REMOTE/$BRANCH^{commit}")
  echo "· data 브랜치 끝: ${parent:0:7}"
elif [ "$rc" -eq 2 ]; then
  echo "!! data 브랜치가 아직 없어요 → 이 실행이 처음 만들어요 (관문을 통과한 네 파일만 담아요)"
  echo "::notice title=data 브랜치 처음 만듦::관문을 통과한 네 파일로 data 브랜치를 처음 만들어요 (v17.6). 사이트 배포가 여기서 데이터를 가져가요."
else
  echo "!! 원격 저장소에서 data 브랜치를 확인하지 못했어요 (git ls-remote 종료 코드 $rc) → 올리지 않아요"
  exit 1
fi

entries=""
for f in "${FILES[@]}"; do
  blob=$(git hash-object -w -- "$f")
  entries+=$(printf '100644 blob %s\t%s' "$blob" "$f")$'\n'
done
tree=$(printf '%s' "$entries" | git mktree)

if [ -n "$parent" ] && [ "$(git rev-parse "$parent^{tree}")" = "$tree" ]; then
  echo "· data 브랜치: 바뀐 것이 없어요 (커밋하지 않아요)"
  exit 0
fi

msg="데이터 갱신 $(TZ=Asia/Seoul date +%Y-%m-%d)"
export GIT_AUTHOR_NAME="baepsae-bot" GIT_AUTHOR_EMAIL="actions@github.com"
export GIT_COMMITTER_NAME="baepsae-bot" GIT_COMMITTER_EMAIL="actions@github.com"
if [ -n "$parent" ]; then
  commit=$(git commit-tree "$tree" -p "$parent" -m "$msg")
else
  commit=$(git commit-tree "$tree" -m "$msg")
fi
git push "$REMOTE" "$commit:refs/heads/$BRANCH"
echo "· data 브랜치에 올렸어요: ${commit:0:7} ($msg, 네 파일)"
