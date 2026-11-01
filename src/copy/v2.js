// ================= 뱁새 2.0 (app.html) 문구 =================
// 2.0 화면의 한국어는 모두 여기에만 있어요 (src/v2/ 코드에는 한국어가 없어요: tests/test_v2_app.py 가 확인해요).
// 출처는 네 가지뿐이에요. 뒤의 주석이 출처예요.
//   숫자     docs/design/mockup-copy.csv 의 번호 (수정안, 비어 있으면 지금 문구). "바뀌는 글"은 {자리} 로 바꿨어요.
//   new      docs/tasks/v18.3-2.0-beta.md 의 "New strings" 표 (Jack 승인)
//   footer   CLAUDE.md 의 고정 문구
//   v17.5    지금 앱(src/detail.jsx)에 이미 있는 승인 문구 (불러오기 실패 · 날짜 · 배당 정보 없음 · 보통 해 ±)
//   spec     v18.3 스펙 본문이 그대로 쓰라고 한 말 (가치 카드의 "PBR 낮은 순"), REDESIGN §3 의 "검증 안 함" (Jack 승인)
//   preview  "예시 데이터" (CSV 3) — 미리 보기 페이지(app-preview.html)의 표시, Jack 승인 2026-11-01
// null = Jack 의 승인을 기다리는 문구 (docs/tasks/v18.3-new-strings-pending.md). 화면은 null 이면 그 줄을 빼요.
// {자리} 는 fill() 로 채워요. "\n" 은 CSV 의 " / " (줄바꿈) 예요.

export const C = {
  app: {
    title: "뱁새 2.0 미리 보기",                                   // new
    sample: "예시 데이터",                                          // 3 · preview
    brand: "뱁새",                                                 // 2
    footer: "교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다.", // footer · 27
    credit: "이성진, INSEAD MBA 26J",                              // footer · 27
    tabsLabel: "주요 메뉴",                                        // 28
    tabs: { today: "오늘", deck: "내 덱", build: "덱 짜기", search: "찾기" }, // 68 29 30 32
    loadFail: "데이터를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.", // v17.5 (T_LOAD_FAIL)
    loadFailAlt: "돋보기를 든 뱁이",                               // 42
    md: "{m}월 {d}일",                                             // 4 · 135 (날짜 부분)
    asOf: "{md} 기준",                                             // v17.5 (DateBadge)
    stale: "{n}일째 갱신이 멈췄어요",                               // v17.5 (DateBadge)
    usClose: "미국 종목은 현지 기준 {md} 종가예요.",                 // 26 (세 번째 문장)
    pending: "준비 중",                                            // new
    notChecked: "아직 자동으로 확인할 수 없어요",                    // new
    reportYear: "{year}년 사업보고서 기준",                         // new
    won: "{n}원",                                                  // 90
    man: "{n}만원",                                                // 45 · 64
    manUnit: "만원",                                               // 64
    about: "약 {x}",                                               // 524 · 527
    count: "{count}개",                                            // 195
    stocksN: "{n}종목",                                            // 424 ("6종목")
    deckName: "{name} 덱",                                         // 386 · 424
    none: "없음",                                                  // 234
    close: "닫기",                                                 // 558
  },

  store: {
    unavailable: "이 기기에서는 기록을 저장할 수 없어요. 브라우저 설정을 확인해 주세요.", // new
    export: "기록 내보내기",                                        // new
    import: "기록 불러오기",                                        // new
    safari: "사파리는 7일 넘게 열지 않으면 기록을 지울 수 있어요. 가끔 기록을 내보내 두세요.", // new
    importFail: null,                                              // pending: 기록 파일을 못 읽었을 때
  },

  today: {
    title: "오늘",                                                 // 19 · 68
    stale: "데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요", // new
  },

  deck: {
    title: "내 덱",                                                // 49
    mine: "내 종목 {n}개",                                         // 20
    holding: "{qty}주 · 평균 단가 {price}",                         // 72
  },

  build: {
    title: "덱 짜기",                                              // 162
    backToday: "오늘 화면으로 돌아가기",                            // 160
    prevStep: "이전 단계",                                         // 161
    restart: "다시 시작",                                          // 163
    stepsAria: "단계",                                             // 164
    steps: { start: "시작", cards: "기준", exclude: "빼기", terms: "조건" }, // 400 401 403 404 (테마 402 는 숨김)
    next: "다음",                                                  // 210
    matchSummary: "조건에 맞는 종목",                               // 209
    seeCands: "후보 {shortN}개 보기",                              // 211

    s0: {
      title: "어떻게 시작할까요?",                                  // 165
      body: "시작 덱을 고르면 카드가 미리 선택돼요. 다음 단계에서 언제든 바꿀 수 있어요.", // 166
      imgAlt: "전구를 든 뱁이",                                     // 167
      blank: "처음부터 직접 만들기",                                 // 168
      blankSub: "카드를 하나씩 직접 골라요",                          // 169
    },
    decks: {                                                       // 344-369 (덱 이름 · 한 줄 설명)
      steadyDiv: { name: "꾸준한 고배당", sub: "배당을 많이, 오래 주는 회사" },
      deepValue: { name: "저평가 가치주", sub: "이익과 자산에 비해 싼 회사" },
      garp: { name: "적정가 성장주", sub: "성장하는데 가격은 적당한 회사" },
      quality: { name: "장기 우량주", sub: "잘 벌고 부채가 적은 대형주" },
      cheapQuality: { name: "이익 대비 싼 우량주", sub: "수익성과 가격을 함께 보는 방식" },
      strict: { name: "깐깐한 기준", sub: "여러 기준을 모두 통과한 회사만 골라요" },
      lowVol: { name: "저변동 방어주", sub: "덜 떨어지는 회사 위주" },
      trend: { name: "추세 추종", sub: "최근 꾸준히 오른 회사" },
      payout: { name: "주주환원 확대", sub: "배당과 자사주 매입을 늘리는 회사" },
      theme: { name: "테마 집중", sub: "관심 테마에 크게 거는 덱" },
      krUs: { name: "한미 반반", sub: "한국과 미국에 반씩 나눠 담기" },
      income: { name: "배당 생활비", sub: "배당으로 생활비를 보태는 덱" },
      divGrowth: { name: "배당 성장주", sub: "배당을 해마다 늘리는 회사" },
    },

    s1: {
      title: "어떤 기준을 더 중요하게 볼까요?",                       // 170
      body: "점수 10점을 카드에 나눠 주세요. 점수를 많이 준 카드일수록 순위에 더 크게 반영돼요.", // 171
      pointsLeft: "남은 점수",                                      // 172
      strictLabel: "얼마나 깐깐하게 고를까요?",                       // 173
      strictAria: "얼마나 깐깐하게 고를까요",                         // 174
      strict: { loose: "넉넉하게", normal: "보통", strict: "깐깐하게", very: "아주 깐깐하게" }, // 238-241
      strictNote: "점수를 준 카드마다 상위 {pct}% 안에 들어야 후보에 올라요. 카드를 많이 고를수록 후보가 빠르게 줄어요.", // 242 + 243
      looseNote: "기준선 없이 점수 순서대로만 정렬해요.",              // 244
      topPct: "상위 {pct}%",                                       // 233
      inc: "{card} 점수 더하기, 지금 {n}",                           // 235
      dec: "{card} 점수 빼기",                                      // 237
      finNA: "금융회사는 해당 없음",                                  // new
      blanks: "자료가 없어 빠진 종목 {n}개",                          // new
      preview: "지금 기준 상위 3종목",                                // 206
      previewNone: "기준선을 모두 통과한 종목이 없어요",               // 411
      score: "{score}점",                                          // 427
    },
    cards: {                                                       // 212-231 (이름 · 기준 한 줄)
      value: { name: "가치", basis: "PBR 낮은 순" },                 // 212 · spec (PER 은 v18.0 에서 합류)
      div: { name: "배당", basis: "배당수익률 높은 순" },             // 214 215
      divGrowth: { name: "배당 성장", basis: "배당 연속 인상 기간 긴 순" }, // 216 217
      growth: { name: "성장", basis: null },                       // 218 · pending (매출만 봐요. "매출·이익" 은 사실과 달라요)
      profit: { name: "수익성", basis: "ROE 높은 순" },              // 220 221
      stable: { name: "재무 안정", basis: "부채비율 낮은 순" },         // 222 223
      lowVol: { name: "낮은 변동성", basis: "주가 변동 작은 순" },       // 224 225
      trend: { name: "추세", basis: "최근 1년 수익률 높은 순" },        // 226 227
      payout: { name: "주주환원", basis: "주주환원율 높은 순" },        // 228 229
      large: { name: "대형주", basis: "시가총액 큰 순" },             // 230 231
    },

    s3: {
      title: "빼고 싶은 종목이 있나요?",                              // 184
      body: "켜면 해당 종목은 후보에서 빠져요",                        // 185
      liquidity: "하루 평균 거래대금이 5억원보다 적은 종목은 항상 제외해요. 원하는 만큼 사고팔기 어렵기 때문이에요.", // 186
      switches: {                                                  // 324-339
        warned: { name: "투자주의·관리종목 빼기", sub: "거래소가 주의·경고한 종목" },
        loss: { name: "적자 회사 빼기", sub: "최근 1년 영업손실" },
        young: { name: "상장 2년 미만 회사 빼기", sub: "실적 이력이 짧아요" },
        debt: { name: "부채가 많은 회사 빼기", sub: "부채비율 200% 초과" },
        noDiv: { name: "무배당 회사 빼기", sub: "최근 1년 배당 0원" },
        china: { name: "중국 매출 비중이 큰 회사 빼기", sub: "중국 매출 비중 30% 초과" },
        sin: { name: "담배·술·도박 회사 빼기", sub: "업종 분류 기준" },
        holding: { name: "지주회사 빼기", sub: "자회사를 거느린 회사" },
      },
    },

    s4: {
      title: "마지막으로 조건을 정해 주세요",                          // 187
      amountLabel: "투자 금액",                                     // 188
      amountEmpty: "투자할 금액을 입력해 주세요. 만원 단위예요.",        // 374
      quick: ["+10만", "+100만", "+1,000만"],                        // 370-372
      clear: "지우기",                                              // 373
      under50: "50만원보다 적으면 여러 종목에 고르게 나눠 담기 어려워요.", // 375
      over10: "10억원이 넘으면 거래대금이 적은 종목은 원하는 만큼 사기 어려울 수 있어요.", // 582
      perStock: "한 종목에 약 {x}",                                  // 377
      mixLabel: "한국 : 미국",                                      // 190
      mixAria: "한국과 미국 비율",                                   // 192
      mix: { kr: "한국만", k73: "한국 7 : 미국 3", k55: "한국 5 : 미국 5", k37: "한국 3 : 미국 7", us: "미국만" }, // 387-391
      usWhole: "미국 주식은 1주 단위로 사요",                         // 191
      countLabel: "종목 수",                                        // 193
      countDec: "종목 수 줄이기",                                    // 194
      countInc: "종목 수 늘리기",                                    // 196
      countNote: "5~30개 · 종목이 적을수록 한 종목의 영향이 커져요",     // 197
      tooMany: "{amount}이면 {n}개 넘게 담기 어려워요. 1주 가격이 비싼 종목은 비중을 맞추기 힘들어요.", // 416 + 417
      methodLabel: "비중 정하는 방식",                               // 198
      method: { calm: "차분하게", even: "고르게", conviction: "확신대로" }, // 378-380
      methodNote: {                                                // 381-383
        calm: "변동이 작은 종목에 더 담아요. 시장이 나쁠 때 덜 떨어지는 경우가 많아요.",
        even: "기준에 맞는 정도와 변동성을 반반씩 반영해요.",
        conviction: "기준에 잘 맞는 종목에 더 담아요. 변동성은 보지 않아요.",
      },
      y2022Label: "2022년 같은 해가 오면",                            // 199
      y2022Empty: "금액을 입력하면 보여요",                            // 385
      eventNote: "공개매수·합병 같은 일이 걸린 종목은 어떤 방식을 골라도 적게 담아요.", // 200 (베타: 준비 중)
      maxLabel: "한 종목 최대 비중",                                  // 201
      cushionLabel: "안전자산 (채권·금)",                             // 202
      cushionNote: "주식과 다르게 움직일 때가 많아요",                   // 203
      cushionAria: "채권과 금 비중",                                  // 204
      nameLabel: "덱 이름",                                         // 205
      pinnedTitle: "꼭 담을 종목",                                   // 182
      pinnedBody: "꼭 담고 싶은 종목이 있다면 직접 추가할 수 있어요. 최대 3개까지예요.", // 183
      add: "담기",                                                 // 508
      remove: "빼기",                                              // 507
      addAria: "{name} 담기",                                       // 508
      removeAria: "{name} 빼기",                                    // 507
      added: "추가됨",                                              // 323
      fixed: "고정",                                               // 342
    },

    few: "기준선을 통과한 종목이 {n}개예요. 이대로 진행해도 되지만 종목을 고르기에는 후보가 적은 편이에요. 종목 수를 줄이거나 기준을 한 단계 낮춰 보세요.", // 413 + 414 + 415
    short: "기준선을 통과한 종목이 {n}개예요. 후보로 쓸 {need}개보다 적어요. 종목 수를 줄이거나 기준을 한 단계 낮춰 보세요.", // 413 + 414 + 409 + 410 + 415
    indFix: "기준을 한 단계 낮추거나 점수를 준 카드 수를 줄여 보세요.",        // 412 (두 번째 문장)
    zero: "기준선을 모두 통과한 종목이 없어요. 기준을 한 단계 낮추거나 점수를 준 카드 수를 줄여 보세요.", // 412
    lowerBtn: "기준을 낮춰 주세요",                                   // 418
    pickCardsBtn: "카드를 골라 주세요",                                // 419
  },

  pick: {
    title: "후보 고르기",                                           // 422
    back: "덱 짜기로 돌아가기",                                      // 421
    heading: "점수가 높은 {n}개를\n먼저 골라 뒀어요",                  // 425
    body: "자유롭게 빼고 넣어 보세요. 같은 업종은 2개까지 담을 수 있어요.", // 426
    worry: "주의할 점 · {worry}",                                   // 428
    receipts: "근거 수치",                                          // 429
    picked: "담은 종목",                                            // 432
    makePlan: "매수 계획 만들기",                                     // 433
    chooseN: "{n}개를 골라 주세요",                                   // 434
    usInd: "미국 · {ind}",                                          // 467
    market: { kr: "한국", us: "미국" },                              // 318 319
    limitN: "{n}개까지만 담을 수 있어요. 하나를 빼고 다시 골라 주세요.",  // 511
    limitInd: "같은 업종은 2개까지만 담을 수 있어요.",                   // 512
    finCo: "금융회사",                                              // 510
    unverified: "검증 안 함",                                        // spec (REDESIGN §3, 꼭 담을 종목)
    caution: {
      pbrHigh: "{metric} {x}배로 비싼 편이에요",                       // 497
      debtHigh: "부채비율 {pct}%로 높은 편이에요",                      // 498
      revFall: "매출이 2년째 줄고 있어요",                              // 503
      opFall: "영업이익 (작년 대비) {pct}",                              // 459 + 숫자 (2년 연속 줄었을 때)
      opFallFull: null,                                            // pending: 영업이익이 2년째 줄고 있어요
      divDrop: "{name} 배당이 줄었어요 · 주당 {a}원 → {b}원",            // new (확인 필요, 배당)
      divDropBody: "특별배당이나 액면분할 때문인지 확인해 주세요.",         // new (확인 필요, 본문)
      volHigh: null,                                               // pending: 주가 변동이 큰 종목
      checksRun: null,                                             // pending: 걸린 게 없을 때 확인한 항목
    },
    receipt: {
      yield: "배당수익률",                                           // 452
      debt: "부채비율",                                             // 458 (한국: 부채 ÷ 자기자본)
      debtUs: null,                                                // pending: 미국 부채비율 (차입금 ÷ 자기자본)
      times: "{x}배",                                              // 453
      growthKr: null,                                              // pending: 한국 성장 = 최근 2년 매출 증가율 (연평균)
      growthUs: null,                                              // pending: 미국 성장 = 최근 1년 매출 증가율
    },
  },

  plan: {
    title: "매수 계획",                                             // 516
    back: "후보 고르기로 돌아가기",                                   // 515
    methodLine: "{method} 나눠 담기",                               // 393 · 518
    ifBuy: "이대로 사면",                                           // 519
    left: "남는 돈 {leftText}",                                     // 520
    amountLabel: "투자 금액",                                       // 521
    div: "연 배당금 (지난 1년 기준)",                                 // 523
    preTax: "세전 금액이에요",                                       // 525
    divUnknown: "배당 정보가 없는 종목 {n}개는 0원으로 계산했어요.",     // v17.5 (T_DY_UNKNOWN)
    riskPartial: "일부 종목(비중 {pct}%)은 베타·변동성 자료가 없어요. 위험 수치는 나머지 종목으로 계산했어요.", // v17.5 (T_NORISK)
    riskNone: "담은 종목 모두 베타·변동성 자료가 없어 위험 수치를 계산할 수 없어요.", // v17.5 (T_RISK_BLIND)
    y2022: "2022년처럼 떨어지면",                                    // 526
    y2022Note: "2022년 시장 하락 폭을 바탕으로 어림한 값이에요",         // new
    volLine: "지금 예산 기준: 보통 해 ±{amt}만원 출렁",                // v17.5 (detail.jsx)
    stocks: "살 종목",                                              // 529
    targetNote: "주황색 선은 목표 비중",                               // 530
    shares: "{n}주",                                               // 531
    priceNote: "{md} 종가와 환율 {fx}원 기준이에요. 미국 주식은 1주 단위로 사요. 실제 매수 가격은 조금 다를 수 있어요.", // 532
    tooSmall: "{n}종목을 1주씩 사기에도 부족해요. 가장 싼 종목도 1주에 {price}이에요.", // 580 + 581
    weightAria: "비중",                                             // 60
    reason: {                                                      // 566-571 (비중 이유 한 줄)
      rank: "점수 {rank}위",
      indCap: "{ind} 업종은 최대 1/3",
      steadyMore: "변동이 작아 더 담음",
      steadyLess: "변동이 커서 조금 줄임",
      core: "핵심 종목",
      maxCap: "한 종목 최대 {pct}%",
      mktSteady: "{mkt} 비중 {pct}% 중 변동이 작은 쪽",
      mktVolatile: "{mkt} 비중 {pct}% 중 변동이 큰 쪽",
      pinned: "꼭 담을 종목",                                        // 182
      cushion: "안전자산 {pct}%",                                     // 395
      tooPricey: "1주 가격이 비싼 종목은 비중을 맞추기 힘들어요.",        // 417 (두 번째 문장) · 0주 줄
      liqCap: null,                                                // pending: 거래대금 한도에서 멈춤
    },
    clash: null,                                                   // pending: 지킬 수 없는 조건 문장 (지금은 조건 이름만 보여요)
    clashParts: { count: "종목 수", max: "한 종목 최대 {pct}%", ind: "{ind} 업종은 최대 1/3", mix: "한국 : 미국", liq: null, // 193 394 566 190
      indCount: "같은 업종은 2개까지만 담을 수 있어요." },              // 512
    rules: {
      title: "내 투자 규칙",                                         // 533
      intro: null,                                                 // 534 — 매일 점검·규칙 고치기는 Part C 에서 생겨요. 그때까지 빼요
      open: "{name} 규칙 보기",                                      // 550
      reason: "매수 이유",                                           // 536
      keep: "계속 지켜져야 할 조건 · 어긋나면 '지켜봐요'",                // 538
      sell: "매도 조건",                                             // 540
      band: "비중 규칙 · 목표 {pct}%",                                // 542
      bandText: "{a}% 미만이면 먼저 사요 · {b}% 넘으면 더 사지 않아요 · {c}% 넘으면 일부 팔아요", // 543
      priceNote: "주가가 많이 떨어졌다는 이유만으로는 어떤 규칙도 작동하지 않아요.", // 544
      dividend: "배당",                                             // 150
      divStreak: "{n}년 연속 늘렸어요",                               // 151
      divLimit: "줄이면 팔 때",                                       // 152
      dpsChange: "주당 {a}원 → {b}원",                                 // 10 · new (확인 필요, 배당)
      divCut: "배당 삭감",                                           // 9 · 541
      audit: "감사의견 문제",                                         // 541
      acquisition: "본업과 상관없는 대규모 인수",                        // 541
      embezzle: null,                                              // pending: 횡령·배임 공시
      debt: "부채비율",                                             // 153
      now: "지금 {x}%",                                             // 148 · 154
      over: "{x}% 넘으면 지켜봐요",                                    // 149 · 155
      roe: "ROE",
      roeLimit: null,                                              // pending: ROE 하한
      opProfit: "영업이익",                                          // 156
      opLimit: null,                                               // pending: 영업이익 2년 연속 감소 (연간)
      cet1: "CET1",
      kics: "지급여력비율",                                           // 485
    },
    deckWarn: {
      title: "이 덱의 주의점",                                        // 545
      rates: "금리가 크게 오르면 은행주와 배당주가 같이 떨어질 수 있어요.", // 546
      semi: "반도체 경기가 꺾이면 {name} 주가가 크게 흔들릴 수 있어요.",   // 547
      usTax: "해외 주식은 연간 양도차익 중 250만원을 넘는 부분에 22% 세금이 붙어요.", // 548 — 출처·연도 줄이 승인되면 보여요
      usTaxSource: null,                                           // pending: 2026년 세법 기준 (출처·연도)
      knew: "이런 이유로 떨어지는 건 처음부터 알고 시작한 일이에요.",       // 549
    },
    bought: "샀어요",                                               // 554
    boughtAria: "샀어요 기록",                                       // 555
    sheetTitle: "산 내용을 기록해 주세요",                             // 556
    sheetBody: "비워 두면 계획한 수량과 {md} 종가로 기록돼요.",          // 557
    date: "매수일",                                                 // 559
    qty: "수량 (주)",                                               // 560
    priceWon: "매수 가격 (원)",                                      // 574
    priceUsd: "매수 가격 (달러)",                                     // 573
    save: "기록하기",                                               // 561
    doneAlt: "기뻐하는 뱁이",                                        // 562
    done: "기록했어요",                                              // 563
    doneBody: null,                                                // 564 — 매일 점검은 Part C 에서 생겨요. 그때까지 빼요
    doneLink: "오늘 화면 보기",                                       // 565
  },
};

// "{name}" 자리를 채워요. 값이 없는 자리는 그대로 둬서 눈에 띄게 해요.
export function fill(tpl, vars) {
  return String(tpl).replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] != null ? String(vars[k]) : m));
}
