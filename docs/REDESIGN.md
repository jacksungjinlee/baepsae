# 뱁새 2.0 — locked design (source of truth for v18.x)

**Status:** decided with Jack in claude.ai chat, 2026-10-31. Change only through a new decision from Jack.
**Read with:** `CLAUDE.md` (rules), `docs/BAEPSAE_VOICE.md` (Korean text), the task in `docs/tasks/`.
**Mockup:** Jack's clickable mockup "뱁새 2.0 목업" (claude.ai Design artifact, private to Jack). Everything a builder
needs from it is written below; where this file and the mockup disagree, this file wins.
All companies, news and numbers in the mockup are fictional.

## 1. What changes

뱁새 becomes a portfolio companion. The user builds a portfolio from their own idea with building-block cards. 뱁새 picks and
sizes the stocks by rules, writes a rule book for every holding, and checks the portfolio every day so the user doesn't
have to. It explains every move against the user's own rules. **No per-user AI.** The old build-it-yourself mode stays
(phase 3 improves it). Korean only until stable. No login (browser storage) for now.

Product rules from `CLAUDE.md` still hold: education, not advice; long-only; verdict first; won-first; 뱁이 only from
Jack's art; disclaimer footer on every screen.

## 2. The core principle: a rule engine, not a price watcher

Taken from how Jack actually runs his own portfolio. These are not optional.

1. **Daily decision order** (the whole daily check is this, in this order):
   1. Did a **sell condition** fire? → status **규칙 깨짐** (팔 차례).
   2. Is a **keep condition** failing? → status **지켜봐요**. No new money goes to it until the next filing or results.
   3. Is the **weight outside its band**? → 먼저 살 차례 / 그만 살 차례 / 줄일 차례.
   4. None of these → **할 일 없음**.
2. **Price never triggers a rule.** A price move alone means nothing happened. The rule engine must not be able to
   express a price-based rule (no "−25% from cost" rules, no stop-losses, no target prices). A daily move of ±5% or more
   only adds a "크게 움직인 종목" note with the news check and a link to 왜 움직였나.
   The one way prices matter: they change **weights**, and the weight bands (§4.1) act on weights. That is portfolio
   arithmetic, not a price rule.
3. **뱁새 never trades.** When a rule fires it says "내 규칙대로라면 팔 차례예요. 판단은 내가 해요." and offers
   팔았어요 / 더 지켜볼게요 / 규칙 고치기. The user records what they did.
4. **Every number shown carries its source and date.** Estimates are labelled 예상 (for example a Korean earnings date
   taken from last year's date). Stale inputs block the computation instead of producing a number.

## 3. Screens (bottom tabs: 오늘 · 내 덱 · 덱 짜기 · 찾기)

### 오늘 (daily, opens first)
- **Hero band = the rule verdict.** Three states:
  - 할 일 없음 (green band): "규칙이 깨진 종목은 없어요". If a holding moved ±5%+, a white inset row: "크게 움직인 종목 1개 ·
    뉴스 확인함 · 솔담정밀 −6.2% · 업종 전체가 빠졌어요. 규칙은 그대로예요." → 왜 움직였나.
  - Quiet: same green band, "새 공시도, 큰 움직임도 없어요."
  - 규칙 깨짐 (apricot band, "오늘 확인할 것 1개"): names the stock, the broken rule, the number and the filing date
    ("배당 삭감 · 주당 4,000원 → 3,200원 · 10월 30일 공시"), then the three buttons above.
- **Deck strip:** 지금 (value), 산 뒤로 (return since purchase). Today's % is a small grey line under them, not a headline.
- **My stocks list:** name + today's %. A chip only on exceptions (큰 움직임, 지켜봐요, 규칙 깨짐). No chip = fine.
- **다음 일정:** next 2 dated events (earnings, dividend record dates), with 예상 where estimated.
- Content dates: "10월 30일(금) 종가". Each market shows its own close date. After the Korean evening run (phase 4),
  US rows are a day older than Korean rows; say so on the screen.

### 내 덱 (the tracking sheet)
- Value, money put in, return vs KOSPI since start (line chart, KOSPI dashed).
- Per stock: shares, average cost, return, current weight vs target (bar with target marker), status note only when not
  normal ("지켜봐요 · 부채비율 88%, 기준 100%").
- **돈을 더 넣는다면:** typed amount (만원) with +10만 / +100만 / +1,000만 / 지우기. Fills the most underweight names first,
  **skipping 규칙 깨짐, 지켜봐요 and anything above 1.25× target**. Whole shares; shows 남는 돈.

### 왜 움직였나 (one stock, one day)
- Header: name, industry, official close, change, date.
- Verdict band: "할 일 없음 / 업종 전체가 빠진 날이에요 / 내 규칙 4개는 모두 괜찮아요."
- Three numbered checks, each one sentence + one picture:
  1. 나만 빠진 게 아니에요 — dot strip of every stock in the same industry group today, mine highlighted, group average
     marked.
  2. Why — rules-only version: "이유는 뉴스 제목으로 확인해요 · 공시 0건 · 업종 뉴스 3건" (headlines listed). AI version
     (phase 5, only if the blind test passes): a two-sentence summary labelled "AI가 뉴스 3건을 읽고 정리했어요".
  3. 내 규칙 — each rule as a check icon + "지금 22% · 30% 넘으면 지켜봐요". An explainer: 괜찮아요 → 지켜봐요 → 규칙 깨짐
     and the three choices.
- 다음에 볼 것 (dated, 예상 if estimated). Folded: past days in the last 3 years with a move of ±5% or more (same
  threshold as the big-move note; the mockup's "6%" text is outdated), split into same-industry vs alone; sources.

### 덱 짜기 (5 steps, live count of candidates in a bottom bar)
0. **시작:** blank deck, or one of 13 starting decks that pre-fill the cards (배당 꾸준형, 깊은 가치형, 합리적 성장형,
   우량주 장기형, 이익 대비 싼 우량주, 깐깐한 기준선형, 덜 흔들리는 방어형, 추세 따라가기형, 주주환원 기대형, 테마 집중형,
   한미 반반 균형형, 은퇴 현금 흐름형, 배당 성장형).
1. **기준:** 10 cards, formal name + sorting basis (CLAUDE.md rule): 가치 (PER·PBR 낮은 순), 배당 (배당수익률 높은 순),
   배당 성장 (배당 늘린 햇수 긴 순), 성장 (매출·이익 증가율), 수익성 (ROE), 재무 안정 (부채비율 낮은 순), 낮은 변동성
   (주가 흔들림 작은 순), 추세 (최근 1년 수익률), 주주환원 (배당+자사주 비율), 대형주 (시가총액 큰 순).
   - **10 points** spread across cards (max 5 per card) decide the ranking.
   - **"얼마나 깐깐하게 고를까요?"** one setting: 넉넉하게 (no cut-off) / 보통 (default: top 50%) / 깐깐하게 (top 30%) /
     아주 깐깐 (top 10%). The cut-off applies to every card that has points; each such card shows "상위 30%".
   - Live preview: "지금 기준 1~3등" with the reason ("배당 95점").
   - Warn when survivors < 2× stock count; block at zero.
2. **테마:** 45 themes in 9 groups, searchable by synonyms ("비만" → 비만 치료제), up to 5, plus the share of the deck
   that goes to theme stocks (20 / 40 / 60%). **꼭 넣을 종목** (up to 3): bypass screening, labelled "검증 안 함",
   still capped.
3. **빼기:** switches with the count each removes: 투자주의·관리종목 (on by default), 적자, 상장 2년 미만, 부채비율 200%+,
   무배당, 중국 매출 30%+, 담배·술·도박, 지주회사. A liquidity floor (daily trading value under 5억원) always applies.
4. **조건:** 넣을 돈 (typed, 만원, quick-add buttons, warnings under 50만원 and over 10억), 한국:미국 (한국만 / 7:3 /
   5:5 / 3:7 / 미국만), 종목 수 (5–30 stepper, warning when the amount is too small for that many), **나눠 담는 방식**
   (see §4.3), 한 종목 최대 비중 (10/15/20/25%), 채권·금 쿠션 (없음/10/20/30%).

### 후보 고르기
- Top 2× N candidates pre-selected N. Each row: score, industry, **life stage** (§4.4), one-line reason, **걱정되는 점**
  (the skeptic's case — always shown, never hidden), 근거 숫자 (expand: key ratios + cash-flow signs).
- Max 2 per industry group.

### 살 목록 · 샀어요
- Typed amount; whole US shares; 남는 돈; 1-year dividend (past year, pre-tax); "2022년처럼 빠지면 약 −X만원".
- Each stock: shares, amount, weight with target marker, **one-line reason for its weight**.
- 내 규칙서 per stock (§4.2) and **알고 시작하는 약점** for the deck (auto-suggested from its shape; the user can add).
- 샀어요: date, quantity, price per stock (blank = planned quantity at the last close). Stored in the browser only.

## 4. Engine rules

### 4.1 Bands (relative to each stock's target)
| Current ÷ target | Status | Action |
|---|---|---|
| < 0.75 | 먼저 살 차례 | New money goes here first |
| 0.75–1.25 | normal | none |
| > 1.25 | 그만 살 차례 | New money goes elsewhere |
| > 1.4 | 줄일 차례 | KR: trim back to target. US: propose a trim with a tax note ("해외 주식은 한 해 판 이익 중 250만원을 넘는 부분에 22% 세금이 붙어요") |

The US tax note must show its source and the year it was checked (Korean overseas-stock capital gains: 250만원 annual
deduction, 22% including local tax, as of 2026). Re-check yearly.

Dividends: pooled by currency, suggested into the most underweight names of the same currency, skipping 규칙 깨짐 and
지켜봐요 names.

### 4.2 Rule book per holding (generated, user-editable)
Three layers, each rule with a number, a source field and a freshness limit:
1. **Common to every stock → 규칙 깨짐:** dividend cut (regular DPS below the prior comparable period — mind frequency
   changes and special dividends), audit opinion other than 적정 / going-concern doubt, 횡령·배임 filing, a large
   acquisition unrelated to the core business.
2. **Industry module defaults** (sell or keep conditions): banks (CET1, DPS raised yearly, government dividend
   intervention), insurers (K-ICS vs regulator level, DPS promise), REITs (occupancy, dividend streak, investment-grade
   tenant share, top-tenant rent coverage), tobacco (guidance wording vs the previous statement, sanctions), pharma
   (top-product share, patent expiry, drug pricing), holding companies (look-through earnings, NAV discount vs own
   history, correlation with the largest subsidiary), rental/subscription (return-ratio policy, cancellations,
   controlling shareholder actions), growth names (free cash flow sign, share issuance).
3. **From the deck's own cards:** e.g. a dividend deck adds "배당 동결 → 지켜봐요"; a 재무 안정 card adds a debt ceiling.

Rules that need reading (guidance wording, "structural" decline, sanctions) are **warnings that put the stock in 지켜봐요
until the user confirms** — never automatic 규칙 깨짐. Vague words must become numbers or be marked "사람이 확인".

### 4.3 Sizing
Order: groups first, then stocks inside each group, then limits. Every target weight is stored with a one-line reason
and the date it was set.
1. **Groups from the user's own choices:** theme share (split across chosen themes), pinned stocks, cushion %, and the
   core (everything else). The Korea:US mix is applied across the core.
2. **Inside a group — 나눠 담는 방식 (user setting):**
   - 차분하게: more money to steadier stocks (inverse 3-year monthly volatility, extremes pulled to the average).
   - 고르게 (default): half fit (deck score), half steadiness.
   - 확신대로: by fit only; volatility ignored.
   Tilts stay within 0.6–1.4× of an equal weight.
   Each choice shows the won loss in a 2022-like year, computed from the actual list.
3. **Always, whatever the setting:** max per stock (user setting), max per industry group (default 1/3), half size for
   stocks with a pending event (tender offer, merger, governance dispute, listing under 2 years), position ≤ a set share
   of 20-day average trading value, whole shares for US, no leverage.
4. **Settings that can't all hold** (e.g. 5 stocks × 10% max = 50%; a 60% theme inside one industry with "max 2 per
   industry" and a 1/3 industry cap): the builder never relaxes a limit silently. It blocks, names the limits that
   clash in one sentence, and offers the fixes (more stocks, a higher max per stock, a smaller theme share). Theme
   stocks still count toward the industry cap.

### 4.4 Life stage (shown on candidates and holdings)
Signs of last year's operating / investing / financing cash flow (Dickinson 2011):

| Stage | Operating | Investing | Financing | Plain second line |
|---|---|---|---|---|
| 시작 | − | − | + | 아직 본업으로 돈을 못 벌어요 |
| 확장 | + | − | + | 벌면서 더 빌려 크게 투자해요 |
| 안정 | + | − | − | 번 돈으로 빚을 갚거나 돌려줘요 |
| 전환 | the other mixes | | | 방향을 다시 잡는 중일 때가 많아요 |
| 축소 | − | + | ± | 자산을 팔아 메우고 있어요 |

Banks, insurers and brokers show "단계 없음" (their cash flows don't fit this test).

### 4.5 Explanations
Every status quotes the rule, the number, the date and the source, in natural Korean (voice guide). Show the keep
conditions that still hold, so the user sees why nothing happened.

## 5. Data principles for everything new
- Rank factors **within each market** (KR and US separately). Never rank by a blank field; log coverage counts.
- Risk numbers (volatility, correlation) from **3 years of monthly data**; state the window wherever shown.
- Text jobs (filings, report text, news) run **once per stock, shared by all users**, never per user. Every
  AI-extracted value stores the document, section, the quoted sentence and the report date; values failing sanity
  bounds are rejected and logged.
- No login means the server cannot know what users hold: daily jobs cover every stock in the screened universe that has
  new filings that day.
- Personal data never enters the repo. Jack's own portfolio is a private reference only.

## 6. Build order (each phase ships through Claude Code with the v17.6 checks)

A **clean run** = a scheduled daily run that passes the publication gate and publishes, with the watchdog green and no
manual fix. Tasks marked **BLOCKED** are not started, even when they are the lowest version not DONE, until Jack says
"start vXX" in a session.

| Phase | Task file | Starts when | Gate to move on |
|---|---|---|---|
| 0 Safety | v17.5, v17.6 | now | 5 consecutive clean runs after v17.6 merges |
| 1 Data foundation | `v18.0-data-foundation.md` | phase-0 gate + Jack's "start" | New data passes the gate; thresholds approved |
| 2 Design system + copy file | `v18.1-design-system-and-copy.md` | phase-0 gate + Jack's "start" (may run beside phase 1) | Jack approves the look and the reviewed text |
| 1b Report-text data + theme tags | v18.2 (to be written) | after v18.0 | Extraction accuracy check passes |
| 3 Deck builder | v18.3 (to be written) | phases 1, 1b, 2 done | 3–5 of Jack's people finish a portfolio alone |
| 4 오늘 screen, news headlines, evening run | v18.4 (to be written) | phase 3 done | 2 weeks of use, 0 wrong facts |
| 5 AI news summaries | only after the Haiku/Sonnet blind test | Jack's decision | — |

The evening Korean run (approved by Jack, 2026-10-31) needs a change to the frozen v17.5 gate, which today requires the
published `pxDate` to be before today. v18.4 must propose that change under **안전 규칙 변경**: publish today's close only
from a final listing (after ~19:00 KST; start the schedule ~19:40 and verify), otherwise keep the morning data and log.

Later, not now: watchlist with re-analysis triggers, tax inputs (realized US gains, ISA/연금), account types, English,
second character, login.
