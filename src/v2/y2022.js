// 2022 calendar-year returns in won, for the plan's "fell like 2022" line (v18.3 Part B).
//
// Every figure is computed from real daily closes, stored below with its source and dates, so a test can recompute it
// (tests/test_v2_engine.py::test_2022_figures_recompute_from_closes).
// Source for all of them: Yahoo Finance chart API, daily bars, field "close" (price only, distributions excluded),
//   https://query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>?period1=1640217600&period2=1672704000&interval=1d
//   fetched 2026-11-01 by the 2.0 session. "from" is the last close of 2021, "to" the last close of 2022 (local dates).
// Cross-check (public, widely reported): KOSPI ended 2021 at 2,977.65 and 2022 at 2,236.40 (-24.9%);
// the S&P 500 ended 2021 at 4,766.18 and 2022 at 3,839.50 (-19.4%).
//
// Per holding (spec): that market's won return x the stock's beta; the cushion ETFs use their own 2022 return.
// If a holding has no figure (no beta, or an ETF not listed here), the plan hides the 2022 line.

export const Y2022_SOURCES = {
  kospi: { symbol: "^KS11", name: "KOSPI Composite Index", from: ["2021-12-30", 2977.65], to: ["2022-12-29", 2236.40] },
  sp500: { symbol: "^GSPC", name: "S&P 500 (USD)", from: ["2021-12-31", 4766.18], to: ["2022-12-30", 3839.50] },
  usdkrw: { symbol: "KRW=X", name: "USD/KRW", from: ["2021-12-31", 1189.89], to: ["2022-12-30", 1260.26] },
  // The two cushion ETFs (src/v2/engine.js CUSHION_ASSETS). KRX tickers, closes in won.
  "114260": { symbol: "114260.KS", name: "KODEX Treasury Bond 3Y", from: ["2021-12-30", 57815], to: ["2022-12-29", 56390] },
  "132030": { symbol: "132030.KS", name: "KODEX Gold Futures (H)", from: ["2021-12-30", 12135], to: ["2022-12-29", 11935] },
};

const ret = (k) => Y2022_SOURCES[k].to[1] / Y2022_SOURCES[k].from[1] - 1;

// Fractions (e.g. -0.2489 = -24.89%).
export const R2022 = {
  kr: ret("kospi"),                                          // -24.89%
  usWon: (1 + ret("sp500")) * (1 + ret("usdkrw")) - 1,       // S&P 500 in won: -19.44% in USD, won +5.91% -> -14.68%
  etf: { "114260": ret("114260"), "132030": ret("132030") }, // -2.46%, -1.65%
};
