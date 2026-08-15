// ================= 뱁새 v11 — 간단 모드 =================
// 모바일 우선. 다섯 가지 질문, 프리셋 + 슬라이더 하나, 쉬운 말로 된 세 장의 진단.
// 어려운 개념(β, 상관, 알파, VaR)은 여기 등장하지 않습니다. 더 깊이는 상세 모드로.
import React, { useState, useEffect, useMemo, useRef } from "react";
import { C, FONT, SERIF, RAD, HAIR } from "./tokens.js";
import { Ic } from "./icons.jsx";
import { Bird, DEFAULT_SETTINGS, store, normCdf } from "./detail.jsx";

const KEY_SIMPLE = "baepsae_v11_simple";
const fmtMw = (mw) => {
  const w = Math.round(mw);
  if (w >= 10000) { const ek = Math.floor(w / 10000), r = w % 10000; return r ? `${ek}억 ${r.toLocaleString()}만원` : `${ek}억원`; }
  return w.toLocaleString() + "만원";
};

// ---------------- 아톰 (모바일 터치 타깃 크게) ----------------
const SCard = ({ children, style = {} }) => (
  <div style={{ background: "#FFFFFF", border: HAIR, borderRadius: RAD.card, padding: 20, ...style }}>{children}</div>
);
const SBtn = ({ children, onClick, kind = "primary", style = {}, disabled }) => {
  const kinds = {
    primary: { background: C.blue, color: "#fff" },
    ghost: { background: "#fff", color: C.sub, border: "1.5px solid " + C.line },
    warm: { background: C.apricotSoft, color: C.apricotDeep, border: "1.5px solid " + C.apricot + "66" },
  };
  return (
    <button disabled={disabled} onClick={onClick}
      style={{ border: "none", borderRadius: RAD.btn, padding: "15px 18px", fontSize: 15, fontWeight: 800,
        cursor: disabled ? "default" : "pointer", opacity: disabled ? 0.5 : 1, fontFamily: FONT, width: "100%", ...kinds[kind], ...style }}>
      {children}
    </button>
  );
};
const Opt = ({ children, sub, on, onClick }) => (
  <button onClick={onClick}
    style={{ display: "block", width: "100%", textAlign: "left", background: on ? C.blueSoft : "#fff",
      border: on ? "1.5px solid " + C.blue : "1.5px solid " + C.line, borderRadius: RAD.card, padding: "15px 16px",
      cursor: "pointer", fontFamily: FONT, marginBottom: 9 }}>
    <div style={{ fontSize: 15, fontWeight: 800, color: C.ink }}>{children}</div>
    {sub && <div style={{ fontSize: 12, color: C.sub, marginTop: 3, lineHeight: 1.5 }}>{sub}</div>}
  </button>
);

// ---------------- 질문 (다섯 개) ----------------
// goal / horizon / crash / emergency 값은 상세 모드 질문의 값과 호환되게 맞춰,
// "이어가기" 때 답변이 그대로 넘어갑니다.
const SQ = [
  { id: "goal", q: "이 돈으로 이루고 싶은 게 뭐예요?", type: "one", opts: [
    { v: "house", ko: "내 집 마련" }, { v: "retire", ko: "은퇴 준비" }, { v: "lump", ko: "목돈 만들기" },
    { v: "edu", ko: "자녀 교육비" }, { v: "grow", ko: "그냥 불려보기" }, { v: "unsure", ko: "아직 모르겠어요" },
  ]},
  { id: "horizon", q: "이 돈이 실제로 필요해지는 건 언제쯤인가요?", type: "one", opts: [
    { v: 2, ko: "3년 안에", sub: "곧 쓸 돈이에요" }, { v: 5, ko: "3~7년 뒤", sub: "중기 목표예요" },
    { v: 10, ko: "7~15년 뒤", sub: "길게 보고 있어요" }, { v: 20, ko: "15년 이상 뒤", sub: "아주 먼 미래예요" },
  ]},
  { id: "crash", q: "1,000만원을 투자했는데 6개월 만에 800만원이 됐어요. 어떻게 하실 것 같아요?", type: "one", opts: [
    { v: "sellall", ko: "전부 팔 것 같아요", sub: "더 잃기 전에 정리" }, { v: "sellsome", ko: "일부는 팔 것 같아요", sub: "줄이고 지켜보기" },
    { v: "hold", ko: "일단 버틸 것 같아요", sub: "계획대로 유지" }, { v: "buy", ko: "오히려 더 살 것 같아요", sub: "싸졌으니 기회" },
  ]},
  { id: "exp", q: "투자 경험은 어느 정도인가요?", type: "one", opts: [
    { v: "first", ko: "처음이에요", sub: "예·적금 위주였어요" }, { v: "some", ko: "조금 해봤어요", sub: "펀드나 주식을 사본 적 있어요" },
    { v: "years", ko: "몇 년 해봤어요", sub: "오르내림을 겪어봤어요" },
  ]},
  { id: "emergency", q: "수입이 끊겨도 버틸 수 있는 비상금이 있나요?", type: "one", opts: [
    { v: "enough", ko: "6개월치 이상 있어요" }, { v: "some", ko: "조금 있어요", sub: "1~3개월치 정도" },
    { v: "none", ko: "거의 없어요" },
  ]},
];

// ---------------- 프로필 → 프리셋 매핑 ----------------
const SPRESETS = [
  { k: "safe", ko: "안정", eq: 30, icon: "shield", line: "지키는 게 먼저인 조합" },
  { k: "bal", ko: "균형", eq: 50, icon: "scale", line: "지키기와 불리기의 중간" },
  { k: "grow", ko: "성장", eq: 70, icon: "seed", line: "불리기에 무게를 둔 조합" },
  { k: "bold", ko: "적극", eq: 85, icon: "flame", line: "출렁임을 견딜 각오가 된 조합" },
];
function pickPreset(ans) {
  const lossPt = { sellall: 0, sellsome: 1, hold: 2, buy: 3 }[ans.crash] ?? 1;
  const horPt = ans.horizon <= 2 ? 0 : ans.horizon <= 5 ? 1 : ans.horizon <= 10 ? 2 : 3;
  const expPt = { first: 0, some: 1, years: 2 }[ans.exp] ?? 0;
  const s = lossPt + horPt + expPt; // 0~8
  let idx = s <= 1 ? 0 : s <= 4 ? 1 : s <= 6 ? 2 : 3;
  let capped = false;
  if (ans.emergency === "none" && idx > 1) { idx = 1; capped = true; }
  if (ans.horizon <= 2 && idx > 1) { idx = 1; capped = true; }
  return { ...SPRESETS[idx], capped };
}

// ---------------- 계산 (4개 블록: 한국주식·미국주식·금·예금) ----------------
function blockMetrics(eqPct, krShare, goldOn, st) {
  const eq = eqPct / 100;
  const wKr = eq * krShare, wUs = eq * (1 - krShare);
  const wG = goldOn ? Math.min(0.05, Math.max(0, 1 - eq)) : 0;
  const wC = Math.max(0, 1 - wKr - wUs - wG);
  const mu = { kr: st.rf + st.mrp, us: st.rf + st.usMrp, g: st.rf + st.mtMrp, c: st.rf };
  const sg = { kr: st.mktVol, us: st.usVol, g: st.mtVol, c: 0 };
  const w = { kr: wKr, us: wUs, g: wG, c: wC };
  const rho = (a, b) => a === b ? 1 :
    (a === "kr" && b === "us") || (a === "us" && b === "kr") ? st.rhoKrUs :
    (a === "kr" && b === "g") || (a === "g" && b === "kr") ? st.rhoKrMt :
    (a === "us" && b === "g") || (a === "g" && b === "us") ? st.rhoUsMt : 0;
  const ks = ["kr", "us", "g", "c"];
  let expRet = 0, varP = 0;
  ks.forEach((i) => { expRet += w[i] * mu[i]; ks.forEach((j) => { varP += w[i] * w[j] * (sg[i] / 100) * (sg[j] / 100) * rho(i, j); }); });
  const volP = Math.sqrt(Math.max(varP, 0)) * 100;
  const m = Math.log(1 + expRet / 100) - (volP / 100) ** 2 / 2; // 대략적 로그수익
  const band10 = (q) => Math.exp(10 * m + q * (volP / 100) * Math.sqrt(10)); // 10년 배수
  return { w, expRet, volP, badYear: expRet - 2 * volP, p10: band10(-1.28), p50: band10(0), p90: band10(1.28) };
}

// ---------------- 화면들 ----------------
function Dots({ n, at }) {
  return (
    <div style={{ display: "flex", gap: 6, justifyContent: "center", margin: "14px 0 4px" }}>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} style={{ width: i === at ? 18 : 6, height: 6, borderRadius: 999, background: i === at ? C.blue : C.line, transition: "all .2s" }} />
      ))}
    </div>
  );
}

function RiskScale({ volP }) {
  const score = Math.min(10, Math.max(0.4, (volP / 24) * 10));
  const marks = [
    { at: 0.9, ko: "예금" }, { at: 3.1, ko: "채권 위주" }, { at: 7.5, ko: "코스피 전체" }, { at: 10, ko: "그 이상" },
  ];
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ position: "relative", height: 10, borderRadius: 999, background: `linear-gradient(90deg, ${C.tealSoft}, ${C.sandSoft} 55%, ${C.coralSoft})`, border: HAIR }}>
        <div style={{ position: "absolute", top: -4, left: `calc(${(score / 10) * 100}% - 9px)`, width: 18, height: 18, borderRadius: 999, background: C.blue, border: "3px solid #fff", boxShadow: "0 1px 4px rgba(28,43,69,0.3)" }} />
      </div>
      <div style={{ position: "relative", height: 16, marginTop: 6 }}>
        {marks.map((mk) => (
          <span key={mk.ko} style={{ position: "absolute", left: `${(mk.at / 10) * 100}%`, transform: "translateX(-50%)", fontSize: 10, color: C.faint, whiteSpace: "nowrap" }}>{mk.ko}</span>
        ))}
      </div>
    </div>
  );
}

export default function SimpleApp({ onGraduate, onExit }) {
  // step: -1 인트로, 0..4 질문, 90 비상금 안내, 5 만들기, 6 진단
  const [step, setStep] = useState(-1);
  const [ans, setAns] = useState({});
  const [eq, setEq] = useState(50);
  const [krShare, setKrShare] = useState(0.5);
  const [goldOn, setGoldOn] = useState(false);
  const [amountMw, setAmountMw] = useState(1000);
  const [booted, setBooted] = useState(false);
  const preset = useMemo(() => (ans.crash ? pickPreset(ans) : null), [ans]);
  const M = useMemo(() => blockMetrics(eq, krShare, goldOn, DEFAULT_SETTINGS), [eq, krShare, goldOn]);

  // ---- 자동 저장 / 복원 ----
  useEffect(() => { (async () => {
    try { const s = await store.get(KEY_SIMPLE); if (s) { const d = JSON.parse(s);
      if (d && typeof d.step === "number") { setStep(d.step); setAns(d.ans || {}); setEq(d.eq ?? 50); setKrShare(d.krShare ?? 0.5); setGoldOn(!!d.goldOn); setAmountMw(d.amountMw ?? 1000); } } } catch (e) {}
    setBooted(true);
  })(); }, []);
  useEffect(() => { if (!booted) return;
    try { store.set(KEY_SIMPLE, JSON.stringify({ step, ans, eq, krShare, goldOn, amountMw })); } catch (e) {}
  }, [booted, step, ans, eq, krShare, goldOn, amountMw]);

  const reset = () => { setStep(-1); setAns({}); setEq(50); setKrShare(0.5); setGoldOn(false); setAmountMw(1000); try { store.del(KEY_SIMPLE); } catch (e) {} };
  const pick = (qi, v) => {
    const q = SQ[qi]; const nx = { ...ans, [q.id]: v }; setAns(nx);
    if (q.id === "emergency" && v === "none") { setStep(90); return; }
    if (qi === SQ.length - 1) { const pr = pickPreset(nx); setEq(pr.eq); setStep(5); }
    else setStep(qi + 1);
  };

  const wrap = { maxWidth: 560, margin: "0 auto", padding: "18px 16px 96px", fontFamily: FONT, color: C.ink };

  // ---------------- 인트로 ----------------
  if (step === -1) return (
    <div style={wrap}>
      <div style={{ textAlign: "center", padding: "26px 0 10px" }}>
        <Bird mood="cheer" size={84} />
        <div style={{ fontFamily: SERIF, fontSize: 24, fontWeight: 700, marginTop: 14, letterSpacing: "-0.01em" }}>간단하게 시작해요</div>
        <div style={{ fontSize: 14, color: C.sub, marginTop: 8, lineHeight: 1.65 }}>
          다섯 가지만 여쭤볼게요. 정답은 없어요.<br />끝나면 내 그릇에 맞는 조합을 함께 만들어봐요.
        </div>
      </div>
      <SBtn onClick={() => setStep(0)} style={{ marginTop: 18 }}>시작하기</SBtn>
      <button onClick={onExit} style={{ display: "block", margin: "14px auto 0", background: "none", border: "none", color: C.faint, fontSize: 12.5, cursor: "pointer", fontFamily: FONT }}>← 모드 선택으로</button>
    </div>
  );

  // ---------------- 비상금 안내 (막지 않고, 솔직하게) ----------------
  if (step === 90) return (
    <div style={wrap}>
      <Dots n={SQ.length} at={4} />
      <SCard style={{ marginTop: 10, borderColor: C.apricot + "88", background: C.apricotSoft }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <Bird mood="worried" size={52} />
          <div>
            <div style={{ fontSize: 16, fontWeight: 800 }}>투자보다 먼저 챙길 게 있어요</div>
            <div style={{ fontSize: 13.5, color: C.sub, marginTop: 6, lineHeight: 1.7 }}>
              비상금이 없으면, 하필 시장이 나쁠 때 투자금을 헐어 쓰게 되기 쉬워요. 그게 손실이 확정되는 가장 흔한 경로예요.
              <b style={{ color: C.ink }}> 생활비 3개월치</b>를 먼저 예·적금으로 만들어두는 걸 추천해요.
            </div>
          </div>
        </div>
      </SCard>
      <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
        <SBtn onClick={() => { setStep(-1); }} kind="ghost">알겠어요, 비상금부터 만들게요</SBtn>
        <SBtn onClick={() => { const pr = pickPreset(ans); setEq(pr.eq); setStep(5); }} kind="warm">그래도 조합은 구경해볼래요</SBtn>
      </div>
      <div style={{ fontSize: 11.5, color: C.faint, marginTop: 10, textAlign: "center" }}>구경은 자유예요. 대신 안정 쪽으로 맞춰서 보여드릴게요.</div>
    </div>
  );

  // ---------------- 질문 ----------------
  if (step >= 0 && step < SQ.length) {
    const q = SQ[step];
    return (
      <div style={wrap}>
        <Dots n={SQ.length} at={step} />
        <div style={{ display: "flex", gap: 10, alignItems: "center", margin: "10px 0 16px" }}>
          <Bird mood="happy" size={40} />
          <div style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.5 }}>{q.q}</div>
        </div>
        {q.opts.map((o) => (
          <Opt key={String(o.v)} sub={o.sub} on={ans[q.id] === o.v} onClick={() => pick(step, o.v)}>{o.ko}</Opt>
        ))}
        {step > 0 && (
          <button onClick={() => setStep(step - 1)} style={{ display: "block", margin: "8px auto 0", background: "none", border: "none", color: C.faint, fontSize: 12.5, cursor: "pointer", fontFamily: FONT }}>← 이전 질문</button>
        )}
      </div>
    );
  }

  // ---------------- 만들기 ----------------
  if (step === 5) {
    const rows = [
      { ko: "한국 주식", w: M.w.kr, col: C.blue }, { ko: "미국 주식", w: M.w.us, col: "#4A659B" },
      { ko: "금", w: M.w.g, col: C.gold }, { ko: "예금·현금", w: M.w.c, col: "#B9B2A6" },
    ].filter((r) => r.w > 0.001);
    return (
      <div style={wrap}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: SERIF, fontSize: 19, fontWeight: 700 }}>나의 조합 만들기</div>
          <button onClick={reset} style={{ background: "none", border: "none", color: C.faint, fontSize: 12, cursor: "pointer", fontFamily: FONT }}>처음부터</button>
        </div>

        {preset && (
          <SCard style={{ marginTop: 12 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <Ic name={preset.icon} size={22} color={C.blue} />
              <div>
                <div style={{ fontSize: 15, fontWeight: 800 }}>답변을 보니, <span style={{ color: C.blue }}>{preset.ko}형</span>에서 시작하면 좋겠어요</div>
                <div style={{ fontSize: 12.5, color: C.sub, marginTop: 2 }}>{preset.line} · 아래에서 얼마든지 조절할 수 있어요</div>
              </div>
            </div>
            {preset.capped && (
              <div style={{ marginTop: 10, fontSize: 12, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 6, padding: "8px 10px", lineHeight: 1.6 }}>
                비상금이나 투자 기간을 생각해서, 한 단계 안정 쪽으로 맞췄어요.
              </div>
            )}
          </SCard>
        )}

        <SCard style={{ marginTop: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div style={{ fontSize: 14, fontWeight: 800 }}>주식 비중</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: C.blue }}>{eq}%</div>
          </div>
          <input type="range" min={0} max={95} step={5} value={eq} onChange={(e) => setEq(+e.target.value)} style={{ width: "100%", accentColor: C.blue, marginTop: 8 }} />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.faint }}><span>지키기</span><span>불리기</span></div>
          <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
            {SPRESETS.map((p) => (
              <button key={p.k} onClick={() => setEq(p.eq)}
                style={{ flex: 1, border: eq === p.eq ? "1.5px solid " + C.blue : "1.5px solid " + C.line, background: eq === p.eq ? C.blueSoft : "#fff", color: eq === p.eq ? C.blue : C.sub, borderRadius: RAD.btn, padding: "8px 0", fontSize: 12.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>
                {p.ko}
              </button>
            ))}
          </div>
        </SCard>

        <SCard style={{ marginTop: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 800 }}>주식 안에서, 한국과 미국은?</div>
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            {[{ v: 0.7, ko: "한국 위주" }, { v: 0.5, ko: "반반" }, { v: 0.3, ko: "미국 위주" }].map((o) => (
              <button key={o.v} onClick={() => setKrShare(o.v)}
                style={{ flex: 1, border: krShare === o.v ? "1.5px solid " + C.blue : "1.5px solid " + C.line, background: krShare === o.v ? C.blueSoft : "#fff", color: krShare === o.v ? C.blue : C.sub, borderRadius: RAD.btn, padding: "10px 0", fontSize: 12.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>
                {o.ko}
              </button>
            ))}
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, fontSize: 13.5, fontWeight: 700, color: C.ink, cursor: "pointer" }}>
            <input type="checkbox" checked={goldOn} onChange={(e) => setGoldOn(e.target.checked)} style={{ width: 17, height: 17, accentColor: C.blue }} />
            금도 조금(5%) 담기
            <span style={{ fontSize: 11.5, color: C.faint, fontWeight: 400 }}>— 주식과 다르게 움직이는 완충재예요</span>
          </label>
        </SCard>

        <SCard style={{ marginTop: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 10 }}>지금 조합</div>
          <div style={{ display: "flex", height: 14, borderRadius: 999, overflow: "hidden", border: HAIR }}>
            {rows.map((r) => <div key={r.ko} style={{ width: (r.w * 100) + "%", background: r.col }} />)}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 14px", marginTop: 10 }}>
            {rows.map((r) => (
              <span key={r.ko} style={{ fontSize: 12.5, color: C.sub, display: "inline-flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: r.col }} />{r.ko} <b style={{ color: C.ink }}>{Math.round(r.w * 100)}%</b>
              </span>
            ))}
          </div>
          <div style={{ marginTop: 12, borderTop: HAIR, paddingTop: 10, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13, color: C.sub }}>투자 금액</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <input type="number" value={amountMw} min={10} step={10} onChange={(e) => setAmountMw(Math.max(10, +e.target.value || 10))}
                style={{ width: 90, textAlign: "right", fontSize: 14, fontWeight: 800, color: C.ink, border: "1.5px solid " + C.line, borderRadius: RAD.input, padding: "6px 8px", fontFamily: FONT }} />
              <span style={{ fontSize: 13, color: C.sub }}>만원</span>
            </span>
          </div>
        </SCard>

        <SBtn onClick={() => setStep(6)} style={{ marginTop: 14 }}>이 조합, 뱁이의 진단 보기 →</SBtn>
      </div>
    );
  }

  // ---------------- 진단 (세 장, 전부 펼침) ----------------
  const praises = [];
  if (M.w.c >= 0.1) praises.push("현금을 " + Math.round(M.w.c * 100) + "% 남겨뒀어요. 시장이 흔들릴 때 버티게 해주는 안전벨트예요.");
  if (M.w.kr > 0.001 && M.w.us > 0.001) praises.push("한국과 미국에 나눠 담았어요. 한 나라 경기에만 기대지 않는 좋은 습관이에요.");
  if (goldOn) praises.push("금을 조금 담았어요. 주식이 힘들 때 다르게 움직여주는 완충재가 생겼어요.");
  if ((ans.horizon ?? 5) >= 10 && eq >= 50) praises.push("긴 시간을 두고 투자하니, 지금 정도의 주식 비중은 시간이 편이 되어줘요.");
  if ((ans.crash === "hold" || ans.crash === "buy") && eq >= 50) praises.push("하락에서 버틸 수 있다고 하셨죠. 그 성향과 이 조합이 잘 맞아요.");
  if (!praises.length) praises.push("무리하지 않는 조합이에요. 천천히 시작하는 것도 훌륭한 전략이에요.");

  const warns = [];
  if (ans.crash === "sellall" && eq > 45) warns.push("하락하면 전부 팔 것 같다고 하셨는데, 주식 비중이 꽤 높아요. 한 단계 낮추는 것도 방법이에요.");
  if ((ans.horizon ?? 5) <= 2 && eq > 45) warns.push("3년 안에 쓸 돈이라면, 주식 비중이 높을수록 필요할 때 하필 내려가 있을 위험이 커져요.");
  if (ans.emergency === "none") warns.push("비상금 없이 시작하면, 급전이 필요할 때 손해를 확정 짓기 쉬워요. 3개월치부터 만들어봐요.");

  const badWon = amountMw * (1 + M.badYear / 100);
  return (
    <div style={wrap}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontFamily: SERIF, fontSize: 19, fontWeight: 700 }}>뱁이의 진단</div>
        <button onClick={() => setStep(5)} style={{ background: "none", border: "none", color: C.faint, fontSize: 12, cursor: "pointer", fontFamily: FONT }}>← 조합 고치기</button>
      </div>

      <SCard style={{ marginTop: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <Ic name="check" size={17} color={C.teal} /><span style={{ fontSize: 14.5, fontWeight: 800 }}>잘하고 있는 점</span>
        </div>
        {praises.map((s, i) => <div key={i} style={{ fontSize: 13.5, color: C.sub, lineHeight: 1.7, marginTop: i ? 6 : 0 }}>· {s}</div>)}
      </SCard>

      <SCard style={{ marginTop: 10 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Ic name="alert" size={17} color={C.sand} /><span style={{ fontSize: 14.5, fontWeight: 800 }}>지금 위험 수준</span>
        </div>
        <RiskScale volP={M.volP} />
        <div style={{ fontSize: 13.5, color: C.sub, lineHeight: 1.7, marginTop: 12 }}>
          아주 나쁜 해에는 {fmtMw(amountMw)}이 <b style={{ color: C.ink }}>{fmtMw(Math.max(badWon, 0))}</b> 근처까지 내려갈 수 있어요.
          그 화면을 보고도 계획대로 갈 수 있는지가 기준이에요.
        </div>
        <div style={{ fontSize: 12, color: C.faint, marginTop: 8, lineHeight: 1.6 }}>
          참고로, 위험 0이 목표가 아니에요. 위험을 전혀 안 지면 돈이 자라지도 않아요. 내가 견딜 수 있는 만큼만 지는 게 목표예요.
        </div>
        {warns.map((s, i) => (
          <div key={i} style={{ marginTop: 8, fontSize: 12.5, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 6, padding: "8px 10px", lineHeight: 1.6 }}>{s}</div>
        ))}
      </SCard>

      <SCard style={{ marginTop: 10 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <Ic name="trend" size={17} color={C.blue} /><span style={{ fontSize: 14.5, fontWeight: 800 }}>10년 뒤 전망 (딱 떨어지는 답은 없어요)</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, textAlign: "center" }}>
          {[{ ko: "아쉬운 경우", v: M.p10, col: C.sub }, { ko: "가운데쯤", v: M.p50, col: C.blue }, { ko: "좋은 경우", v: M.p90, col: C.teal }].map((b) => (
            <div key={b.ko} style={{ border: HAIR, borderRadius: RAD.card, padding: "12px 6px" }}>
              <div style={{ fontSize: 11, color: C.faint }}>{b.ko}</div>
              <div style={{ fontSize: 15, fontWeight: 800, color: b.col, marginTop: 4 }}>{fmtMw(amountMw * b.v)}</div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: C.faint, marginTop: 10, lineHeight: 1.6 }}>
          {fmtMw(amountMw)}을 10년 두었을 때의 대략적인 범위예요. 미래는 넓은 범위로만 말할 수 있고, 그게 정직한 답이에요.
        </div>
      </SCard>

      <SCard style={{ marginTop: 14, background: C.blueSoft, borderColor: C.blue + "33" }}>
        <div style={{ fontSize: 14.5, fontWeight: 800 }}>더 깊이 보고 싶다면</div>
        <div style={{ fontSize: 13, color: C.sub, marginTop: 5, lineHeight: 1.65 }}>
          상세 모드에서는 종목 하나하나 고르고, 세금과 스트레스 테스트까지 볼 수 있어요.
          지금까지의 답변은 그대로 가져가요.
        </div>
        <SBtn onClick={() => onGraduate({
          answers: {
            goal: ans.goal, horizon: ans.horizon,
            crash: ans.crash ? [ans.crash] : undefined,
            emergency: ans.emergency === "enough" ? 8 : ans.emergency === "some" ? 2 : 0,
          }, budgetMw: amountMw,
        })} style={{ marginTop: 12 }}>상세 모드로 이어가기 →</SBtn>
      </SCard>

      <div style={{ textAlign: "center", marginTop: 18 }}>
        <button onClick={onExit} style={{ background: "none", border: "none", color: C.faint, fontSize: 12.5, cursor: "pointer", fontFamily: FONT }}>← 모드 선택으로</button>
      </div>
      <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", marginTop: 14, lineHeight: 1.6 }}>
        교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다.
      </div>
    </div>
  );
}
