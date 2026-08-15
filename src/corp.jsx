// ================= 뱁새 v12 — 기업분석 =================
// 시장 지도(업종 성장 사분면·업종 개요·PBR×ROE·멀티플 분포)와
// 기업 상세(멀티플 위치·3개년 재무·밸류에이션 풋볼필드·DCF 분석 + 리버스 DCF).
// 원칙: 값 하나를 단정하지 않고, 분포와 범위와 가정을 보여줍니다.
import React, { useState, useEffect, useMemo, useRef } from "react";
import { C, FONT, SERIF, RAD, HAIR } from "./tokens.js";
import { Ic } from "./icons.jsx";
import { Bird, store, SECTORS, SEC, KEY_SLOTS, KEY_SLOT } from "./detail.jsx";

const KEY_DCF = "baepsae_v12_dcf";
const CREDIT = "이성진, INSEAD MBA 26J · Jack (Sung Jin) Lee, INSEAD MBA 26J";

// ---------------- 포맷 ----------------
const fmtEok = (v) => v == null ? "—" : Math.abs(v) >= 10000 ? (v / 10000).toFixed(1) + "조원" : Math.round(v).toLocaleString() + "억원";
const fmtWon = (v) => v == null ? "—" : Math.round(v).toLocaleString() + "원";
const fmtShort = (v) => v == null ? "—" : Math.abs(v) >= 1e8 ? (v / 1e8).toFixed(1) + "억" : Math.abs(v) >= 1e4 ? (v / 1e4).toFixed(1) + "만" : Math.round(v).toLocaleString();
const pc = (v, d = 1) => v == null ? "—" : v.toFixed(d) + "%";
const clamp = (v, a, b) => Math.min(Math.max(v, a), b);

// ---------------- 공용 아톰 ----------------
const Card = ({ children, style = {} }) => (
  <div style={{ background: "#FFFFFF", border: HAIR, borderRadius: RAD.card, padding: 18, ...style }}>{children}</div>
);
const H = ({ children, onWhy }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
    <span style={{ fontSize: 14.5, fontWeight: 800, color: C.ink }}>{children}</span>
    {onWhy && <button onClick={onWhy} style={{ fontSize: 10, color: C.faint, background: C.bg, border: "none", borderRadius: 999, width: 16, height: 16, cursor: "pointer", fontWeight: 800, fontFamily: FONT }}>?</button>}
  </div>
);
const Sub = ({ children, style = {} }) => <div style={{ fontSize: 12, color: C.sub, lineHeight: 1.6, ...style }}>{children}</div>;
const ChipBtn = ({ on, onClick, children }) => (
  <button onClick={onClick} style={{ border: on ? "1.5px solid " + C.blue : "1.5px solid " + C.line, background: on ? C.blueSoft : "#fff", color: on ? C.blue : C.sub, borderRadius: 999, padding: "5px 11px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{children}</button>
);

// ---------------- 설명 시트 ----------------
const EXPL = {
  quad: { t: "업종 성장 사분면", b: "가로축은 업종의 3년 매출 성장률(상장사 합산 기준), 세로축은 각 기업의 3년 매출 성장률이에요. 오른쪽 위는 성장하는 산업 안에서 함께 성장하는 기업이고, 왼쪽 위는 산업이 역성장하는데 홀로 성장하는 기업 — 점유율 확대인지 일회성 효과인지 확인이 필요한 구간이에요. 주의: '업종 성장'은 상장사 매출 합산 기준이라, 비상장사와 해외 매출 구성에 따라 실제 시장 성장과 차이가 날 수 있어요." },
  secrank: { t: "업종 성장률 순위", b: "각 업종의 3년 연평균 매출 성장률(상장사 합산 기준)을 큰 순서대로 늘어놓았어요. 막대 옆의 매출 규모와 수익성을 함께 보면 '커지는 판인가, 돈이 되는 판인가'를 같이 판단할 수 있어요. 표본이 5개 미만인 업종은 성장률을 표시하지 않아요." },
  scatter: { t: "PBR × ROE", b: "가로축은 자기자본이익률(ROE), 세로축은 주가순자산비율(PBR)이에요. 보통 자본을 잘 굴리는 회사일수록(ROE 높음) 장부가치 대비 높은 값(PBR 높음)에 거래돼요. 이 관계에서 크게 벗어난 위치는 '왜?'라고 물어볼 출발점이지, 그 자체로 싸다/비싸다의 답은 아니에요." },
  box: { t: "업종별 분포", b: "상자는 업종 내 25~75% 구간, 가운데 선은 중간값이에요. 같은 PER 10배라도 업종에 따라 비싼 값일 수도, 싼 값일 수도 있어요 — 멀티플은 항상 같은 업종의 분포 안에서 읽는 것이 기본이에요." },
  per: { t: "PER (주가수익비율)", b: "시장이 이 회사의 이익 1원에 몇 원을 내고 있는지예요. 높다는 건 시장이 앞으로의 성장을 크게 기대한다는 뜻이고, 그 기대가 실현되지 않으면 주가가 조정될 수 있다는 뜻이기도 해요. 적자 기업은 PER을 계산할 수 없어요." },
  pbr: { t: "PBR (주가순자산비율)", b: "회사 장부상 순자산 1원을 시장이 몇 원으로 평가하는지예요. 1배 미만은 장부가치보다 싸게 거래된다는 뜻인데, 그 자체로 저평가라기보다 '시장이 이 자산의 수익성을 의심한다'는 신호일 때가 많아요. ROE와 함께 읽어야 해요." },
  roe: { t: "ROE (자기자본이익률)", b: "주주 돈 100원으로 1년에 몇 원을 벌었는지예요. 꾸준히 높은 ROE는 좋은 사업의 흔적이지만, 부채를 늘려도 ROE는 올라가요 — 부채비율과 함께 보세요." },
  payout: { t: "배당성향", b: "번 이익 중 얼마를 배당으로 돌려주는지예요. 이익보다 배당이 큰 상태(100% 초과)가 이어지면 지속되기 어려워요." },
  ff: { t: "밸류에이션 풋볼필드", b: "잣대 하나로는 회사를 판단할 수 없어요. PER·PBR·PSR·배당수익률 같은 여러 잣대에서 이 회사가 같은 업종 회사들 중 낮은 쪽에 있는지 높은 쪽에 있는지를 나란히 놓은 그림이에요. 파란 상자는 업종의 25~75% 구간, 주황 점이 이 회사의 위치예요. 낮다고 곧 싸다는 뜻은 아니에요 — 시장이 왜 이 위치에 두었는지 물어보는 출발점이에요." },
  dcf: { t: "DCF 분석", b: "미래 이익을 가정하고 현재 가치로 할인해 더하는 계산이에요. 여기서는 순이익을 현금흐름으로 근사하는 큰 단순화를 써요(실제로는 투자·운전자본 등으로 달라요). 그래서 이 도구의 목적은 '적정주가 찾기'가 아니라, 가정을 바꿀 때 값이 얼마나 민감하게 움직이는지, 그리고 지금 주가에는 어떤 성장 기대가 담겨 있는지를 보는 거예요." },
  rev: { t: "리버스 DCF", b: "계산 방향을 뒤집어서, '지금 주가가 정당화되려면 앞으로 몇 %씩 성장해야 하나'를 풉니다. 그 성장률이 회사의 과거와 업종 현실에 비추어 그럴듯한지 스스로 판단해보는 것 — 그게 이 도구의 핵심 질문이에요." },
};
function ExplainSheet({ id, onClose }) {
  if (!id || !EXPL[id]) return null;
  const e = EXPL[id];
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(28,43,69,0.35)", zIndex: 90, display: "flex", alignItems: "flex-end", justifyContent: "center" }}>
      <div onClick={(ev) => ev.stopPropagation()} style={{ background: "#fff", borderRadius: "12px 12px 0 0", padding: "22px 20px 30px", maxWidth: 560, width: "100%", fontFamily: FONT }}>
        <div style={{ fontSize: 15.5, fontWeight: 800, color: C.ink }}>{e.t}</div>
        <div style={{ fontSize: 13.5, color: C.sub, lineHeight: 1.75, marginTop: 8 }}>{e.b}</div>
        <button onClick={onClose} style={{ marginTop: 16, width: "100%", background: C.blue, color: "#fff", border: "none", borderRadius: RAD.btn, padding: "12px", fontSize: 14, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>알겠어요</button>
      </div>
    </div>
  );
}

// ---------------- 사분면 라벨 (전문적 톤) ----------------
const QUADS = [
  { x: 1, y: 1, t: "성장 산업 · 성장 기업", s: "산업과 기업이 함께 성장" },
  { x: -1, y: 1, t: "역성장 산업 · 성장 기업", s: "산업 역풍 속 단독 성장 — 점유율 확대 여부 확인" },
  { x: 1, y: -1, t: "성장 산업 · 역성장 기업", s: "산업 성장의 수혜에서 소외" },
  { x: -1, y: -1, t: "역성장 산업 · 역성장 기업", s: "산업·기업 동반 위축" },
];

// ---------------- SVG 산점도 (사분면 / PBR×ROE 공용) ----------------
function Scatter({ pts, xDomain, yDomain, xLabel, yLabel, quads, onPick, height = 420, zoomable }) {
  const W = 720, Hh = height, m = { l: 46, r: 14, t: 26, b: 40 };
  const [z, setZ] = useState({ k: 1, cx: (xDomain[0] + xDomain[1]) / 2, cy: (yDomain[0] + yDomain[1]) / 2 });
  const svgRef = useRef(null);
  const drag = useRef(null);
  const moved = useRef(false);
  const spanX = (xDomain[1] - xDomain[0]) / z.k, spanY = (yDomain[1] - yDomain[0]) / z.k;
  const cx = clamp(z.cx, xDomain[0] + spanX / 2, xDomain[1] - spanX / 2);
  const cy = clamp(z.cy, yDomain[0] + spanY / 2, yDomain[1] - spanY / 2);
  const xd = [cx - spanX / 2, cx + spanX / 2], yd = [cy - spanY / 2, cy + spanY / 2];
  const plotW = W - m.l - m.r, plotH = Hh - m.t - m.b;
  const sx = (v) => m.l + (clamp(v, xd[0], xd[1]) - xd[0]) / (xd[1] - xd[0]) * plotW;
  const sy = (v) => Hh - m.b - (clamp(v, yd[0], yd[1]) - yd[0]) / (yd[1] - yd[0]) * plotH;
  const x0 = xd[0] < 0 && xd[1] > 0 ? sx(0) : null;
  const y0 = yd[0] < 0 && yd[1] > 0 ? sy(0) : null;
  const ticksX = [xd[0], (xd[0] + xd[1]) / 2, xd[1]];
  const ticksY = [yd[0], (yd[0] + yd[1]) / 2, yd[1]];

  // 휠 확대 (커서 기준) — passive:false 로 직접 부착
  useEffect(() => {
    if (!zoomable) return;
    const el = svgRef.current; if (!el) return;
    const onWheel = (e) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const vx = (e.clientX - rect.left) * W / rect.width;
      const vy = (e.clientY - rect.top) * Hh / rect.height;
      const dx = xd[0] + clamp((vx - m.l) / plotW, 0, 1) * (xd[1] - xd[0]);
      const dyv = yd[0] + clamp((Hh - m.b - vy) / plotH, 0, 1) * (yd[1] - yd[0]);
      const nk = clamp(z.k * (e.deltaY < 0 ? 1.25 : 0.8), 1, 12);
      const r = z.k / nk;
      setZ({ k: nk, cx: dx + (cx - dx) * r, cy: dyv + (cy - dyv) * r });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const zoomBy = (f) => setZ((o) => ({ ...o, k: clamp(o.k * f, 1, 12), cx, cy }));
  const reset = () => setZ({ k: 1, cx: (xDomain[0] + xDomain[1]) / 2, cy: (yDomain[0] + yDomain[1]) / 2 });
  const onPointerDown = (e) => {
    if (!zoomable || z.k === 1) return;
    moved.current = false;
    drag.current = { x: e.clientX, y: e.clientY, cx, cy };
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err) {}
  };
  const onPointerMove = (e) => {
    const d = drag.current; if (!d || !svgRef.current) return;
    if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 5) moved.current = true;
    const rect = svgRef.current.getBoundingClientRect();
    const ddx = (e.clientX - d.x) * (W / rect.width) * (xd[1] - xd[0]) / plotW;
    const ddy = (e.clientY - d.y) * (Hh / rect.height) * (yd[1] - yd[0]) / plotH;
    setZ((o) => ({ ...o, cx: d.cx - ddx, cy: d.cy + ddy }));
  };
  const onPointerUp = () => { drag.current = null; };

  const visible = pts.filter((p) => p.x >= xd[0] && p.x <= xd[1] && p.y >= yd[0] && p.y <= yd[1]);
  const labelOn = zoomable && z.k >= 2 && visible.length <= 30;

  return (
    <div style={{ position: "relative" }}>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${Hh}`}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}
        style={{ width: "100%", height: "auto", display: "block", touchAction: zoomable && z.k > 1 ? "none" : "pan-y", cursor: zoomable && z.k > 1 ? "grab" : "default" }}>
        <rect x={m.l} y={m.t} width={plotW} height={plotH} fill={C.bg} rx="6" />
        {quads && x0 != null && y0 != null && (
          <g>
            <rect x={x0} y={m.t} width={W - m.r - x0} height={y0 - m.t} fill={C.tealSoft} opacity="0.5" />
            <rect x={m.l} y={m.t} width={x0 - m.l} height={y0 - m.t} fill={C.blueSoft} opacity="0.3" />
            <rect x={x0} y={y0} width={W - m.r - x0} height={Hh - m.b - y0} fill={C.sandSoft} opacity="0.35" />
            <rect x={m.l} y={y0} width={x0 - m.l} height={Hh - m.b - y0} fill={C.coralSoft} opacity="0.4" />
            {QUADS.map((q) => {
              const qx = q.x > 0 ? W - m.r - 8 : m.l + 8, anchor = q.x > 0 ? "end" : "start";
              const qy = q.y > 0 ? m.t + 16 : Hh - m.b - 20;
              return (
                <g key={q.t}>
                  <text x={qx} y={qy} textAnchor={anchor} fontSize="11.5" fontWeight="800" fill={C.ink} fontFamily={FONT}>{q.t}</text>
                  <text x={qx} y={qy + 13} textAnchor={anchor} fontSize="9" fill={C.faint} fontFamily={FONT}>{q.s}</text>
                </g>
              );
            })}
          </g>
        )}
        {x0 != null && <line x1={x0} y1={m.t} x2={x0} y2={Hh - m.b} stroke={C.line} strokeWidth="1.5" />}
        {y0 != null && <line x1={m.l} y1={y0} x2={W - m.r} y2={y0} stroke={C.line} strokeWidth="1.5" />}
        {ticksX.map((t, i) => <text key={"x" + i} x={sx(t)} y={Hh - m.b + 16} textAnchor="middle" fontSize="10" fill={C.faint} fontFamily={FONT}>{Math.round(t)}</text>)}
        {ticksY.map((t, i) => <text key={"y" + i} x={m.l - 8} y={sy(t) + 3} textAnchor="end" fontSize="10" fill={C.faint} fontFamily={FONT}>{Math.round(t * 10) / 10}</text>)}
        <text x={(m.l + W - m.r) / 2} y={Hh - 6} textAnchor="middle" fontSize="10.5" fill={C.sub} fontFamily={FONT}>{xLabel}</text>
        <text x={12} y={(m.t + Hh - m.b) / 2} textAnchor="middle" fontSize="10.5" fill={C.sub} fontFamily={FONT} transform={`rotate(-90 12 ${(m.t + Hh - m.b) / 2})`}>{yLabel}</text>
        {pts.map((p) => (
          <circle key={p.id} cx={sx(p.x)} cy={sy(p.y)} r={p.r} fill={p.color} opacity={p.held ? 0.95 : 0.55}
            stroke={p.held ? C.apricotDeep : "#fff"} strokeWidth={p.held ? 2 : 0.5}
            onClick={() => { if (!moved.current && onPick) onPick(p.id); }} style={{ cursor: onPick ? "pointer" : "default" }}>
            <title>{p.label}</title>
          </circle>
        ))}
        {labelOn && visible.map((p) => (
          <text key={"l" + p.id} x={sx(p.x) + p.r + 3} y={sy(p.y) + 3.5} fontSize="9.5" fontWeight="700" fill={C.ink} fontFamily={FONT} pointerEvents="none">{p.nm}</text>
        ))}
      </svg>
      {zoomable && (
        <div style={{ position: "absolute", top: 6, right: 6, display: "flex", gap: 4 }}>
          {[["+", () => zoomBy(1.5)], ["-", () => zoomBy(1 / 1.5)], ["1:1", reset]].map(([ko, fn]) => (
            <button key={ko} onClick={fn} style={{ width: ko === "1:1" ? 34 : 26, height: 26, border: HAIR, background: "#fff", borderRadius: 6, fontSize: 13, fontWeight: 800, color: C.ink, cursor: "pointer", fontFamily: FONT, padding: 0 }}>{ko}</button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------- 사분위 밴드 (기업 페이지 멀티플 행) ----------------
function QuartBand({ q, v, max }) {
  if (!q) return <div style={{ fontSize: 10.5, color: C.faint }}>업종 표본 부족</div>;
  const W = 190, Hh = 16;
  const s = (x) => clamp(x / max, 0, 1) * W;
  return (
    <svg width={W} height={Hh} style={{ display: "block" }}>
      <line x1="0" y1={Hh / 2} x2={W} y2={Hh / 2} stroke={C.line} strokeWidth="2" />
      <rect x={s(q[0])} y={3} width={Math.max(2, s(q[2]) - s(q[0]))} height={Hh - 6} fill={C.blueSoft} rx="3" />
      <line x1={s(q[1])} y1={2} x2={s(q[1])} y2={Hh - 2} stroke={C.blue} strokeWidth="2" />
      {v != null && <circle cx={s(v)} cy={Hh / 2} r="4.5" fill={C.apricotDeep} stroke="#fff" strokeWidth="1.5" />}
    </svg>
  );
}

// ---------------- 3개년 스파크바 ----------------
function Spark3({ label, arr }) {
  const vals = [arr[2], arr[1], arr[0]]; // 과거 → 현재
  if (vals.every((v) => v == null)) return null;
  const mx = Math.max(...vals.map((v) => Math.abs(v || 0)), 1);
  const W = 92, Hh = 62, bw = 22, base = vals.some((v) => (v || 0) < 0) ? Hh * 0.62 : Hh - 14;
  const yoy = (() => {
    const c = arr[0], p = arr[1];
    if (c == null || p == null) return null;
    if (p > 0 && c > 0) return (c / p - 1) * 100;
    if (p <= 0 && c > 0) return "흑전";
    if (p > 0 && c <= 0) return "적전";
    return "적자";
  })();
  return (
    <div style={{ textAlign: "center" }}>
      <svg width={W} height={Hh} style={{ display: "block", margin: "0 auto" }}>
        {vals.map((v, i) => {
          if (v == null) return null;
          const h = Math.abs(v) / mx * (base - 8);
          const x = 6 + i * (bw + 7);
          const y = v >= 0 ? base - h : base;
          return <rect key={i} x={x} y={y} width={bw} height={Math.max(h, 1.5)} rx="2.5"
            fill={i === 2 ? C.blue : "#C7CEDB"} opacity={v >= 0 ? 1 : 0.75} />;
        })}
        <line x1="4" y1={base} x2={W - 4} y2={base} stroke={C.line} strokeWidth="1" />
      </svg>
      <div style={{ fontSize: 11, fontWeight: 800, color: C.ink, marginTop: 4 }}>{label}</div>
      <div style={{ fontSize: 10, color: C.sub }}>{fmtEok(arr[0])}</div>
      <div style={{ fontSize: 10, fontWeight: 800, color: typeof yoy === "number" ? (yoy >= 0 ? C.teal : C.coral) : C.coral }}>
        {typeof yoy === "number" ? (yoy >= 0 ? "+" : "") + yoy.toFixed(1) + "%" : yoy || ""}
      </div>
    </div>
  );
}

// ---------------- DCF 계산 (순수 함수) ----------------
export function dcfPerShare({ ni0, sharesM, g1, fade, disc, term }) {
  // ni0: 억원, sharesM: 백만주, 수익률은 %. 반환: 원/주
  if (!ni0 || !sharesM || sharesM <= 0) return null;
  const d = disc / 100, tg = term / 100;
  if (d <= tg + 0.005) return null;
  let pv = 0, ni = ni0;
  for (let t = 1; t <= 5; t++) {
    const g = fade ? (g1 + (term - g1) * (t - 1) / 4) / 100 : g1 / 100;
    ni = ni * (1 + g);
    pv += ni / Math.pow(1 + d, t);
  }
  const tv = ni * (1 + tg) / (d - tg);
  pv += tv / Math.pow(1 + d, 5);
  return pv / sharesM * 100; // 억원/백만주 → 원
}
export function reverseDcf({ price, ni0, sharesM, fade, disc, term }) {
  if (!price || !ni0 || ni0 <= 0 || !sharesM) return null;
  const f = (g) => dcfPerShare({ ni0, sharesM, g1: g, fade, disc, term }) - price;
  let lo = -30, hi = 60;
  if (f(lo) > 0) return { edge: "low" };
  if (f(hi) < 0) return { edge: "high" };
  for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; (f(mid) > 0 ? hi = mid : lo = mid); }
  return { g: (lo + hi) / 2 };
}

// ---------------- 데이터 없음 안내 ----------------
function MissingData({ onRetry }) {
  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "44px 16px", textAlign: "center", fontFamily: FONT, color: C.ink }}>
      <Bird mood="think" size={72} />
      <div style={{ fontFamily: SERIF, fontSize: 21, fontWeight: 700, marginTop: 14 }}>기업분석 데이터가 아직 없어요</div>
      <Card style={{ marginTop: 16, textAlign: "left" }}>
        <Sub>
          데이터 파이프라인이 한 번 돌아야 corp.json 이 만들어져요.<br /><br />
          1. GitHub 저장소 → <b style={{ color: C.ink }}>Actions</b> 탭<br />
          2. <b style={{ color: C.ink }}>시세 데이터 갱신</b> 워크플로 선택<br />
          3. <b style={{ color: C.ink }}>Run workflow</b> 버튼 클릭<br />
          4. 완료(10~30분) 후 이 페이지 새로고침
        </Sub>
      </Card>
      <button onClick={onRetry} style={{ marginTop: 14, background: C.blue, color: "#fff", border: "none", borderRadius: RAD.btn, padding: "12px 22px", fontSize: 13.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>다시 확인</button>
    </div>
  );
}

// ---------------- 시장 지도 ----------------
export function MarketView({ data, heldMap, onOpen, setExplain }) {
  const [capMin, setCapMin] = useState(1);
  const [secFilter, setSecFilter] = useState("all");
  const [heldOnly, setHeldOnly] = useState(false);
  const [heldNote, setHeldNote] = useState(false);
  const [boxKey, setBoxKey] = useState("per");
  const comps = data.companies, secs = data.sectors;
  const heldCount = Object.keys(heldMap).length;
  const passBase = (c) => (heldOnly ? !!heldMap[c.t] : (c.cap || 0) >= capMin) && (secFilter === "all" || c.s === secFilter);

  const quadPts = useMemo(() => comps
    .filter((c) => c.g3 != null && secs[c.s]?.g != null && passBase(c))
    .map((c) => ({ id: c.t, nm: c.nk, x: secs[c.s].g, y: c.g3, r: clamp(Math.sqrt(c.cap || 0.3) * 2.6, 2.5, 15),
      color: SEC(c.s).color, held: !!heldMap[c.t], label: `${c.nk} · ${SEC(c.s).ko}\n업종 ${pc(secs[c.s].g)} · 기업 ${pc(c.g3)} · ${c.cap ? c.cap.toFixed(1) + "조" : ""}` })), [comps, secs, capMin, secFilter, heldMap, heldOnly]);

  const secRank = useMemo(() => Object.entries(secs)
    .filter(([k, s]) => s.g != null)
    .map(([k, s]) => ({ k, ko: SEC(k).ko, g: s.g, rev0: s.rev0, opm: s.opm, roe: s.roe, color: SEC(k).color }))
    .sort((a, b) => b.g - a.g), [secs]);
  const secGMax = Math.max(...secRank.map((r) => Math.abs(r.g)), 1);
  const secExcluded = Object.entries(secs).filter(([k, s]) => s.g == null).map(([k, s]) => `${SEC(k).ko}(${s.n})`);

  const pbrRoePts = useMemo(() => comps
    .filter((c) => c.pbr != null && c.roe != null && passBase(c))
    .map((c) => ({ id: c.t, nm: c.nk, x: c.roe, y: c.pbr, r: clamp(Math.sqrt(c.cap || 0.3) * 2.6, 2.5, 15),
      color: SEC(c.s).color, held: !!heldMap[c.t], label: `${c.nk}\nROE ${pc(c.roe)} · PBR ${c.pbr}배` })), [comps, capMin, secFilter, heldMap, heldOnly]);
  const hasMult = useMemo(() => comps.some((c) => c.per != null || c.pbr != null), [comps]);

  const boxRows = useMemo(() => Object.entries(secs)
    .map(([k, s]) => ({ k, ko: SEC(k).ko, n: s.n, q: boxKey === "per" ? s.perQ : s.pbrQ, color: SEC(k).color }))
    .filter((r) => r.q).sort((a, b) => a.q[1] - b.q[1]), [secs, boxKey]);
  const boxMax = boxKey === "per" ? 60 : 8;

  const secKeys = useMemo(() => [...new Set(comps.map((c) => c.s))].sort((a, b) => (secs[b]?.mc || 0) - (secs[a]?.mc || 0)), [comps, secs]);
  const heldN = quadPts.filter((p) => p.held).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        {[[0, "전체"], [1, "1조 이상"], [10, "10조 이상"]].map(([v, ko]) => (
          <ChipBtn key={v} on={capMin === v && !heldOnly} onClick={() => { setHeldOnly(false); setCapMin(v); }}>{ko}</ChipBtn>
        ))}
        <ChipBtn on={heldOnly} onClick={() => { if (heldCount === 0) { setHeldNote(true); } else { setHeldNote(false); setHeldOnly(!heldOnly); } }}>내 포트폴리오만</ChipBtn>
        <select value={secFilter} onChange={(e) => setSecFilter(e.target.value)}
          style={{ border: "1.5px solid " + C.line, borderRadius: 999, padding: "5px 10px", fontSize: 11.5, fontWeight: 700, color: C.sub, fontFamily: FONT, background: "#fff" }}>
          <option value="all">전체 업종</option>
          {secKeys.map((k) => <option key={k} value={k}>{SEC(k).ko}</option>)}
        </select>
      </div>
      {heldNote && <Sub style={{ color: C.coral }}>저장된 포트폴리오가 없어요. 포트폴리오 탭에서 하나 저장하면 이 필터를 쓸 수 있어요.</Sub>}

      <Card>
        <H onWhy={() => setExplain("quad")}>업종 성장 사분면 — 어느 판에서 누가 크고 있나</H>
        <Sub style={{ marginTop: 3 }}>
          가로: 업종 매출 성장률(3년 연평균, 상장사 합산) · 세로: 기업 매출 성장률 · 원 크기: 시가총액
          {heldN > 0 && <> · <span style={{ color: C.apricotDeep, fontWeight: 800 }}>주황 테두리 {heldN}개는 내 포트폴리오 보유 종목</span></>}
        </Sub>
        <div className="cgrid4" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 6, margin: "10px 0" }}>
          {[
            { t: "성장 산업 · 성장 기업", s: "산업과 기업이 함께 성장 — 가장 탄탄한 조합", bg: C.tealSoft, dot: C.teal },
            { t: "역성장 산업 · 성장 기업", s: "산업 역풍 속 단독 성장 — 점유율 확대인지 확인", bg: C.blueSoft, dot: C.blue },
            { t: "성장 산업 · 역성장 기업", s: "성장하는 산업에서 소외 — 경쟁력 점검 필요", bg: C.sandSoft, dot: C.sand },
            { t: "역성장 산업 · 역성장 기업", s: "산업·기업 동반 위축 — 구조적 어려움 신호", bg: C.coralSoft, dot: C.coral },
          ].map((q) => (
            <div key={q.t} style={{ background: q.bg, borderRadius: 7, padding: "8px 10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 7, height: 7, borderRadius: 999, background: q.dot, flexShrink: 0 }} />
                <span style={{ fontSize: 10.5, fontWeight: 800, color: C.ink }}>{q.t}</span>
              </div>
              <div style={{ fontSize: 9.5, color: C.sub, marginTop: 3, lineHeight: 1.45 }}>{q.s}</div>
            </div>
          ))}
        </div>
        <Scatter pts={quadPts} xDomain={[-30, 50]} yDomain={[-30, 50]} quads zoomable
          xLabel="업종 매출 성장률 (%) — 오른쪽일수록 성장하는 산업" yLabel="기업 매출 성장률 (%) — 위일수록 성장하는 기업" onPick={onOpen} />
        <Sub style={{ marginTop: 8, fontSize: 11, color: C.faint }}>휠이나 + 버튼으로 확대, 드래그로 이동할 수 있어요 · 확대하면 회사 이름이 나타나요 · 원을 누르면 기업 페이지로 이동해요</Sub>
      </Card>

      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H onWhy={() => setExplain("secrank")}>업종 성장률 순위 — 어느 판이 커지고 있나</H>
          <Sub style={{ marginTop: 3 }}>3년 연평균 매출 성장률(상장사 합산 기준)이에요. 규모·수익성을 함께 보세요.</Sub>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12, maxHeight: 340, overflowY: "auto", paddingRight: 4 }}>
            {secRank.map((r) => (
              <div key={r.k} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 96, fontSize: 11, fontWeight: 800, color: C.ink, flexShrink: 0, textAlign: "right" }}>{r.ko}</span>
                <svg viewBox="0 0 200 15" style={{ flex: 1, height: 15, minWidth: 90 }}>
                  <line x1="100" y1="0" x2="100" y2="15" stroke={C.line} strokeWidth="1" />
                  <rect x={r.g >= 0 ? 100 : 100 - Math.abs(r.g) / secGMax * 96} y="2.5"
                    width={Math.max(Math.abs(r.g) / secGMax * 96, 1.5)} height="10" rx="3"
                    fill={r.g >= 0 ? C.teal : C.coral} opacity="0.85" />
                </svg>
                <span style={{ width: 48, fontSize: 11.5, fontWeight: 800, textAlign: "right", flexShrink: 0, color: r.g >= 0 ? C.teal : C.coral }}>{r.g >= 0 ? "+" : ""}{r.g}%</span>
                <span style={{ width: 104, fontSize: 9.5, color: C.faint, flexShrink: 0 }}>매출 {r.rev0 >= 100 ? Math.round(r.rev0) : r.rev0}조{r.opm != null ? ` · 이익률 ${r.opm}%` : r.roe != null ? ` · ROE ${r.roe}%` : ""}</span>
              </div>
            ))}
          </div>
          {secExcluded.length > 0 && <Sub style={{ marginTop: 8, fontSize: 10.5, color: C.faint }}>표본 부족으로 표시하지 않음: {secExcluded.join(", ")}</Sub>}
        </Card>
        <Card>
          <H onWhy={() => setExplain("scatter")}>PBR × ROE — 수익성과 평가의 관계</H>
          <Sub style={{ marginTop: 3 }}>자본을 잘 굴리는 회사가 비싸게 거래되는 게 보통이에요. 그 관계에서 벗어난 위치가 질문의 출발점이에요.</Sub>
          <div style={{ marginTop: 8 }}>
            {!hasMult ? <Sub style={{ padding: "30px 0", textAlign: "center" }}>PER·PBR 데이터가 아직 없어요.<br />v12.5 코드 업로드 후 Actions에서 데이터 갱신을 한 번 실행하면 채워져요.</Sub>
              : <Scatter pts={pbrRoePts} xDomain={[-10, 40]} yDomain={[0, 8]} height={340} zoomable
                  xLabel="ROE (%)" yLabel="PBR (배)" onPick={onOpen} />}
          </div>
        </Card>
      </div>

      <Card>
        <H onWhy={() => setExplain("box")}>업종별 멀티플 분포 — 같은 숫자도 판에 따라 다르게 읽혀요</H>
        <div style={{ display: "flex", gap: 6, margin: "8px 0" }}>
          <ChipBtn on={boxKey === "per"} onClick={() => setBoxKey("per")}>PER</ChipBtn>
          <ChipBtn on={boxKey === "pbr"} onClick={() => setBoxKey("pbr")}>PBR</ChipBtn>
        </div>
        {boxRows.length === 0 && <Sub style={{ padding: "22px 0", textAlign: "center" }}>PER·PBR 데이터가 아직 없어요. 데이터 갱신을 한 번 실행하면 채워져요.</Sub>}
        <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 6 }}>
          {boxRows.map((r) => (
            <div key={r.k} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 110, fontSize: 11.5, fontWeight: 700, color: C.ink, flexShrink: 0, textAlign: "right" }}>{r.ko} <span style={{ color: C.faint, fontWeight: 400 }}>({r.n})</span></span>
              <div style={{ flex: 1 }}><QuartBand q={r.q} v={null} max={boxMax} /></div>
              <span style={{ width: 92, fontSize: 10.5, color: C.sub, flexShrink: 0 }}>{r.q[0]}–{r.q[2]} <b style={{ color: C.blue }}>중간 {r.q[1]}</b></span>
            </div>
          ))}
        </div>
        <Sub style={{ marginTop: 8, fontSize: 10.5, color: C.faint }}>{boxKey === "per" ? "PER은 0~200배 구간만 집계 (적자 기업 제외)" : "PBR은 0~20배 구간만 집계"} · 상자: 25~75% · 선: 중간값</Sub>
      </Card>
    </div>
  );
}

// ---------------- 기업 찾기 ----------------
export function SearchView({ data, heldMap, onOpen }) {
  const [q, setQ] = useState("");
  const [sec, setSec] = useState("all");
  const [sort, setSort] = useState("cap");
  const [heldOnly, setHeldOnly] = useState(false);
  const [limit, setLimit] = useState(30);
  const comps = data.companies;
  const secKeys = useMemo(() => [...new Set(comps.map((c) => c.s))].sort((a, b) => (data.sectors[b]?.mc || 0) - (data.sectors[a]?.mc || 0)), [comps, data.sectors]);
  const rows = useMemo(() => {
    let r = comps;
    if (q.trim()) { const s = q.trim().toLowerCase(); r = r.filter((c) => c.nk.toLowerCase().includes(s) || c.t.includes(s)); }
    if (sec !== "all") r = r.filter((c) => c.s === sec);
    if (heldOnly) r = r.filter((c) => heldMap[c.t]);
    const key = { cap: (c) => -(c.cap || 0), g3: (c) => -(c.g3 ?? -999), per: (c) => (c.per && c.per > 0 ? c.per : 9e9), roe: (c) => -(c.roe ?? -999) }[sort];
    return [...r].sort((a, b) => key(a) - key(b));
  }, [comps, q, sec, sort, heldOnly, heldMap]);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <Card style={{ padding: 14 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="회사 이름이나 종목코드로 찾기"
          style={{ width: "100%", boxSizing: "border-box", border: "1.5px solid " + C.line, borderRadius: RAD.input, padding: "11px 12px", fontSize: 14, fontFamily: FONT, color: C.ink, outline: "none" }} />
        <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
          <select value={sec} onChange={(e) => setSec(e.target.value)} style={{ border: "1.5px solid " + C.line, borderRadius: 999, padding: "5px 10px", fontSize: 11.5, fontWeight: 700, color: C.sub, fontFamily: FONT, background: "#fff" }}>
            <option value="all">전체 업종</option>
            {secKeys.map((k) => <option key={k} value={k}>{SEC(k).ko}</option>)}
          </select>
          {[["cap", "시가총액순"], ["g3", "성장률순"], ["per", "PER 낮은순"], ["roe", "ROE 높은순"]].map(([v, ko]) => (
            <ChipBtn key={v} on={sort === v} onClick={() => setSort(v)}>{ko}</ChipBtn>
          ))}
          <ChipBtn on={heldOnly} onClick={() => setHeldOnly(!heldOnly)}>보유만</ChipBtn>
        </div>
      </Card>
      <Card style={{ padding: "6px 14px" }}>
        {rows.slice(0, limit).map((c) => (
          <button key={c.t} onClick={() => onOpen(c.t)}
            style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", background: "none", border: "none", borderBottom: "1px solid " + C.line, padding: "11px 2px", cursor: "pointer", fontFamily: FONT, textAlign: "left" }}>
            <span style={{ width: 9, height: 9, borderRadius: 999, background: SEC(c.s).color, flexShrink: 0 }} />
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: 13.5, fontWeight: 800, color: C.ink }}>{c.nk}</span>
              {heldMap[c.t] && <span style={{ marginLeft: 6, fontSize: 9.5, fontWeight: 800, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 999, padding: "2px 7px" }}>보유</span>}
              <span style={{ display: "block", fontSize: 10.5, color: C.faint }}>{SEC(c.s).ko} · {c.cap ? c.cap.toFixed(1) + "조" : "—"}</span>
            </span>
            <span style={{ textAlign: "right", flexShrink: 0 }}>
              <span style={{ display: "block", fontSize: 12.5, fontWeight: 800, color: C.ink }}>{fmtWon(c.price)}</span>
              <span style={{ display: "block", fontSize: 10, color: C.sub }}>PER {c.per ?? "—"} · 성장 {pc(c.g3)}</span>
            </span>
          </button>
        ))}
        {rows.length > limit && (
          <button onClick={() => setLimit(limit + 30)} style={{ display: "block", width: "100%", background: "none", border: "none", color: C.blue, fontSize: 12.5, fontWeight: 800, padding: "12px", cursor: "pointer", fontFamily: FONT }}>더 보기 ({rows.length - limit}개 남음)</button>
        )}
        {rows.length === 0 && <Sub style={{ padding: "14px 2px" }}>검색 결과가 없어요.</Sub>}
      </Card>
    </div>
  );
}

// ---------------- 기업 상세 ----------------
function MultRow({ label, valTxt, band, sentence, onWhy }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: "1px solid " + C.line, flexWrap: "wrap" }}>
      <button onClick={onWhy} style={{ width: 118, textAlign: "left", background: "none", border: "none", padding: 0, cursor: onWhy ? "pointer" : "default", fontFamily: FONT, flexShrink: 0 }}>
        <span style={{ fontSize: 12.5, fontWeight: 800, color: C.ink }}>{label}</span>
        {onWhy && <span style={{ marginLeft: 4, fontSize: 9, color: C.faint }}>?</span>}
        <span style={{ display: "block", fontSize: 14, fontWeight: 800, color: C.blue, marginTop: 1 }}>{valTxt}</span>
      </button>
      {band}
      <span style={{ flex: 1, minWidth: 160, fontSize: 11.5, color: C.sub, lineHeight: 1.55 }}>{sentence}</span>
    </div>
  );
}

export function CompanyView({ data, t, heldInfo, onBack, onOpen, setExplain }) {
  const c = data.companies.find((x) => x.t === t);
  const sec = c ? data.sectors[c.s] : null;
  if (!c) return <Card><Sub>이 종목의 데이터를 찾지 못했어요.</Sub></Card>;

  const sharesM = c.shm || (c.cap && c.price ? c.cap * 1e12 / c.price / 1e6 : null);
  const volTxt = c.beta == null ? null : c.beta > 1.15 ? "시장보다 출렁임이 큰 편" : c.beta < 0.85 ? "시장보다 출렁임이 작은 편" : "시장과 비슷하게 움직이는 편";
  const payout = c.dps && c.eps && c.eps > 0 ? c.dps / c.eps * 100 : null;

  // 멀티플 문장
  const perSent = c.per == null ? "적자이거나 데이터가 없어 PER을 계산할 수 없어요."
    : sec?.perQ ? `이익 1원에 ${c.per}원 — 업종 중간값 ${sec.perQ[1]}배보다 ${c.per > sec.perQ[1] ? "높아요. 시장의 기대가 큰 만큼, 그 기대의 근거를 물어볼 자리예요." : "낮아요. 싸다는 뜻일 수도, 시장이 성장을 의심한다는 뜻일 수도 있어요."}`
    : `이익 1원에 시장이 ${c.per}원을 내고 있어요.`;
  const pbrSent = c.pbr == null ? "데이터가 없어요."
    : sec?.pbrQ ? `순자산 1원을 ${c.pbr}원으로 평가 — 업종 중간값은 ${sec.pbrQ[1]}배예요. ROE와 함께 읽어야 정확해요.`
    : `순자산 1원을 시장이 ${c.pbr}원으로 평가해요.`;
  const roeSent = c.roe == null ? "데이터가 없어요."
    : sec?.roe != null ? `주주 돈 100원으로 연 ${c.roe}원 — 업종 중간값(${sec.roe}%)보다 ${c.roe > sec.roe ? "높은" : "낮은"} 수준이에요.${c.debt != null && c.debt > 200 ? " 다만 부채비율이 " + c.debt + "%로 높은 편이라, 레버리지 효과를 감안해야 해요." : ""}`
    : `주주 돈 100원으로 연 ${c.roe}원을 벌었어요.`;

  // 매출↑ 이익 정체 플래그
  const revUp = c.rev[0] && c.rev[2] && c.rev[0] > c.rev[2] * 1.1;
  const niFlat = c.ni[0] != null && c.ni[2] != null && c.ni[0] <= c.ni[2] * 1.02;

  // 밸류에이션 풋볼필드 — 여러 잣대에서 업종 내 위치 (p5~p95 스케일, 25~75% 상자)
  const peers = data.companies.filter((x) => x.s === c.s);
  const psrOf = (x) => x.cap && x.rev && x.rev[0] > 0 ? x.cap * 1e4 / x.rev[0] : null;
  const mkPos = (ko, vals, v, fmt, dir) => {
    const arr = vals.filter((x) => x != null && isFinite(x)).sort((a, b) => a - b);
    if (v == null || !isFinite(v) || arr.length < 5) return null;
    const q = (pp) => { const i = pp * (arr.length - 1), lo = Math.floor(i), hi = Math.ceil(i); return arr[lo] + (arr[hi] - arr[lo]) * (i - lo); };
    const lo = q(0.05), hi = q(0.95);
    const span = hi - lo || 1;
    const below = arr.filter((x) => x < v).length;
    const rank = dir === "high" ? arr.length - below : below + 1;
    return { ko, v, fmt, pos: clamp((v - lo) / span, 0, 1), band: [clamp((q(0.25) - lo) / span, 0, 1), clamp((q(0.75) - lo) / span, 0, 1)],
      mid: clamp((q(0.5) - lo) / span, 0, 1), n: arr.length,
      sent: dir === "high" ? `업종 ${arr.length}개사 중 높은 쪽에서 ${rank}번째` : `업종 ${arr.length}개사 중 낮은 쪽에서 ${rank}번째` };
  };
  const ffRows = [
    c.lo && c.hi && c.price ? { ko: "52주 주가 위치", v: c.price, fmt: (x) => fmtShort(x) + "원", pos: clamp((c.price - c.lo) / ((c.hi - c.lo) || 1), 0, 1), band: null, mid: null,
      sent: `52주 범위(${fmtShort(c.lo)}~${fmtShort(c.hi)}원)의 ${Math.round(clamp((c.price - c.lo) / ((c.hi - c.lo) || 1), 0, 1) * 100)}% 지점` } : null,
    mkPos("PER", peers.map((x) => (x.per > 0 && x.per < 200 ? x.per : null)), c.per > 0 && c.per < 200 ? c.per : null, (x) => x.toFixed(1) + "배"),
    mkPos("PBR", peers.map((x) => (x.pbr > 0 && x.pbr < 20 ? x.pbr : null)), c.pbr > 0 && c.pbr < 20 ? c.pbr : null, (x) => x.toFixed(2) + "배"),
    mkPos("PSR (매출 대비)", peers.map((x) => { const ps = psrOf(x); return ps > 0 && ps < 50 ? ps : null; }), (() => { const ps = psrOf(c); return ps > 0 && ps < 50 ? ps : null; })(), (x) => x.toFixed(1) + "배"),
    c.dy > 0 ? mkPos("배당수익률", peers.map((x) => (x.dy > 0 ? x.dy : null)), c.dy, (x) => x.toFixed(1) + "%", "high") : null,
  ].filter(Boolean);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <button onClick={onBack} style={{ alignSelf: "flex-start", display: "inline-flex", alignItems: "center", gap: 5, border: HAIR, background: "#fff", borderRadius: 999, padding: "6px 12px", fontSize: 11.5, fontWeight: 700, color: C.sub, cursor: "pointer", fontFamily: FONT }}>
        <Ic name="back" size={12} color={C.sub} />기업 찾기
      </button>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, flexWrap: "wrap" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 20, fontWeight: 800, color: C.ink }}>{c.nk}</span>
              <span style={{ fontSize: 10.5, fontWeight: 800, color: "#fff", background: SEC(c.s).color, borderRadius: 999, padding: "3px 9px" }}>{SEC(c.s).ko}</span>
              <span style={{ fontSize: 10.5, color: C.faint }}>{c.t}</span>
            </div>
            {volTxt && <Sub style={{ marginTop: 5 }}>{volTxt} (β {c.beta} · 연 변동성 {pc(c.vol, 0)})</Sub>}
            {heldInfo && heldInfo.length > 0 && (
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 7 }}>
                {heldInfo.map((h, i) => (
                  <span key={i} style={{ fontSize: 10.5, fontWeight: 800, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 999, padding: "3px 9px" }}>
                    {h.slot}에 {h.pct != null ? h.pct.toFixed(0) + "%" : ""} 보유
                  </span>
                ))}
              </div>
            )}
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 21, fontWeight: 800, color: C.ink }}>{fmtWon(c.price)}</div>
            <div style={{ fontSize: 11, color: C.sub }}>시가총액 {c.cap ? c.cap.toFixed(1) + "조원" : "—"}</div>
          </div>
        </div>
      </Card>

      <Card>
        <H onWhy={() => setExplain("box")}>멀티플 — 업종 분포 속의 위치</H>
        <Sub style={{ marginTop: 3 }}>주황 점이 이 회사, 파란 상자가 업종의 25~75% 구간이에요.</Sub>
        <div style={{ marginTop: 4 }}>
          <MultRow label="PER" valTxt={c.per != null ? c.per + "배" : "—"} onWhy={() => setExplain("per")}
            band={<QuartBand q={sec?.perQ} v={c.per} max={60} />} sentence={perSent} />
          <MultRow label="PBR" valTxt={c.pbr != null ? c.pbr + "배" : "—"} onWhy={() => setExplain("pbr")}
            band={<QuartBand q={sec?.pbrQ} v={c.pbr} max={8} />} sentence={pbrSent} />
          <MultRow label="ROE" valTxt={pc(c.roe)} onWhy={() => setExplain("roe")}
            band={<div style={{ width: 190, fontSize: 10.5, color: C.faint }}>업종 중간값 {pc(sec?.roe)}</div>} sentence={roeSent} />
          <MultRow label="배당수익률" valTxt={pc(c.dy)} onWhy={() => setExplain("payout")}
            band={<div style={{ width: 190, fontSize: 10.5, color: C.faint }}>배당성향 {payout != null ? payout.toFixed(0) + "%" : "—"}</div>}
            sentence={payout == null ? "배당이 없거나 이익 데이터가 없어요." : payout > 100 ? "이익보다 많은 배당을 주고 있어요 — 이 수준은 계속되기 어려워요." : payout > 60 ? "이익의 상당 부분을 배당으로 돌려주는 편이에요." : "이익 대비 무리 없는 배당 수준이에요."} />
        </div>
      </Card>

      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H>3개년 흐름 — 매출이 이익으로 이어지고 있나</H>
          {c.rev[0] == null && c.ni[0] == null ? <Sub style={{ marginTop: 8 }}>재무제표 데이터가 아직 없어요. (파이프라인이 사업보고서를 못 찾은 종목이에요)</Sub> : (
            <>
              <div style={{ display: "flex", justifyContent: "space-around", marginTop: 12, gap: 6 }}>
                <Spark3 label="매출" arr={c.rev} />
                <Spark3 label="영업이익" arr={c.op} />
                <Spark3 label="순이익" arr={c.ni} />
              </div>
              {revUp && niFlat && (
                <div style={{ marginTop: 12, fontSize: 11.5, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 6, padding: "9px 11px", lineHeight: 1.6 }}>
                  매출은 성장했지만 이익이 따라오지 못했어요. 원가·비용 구조나 일회성 요인을 확인해볼 대목이에요.
                </div>
              )}
            </>
          )}
        </Card>
        <Card>
          <H onWhy={() => setExplain("ff")}>밸류에이션 풋볼필드 — 여러 잣대로 본 높낮이</H>
          {ffRows.length === 0 ? <Sub style={{ marginTop: 8 }}>표시할 잣대가 없어요. 데이터 갱신 후 채워져요.</Sub> : (
            <div style={{ marginTop: 6 }}>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 0, fontSize: 9, color: C.faint, paddingRight: 2 }}>
                <span style={{ width: "52%", display: "flex", justifyContent: "space-between" }}><span>낮음</span><span>높음</span></span>
              </div>
              {ffRows.map((r) => (
                <div key={r.ko} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0", borderBottom: "1px solid " + C.line }}>
                  <span style={{ width: 108, flexShrink: 0 }}>
                    <span style={{ display: "block", fontSize: 11.5, fontWeight: 800, color: C.ink }}>{r.ko}</span>
                    <span style={{ display: "block", fontSize: 12.5, fontWeight: 800, color: C.blue }}>{r.fmt(r.v)}</span>
                  </span>
                  <svg viewBox="0 0 200 16" style={{ flex: 1, height: 16, minWidth: 90 }}>
                    <line x1="3" y1="8" x2="197" y2="8" stroke={C.line} strokeWidth="2" />
                    {r.band && <rect x={3 + r.band[0] * 194} y="4" width={Math.max(2, (r.band[1] - r.band[0]) * 194)} height="8" rx="3" fill={C.blueSoft} />}
                    {r.mid != null && <line x1={3 + r.mid * 194} y1="3" x2={3 + r.mid * 194} y2="13" stroke={C.blue} strokeWidth="1.5" />}
                    <circle cx={3 + r.pos * 194} cy="8" r="5" fill={C.apricotDeep} stroke="#fff" strokeWidth="1.5" />
                  </svg>
                </div>
              ))}
              <Sub style={{ fontSize: 10.5, color: C.faint, marginTop: 8 }}>
                {ffRows.filter((r) => r.sent).map((r) => `${r.ko}: ${r.sent}`).join(" · ")}
              </Sub>
              <Sub style={{ fontSize: 10.5, color: C.faint, marginTop: 4 }}>파란 상자: 업종 25~75% 구간 · 파란 선: 중간값 · 주황 점: 이 회사. 낮다고 곧 싸다는 뜻은 아니에요.</Sub>
            </div>
          )}
        </Card>
      </div>

      <DcfCard c={c} sharesM={sharesM} setExplain={setExplain} />

      <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", lineHeight: 1.7, padding: "6px 0 20px" }}>
        교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다.<br />{CREDIT}
      </div>
    </div>
  );
}

// ---------------- DCF 분석 ----------------
function Slider({ label, val, setVal, min, max, step, unit }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>{label}</span>
        <span style={{ fontSize: 14, fontWeight: 800, color: C.blue }}>{val}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={val} onChange={(e) => setVal(+e.target.value)} style={{ width: "100%", accentColor: C.blue }} />
    </div>
  );
}

export function DcfCard({ c, sharesM, setExplain }) {
  const auto = c.dcfReady && c.ni[0] != null && sharesM;
  const [ni0, setNi0] = useState(auto ? c.ni[0] : "");
  const [shm, setShm] = useState(sharesM ? Math.round(sharesM * 10) / 10 : "");
  const [g1, setG1] = useState(clamp(Math.round(c.g3 ?? 10), -10, 25));
  const [fade, setFade] = useState(true);
  const [disc, setDisc] = useState(10);
  const [term, setTerm] = useState(2);
  const [saved, setSaved] = useState(false);
  useEffect(() => { (async () => {
    try { const raw = await store.get(KEY_DCF); const m = raw ? JSON.parse(raw) : {}; const s = m[c.t];
      if (s) { setNi0(s.ni0); setShm(s.shm); setG1(s.g1); setFade(s.fade); setDisc(s.disc); setTerm(s.term); } } catch (e) {}
  })(); }, [c.t]);

  const N = +ni0 || null, S = +shm || null;
  const val = dcfPerShare({ ni0: N, sharesM: S, g1, fade, disc, term });
  const gap = val && c.price ? (val / c.price - 1) * 100 : null;
  const rev = useMemo(() => reverseDcf({ price: c.price, ni0: N, sharesM: S, fade, disc, term }), [c.price, N, S, fade, disc, term]);

  // 민감도: 할인율 × 영구성장률
  const discs = [disc - 2, disc - 1, disc, disc + 1, disc + 2].filter((d) => d >= 5);
  const terms = [term - 1, term - 0.5, term, term + 0.5, term + 1].filter((t) => t >= 0);
  const grid = discs.map((d) => terms.map((tg) => (tg < d - 1 ? dcfPerShare({ ni0: N, sharesM: S, g1, fade, disc: d, term: tg }) : null)));
  const flat = grid.flat().filter((v) => v != null);
  const sensLo = flat.length ? Math.min(...flat) : null, sensHi = flat.length ? Math.max(...flat) : null;

  const save = async () => {
    try {
      const raw = await store.get(KEY_DCF); const m = raw ? JSON.parse(raw) : {};
      m[c.t] = { ni0: N, shm: S, g1, fade, disc, term, lo: sensLo, hi: sensHi, val };
      await store.set(KEY_DCF, JSON.stringify(m));
      setSaved(true); setTimeout(() => setSaved(false), 1600);
    } catch (e) {}
  };

  return (
    <Card>
      <H onWhy={() => setExplain("dcf")}>DCF 분석 — 가정에 따라 가치가 어떻게 달라지나</H>
      <Sub style={{ marginTop: 3 }}>
        순이익을 현금흐름으로 근사한 <b style={{ color: C.ink }}>단순화 모형</b>입니다. 특정 가격을 제시하기 위한 것이 아니라, 가정이 바뀔 때 가치 추정이 얼마나 달라지는지 확인하는 도구예요.
        {!auto && " 이 종목은 자동 채움 데이터가 없어 직접 입력이 필요해요."}
      </Sub>

      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <label style={{ flex: 1 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: C.sub }}>시작 순이익 (억원)</span>
              <input type="number" value={ni0} onChange={(e) => setNi0(e.target.value)} placeholder="예: 3000"
                style={{ width: "100%", boxSizing: "border-box", border: "1.5px solid " + C.line, borderRadius: RAD.input, padding: "8px 9px", fontSize: 13, fontWeight: 800, color: C.ink, fontFamily: FONT, marginTop: 3 }} />
            </label>
            <label style={{ flex: 1 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: C.sub }}>주식 수 (백만주)</span>
              <input type="number" value={shm} onChange={(e) => setShm(e.target.value)} placeholder="예: 130"
                style={{ width: "100%", boxSizing: "border-box", border: "1.5px solid " + C.line, borderRadius: RAD.input, padding: "8px 9px", fontSize: 13, fontWeight: 800, color: C.ink, fontFamily: FONT, marginTop: 3 }} />
            </label>
          </div>
          <Slider label="향후 5년 이익 성장률 (연)" val={g1} setVal={setG1} min={-20} max={40} step={1} unit="%" />
          <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: C.ink, fontWeight: 700, cursor: "pointer" }}>
            <input type="checkbox" checked={fade} onChange={(e) => setFade(e.target.checked)} style={{ width: 15, height: 15, accentColor: C.blue }} />
            성장률이 5년에 걸쳐 영구성장률로 수렴
          </label>
          <Slider label="할인율 (요구수익률)" val={disc} setVal={setDisc} min={6} max={16} step={0.5} unit="%" />
          <Slider label="영구성장률" val={term} setVal={setTerm} min={0} max={4} step={0.5} unit="%" />
          {disc <= term + 1 && <Sub style={{ color: C.coral, fontSize: 11 }}>할인율이 영구성장률에 너무 가까우면 값이 무한대로 발산해요. 할인율을 높이거나 영구성장률을 낮춰주세요.</Sub>}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ background: C.bg, borderRadius: RAD.card, padding: 16, border: HAIR }}>
            <div style={{ fontSize: 11, color: C.sub }}>이 가정에서의 모형값 (주당)</div>
            <div style={{ fontSize: 25, fontWeight: 800, color: C.ink, marginTop: 2 }}>{val ? fmtWon(val) : "—"}</div>
            {gap != null && (
              <div style={{ fontSize: 12, fontWeight: 800, marginTop: 3, color: gap >= 0 ? C.teal : C.coral }}>
                현재 주가 대비 {gap >= 0 ? "+" : ""}{gap.toFixed(0)}%
                <span style={{ color: C.faint, fontWeight: 400 }}> — 가정이 바뀌면 이 숫자도 바뀌어요</span>
              </div>
            )}
          </div>
          {rev && (
            <div style={{ background: C.apricotSoft, borderRadius: RAD.card, padding: 14, border: "1px solid " + C.apricot + "55" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 800, color: C.apricotDeep }}>리버스 DCF</span>
                <button onClick={() => setExplain("rev")} style={{ fontSize: 9, color: C.apricotDeep, background: "#fff", border: "none", borderRadius: 999, width: 15, height: 15, cursor: "pointer", fontWeight: 800, fontFamily: FONT }}>?</button>
              </div>
              <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.65, marginTop: 5 }}>
                {rev.edge === "low" ? "지금 주가는 연 −30% 이하의 역성장을 가정해도 설명되지 않을 만큼 낮아요. 모형 밖의 이유(부채, 소송, 지배구조 등)를 봐야 해요."
                  : rev.edge === "high" ? "지금 주가를 정당화하려면 5년간 연 60%가 넘는 성장이 필요해요. 그만한 근거가 있는지가 질문이에요."
                  : <>지금 주가에는 <b>향후 5년 연 {rev.g.toFixed(1)}% 성장</b>(이후 {term}%)이 담겨 있어요. 이 회사의 최근 3년 성장률은 {pc(c.g3)}였어요 — 그 간극이 그럴듯한지가 핵심 질문이에요.</>}
              </div>
            </div>
          )}
          {N != null && N <= 0 && <Sub style={{ color: C.coral, fontSize: 11 }}>순이익이 0 이하라 이 단순 모형으로는 계산할 수 없어요. 흑자 전환 가정을 직접 입력해보거나, 이 회사엔 다른 잣대가 필요해요.</Sub>}
        </div>
      </div>

      {flat.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: C.ink, marginBottom: 6 }}>민감도 — 할인율 × 영구성장률에 따라 (주당, 원)</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", fontSize: 11, fontFamily: FONT, minWidth: 380 }}>
              <thead><tr>
                <th style={{ padding: "5px 8px", color: C.faint, fontWeight: 700, textAlign: "left" }}>할인율↓ 영구성장→</th>
                {terms.map((tg) => <th key={tg} style={{ padding: "5px 8px", color: C.sub, fontWeight: 800 }}>{tg}%</th>)}
              </tr></thead>
              <tbody>
                {discs.map((d, i) => (
                  <tr key={d}>
                    <td style={{ padding: "5px 8px", color: C.sub, fontWeight: 800 }}>{d}%</td>
                    {terms.map((tg, j) => {
                      const v = grid[i][j];
                      const ratio = v && c.price ? v / c.price : null;
                      const bgc = v == null ? "#fff" : ratio > 1.15 ? C.blueSoft : ratio < 0.85 ? C.sandSoft : "#fff";
                      const on = d === disc && tg === term;
                      return <td key={tg} style={{ padding: "5px 8px", textAlign: "right", background: bgc, border: on ? "1.5px solid " + C.blue : "1px solid " + C.line, fontWeight: on ? 800 : 500, color: C.ink }}>{v ? fmtShort(v) : "—"}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Sub style={{ fontSize: 10.5, color: C.faint, marginTop: 5 }}>파란 배경: 모형값이 현재가보다 15% 이상 높음 · 모래색: 15% 이상 낮음. 색은 판단이 아니라 위치 표시예요.</Sub>
          <button onClick={save} style={{ marginTop: 10, background: saved ? C.teal : C.blue, color: "#fff", border: "none", borderRadius: RAD.btn, padding: "10px 16px", fontSize: 12.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>
            {saved ? "저장됐어요" : "이 가정 저장하기 (다음에 이 종목을 열 때 불러와요)"}
          </button>
        </div>
      )}
    </Card>
  );
}

// ---------------- 루트 ----------------
const CORP_CSS = `
  @media (max-width: 880px) { .cgrid2 { grid-template-columns: 1fr !important } .cgrid4 { grid-template-columns: 1fr 1fr !important } }
`;

export default function CorpApp() {
  const [state, setState] = useState({ st: "loading" });
  const [view, setView] = useState({ kind: "market" });
  const [heldMap, setHeldMap] = useState({});
  const [explain, setExplain] = useState(null);
  const [tries, setTries] = useState(0);

  useEffect(() => { (async () => {
    setState({ st: "loading" });
    try {
      const r = await fetch("./corp.json", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      if (!d || !Array.isArray(d.companies) || !d.companies.length) throw new Error("empty");
      setState({ st: "ready", data: d });
    } catch (e) { setState({ st: "missing" }); }
  })(); }, [tries]);

  // 포트폴리오 보유 종목 맵 (읽기 전용)
  useEffect(() => { (async () => {
    try {
      const raw = await store.get(KEY_SLOTS); const slots = raw ? JSON.parse(raw) : [];
      const map = {};
      for (const meta of (Array.isArray(slots) ? slots : []).slice(0, 20)) {
        try {
          const praw = await store.get(KEY_SLOT(meta.id)); if (!praw) continue;
          const p = JSON.parse(praw); const hs = Array.isArray(p.holdings) ? p.holdings : [];
          const tot = hs.reduce((s, h) => s + (h.mw || 0), 0);
          hs.forEach((h) => {
            if (!h.t) return;
            (map[h.t] = map[h.t] || []).push({ slot: meta.name || "포트폴리오", pct: tot > 0 ? (h.mw || 0) / tot * 100 : null });
          });
        } catch (e) {}
      }
      setHeldMap(map);
    } catch (e) {}
  })(); }, []);

  if (state.st === "loading") return (
    <div style={{ minHeight: "50vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT }}>
      <div style={{ textAlign: "center" }}><Bird mood="cheer" size={56} /><div style={{ fontSize: 12.5, color: C.sub, marginTop: 8 }}>기업 데이터를 불러오는 중…</div></div>
    </div>
  );
  if (state.st === "missing") return <MissingData onRetry={() => setTries(tries + 1)} />;

  const d = state.data;
  return (
    <div style={{ maxWidth: 1140, margin: "0 auto", padding: "14px 16px 40px", fontFamily: FONT, color: C.ink }}>
      <style>{CORP_CSS}</style>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, gap: 8, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 6 }}>
          <ChipBtn on={view.kind === "market"} onClick={() => setView({ kind: "market" })}>시장 지도</ChipBtn>
          <ChipBtn on={view.kind !== "market"} onClick={() => setView({ kind: "search" })}>기업 찾기</ChipBtn>
        </div>
        <span style={{ fontSize: 10.5, color: C.faint }}>재무 데이터 기준일 {d.asOf} · 사업보고서는 직전 연도 기준</span>
      </div>
      {view.kind === "market" && <MarketView data={d} heldMap={heldMap} onOpen={(t) => setView({ kind: "co", t })} setExplain={setExplain} />}
      {view.kind === "search" && <SearchView data={d} heldMap={heldMap} onOpen={(t) => setView({ kind: "co", t })} />}
      {view.kind === "co" && <CompanyView data={d} t={view.t} heldInfo={heldMap[view.t]} onBack={() => setView({ kind: "search" })} onOpen={(t) => setView({ kind: "co", t })} setExplain={setExplain} />}
      {view.kind === "market" && (
        <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", marginTop: 20, lineHeight: 1.7 }}>
          교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다.<br />{CREDIT}
        </div>
      )}
      <ExplainSheet id={explain} onClose={() => setExplain(null)} />
    </div>
  );
}
