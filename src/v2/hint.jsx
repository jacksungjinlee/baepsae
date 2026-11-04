// iPhone home-screen hint (v19.0c): only in iPhone Safari itself, never inside the app added to the home screen
// (store.js iphoneSafari). On iPhone the records live in Safari's storage and the home-screen app keeps its own.
//   kind "first": before any portfolio exists (홈 first visit, empty 포트폴리오) — add it to the home screen first, with the
//                 old app's two steps (Share button, then '홈 화면에 추가').
//   kind "move":  a portfolio exists (포트폴리오, records card) — 기록 내보내기 here, then 기록 불러오기 in the home-screen app.
// The wording waits for Jack (C.hint is null until then): meanwhile only a hidden marker keeps the place, so the tests can
// check where and when the hint would show. No numbers in it, so it may sit on a screen with a 뱁이.
import React, { useState } from "react";
import { SPACE } from "../ui/tokens.js";
import { C } from "./format.js";
import { Note } from "./ui.jsx";
import { iphoneSafari } from "./store.js";

export function IosHint({ kind }) {
  const [on] = useState(() => iphoneSafari());
  if (!on) return null;
  const text = kind === "first" ? C.hint.first : C.hint.move;
  if (!text) return <span data-ui-v2="ios-hint" data-kind={kind} data-pending="1" hidden />;
  const steps = kind === "first" && Array.isArray(C.hint.steps) ? C.hint.steps : [];
  return (
    <Note data-ui-v2="ios-hint" data-kind={kind}>
      <span style={{ display: "block" }}>{text}</span>
      {steps.length > 0 && (
        <ol style={{ margin: `${SPACE(1)}px 0 0`, paddingLeft: SPACE(5) }}>
          {steps.map((x, i) => <li key={i}>{x}</li>)}
        </ol>
      )}
    </Note>
  );
}
