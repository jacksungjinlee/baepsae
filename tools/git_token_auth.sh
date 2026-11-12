#!/usr/bin/env bash
# 발행 단계(커밋 & 푸시 · data 브랜치에 올리기)가 푸시 직전에 불러요: 이 작업의 GitHub 토큰을 git 에 알려 줘요.
#
# 왜 여기서: 예전에는 actions/checkout 이 토큰을 작업 폴더(.git/config)에 남겨 두어, 그 뒤의 모든 단계가 파일로 읽을 수
# 있었어요 — 화면 검사 도구(npm · pip 패키지), 브라우저까지요. 이제 checkout 은 토큰을 남기지 않고(persist-credentials: false),
# git 은 발행하는 두 단계에서 여기서부터만 토큰을 알아요 (Jack, 2026-11-12). 줄인 것이지 막은 것은 아니에요: 데이터 수집과
# 관문 단계는 GitHub API 를 읽으려고 아직 자기 환경으로 토큰을 받아요 (같은 작업 안의 변조된 도구는 여전히 위험해요 —
# 읽기 전용 작업과 발행 작업을 나누는 것은 다음 일, docs/RUNBOOK.md).
# 토큰은 화면에 찍지 않아요. 토큰이 없거나 GitHub 이 받아 주지 않으면 여기서 멈춰요 (푸시하지 않아요).
set -euo pipefail
export GIT_TERMINAL_PROMPT=0     # 토큰이 안 먹으면 사용자 이름을 묻지 말고 바로 실패해요

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "!! GITHUB_TOKEN 이 이 단계의 환경에 없어요 → 푸시하지 않아요"
  exit 1
fi
case "$GITHUB_TOKEN" in
  *[[:space:]]*) echo "!! GITHUB_TOKEN 에 공백이 있어요 (값은 찍지 않아요) → 푸시하지 않아요"; exit 1 ;;
esac
REMOTE="${1:-origin}"
basic="$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
echo "::add-mask::${basic}"     # checkout 처럼: 이 값이 로그 어디에 나와도 *** 로 가려요 (토큰 자체는 GitHub 이 이미 가려요)
git config --local "http.https://github.com/.extraheader" "AUTHORIZATION: basic $basic"
# 토큰이 받아들여지는지 읽기로 먼저 확인해요 (틀린 토큰이면 공개 저장소라도 GitHub 이 거절해요). 네트워크가 잠깐 끊긴 것으로
# 발행이 멈추지 않게 세 번까지 해요 (5초 · 10초 쉬고). 이것은 토큰이 유효하다는 확인이지, 쓰기 권한까지 보는 것은 아니에요.
ok=""
for wait in 5 10 0; do
  if git ls-remote --exit-code "$REMOTE" "refs/heads/main" > /dev/null; then ok=1; break; fi
  if [ "$wait" -gt 0 ]; then echo "· 원격 저장소 읽기 실패 — ${wait}초 뒤 다시 해요"; sleep "$wait"; fi
done
if [ -z "$ok" ]; then
  echo "!! 토큰으로 원격 저장소($REMOTE)를 세 번 다 읽지 못했어요 → 푸시하지 않아요"
  echo "   바로 위 git 오류 줄을 보세요: 'Authentication failed' · 403 = 토큰 문제 · 'Could not resolve' · 'unable to access' · 시간 초과 = 네트워크 (다음 실행이 다시 해요)"
  exit 1
fi
echo "· 토큰 확인됨: GitHub 이 받아 줬어요 (git 은 이 단계부터만 토큰을 알아요)"
