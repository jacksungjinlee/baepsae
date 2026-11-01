// ================= 뱁새 2.0 beta (app.html, v18.3 Parts A + B) =================
// Built by build-app.sh into app.html: live data from the same site (data.json, corp.json, macro.json).
// The current app (baepsae.html) is untouched.
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app.jsx";
import { loadAll } from "./load.js";
import { STORE_KEY } from "./store.js";

const LIVE = { preview: false, storeKey: STORE_KEY, exportPrefix: "baepsae-records", load: () => loadAll() };

createRoot(document.getElementById("root")).render(<App source={LIVE} />);
