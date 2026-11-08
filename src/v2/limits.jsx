// ================= 내 규칙 정하기 (v19.3d2) =================
// The two limits a 가진 종목 portfolio's concentration rules use (pf.js limitsOf): 한 종목 {x}% 이하 and 한 업종 {x}% 이하,
// kept in the portfolio's `limits { stock, ind }` (store.js: whole % 1-100). Address #portfolio/rules/<deck id>.
// The fields start at the portfolio's current limits; 처음 값으로 되돌리기 puts back 30% and 35% (not saved until 저장).
// 저장 writes through setStoreData, which never writes records that would not read back (app.jsx: the refused line
// shows then). A limit equal to its default is not stored; the portfolio keeps when they were saved (limitsTs, pf.js).
// No 뱁이 (numbers). No Korean here: src/copy/v2.js.
import React, { useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Button } from "../ui/components.jsx";
import { C, fill, todayKst } from "./format.js";
import { Page, AppBar, ScreenTitle, Card, Note, Footer, tx } from "./ui.jsx";
import { LIMITS, limitsOf, readLimit, withLimits } from "./pf.js";
import { shownName } from "./legacy.js";
import { validStore, versionFor } from "./store.js";


// One limit: its rule as a whole line ("한 종목 40% 이하", the typed value while it is valid, else the saved one), then the field.
function LimitField({ id, tpl, value, saved, onChange, first }) {
  const v = readLimit(value);
  const line = fill(tpl, { x: v != null ? v : saved });
  return (
    <label data-limit={id} style={{ display: "flex", alignItems: "center", gap: SPACE(2), padding: `${SPACE(3)}px 0`, borderTop: first ? "none" : `1px solid ${COLOR.line}` }}>
      <span data-ui-v2={"limit-line-" + id} style={tx(SIZE.body, WEIGHT.bold, COLOR.ink, { flex: 1, minWidth: 0 })}>{line}</span>
      <input type="text" inputMode="numeric" value={value} aria-label={line} aria-invalid={v != null ? undefined : "true"} data-ui-v2={"limit-" + id}
        onChange={(e) => onChange(e.target.value.replace(/[^\d]/g, "").slice(0, 3))}
        style={{ width: 72, minHeight: TOUCH, border: v != null ? `1px solid ${COLOR.border}` : `2px solid ${COLOR.watch}`, borderRadius: RADIUS.sm, padding: `0 ${SPACE(2)}px`,
          textAlign: "right", background: COLOR.surface, ...tx(SIZE.body, WEIGHT.semi, COLOR.ink) }} />
      <span aria-hidden="true" style={tx(SIZE.body, WEIGHT.bold, COLOR.ink)}>%</span>
    </label>
  );
}

export function Limits({ deck, store, setStoreData, onBack, pad }) {
  const cur = limitsOf(deck);
  const [stock, setStock] = useState(String(cur.stock));
  const [ind, setInd] = useState(String(cur.ind));
  const s = readLimit(stock), i = readLimit(ind);
  const [tried, setTried] = useState(false);              // the refused line only after a 저장 here (app.jsx clears an older one)
  const ok = s != null && i != null;
  const save = () => {
    const next = ok ? withLimits(store.data, deck.id, s, i, Date.now()) : null;
    if (!next) return;
    setTried(true);
    setStoreData(next);                                  // refused (would not read back): the line shows here, and this stays
    if (validStore({ ...next, v: versionFor(next) }, todayKst())) onBack();
  };
  return (
    <Page pad={pad}>
      <AppBar onBack={onBack} backLabel={C.co.back} />
      <ScreenTitle>{C.lim.title}</ScreenTitle>
      <p data-ui-v2="limits-deck" style={tx(SIZE.sm, WEIGHT.semi, COLOR.text2, { marginTop: SPACE(1) })}>{shownName(deck.name)}</p>
      <p style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(2) })}>{C.lim.sub}</p>
      <Card data-ui-v2="limits">
        <LimitField id="stock" tpl={C.pfr.stock} value={stock} saved={cur.stock} onChange={setStock} first />
        <LimitField id="ind" tpl={C.pfr.ind} value={ind} saved={cur.ind} onChange={setInd} />
        <button type="button" data-ui-v2="limits-reset" onClick={() => { setStock(String(LIMITS.stock)); setInd(String(LIMITS.ind)); }}
          style={{ border: "none", background: "none", minHeight: TOUCH, padding: 0, cursor: "pointer",
            ...tx(SIZE.xs, WEIGHT.bold, COLOR.text2, { marginTop: SPACE(1), textDecoration: "underline", textUnderlineOffset: 3 }) }}>{C.lim.reset}</button>
      </Card>
      {tried && store.refused && <Note tone="watch" data-ui-v2="store-refused">{C.plan.badInput}</Note>}
      {!store.writable && <Note tone="watch">{C.store.unavailable}</Note>}
      <div data-ui-v2="limits-save" style={{ marginTop: SPACE(4) }}>
        <Button kind="primary" disabled={!ok || !store.writable} onClick={save}>{C.lim.save}</Button>
      </div>
      <Footer />
    </Page>
  );
}
