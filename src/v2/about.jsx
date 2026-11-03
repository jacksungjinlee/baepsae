// ================= 뱁새 2.0 소개 (About) page (v19.0 Part D, route #about) =================
// Who made 뱁새 and how it works. Every word is docs/design/v19/copy/about.md, word for word, kept in src/copy/v2.js
// (C.about.ko / C.about.en). Layout from docs/design/v19/reference/About.dc.html (phone), in today's 2.0 shell: the
// app bar with a back button, the 뱁이 header with the 한국어 / English switch, the sections, the footer.
// - Korean first. The switch is remembered on this device (localStorage "baepsae_v2_about_lang"); when the browser
//   blocks storage the page still works and the choice lasts until the page closes.
// - The figures row and the sentence with "{n}" come from the loaded data (aboutstats.js aboutView): never typed in.
import React, { useEffect, useRef, useState } from "react";
import { COLOR, SIZE, WEIGHT, SPACE, RADIUS, TOUCH } from "../ui/tokens.js";
import { Icon } from "../ui/icons.jsx";
import { Segmented } from "../ui/components.jsx";
import { C, fill, nf } from "./format.js";
import { Page, Card, AppBar, Footer, tx } from "./ui.jsx";
import { aboutView } from "./aboutstats.js";

export const ABOUT_LANG_KEY = "baepsae_v2_about_lang";
const LANGS = ["ko", "en"];

function readLang() {
  try {
    const v = window.localStorage.getItem(ABOUT_LANG_KEY);
    return LANGS.includes(v) ? v : "ko";
  } catch (e) {
    console.warn("[v2] about: language choice not readable (" + ((e && e.message) || e) + "), showing Korean");
    return "ko";
  }
}

function saveLang(v) {
  try {
    window.localStorage.setItem(ABOUT_LANG_KEY, v);
  } catch (e) {
    console.warn("[v2] about: language choice not saved (" + ((e && e.message) || e) + "), kept until the page closes");
  }
}

function SectionTitle({ children }) {
  return <h3 style={tx(SIZE.h3, WEIGHT.bold, COLOR.ink, { marginBottom: SPACE(3) })}>{children}</h3>;
}

const para = tx(SIZE.sm, WEIGHT.regular, COLOR.ink, { lineHeight: 1.65 });
const rowLine = { borderTop: `1px solid ${COLOR.line}` };
const label = tx(SIZE.xxs, WEIGHT.bold, COLOR.text3, { marginTop: SPACE(4), marginBottom: SPACE(1) });

function Figure({ value, name, testId }) {
  return (
    <span data-ui-v2={testId} style={{ background: COLOR.surface, borderRadius: RADIUS.sm, padding: `${SPACE(2)}px ${SPACE(3)}px`,
      display: "flex", flexDirection: "column", justifyContent: "center" }}>
      {value != null && <span data-ui-v2="about-figure-value" style={tx(SIZE.body, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3 })}>{value}</span>}
      <span style={tx(SIZE.xxs, value != null ? WEIGHT.regular : WEIGHT.bold, value != null ? COLOR.text2 : COLOR.ink)}>{name}</span>
    </span>
  );
}

// load: the app's load state (figures); onBack: back to the screen before (src/v2/app.jsx clears the hash).
export function About({ load, onBack }) {
  const [lang, setLang] = useState(readLang);
  const head = useRef(null);
  // Opening 소개 moves focus to its heading, so a screen reader starts here (the screen behind is hidden).
  useEffect(() => {
    try { if (head.current) head.current.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
  }, []);
  const a = C.about[lang];
  const view = aboutView(load);
  const pick = (v) => {
    if (!LANGS.includes(v)) return;
    setLang(v);
    saveLang(v);
  };
  const m = a.maker;
  return (
    <Page>
      <AppBar onBack={onBack} backLabel={C.app.close} />
      <div data-ui-v2="about" data-lang={lang} lang={lang}>
        <section data-ui-v2="about-hero" style={{ background: COLOR.heroCalm, borderRadius: RADIUS.lg, padding: SPACE(5), marginTop: SPACE(2) }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <div data-ui-v2="about-lang" style={{ width: SPACE(48), maxWidth: "100%" }}>
              <Segmented label={C.about.langLabel} value={lang} onChange={pick}
                options={LANGS.map((k) => ({ value: k, label: C.about.langs[k] }))} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: SPACE(3), marginTop: SPACE(1) }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h2 ref={head} tabIndex={-1} data-ui-v2="about-heading" style={tx(SIZE.h1, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.2, letterSpacing: "-0.03em", outline: "none" })}>{a.hero.name}</h2>
              <p data-ui-v2="about-descriptor" style={tx(SIZE.h3, WEIGHT.bold, COLOR.ink, { marginTop: SPACE(2), lineHeight: 1.4 })}>{a.hero.descriptor}</p>
              <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(2) })}>{a.hero.catch}</p>
            </div>
            <img src="baepi-og.webp" alt={C.about.heroAlt} width={108} height={108} style={{ objectFit: "contain", flexShrink: 0 }} />
          </div>
          {view.figures && (
            <div data-ui-v2="about-figures" style={{ display: "flex", flexWrap: "wrap", gap: SPACE(2), marginTop: SPACE(4) }}>
              <Figure testId="about-stocks" value={nf(view.figures.count)} name={a.figures.stocks} />
              <Figure testId="about-groups" value={nf(view.figures.groups)} name={a.figures.groups} />
              <Figure testId="about-refresh" value={null} name={a.figures.refresh} />
            </div>
          )}
        </section>

        <Card data-ui-v2="about-what">
          <SectionTitle>{a.what.title}</SectionTitle>
          <p style={para}>{a.what.intro}</p>
          {view.n != null && (
            <p data-ui-v2="about-data" style={tx(SIZE.sm, WEIGHT.regular, COLOR.ink, { lineHeight: 1.65, marginTop: SPACE(3),
              background: COLOR.page, borderRadius: RADIUS.md, padding: SPACE(3) })}>{fill(a.what.data, { n: nf(view.n) })}</p>
          )}
          <div style={{ marginTop: SPACE(2) }}>
            {a.what.items.map((it) => (
              <div key={it.title} style={{ ...rowLine, padding: `${SPACE(3)}px 0` }}>
                <p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{it.title}</p>
                <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1), lineHeight: 1.6 })}>{it.body}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card data-ui-v2="about-who">
          <SectionTitle>{a.who.title}</SectionTitle>
          <p style={para}>{a.who.intro}</p>
          <ul style={{ listStyle: "none", margin: `${SPACE(2)}px 0 0`, padding: 0 }}>
            {a.who.items.map((t) => (
              <li key={t} style={{ display: "flex", gap: SPACE(2), alignItems: "flex-start", padding: `${SPACE(1)}px 0` }}>
                <span aria-hidden="true" style={{ width: SPACE(6), height: SPACE(6), borderRadius: 999, background: COLOR.okBg, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Icon name="check" size={14} tone="ok" />
                </span>
                <span style={tx(SIZE.sm, WEIGHT.regular, COLOR.ink, { lineHeight: 1.55 })}>{t}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card data-ui-v2="about-why">
          <SectionTitle>{a.why.title}</SectionTitle>
          {a.why.body.map((t, i) => <p key={i} style={{ ...para, marginTop: i ? SPACE(3) : 0 }}>{t}</p>)}
        </Card>

        <Card data-ui-v2="about-principles">
          <SectionTitle>{a.principles.title}</SectionTitle>
          <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {a.principles.items.map((it, i) => (
              <li key={it.title} style={{ display: "flex", gap: SPACE(3), padding: `${SPACE(3)}px 0`, ...(i ? rowLine : {}) }}>
                <span aria-hidden="true" style={{ width: SPACE(7), height: SPACE(7), borderRadius: 999, background: COLOR.ink, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center", ...tx(SIZE.xs, WEIGHT.heavy, COLOR.surface) }}>{i + 1}</span>
                <div style={{ minWidth: 0 }}>
                  <p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>{it.title}</p>
                  <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1), lineHeight: 1.6 })}>{it.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>

        <Card data-ui-v2="about-run">
          <SectionTitle>{a.run.title}</SectionTitle>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {a.run.items.map((t, i) => (
              <li key={t} style={{ padding: `${SPACE(2)}px 0`, ...(i ? rowLine : {}), ...tx(SIZE.sm, WEIGHT.regular, COLOR.ink, { lineHeight: 1.55 }) }}>{t}</li>
            ))}
          </ul>
        </Card>

        <Card data-ui-v2="about-name">
          <SectionTitle>{a.name.title}</SectionTitle>
          {a.name.body.map((t, i) => <p key={i} style={{ ...para, marginTop: i ? SPACE(3) : 0 }}>{t}</p>)}
        </Card>

        <Card data-ui-v2="about-maker">
          <SectionTitle>{m.title}</SectionTitle>
          <div style={{ display: "flex", alignItems: "center", gap: SPACE(4) }}>
            <img data-ui-v2="about-photo" src="jack-photo.jpg" alt={m.photoAlt} width={88} height={88}
              style={{ borderRadius: 999, objectFit: "cover", flexShrink: 0, background: COLOR.surface, boxShadow: `0 0 0 1px ${COLOR.border}` }} />
            <div style={{ minWidth: 0 }}>
              <p style={tx(SIZE.h2, WEIGHT.heavy, COLOR.ink, { lineHeight: 1.3 })}>{m.name}</p>
              <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.text2, { marginTop: SPACE(1) })}>{m.role}</p>
            </div>
          </div>
          <p style={label}>{m.edu.label}</p>
          <p style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink)}>{m.edu.value}</p>
          <p style={label}>{m.career.label}</p>
          {m.career.items.map((it) => (
            <div key={it.org} style={{ ...rowLine, padding: `${SPACE(2)}px 0` }}>
              <p style={tx(SIZE.sm, WEIGHT.bold, COLOR.ink)}>
                {it.org}{it.note && <span style={tx(SIZE.sm, WEIGHT.regular, COLOR.text2)}>{" · "}{it.note}</span>}
              </p>
              <p style={tx(SIZE.xs, WEIGHT.regular, COLOR.neutral, { marginTop: SPACE(1) })}>{it.what}</p>
            </div>
          ))}
          <p style={label}>{m.built.label}</p>
          <ul style={{ margin: 0, paddingLeft: SPACE(5) }}>
            {m.built.items.map((t) => <li key={t} style={tx(SIZE.sm, WEIGHT.regular, COLOR.ink, { margin: `${SPACE(1)}px 0`, lineHeight: 1.55 })}>{t}</li>)}
          </ul>
          <p style={label}>{m.langs.label}</p>
          <p style={tx(SIZE.sm, WEIGHT.semi, COLOR.ink)}>{m.langs.value}</p>
          <a data-ui-v2="about-linkedin" href={C.about.linkedInUrl} target="_blank" rel="noopener"
            style={{ marginTop: SPACE(4), display: "inline-flex", alignItems: "center", minHeight: TOUCH, padding: `0 ${SPACE(4)}px`,
              borderRadius: RADIUS.sm, background: COLOR.ink, textDecoration: "none", ...tx(SIZE.sm, WEIGHT.bold, COLOR.surface) }}>{m.linkedIn}</a>
        </Card>
      </div>
      <Footer />
    </Page>
  );
}
