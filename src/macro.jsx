// ================= 뱁새 v14 — 금리·원자재 =================
// 국고채 수익률 곡선, 장단기 금리차, 금·은·유가, 듀레이션 체험, 브라질 국채 사례.
// 원칙: 예측이 아니라 이해. 금리와 자산의 관계를 스스로 만져보게 합니다.
import React, { useState, useEffect, useMemo } from "react";
import { C, FONT, RAD, HAIR } from "./tokens.js";
import { Bird } from "./detail.jsx";

const CREDIT = "이성진, INSEAD MBA 26J · Jack (Sung Jin) Lee, INSEAD MBA 26J";
const clamp = (v, a, b) => Math.min(Math.max(v, a), b);

const Card = ({ children, style = {} }) => (
  <div style={{ background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 18, ...style }}>{children}</div>
);
const H = ({ num, main, sub }) => (
  <div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      {num && <span style={{ fontSize: 11, fontWeight: 800, color: C.apricotDeep, letterSpacing: "0.1em" }}>{num}</span>}
      <span style={{ fontSize: 15.5, fontWeight: 800, color: C.ink, letterSpacing: "-0.01em" }}>{main}</span>
    </div>
    {sub && <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3 }}>{sub}</div>}
  </div>
);
const Sub = ({ children, style = {} }) => <div style={{ fontSize: 12, color: C.sub, lineHeight: 1.6, ...style }}>{children}</div>;

// ---------------- 선 차트 (월별 시계열) ----------------
function LineChart({ series, height = 220, unit = "", zero }) {
  // series: [{m:[...], v:[...], ko, color}]
  const W = 640, Hh = height, m = { l: 44, r: 10, t: 12, b: 26 };
  const all = series.flatMap((s) => s.v);
  if (!all.length) return null;
  let lo = Math.min(...all), hi = Math.max(...all);
  if (zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  const pad = (hi - lo) * 0.08 || 1;
  lo -= pad; hi += pad;
  const n = Math.max(...series.map((s) => s.v.length));
  const sx = (i, len) => m.l + (len <= 1 ? 0 : (i / (len - 1)) * (W - m.l - m.r));
  const sy = (v) => Hh - m.b - ((v - lo) / (hi - lo)) * (Hh - m.t - m.b);
  const labels = series[0].m;
  const step = Math.max(1, Math.floor(labels.length / 6));
  return (
    <svg viewBox={`0 0 ${W} ${Hh}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={m.l} y={m.t} width={W - m.l - m.r} height={Hh - m.t - m.b} fill={C.bg} rx="6" />
      {[lo + pad, (lo + hi) / 2, hi - pad].map((v, i) => (
        <g key={i}>
          <line x1={m.l} y1={sy(v)} x2={W - m.r} y2={sy(v)} stroke={C.line} strokeWidth="1" strokeDasharray="2 3" />
          <text x={m.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="9.5" fill={C.faint} fontFamily={FONT}>{v.toFixed(1)}{unit}</text>
        </g>
      ))}
      {zero && lo < 0 && hi > 0 && <line x1={m.l} y1={sy(0)} x2={W - m.r} y2={sy(0)} stroke={C.faint} strokeWidth="1.4" />}
      {labels.map((lb, i) => i % step === 0 ? <text key={i} x={sx(i, labels.length)} y={Hh - 8} textAnchor="middle" fontSize="9" fill={C.faint} fontFamily={FONT}>{lb}</text> : null)}
      {series.map((s) => (
        <g key={s.ko}>
          <path d={s.v.map((v, i) => `${i === 0 ? "M" : "L"}${sx(i, s.v.length)},${sy(v)}`).join(" ")}
            fill="none" stroke={s.color} strokeWidth="2.2" strokeLinejoin="round" />
          <circle cx={sx(s.v.length - 1, s.v.length)} cy={sy(s.v[s.v.length - 1])} r="3.5" fill={s.color} />
        </g>
      ))}
      <g>
        {series.map((s, i) => (
          <g key={s.ko} transform={`translate(${m.l + 8 + i * 130}, ${m.t + 12})`}>
            <line x1="0" y1="0" x2="16" y2="0" stroke={s.color} strokeWidth="2.5" />
            <text x="21" y="3.5" fontSize="10" fontWeight="700" fill={C.ink} fontFamily={FONT}>{s.ko}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

// ---------------- 수익률 곡선 ----------------
function CurveChart({ curve }) {
  const W = 640, Hh = 240, m = { l: 44, r: 14, t: 14, b: 30 };
  const all = [...curve.now, ...curve.ago];
  const lo = Math.min(...all) - 0.2, hi = Math.max(...all) + 0.2;
  const sx = (i) => m.l + (i / (curve.tenors.length - 1)) * (W - m.l - m.r);
  const sy = (v) => Hh - m.b - ((v - lo) / (hi - lo)) * (Hh - m.t - m.b);
  const path = (vals) => vals.map((v, i) => `${i === 0 ? "M" : "L"}${sx(i)},${sy(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${Hh}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={m.l} y={m.t} width={W - m.l - m.r} height={Hh - m.t - m.b} fill={C.bg} rx="6" />
      {curve.tenors.map((t, i) => (
        <text key={t} x={sx(i)} y={Hh - 10} textAnchor="middle" fontSize="10" fill={C.sub} fontFamily={FONT} fontWeight="700">{t}년</text>
      ))}
      {[lo + 0.2, (lo + hi) / 2, hi - 0.2].map((v, i) => (
        <text key={i} x={m.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="9.5" fill={C.faint} fontFamily={FONT}>{v.toFixed(1)}%</text>
      ))}
      <path d={path(curve.ago)} fill="none" stroke="#B9C2D4" strokeWidth="2.2" strokeDasharray="5 4" />
      <path d={path(curve.now)} fill="none" stroke={C.ink} strokeWidth="2.6" />
      {curve.now.map((v, i) => (
        <g key={i}>
          <circle cx={sx(i)} cy={sy(v)} r="4" fill={C.ink} />
          <text x={sx(i)} y={sy(v) - 9} textAnchor="middle" fontSize="9.5" fontWeight="800" fill={C.ink} fontFamily={FONT}>{v.toFixed(2)}</text>
        </g>
      ))}
      <g transform={`translate(${m.l + 8}, ${m.t + 12})`}>
        <line x1="0" y1="0" x2="16" y2="0" stroke={C.ink} strokeWidth="2.6" /><text x="21" y="3.5" fontSize="10" fontWeight="700" fill={C.ink} fontFamily={FONT}>지금</text>
        <line x1="64" y1="0" x2="80" y2="0" stroke="#B9C2D4" strokeWidth="2.2" strokeDasharray="5 4" /><text x="85" y="3.5" fontSize="10" fontWeight="700" fill={C.sub} fontFamily={FONT}>1년 전</text>
      </g>
    </svg>
  );
}

// ---------------- 듀레이션 체험 ----------------
function DurationPlay({ baseY }) {
  const [mat, setMat] = useState(10);
  const [dy, setDy] = useState(1.0);
  const y = (baseY || 3.0) / 100;
  // 액면가 채권(쿠폰=수익률)의 맥컬레이 듀레이션 → 수정 듀레이션
  const dMac = (1 + y) / y * (1 - Math.pow(1 + y, -mat));
  const dMod = dMac / (1 + y);
  const chg = -dMod * dy;
  return (
    <div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {[1, 3, 5, 10, 20, 30].map((mv) => (
          <button className="bchip" key={mv} onClick={() => setMat(mv)}
            style={{ border: mat === mv ? "1.5px solid " + C.ink : "1.5px solid " + C.line, background: mat === mv ? C.ink : "#fff", color: mat === mv ? "#fff" : C.sub, borderRadius: 999, padding: "5px 12px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{mv}년물</button>
        ))}
      </div>
      <div style={{ marginTop: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>금리가 이만큼 움직이면</span>
          <span style={{ fontSize: 15, fontWeight: 800, color: dy >= 0 ? C.up : C.down }}>{dy >= 0 ? "+" : ""}{dy.toFixed(1)}%p</span>
        </div>
        <input type="range" min="-3" max="3" step="0.1" value={dy} onChange={(e) => setDy(+e.target.value)} style={{ width: "100%", accentColor: C.ink }} />
      </div>
      <div style={{ background: C.bg, border: HAIR, borderRadius: 8, padding: 16, marginTop: 10, textAlign: "center" }}>
        <div style={{ fontSize: 11.5, color: C.sub }}>{mat}년물 채권 가격은 대략</div>
        <div style={{ fontSize: 30, fontWeight: 800, color: chg >= 0 ? C.up : C.down, fontVariantNumeric: "tabular-nums" }}>{chg >= 0 ? "+" : ""}{chg.toFixed(1)}%</div>
        <div style={{ fontSize: 10.5, color: C.faint, marginTop: 4 }}>수정 듀레이션 약 {dMod.toFixed(1)}년 × 금리 변화 (1차 근사 · 현 수익률 {(y * 100).toFixed(1)}% 가정)</div>
      </div>
      <Sub style={{ marginTop: 10, fontSize: 11.5 }}>
        같은 "채권"이라도 만기가 길수록 금리에 몇 배로 출렁여요. 30년물은 안전자산이 아니라 <b style={{ color: C.ink }}>금리 방향에 거는 큰 베팅</b>에 가까워요 — 채권 ETF를 고를 때 가장 먼저 볼 것이 듀레이션인 이유예요.
      </Sub>
    </div>
  );
}

// ---------------- 브라질 국채 사례 ----------------
function BrazilCase() {
  const [fxChg, setFxChg] = useState(-15);
  const coupon = 10;
  const net = ((1 + coupon / 100) * (1 + fxChg / 100) - 1) * 100;
  return (
    <div>
      <Sub>
        브라질 국채는 <b style={{ color: C.ink }}>연 10% 안팎의 쿠폰</b>과 한·브라질 조세협약에 따른 비과세로 한국에서 꾸준히 인기가 있어요.
        하지만 이 채권은 <b style={{ color: C.ink }}>헤알화(BRL)로 표시</b>돼요 — 손에 쥐는 원화 수익률은 쿠폰에서 환율 변동을 곱한 값이에요.
        헤알화는 지난 15년간 원화 대비 큰 폭의 하락을 반복했고, 그때마다 높은 쿠폰이 상쇄되거나 손실로 뒤집혔어요.
      </Sub>
      <div style={{ marginTop: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>1년 뒤 헤알화가 원화 대비</span>
          <span style={{ fontSize: 15, fontWeight: 800, color: fxChg >= 0 ? C.up : C.down }}>{fxChg >= 0 ? "+" : ""}{fxChg}%</span>
        </div>
        <input type="range" min="-30" max="20" step="1" value={fxChg} onChange={(e) => setFxChg(+e.target.value)} style={{ width: "100%", accentColor: C.ink }} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 10, textAlign: "center" }}>
        <div style={{ background: C.bg, border: HAIR, borderRadius: 8, padding: "12px 6px" }}>
          <div style={{ fontSize: 10, color: C.faint }}>쿠폰 (헤알 기준)</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: C.teal }}>+{coupon}%</div>
        </div>
        <div style={{ background: C.bg, border: HAIR, borderRadius: 8, padding: "12px 6px" }}>
          <div style={{ fontSize: 10, color: C.faint }}>환율 효과</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: fxChg >= 0 ? C.teal : C.coral }}>{fxChg >= 0 ? "+" : ""}{fxChg}%</div>
        </div>
        <div style={{ background: C.ink, borderRadius: 8, padding: "12px 6px" }}>
          <div style={{ fontSize: 10, color: "rgba(255,255,255,0.7)" }}>원화 실수령 (근사)</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>{net >= 0 ? "+" : ""}{net.toFixed(1)}%</div>
        </div>
      </div>
      <Sub style={{ marginTop: 10, fontSize: 10.5, color: C.faint }}>
        수치는 이해를 돕기 위한 예시예요 (표면금리·매입단가·잔존만기·거래비용에 따라 달라요). 요점은 하나 — <b style={{ color: C.sub }}>표시된 수익률 숫자와 손에 쥐는 원화 수익률은 다른 것</b>이고, 그 차이의 대부분이 환율이에요.
      </Sub>
    </div>
  );
}

// ---------------- 루트 ----------------
export function MacroBody({ data }) {
  const baseY = data.curve && data.curve.tenors.includes(10) ? data.curve.now[data.curve.tenors.indexOf(10)] : null;
  const sprSeries = [
    data.sprKr ? { ...data.sprKr, ko: "한국 10년−3년", color: C.ink } : null,
    data.sprUs ? { ...data.sprUs, ko: "미국 10년−2년", color: "#8A6FB8" } : null,
  ].filter(Boolean);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H num="01" main="국고채 수익률 곡선" sub={data.curve ? `한국은행 ECOS · 기준 ${data.curve.date}` : "한국은행 ECOS 연동"} />
          {data.curve ? (
            <>
              <div style={{ marginTop: 10 }}><CurveChart curve={data.curve} /></div>
              <Sub style={{ marginTop: 8, fontSize: 11 }}>
                만기별 금리를 이은 선이에요. 곡선 전체가 오르내리면 통화정책·물가 기대의 변화, 짧은 쪽과 긴 쪽의 기울기가 바뀌면 경기 전망의 변화를 뜻할 때가 많아요. 1년 전(점선)과 비교해 어디가 움직였는지 보세요.
              </Sub>
            </>
          ) : (
            <Sub style={{ padding: "26px 0", textAlign: "center" }}>
              ECOS 키가 아직 연결되지 않았어요.<br />ecos.bok.or.kr에서 무료 키 발급 → GitHub 저장소 → Settings → Secrets → <b style={{ color: C.ink }}>ECOS_API_KEY</b> 등록 → 데이터 갱신 실행.
            </Sub>
          )}
        </Card>
        <Card>
          <H num="02" main="장단기 금리차" sub="장기금리 − 단기금리 · 월별 · 최근 3년" />
          {sprSeries.length ? (
            <>
              <div style={{ marginTop: 10 }}><LineChart series={sprSeries} unit="%p" zero /></div>
              <Sub style={{ marginTop: 8, fontSize: 11 }}>
                보통은 오래 빌려줄수록 금리가 높아 양(+)이에요. 0 아래로 뒤집히는 역전은 역사적으로 경기 둔화에 앞서는 일이 많았지만 — <b style={{ color: C.ink }}>신호이지 타이머가 아니에요</b>. 역전 후 실제 둔화까지 시차도, 예외도 있었어요.
              </Sub>
            </>
          ) : <Sub style={{ padding: "26px 0", textAlign: "center" }}>데이터 갱신 후 표시돼요.</Sub>}
        </Card>
      </div>

      <Card>
        <H num="03" main="금·은·유가" sub="월별 · 최근 3년 · 금·은은 원화 환산, 유가는 달러(WTI)" />
        <div className="cgrid3m" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginTop: 10 }}>
          {[
            data.gold ? { d: data.gold, ko: "금 (원/온스)", color: "#C9A227" } : null,
            data.silver ? { d: data.silver, ko: "은 (원/온스)", color: "#8B95A8" } : null,
            data.wti ? { d: data.wti, ko: "WTI (달러/배럴)", color: "#5A4F45" } : null,
          ].filter(Boolean).map((s) => (
            <div key={s.ko}>
              <LineChart series={[{ ...s.d, ko: s.ko, color: s.color }]} height={180} />
            </div>
          ))}
        </div>
        <Sub style={{ marginTop: 8, fontSize: 10.5, color: C.faint }}>원자재는 이자를 낳지 않아요 — 포트폴리오에서의 역할은 수익이 아니라 분산이에요. 과거 흐름은 미래를 보장하지 않아요.</Sub>
      </Card>

      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H num="04" main="금리가 1%p 움직이면, 내 채권은?" sub="듀레이션 체험 · 1차 근사" />
          <div style={{ marginTop: 12 }}><DurationPlay baseY={baseY} /></div>
        </Card>
        <Card>
          <H num="05" main="사례 연구 — 브라질 국채" sub="쿠폰과 환율의 분해 · 예시 수치" />
          <div style={{ marginTop: 12 }}><BrazilCase /></div>
        </Card>
      </div>

      <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", lineHeight: 1.7, padding: "6px 0 20px" }}>
        뱁새는 수익률을 약속하지 않아요. 금리와 자산의 관계를 스스로 이해하도록 돕는 교육용 도구이며,<br />투자 자문이 아니고 모든 판단과 책임은 본인에게 있습니다.<br />{CREDIT}
      </div>
    </div>
  );
}

export default function MacroApp() {
  const [state, setState] = useState({ st: "loading" });
  const [tries, setTries] = useState(0);
  useEffect(() => { (async () => {
    setState({ st: "loading" });
    try {
      const r = await fetch("./macro.json", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      setState({ st: "ready", data: d });
    } catch (e) { setState({ st: "missing" }); }
  })(); }, [tries]);

  if (state.st === "loading") return (
    <div style={{ minHeight: "50vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT }}>
      <div style={{ textAlign: "center" }}><Bird mood="data" size={64} /><div style={{ fontSize: 12.5, color: C.sub, marginTop: 8 }}>금리 데이터를 불러오는 중…</div></div>
    </div>
  );
  if (state.st === "missing") return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "44px 16px", textAlign: "center", fontFamily: FONT, color: C.ink }}>
      <Bird mood="search" size={80} />
      <div style={{ fontSize: 19, fontWeight: 800, marginTop: 14 }}>금리·원자재 데이터가 아직 없어요</div>
      <Card style={{ marginTop: 16, textAlign: "left" }}>
        <Sub>GitHub 저장소 → <b style={{ color: C.ink }}>Actions</b> → <b style={{ color: C.ink }}>시세 데이터 갱신</b> → <b style={{ color: C.ink }}>Run workflow</b> 실행 후 새로고침하면 macro.json이 만들어져요.</Sub>
      </Card>
      <button onClick={() => setTries(tries + 1)} style={{ marginTop: 14, background: C.blue, color: "#fff", border: "none", borderRadius: RAD.btn, padding: "12px 22px", fontSize: 13.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>다시 확인</button>
    </div>
  );

  return (
    <div className="cwrap" style={{ maxWidth: 1140, margin: "0 auto", padding: "14px 16px 40px", fontFamily: FONT, color: C.ink }}>
      <style>{`@media (max-width: 880px) { .cgrid2 { grid-template-columns: 1fr !important } .cgrid3m { grid-template-columns: 1fr !important } }
        .cwrap svg, .cwrap svg text { user-select: none; -webkit-user-select: none; }
        @media (max-width: 880px) { .bchip { padding: 8px 14px !important; font-size: 12.5px !important } input[type="range"] { height: 30px } }`}</style>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <span style={{ fontSize: 10.5, color: C.faint }}>기준 {state.data.asOf} · 매일 자동 갱신</span>
      </div>
      <MacroBody data={state.data} />
    </div>
  );
}
