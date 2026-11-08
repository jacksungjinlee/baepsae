// ================= 뱁새 2.0 beta (app.html, v18.3 Parts A + B) =================
// Built by build-app.sh into app.html: live data from the same site (data.json, corp.json, macro.json).
// The current app (baepsae.html) is untouched.
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app.jsx";
import { loadAll, loadDisc, loadLogoIndex, LOGO_DIR, refetchNewer } from "./load.js";
import { setLogoSource } from "./logo.jsx";
import { STORE_KEY } from "./store.js";

// refetch (2026-11-08): a page brought back into view with stale data fetches the files once (app.jsx, load.js refetchNewer).
const LIVE = { preview: false, storeKey: STORE_KEY, exportPrefix: "baepsae-records", load: () => loadAll(), loadDisc: () => loadDisc(),
  refetch: (cur, disc) => refetchNewer(cur, disc) };
setLogoSource(loadLogoIndex, LOGO_DIR);           // v19.3a: company logos from this site's logos/ (the preview never does this)

createRoot(document.getElementById("root")).render(<App source={LIVE} />);
