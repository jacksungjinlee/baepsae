// ================= Company marks (v19.1a, docs/tasks/v19.1-company-page.md Part G) =================
// Wherever 2.0 lists a company (the company page, 종목, 포트폴리오, 홈, 거래대금 상위, 왜 움직였나) it shows this mark.
// Real logos wait for the provider test (Part L): until Jack picks a provider, LOGO_PROVIDER is null, so no <img> is
// drawn and no outside address is ever asked for (tests/test_v2_app.py and the smoke tests check zero outside requests).
// Every company shows the fallback: a rounded square in one of ten fixed colours (company.js markColor, by the code)
// with the first letter of the name in white. Never a grey placeholder, never a broken image, never a layout jump.
// The letter is drawn by CSS from data-initial (src/v2/template.html): a decoration, not text (aria-hidden).
//
// The hook for later (OFF now): a provider is { name, url(s) -> address or null }. Its image would load lazily on top of
// the mark (same box, so nothing moves), give up after LOGO_TIMEOUT_MS, and every failure is counted in the console.
import React, { useEffect, useState } from "react";
import { FONT, WEIGHT } from "../ui/tokens.js";
import { markColor, markLetter } from "./company.js";

export const LOGO_PROVIDER = null;          // v19.1 Part L decides. Until then: letter marks only, zero outside requests
export const LOGO_TIMEOUT_MS = 3000;
const stats = { marks: 0, failed: 0, said: false };
export const logoUrl = (s) => (LOGO_PROVIDER && s ? LOGO_PROVIDER.url(s) || null : null);

function sayOnce() {
  if (stats.said) return;
  stats.said = true;
  console.info("[v2] company logos: no provider yet (v19.1 Part L), every company shows its letter mark");
}
function failed(t, why) {
  stats.failed += 1;
  console.warn(`[v2] logo not shown for ${t} (${why}): letter mark instead · ${stats.failed} so far`);
}

// s: the stock row (or { t, nk }); name: the name to take the letter from (defaults to s.nk). size in px.
export function CoMark({ s, t, name, size = 36 }) {
  const code = t || (s && s.t) || "";
  const nk = name || (s && s.nk) || code;
  const url = logoUrl(s || { t: code, nk });
  const [img, setImg] = useState("wait");        // wait · shown · gone (only with a provider)
  stats.marks += 1;
  if (!url) sayOnce();
  useEffect(() => {
    if (!url) return undefined;
    const timer = setTimeout(() => setImg((x) => { if (x === "wait") { failed(code, "timeout"); return "gone"; } return x; }), LOGO_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [url]);
  const box = { width: size, height: size, borderRadius: Math.round(size * 0.28), flexShrink: 0, position: "relative", overflow: "hidden" };
  return (
    <span data-ui-v2="co-mark" data-t={code} aria-hidden="true" style={box}>
      <span data-initial={markLetter(nk, code)} style={{ position: "absolute", inset: 0, background: markColor(code), color: "#FFFFFF",
        display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT, fontWeight: WEIGHT.heavy,
        fontSize: Math.round(size * 0.44), lineHeight: 1, letterSpacing: 0 }} />
      {url && img !== "gone" && (
        <img src={url} alt="" loading="lazy" decoding="async" width={size} height={size} referrerPolicy="no-referrer"
          onLoad={() => setImg("shown")} onError={() => { failed(code, "error"); setImg("gone"); }}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", background: "#FFFFFF", opacity: img === "shown" ? 1 : 0 }} />
      )}
    </span>
  );
}
