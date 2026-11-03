# v19 design hand-off (Jack's claude.ai design chat, 2026-11-03)

Everything Claude Code needs for `docs/tasks/v19.0-layout-c.md`. Jack approved the design on the private design board;
this folder is the copy you can read.

## What is here

| Path | What it is |
|---|---|
| `assets/baepi-*.png` | Jack's new 뱁이 images (his own art, generated and approved by him). Trimmed to equal margins, 512 x 512 transparent PNG. `baepi-og.png` is the character only (614 x 712) for the link-preview image. |
| `assets/jack-photo.jpg` | Jack's headshot for the About page, 512 x 512, shown as a circle. Jack agreed it is public. |
| `copy/about.md` | The About page text, Korean and English, verbatim. |
| `reference/*.dc.html` | The approved design boards as HTML. Read them for layout, sizes, colours and structure. Their content (회사 이름, 숫자, 뉴스) is fictional example data, and Korean text that is not in the task file's 「새 문구」 tables is **not** approved copy. |
| `reference/canvas.json` | Board titles and positions (which board is which screen). |

## Images referenced inside the boards

The boards load images by an internal address. Map them to files like this:

| Address in the boards | File |
|---|---|
| `/_blob/1cee864feb9bb0d24d3b90385ebeb4ca` | `assets/baepi-mark.png` |
| `/_blob/149868f670ecf99f8142f4ab1e4580e3` | `assets/baepi-og.png` |
| `/_blob/bec0caa9f3df9547d5809bd03d9c08bc` | `assets/baepi-16-build.png` |
| `/_blob/646ee4136c3bdb7c6dd999127da8fce2` | `assets/baepi-15-portfolio.png` |
| `/_blob/a31d067bec1b3dfcd67eb30e61f34e5f` | `assets/baepi-20-error.png` |
| `/_blob/a06c355ee0c7cb0b0d0703122c8a6ac5` | `assets/baepi-22-safe.png` |
| `/_blob/42960797fadeaa61f7cdebb7449680f0` | `assets/baepi-17-import.png` |
| `/_blob/45129d48ec2c7b2a5586cd7fcc36d595` | `assets/baepi-18-rules.png` |
| `/_blob/ce3380a43d43b6eb7193a1b20a9bce77` | `assets/baepi-21-wip.png` |
| `/_blob/6d4ea2f88560769733c93af86e5b6ad4` | `assets/baepi-23-calendar.png` |
| `/_blob/32900419fad4d0f0e2f62703f047f241` | `assets/jack-photo.jpg` |
| `/_blob/7efdc18f…`, `e0ad76c3…`, `bf2b6c81…`, `e72b9260…`, `25ef598b…`, `893bb657…`, `adba5817…`, `815da92a…`, `77be5f1b…` | the existing `baepi-1` … `baepi-9` (wave, magnifier, chart board, lightbulb, happy, coin, laptop, sprout pot, sleeping) |
| `/_blob/61947ccb…` | Pretendard (already in `fonts/`) |

## Boards → screens

| Board | Screen |
|---|---|
| `NavC` / `NavCNew` | Phone 홈, with a portfolio / first visit |
| `Deck` | Phone 포트폴리오 tab (the current 내 덱 screen, renamed) |
| `CStock` | Phone 종목 tab |
| `CMarket` | Phone 시장 tab (segmented 금리·원자재 / 공시·수급) |
| `Menu` | Phone ☰ menu |
| `About` / `PcAbout` | 소개 page, phone / PC |
| `Main`, `Why`, `Build` | Today's verdict (state icon, no mascot), why it moved, 포트폴리오 만들기 start |
| `PcHome`, `PcHomeNew`, `PcMarket` | PC step 1 layouts (left menu, two columns) |
| `PcPortfolio`, `PcBuild`, `PcStock` | PC step 2 (later task): click-to-see detail, live build panel, company page |
| `OgPreview` | The link-preview image (1200 x 630) |
