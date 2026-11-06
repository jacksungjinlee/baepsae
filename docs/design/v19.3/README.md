# v19.3 design hand-off (Jack's claude.ai design chat, 2026-11-06)

Boards and pictures for `docs/tasks/v19.3-portfolio-pictures-accounts.md`. Jack approved the design on the private design
board (version 48). Read the boards for layout, sizes, colours and structure. All companies, logos and numbers on them
are made up. Their Korean text is final only where the task file's 「새 문구」 table lists it.

These boards replace `PfStart`, `PfEdit` and `PfReport` in `docs/design/v19.1/` (the planned v19.1b screens).

## Boards → screens

| Board | Screen | Task part |
|---|---|---|
| `VisualKit` | Picture language: one picture and one tint per 기준, mini infographics | A |
| `BuildStart2` | 포트폴리오 만들기 · 시작 (two ways in, templates as recipe cards) | D |
| `BuildCards2` | 기준 카드: 10 points, 10-slot meter, live company count | D |
| `PcStart2` | PC: left menu, account box at the bottom left, 3-column templates | D, K |
| `Guide2a` … `Guide2d` | First visit: welcome, then 직접 해 보기 steps 1/3 to 3/3 | E |
| `Import2` | 가진 종목 넣기 (search, paste, amount mode, optional 평균 단가) | F |
| `Report2` | 내 포트폴리오 점검 | G |
| `Home2` | 홈: rules hero, account banner, 내 수익 (no 3-month line yet) | H |
| `CoSummary2`, `CoValue2`, `CoDiv2`, `CoSummaryUS` | Company page updates (Korea, US) | I |
| `Signup2`, `Login2`, `Menu2` | Accounts: sign-up, login + merge choice, menu | K |

## Pictures (`assets/pictures/`)

Web-size copies only: Adobe pictures 192 × 192 px, Fluent pictures 128 × 128 px, transparent PNG. **Never commit larger
Adobe files** (licence: see `LICENSES.md`). Fluent originals at 256 px are at
`https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/<Name>/3D/<name>_3d.png` if a sharper copy is needed.

| 기준 (engine card id) | Picture | Tint family |
|---|---|---|
| 가치 (`value`) | `fluent-label.png` | 가치 green |
| 배당 (`div`) | `adobe-coins.png` | 배당 gold |
| 배당 성장 (`divGrowth`, 준비 중) | `adobe-arrows-coins.png` | 배당 gold |
| 성장 (`growth`) | `adobe-tree.png` | 실적 blue |
| 수익성 (`profit`) | `adobe-profit.png` | 실적 blue |
| 재무 안정 (`stable`) | `adobe-safe.png` | 출렁임·위험 lilac |
| 낮은 변동성 (`lowVol`) | `fluent-turtle.png` | 출렁임·위험 lilac |
| 추세 (`trend`) | `adobe-chart.png` | teal |
| 주주환원 (`payout`, 준비 중) | `adobe-gift.png` | 배당 gold |
| 대형주 (`large`) | `adobe-bank.png` | teal |

| Template (engine id) | Picture |
|---|---|
| 저평가 가치주 (`deepValue`) | `fluent-magnifying-glass-tilted-left.png` |
| 적정가 성장주 (`garp`) | `fluent-balance-scale.png` |
| 장기 우량주 (`quality`) | `fluent-deciduous-tree.png` |
| 깐깐한 기준 (`strict`) | `fluent-gem-stone.png` |
| 저변동 방어주 (`lowVol`) | `fluent-umbrella.png` |
| 추세 추종 (`trend`) | `fluent-sailboat.png` |
| 한미 반반 (`krUs`) | `fluent-globe-showing-asia-australia.png` |
| 배당 생활비 (`income`) | `fluent-shopping-cart.png` |
| 가진 종목 (start card) | `adobe-wallet.png` |

## Image addresses inside the boards

| Address | File |
|---|---|
| `/_blob/5a47716d85af044ecd79c26f6e255d9e` | `assets/pictures/fluent-label.png` |
| `/_blob/f1682d115b26483b6f23f55d666d0b95` | `assets/pictures/adobe-coins.png` |
| `/_blob/85f19ac00e590d9a411a71d168f7ef27` | `assets/pictures/adobe-arrows-coins.png` |
| `/_blob/ce46d3beba67b824e4d7a182ce9a4faf` | `assets/pictures/adobe-tree.png` |
| `/_blob/c28b92508d6998115e71e3b1e7d2afb9` | `assets/pictures/adobe-profit.png` |
| `/_blob/25a91461eba59cf801f9fdb0b49d7486` | `assets/pictures/adobe-safe.png` |
| `/_blob/d90598992be3ecc7cfe1370e649ef19f` | `assets/pictures/fluent-turtle.png` |
| `/_blob/dc1ffc6ea46a5ab444ce55fdf6c1c334` | `assets/pictures/adobe-chart.png` |
| `/_blob/b3f1ef1c548161262d65bcaa01f9aabf` | `assets/pictures/adobe-gift.png` |
| `/_blob/d7da0e1e978acdc3eee75e52d0cdcb77` | `assets/pictures/adobe-bank.png` |
| `/_blob/99e5e20d04e0fad15955fa577a5d2c58` | `assets/pictures/adobe-wallet.png` |
| `/_blob/7e2d6325e09276caeaa2ce37c2fcaff2` | `assets/pictures/fluent-magnifying-glass-tilted-left.png` |
| `/_blob/7c58719fcacc51f101cec52fc2cd7a4b` | `assets/pictures/fluent-balance-scale.png` |
| `/_blob/e478bc67473728da7ee0f52b5b4b927e` | `assets/pictures/fluent-deciduous-tree.png` |
| `/_blob/192c5f964807ef6f4fbb1355dbb2ab44` | `assets/pictures/fluent-gem-stone.png` |
| `/_blob/d19662494454bba9fc94861f08ec7c0e` | `assets/pictures/fluent-umbrella.png` |
| `/_blob/aa94dcf13cd23aedc3657f1803a5338d` | `assets/pictures/fluent-sailboat.png` |
| `/_blob/cf7b204982bedf6488f7d5146d21f6f5` | `assets/pictures/fluent-globe-showing-asia-australia.png` |
| `/_blob/30631b9266bb8d194d677629ddd1f1a1` | `assets/pictures/fluent-shopping-cart.png` |
| `/_blob/1cee864feb9bb0d24d3b90385ebeb4ca` | `../v19/assets/baepi-mark.png` |
| `/_blob/bec0caa9f3df9547d5809bd03d9c08bc` | `../v19/assets/baepi-16-build.png` |
| `/_blob/b3c3af1176e32b0a827de1bcfa0cc13f` | `../v19/assets/baepi-15-portfolio.png` |
| `/_blob/61947ccbd94ccbe1efb143237a83363c` | Pretendard (already in `fonts/`) |

The coloured company marks on the boards are invented shapes for invented companies. Never ship them as logos.
