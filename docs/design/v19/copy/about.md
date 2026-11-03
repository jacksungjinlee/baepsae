# 소개 (About) 페이지 문구 — Jack 승인 2026-11-03

아래 문구를 한 글자도 바꾸지 말고 그대로 써 주세요. 한국어가 기본이고, 페이지 맨 위의 한국어 / English 버튼으로 영어를 볼 수 있어요.
디자인은 reference/About.dc.html (휴대폰), reference/PcAbout.dc.html (PC)을 따라요.

**숫자 줄 규칙:** 분석 종목 = data.json에서 cls가 kr 또는 us인 종목 수, 업종 그룹 = 그 종목들의 ind 값 가운데 etc·other·빈 값을 뺀 서로 다른 개수. 본문의 "3,000개가 넘는"은 "{n}개가 넘는" 틀로 바꾸고 n은 분석 종목 수를 백 단위로 내린 값이에요 (예: 3,256 → 3,200). 데이터가 없으면 숫자 줄을 통째로 숨겨요. 숫자를 코드에 박아 두지 마세요.

## 한국어

- 머리글 (hero): **뱁새** / 내 기준으로 만드는 포트폴리오 / 철새처럼 옮겨 다니지 않는 투자
- 숫자 줄 (live figures): 3,256 분석 종목 · 57 업종 그룹 · 매 거래일 데이터 갱신  ← 숫자는 data.json에서 계산 (아래 규칙)

### 뱁새는 이런 도구예요

뱁새는 내 기준에 맞는 종목을 찾아 포트폴리오를 만들고, 정한 규칙대로 매일 점검하는 투자 도구예요.

거래일마다 3,000개가 넘는 한국·미국 종목의 데이터를 새로 받고, 정교하게 설계한 규칙 기반 알고리즘이 내 기준에 맞는 종목과 비중을 찾아 줘요. 종목마다 근거 수치를 함께 보여 줘서, 왜 이 종목이 뽑혔는지 직접 확인할 수 있어요.

- **기준으로 고르기** 가치, 배당, 성장, 수익성 같은 기준 카드에 점수를 나눠 주면, 한국과 미국 종목을 시장별로 비교해 순위를 매겨요.
- **비중까지 정하기** 한 업종에 몰리지 않도록 비중을 나누고, 살 주식 수까지 계산해요.
- **규칙으로 점검하기** 종목마다 매도 조건과 계속 지켜져야 할 조건을 정해 두고, 매일 종가와 새로 나온 실적으로 확인해요.
- **움직인 이유 보기** 주가가 크게 움직인 날에는 같은 업종 종목과 비교해, 업종 전체가 함께 움직였는지 보여 줘요.

### 누구를 위한 도구인가요

주식에 직접 투자하는 모든 개인 투자자를 위해 만들었어요.

- 뉴스나 주변 추천으로 샀다가, 언제 팔지 몰라 고민해 본 분
- 수익률은 매일 보지만, 왜 샀는지는 따로 적어 두지 않은 분
- 보유 종목을 감이 아니라 숫자와 규칙으로 관리하고 싶은 분
- 단기 수익보다 오래 지킬 수 있는 투자 원칙을 세우고 싶은 분

### 왜 만들었나요

뱁새는 제가 직접 투자할 때 쓰던 방법에서 시작했어요. 사기 전에 기준을 정하고, 산 뒤에는 미리 정한 규칙으로 판단하는 방법이에요.

가족과 친구들도 이 방법을 쓰고 싶어 했어요. 하지만 일반 증권사 앱에는 이런 기능이 없었고, 샤프 지수나 베타 같은 용어는 어렵게 느껴졌어요.

그래서 복잡한 계산은 뱁새가 맡고, 사용자는 기준과 결과에만 집중할 수 있는 도구로 만들었어요.

### 투자 원칙

1. **위험에는 그만한 보상이 따라야 해요.** 같은 수익이라면 덜 흔들린 투자가 더 좋은 투자예요. 그래서 감수한 위험 한 단위당 얼마를 벌었는지 보여 주는 샤프 지수를 중요하게 봐요.
2. **기준이 먼저, 종목은 그다음이에요.** 사기 전에 기준을 정하고, 산 뒤에는 기분이 아니라 규칙으로 판단해요.
3. **레버리지와 공매도는 다루지 않아요.** 둘 다 정당한 투자 수단이지만, 원금보다 큰 손실이 날 수 있어요. 일반 개인 투자자에게는 감수하는 위험에 비해 보상이 충분하지 않다고 봐서, 뱁새는 사서 보유하는 투자만 다뤄요.

### 이렇게 운영해요

- 거래일마다 종가와 공시 자료로 모든 숫자를 새로 계산하고, 숫자마다 기준일과 출처를 함께 적어요.
- 종목을 추천하거나 목표 주가를 제시하지 않아요. 판단에 필요한 숫자와 근거를 보여 드리고, 결정은 직접 내리실 수 있게 도와요.
- 광고, 유료 서비스, 회원 가입이 없어요. 내 포트폴리오 기록은 지금 쓰는 기기에만 저장돼요.

### 이름 이야기

뱁새라는 이름은 ‘뱁새가 황새 따라가다 가랑이 찢어진다’는 속담에서 왔어요. 속담 때문에 욕심 많은 작은 새로 알려졌지만, 실제 뱁새는 일 년 내내 우리나라에 머무는 텃새예요. 계절마다 옮겨 다니는 철새와 달리, 덤불 속에 튼튼한 둥지를 짓고 살아요. 유행을 따라 종목을 옮겨 다니지 않고, 내 기준으로 고른 종목을 오래 지키자는 뜻을 담았어요. 마스코트 뱁이도 이 뱁새에서 이름을 따왔어요.

### 뱁새를 만든 사람

**이성진** · 사업 개발 · 전략 · 투자 검토 (사진: assets/jack-photo.jpg, alt "이성진 사진")

- 학력: INSEAD MBA
- 경력 · 게임·엔터테인먼트 업계 6~7년:
    - Navi Games Agency — 게임 사업 개발 컨설팅
    - 넵튠 · 카카오게임즈 자회사 — 사업 개발, 전략, 투자 검토
    - TimeTree · 도쿄 — 글로벌 서비스 운영, 해외 시장 진출
- 서비스를 만들며:
    - 다양한 개인 투자자들의 의견을 듣고 서비스 방향을 정했어요.
    - INSEAD에서 배운 자산운용, 기업가치 평가, 헤지펀드, 통계 수업을 바탕으로 기준 카드, 비중 계산, 매일 점검 규칙까지 투자 로직을 직접 설계했어요.
    - 공시와 종가를 매일 자동으로 모으고, 잘못된 숫자가 보이지 않게 검증하는 데이터 체계를 만들었어요.
- 언어: 한국어 · 영어 · 일본어
- LinkedIn: https://www.linkedin.com/in/jacksungjinlee/


## English

- 머리글 (hero): **뱁새** / Build a portfolio on your own criteria / Don't hop from trend to trend
- 숫자 줄 (live figures): 3,256 stocks covered · 57 industry groups · Every trading day data refresh  ← 숫자는 data.json에서 계산 (아래 규칙)

### What Baepsae is

Baepsae is an investing tool that finds stocks matching your own criteria, builds a portfolio from them, and checks it against your rules every day.

Every trading day, fresh data for more than 3,000 Korean and US stocks comes in, and a carefully designed rule-based algorithm finds the stocks and weights that fit your criteria. Each stock shows its supporting figures, so you can see exactly why it was picked.

- **Pick by criteria** Spread points across criteria cards such as value, dividends, growth and profitability, and Baepsae ranks Korean and US stocks within each market.
- **Set the weights** Weights are spread so that no single industry dominates, down to the number of shares to buy.
- **Check by rules** Each holding gets sell conditions and conditions that must keep holding true, checked every day against closing prices and newly reported results.
- **See why it moved** On a big move, the stock is compared with its industry peers to show whether the whole industry moved with it.

### Who it is for

Every individual investor who buys stocks directly.

- People who bought on a tip and never knew when to sell
- People who check returns daily but never wrote down why they bought
- People who want to manage holdings by numbers and rules, not gut feeling
- People who want principles they can keep for decades rather than quick gains

### Why I built it

Baepsae started as the method I use for my own investing: set the criteria before buying, and judge only by pre-set rules afterwards.

Family and friends wanted to use it too, but ordinary brokerage apps offer nothing like it, and terms such as the Sharpe ratio and beta put most people off.

So Baepsae does the heavy calculation, and users can focus on their criteria and the results.

### What I believe about investing

1. **Risk should be paid for.** For the same return, the steadier investment is the better one. That is why I put weight on the Sharpe ratio, which shows how much return each unit of risk earned.
2. **Criteria first, stocks second.** Set the criteria before buying; afterwards, judge by rules, not mood.
3. **No leverage or short selling.** Both are legitimate tools, but losses can exceed what you put in. For most individual investors the reward does not justify that risk, so Baepsae covers buying and holding only.

### How it is run

- Every trading day, all numbers are recalculated from closing prices and filings, and each one shows its date and source.
- No stock tips or target prices. Baepsae shows the numbers and the reasoning; the decision is yours.
- No ads, no paid tier, no sign-up. Your portfolio records stay on your own device.

### The name

The 뱁새 (vinous-throated parrotbill) is the small bird in a Korean proverb about overreaching. The real 뱁새, though, stays in Korea all year and builds sturdy nests, unlike migratory birds that move with the seasons. The name stands for that: don't hop from trend to trend; pick by your own criteria and hold. The mascot, 뱁이, is named after it.

### The person behind Baepsae

**Jack (Sung Jin) Lee** · Business development · Strategy · Investment screening (사진: assets/jack-photo.jpg, alt "Photo of Jack (Sung Jin) Lee")

- Education: INSEAD MBA
- Experience · 6–7 years in games and entertainment:
    - Navi Games Agency — Business development consulting for games
    - Neptune · a Kakao Games subsidiary — Business development, strategy, investment screening
    - TimeTree · Tokyo — Global service and go-to-market
- Building the service:
    - Shaped the service around feedback from a wide range of individual investors.
    - Designed the investing logic, from criteria cards and position sizing to daily rule checks, drawing on INSEAD courses in asset management, valuation, hedge funds and statistics.
    - Built a data system that collects filings and closing prices every day and checks them before anything is published.
- Languages: Korean · English · Japanese
- LinkedIn: https://www.linkedin.com/in/jacksungjinlee/

