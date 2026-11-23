// 예전 뱁새: 소액주주 배당수익률 표시 (2026-11-23; Jack 2026-11-19 Q6 "a later PR, labelled as the 소액주주 rate").
// The old app's 기업 분석 page shows the 사업보고서's own yield (corp.json dy). For a 차등배당 company that yield is the 소액주주 rate:
// the pipeline (fetch_data.small_holder_div) puts dpsSmall · dytSmall on a company only when the report's note says its dividend per
// share is what the small shareholders get (교보증권 2025: "기타주주(최대주주 외) 550원, 최대주주 무배당"), and the report works its yield
// from that figure. This switch adds the label to that tile's name. Off until Jack approves the label; with `on` true and `label` still
// null nothing changes either. The 2.0 app has its own switch (src/v2/smallcfg.js).
// An object, so the tests can build both states from one bundle; the app never writes to it.
export const SMALL_YIELD_OLD = {
  on: false,
  label: null,      // 제안 (Jack 승인 대기, 2026-11-23): "소액주주 기준" — 기업 분석의 '배당수익률' 칸 이름 옆 ("배당수익률 · 소액주주 기준")
};
const n = (x) => (typeof x === "number" && Number.isFinite(x) ? x : null);
// -> the label to put beside 배당수익률 for this corp.json company (or data.json stock), or null.
export function smallYieldLabel(row, cfg = SMALL_YIELD_OLD) {
  if (!cfg || !cfg.on || !cfg.label || !row) return null;
  return n(row.dpsSmall) > 0 && n(row.dytSmall) > 0 ? cfg.label : null;
}
