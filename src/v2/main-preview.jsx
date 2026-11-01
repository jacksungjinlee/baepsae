// ================= 뱁새 2.0 preview (app-preview.html) =================
// The same app as app.html, on embedded FICTIONAL example data (src/preview/fictional.json): no data file is fetched,
// every screen carries the "예시 데이터" label, records use their own storage key, and the page is linked from nowhere.
// The example data has a fixed publish date, so the stale check is off here (resolveLoad's preview option).
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app.jsx";
import { resolveLoad } from "./load.js";
import { PREVIEW_STORE_KEY } from "./store.js";
import { R2022 } from "./y2022.js";
import FICTION from "../preview/fictional.json";

// The fictional bond and gold funds stand in for the real cushion funds and borrow their real 2022 returns ("like").
const r2022 = { ...R2022, etf: { ...R2022.etf } };
for (const c of FICTION.cushion) r2022.etf[c.t] = R2022.etf[c.like];
const cushion = FICTION.cushion.map((c) => ({ t: c.t, share: c.share }));
const ok = (d) => ({ ok: true, data: d, error: null });

const PREVIEW = {
  preview: true, storeKey: PREVIEW_STORE_KEY, exportPrefix: "baepsae-preview-records",
  load: () => Promise.resolve(resolveLoad({ data: ok(FICTION.data), corp: ok(FICTION.corp), macro: ok(FICTION.macro) }, undefined,
    { preview: true, cushion, r2022 })),
};

createRoot(document.getElementById("root")).render(<App source={PREVIEW} />);
