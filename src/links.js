// ================= Addresses shared by the old app (baepsae.html) and 뱁새 2.0 (app.html) =================
// The 소개 (About) page lives in 2.0 under the hash #about (v19.0 Part D, Jack 2026-11-03). Footers link to it instead of a
// credit line. The old app may not import from src/ui (tests/test_styleguide.py), so the address lives here, once.
// No words here: each app keeps its own link label (old app: src/detail.jsx T.about, 2.0: src/copy/v2.js app.aboutLink).
export const ABOUT_HASH = "#about";
export const ABOUT_URL = "./app.html#about";   // from the old app: opens 2.0 on its 소개 page

// The old app as 2.0 opens it (CV link, Jack 2026-11-05). baepsae.html is on Jack's CV: a plain visit (no marker, no #) goes
// to 2.0 (template.html's first script). Every 2.0 link into the old app carries the marker ?from=app (routes.js OLD_LINKS
// adds the deep-link # after it). A query survives the old app's replaceState that clears the # after reading a deep link,
// so a reload stays in the old app. template.html reads the same "from=app" (tests/test_cv_link.py keeps them equal).
export const OLD_APP = "./baepsae.html?from=app";
