// ================= 기준 · 템플릿 그림 (v19.3b, docs/tasks/v19.3-portfolio-pictures-accounts.md Part A) =================
// One picture per 기준 everywhere a 기준 appears, each on its topic tint chip (CLAUDE.md tints: 가치 green, 배당 gold,
// 실적 blue, 출렁임·위험 lilac, teal for the rest). Templates have their own picture on the tint the board gives them.
// The files are Adobe Stock (free) and Microsoft Fluent Emoji 3D (MIT: pictures/LICENSE-fluent-emoji.txt) pictures,
// resized by tools/resize_pictures.py from docs/design/v19.3/assets/pictures (never redrawn or recoloured). They keep
// their own colours: the icon colour rules apply to Phosphor icons and to the chips, not to these pictures (Part M).
// The service worker keeps a copy for offline use (sw.js PICTURES; tests/test_pictures.py keeps the lists in step).
// No Korean here: names come from src/copy/v2.js.

// 기준 (engine.js CARDS ids) → picture + topic (src/ui/tokens.js TOPIC_CHIP key)
export const CARD_PICS = {
  value: { src: "pictures/fluent-label.webp", topic: "value" },
  div: { src: "pictures/adobe-coins.webp", topic: "div" },
  divGrowth: { src: "pictures/adobe-arrows-coins.webp", topic: "div" },
  growth: { src: "pictures/adobe-tree.webp", topic: "earn" },
  profit: { src: "pictures/adobe-profit.webp", topic: "earn" },
  stable: { src: "pictures/adobe-safe.webp", topic: "risk" },
  lowVol: { src: "pictures/fluent-turtle.webp", topic: "risk" },
  trend: { src: "pictures/adobe-chart.webp", topic: "disc" },
  payout: { src: "pictures/adobe-gift.webp", topic: "div" },
  large: { src: "pictures/adobe-bank.webp", topic: "disc" },
};

// Visible templates (engine.js DECKS without hidden) → picture + topic. topic null = the warm-grey chip (COLOR.select),
// as the board draws 깐깐한 기준.
export const DECK_PICS = {
  deepValue: { src: "pictures/fluent-magnifying-glass-tilted-left.webp", topic: "value" },
  garp: { src: "pictures/fluent-balance-scale.webp", topic: "earn" },
  quality: { src: "pictures/fluent-deciduous-tree.webp", topic: "earn" },
  strict: { src: "pictures/fluent-gem-stone.webp", topic: null },
  lowVol: { src: "pictures/fluent-umbrella.webp", topic: "risk" },
  trend: { src: "pictures/fluent-sailboat.webp", topic: "disc" },
  krUs: { src: "pictures/fluent-globe-showing-asia-australia.webp", topic: "disc" },
  income: { src: "pictures/fluent-shopping-cart.webp", topic: "div" },
};

// 가진 종목으로 시작하기 (the start card of v19.3c Part D): shipped and cached now, shown from v19.3c.
export const START_PICS = { holdings: { src: "pictures/adobe-wallet.webp", topic: null } };

// Chip and picture sizes (px): the picture sits in the middle of its chip. Part A: at 18–24 px some Adobe pictures go
// muddy, so a spot whose picture was hard to read in the 1× and 2× screenshots moved up one size on the board grid
// (row 20 → 24, fit 24 → 28: 성장 · 수익성 · 배당 at 1×, v19.3b).
export const PIC_SIZES = {
  row: { chip: 32, pic: 24 },      // a 기준 named inside a line of text (미리 보기 · 후보 · 근거 수치 · 매수 계획)
  fit: { chip: 40, pic: 28 },      // 기준 카드 list (one column until v19.3c) and 내 기준과 맞는 정도 rows on the company page
  card: { chip: 48, pic: 32 },     // 기준 카드: BuildCards2 (v19.3c's two-column cards)
  deck: { chip: 52, pic: 36 },     // template: BuildStart2
};
