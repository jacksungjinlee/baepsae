// ================= 뱁새 v11 — 셸 (내비게이션 + 모드 분기) =================
// 상단 탭: 포트폴리오(현재) · 기업분석(준비 중) · 공시·수급(준비 중)
// 포트폴리오 탭은 간단/상세 모드 게이트에서 시작합니다.
import React, { useState, useEffect, useMemo, useRef } from "react";
import { C, FONT, SERIF, RAD, HAIR } from "./tokens.js";
import { Ic, Seal } from "./icons.jsx";
import DetailApp, { Bird, store } from "./detail.jsx";
import SimpleApp from "./simple.jsx";
import CorpApp from "./corp.jsx";
import DiscApp from "./disc.jsx";
import MacroApp from "./macro.jsx";
import InfoApp from "./info.jsx";

const MAST_CSS = `@media (max-width: 560px) { .mastSub { display: none } }
.botNav { display: none; position: fixed; left: 0; right: 0; bottom: 0; z-index: 70; background: rgba(250,248,245,0.97); backdrop-filter: blur(10px); border-top: 1px solid rgba(27,43,75,0.14); padding: 5px 2px calc(5px + env(safe-area-inset-bottom)); }
.botNav .row { display: flex; }
.botNav button { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; background: none; border: none; cursor: pointer; padding: 4px 0; }
@media (max-width: 880px) {
  .topTabs { display: none !important }
  .botNav { display: block !important }
  .shellbody { padding-bottom: calc(64px + env(safe-area-inset-bottom)) }
  .gatecols { grid-template-columns: 1fr !important }
}`;
const CREDIT_KO = "이성진, INSEAD MBA 26J";
const CREDIT_EN = "Jack (Sung Jin) Lee, INSEAD MBA 26J";

const TABS = [
  { id: "pf", ko: "포트폴리오", icon: "compass" },
  { id: "corp", ko: "기업분석", icon: "chart" },
  { id: "disc", ko: "공시·수급", icon: "doc" },
  { id: "macro", ko: "금리·원자재", icon: "rates" },
  { id: "info", ko: "정보", icon: "info" },
];

function TopNav({ tab, setTab, showBack, onBack }) {
  return (
    <>
    <div style={{ position: "sticky", top: 0, zIndex: 60, background: "rgba(250,248,245,0.95)", backdropFilter: "blur(8px)", borderTop: "3px solid " + C.ink, borderBottom: "1px solid " + C.ink + "33", boxShadow: "0 1px 0 rgba(27,43,75,0.06)" }}>
      <div style={{ maxWidth: 1140, margin: "0 auto", padding: "0 16px", height: 48, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <Seal size={25} />
          <span style={{ fontFamily: FONT, fontSize: 16.5, fontWeight: 900, color: C.ink, letterSpacing: "-0.01em" }}>뱁새</span>
          <span className="mastSub" style={{ fontFamily: FONT, fontSize: 10, color: C.faint, borderLeft: "1px solid " + C.line, paddingLeft: 8, letterSpacing: "0.03em" }}>황새 말고, 내 걸음으로</span>
        </div>
        <div className="topTabs" style={{ display: "flex", gap: 2, overflowX: "auto", flex: 1 }}>
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
    <nav className="botNav"><div className="row">
      {TABS.map((tb) => {
        const on = tab === tb.id;
        return (
          <button key={tb.id} onClick={() => setTab(tb.id)}>
            <Ic name={tb.icon} size={19} color={on ? C.ink : C.faint} />
            <span style={{ fontSize: 9.5, fontWeight: on ? 800 : 600, color: on ? C.ink : C.faint, fontFamily: FONT }}>{tb.ko}</span>
          </button>
        );
      })}
      </div>
    </nav>
    </>
  );
}

// ---- 계측: GoatCounter 이벤트 (없으면 조용히 무시) ----
const gcEvent = (n) => { try { window.goatcounter && window.goatcounter.count({ path: "evt-" + n, title: n, event: true }); } catch (e) {} };

// ---- 성적표 데이터 (corp.json 지연 로드, 캐시) ----
let GATE_CORP = null;
async function loadGateCorp() {
  if (GATE_CORP) return GATE_CORP;
  try {
    const r = await fetch("./corp.json", { cache: "no-store" });
    GATE_CORP = r.ok ? await r.json() : { companies: [], sectors: {} };
  } catch (e) { GATE_CORP = { companies: [], sectors: {} }; }
  return GATE_CORP;
}
const fmtWonG = (v) => v == null ? "—" : Math.round(v).toLocaleString() + "원";

function ScoreCard({ c, sectors, onOpenCorp, onQuickDiag }) {
  const sec = sectors[c.s] || {};
  const niYoY = c.ni && c.ni[0] != null && c.ni[1] > 0 ? (c.ni[0] / c.ni[1] - 1) * 100 : null;
  const lines = [];
  if (c.per != null && sec.perQ) lines.push(`PER ${c.per}배 — 업종 중간 ${sec.perQ[1]}배보다 ${c.per > sec.perQ[1] ? "높아요. 시장의 기대가 큰 만큼 근거를 물을 자리예요." : "낮아요. 싸다는 뜻일 수도, 시장이 의심한다는 뜻일 수도 있어요."}`);
  else if (c.pbr != null && sec.pbrQ) lines.push(`PBR ${c.pbr}배 — 업종 중간 ${sec.pbrQ[1]}배 대비 ${c.pbr > sec.pbrQ[1] ? "높은" : "낮은"} 평가예요.`);
  else lines.push("적자이거나 재무 데이터가 아직 없어요.");
  if (c.r3 != null && c.r3 >= 15 && niYoY != null && niYoY <= 5) lines.push(`최근 3개월 +${c.r3}% 올랐지만 연간 실적은 그대로예요 — 가격을 움직인 건 실적보다 기대나 수급일 수 있어요.`);
  else if (c.r3 != null && c.r3 <= -15 && niYoY != null && niYoY >= 10) lines.push(`실적은 좋아졌는데 3개월간 ${c.r3}% 내렸어요 — 시장이 무엇을 걱정하는지 볼 대목이에요.`);
  else if (c.g3 != null) lines.push(`매출은 3년간 연평균 ${c.g3 >= 0 ? "+" : ""}${c.g3}% ${c.g3 >= 0 ? "성장했어요" : "감소했어요"}.`);
  const flagN = c.fl ? Object.keys(c.fl).length : 0;
  return (
    <div style={{ background: "#fff", border: "1.5px solid " + C.ink, borderRadius: RAD.card, padding: 16, marginTop: 10, textAlign: "left" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 16, fontWeight: 800, color: C.ink }}>{c.nk}</span>
        <span style={{ fontSize: 13, fontWeight: 800, color: C.ink, fontVariantNumeric: "tabular-nums" }}>{fmtWonG(c.price)}
          {c.r3 != null && <span style={{ marginLeft: 8, fontSize: 11.5, color: c.r3 >= 0 ? C.up : C.down }}>3개월 {c.r3 >= 0 ? "+" : ""}{c.r3}%</span>}
        </span>
      </div>
      <div style={{ marginTop: 9, display: "flex", flexDirection: "column", gap: 6 }}>
        {lines.map((l, i) => <div key={i} style={{ fontSize: 12, color: C.ink, lineHeight: 1.6 }}>{l}</div>)}
        {flagN > 0 && <div style={{ fontSize: 12, color: C.coral, fontWeight: 700 }}>짚고 갈 재무 신호 {flagN}개가 있어요</div>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 7, marginTop: 12 }}>
        <button onClick={() => { gcEvent("gate-diag"); onQuickDiag(c.t); }}
          style={{ background: C.ink, color: "#fff", border: "none", borderRadius: 10, padding: "12px 14px", fontSize: 13, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>
          이 종목이 담긴 내 계좌, 전체 진단하기 →</button>
        <button onClick={() => { gcEvent("gate-corp"); onOpenCorp(c.t); }}
          style={{ background: "#fff", color: C.ink, border: "1.5px solid " + C.line, borderRadius: 10, padding: "10px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: FONT }}>
          기업분석에서 자세히 보기</button>
      </div>
      <div style={{ fontSize: 10, color: C.faint, marginTop: 8 }}>사실의 요약일 뿐, 매수·매도 판단이 아니에요.</div>
    </div>
  );
}

function GateSearch({ onOpenCorp, onQuickDiag }) {
  const [q, setQ] = useState("");
  const [d, setD] = useState(null);
  const [sel, setSel] = useState(null);
  const boot = async () => { if (!d) setD(await loadGateCorp()); };
  const res = useMemo(() => {
    if (!d || !q.trim()) return [];
    const t = q.trim().toLowerCase();
    return d.companies.filter((c) => c.nk.toLowerCase().includes(t) || c.t.includes(t))
      .sort((a, b) => (b.cap || 0) - (a.cap || 0)).slice(0, 6);
  }, [d, q]);
  return (
    <div style={{ maxWidth: 460, margin: "0 auto" }}>
      <input value={q} onFocus={boot} onChange={(e) => { setQ(e.target.value); setSel(null); boot(); }}
        placeholder="궁금한 종목이 있나요? — 이름 또는 코드"
        style={{ width: "100%", boxSizing: "border-box", border: "1.5px solid " + C.ink, borderRadius: 12, padding: "14px 16px", fontSize: 14.5, fontFamily: FONT, color: C.ink, outline: "none", background: "#fff" }} />
      {!sel && res.length > 0 && (
        <div style={{ background: "#fff", border: HAIR, borderRadius: 12, marginTop: 6, overflow: "hidden", textAlign: "left" }}>
          {res.map((c) => (
            <button key={c.t} onClick={() => { gcEvent("gate-score"); setSel(c); }}
              style={{ display: "flex", justifyContent: "space-between", width: "100%", background: "none", border: "none", borderBottom: "1px solid " + C.line, padding: "11px 14px", cursor: "pointer", fontFamily: FONT }}>
              <span style={{ fontSize: 13, fontWeight: 800, color: C.ink }}>{c.nk}</span>
              <span style={{ fontSize: 11, color: C.faint }}>{c.t}</span>
            </button>
          ))}
        </div>
      )}
      {sel && <ScoreCard c={sel} sectors={d.sectors} onOpenCorp={onOpenCorp} onQuickDiag={onQuickDiag} />}
      {q.trim() && d && res.length === 0 && !sel && <div style={{ fontSize: 11.5, color: C.faint, marginTop: 8 }}>찾지 못했어요 — 상장사 이름이나 6자리 코드로 검색해요. (데이터 갱신 전이면 비어 있을 수 있어요)</div>}
    </div>
  );
}

function ModeGate({ onPick, hasSimpleSave, onOpenCorp, onQuickDiag }) {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "30px 16px 60px", fontFamily: FONT, color: C.ink }}>
      <div style={{ textAlign: "center" }}>
        <Bird mood="happy" size={84} />
        <div style={{ fontSize: 23, fontWeight: 900, marginTop: 12, letterSpacing: "-0.01em" }}>내 종목, 괜찮은 걸까요?</div>
        <div style={{ fontSize: 12.5, color: C.sub, marginTop: 6 }}>종목 하나로 5초 성적표부터 — 황새 말고, 내 걸음으로</div>
        <div style={{ marginTop: 16 }}>
          <GateSearch onOpenCorp={onOpenCorp} onQuickDiag={onQuickDiag} />
        </div>
      </div>

      <div className="gatecols" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginTop: 26 }}>
        <button onClick={() => { gcEvent("gate-quick"); onQuickDiag(null); }}
          style={{ textAlign: "left", background: "#fff", border: "1.5px solid " + C.blue, borderRadius: RAD.card, padding: 16, cursor: "pointer", fontFamily: FONT }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Ic name="target" size={18} color={C.blue} />
            <span style={{ fontSize: 14.5, fontWeight: 800, color: C.ink }}>30초 진단</span>
          </div>
          <div style={{ fontSize: 11.5, color: C.sub, marginTop: 7, lineHeight: 1.6 }}>지금 보유 종목을 넣으면 건강 점수·쏠림·상관을 바로 보여줘요. 기본 성향으로 시작해요.</div>
        </button>
        <button onClick={() => { gcEvent("gate-test"); onPick("simple"); }}
          style={{ textAlign: "left", background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 16, cursor: "pointer", fontFamily: FONT }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Ic name="seed" size={18} color={C.apricotDeep} />
            <span style={{ fontSize: 14.5, fontWeight: 800, color: C.ink }}>성향 테스트로 시작</span>
          </div>
          <div style={{ fontSize: 11.5, color: C.sub, marginTop: 7, lineHeight: 1.6 }}>다섯 질문이면 내 투자 그릇이 보여요. 처음이라면 여기부터.</div>
          {hasSimpleSave && <div style={{ fontSize: 10.5, color: C.teal, fontWeight: 700, marginTop: 7 }}>하던 작업이 저장돼 있어요</div>}
        </button>
        <button onClick={() => { gcEvent("gate-detail"); onPick("detail"); }}
          style={{ textAlign: "left", background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 16, cursor: "pointer", fontFamily: FONT }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Ic name="compass" size={18} color={C.blue} />
            <span style={{ fontSize: 14.5, fontWeight: 800, color: C.ink }}>차근차근 만들기</span>
          </div>
          <div style={{ fontSize: 11.5, color: C.sub, marginTop: 7, lineHeight: 1.6 }}>열한 질문 프로필과 세금·스트레스 테스트까지, 꼼꼼한 상세 모드예요.</div>
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

function BottomNav({ tab, setTab }) {
  return (
    <nav className="botNav" style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 70, background: "rgba(255,255,255,0.97)", backdropFilter: "blur(8px)", borderTop: "1px solid " + C.line, display: "none", paddingBottom: "env(safe-area-inset-bottom)" }}>
      <div style={{ display: "flex", justifyContent: "space-around", height: 56 }}>
        {TABS.map((tb) => {
          const on = tab === tb.id;
          return (
            <button key={tb.id} onClick={() => setTab(tb.id)}
              style={{ flex: 1, background: "none", border: "none", cursor: "pointer", fontFamily: FONT, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 3, padding: 0 }}>
              <Ic name={tb.icon} size={19} color={on ? C.ink : C.faint} />
              <span style={{ fontSize: 9.5, fontWeight: on ? 800 : 600, color: on ? C.ink : C.faint }}>{tb.ko}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export default function Shell() {
  const [tab, setTab] = useState("pf");
  const [corpJump, setCorpJump] = useState(null);
  const [mode, setMode] = useState(null); // null=게이트, "simple", "detail"
  const [seed, setSeed] = useState(null);
  const [hasSimpleSave, setHasSimpleSave] = useState(false);

  useEffect(() => { (async () => {
    try { const s = await store.get("baepsae_v11_simple"); setHasSimpleSave(!!s); } catch (e) {}
  })(); }, [mode]);

  const graduate = (sd) => { setSeed(sd); setMode("detail"); };
  const quickDiag = (t) => { setSeed({ quick: true, holdings: t ? [{ t, mw: 100 }] : [] }); setMode("detail"); setTab("pf"); };
  useEffect(() => { try { window.history.scrollRestoration = "manual"; } catch (e) {} }, []);
  useEffect(() => { window.scrollTo(0, 0); }, [tab, mode]);

  return (
    <div className="shellbody" style={{ minHeight: "100vh", background: C.bg }}>
      <style>{GATE_CSS}</style>
      <style>{MAST_CSS}</style>
      <TopNav tab={tab} setTab={setTab} showBack={tab === "pf" && mode !== null} onBack={() => { setMode(null); setSeed(null); }} />
      <div className="shellbody">
      {tab === "pf" && mode === null && <ModeGate onPick={setMode} hasSimpleSave={hasSimpleSave} onOpenCorp={(t) => { setCorpJump(t); setTab("corp"); }} onQuickDiag={quickDiag} />}
      {tab === "pf" && mode === "simple" && <SimpleApp onGraduate={graduate} onExit={() => setMode(null)} />}
      {tab === "pf" && mode === "detail" && <DetailApp seed={seed} />}
      {tab === "corp" && <CorpApp jump={corpJump} onJumpDone={() => setCorpJump(null)} />}
      {tab === "disc" && <DiscApp onOpenCompany={(t) => { setCorpJump(t); setTab("corp"); }} />}
      {tab === "macro" && <MacroApp />}
      {tab === "info" && <InfoApp />}
      </div>
      <BottomNav tab={tab} setTab={setTab} />
    </div>
  );
}
