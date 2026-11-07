#!/bin/bash
# v19.3a (docs/tasks/v19.3-portfolio-pictures-accounts.md Part J): 검사를 통과한 회사 로고 폴더를 logos 브랜치에 올려요.
# 사이트 배포(deploy.yml)가 data 브랜치의 네 JSON 과 함께 여기서 logos/ 를 가져가요. 로고는 main 에 절대 넣지 않아요.
#
#   bash tools/push_logos_branch.sh DIR        # DIR = logo-dev-fetch artifact 의 logos/ 폴더
#
# - 손으로만 돌려요: 세션이 logo-dev-fetch 의 artifact(요약 · 대조표)를 보고 난 뒤에. 그 workflow 는 읽기 권한만 있어요.
# - DIR 에는 index.json 과 .webp · .png 그림만 있어야 하고, index.json 과 그림이 서로 맞아야 해요 (tools/logos/logo_index.py:
#   빠진 그림 · 목록에 없는 그림 · 다른 이름 · 하위 폴더 · 링크 · SVG · 128 x 128 이 아닌 그림 · 너무 큰 파일 → 아무것도 올리지 않아요).
#   dropped/ 폴더(검사에서 빠진 그림)나, 오류 뒤 살려 낸 폴더(salvaged: 같은 그림 · 우선주 단계를 건너뜀)도 올리지 않아요.
# - logos 브랜치의 커밋에는 logos/ 폴더 하나만 들어 있어요 (코드 없음). 있으면 그 끝 위에 커밋 하나를 더하고, 없으면 처음 만들어요.
#   바뀐 것이 없으면 커밋하지 않아요. 브랜치 이름은 logos 로 정해져 있어요 (main · data 에는 절대 쓰지 않아요).
# - 강제 푸시는 하지 않아요. 그사이 누가 먼저 올렸으면 푸시가 거절되고 멈춰요 (사이트는 그대로예요).
# - 작업 폴더·현재 브랜치는 건드리지 않아요 (git 의 저수준 명령으로 커밋을 직접 만들어요).
set -euo pipefail

DIR="${1:?로고 폴더(artifact 의 logos/) 경로가 필요해요}"
REMOTE="${LOGOS_REMOTE:-origin}"
BRANCH="logos"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$DIR" ] || [ -L "$DIR" ]; then
  echo "!! 로고 폴더가 아니에요 ($DIR) → logos 브랜치에 올리지 않아요"
  exit 1
fi
if ! python3 "$HERE/logos/logo_index.py" publishable "$DIR"; then
  echo "!! 로고 폴더가 검사를 통과하지 못했어요 (위 줄) → logos 브랜치에 올리지 않아요"
  exit 1
fi
# 2026-11-07 (Jack): 회사 홈페이지 아이콘(route site)이 있으면, main 의 데이터 출처 줄이 "일부는 각 회사 홈페이지" 를 말한 뒤에만 올려요
if python3 "$HERE/logos/logo_index.py" has-site "$DIR"; then
  if ! git fetch -q "$REMOTE" main; then
    echo "!! main 을 받지 못해 데이터 출처 줄을 확인하지 못했어요 → logos 브랜치에 올리지 않아요"
    exit 1
  fi
  if ! git show "$REMOTE/main:src/info.jsx" 2>/dev/null | grep -q "일부는 각 회사 홈페이지"; then
    echo "!! 홈페이지 아이콘이 있는데 main 의 데이터 출처 줄에 '일부는 각 회사 홈페이지' 가 아직 없어요 → logos 브랜치에 올리지 않아요"
    exit 1
  fi
fi
ABS="$(cd "$DIR" && pwd)"

mapfile -t names < <(find "$ABS" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort)
for n in "${names[@]}"; do
  if ! [[ "$n" == "index.json" || "$n" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,23}\.(webp|png)$ ]]; then
    echo "!! 올릴 수 없는 파일이에요: $n → logos 브랜치에 올리지 않아요"
    exit 1
  fi
done
mapfile -t blobs < <(for n in "${names[@]}"; do printf '%s/%s\n' "$ABS" "$n"; done | git hash-object -w --stdin-paths)
if [ "${#blobs[@]}" -ne "${#names[@]}" ] || [ "${#names[@]}" -lt 1 ]; then
  echo "!! 파일을 git 에 담지 못했어요 → 올리지 않아요"
  exit 1
fi
sub=$(for i in "${!names[@]}"; do printf '100644 blob %s\t%s\n' "${blobs[$i]}" "${names[$i]}"; done | git mktree)
tree=$(printf '040000 tree %s\tlogos\n' "$sub" | git mktree)
# 커밋할 트리를 한 번 더 확인해요: logos/index.json 과 logos/ 의 그림만
while IFS= read -r p; do
  if ! [[ "$p" == "logos/index.json" || "$p" =~ ^logos/[A-Za-z0-9][A-Za-z0-9._-]{0,23}\.(webp|png)$ ]]; then
    echo "!! 트리에 다른 파일이 있어요: $p → 올리지 않아요"
    exit 1
  fi
done < <(git ls-tree -r --name-only "$tree")

# 정확히 refs/heads/logos 만 봐요 (ls-remote 의 이름 맞추기는 끝부분이라 refs/heads/누구/logos 도 걸려요)
if ! refs=$(git ls-remote "$REMOTE" "refs/heads/$BRANCH"); then
  echo "!! 원격 저장소에서 logos 브랜치를 확인하지 못했어요 (git ls-remote 실패) → 올리지 않아요"
  exit 1
fi
remote_tip=$(printf '%s\n' "$refs" | awk -v r="refs/heads/$BRANCH" '$2 == r { print $1 }')
parent=""
if [ -n "$remote_tip" ]; then
  git fetch -q --depth=1 "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH"
  parent=$(git rev-parse "refs/remotes/$REMOTE/$BRANCH^{commit}")
  echo "· logos 브랜치 끝: ${parent:0:7}"
else
  echo "!! logos 브랜치가 아직 없어요 → 처음 만들어요 (검사를 통과한 logos/ 폴더만 담아요)"
fi

if [ -n "$parent" ] && [ "$(git rev-parse "$parent^{tree}")" = "$tree" ]; then
  echo "· logos 브랜치: 바뀐 것이 없어요 (커밋하지 않아요)"
  exit 0
fi

pictures=$(( ${#names[@]} - 1 ))
msg="로고 갱신 $(TZ=Asia/Seoul date +%Y-%m-%d) (그림 ${pictures}개)"
export GIT_AUTHOR_NAME="baepsae-bot" GIT_AUTHOR_EMAIL="actions@github.com"
export GIT_COMMITTER_NAME="baepsae-bot" GIT_COMMITTER_EMAIL="actions@github.com"
if [ -n "$parent" ]; then
  commit=$(git commit-tree "$tree" -p "$parent" -m "$msg")
else
  commit=$(git commit-tree "$tree" -m "$msg")
fi
if [ -n "$parent" ] && ! git merge-base --is-ancestor "$parent" "$commit"; then
  echo "!! 새 커밋이 logos 브랜치 끝 위에 있지 않아요 → 올리지 않아요"
  exit 1
fi
# 처음이면 logos 브랜치를 새로 만들고, 그다음부터는 끝 위에 커밋 하나를 더하는 보통 푸시(fast-forward)만 해요.
# 강제 푸시 · 브랜치 지우기는 절대 하지 않아요 (이 세션의 git 프록시도 막아요).
if ! git push "$REMOTE" "$commit:refs/heads/$BRANCH"; then
  echo "!! logos 브랜치에 올리지 못했어요: 원격이 거절했어요 (그사이 누가 먼저 올려서 fast-forward 가 아니거나, 권한이 없어요)."
  echo "!! 강제로 올리지 않아요. 이 스크립트를 다시 돌리면 새 끝 위에 다시 만들어요. logos 브랜치와 사이트는 그대로예요."
  exit 1
fi
echo "· logos 브랜치에 올렸어요: ${commit:0:7} ($msg)"
