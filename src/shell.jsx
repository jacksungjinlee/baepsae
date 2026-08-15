// ================= 뱁새 v11 — 셸 (내비게이션 + 모드 분기) =================
// 상단 탭: 포트폴리오(현재) · 기업분석(준비 중) · 공시·수급(준비 중)
// 포트폴리오 탭은 간단/상세 모드 게이트에서 시작합니다.
import React, { useState, useEffect } from "react";
import { C, FONT, SERIF, RAD, HAIR } from "./tokens.js";
import { Ic, Seal } from "./icons.jsx";
import DetailApp, { Bird, store } from "./detail.jsx";
import SimpleApp from "./simple.jsx";
import CorpApp from "./corp.jsx";

const MAST_CSS = `@media (max-width: 560px) { .mastSub { display: none } }`;
const CREDIT_KO = "이성진, INSEAD MBA 26J";
const CREDIT_EN = "Jack (Sung Jin) Lee, INSEAD MBA 26J";

const TABS = [
  { id: "pf", ko: "포트폴리오", icon: "compass" },
  { id: "corp", ko: "기업분석", icon: "chart" },
  { id: "disc", ko: "공시·수급", icon: "doc", soon: true },
];

function TopNav({ tab, setTab, showBack, onBack }) {
  return (
    <div style={{ position: "sticky", top: 0, zIndex: 60, background: "rgba(250,248,245,0.95)", backdropFilter: "blur(8px)", borderTop: "3px solid " + C.ink, borderBottom: "1px solid " + C.ink + "33", boxShadow: "0 1px 0 rgba(27,43,75,0.06)" }}>
      <div style={{ maxWidth: 1140, margin: "0 auto", padding: "0 16px", height: 48, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <Seal size={25} />
          <span style={{ fontFamily: SERIF, fontSize: 17, fontWeight: 900, color: C.ink, letterSpacing: "0.01em" }}>뱁새</span>
          <span className="mastSub" style={{ fontFamily: SERIF, fontSize: 10, color: C.faint, borderLeft: "1px solid " + C.line, paddingLeft: 8, letterSpacing: "0.04em" }}>황새 말고, 내 걸음으로</span>
        </div>
        <div style={{ display: "flex", gap: 2, overflowX: "auto", flex: 1 }}>
          {TABS.map((tb) => {
            const on = tab === tb.id;
            return (
              <button key={tb.id} onClick={() => setTab(tb.id)}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "none", background: "none", cursor: "pointer",
                  fontFamily: FONT, fontSize: 13, fontWeight: on ? 800 : 600, color: on ? C.ink : C.faint,
                  padding: "0 10px", height: 48, borderBottom: on ? "3px solid " + C.ink : "3px solid transparent", whiteSpace: "nowrap" }}>
                <Ic name={tb.icon} size={15} color={on ? C.ink : C.faint} />
                {tb.ko}
                {tb.soon && <span style={{ fontSize: 9, fontWeight: 800, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 999, padding: "2px 6px" }}>준비 중</span>}
              </button>
            );
          })}
        </div>
        {showBack && (
          <button onClick={onBack}
            style={{ display: "inline-flex", alignItems: "center", gap: 5, border: HAIR, background: "#fff", borderRadius: 999, padding: "5px 11px", fontSize: 11.5, fontWeight: 700, color: C.sub, cursor: "pointer", fontFamily: FONT, flexShrink: 0 }}>
            <Ic name="back" size={12} color={C.sub} />모드 선택
          </button>
        )}
      </div>
    </div>
  );
}

function ModeGate({ onPick, hasSimpleSave }) {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "34px 16px 60px", fontFamily: FONT, color: C.ink }}>
      <div style={{ textAlign: "center" }}>
        <Bird mood="cheer" size={92} />
        <div style={{ fontFamily: SERIF, fontSize: 27, fontWeight: 700, marginTop: 16, letterSpacing: "-0.01em" }}>뱁새</div>
        <div style={{ fontFamily: SERIF, fontSize: 14.5, color: C.sub, marginTop: 6 }}>황새 말고, 내 걸음으로</div>
        <div style={{ fontSize: 13.5, color: C.sub, marginTop: 14, lineHeight: 1.7 }}>
          내 그릇에 맞는 포트폴리오를 만들어보는 교육용 도구예요.<br />오늘은 어떤 걸음으로 갈까요?
        </div>
      </div>

      <div className="gatecols" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 26 }}>
        <button onClick={() => onPick("simple")}
          style={{ textAlign: "left", background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 20, cursor: "pointer", fontFamily: FONT }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Ic name="seed" size={20} color={C.apricotDeep} />
            <span style={{ fontSize: 17, fontWeight: 800, color: C.ink }}>간단히</span>
            <span style={{ fontSize: 10.5, fontWeight: 800, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 999, padding: "3px 8px" }}>10분 · 처음이라면</span>
          </div>
          <div style={{ fontSize: 13, color: C.sub, marginTop: 9, lineHeight: 1.65 }}>
            다섯 가지 질문으로 시작해요. 어려운 개념 없이, 큰 그림의 조합과 쉬운 진단만 담백하게.
          </div>
          {hasSimpleSave && <div style={{ fontSize: 11.5, color: C.teal, fontWeight: 700, marginTop: 9 }}>하던 작업이 저장되어 있어요 — 이어서 해요</div>}
        </button>

        <button onClick={() => onPick("detail")}
          style={{ textAlign: "left", background: "#fff", border: "1.5px solid " + C.blue, borderRadius: RAD.card, padding: 20, cursor: "pointer", fontFamily: FONT }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Ic name="compass" size={20} color={C.blue} />
            <span style={{ fontSize: 17, fontWeight: 800, color: C.ink }}>상세히</span>
            <span style={{ fontSize: 10.5, fontWeight: 800, color: C.blue, background: C.blueSoft, borderRadius: 999, padding: "3px 8px" }}>꼼꼼하게</span>
          </div>
          <div style={{ fontSize: 13, color: C.sub, marginTop: 9, lineHeight: 1.65 }}>
            열한 가지 질문으로 프로필을 만들고, 종목을 직접 골라 담아요. 세금·스트레스 테스트·벤치마크 비교까지.
          </div>
        </button>
      </div>

      <div style={{ textAlign: "center", marginTop: 34, fontSize: 11, color: C.faint, lineHeight: 1.8 }}>
        교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다.<br />
        {CREDIT_KO} · {CREDIT_EN}
      </div>
    </div>
  );
}

function Stub({ kind }) {
  const M = {
    corp: {
      icon: "chart", title: "기업분석", line: "숫자로 기업을 읽는 곳",
      items: [
        "밸류에이션 멀티플 — PER·PBR·ROE를 업종 분포 속에서 비교해요",
        "풋볼필드 차트 — 한 기업의 가치를 여러 잣대로 한눈에",
        "DCF 샌드박스 — 가정을 직접 움직이며 '가격에 담긴 기대'를 확인해요",
      ],
    },
    disc: {
      icon: "doc", title: "공시·수급", line: "공개된 발자국을 따라 읽는 곳",
      items: [
        "내부자 거래 — 임원·주요주주가 자기 회사 주식을 사고판 공시 모아보기",
        "국민연금 트래커 — 큰손의 보유 변화 살펴보기",
      ],
    },
  }[kind];
  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "44px 16px", fontFamily: FONT, color: C.ink, textAlign: "center" }}>
      <Ic name={M.icon} size={34} color={C.blue} />
      <div style={{ fontFamily: SERIF, fontSize: 22, fontWeight: 700, marginTop: 12 }}>{M.title}</div>
      <div style={{ fontSize: 13, color: C.sub, marginTop: 5 }}>{M.line} · 준비하고 있어요</div>
      <div style={{ background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 18, marginTop: 20, textAlign: "left" }}>
        {M.items.map((s, i) => (
          <div key={i} style={{ fontSize: 13, color: C.sub, lineHeight: 1.7, marginTop: i ? 8 : 0, display: "flex", gap: 8 }}>
            <Ic name="spark" size={13} color={C.apricotDeep} style={{ marginTop: 3 }} />{s}
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: C.faint, marginTop: 16 }}>{CREDIT_KO} · {CREDIT_EN}</div>
    </div>
  );
}

const GATE_CSS = `
  @media (max-width: 640px) { .gatecols { grid-template-columns: 1fr !important } }
`;

export default function Shell() {
  const [tab, setTab] = useState("pf");
  const [mode, setMode] = useState(null); // null=게이트, "simple", "detail"
  const [seed, setSeed] = useState(null);
  const [hasSimpleSave, setHasSimpleSave] = useState(false);

  useEffect(() => { (async () => {
    try { const s = await store.get("baepsae_v11_simple"); setHasSimpleSave(!!s); } catch (e) {}
  })(); }, [mode]);

  const graduate = (sd) => { setSeed(sd); setMode("detail"); };

  return (
    <div style={{ minHeight: "100vh", background: C.bg }}>
      <style>{GATE_CSS}</style>
      <style>{MAST_CSS}</style>
      <TopNav tab={tab} setTab={setTab} showBack={tab === "pf" && mode !== null} onBack={() => { setMode(null); setSeed(null); }} />
      {tab === "pf" && mode === null && <ModeGate onPick={setMode} hasSimpleSave={hasSimpleSave} />}
      {tab === "pf" && mode === "simple" && <SimpleApp onGraduate={graduate} onExit={() => setMode(null)} />}
      {tab === "pf" && mode === "detail" && <DetailApp seed={seed} />}
      {tab === "corp" && <CorpApp />}
      {tab === "disc" && <Stub kind="disc" />}
    </div>
  );
}
