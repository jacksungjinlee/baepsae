# 2026-11-08 evening: status and open questions (for Jack and the design chat)

## Live today (each checked on the live site)
#84 tests · #86 CLAUDE.md say-why rule · #87 records hotfix · #88 footer · #85 new 홈 + company pages · #89 "being fixed" lines ·
#90 stale page refetch · #91 say-why lines · #93 period labels · #92 first-visit guide + new 포트폴리오 만들기 start ·
#95 being-fixed date → 11월 10일 · #94 v19.3d2 (가진 종목 넣기 −/+, + 종목 더하기, 내 규칙 정하기, 반도체·전자부품 group, phone-clock safety).

## Open PRs
- #96 say-why batch 2 — ready; needs Jack's yes on 9 one-for-one smoke_v2 lines (meter counts one company once).
- #97 app lines for the DART re-read — ready; needs Jack's yes on the smoke_app gate_card("en") edit and the decisions below.
- #71 v19.7 spec — edited on its branch (docs/v19.7-portfolio-edit, head 8a7e478) for Jack to check on GitHub.

## DART re-read (branch claude/interest-reread, head 3d91926)
- Monday after 08:30 KST: a full DART branch test run (Monday's one full run).
- Tuesday after the 08:17 scheduled publish: merge #97, then the re-read PR, then main's manual full run (~13,300 DART calls).

## #71 (v19.7 spec) — what changed on its branch
1. Part D [B3]: the one "내 기준 상위 x%" number appears only in the finder, the compare screen, 종목 바꾸기's 담기 sheet and 홈's 내 기준 list. 점검 stays as it is. Part A's 목표 비중 rows don't show it (no place on the approved board).
2. Part A new [D2] "When the cap can't reach 100%": when n × cap < 100, 바꾼 내용 저장 is off; the line "종목이 {n}개뿐이라, 한 종목을 최대 {x}%까지만 담으면 합계가 100%가 되지 않아요." and the button "최대 비중을 {y}%로 올리기" (y = 100 ÷ n rounded up) replace "합계를 100%로 맞추기". The button raises 최대 비중 to y, shares out what's missing, and is saved by 바꾼 내용 저장 (planPx kept; plannedQty recomputed as in C3). In the 빼기 sheet, 팔고 빼기 stays off until the button is tapped, then saves the sale, the removal and the new cap in one step. Edge cases: n × cap = 100 → no line; y never above 100.
3. Part B: a pointer to D2. Appendix 1: the two new lines. v19.5 line 60: the 내 기준 list number is the v19.7 [B3] number.
Choices to confirm: Part A rows don't show the number; only 팔고 빼기 is blocked in the 빼기 sheet; "합계를 100%로 맞추기" hidden while the D2 line shows.
Still open in that spec: h (cushion funds vs the cap), i (B4), a–g, j, k (how a 16.67% target steps), l, m (the 5억 floor in 상위 x%).
