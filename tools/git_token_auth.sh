#!/usr/bin/env bash
# 발행 단계(커밋 & 푸시 · data 브랜치에 올리기)가 푸시 직전에 불러요: 이 작업의 GitHub 토큰을 git 에 알려 줘요.
#
# 왜 여기서: 예전에는 actions/checkout 이 토큰을 작업 폴더(.git/config)에 남겨 두어, 그 뒤의 모든 단계가 읽을 수 있었어요 —
# 데이터 수집 도구, 화면 검사 도구(npm · pip 패키지), 브라우저까지요. 이제 checkout 은 토큰을 남기지 않고
# (persist-credentials: false), 발행하는 두 단계만 자기 환경으로 토큰을 받아 여기서 설정해요 (Jack, 2026-11-12).
# 토큰은 화면에 찍지 않아요. 토큰이 없거나 GitHub 이 받아 주지 않으면 여기서 멈춰요 (푸시하지 않아요).
set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "!! GITHUB_TOKEN 이 이 단계의 환경에 없어요 → 푸시하지 않아요"
  exit 1
fi
REMOTE="${1:-origin}"
basic="$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
git config --local "http.https://github.com/.extraheader" "AUTHORIZATION: basic $basic"
# 토큰이 받아들여지는지 읽기로 먼저 확인해요 (틀린 토큰이면 공개 저장소라도 GitHub 이 거절해요)
if ! git ls-remote --exit-code "$REMOTE" "refs/heads/main" > /dev/null; then
  echo "!! 토큰으로 원격 저장소($REMOTE)를 읽지 못했어요 → 푸시하지 않아요"
  exit 1
fi
echo "· 푸시 권한 준비됨 (토큰은 이 단계부터만 git 이 알아요)"
