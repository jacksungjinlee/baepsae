// ================= One rounding for every signed percent in 2.0 (Track 2 audit 4.10) =================
// Pure, no imports: src/ui/components.jsx (ListRow, DotStrip) and src/v2/deckcalc.js signedPct both read it, so a stock's
// 오늘 등락률 shows the same digits on every screen. Before, 홈 rounded with Math.round (−3.95 → −3.9, +3.95 → +4.0) and the
// list rows with toFixed (+0.15 → +0.1 because 0.15 is stored as 0.1499…, +0.25 → +0.3): on the 11-24 publish 144 stocks read
// 0.1%p apart. data.json d1 has two decimals, so a d1 ending in 5 sits exactly halfway and the file alone cannot say which side
// the true change is on (worked back from the closes, it is either side about half the time). The rule is the usual one: a half
// goes away from zero, so a rise and a fall of the same size read the same.

// The percent as shown, one decimal: a half away from zero on the number as written (3.95 → 4.0, −3.95 → −4.0, 0.15 → 0.2).
// The ×10 is cut to 12 significant digits first, so floating-point noise (4.35 × 10 = 43.49999999999999) never decides a
// half. Never −0 (−0.04 → 0). A screen that colours by the value as shown reads this, so its colour and its text agree.
// Not a number in, NaN out (null reads as 0, as Math.round did).
export const shownPct = (v) => {
  const a = Math.round(Number((Math.abs(v) * 10).toPrecision(12))) / 10;
  return v < 0 && a > 0 ? -a : a;
};

// "+4.0%" · "−4.0%" · "0.0%": the sign follows the shown value (−0.04 is "0.0%", never "−0.0%"), the minus is U+2212 and
// thousands take a comma (ko-KR, like format.js nf).
export const signedPct = (v) => {
  const r = shownPct(v);
  const digits = Math.abs(r).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${r < 0 ? "−" : r > 0 ? "+" : ""}${digits}%`;
};
