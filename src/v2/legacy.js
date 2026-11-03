// Names saved before v19.0c (v19.0c renamed the portfolio in every word users see). A portfolio's default name was
// C.legacy.deckName ("{start type name} …") or C.legacy.myDeck. The saved record is never rewritten: the name is mapped
// only when it is shown, and only when it is exactly one of those defaults (a name the user typed is shown as typed).
import { C, fill } from "./format.js";

export function shownName(name) {
  if (typeof name !== "string") return name;
  if (name === C.legacy.myDeck) return C.deck.title;
  for (const id of Object.keys(C.build.decks)) {
    const x = C.build.decks[id].name;
    if (name === fill(C.legacy.deckName, { name: x })) return fill(C.app.deckName, { name: x });
  }
  return name;
}
