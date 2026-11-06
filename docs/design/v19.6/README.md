# v19.6 design hand-off (Jack's claude.ai design chat, 2026-11-06)

Boards for `docs/tasks/v19.6-records-alerts-dark.md`. Jack approved them on the private design board (version 54).
Read them for layout, sizes, colours and structure. All companies, logos and numbers are made up. Their Korean text is
final only where the task file's Appendix 1 lists it. Small grey lines that explain a board (not part of the screen)
are notes, not UI.

## Boards → screens

| Board | Screen | Task part |
|---|---|---|
| `Records2` | 팔았어요 · 배당 받았어요 | A |
| `Returns2` | 내 수익: 가진 종목 · 판 종목 · 받은 배당, 미국 종목 환율 split, 기록 내려받기 | A |
| `Today2` | 오늘 볼 것: 유상증자 · 전환사채 cards, 임원 지분 변동, 국민연금, 다가오는 일정 | B |
| `Watch2` | 관심 종목 with conditions | C |
| `Home2Dark`, `BuildCards2Dark`, `CoSummary2Dark`, `HomeMovers2Dark` | 어두운 화면 versions of approved boards | D |
| `Weekly2` | 이번 주 정리 | E |
| `TaxCheck2` | 연말에 확인할 숫자 | F |
| `ImportShot2` | 스크린샷에서 가져오기 | G |
| `Notify2` | 알림 받기 (the grey phone box shows how a push looks; it is not part of the screen) | H |

`dark-palette.py` is the colour mapping that made the dark boards from the light ones. It is a reference for Part D,
not app code.

## Image addresses inside the boards

The boards use the same pictures and 뱁이 mark as v19.3; `docs/design/v19.3/README.md` maps every `/_blob/…` address
to its file. The coloured company marks are invented shapes for invented companies. Never ship them as logos.
