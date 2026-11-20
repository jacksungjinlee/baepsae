// ================= 종목 바꾸기 · 내 기준으로 찾기 · 두 종목 비교: pieces the three screens share (v19.7b) =================
// Moved out of editor.jsx unchanged (v19.7a), so finder.jsx and compare.jsx can use them without importing the editor screen:
// the 업종 비중 bar, a target as shown, and the 재무 경고 row of the 담기 sheet (the company page's rule). No Korean here.
import React from "react";
import { COLOR, SIZE, WEIGHT, SPACE, holdingShades, HOLDING_SHADES } from "../ui/tokens.js";
import { C, fill, nf } from "./format.js";
import { tx } from "./ui.jsx";
import { warnings } from "./warn.js";
import { icrOffShown } from "./fix.js";
import { warnKind, uncheckedCount } from "./company.js";
import * as E from "./edit.js";

export const pctText = (p) => { const x = E.pctShown(p); return nf(x.n, x.d); };

// The stacked bar of target weights by industry group, with its legend (navy shades by weight, never logo colours).
export function IndBar({ parts }) {
  const shades = holdingShades(parts.map((p) => p.pct));
  const total = parts.reduce((a, p) => a + p.pct, 0) || 1;
  return (
    <div data-ui-v2="edit-ind-bar">
      <div aria-hidden="true" style={{ display: "flex", gap: 2, borderRadius: 7, overflow: "hidden", height: 14, background: COLOR.page }}>
        {parts.map((p, i) => <span key={p.key || "none"} style={{ width: `${(p.pct / total) * 100}%`, background: shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1] }} />)}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap" }}>
        {parts.map((p, i) => (
          <span key={p.key || "none"} data-ui-v2="edit-ind-part" data-ind={p.key} data-pct={Math.round(p.pct * 100) / 100}
            style={{ ...tx(SIZE.xs, WEIGHT.regular, COLOR.neutral), display: "inline-flex", alignItems: "center", gap: 5, margin: `${SPACE(2)}px ${SPACE(3)}px 0 0` }}>
            <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 3, background: shades[i] || HOLDING_SHADES[HOLDING_SHADES.length - 1], flexShrink: 0 }} />
            {p.cushion ? C.build.s4.cushionLabel : p.name || C.rpt.noInd} <b style={{ color: COLOR.ink }}>{pctText(p.pct)}%</b>
          </span>
        ))}
      </div>
    </div>
  );
}

// The 재무 경고 row of the 담기 sheet (pure; tests). The company page's rule (company.js warnKind, Jack 2026-11-14): a count when
// a check fired, "…없어요" only when every check ran, "확인한 …" when only some did (PR #68's case and the "some" case), "재무 경고"
// when none could run. A short line here: no ✓ chips in this sheet (as for "없어요"); under the row the company page's reason
// lines: the 이자보상배율 one (warn.js icrIe), "4가지 중 {k}가지는 …" for the other checks that could not run, and "필요한 자료가
// 없어서 확인하지 못했어요." when none could. s: the data.json row · co: its corp.json row.
// -> { w, kind, warnLine, unchecked, why, whyKind: "noIcr" | "count" | "noData" | null }
export function addWarnView(s, co) {
  const w = s && s.cls === "kr" ? warnings(s, co) : null;
  const W = C.co.warn;
  const kind = warnKind(s, w);
  const warnLine = kind === "flags" ? fill(W.count, { n: w.flags.length }) : kind === "partial" || kind === "some" ? W.nonePartial : kind === "none" ? W.none : null;
  const unchecked = kind === "unchecked" && !!C.rank.warn && !!W.noData;      // "재무 경고" in the row, Jack's reason line under it
  const noIcr = w && w.icrIe && W.noneSubNoIcr ? W.noneSubNoIcr : null;
  const k = (kind === "flags" || kind === "some") ? uncheckedCount(w, s.cls === "kr" && icrOffShown(co)) : 0;
  const cnt = k && W.uncheckedN ? fill(W.uncheckedN, { k }) : null;
  const why = noIcr || cnt || (unchecked ? W.noData : null);
  return { w, kind, warnLine, unchecked, why, whyKind: noIcr ? "noIcr" : cnt ? "count" : why ? "noData" : null };
}

